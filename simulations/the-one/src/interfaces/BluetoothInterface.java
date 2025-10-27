package interfaces;

import core.*;
import input.StaticHostMessageGenerator;
import input.StaticHostMessageGenerator.Mode;
import java.util.Collection;
import movement.RandomStationaryCluster;
import util.Room;

// loosely based on bluetooth, but only in direct line of sight
public class BluetoothInterface extends NetworkInterface {
    /**
     * Maximum number of parallel connections allowed -setting id ({@value} ).
     */
    public static final String COMMUNICATION_MODE_S = "communicationMode";

    /**
     * Maximum links this interface can have -setting id {@value}.
     */
    public static final String MAX_NODE_DEGREE_S = "maxDegree";

    protected final StaticHostMessageGenerator.Mode mode;
    protected final int maxDegree;

    /**
     * Reads the interface settings from the Settings file
     */
    public BluetoothInterface(Settings s) {
        super(s);
        this.mode = Mode.getByValue(s.getInt(COMMUNICATION_MODE_S));
        this.maxDegree = s.getInt(MAX_NODE_DEGREE_S);
    }

    /**
     * Copy constructor
     * 
     * @param ni the copied network interface object
     */
    public BluetoothInterface(BluetoothInterface ni) {
        super(ni);
        this.mode = ni.mode;
        this.maxDegree = ni.maxDegree;
    }

    @Override
    public NetworkInterface replicate() {
        return new BluetoothInterface(this);
    }

    /**
     * Tries to connect this host to another host. The other host must be
     * active, within range of this host, have a clear line of sight of it,
     * and have connection capacity, for the connection to succeed.
     * For simplification, assume both hosts' have only bluetooth network interfaces
     *
     * @param anotherInterface The interface to connect to
     */
    @Override
    public void connect(NetworkInterface anotherInterface) {
        if (canConnect(anotherInterface)) {
            // perform costly line of sight check only if all the other conditions hold
            boolean hasClearLineOfSight = hasFreeLineOfSight(this.getHost(), anotherInterface.getHost());

            if (hasClearLineOfSight) {
                Connection con = new LimitedMTUConnection(this.host, this,
                        anotherInterface.getHost(), anotherInterface);
                connect(con, anotherInterface);
            }
        }
    }

    @Override
    public boolean canConnect(NetworkInterface anotherInterface) {
        return this != anotherInterface
            && isScanning()
            && anotherInterface.getHost().isRadioActive()
            && isWithinRange(anotherInterface)
            && canCommunicateWith(anotherInterface)
            && !isConnected(anotherInterface)
            && hasConnectionCapacity(this)
            && hasConnectionCapacity(anotherInterface);
    }

    private boolean hasConnectionCapacity(NetworkInterface ni) {
        // assume interface is BluetoothInterface
        BluetoothInterface btInterface = (BluetoothInterface)ni;

        return ni.getConnections().size() < btInterface.maxDegree;
    }

    private boolean canCommunicateWith(NetworkInterface anotherInterface) {
        // assume the other interface is also BluetoothInterface
        // also assume both this and the other host are both RandomStationaryCluster movement model
        RandomStationaryCluster thisMovement = (RandomStationaryCluster)this.getHost().getMovementModel();

        // intercluster communication mode does not restrict communication between clusters
        // intracluster mode imposes communication only within the cluster
        return this.mode == Mode.INTER_CLUSTER || thisMovement.isInSameCluster(anotherInterface.getHost());
    }

    /**
     * Updates the state of current connections (i.e. tears down connections
     * that are out of range and creates new ones).
     */
    @Override
    public void update() {
        if (optimizer == null) {
            return; /* nothing to do */
        }

        // First break the old ones
        optimizer.updateLocation(this);
        for (int i = 0; i < this.connections.size();) {
            Connection con = this.connections.get(i);
            NetworkInterface anotherInterface = con.getOtherInterface(this);

            // all connections should be up at this stage
            assert con.isUp() : "Connection " + con + " was down!";
            DTNHost from = this.getHost();
            DTNHost to = anotherInterface.getHost();
            double p = this.getRandomDouble();
            if (!isWithinRange(anotherInterface) || !hasFreeLineOfSight(from, to)) {
                disconnect(con, anotherInterface);
                connections.remove(i);
            } else {
                i++;
            }
        }
        // Then find new possible connections
        Collection<NetworkInterface> interfaces = optimizer.getNearInterfaces(this);
        for (NetworkInterface i : interfaces) {
            connect(i);
        }

        /* update all connections */
        for (Connection con : getConnections()) {
            con.update();
        }
    }

    private boolean hasFreeLineOfSight(DTNHost from, DTNHost to) {
        var hostLocation = from.getLocation();
        var otherLocation = to.getLocation();
        return isFreePath(hostLocation, otherLocation);
    }

