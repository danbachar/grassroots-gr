package util;

import core.Coord;

import java.util.ArrayList;
import java.util.List;

// Helper class to store room dimensions
public class Room {
    private final List<Coord> polygon;

    public Room(String filePath, String name) {
        this.polygon = readPolygon(filePath);
        if (polygon.isEmpty()) {
            System.err.println("LectureTakerMovement: No valid polygon found in file " + filePath);
        }
    }

    public List<Coord> getPolygon() {
        return this.polygon;
    }

    public static ArrayList<Coord> readPolygon(String filePath) {
        ArrayList<Coord> coords = new ArrayList<>();
        try (java.io.BufferedReader reader = new java.io.BufferedReader(new java.io.FileReader(filePath))) {
            String line;
            while ((line = reader.readLine()) != null) {
                String[] parts = line.substring(line.indexOf('(') + 1, line.indexOf(')')).split("\\s+");
                double x = Double.parseDouble(parts[0]);
                double y = Double.parseDouble(parts[1]);
                x = Math.round(x * 1000.0) / 1000.0;
                y = Math.round(y * 1000.0) / 1000.0;
                coords.add(new Coord(x, y));
            }
        } catch (java.io.IOException e) {
            System.err.println("Error parsing WKT file: " + filePath + ". " + e.getMessage());
            return new ArrayList<>();
        }
        return coords;
    }

    public boolean isCoordinateInRoom(Coord coordinate) {
        if (polygon.isEmpty() || polygon.size() < 2) {
            System.err.println("Cannot calculate line intersection with room: room has less than two points");
            return false;
        }

        int intersections = getIntersections(coordinate);

        return intersections % 2 == 1;
    }

    public boolean lineBetweenCoordsIntersectsRoom(Coord p1, Coord p2) {
        if (polygon.isEmpty() || polygon.size() < 2) {
            System.err.println("Cannot calculate line intersection with room: room has less than two points");
            return false;
        }

        Line line = new Line(p1, p2);

        // map polygon to lines
        // TODO: not efficient, not pretty, should be made better, but easy for now
        Coord last = polygon.getFirst();
        for (int i = 1; i < polygon.size(); i++) {
            Coord previousPoint = polygon.get(i - 1);
            Coord current = polygon.get(i);
            last = current;

            Line segment = new Line(previousPoint, current);
            if (line.hasIntersectionWithSegment(segment)) {
                return true;
            }
        }

        Line segment = new Line(last, polygon.getFirst());

        return line.hasIntersectionWithSegment(segment);
    }

    private int getIntersections(Coord coordinate) {
        Coord origin = new Coord(0, 0);
        Line ray = new Line(origin, coordinate);

        // ray-casting algorithm: if number of intersections of ray from origin to coord with polygon is even, point is outside
        // else, point is inside
        // https://stackoverflow.com/a/218081

        // TODO: not efficient, not pretty, should be made better, but easy for now
        Coord last = polygon.getFirst();
        int intersections = 0;
        for (int i = 1; i < polygon.size(); i++) {
            Coord previousPoint = polygon.get(i - 1);
            Coord current = polygon.get(i);
            last = current;

            Line segment = new Line(previousPoint, current);
            boolean hit = ray.hasIntersectionWithSegment(segment);
            if (hit) {
                intersections += 1;
            }
        }

        Line segment = new Line(last, polygon.getFirst());
        if (ray.hasIntersectionWithSegment(segment)) {
            intersections += 1;
        }
        return intersections;
    }

    private record Line(Coord start, Coord end) {

        /*
             * Line intercept math by Paul Bourke
             * http://paulbourke.net/geometry/pointlineplane/
             *
             * - Returns the coordinate of the intersection point
             * - Returns FALSE if the lines don't intersect
             *
             * Coordinates x1, y1, x2 and y2 designate the start and end point of the first
             * line
             * Coordinates x3, y3, x4 and y4 designate the start and end point of the second
             * line
             */
            private boolean hasIntersectionWithSegment(Line segment) {
                double distance1 = this.start().distance(this.end());
                double distance2 = segment.start().distance(segment.end());

                if (distance1 == 0 || distance2 == 0) {
                    return false;
                }

                // Coordinates x1, y1, x2 and y2 designate the start and end point of the line
                // Coordinates x3, y3, x4 and y4 designate the start and end point of the (polygon) segment
                double x1 = this.start().getX();
                double x2 = this.end().getX();
                double x3 = segment.start().getX();
                double x4 = segment.end().getX();
                double y1 = this.start().getY();
                double y2 = this.end().getY();
                double y3 = segment.start().getY();
                double y4 = segment.end().getY();

                double denominator = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1);

                // Lines are parallel
                if (denominator == 0) {
                    return false;
                }

                double ua = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denominator;
                double ub = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / denominator;

                // is the intersection along the segments
                if (ua < 0 || ua > 1 || ub < 0 || ub > 1) {
                    return false;
                }

                return true;
            }
        }

}
