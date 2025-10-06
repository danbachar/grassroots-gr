package interfaces;

import core.*;
import input.StaticHostMessageGenerator;
import input.StaticHostMessageGenerator.Mode;
import java.util.Collection;
import movement.RandomStationaryCluster;
import util.Room;

// loosely based on bluetooth 5.0, but only in direct line of sight
//  Optionally supports a churn rate p: for every timeslot, there is a p chance this connection will break (and never come back)
public class BluetoothInterface extends NetworkInterface {
    /**
     * Maximum number of parallel connections allowed -setting id ({@value} ).
     */
    public static final String COMMUNICATION_MODE_S = "communicationMode";

    protected final StaticHostMessageGenerator.Mode mode;

    /**
     * Reads the interface settings from the Settings file
     */
    public BluetoothInterface(Settings s) {
        super(s);
        this.mode = Mode.getByValue(s.getInt(COMMUNICATION_MODE_S));
    }

    /**
     * Copy constructor
     * 
     * @param ni the copied network interface object
     */
    public BluetoothInterface(BluetoothInterface ni) {
        super(ni);
        this.mode = ni.mode;
    }

    public NetworkInterface replicate() {
        return new BluetoothInterface(this);
    }

    /**
     * Tries to connect this host to another host. The other host must be
     * active, within range of this host, and have a clear line of sight of it for
     * the connection to succeed.
     * For simplification, assume both hosts' have only bluetooth network interfaces
     *
     * @param anotherInterface The interface to connect to
     */
    public void connect(NetworkInterface anotherInterface) {
        if (isScanning()
                && anotherInterface.getHost().isRadioActive()
                && isWithinRange(anotherInterface)
                && canCommunicateWith(anotherInterface)
                && !isConnected(anotherInterface)
                && (this != anotherInterface)) {
            // perform costly line of sight check only if all the other conditions hold
            boolean hasClearLineOfSight = hasFreeLineOfSight(this.getHost(), anotherInterface.getHost());

            if (hasClearLineOfSight) {
                Connection con = new LimitedMTUConnection(this.host, this,
                        anotherInterface.getHost(), anotherInterface);
                connect(con, anotherInterface);
            }
        }
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

    /**
     * Returns a string representation of the object.
     * 
     * @return a string representation of the object.
     */
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

    // Constants
    public static final double BANDWIDTH_HZ = 1_000_000.0; // 1 MHz channel bandwidth
    public static final double TX_POWER_DBM = 0.0; // Transmit power in dBm
    public static final double PATH_LOSS_EXPONENT = 2.0; // Free space exponent
    public static final double REFERENCE_DISTANCE_M = 1.0; // Reference distance d0 in meters
    public static final double PATH_LOSS_AT_REF_DB = 40.0; // Empirical PL(d0) at 1m for 2.4 GHz
    public static final double NOISE_FLOOR_DBM = -85.0; // Noise floor (dBm) at 1 MHz BW

    // Gaussian shadowing (optional, set to 0.0 if not needed)
    public static final double SHADOWING_DB = 0.0;

    // Get path loss in dB for a given distance
    private static double getPathLoss(double distanceMeters) {
        if (distanceMeters < REFERENCE_DISTANCE_M) {
            distanceMeters = REFERENCE_DISTANCE_M;
        }
        return PATH_LOSS_AT_REF_DB + 10 * PATH_LOSS_EXPONENT * Math.log10(distanceMeters / REFERENCE_DISTANCE_M)
                + SHADOWING_DB;
    }

    // Get SNR (linear ratio) from transmit power and path loss
    private static double getSNR(double distanceMeters) {
        double receivedPower_dBm = TX_POWER_DBM - getPathLoss(distanceMeters);
        double snr_dB = receivedPower_dBm - NOISE_FLOOR_DBM;
        return Math.pow(10.0, snr_dB / 10.0); // Convert from dB to linear
    }

    // Compute bitrate using Shannon capacity (bps)
    public static double getBitrateBps(double distanceMeters) {
        double snr = getSNR(distanceMeters);
        // Shannon capacity: C = B * log2(1 + SNR)
        double capacity = BANDWIDTH_HZ * Math.log(1 + snr) / Math.log(2.0); // Shannon capacity in bps

        // Scale the capacity to ensure 1 Mbit/s at reference distance (1 meter)
        double snrAtRef = getSNR(REFERENCE_DISTANCE_M);
        double capacityAtRef = BANDWIDTH_HZ * Math.log(1 + snrAtRef) / Math.log(2.0);
        double scalingFactor = 1_000_000.0 / capacityAtRef; // Scale to get 1 Mbit/s at 1m

        double scaledCapacity = capacity * scalingFactor;

        // Avoid exceeding realistic BLE limits
        return Math.min(scaledCapacity, 1_000_000.0);
    }

    public static double getBitrateKiloBytesPerSec(double distanceMeters) {
        return (getBitrateBps(distanceMeters) / 8.0) / 1000.0;
    }

    public static void main(String[] args) {
        for (int d = 0; d <= 200; d += 20) {
            double kbps = BluetoothLEBitrateCalculator.getBitrateKiloBytesPerSec(d);
            System.out.printf("%dm,%.0fkB/s\n", d, kbps);
        }
    }
}