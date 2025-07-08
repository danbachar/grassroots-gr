/*
 * Copyright 2010 Aalto University, ComNet
 * Released under GPLv3. See LICENSE.txt for details.
 */
package movement;

import core.*;
import util.Room;

/**
 * A movement model where nodes are placed randomly within a polygon area and
 * remain stationary throughout the simulation.
 */
public class RandomStationaryConstrained extends MovementModel {

    public static final String OFFSET_X_S = "offsetX";
    public static final String OFFSET_Y_S = "offsetY";

    public final int xOffset;
    public final int yOffset;

    private Coord location;
    private final double height;
    private final double width;
    private final Room constrainedRoom;

    /**
     * Reads the interface settings from the Settings file
     */
    public RandomStationaryConstrained(Settings s) {
        super(s);

        this.xOffset = s.getInt(OFFSET_X_S);
        this.yOffset = s.getInt(OFFSET_Y_S);

        // get random room to spawn in
        int randomIndex = rng.nextInt(DTNSim.allRooms.size());
        Room room = DTNSim.allRooms.get(randomIndex);
        this.constrainedRoom = room;
        var polygonCoords = room.getPolygon();

        var maxXPolygonCoordinate = polygonCoords.stream().mapToDouble(Coord::getX).max().getAsDouble();
        var minXPolygonCoordinate = polygonCoords.stream().mapToDouble(Coord::getX).min().getAsDouble();
        this.width = maxXPolygonCoordinate - minXPolygonCoordinate;

        var maxYPolygonCoordinate = polygonCoords.stream().mapToDouble(Coord::getY).max().getAsDouble();
        var minYPolygonCoordinate = polygonCoords.stream().mapToDouble(Coord::getY).min().getAsDouble();
        this.height = maxYPolygonCoordinate - minYPolygonCoordinate;
    }

    protected RandomStationaryConstrained(RandomStationaryConstrained rsc) {
        super(rsc);

        this.xOffset = rsc.xOffset;
        this.yOffset = rsc.yOffset;

        // get random room to spawn in
        int randomIndex = rng.nextInt(DTNSim.allRooms.size());
        Room room = DTNSim.allRooms.get(randomIndex);
        this.constrainedRoom = room;
        
        var polygonCoords = room.getPolygon();

        var maxXPolygonCoordinate = polygonCoords.stream().mapToDouble(Coord::getX).max().getAsDouble();
        var minXPolygonCoordinate = polygonCoords.stream().mapToDouble(Coord::getX).min().getAsDouble();
        this.width = maxXPolygonCoordinate - minXPolygonCoordinate;

        var maxYPolygonCoordinate = polygonCoords.stream().mapToDouble(Coord::getY).max().getAsDouble();
        var minYPolygonCoordinate = polygonCoords.stream().mapToDouble(Coord::getY).min().getAsDouble();
        this.height = maxYPolygonCoordinate - minYPolygonCoordinate;
    }

    @Override
    public RandomStationaryConstrained replicate() {
        return new RandomStationaryConstrained(this);
    }

    /**
     * Generates a random coordinate within the specified rectangle
     *
     * @return Random coordinate within the rectangle
     */
    private Coord generateRandomLocation() {
        assert rng != null : "MovementModel not initialized!";

        Coord randomLocation;
        boolean inRoom;
        do {
            double x = this.xOffset + rng.nextDouble() * this.width;
            double y = this.yOffset + rng.nextDouble() * this.height;
            randomLocation = new Coord(x, y);
            inRoom = this.constrainedRoom.isCoordinateInRoom(randomLocation);
        } while (!inRoom);

        return randomLocation;
    }

    /**
     * Returns the randomly generated initial location
     *
     * @return the initial location of this node
     */
    @Override
    public Coord getInitialLocation() {
        if (this.location == null) {
            // generate random location if not already set
            this.location = generateRandomLocation();
        }

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
}