    /**
     * Creates a connection to another host. This method does not do any checks
     * on whether the other node is in range or active
     * 
     * @param anotherInterface The interface to create the connection to
     */
    @Override
    public void createConnection(NetworkInterface anotherInterface) {
        if (!isConnected(anotherInterface) && (this != anotherInterface)) {
            Connection con = new LimitedMTUConnection(this.host, this,
                    anotherInterface.getHost(), anotherInterface);
            connect(con, anotherInterface);
        }
    }

    /**
     * Returns the transmit speed to another interface based on the
     * distance to this interface
     * 
     * @param ni The other network interface
     */
    @Override
    public int getTransmitSpeed(NetworkInterface ni) {
        double distance;

        /* distance to the other interface */
        distance = ni.getLocation().distance(this.getLocation());

        if (distance >= this.transmitRange) {
            return 0;
        }

        return (int) Math.floor(BluetoothLEBitrateCalculator.getBitrateBps(distance));
    }

    public int getMaxDegree() {
        return this.maxDegree;
    }

    /**
     * Returns a string representation of the object.
     * 
     * @return a string representation of the object.
     */
    @Override
    public String toString() {
        return "BluetoothInterface " + super.toString();
    }

    private boolean isFreePath(Coord thisHostLocation, Coord thatHostLocation) {
        // Checks if there is a room between the two hosts which would obstruct clear line of sight
        // TODO: check if it works with a polygon room (L shape)
        for (Room room : DTNSim.allRooms) {
            boolean lineIntersectsRoom = room.lineBetweenCoordsIntersectsRoom(thisHostLocation, thatHostLocation);
            if (lineIntersectsRoom) {
                return false;
            }
        }

        return true;
    }
}

class BluetoothLEBitrateCalculator {

    public static final double BANDWIDTH_HZ = 2_000_000.0; // 2 MHz channel bandwidth for BLE
    public static final double TX_POWER_DBM = 12; // Transmit power in dBm from testbed results using Raspberry Pi 3b+
    public static final double NOISE_FLOOR_DBM = -85.0; // Noise floor (dBm) at 1 MHz BW TODO: measure this
    public static final double ALPHA = 2.271; // Path loss exponent from empirical data

    // Empirical data: Distance (m) -> Mean RSSI (dBm)
    private static final java.util.TreeMap<Double, Double> empiricalRSSI = new java.util.TreeMap<>();

    // Use testbed bluetooth measurements
    static {
        // Path Loss = TX_POWER_DBM - Mean RSSI
        empiricalRSSI.put(0.0, TX_POWER_DBM - (-17.21));
        empiricalRSSI.put(0.5, TX_POWER_DBM - (-39.51));
        empiricalRSSI.put(1.0, TX_POWER_DBM - (-46.93));
        empiricalRSSI.put(1.5, TX_POWER_DBM - (-57.95));
        empiricalRSSI.put(2.0, TX_POWER_DBM - (-67.95));
        empiricalRSSI.put(5.0, TX_POWER_DBM - (-72.85));
        empiricalRSSI.put(7.5, TX_POWER_DBM - (-82.49));
        empiricalRSSI.put(10.0, TX_POWER_DBM - (-88.79));
        empiricalRSSI.put(20.0, TX_POWER_DBM - (-97.20));
        empiricalRSSI.put(30.0, TX_POWER_DBM - (-93.50));
        empiricalRSSI.put(60.0, TX_POWER_DBM - (-91.48));
        empiricalRSSI.put(70.0, TX_POWER_DBM - (-94.57));
        empiricalRSSI.put(80.0, TX_POWER_DBM - (-95.39));
        empiricalRSSI.put(90.0, TX_POWER_DBM - (-92.86));
        empiricalRSSI.put(110.0, TX_POWER_DBM - (-95.17));
        empiricalRSSI.put(120.0, TX_POWER_DBM - (-95.86));
    }

    // Get RSSI in dBm for a given distance using log-distance path loss model
    // Formula: RSSI_d = A - 10*alpha*log10(d/d0)
    // where A is the RSSI at distance d0=0.0m (reference distance)
    // and d is the target distance from d0
    // Returns null for distances outside the empirical range
    private static Double getRSSI(double distanceMeters) {
        if (distanceMeters < 0) {
            return null;
        }

        // use the nearest smaller key as the reference point (d0)
        double d0 = empiricalRSSI.floorKey(distanceMeters);
        double A = empiricalRSSI.get(d0); // RSSI at d0

        if (distanceMeters == 0.0) {
            return A; // no interpolation
        }

        if (distanceMeters > empiricalRSSI.lastKey()) {
            return null;
        }

        // Use log-distance path loss model: RSSI_d = A - 10*alpha*log10(d)
        // Apply the formula: RSSI_d = A - 10*alpha*log10(d/d0)
        if (d0 == 0.0) {
            d0 = 0.01; // avoid null division through log(0)
        }
        double rssi = A - 10.0 * ALPHA * Math.log10(distanceMeters / d0);
        
        return rssi;
    }

