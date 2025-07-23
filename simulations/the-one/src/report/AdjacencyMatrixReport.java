/*
 * Copyright 2024 Aalto University, ComNet
 * Released under GPLv3. See LICENSE.txt for details.
 */

package report;

import java.util.List;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

import core.Connection;
import core.DTNHost;

/**
 * Adjacency matrix snapshot report. Reports the adjacency matrix of all nodes 
 * (1 for connected, 0 for not connected) every configurable amount of seconds.
 * Each timestamp creates a complete n×n adjacency matrix showing the connectivity 
 * state of the entire network at that point in time.
 * 
 * The output format is:
 * [timestamp]
 * # Node IDs: node1 node2 node3 ...
 * 0 1 0 1 ...  (connections for node1)
 * 1 0 1 0 ...  (connections for node2)
 * 0 1 0 1 ...  (connections for node3)
 * ...
 * 
 * Where 1 indicates connected nodes and 0 indicates no connection.
 * The matrix is symmetric since connections are bidirectional.
 * The diagonal elements are 1 since nodes are considered connected to themselves.
 */
public class AdjacencyMatrixReport extends SnapshotReport {
    
    /**
     * Constructor. Reads the settings and initializes the report module.
     */
    public AdjacencyMatrixReport() {
        super();
    }
    
    @Override
    protected void writeSnapshot(DTNHost host) {
        // This method is not used in this implementation since we override
        // createSnapshot to generate the complete adjacency matrix
    }
    
    @Override
    protected void createSnapshot(List<DTNHost> hosts) {
        write("[" + (int)getSimTime() + "]"); /* simulation time stamp */
        
        // Create a sorted list of all hosts for consistent ordering
        List<DTNHost> sortedHosts = new ArrayList<DTNHost>(hosts);
        Collections.sort(sortedHosts, (h1, h2) -> Integer.compare(h1.getAddress(), h2.getAddress()));
        
        // If we have a subset of reported nodes, filter the hosts
        if (this.reportedNodes != null) {
            sortedHosts.removeIf(h -> !this.reportedNodes.contains(h.getAddress()));
        }
        
        int n = sortedHosts.size();
        if (n == 0) return; // No hosts to report
        
        // Write header with node IDs
        StringBuilder headerBuilder = new StringBuilder("# Node IDs:");
        for (DTNHost host : sortedHosts) {
            headerBuilder.append(" ").append(host.getAddress());
        }
        write(headerBuilder.toString());
        
        // Create adjacency matrix
        int[][] adjacencyMatrix = new int[n][n];
        
        // Initialize diagonal to 1 (nodes are connected to themselves)
        for (int i = 0; i < n; i++) {
            adjacencyMatrix[i][i] = 1;
        }
        
        // Fill the adjacency matrix
        for (int i = 0; i < n; i++) {
            DTNHost host = sortedHosts.get(i);
            for (Connection con : host.getConnections()) {
                DTNHost otherHost = con.getOtherNode(host);
                int otherIndex = sortedHosts.indexOf(otherHost);
                if (otherIndex != -1) { // Other host is in our sorted list
                    adjacencyMatrix[i][otherIndex] = 1;
                }
            }
        }
        
        // Write the matrix rows
        for (int i = 0; i < n; i++) {
            StringBuilder rowBuilder = new StringBuilder();
            for (int j = 0; j < n; j++) {
                if (j > 0) rowBuilder.append(" ");
                rowBuilder.append(adjacencyMatrix[i][j]);
            }
            write(rowBuilder.toString());
        }
    }
}
