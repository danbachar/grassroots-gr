/*
 * Copyright 2010 Aalto University, ComNet
 * Released under GPLv3. See LICENSE.txt for details.
 */
package movement;

import core.*;
import java.util.Optional;
import util.HostCluster;
import util.Room;

/**
 * A movement model where nodes are placed randomly within a polygon area and
 * remain stationary throughout the simulation.
 */
public class RandomStationaryCluster extends MovementModel {

    public static final String HOSTS_PER_CLUSTER_S = "hostsPerCluster";
    public static final String NUMBER_CLUSTERS_S = "numberOfClusters";
    public static final String CLUSTER_SIZE_S = "clusterSize";
    public static final String CLUSTER_ID_S = "clusterID";
    public static final String OFFSET_X_S = "offsetX";
    public static final String OFFSET_Y_S = "offsetY";

    public final int clusterID;
    public final int xOffset;
    public final int yOffset;
    public final int hostsPerCluster;
    public final int numberOfClusters;
    public final double clusterSize;

    private Coord location;
    private final Room constrainedRoom;
    private final HostCluster hostCluster;

    /**
     * Reads the interface settings from the Settings file
     */
    public RandomStationaryCluster(Settings s) {
        super(s);

        this.xOffset = s.getInt(OFFSET_X_S);
        this.yOffset = s.getInt(OFFSET_Y_S);
        
        this.hostsPerCluster = s.getInt(HOSTS_PER_CLUSTER_S);
        this.numberOfClusters = s.getInt(NUMBER_CLUSTERS_S);
        this.clusterSize = s.getDouble(CLUSTER_SIZE_S);
        this.clusterID = s.getInt(CLUSTER_ID_S);

        // get random room to spawn in
        int randomIndex = rng.nextInt(DTNSim.allRooms.size());
        Room room = DTNSim.allRooms.get(randomIndex);
        this.constrainedRoom = room;

        // get random cluster to spawn in
        this.hostCluster = this.getOrCreateHostCluster(this.clusterID, clusterSize, room);
        // this.hostCluster.addHost(this.getHost());
        // TODO: this is not possible: cannot access host from movement. instead, get x and y of cluster using width and height, assign to that area
    }

    protected RandomStationaryCluster(RandomStationaryCluster rsc) {
        super(rsc);

        this.xOffset = rsc.xOffset;
        this.yOffset = rsc.yOffset;

        this.hostsPerCluster = rsc.hostsPerCluster;
        this.numberOfClusters = rsc.numberOfClusters;
        this.clusterSize = rsc.clusterSize;
        this.clusterID = rsc.clusterID;

        // get random room to spawn in
        int randomIndex = rng.nextInt(DTNSim.allRooms.size());
        Room room = DTNSim.allRooms.get(randomIndex);
        this.constrainedRoom = room;

        this.hostCluster = this.getOrCreateHostCluster(clusterID, clusterSize, this.constrainedRoom);
    }

    @Override
    public RandomStationaryCluster replicate() {
        return new RandomStationaryCluster(this);
    }

    /**
     * Generates a random coordinate within the specified rectangle
     *
     * @return Random coordinate within the rectangle
     */
    private Coord generateRandomLocation() {
        assert rng != null : "MovementModel not initialized!";

        Coord randomLocation;
        boolean inRoom, inCluster;
        Coord start = this.hostCluster.getClusterStart();
        double clusterSize = this.hostCluster.getClusterSize();
        double centerX = start.getX() + (clusterSize / 2);
        double centerY = start.getY() + (clusterSize / 2);
        double halfR = clusterSize/2;
        double rSqrtHalf = clusterSize * Math.sqrt(0.5);
        do {
            double epsilon = rng.nextDouble(0, halfR);

            int addOrSubstractX = rng.nextBoolean() ? 1 : -1;
            double x = centerX + addOrSubstractX * epsilon;

            int addOrSubstractY = rng.nextBoolean() ? 1 : -1;
            double y = centerY + addOrSubstractY * epsilon;
            randomLocation = new Coord(x, y);
            inCluster = this.hostCluster.coordInCluster(randomLocation);
        } while (!inCluster);

        return randomLocation;
    }

    /**
     * Returns the randomly generated initial location
     *
     * @return the initial location of this node
     */
    @Override
    public Coord getInitialLocation() {
        this.location = generateRandomLocation();

        return this.location;
    }

    /**
     * Returns a single coordinate path (node stays at its initial location)
     *
     * @return a single coordinate path
     */
    @Override
    public Path getPath() {
        Path p = new Path(0); // Speed 0 = stationary
        p.addWaypoint(location);
        return p;
    }

    @Override
    public double nextPathAvailable() {
        return Double.MAX_VALUE; // no new paths available (stationary)
    }

    /**
     * Get or create a host cluster. It generates or fetches a cluster for this movement model.
     * @param clusterID is the ID of the cluster
     * @param clusterSize is the size of the cluster in meters: every cluster gets the same size cell to spawn at
     * @param room is the room in which the cluster is located
     */
    private HostCluster getOrCreateHostCluster(int clusterID, double clusterSize, Room room) {
        var cluster = DTNSim.allHostClusters.stream().filter(c -> c.getID() == clusterID).findAny();
        if (cluster.isEmpty()) {
            var val = new HostCluster(clusterID, this.hostsPerCluster, clusterSize, room, this.xOffset, this.yOffset);
            DTNSim.allHostClusters.add(val);
            cluster = Optional.of(val);
        }
        
        return cluster.get();
    }

    public boolean isInSameCluster(DTNHost otherHost) {
        int otherID = ((RandomStationaryCluster) otherHost.getMovementModel()).hostCluster.getID();
        int thisID = this.hostCluster.getID();

        return thisID == otherID;
    }
}