    // Get SNR (linear ratio) from transmit power and path loss
    private static double getSNR(double distanceMeters) {
        double receivedPower = TX_POWER_DBM - getRSSI(distanceMeters);
        double SNR = receivedPower - NOISE_FLOOR_DBM;
        return Math.pow(10.0, SNR / 10.0); // Convert from dB to linear
    }

    // Compute bitrate using Shannon capacity (bps)
    public static double getBitrateBps(double distanceMeters) {
        double snr = getSNR(distanceMeters);
        // Shannon capacity: C = B * log2(1 + SNR)
        double capacity = BANDWIDTH_HZ * Math.log(1 + snr) / Math.log(2.0); // Shannon capacity in bps

        // Use 1M PHY
        return Math.max(0, Math.min(capacity, 1_000_000.0));
    }

    public static double getBitrateKiloBytesPerSec(double distanceMeters) {
        return (getBitrateBps(distanceMeters) / 8.0) / 1000.0;
    }

    public static void main(String[] args) {
        System.out.println("Bitrate based on empirical data:");
        double d = 0.0;
        double kbps = BluetoothLEBitrateCalculator.getBitrateKiloBytesPerSec(d);
        System.out.printf("%.1fm, %.2fkB/s\n", d, kbps);

        d = 0.5;
        kbps = BluetoothLEBitrateCalculator.getBitrateKiloBytesPerSec(d);
        System.out.printf("%.1fm, %.2fkB/s\n", d, kbps);

        d = 1.0;
        kbps = BluetoothLEBitrateCalculator.getBitrateKiloBytesPerSec(d);
        System.out.printf("%.1fm, %.2fkB/s\n", d, kbps);

        d = 1.5;
        kbps = BluetoothLEBitrateCalculator.getBitrateKiloBytesPerSec(d);
        System.out.printf("%.1fm, %.2fkB/s\n", d, kbps);

        d = 2.0;
        kbps = BluetoothLEBitrateCalculator.getBitrateKiloBytesPerSec(d);
        System.out.printf("%.1fm, %.2fkB/s\n", d, kbps);

        d = 5.0;
        kbps = BluetoothLEBitrateCalculator.getBitrateKiloBytesPerSec(d);
        System.out.printf("%.1fm, %.2fkB/s\n", d, kbps);

        d = 7.5;
        kbps = BluetoothLEBitrateCalculator.getBitrateKiloBytesPerSec(d);
        System.out.printf("%.1fm, %.2fkB/s\n", d, kbps);

        d = 10.0;
        kbps = BluetoothLEBitrateCalculator.getBitrateKiloBytesPerSec(d);
        System.out.printf("%.1fm, %.2fkB/s\n", d, kbps);

        d = 20.0;
        kbps = BluetoothLEBitrateCalculator.getBitrateKiloBytesPerSec(d);
        System.out.printf("%.1fm, %.2fkB/s\n", d, kbps);

        d = 30.0;
        kbps = BluetoothLEBitrateCalculator.getBitrateKiloBytesPerSec(d);
        System.out.printf("%.1fm, %.2fkB/s\n", d, kbps);

        d = 40.0;
        kbps = BluetoothLEBitrateCalculator.getBitrateKiloBytesPerSec(d);
        System.out.printf("%.1fm, %.2fkB/s\n", d, kbps);

        d = 50.0;
        kbps = BluetoothLEBitrateCalculator.getBitrateKiloBytesPerSec(d);
        System.out.printf("%.1fm, %.2fkB/s\n", d, kbps);

        d = 60.0;
        kbps = BluetoothLEBitrateCalculator.getBitrateKiloBytesPerSec(d);
        System.out.printf("%.1fm, %.2fkB/s\n", d, kbps);

        d = 70.0;
        kbps = BluetoothLEBitrateCalculator.getBitrateKiloBytesPerSec(d);
        System.out.printf("%.1fm, %.2fkB/s\n", d, kbps);

        d = 80.0;
        kbps = BluetoothLEBitrateCalculator.getBitrateKiloBytesPerSec(d);
        System.out.printf("%.1fm, %.2fkB/s\n", d, kbps);

        d = 90.0;
        kbps = BluetoothLEBitrateCalculator.getBitrateKiloBytesPerSec(d);
        System.out.printf("%.1fm, %.2fkB/s\n", d, kbps);

        d = 100.0;
        kbps = BluetoothLEBitrateCalculator.getBitrateKiloBytesPerSec(d);
        System.out.printf("%.1fm, %.2fkB/s\n", d, kbps);

        d = 110.0;
        kbps = BluetoothLEBitrateCalculator.getBitrateKiloBytesPerSec(d);
        System.out.printf("%.1fm, %.2fkB/s\n", d, kbps);

        d = 120.0;
        kbps = BluetoothLEBitrateCalculator.getBitrateKiloBytesPerSec(d);
        System.out.printf("%.1fm, %.2fkB/s\n", d, kbps);
    }
}