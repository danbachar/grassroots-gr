package util;

import core.Coord;
import core.DTNHost;
import java.util.ArrayList;
import java.util.List;

public class HostCluster {
    public final int id;
    private final List<DTNHost> hosts;
    private final int maximumClusterCardinality;
    private final Coord clusterStart;
    private final double clusterSize;

    /**
     * Create a new host cluster with given ID and maximum size
     * 
     * @param id Cluster ID
     * @param maximumClusterCardinality Maximum number of hosts in the cluster
     * @param clusterSize is the size of the cluster in meters: every cluster gets the same size cell to spawn at
     * @param room is the room in which the cluster is located
     * @param offsetX X offset for the room beginning
     * @param offsetY Y offset for the room beginning
     */

    public HostCluster(int id, int maximumClusterCardinality, double clusterSize, Room room, double offsetX, double offsetY) {
        this.id = id;
        this.hosts = new ArrayList<>();
        this.maximumClusterCardinality = maximumClusterCardinality;
        this.clusterSize = clusterSize;
        
        // Calculate potential grid dimensions based on room bounds
        int clustersPerRow = (int) (room.getWidth() / clusterSize);
        int clustersPerColumn = (int) (room.getHeight() / clusterSize);
        
        // Find valid cluster positions within the polygon TODO: move me to some one-time init
        List<int[]> validPositions = new ArrayList<>();
        for (int row = 0; row < clustersPerColumn; row++) {
            for (int col = 0; col < clustersPerRow; col++) {
                // Calculate cluster start point (top-left corner)
                double startX = offsetX + col * clusterSize;
                double startY = offsetY + row * clusterSize;
                Coord clusterStart = new Coord(startX, startY);

                // Check if cluster start is within the room polygon
                boolean isStartWithinRoom = room.isCoordinateInRoom(clusterStart);
                if (isStartWithinRoom) {
                    double endX = startX + clusterSize;
                    double endY = startY + clusterSize;
                    Coord clusterEnd = new Coord(endX, endY);

                    boolean isEndWithinRoom = room.isCoordinateInRoom(clusterEnd);
                    if (isEndWithinRoom) {
                        validPositions.add(new int[]{col, row});
                    }
                }
            }
        }
        
        if (id >= validPositions.size()) {
            throw new IllegalStateException("Cannot place cluster ID " + id + ": only " + validPositions.size() + " valid positions available");
        }

        int[] position = validPositions.get(id);
        int col = position[0];
        int row = position[1];
        this.clusterStart = new Coord(offsetX + col * clusterSize, offsetY + row * clusterSize);
    }

    public int getID() {
        return this.id;
    }

    public List<DTNHost> getHosts() {
        return this.hosts;
    }

    public int getMaximumClusterCardinality() {
        return this.maximumClusterCardinality;
    }

    public int addHost(DTNHost host) {
        if (hosts.size() >= maximumClusterCardinality) {
            throw new IllegalStateException("Cannot add more hosts to the cluster: maximum size reached");
        }

        hosts.add(host);
        return hosts.size();
    }

    public boolean coordInCluster(Coord coord) {
        double x = coord.getX();
        double y = coord.getY();
        double clusterXStart = clusterStart.getX();
        double clusterXEnd = clusterXStart + clusterSize;
        double clusterYStart = clusterStart.getY();
        double clusterYEnd = clusterYStart + clusterSize;

        return x >= clusterXStart && x <= clusterXEnd
            && y >= clusterYStart && y <= clusterYEnd;
    }

    public Coord getClusterStart() {
        return clusterStart;
    }

    public double getClusterSize() {
        return clusterSize;
    }
}
