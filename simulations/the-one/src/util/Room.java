package util;

import core.Coord;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Optional;

// Helper class to store room dimensions
public class Room {

    private final List<Coord> polygon;
    private final List<Line> segments;
    private final Coord origin;

    public Room(String filePath, String name, double offsetX, double offsetY) {
        this.polygon = readPolygon(filePath);
        if (polygon.isEmpty()) {
            System.err.println("LectureTakerMovement: No valid polygon found in file " + filePath);
        }
        var segments = new ArrayList<Line>();
        for (int i = 0; i < polygon.size(); i++) {
            Coord start = polygon.get(i);
            Coord end = polygon.get((i + 1) % polygon.size()); // wrap around to first vertex
            segments.add(new Line(start, end));
        }
        this.segments = segments;

        origin = new Coord(offsetX, offsetY);
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

        // Check if coordinate is exactly one of the polygon vertices
        if (polygon.contains(coordinate)) {
            return true;
        }

        // check if coordinate is located on one of the polygon edges
        boolean isOnEdge = this.segments.stream().anyMatch(segment -> segment.isPointOnSegment(coordinate));
        if (isOnEdge) {
            return true;
        }

        // Check if coordinate is inside the polygon using ray casting
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
            var hasIntersections = line.getSegmentInterception(segment).isPresent();
            if (hasIntersections) {
                return true;
            }
        }

        Line segment = new Line(last, polygon.getFirst());

        return line.getSegmentInterception(segment).isPresent();
    }

    private int getIntersections(Coord coordinate) {
        Line ray = new Line(this.origin, coordinate);

        // ray-casting algorithm: if number of intersections of ray from origin to coord with polygon is even, point is outside
        // else, point is inside
        // https://stackoverflow.com/a/218081
        // TODO: not efficient, not pretty, should be made better, but easy for now
        HashSet<Coord> intersections = new HashSet<>();
        for (int i = 1; i < polygon.size(); i++) {
            Coord previousPoint = polygon.get(i - 1);
            Coord current = polygon.get(i);

            Line segment = new Line(previousPoint, current);
            var intersection = ray.getSegmentInterception(segment);
            if (intersection.isPresent()) {
                intersections.add(intersection.get());
            }
        }

        Coord last = polygon.getLast();
        Line segment = new Line(last, polygon.getFirst());
        var intersection = ray.getSegmentInterception(segment);
        if (intersection.isPresent()) {
            intersections.add(intersection.get());
        }

        return intersections.size();
    }

    public double getWidth() {
        var maxXPolygonCoordinate = this.polygon.stream().mapToDouble(Coord::getX).max().getAsDouble();
        var minXPolygonCoordinate = this.polygon.stream().mapToDouble(Coord::getX).min().getAsDouble();
        return maxXPolygonCoordinate - minXPolygonCoordinate;
    }

    public double getHeight() {
        var maxYPolygonCoordinate = this.polygon.stream().mapToDouble(Coord::getY).max().getAsDouble();
        var minYPolygonCoordinate = this.polygon.stream().mapToDouble(Coord::getY).min().getAsDouble();
        return maxYPolygonCoordinate - minYPolygonCoordinate;
    }

    public record Line(Coord start, Coord end) {

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
        public Optional<Coord> getSegmentInterception(Line segment) {
            double distance1 = this.start().distance(this.end());
            double distance2 = segment.start().distance(segment.end());

            if (distance1 == 0 || distance2 == 0) {
                return Optional.empty();
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
                return Optional.empty();
            }

            double ua = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denominator;
            double ub = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / denominator;

            // is the intersection along the segments
            if (ua < 0 || ua > 1 || ub < 0 || ub > 1) {
                return Optional.empty();
            }

            double x = x1 + ua * (x2 - x1);
            double y = y1 + ua * (y2 - y1);

            var point = new Coord(x, y);
            return Optional.of(point);
        }

        public boolean isPointOnSegment(
                final Coord point) {
            final double crossProduct
                    = (point.getY() - start.getY()) * (end.getX() - start.getX())
                    - (point.getX() - start.getX()) * (end.getY() - start.getY());
            if (Math.abs(crossProduct) > 0.0000001) {
                return false;
            }

            final double dotProduct
                    = (point.getX() - start.getX()) * (end.getX() - start.getX())
                    + (point.getY() - start.getY()) * (end.getY() - start.getY());
            if (dotProduct < 0) {
                return false;
            }

            final double squaredLength
                    = (end.getX() - start.getX()) * (end.getX() - start.getX())
                    + (end.getY() - start.getY()) * (end.getY() - start.getY());
            return dotProduct <= squaredLength;
        }
    }
}
