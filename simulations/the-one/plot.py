from typing import Optional
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pickle
from load_data import Message, Hop, HostInfo, Topology, Configuration # types needed otherwise the pickle load won't work
import os
import matplotlib.pyplot as plt

def calculate_gini_coefficient(values: list[float]) -> float:
    """
    Calculate the Gini coefficient for a list of values.
    
    The Gini coefficient measures inequality in a distribution.
    Returns a value between 0 (perfect equality) and 1 (perfect inequality).
    
    Args:
        values: List of numeric values (e.g., node degrees)
        
    Returns:
        Gini coefficient (0-1)
    """
    if not values or len(values) == 0:
        return 0.0
    
    # Remove any NaN or infinite values
    values = [v for v in values if np.isfinite(v)]
    
    if len(values) == 0:
        return 0.0
    
    sorted_values = np.sort(np.array(values))
    n = len(sorted_values)
    
    # Calculate Gini coefficient
    # Formula: G = (2 * sum(i * x_i)) / (n * sum(x_i)) - (n + 1) / n
    cumsum = np.cumsum(sorted_values)
    total = cumsum[-1]
    
    if total == 0:
        return 0.0
    
    # Gini = (2 * sum of (rank * value)) / (n * total) - (n + 1) / n
    gini = (2.0 * np.sum((np.arange(1, n + 1) * sorted_values))) / (n * total) - (n + 1.0) / n
    
    return gini

def calculate_centralization_score(node_degrees: list[float], num_links: int) -> float:
    """
    Calculate the centralization score S for a distribution of node degrees.
    
    Formula: S = sum((a_i / C)^2) - 1/C
    where a_i is the node degree of node i, and C is the total number of edges
    
    Args:
        node_degrees: List of node degrees
        num_links: Number of edges/links between nodes
        
    Returns:
        Centralization score (higher means more centralized)
    """
    if not node_degrees or len(node_degrees) == 0:
        return 0.0
    
    # Remove any NaN or infinite values
    degrees = [d for d in node_degrees if np.isfinite(d)]
    
    if len(degrees) == 0:
        return 0.0

    C = num_links if num_links > 0 else 1  # Avoid division by zero

    # Calculate S = sum((a_i / C)^2) - 1/C
    centralization = sum((a_i / C) ** 2 for a_i in degrees) - (1.0 / C)
    
    return centralization

def calculate_l0_norm(degrees: list[float]) -> float:
    """
    Calculate the L0 norm (sparsity) of node degrees.
    
    The L0 norm counts the number of non-zero elements, indicating how many
    nodes are actively participating in the network (have at least one connection).
    
    Args:
        degrees: List of node degrees
        
    Returns:
        Ratio of active nodes (L0 / total nodes), ranging from 0 to 1
    """
    # Count non-zero degrees (active nodes)
    non_zero_count = sum(1 for d in degrees if d > 0)
    
    # Return as ratio
    return non_zero_count / len(degrees)

def get_host_distance_matrix(messages: list[Message]):
    """
    Create a distance matrix between hosts using actual host coordinates.

    Args:
        messages: All messages with host coordinate information
        
    Returns:
        Distance_matrix
    """
    
    # Get all unique hosts
    hosts: dict[int, HostInfo] = {}
    for msg in messages:
        hosts[int(msg.source_host.host_id.split('_')[-1])] = msg.source_host
        hosts[int(msg.target_host.host_id.split('_')[-1])] = msg.target_host

    # Convert to sorted list for consistent indexing
    host_list = sorted(list(hosts))
    
    # Initialize distance matrix with NaN (no connection/data)
    n_hosts = len(host_list)
    distance_matrix = np.full((n_hosts, n_hosts), np.nan)
    
    # Calculate distances between all pairs of hosts using coordinates
    for i, host1_id in enumerate(host_list):
        host1 = hosts[host1_id]
        for j, host2_id in enumerate(host_list):
            host2 = hosts[host2_id]
            if i != j:
                distance = host1.distance_to(host2)
                distance_matrix[i][j] = distance
            elif i == j:
                distance_matrix[i][j] = 0.0  # Distance to self is 0
    
    return distance_matrix

def get_delivery_success_matrix(all_messages: list[Message], delivered_messages: list[Message], time_threshold: float = 10.0):
    """
    Create a delivery success probability matrix between hosts for a specific communication mode.
    
    Args:
        all_messages: All created messages
        delivered_messages: Successfully delivered messages
        mode: 0 for intra-cluster, 1 for inter-cluster
        time_threshold: Time threshold for successful delivery
        
    Returns:
        Tuple of (success_matrix, host_list)
    """

    # Get all unique hosts that appear in messages
    hosts: dict[int, HostInfo] = {}
    for msg in all_messages:
        # host id is the last number splitting the host id by underscores: random_stationary_clusternumber_id
        hosts[int(msg.source_host.host_id.split('_')[-1])] = msg.source_host
        hosts[int(msg.target_host.host_id.split('_')[-1])] = msg.target_host

    n_hosts = len(hosts)
    total_attempts = np.zeros((n_hosts, n_hosts))
    successful_deliveries = np.zeros((n_hosts, n_hosts))
    
    # Count total attempts
    for msg in all_messages:
        source = int(msg.source_host.host_id.split('_')[-1])
        destination = int(msg.target_host.host_id.split('_')[-1])
        total_attempts[source, destination] += 1
    
    delivered_messages_in_t = [msg for msg in delivered_messages if msg.delivery_time <= time_threshold]

    # Count successful deliveries
    for msg in delivered_messages_in_t:
        source = int(msg.source_host.host_id.split('_')[-1])
        destination = int(msg.target_host.host_id.split('_')[-1])
        successful_deliveries[source, destination] += 1

    # Calculate success probability matrix
    success_matrix = np.divide(successful_deliveries, total_attempts, 
                              out=np.zeros_like(successful_deliveries), 
                              where=total_attempts!=0)
    
    return success_matrix

def get_topology_matrix_from_connectivity(topology: Topology, n_hosts: int = 72):
    """
    Create a topology matrix from connectivity report data.
    
    Args:
        topology: Dictionary mapping node_id -> set of neighbor node_ids
        n_hosts: Number of hosts in the network (default 72)
        
    Returns:
        Binary topology matrix (1 if link exists, 0 otherwise)
    """
    topology_matrix = np.zeros((n_hosts, n_hosts))
    
    for node_id_str, neighbors in topology.connections.items():
        node_id = int(node_id_str)
        for neighbor_str in neighbors:
            neighbor_id = int(neighbor_str)
            topology_matrix[node_id, neighbor_id] = 1
    
    return topology_matrix

def load_messages_per_run(all_messages: list[Message], delivered_messages: list[Message], run: int, range_suffix: int, mode: int):
    """
    Filter messages for a specific config.
    
    Args:
        all_messages: List of all messages
        delivered_messages: List of delivered messages
        run: Run number
        range_suffix: Communication range
        mode: Mode (0 for intra, 1 for inter)
        
    Returns:
        Tuple of (all_messages, delivered_messages) for this specific run
    """

    all_messages_per_config = [msg for msg in all_messages if msg.run == run and msg.communication_range == range_suffix and msg.mode == mode]
    delivered_messages_per_config = [msg for msg in delivered_messages if msg.run == run and msg.communication_range == range_suffix and msg.mode == mode]

    return all_messages_per_config, delivered_messages_per_config

def plot_max_degree_vs_throughput(delivered_messages: list[Message]):
    """Plot maximum allowed node degree vs achieved throughput, with one curve per communication radius: """
    
    # Group by communication_range and max_degree
    throughput_data = {}
    for msg in delivered_messages:
        key = (msg.mode, msg.communication_range, msg.max_degree)
        if key not in throughput_data:
            throughput_data[key] = []
        if msg.delivery_time > 0:
            throughput = msg.size / msg.delivery_time
            throughput_data[key].append(throughput)
    
    # Calculate Mean throughput per group
    modes = sorted(set(k[0] for k in throughput_data.keys()))
    ranges = sorted(set(k[1] for k in throughput_data.keys()))
    max_degrees = sorted(set(k[2] for k in throughput_data.keys()))
    

    for mode in modes:
        for comm_range in ranges:
            available_degrees = [k[2] for k in throughput_data.keys() 
                            if k[0] == mode and k[1] == comm_range]
            print(f"Mode {mode}, Range {comm_range}m: degrees {sorted(set(available_degrees))}")
            
            # Debug: check which degrees have actual throughput data (non-empty lists)
            degrees_with_data = [k[2] for k in throughput_data.keys() 
                               if k[0] == mode and k[1] == comm_range and throughput_data[k]]
            if sorted(set(available_degrees)) != sorted(set(degrees_with_data)):
                print(f"  -> But only these have non-empty data: {sorted(set(degrees_with_data))}")

    colors = plt.cm.viridis(np.linspace(0, 1, len(ranges)))
    markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h', 'H', '+', 'x']
    
    # Create vertical layout (2 rows, 1 column)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10))
    
    # Intra-cluster subplot (top)
    for range_idx, comm_range in enumerate(ranges):
        x_vals = []
        y_vals = []
        for max_deg in max_degrees:
            key = (0, comm_range, max_deg)
            if key in throughput_data and throughput_data[key]:
                avg_throughput = np.mean(throughput_data[key])
                x_vals.append(max_deg)
                y_vals.append(avg_throughput)
        
        if x_vals:
            ax1.plot(x_vals, y_vals, marker=markers[range_idx % len(markers)], 
                    linestyle='-', label=f'Range {comm_range}m', 
                    linewidth=2, markersize=8, color=colors[range_idx])
    
    # No x-axis label on top subplot
    ax1.set_ylabel('Mean Throughput (bytes/second)')
    ax1.set_title('Intra-cluster')
    ax1.grid(True, alpha=0.3)
    
    # Inter-cluster subplot (bottom)
    for range_idx, comm_range in enumerate(ranges):
        x_vals = []
        y_vals = []
        for max_deg in max_degrees:
            key = (1, comm_range, max_deg)
            if key in throughput_data and throughput_data[key]:
                avg_throughput = np.mean(throughput_data[key])
                x_vals.append(max_deg)
                y_vals.append(avg_throughput)
        
        if x_vals:
            ax2.plot(x_vals, y_vals, marker=markers[range_idx % len(markers)], 
                    linestyle='-', label=f'Range {comm_range}m', 
                    linewidth=2, markersize=8, color=colors[range_idx])
    
    ax2.set_xlabel('Maximum Allowed Node Degree')
    ax2.set_ylabel('Mean Throughput (bytes/second)')
    ax2.set_title('Inter-cluster')
    ax2.grid(True, alpha=0.3)
    
    # Create shared legend below both subplots
    handles, labels = ax1.get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(0.5, -0.05), ncol=4, frameon=True)
    
    # Adjust layout to make room for legend
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.15)
    
    plt.savefig('figures/max_degree_vs_throughput.png', dpi=300, bbox_inches='tight')
    plt.close()

def plot_metrics_vs_max_degree(delivered_messages: list[Message], topologies: dict[Configuration, Topology]):
    """
    Plot Gini coefficient, centralization score, and L0 norm vs max node degree,
    split by mode (intra/inter-cluster), with one curve for each communication range.
    
    Each randomized run is treated as an individual data point, showing the natural
    variation in centralization metrics across different random topologies.
    
    Creates 6 subplots (3x2 grid):
    - Top row: Gini coefficient (intra, inter)
    - Middle row: Centralization score S (intra, inter)
    - Bottom row: L0 norm / sparsity (intra, inter)
    """
    TOTAL_NODES = 72
    
    # Get all available runs with randomized topologies
    randomized_runs = sorted(set(
        config.run_number 
        for config in topologies.keys() 
        if config.run_randomize_seed == 1
    ))
    
    if not randomized_runs:
        print("Warning: No randomized topologies found. Falling back to non-randomized (run=1).")
        randomized_runs = [1]
    
    # Collect individual data points (one per run)
    data_points = []
    
    config_keys = set()
    for msg in delivered_messages:
        config_keys.add((msg.mode, msg.communication_range, msg.max_degree))
    
    for mode, comm_range, max_deg in config_keys:
        for run_num in randomized_runs:
            config = Configuration(
                run_number=run_num, 
                range=comm_range, 
                max_degree=max_deg, 
                mode=mode,
                run_randomize_seed=1
            )
            topology = topologies.get(config)
            
            if topology is None:
                continue
            
            # Extract degrees for ALL nodes from the topology
            degrees_list = []
            for node_id in range(TOTAL_NODES):
                node_name = str(node_id)
                if node_name in topology.connections:
                    degrees_list.append(len(topology.connections[node_name]))
                else:
                    degrees_list.append(0)  # Isolated node
            
            # Calculate all metrics for this run
            gini_coef = calculate_gini_coefficient(degrees_list)
            num_links = topology.get_number_of_links()
            s_score = calculate_centralization_score(degrees_list, num_links)
            l0_norm = calculate_l0_norm(degrees_list)
            
            data_points.append({
                'mode': mode,
                'comm_range': comm_range,
                'max_degree': max_deg,
                'run': run_num,
                'gini': gini_coef,
                's_score': s_score,
                'l0_norm': l0_norm
            })
    
    modes = sorted(set(d['mode'] for d in data_points))
    ranges = sorted(set(d['comm_range'] for d in data_points))
    max_degrees = sorted(set(d['max_degree'] for d in data_points))
    modes = sorted(set(d['mode'] for d in data_points))
    ranges = sorted(set(d['comm_range'] for d in data_points))
    max_degrees = sorted(set(d['max_degree'] for d in data_points))
    
    # Create 3x2 subplot grid
    fig, axes = plt.subplots(3, 2, figsize=(16, 18))
    
    mode_names = {0: 'Intra-cluster', 1: 'Inter-cluster'}
    colors = plt.cm.viridis(np.linspace(0, 1, len(ranges)))
    markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h', 'H', '+', 'x']
    
    # Plot Gini coefficient (top row)
    for mode_idx, mode in enumerate(modes):
        ax = axes[0, mode_idx]
        
        for range_idx, comm_range in enumerate(ranges):
            # Filter points for this mode and range
            points = [d for d in data_points if d['mode'] == mode and d['comm_range'] == comm_range]
            
            if not points:
                continue
            
            # Group by max_degree
            degree_groups = {}
            for point in points:
                max_deg = point['max_degree']
                if max_deg not in degree_groups:
                    degree_groups[max_deg] = []
                degree_groups[max_deg].append(point['gini'])
            
            # Calculate statistics for each max_degree
            x_vals = []
            y_vals = []
            y_stds = []
            
            for max_deg in sorted(degree_groups.keys()):
                x_vals.append(max_deg)
                y_vals.append(np.mean(degree_groups[max_deg]))
                y_stds.append(np.std(degree_groups[max_deg]))
            
            if x_vals:
                ax.errorbar(x_vals, y_vals, yerr=y_stds,
                           marker=markers[range_idx % len(markers)], 
                           markersize=8,
                           linewidth=2,
                           capsize=5,
                           capthick=2,
                           label=f'{int(comm_range)}m range',
                           color=colors[range_idx])
        
        ax.set_xlabel('Maximum Allowed Node Degree', fontsize=12)
        ax.set_ylabel('Gini Coefficient', fontsize=12)
        ax.set_title(f'Gini Coefficient', fontsize=14)
        ax.set_ylim(0, 1)  # Gini coefficient ranges from 0 to 1
        ax.grid(True, alpha=0.3)
    
    # Plot Centralization Score (middle row)
    for mode_idx, mode in enumerate(modes):
        ax = axes[1, mode_idx]
        
        for range_idx, comm_range in enumerate(ranges):
            # Filter points for this mode and range
            points = [d for d in data_points if d['mode'] == mode and d['comm_range'] == comm_range]
            
            if not points:
                continue
            
            # Group by max_degree
            degree_groups = {}
            for point in points:
                max_deg = point['max_degree']
                if max_deg not in degree_groups:
                    degree_groups[max_deg] = []
                degree_groups[max_deg].append(point['s_score'])
            
            # Calculate statistics for each max_degree
            x_vals = []
            y_vals = []
            y_stds = []
            
            for max_deg in sorted(degree_groups.keys()):
                x_vals.append(max_deg)
                y_vals.append(np.mean(degree_groups[max_deg]))
                y_stds.append(np.std(degree_groups[max_deg]))
            
            if x_vals:
                ax.errorbar(x_vals, y_vals, yerr=y_stds,
                           marker=markers[range_idx % len(markers)], 
                           markersize=8,
                           linewidth=2,
                           capsize=5,
                           capthick=2,
                           label=f'{int(comm_range)}m range',
                           color=colors[range_idx])
        
        ax.set_xlabel('Maximum Allowed Node Degree', fontsize=12)
        ax.set_ylabel('Centralization Score S', fontsize=12)
        ax.set_title(f'Centralization Score', fontsize=14)
        ax.grid(True, alpha=0.3)
    
    # Plot L0 Norm (bottom row)
    for mode_idx, mode in enumerate(modes):
        ax = axes[2, mode_idx]
        
        for range_idx, comm_range in enumerate(ranges):
            # Filter points for this mode and range
            points = [d for d in data_points if d['mode'] == mode and d['comm_range'] == comm_range]
            
            if not points:
                continue
            
            # Group by max_degree
            degree_groups = {}
            for point in points:
                max_deg = point['max_degree']
                if max_deg not in degree_groups:
                    degree_groups[max_deg] = []
                degree_groups[max_deg].append(point['l0_norm'])
            
            # Calculate statistics for each max_degree
            x_vals = []
            y_vals = []
            y_stds = []
            
            for max_deg in sorted(degree_groups.keys()):
                x_vals.append(max_deg)
                y_vals.append(np.mean(degree_groups[max_deg]))
                y_stds.append(np.std(degree_groups[max_deg]))
            
            if x_vals:
                ax.errorbar(x_vals, y_vals, yerr=y_stds,
                           marker=markers[range_idx % len(markers)], 
                           markersize=8,
                           linewidth=2,
                           capsize=5,
                           capthick=2,
                           label=f'{int(comm_range)}m range',
                           color=colors[range_idx])
        
        ax.set_xlabel('Maximum Allowed Node Degree', fontsize=12)
        ax.set_ylabel('L0 Norm (Active Node Ratio)', fontsize=12)
        ax.set_title(f'Network Sparsity (L0)', fontsize=14)
        ax.set_ylim(0, 1.05)  # L0 ratio ranges from 0 to 1
        ax.grid(True, alpha=0.3)
    
    # Add shared legend below all subplots
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(0.5, -0.02), 
               ncol=min(len(labels), 5), fontsize=11, frameon=True)
    
    plt.tight_layout(rect=[0, 0.03, 1, 1])

    # Split versions by distance range
    low_ranges = [r for r in ranges if r <= 40]
    high_ranges = [r for r in ranges if r >= 50]
    
    # Function to plot for a specific distance range
    def plot_for_distance_range(distance_ranges, range_label, filename_suffix, use_log_gini=False):
        """Helper function to create plots for a specific distance range
        
        Args:
            distance_ranges: List of communication ranges to plot
            range_label: Label for the distance range (e.g., "Low Distances: ≤40m")
            filename_suffix: Suffix for the output filename (e.g., "low_dist")
            use_log_gini: If True, use log scale for Gini coefficient y-axis
        """
        if not distance_ranges:
            return
            
        colors_local = plt.cm.viridis(np.linspace(0, 1, len(distance_ranges)))
        
        # Plot 1: All metrics (3x2 grid) for this distance range
        fig1, axes1 = plt.subplots(3, 2, figsize=(16, 18))
        
        # Gini coefficient (top row)
        for mode_idx, mode in enumerate(modes):
            ax = axes1[0, mode_idx]
            
            for range_idx, comm_range in enumerate(distance_ranges):
                points = [d for d in data_points if d['mode'] == mode and d['comm_range'] == comm_range]
                
                if not points:
                    continue
                
                degree_groups = {}
                for point in points:
                    max_deg = point['max_degree']
                    if max_deg not in degree_groups:
                        degree_groups[max_deg] = []
                    degree_groups[max_deg].append(point['gini'])
                
                x_vals = []
                y_vals = []
                y_stds = []
                
                for max_deg in sorted(degree_groups.keys()):
                    x_vals.append(max_deg)
                    y_vals.append(np.mean(degree_groups[max_deg]))
                    y_stds.append(np.std(degree_groups[max_deg]))
                
                if x_vals:
                    ax.errorbar(x_vals, y_vals, yerr=y_stds,
                               marker=markers[range_idx % len(markers)], 
                               markersize=8,
                               linewidth=2,
                               capsize=5,
                               capthick=2,
                               label=f'{int(comm_range)}m range',
                               color=colors_local[range_idx])
            
            ax.set_xlabel('Maximum Allowed Node Degree', fontsize=12)
            ax.set_ylabel('Gini Coefficient', fontsize=12)
            ax.set_title(f'{mode_names[mode_idx]}', fontsize=14)
            if use_log_gini:
                ax.set_yscale('log')
                ax.set_ylim(0.001, 1)
            else:
                ax.set_ylim(0, 1)
            ax.grid(True, alpha=0.3)
        
        # Centralization Score (middle row)
        for mode_idx, mode in enumerate(modes):
            ax = axes1[1, mode_idx]
            
            for range_idx, comm_range in enumerate(distance_ranges):
                points = [d for d in data_points if d['mode'] == mode and d['comm_range'] == comm_range]
                
                if not points:
                    continue
                
                degree_groups = {}
                for point in points:
                    max_deg = point['max_degree']
                    if max_deg not in degree_groups:
                        degree_groups[max_deg] = []
                    degree_groups[max_deg].append(point['s_score'])
                
                x_vals = []
                y_vals = []
                y_stds = []
                
                for max_deg in sorted(degree_groups.keys()):
                    x_vals.append(max_deg)
                    y_vals.append(np.mean(degree_groups[max_deg]))
                    y_stds.append(np.std(degree_groups[max_deg]))
                
                if x_vals:
                    ax.errorbar(x_vals, y_vals, yerr=y_stds,
                               marker=markers[range_idx % len(markers)], 
                               markersize=8,
                               linewidth=2,
                               capsize=5,
                               capthick=2,
                               label=f'{int(comm_range)}m range',
                               color=colors_local[range_idx])
            
            ax.set_xlabel('Maximum Allowed Node Degree', fontsize=12)
            ax.set_ylabel('Centralization Score S', fontsize=12)
            ax.set_title(f'{mode_names[mode_idx]}', fontsize=14)
            ax.grid(True, alpha=0.3)
        
        # L0 Norm (bottom row)
        for mode_idx, mode in enumerate(modes):
            ax = axes1[2, mode_idx]
            
            for range_idx, comm_range in enumerate(distance_ranges):
                points = [d for d in data_points if d['mode'] == mode and d['comm_range'] == comm_range]
                
                if not points:
                    continue
                
                degree_groups = {}
                for point in points:
                    max_deg = point['max_degree']
                    if max_deg not in degree_groups:
                        degree_groups[max_deg] = []
                    degree_groups[max_deg].append(point['l0_norm'])
                
                x_vals = []
                y_vals = []
                y_stds = []
                
                for max_deg in sorted(degree_groups.keys()):
                    x_vals.append(max_deg)
                    y_vals.append(np.mean(degree_groups[max_deg]))
                    y_stds.append(np.std(degree_groups[max_deg]))
                
                if x_vals:
                    ax.errorbar(x_vals, y_vals, yerr=y_stds,
                               marker=markers[range_idx % len(markers)], 
                               markersize=8,
                               linewidth=2,
                               capsize=5,
                               capthick=2,
                               label=f'{int(comm_range)}m range',
                               color=colors_local[range_idx])
            
            ax.set_xlabel('Maximum Allowed Node Degree', fontsize=12)
            ax.set_ylabel('L0 Norm (Active Node Ratio)', fontsize=12)
            ax.set_title(f'{mode_names[mode_idx]}', fontsize=14)
            ax.set_ylim(0, 1.05)
            ax.grid(True, alpha=0.3)

        # Add shared legend below all subplots
        handles, labels = axes1[0, 0].get_legend_handles_labels()
        fig1.legend(handles, labels, loc='lower center', bbox_to_anchor=(0.5, -0.02), 
                   ncol=min(len(labels), 5), fontsize=11, frameon=True)

        plt.suptitle(f'Network Centralization Metrics vs Maximum Node Degree',
                     fontsize=16, y=0.997)
        plt.tight_layout(rect=[0, 0.03, 1, 0.99])
        plt.savefig(f'figures/centralization_metrics_vs_max_degree_all_metrics_{filename_suffix}.png', 
                    dpi=300, bbox_inches='tight')
        plt.close()
        
        # Plot 2: Intra-cluster only (Gini + S-score)
        fig2, axes2 = plt.subplots(2, 1, figsize=(5, 7))
        
        # Gini coefficient
        ax = axes2[0]
        for range_idx, comm_range in enumerate(distance_ranges):
            points = [d for d in data_points if d['mode'] == 0 and d['comm_range'] == comm_range]
            
            if not points:
                continue
            
            degree_groups = {}
            for point in points:
                max_deg = point['max_degree']
                if max_deg not in degree_groups:
                    degree_groups[max_deg] = []
                degree_groups[max_deg].append(point['gini'])
            
            x_vals = []
            y_vals = []
            y_stds = []
            
            for max_deg in sorted(degree_groups.keys()):
                x_vals.append(max_deg)
                y_vals.append(np.mean(degree_groups[max_deg]))
                y_stds.append(np.std(degree_groups[max_deg]))
            
            if x_vals:
                ax.errorbar(x_vals, y_vals, yerr=y_stds,
                           marker=markers[range_idx % len(markers)], 
                           markersize=8,
                           linewidth=2,
                           capsize=5,
                           capthick=2,
                           label=f'{int(comm_range)}m range',
                           color=colors_local[range_idx])
        
        ax.set_ylabel('Gini Coefficient', fontsize=12)
        
        if use_log_gini:
            ax.set_yscale('log')
            ax.set_ylim(0.001, 1)
        else:
            ax.set_ylim(0, 1)
        ax.grid(True, alpha=0.3)
        
        # S-score
        ax = axes2[1]
        for range_idx, comm_range in enumerate(distance_ranges):
            points = [d for d in data_points if d['mode'] == 0 and d['comm_range'] == comm_range]
            
            if not points:
                continue
            
            degree_groups = {}
            for point in points:
                max_deg = point['max_degree']
                if max_deg not in degree_groups:
                    degree_groups[max_deg] = []
                degree_groups[max_deg].append(point['s_score'])
            
            x_vals = []
            y_vals = []
            y_stds = []
            
            for max_deg in sorted(degree_groups.keys()):
                x_vals.append(max_deg)
                y_vals.append(np.mean(degree_groups[max_deg]))
                y_stds.append(np.std(degree_groups[max_deg]))
            
            if x_vals:
                ax.errorbar(x_vals, y_vals, yerr=y_stds,
                           marker=markers[range_idx % len(markers)], 
                           markersize=8,
                           linewidth=2,
                           capsize=5,
                           capthick=2,
                           label=f'{int(comm_range)}m range',
                           color=colors_local[range_idx])
        
        ax.set_xlabel('Maximum Allowed Node Degree', fontsize=12)
        ax.set_ylabel('Centralization Score S', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # Add shared legend below the plots
        handles, labels = axes2[1].get_legend_handles_labels()
        fig2.legend(handles, labels, loc='lower center', ncol=min(len(labels), 4), 
                   bbox_to_anchor=(0.5, -0.02), fontsize=11, frameon=True)
        
        plt.suptitle(f'Intra-cluster Centralization Metrics vs Maximum Node Degree)',
                     fontsize=14, y=0.995)
        plt.tight_layout(rect=[0, 0.03, 1, 0.98])
        plt.savefig(f'figures/centralization_metrics_vs_max_degree_intra_{filename_suffix}.png', 
                    dpi=300, bbox_inches='tight')
        plt.close()
        
        # Plot 3: Inter-cluster only (Gini + S-score)
        fig3, axes3 = plt.subplots(2, 1, figsize=(5, 9))
        
        # Gini coefficient
        ax = axes3[0]
        for range_idx, comm_range in enumerate(distance_ranges):
            points = [d for d in data_points if d['mode'] == 1 and d['comm_range'] == comm_range]
            
            if not points:
                continue
            
            degree_groups = {}
            for point in points:
                max_deg = point['max_degree']
                if max_deg not in degree_groups:
                    degree_groups[max_deg] = []
                degree_groups[max_deg].append(point['gini'])
            
            x_vals = []
            y_vals = []
            y_stds = []
            
            for max_deg in sorted(degree_groups.keys()):
                x_vals.append(max_deg)
                y_vals.append(np.mean(degree_groups[max_deg]))
                y_stds.append(np.std(degree_groups[max_deg]))
            
            if x_vals:
                ax.errorbar(x_vals, y_vals, yerr=y_stds,
                           marker=markers[range_idx % len(markers)], 
                           markersize=8,
                           linewidth=2,
                           capsize=5,
                           capthick=2,
                           label=f'{int(comm_range)}m range',
                           color=colors_local[range_idx])
        
        ax.set_ylabel('Gini Coefficient', fontsize=12)
        
        if use_log_gini:
            ax.set_yscale('log')
            ax.set_ylim(0.001, 1)
        else:
            ax.set_ylim(0, 1)
        ax.grid(True, alpha=0.3)
        
        # S-score
        ax = axes3[1]
        for range_idx, comm_range in enumerate(distance_ranges):
            points = [d for d in data_points if d['mode'] == 1 and d['comm_range'] == comm_range]
            
            if not points:
                continue
            
            degree_groups = {}
            for point in points:
                max_deg = point['max_degree']
                if max_deg not in degree_groups:
                    degree_groups[max_deg] = []
                degree_groups[max_deg].append(point['s_score'])
            
            x_vals = []
            y_vals = []
            y_stds = []
            
            for max_deg in sorted(degree_groups.keys()):
                x_vals.append(max_deg)
                y_vals.append(np.mean(degree_groups[max_deg]))
                y_stds.append(np.std(degree_groups[max_deg]))
            
            if x_vals:
                ax.errorbar(x_vals, y_vals, yerr=y_stds,
                           marker=markers[range_idx % len(markers)], 
                           markersize=8,
                           linewidth=2,
                           capsize=5,
                           capthick=2,
                           label=f'{int(comm_range)}m range',
                           color=colors_local[range_idx])
        
        ax.set_xlabel('Maximum Allowed Node Degree', fontsize=12)
        ax.set_ylabel('Centralization Score S', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # Add shared legend below the plots
        handles, labels = axes3[1].get_legend_handles_labels()
        fig3.legend(handles, labels, loc='lower center', ncol=min(len(labels), 3), 
                   bbox_to_anchor=(0.5, -0.02), fontsize=11, frameon=True)
        
        plt.suptitle(f'Inter-cluster Centralization Metrics vs Maximum Node Degree',
                     fontsize=14, y=0.995)
        plt.tight_layout(rect=[0, 0.03, 1, 0.98])
        plt.savefig(f'figures/centralization_metrics_vs_max_degree_inter_{filename_suffix}.png', 
                    dpi=300, bbox_inches='tight')
        plt.close()
        # GOOD PLOT
    
    plot_for_distance_range(low_ranges, "Low Distances: ≤40m", "low_dist", use_log_gini=False)
    plot_for_distance_range(high_ranges, "High Distances: 50-100m", "high_dist", use_log_gini=False)

def plot_max_degree_vs_throughput_run_comparison(delivered_messages: list[Message], n: int = 20):
    """
    Plot node degree vs throughput for mode 0 (intra-cluster), comparing:
    - Single run (run 1) data
    - Aggregated normalized data from n runs
    """
    
    # Separate messages by run
    runs_data = {}
    for msg in delivered_messages:
        if msg.mode != 0:  # Only mode 0 (intra-cluster)
            continue
        
        run = msg.run
        if run not in runs_data:
            runs_data[run] = []
        
        if msg.delivery_time > 0:
            throughput = msg.size / msg.delivery_time
            runs_data[run].append({
                'max_degree': msg.max_degree,
                'comm_range': msg.communication_range,
                'throughput': throughput
            })
    
    if not runs_data:
        print("No mode 0 data found for run comparison")
        return
    
    # Get available runs
    available_runs = sorted(runs_data.keys())
    
    # Check if run 1 exists
    if 1 not in available_runs:
        print(f"Run 1 not found. Available runs: {available_runs}")
        return
    
    # Get all communication ranges
    all_comm_ranges = sorted(set(msg['comm_range'] for run_data in runs_data.values() for msg in run_data))
    
    fig, axes = plt.subplots(1, len(all_comm_ranges), figsize=(6*len(all_comm_ranges), 5))
    if len(all_comm_ranges) == 1:
        axes = [axes]
    
    for idx, comm_range in enumerate(all_comm_ranges):
        ax = axes[idx]
        
        # Extract run 1 data for this communication range
        run1_data = [msg for msg in runs_data[1] if msg['comm_range'] == comm_range]
        
        # Extract first n runs (or however many are available)
        runs_to_aggregate = sorted([r for r in available_runs if r <= n])
        
        # Group by max_degree
        run1_by_degree = {}
        for msg in run1_data:
            degree = msg['max_degree']
            if degree not in run1_by_degree:
                run1_by_degree[degree] = []
            run1_by_degree[degree].append(msg['throughput'])
        
        # Aggregate across runs
        aggregated_by_degree = {}
        for run in runs_to_aggregate:
            run_data = [msg for msg in runs_data[run] if msg['comm_range'] == comm_range]
            for msg in run_data:
                degree = msg['max_degree']
                if degree not in aggregated_by_degree:
                    aggregated_by_degree[degree] = []
                aggregated_by_degree[degree].append(msg['throughput'])
        
        # Calculate statistics
        all_degrees = sorted(set(list(run1_by_degree.keys()) + list(aggregated_by_degree.keys())))
        
        run1_means = []
        run1_stds = []
        run1_x = []
        
        agg_means = []
        agg_stds = []
        agg_x = []
        
        for degree in all_degrees:
            if degree in run1_by_degree and run1_by_degree[degree]:
                run1_means.append(np.mean(run1_by_degree[degree]))
                run1_stds.append(np.std(run1_by_degree[degree]))
                run1_x.append(degree)
            
            if degree in aggregated_by_degree and aggregated_by_degree[degree]:
                agg_means.append(np.mean(aggregated_by_degree[degree]))
                agg_stds.append(np.std(aggregated_by_degree[degree]))
                agg_x.append(degree)
        
        # Plot run 1 data
        if run1_x:
            ax.errorbar(run1_x, run1_means, yerr=run1_stds, marker='o', 
                       label='Run 1', linewidth=2, markersize=8, capsize=5, capthick=2,
                       color='blue', alpha=0.7)
        
        # Plot aggregated data (raw throughput values)
        if agg_x:
            ax.errorbar(agg_x, agg_means, yerr=agg_stds, marker='s',
                       label=f'Aggregate (runs 1-{len(runs_to_aggregate)})', 
                       linewidth=2, markersize=8, capsize=5, capthick=2,
                       color='red', alpha=0.7)
        
        ax.set_xlabel('Maximum Allowed Node Degree')
        ax.set_ylabel('Mean Throughput (bytes/second)')
        ax.set_title(f'Throughput vs Max Degree\nCommunication Range: {comm_range}m')
        ax.grid(True, alpha=0.3)
        ax.legend()
    
    plt.tight_layout()
    plt.savefig('figures/max_degree_vs_throughput_run_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()

def plot_message_delivery_distribution(all_messages: list[Message], delivered_messages: list[Message], num_bins=20):
    """Plot message creation and delivery distribution per distance by mode
    
    Shows bars for delivered messages and shaded areas on top showing undelivered messages.
    The total height (bar + shaded area) represents all generated messages.
    """
    # Create a figure with 2 subplots vertically
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7, 6))
    
    # Subplot 1: Intra-cluster message distribution
    all_intra_messages = [msg for msg in all_messages if msg.distance > 0 and msg.mode == 0]
    delivered_intra_messages = [msg for msg in delivered_messages if msg.distance > 0 and msg.mode == 0]
    all_intra_distances = [msg.distance for msg in all_intra_messages]
    delivered_intra_distances = [msg.distance for msg in delivered_intra_messages]
    
    if all_intra_distances:
        # Create bins specific to intra-cluster distance range
        min_intra_dist = min(all_intra_distances)
        max_intra_dist = max(all_intra_distances)
        intra_bins = np.linspace(min_intra_dist, max_intra_dist, num_bins + 1)
        intra_bin_centers = (intra_bins[:-1] + intra_bins[1:]) / 2
        intra_bin_width = intra_bins[1] - intra_bins[0]
        
        all_intra_counts = []
        delivered_intra_counts = []
        for i in range(len(intra_bins)-1):
            all_count = sum(1 for d in all_intra_distances if intra_bins[i] <= d < intra_bins[i+1])
            delivered_count = sum(1 for d in delivered_intra_distances if intra_bins[i] <= d < intra_bins[i+1])
            all_intra_counts.append(all_count)
            delivered_intra_counts.append(delivered_count)
        
        bars_intra = ax1.bar(intra_bin_centers, delivered_intra_counts,
                            width=intra_bin_width * 0.8,
                            alpha=0.7,
                            label='Delivered',
                            color='green',
                            edgecolor='black',
                            linewidth=0.5)
        
        # Add shaded area above bars showing undelivered messages
        intra_undelivered_label_added = False
        for center, all_count, delivered_count in zip(intra_bin_centers, all_intra_counts, delivered_intra_counts):
            if all_count > delivered_count:
                left_edge = center - (intra_bin_width * 0.4)
                height_shade = all_count - delivered_count
                
                # Only add label for the first undelivered rectangle
                label = 'Undelivered' if not intra_undelivered_label_added else ''
                ax1.add_patch(plt.Rectangle((left_edge, delivered_count), intra_bin_width * 0.8, height_shade,
                                           facecolor='lightgreen', alpha=0.4, edgecolor='black', linewidth=0.5, label=label))
                intra_undelivered_label_added = True
                
                ax1.text(center, all_count, f'{all_count}',
                        ha='center', va='bottom', fontsize=8)
            elif all_count > 0:
                ax1.text(center, all_count, f'{all_count}',
                        ha='center', va='bottom', fontsize=8)
        
        intra_delivery_rate = (len(delivered_intra_distances) / len(all_intra_distances) * 100) if all_intra_distances else 0
        ax1.set_title('Intra-cluster message distribution', fontsize=12, color='black')
        ax1.legend(loc='upper right', fontsize=8)
        # ax1.text(0.02, 0.02, f'Total: {len(all_intra_distances):,}\nDelivered: {len(delivered_intra_distances):,} ({intra_delivery_rate:.1f}%)',
        #         transform=ax1.transAxes,
        #         verticalalignment='bottom',
        #         bbox=dict(boxstyle='round', facecolor='white', alpha=0.8),
        #         fontsize=9)
        ax1.set_xlim(min_intra_dist - intra_bin_width/2, max_intra_dist + intra_bin_width/2)
    else:
        ax1.text(0.5, 0.5, 'No intra-cluster\nmessages found',
                transform=ax1.transAxes,
                ha='center', va='center',
                fontsize=12)
        ax1.set_title('Intra-cluster message distribution', fontsize=12, color='black')
    
    ax1.set_ylabel('Number of Messages', fontsize=10)
    ax1.grid(True, alpha=0.3, axis='y')
    # Remove x-axis label from top subplot
    ax1.tick_params(labelbottom=True)
    
    # Subplot 2: Inter-cluster message distribution
    all_inter_messages = [msg for msg in all_messages if msg.distance > 0 and msg.mode == 1]
    delivered_inter_messages = [msg for msg in delivered_messages if msg.distance > 0 and msg.mode == 1]
    all_inter_distances = [msg.distance for msg in all_inter_messages]
    delivered_inter_distances = [msg.distance for msg in delivered_inter_messages]
    
    if all_inter_distances:
        # Create bins specific to inter-cluster distance range
        min_inter_dist = min(all_inter_distances)
        max_inter_dist = max(all_inter_distances)
        inter_bins = np.linspace(min_inter_dist, max_inter_dist, num_bins + 1)
        inter_bin_centers = (inter_bins[:-1] + inter_bins[1:]) / 2
        inter_bin_width = inter_bins[1] - inter_bins[0]
        
        all_inter_counts = []
        delivered_inter_counts = []
        for i in range(len(inter_bins)-1):
            all_count = sum(1 for d in all_inter_distances if inter_bins[i] <= d < inter_bins[i+1])
            delivered_count = sum(1 for d in delivered_inter_distances if inter_bins[i] <= d < inter_bins[i+1])
            all_inter_counts.append(all_count)
            delivered_inter_counts.append(delivered_count)
        
        bars_inter = ax2.bar(inter_bin_centers, delivered_inter_counts,
                            width=inter_bin_width * 0.8,
                            alpha=0.7,
                            label='Delivered',
                            color='red',
                            edgecolor='black',
                            linewidth=0.5)
        
        # Add shaded area above bars showing undelivered messages
        inter_undelivered_label_added = False
        for center, all_count, delivered_count in zip(inter_bin_centers, all_inter_counts, delivered_inter_counts):
            if all_count > delivered_count:
                left_edge = center - (inter_bin_width * 0.4)
                height_shade = all_count - delivered_count
                
                # Only add label for the first undelivered rectangle
                label = 'Undelivered' if not inter_undelivered_label_added else ''
                ax2.add_patch(plt.Rectangle((left_edge, delivered_count), inter_bin_width * 0.8, height_shade,
                                           facecolor='lightcoral', alpha=0.4, edgecolor='black', linewidth=0.5, label=label))
                inter_undelivered_label_added = True
                
                ax2.text(center, all_count, f'{all_count}',
                        ha='center', va='bottom', fontsize=8)
            elif all_count > 0:
                ax2.text(center, all_count, f'{all_count}',
                        ha='center', va='bottom', fontsize=8)
        
        inter_delivery_rate = (len(delivered_inter_distances) / len(all_inter_distances) * 100) if all_inter_distances else 0
        ax2.set_title('Inter-cluster message distribution', fontsize=12, color='black')
        ax2.legend(loc='upper right', fontsize=8)
        # ax2.text(0.02, 0.02, f'Total: {len(all_inter_distances):,}\nDelivered: {len(delivered_inter_distances):,} ({inter_delivery_rate:.1f}%)',
        #         transform=ax2.transAxes,
        #         verticalalignment='bottom',
        #         bbox=dict(boxstyle='round', facecolor='white', alpha=0.8),
        #         fontsize=9)
        ax2.set_xlim(min_inter_dist - inter_bin_width/2, max_inter_dist + inter_bin_width/2)
    else:
        ax2.text(0.5, 0.5, 'No inter-cluster\nmessages found',
                transform=ax2.transAxes,
                ha='center', va='center',
                fontsize=12)
        ax2.set_title('Inter-cluster message distribution', fontsize=12, color='black')
    
    ax2.set_xlabel('Distance (m)', fontsize=10)
    ax2.set_ylabel('Number of Messages', fontsize=10)
    ax2.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig('figures/message_distance_distribution.png', 
                bbox_inches='tight', dpi=300)
    plt.close()

def plot_centralization_vs_delivery(all_messages: list[Message], delivered_messages: list[Message], topologies: dict[Configuration, Topology], time_threshold: float = 240.0):
    """
    Plot Gini coefficient and centralization score vs. delivery probability.
    
    Each randomized run is treated as an individual data point, showing the natural
    variation in the relationship between centralization and delivery.
    
    Creates a 2x2 grid:
    - Top row: Gini vs Delivery (intra-cluster, inter-cluster)
    - Bottom row: S-score vs Delivery (intra-cluster, inter-cluster)
    
    Args:
        all_messages: All created messages
        delivered_messages: Successfully delivered messages
        topologies: Dictionary mapping configuration to topology
        time_threshold: Time threshold for counting successful deliveries (default 240s)
    """
    TOTAL_NODES = 72
    
    # Get all available runs with randomized topologies
    randomized_runs = sorted(set(
        config.run_number 
        for config in topologies.keys() 
        if config.run_randomize_seed == 1
    ))
    
    if not randomized_runs:
        raise ValueError("No randomized topologies found.")
    
    data_points = []
    
    config_keys = set()
    for msg in all_messages:
        config_keys.add((msg.mode, msg.communication_range, msg.max_degree))
    
    for mode, comm_range, max_deg in config_keys:
        for run_num in randomized_runs:
            config = Configuration(
                run_number=run_num, 
                range=comm_range, 
                max_degree=max_deg, 
                mode=mode, 
                run_randomize_seed=1
            )
            topology = topologies.get(config)
            if topology is None:
                raise("fuck")
            
            # Calculate topology metrics
            degrees_list = []
            for node_id in range(TOTAL_NODES):
                node_name = str(node_id)
                if node_name in topology.connections:
                    degrees_list.append(len(topology.connections[node_name]))
                else:
                    degrees_list.append(0)
            
            gini = calculate_gini_coefficient(degrees_list)
            num_links = topology.get_number_of_links()
            s_score = calculate_centralization_score(degrees_list, num_links)
            
            # Calculate delivery probability for this specific run
            msgs_run = [msg for msg in all_messages 
                       if msg.mode == mode and msg.communication_range == comm_range 
                       and msg.max_degree == max_deg and msg.run == run_num]
            delivered_run = [msg for msg in delivered_messages 
                            if msg.mode == mode and msg.communication_range == comm_range 
                            and msg.max_degree == max_deg and msg.run == run_num 
                            and msg.delivery_time <= time_threshold]
            
            if len(msgs_run) > 0:
                delivery_prob = len(delivered_run) / len(msgs_run) * 100
                
                data_points.append({
                    'mode': mode,
                    'comm_range': comm_range,
                    'max_degree': max_deg,
                    'run': run_num,
                    'delivery_prob': delivery_prob,
                    'gini': gini,
                    's_score': s_score
                })
    
    # Create 2x2 subplot grid
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    mode_names = {0: 'Intra-cluster', 1: 'Inter-cluster'}
    
    # Prepare marker mappings
    ranges = sorted(set(d['comm_range'] for d in data_points))
    
    markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h', 'H', '+', 'x']
    colors = plt.cm.viridis(np.linspace(0, 1, len(ranges)))
    
    # Plot Gini coefficient (top row)
    for mode_idx, mode in enumerate([0, 1]):
        ax = axes[0, mode_idx]
        
        for range_idx, comm_range in enumerate(ranges):
            # Get all points for this communication range and mode
            points = [d for d in data_points 
                     if d['mode'] == mode and d['comm_range'] == comm_range]
            
            if not points:
                continue
            
            # Group by delivery_prob and calculate mean/std for each group
            # This creates error bars showing variance across runs with similar delivery rates
            delivery_groups = {}
            for point in points:
                dp = round(point['delivery_prob'], 1)  # Round to 0.1% precision for grouping
                if dp not in delivery_groups:
                    delivery_groups[dp] = {'gini': [], 'delivery_probs': []}
                delivery_groups[dp]['gini'].append(point['gini'])
                delivery_groups[dp]['delivery_probs'].append(point['delivery_prob'])
            
            # Calculate statistics for each group
            x_vals = []
            y_vals = []
            y_stds = []
            
            for dp in sorted(delivery_groups.keys()):
                x_vals.append(np.mean(delivery_groups[dp]['delivery_probs']))
                y_vals.append(np.mean(delivery_groups[dp]['gini']))
                y_stds.append(np.std(delivery_groups[dp]['gini']))
            
            if x_vals:
                # Plot with error bars
                ax.errorbar(x_vals, y_vals, yerr=y_stds,
                           marker=markers[range_idx % len(markers)],
                           markersize=8,
                           linewidth=2,
                           capsize=5,
                           capthick=2,
                           color=colors[range_idx],
                           label=f'{int(comm_range)}m range')
        
        ax.set_xlabel('Delivery Probability (%)', fontsize=11)
        ax.set_ylabel('Gini Coefficient', fontsize=11)
        ax.set_title(f'Gini vs Delivery', fontsize=12, fontweight='bold')
        ax.set_ylim(0, 1)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best', fontsize=9)
    
    # Plot S-score (bottom row)
    for mode_idx, mode in enumerate([0, 1]):
        ax = axes[1, mode_idx]
        
        for range_idx, comm_range in enumerate(ranges):
            # Get all points for this communication range and mode
            points = [d for d in data_points 
                     if d['mode'] == mode and d['comm_range'] == comm_range]
            
            if not points:
                continue
            
            # Group by delivery_prob and calculate mean/std for each group
            delivery_groups = {}
            for point in points:
                dp = round(point['delivery_prob'], 1)  # Round to 0.1% precision for grouping
                if dp not in delivery_groups:
                    delivery_groups[dp] = {'s_score': [], 'delivery_probs': []}
                delivery_groups[dp]['s_score'].append(point['s_score'])
                delivery_groups[dp]['delivery_probs'].append(point['delivery_prob'])
            
            # Calculate statistics for each group
            x_vals = []
            y_vals = []
            y_stds = []
            
            for dp in sorted(delivery_groups.keys()):
                x_vals.append(np.mean(delivery_groups[dp]['delivery_probs']))
                y_vals.append(np.mean(delivery_groups[dp]['s_score']))
                y_stds.append(np.std(delivery_groups[dp]['s_score']))
            
            if x_vals:
                # Plot with error bars
                ax.errorbar(x_vals, y_vals, yerr=y_stds,
                           marker=markers[range_idx % len(markers)],
                           markersize=8,
                           linewidth=2,
                           capsize=5,
                           capthick=2,
                           color=colors[range_idx],
                           label=f'{int(comm_range)}m range')
        
        ax.set_xlabel('Delivery Probability (%)', fontsize=11)
        ax.set_ylabel('Centralization Score S', fontsize=11)
        ax.set_title(f'S-score vs Delivery', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best', fontsize=9)
    
    # Create title with appropriate threshold label
    threshold_label = "All Deliveries" if time_threshold == float('inf') else f"Time Threshold: {int(time_threshold)}s"
    plt.suptitle(f'Centralization Metrics vs. Delivery Probability\n({threshold_label})',
                 fontsize=14, fontweight='bold', y=0.995)
    
    plt.tight_layout(rect=[0, 0, 1, 0.99])
    
    # Create filename with appropriate threshold label
    threshold_suffix = "all" if time_threshold == float('inf') else f"t{int(time_threshold)}"
    plt.savefig(f'figures/centralization_vs_delivery_subplots_{threshold_suffix}.png', 
                dpi=300, bbox_inches='tight')
    plt.close()
    
    threshold_display = "all deliveries" if time_threshold == float('inf') else f"threshold={int(time_threshold)}s"
    print(f"Subplot centralization vs delivery plot saved ({threshold_display})")

def plot_latency_vs_max_degree(delivered_messages: list[Message], topologies: dict[Configuration, Topology]):
    """
    Plot mean latency vs max node degree for different distance ranges.
    
    Creates separate plots for:
    - Low distances (≤40m) - intra and inter cluster
    - High distances (50-100m) - intra and inter cluster  
    - All distances - intra and inter cluster
    """
    TOTAL_NODES = 72
    
    # Get all available runs with randomized topologies
    randomized_runs = sorted(set(
        config.run_number 
        for config in topologies.keys() 
        if config.run_randomize_seed == 1
    ))
    
    if not randomized_runs:
        print("Warning: No randomized topologies found.")
        randomized_runs = [1]
    
    # Collect data points: latency per run/config
    data_points = []
    
    config_keys = set()
    for msg in delivered_messages:
        if msg.delivery_time > 0:
            config_keys.add((msg.mode, msg.communication_range, msg.max_degree))
    
    for mode, comm_range, max_deg in config_keys:
        for run_num in randomized_runs:
            # Get delivered messages for this specific run/config
            msgs_run = [msg for msg in delivered_messages 
                       if msg.mode == mode and msg.communication_range == comm_range 
                       and msg.max_degree == max_deg and msg.run == run_num
                       and msg.delivery_time > 0]
            
            if len(msgs_run) > 0:
                latencies = [msg.delivery_time for msg in msgs_run]
                mean_latency = np.mean(latencies)
                
                data_points.append({
                    'mode': mode,
                    'comm_range': comm_range,
                    'max_degree': max_deg,
                    'run': run_num,
                    'mean_latency': mean_latency
                })
    
    ranges = sorted(set(d['comm_range'] for d in data_points))
    max_degrees = sorted(set(d['max_degree'] for d in data_points))
    
    # Split by distance
    low_ranges = [r for r in ranges if r <= 40]
    high_ranges = [r for r in ranges if r >= 50]
    
    mode_names = {0: 'Intra-cluster', 1: 'Inter-cluster'}
    markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h', 'H', '+', 'x']
    
    def plot_for_mode_and_ranges(mode, distance_ranges, range_label, filename_suffix):
        """Helper to plot latency vs max_degree for a specific mode and distance range"""
        if not distance_ranges:
            return
        
        colors_local = plt.cm.viridis(np.linspace(0, 1, len(distance_ranges)))
        
        fig, ax = plt.subplots(figsize=(10, 7))
        
        for range_idx, comm_range in enumerate(distance_ranges):
            # Filter points for this mode and range
            points = [d for d in data_points 
                     if d['mode'] == mode and d['comm_range'] == comm_range]
            
            if not points:
                continue
            
            # Group by max_degree
            degree_groups = {}
            for point in points:
                max_deg = point['max_degree']
                if max_deg not in degree_groups:
                    degree_groups[max_deg] = []
                degree_groups[max_deg].append(point['mean_latency'])
            
            # Calculate statistics
            x_vals = []
            y_vals = []
            y_stds = []
            
            for max_deg in sorted(degree_groups.keys()):
                x_vals.append(max_deg)
                y_vals.append(np.mean(degree_groups[max_deg]))
                y_stds.append(np.std(degree_groups[max_deg]))
            
            if x_vals:
                ax.errorbar(x_vals, y_vals, yerr=y_stds,
                           marker=markers[range_idx % len(markers)], 
                           markersize=4,
                           linewidth=1,
                           capsize=3,
                           capthick=1,
                           label=f'{int(comm_range)}m range',
                           color=colors_local[range_idx])
        
        ax.set_xlabel('Maximum Allowed Node Degree', fontsize=12)
        ax.set_ylabel('Mean Latency (seconds)', fontsize=12)
        # ax.set_title(f'{mode_names[mode]}', fontsize=14)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best', fontsize=10)
        ax.set_yscale('log')
        
        plt.tight_layout()
        plt.savefig(f'figures/latency_vs_max_degree_{filename_suffix}.png', 
                   dpi=300, bbox_inches='tight')
        plt.close()
    
    # Generate plots for each mode and distance range combination
    # for mode in [0, 1]:
    for mode in [1]:
        mode_suffix = 'intra' if mode == 0 else 'inter'
        
        # # Low distances
        # if low_ranges:
        #     plot_for_mode_and_ranges(mode, low_ranges, "Low Distances: ≤40m", 
        #                             f"{mode_suffix}_low_dist")
        
        # High distances
        # if high_ranges:
        #     plot_for_mode_and_ranges(mode, high_ranges, "High Distances: 50-100m", 
        #                             f"{mode_suffix}_high_dist")
        
        # All distances
        plot_for_mode_and_ranges(mode, ranges, "All Distances", f"{mode_suffix}_all_dist")

def plot_latency_vs_centralization(delivered_messages: list[Message], topologies: dict[Configuration, Topology]):
    """
    Plot mean latency vs Gini coefficient and S-score for different distance ranges.
    
    Creates separate plots for:
    - Low distances (≤40m) - intra and inter cluster
    - High distances (50-100m) - intra and inter cluster
    - All distances - intra and inter cluster
    """
    TOTAL_NODES = 72
    
    # Get all available runs with randomized topologies
    randomized_runs = sorted(set(
        config.run_number 
        for config in topologies.keys() 
        if config.run_randomize_seed == 1
    ))
    
    if not randomized_runs:
        print("Warning: No randomized topologies found.")
        randomized_runs = [1]
    
    # Collect data points
    data_points = []
    
    config_keys = set()
    for msg in delivered_messages:
        if msg.delivery_time > 0:
            config_keys.add((msg.mode, msg.communication_range, msg.max_degree))
    
    for mode, comm_range, max_deg in config_keys:
        for run_num in randomized_runs:
            # Get topology metrics
            config = Configuration(
                run_number=run_num, 
                range=comm_range, 
                max_degree=max_deg, 
                mode=mode,
                run_randomize_seed=1
            )
            topology = topologies.get(config)
            
            if topology is None:
                continue
            
            # Calculate topology metrics
            degrees_list = []
            for node_id in range(TOTAL_NODES):
                node_name = str(node_id)
                if node_name in topology.connections:
                    degrees_list.append(len(topology.connections[node_name]))
                else:
                    degrees_list.append(0)
            
            gini = calculate_gini_coefficient(degrees_list)
            num_links = topology.get_number_of_links()
            s_score = calculate_centralization_score(degrees_list, num_links)
            
            # Get latency for this run/config
            msgs_run = [msg for msg in delivered_messages 
                       if msg.mode == mode and msg.communication_range == comm_range 
                       and msg.max_degree == max_deg and msg.run == run_num
                       and msg.delivery_time > 0]
            
            if len(msgs_run) > 0:
                latencies = [msg.delivery_time for msg in msgs_run]
                mean_latency = np.mean(latencies)
                
                data_points.append({
                    'mode': mode,
                    'comm_range': comm_range,
                    'max_degree': max_deg,
                    'run': run_num,
                    'mean_latency': mean_latency,
                    'gini': gini,
                    's_score': s_score
                })
    
    ranges = sorted(set(d['comm_range'] for d in data_points))
    
    # Split by distance
    low_ranges = [r for r in ranges if r <= 40]
    high_ranges = [r for r in ranges if r >= 50]
    
    mode_names = {0: 'Intra-cluster', 1: 'Inter-cluster'}
    markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h', 'H', '+', 'x']
    
    def plot_for_mode_and_ranges(mode, distance_ranges, range_label, filename_suffix):
        """Helper to plot latency vs centralization metrics"""
        if not distance_ranges:
            return
        
        colors_local = plt.cm.viridis(np.linspace(0, 1, len(distance_ranges)))
        
        # Create 2 subplots: Gini and S-score
        fig, axes = plt.subplots(2, 1, figsize=(10, 14))
        
        # Plot 1: Latency vs Gini
        ax = axes[0]
        for range_idx, comm_range in enumerate(distance_ranges):
            points = [d for d in data_points 
                     if d['mode'] == mode and d['comm_range'] == comm_range]
            
            if not points:
                continue
            
            # Group by gini (rounded for grouping)
            gini_groups = {}
            for point in points:
                gini_key = round(point['gini'], 3)  # Round to 0.001 precision
                if gini_key not in gini_groups:
                    gini_groups[gini_key] = {'latencies': [], 'ginis': []}
                gini_groups[gini_key]['latencies'].append(point['mean_latency'])
                gini_groups[gini_key]['ginis'].append(point['gini'])
            
            x_vals = []
            y_vals = []
            y_stds = []
            
            for gini_key in sorted(gini_groups.keys()):
                x_vals.append(np.mean(gini_groups[gini_key]['ginis']))
                y_vals.append(np.mean(gini_groups[gini_key]['latencies']))
                y_stds.append(np.std(gini_groups[gini_key]['latencies']))
            
            if x_vals:
                ax.errorbar(x_vals, y_vals, yerr=y_stds,
                           marker=markers[range_idx % len(markers)], 
                           markersize=4,
                           linewidth=1,
                           capsize=3,
                           capthick=1,
                           label=f'{int(comm_range)}m range',
                           color=colors_local[range_idx])
        
        ax.set_xlabel('Gini Coefficient', fontsize=12)
        ax.set_ylabel('Mean Latency (seconds)', fontsize=12)
        ax.set_title('Mean Latency vs Gini Coefficient', fontsize=14)
        ax.grid(True, alpha=0.3)
        ax.set_yscale('log')
        
        # Plot 2: Latency vs S-score
        ax = axes[1]
        for range_idx, comm_range in enumerate(distance_ranges):
            points = [d for d in data_points 
                     if d['mode'] == mode and d['comm_range'] == comm_range]
            
            if not points:
                continue
            
            # Group by s_score (rounded for grouping)
            s_groups = {}
            for point in points:
                s_key = round(point['s_score'], 4)  # Round to 0.0001 precision
                if s_key not in s_groups:
                    s_groups[s_key] = {'latencies': [], 's_scores': []}
                s_groups[s_key]['latencies'].append(point['mean_latency'])
                s_groups[s_key]['s_scores'].append(point['s_score'])
            
            x_vals = []
            y_vals = []
            y_stds = []
            
            for s_key in sorted(s_groups.keys()):
                x_vals.append(np.mean(s_groups[s_key]['s_scores']))
                y_vals.append(np.mean(s_groups[s_key]['latencies']))
                y_stds.append(np.std(s_groups[s_key]['latencies']))
            
            if x_vals:
                ax.errorbar(x_vals, y_vals, yerr=y_stds,
                           marker=markers[range_idx % len(markers)], 
                           markersize=4,
                           linewidth=1,
                           capsize=3,
                           capthick=1,
                           label=f'{int(comm_range)}m range',
                           color=colors_local[range_idx])
        
        ax.set_xlabel('Centralization Score S', fontsize=12)
        ax.set_ylabel('Mean Latency (seconds)', fontsize=12)
        ax.set_title('Mean Latency vs Centralization Score', fontsize=14)
        ax.grid(True, alpha=0.3)
        ax.set_yscale('log')
        
        # Shared legend
        handles, labels = axes[1].get_legend_handles_labels()
        fig.legend(handles, labels, loc='lower center', ncol=min(len(labels), 3), 
                  bbox_to_anchor=(0.5, -0.02), fontsize=11, frameon=True)
        
        plt.suptitle(f'Mean Latency vs Centralization Metrics\n{mode_names[mode]} - {range_label}',
                    fontsize=14, fontweight='bold', y=0.995)
        plt.tight_layout(rect=[0, 0.03, 1, 0.98])
        plt.savefig(f'figures/latency_vs_centralization_{filename_suffix}.png', 
                   dpi=300, bbox_inches='tight')
        plt.close()
    
    # Generate plots for each mode and distance range combination
    # for mode in [0, 1]:
    for mode in [1]:
        mode_suffix = 'intra' if mode == 0 else 'inter'
        
        # # Low distances
        # if low_ranges:
        #     plot_for_mode_and_ranges(mode, low_ranges, "Low Distances: ≤40m", 
        #                             f"{mode_suffix}_low_dist")
        
        # High distances
        if high_ranges:
            plot_for_mode_and_ranges(mode, high_ranges, "High Distances: 50-100m", 
                                    f"{mode_suffix}_high_dist")
        
        # # All distances
        plot_for_mode_and_ranges(mode, ranges, "All Distances", f"{mode_suffix}_all_dist")

def plot_topology_and_distance_matrices(all_messages: list[Message], topologies: dict[Configuration, Topology]):
    """
    Generate topology and distance matrix plots for each range and max_degree.
    
    Uses non-randomized topologies (run_randomize_seed=0, run=1) for consistent visualization.
    
    Creates combined plots with 1 row × 3 columns:
    - Left: Distance matrix (same for both modes)
    - Middle: Topology matrix for intra-cluster mode
    - Right: Topology matrix for inter-cluster mode
    
    Args:
        all_messages: All created messages
        topologies: Dictionary mapping configuration (range, mode, max_degree, run) to topology
    """
    
    # Create directory for plots
    plots_dir = "figures/topology_distance_matrices"
    os.makedirs(plots_dir, exist_ok=True)
    
    # Get unique ranges and max_degrees
    ranges = sorted(set(msg.communication_range for msg in all_messages))
    max_degrees = sorted(set(msg.max_degree for msg in all_messages))
    modes = [0, 1]  # intra-cluster, inter-cluster
    messages_by_degree = { (comm_range, mode, max_deg): [] for comm_range in ranges for max_deg in max_degrees for mode in modes }
    for message in all_messages:
        key = (message.communication_range, message.mode, message.max_degree)
        messages_by_degree[key].append(message)
    
    max_range = float(max(ranges))   
    for comm_range in [max_range]:
        for max_deg in max_degrees:
            print(f"Processing topology/distance matrices for range {comm_range}m, max_degree={max_deg}...")
            
            # Create figure with 1 row × 3 columns
            fig, axes = plt.subplots(1, 3, figsize=(18, 6))
            
            # Calculate distance matrix (same for both modes, use mode 0 messages)
            all_messages_mode0 = messages_by_degree[(comm_range, 0, max_deg)]
            if all_messages_mode0:
                distance_matrix = get_host_distance_matrix(all_messages_mode0)
                
                # Plot distance matrix (left)
                ax_dist = axes[0]
                im_dist = ax_dist.imshow(distance_matrix, cmap='viridis', interpolation='nearest', origin='lower')
                ax_dist.set_xlabel('Host Index', fontsize=16)
                ax_dist.set_ylabel('Host Index', fontsize=16)
                cbar_dist = plt.colorbar(im_dist, ax=ax_dist, label='Distance (m)', fontsize=16)
            
            # Plot topology matrices for both modes
            for mode_idx, mode in enumerate(modes):
                mode_name = "Intra-cluster" if mode == 0 else "Inter-cluster"
                ax_topo = axes[mode_idx + 1]  # Index 1 for intra, 2 for inter
                
                # Get non-randomized topology (run_randomize_seed=0, run=1)
                topology_key = Configuration(range=comm_range, mode=mode, max_degree=max_deg, run_number=1, run_randomize_seed=0)
                if topology_key in topologies:
                    topology: Topology = topologies[topology_key]
                    topology_matrix = get_topology_matrix_from_connectivity(topology)
                else:
                    configurations: list[Configuration] = topologies.keys()
                    other_topologies = [config.__str__() for config in configurations if config.range == comm_range and config.mode == mode]
                    print(f"    Warning: No topology found for range {comm_range}, mode {mode}, max_degree {max_deg}, run 1, randomize_seed 0")
                    print(f"    Others: {other_topologies}")
                    raise ValueError(f"No topology found for range {comm_range}, mode {mode}, max_degree {max_deg}, run 1, randomize_seed 0")
                
                # Plot topology matrix
                im_topo = ax_topo.imshow(topology_matrix, cmap='binary', interpolation='nearest', 
                                   vmin=0, vmax=1, origin='lower')
                ax_topo.set_title(f'Topology - {mode_name}', fontsize=14, fontweight='bold')
                ax_topo.set_ylabel('Host Index', fontsize=12)
                ax_topo.set_xlabel('Host Index', fontsize=12)

            fig.suptitle(f'Communication Range: {int(comm_range)}m - Max Degree: {max_deg}', 
                        fontsize=14, fontweight='bold', y=0.98)
            
            plt.tight_layout(rect=[0, 0, 1, 0.96])
            
            plot_filename = f"{plots_dir}/range{int(comm_range)}_maxdeg{max_deg}_topology_distance.png"
            plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"  Saved: {plot_filename}")

def plot_delivery_success_matrices(all_messages: list[Message], delivered_messages: list[Message], *time_thresholds: float):
    """
    Generate delivery success probability matrix plots for each range and max_degree.
    
    Creates plots with both modes (intra-cluster and inter-cluster) as subplots for each time threshold.
    Layout: 2 rows × N columns (where N is the number of time thresholds)
    - Top row: intra-cluster delivery probability for each threshold
    - Bottom row: inter-cluster delivery probability for each threshold
    
    Args:
        all_messages: All created messages
        delivered_messages: Successfully delivered messages
        *time_thresholds: Variable number of time thresholds for delivery success calculation
    
    Example:
        plot_delivery_success_matrices(all_msgs, delivered_msgs, 10.0, 60.0, 240.0)
    """
    
    if not time_thresholds:
        print("Error: At least one time threshold must be provided")
        return
    
    # Create directory for plots
    plots_dir = "figures/delivery_success_matrices"
    os.makedirs(plots_dir, exist_ok=True)
    
    # Get unique ranges and max_degrees
    ranges = sorted(set(msg.communication_range for msg in all_messages))
    max_degrees = sorted(set(msg.max_degree for msg in all_messages))
    modes = [0, 1]  # intra-cluster, inter-cluster
    
    messages_by_degree = { (comm_range, mode, max_deg): [] for comm_range in ranges for max_deg in max_degrees for mode in modes }
    delivered_by_degree = { (comm_range, mode, max_deg): [] for comm_range in ranges for max_deg in max_degrees for mode in modes }
    
    for message in all_messages:
        key = (message.communication_range, message.mode, message.max_degree)
        messages_by_degree[key].append(message)
    for message in delivered_messages:
        key = (message.communication_range, message.mode, message.max_degree)
        delivered_by_degree[key].append(message)
    
    max_range = float(max(ranges))   
    for comm_range in [max_range]:
        for max_deg in max_degrees:
            # Create filename suffix with all thresholds
            threshold_str = "_".join([f"{int(t)}s" for t in time_thresholds])
            print(f"Processing delivery success matrices for range {comm_range}m, max_degree={max_deg}, thresholds={threshold_str}...")
            
            # Get runs for statistics (same across all modes and thresholds)
            sample_key = (comm_range, 0, max_deg)
            all_messages_sample = messages_by_degree[sample_key]
            runs = sorted(set(msg.run for msg in all_messages_sample)) if all_messages_sample else []
            
            # Create separate plots for each mode
            for mode in modes:
                mode_name = "intra" if mode == 0 else "inter"
                mode_name_title = "Intra-cluster" if mode == 0 else "Inter-cluster"
                
                # Create figure with N rows × 1 column (vertical layout)
                n_thresholds = len(time_thresholds)
                fig_height = 3.5 * n_thresholds  # 3.5 inches per threshold row (matches centralization plots)
                
                # Use gridspec to have more control over layout
                fig = plt.figure(figsize=(5, fig_height), constrained_layout=True)
                gs = fig.add_gridspec(n_thresholds, 2, width_ratios=[20, 1], wspace=0.15)
                
                # Create axes for matrices (left column)
                axes = [fig.add_subplot(gs[i, 0]) for i in range(n_thresholds)]
                
                # Store the image for later colorbar creation
                im_for_colorbar = None
                
                # Plot each threshold as a row
                for threshold_idx, time_threshold in enumerate(time_thresholds):
                    ax = axes[threshold_idx]
                    
                    # Filter messages for this range, mode, and max_degree (across all runs)
                    all_messages_filtered = messages_by_degree[(comm_range, mode, max_deg)]
                    delivered_messages_filtered = delivered_by_degree[(comm_range, mode, max_deg)]
                    
                    if not all_messages_filtered:
                        print(f"  No messages found for {mode_name} mode")
                        # Mark axes as empty
                        ax.text(0.5, 0.5, f'No data for {mode_name}-cluster', 
                               ha='center', va='center', transform=ax.transAxes, fontsize=16)
                        ax.set_xticks([])
                        ax.set_yticks([])
                        continue
                    
                    # Calculate delivery success matrix for this threshold
                    success_matrix = get_delivery_success_matrix(all_messages_filtered, delivered_messages_filtered, time_threshold)
                    
                    # Calculate statistics
                    n_messages = len(all_messages_filtered)
                    delivered_at_threshold = [msg for msg in delivered_messages_filtered if msg.delivery_time <= time_threshold]
                    n_delivered = len(delivered_at_threshold)
                    delivery_rate = (n_delivered / n_messages * 100) if n_messages > 0 else 0
                    
                    # Plot delivery success matrix
                    im = ax.imshow(success_matrix, cmap='RdYlGn', interpolation='nearest', 
                                  vmin=0, vmax=1, origin='lower', aspect='equal')
                    
                    # Store image for colorbar (use the last one)
                    im_for_colorbar = im
                    
                    # Set title with threshold
                    ax.set_title(f'Threshold: {int(time_threshold)}s, delivery rate: {delivery_rate:.1f}%', 
                               fontsize=12, pad=10)
                    
                    # Y-label on all rows
                    ax.set_ylabel('Host Index', fontsize=12)
                    
                    # X-label only on bottom row
                    if threshold_idx == n_thresholds - 1:
                        ax.set_xlabel('Host Index', fontsize=12)
                    
                    # Set equal aspect ratio to ensure square matrices
                    ax.set_aspect('equal', adjustable='box')
                    
                    # Tick label size
                    ax.tick_params(axis='both', which='major', labelsize=12)
                    
                    print(f"    {mode_name.title()}-cluster, threshold {int(time_threshold)}s: {n_delivered:,}/{n_messages:,} ({delivery_rate:.1f}%)")
                
                # Add a single colorbar in the right column, spanning all rows
                if im_for_colorbar is not None:
                    # Create colorbar axis on the right side
                    cbar_ax = fig.add_subplot(gs[:, 1])
                    cbar = fig.colorbar(im_for_colorbar, cax=cbar_ax, label='Delivery Probability')
                    cbar.ax.tick_params(labelsize=12)
                    cbar.set_label('Delivery Probability', fontsize=12)
                
                plot_filename = f"{plots_dir}/range{int(comm_range)}_maxdeg{max_deg}_{mode_name}_thresholds_{threshold_str}.png"
                plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
                plt.close()
                
                print(f"  Saved: {plot_filename}")

def plot_delivery_success_matrices_comparison(all_messages: list[Message], delivered_messages: list[Message], mode: int, *time_thresholds: float):
    """
    Generate delivery success probability matrix plots comparing multiple time thresholds for a single mode.
    
    Creates plots with 1 row × N columns (where N is the number of thresholds):
    - Each column shows the delivery probability at one time threshold
    
    Args:
        all_messages: All created messages
        delivered_messages: Successfully delivered messages
        mode: Communication mode (0 for intra-cluster, 1 for inter-cluster)
        *time_thresholds: Variable number of time thresholds for delivery success calculation
    
    Example:
        plot_delivery_success_matrices_comparison(all_msgs, delivered_msgs, 0, 10.0, 60.0, 240.0)
    """
    
    if not time_thresholds:
        print("Error: At least one time threshold must be provided")
        return
    
    # Create directory for plots
    plots_dir = "figures/delivery_success_matrices"
    os.makedirs(plots_dir, exist_ok=True)
    
    # Get unique ranges and max_degrees
    ranges = sorted(set(msg.communication_range for msg in all_messages))
    max_degrees = sorted(set(msg.max_degree for msg in all_messages))
    
    messages_by_degree = {}
    delivered_by_degree = {}
    
    for comm_range in ranges:
        for max_deg in max_degrees:
            key = (comm_range, mode, max_deg)
            messages_by_degree[key] = []
            delivered_by_degree[key] = []
    
    for message in all_messages:
        if message.mode == mode:
            key = (message.communication_range, message.mode, message.max_degree)
            messages_by_degree[key].append(message)
    
    for message in delivered_messages:
        if message.mode == mode:
            key = (message.communication_range, message.mode, message.max_degree)
            delivered_by_degree[key].append(message)
    
    mode_name = "intra" if mode == 0 else "inter"
    mode_name_title = "Intra-cluster" if mode == 0 else "Inter-cluster"
    
    max_range = float(max(ranges))   
    for comm_range in [max_range]:
        for max_deg in max_degrees:
            print(f"Processing delivery success comparison for range {comm_range}m, max_degree={max_deg}, mode={mode_name}...")
            
            # Create figure with 1 row × N columns (N = number of thresholds)
            n_thresholds = len(time_thresholds)
            fig_width = 8 * n_thresholds  # 8 inches per subplot
            fig, axes = plt.subplots(1, n_thresholds, figsize=(fig_width, 7))
            
            # Make axes iterable even if there's only one threshold
            if n_thresholds == 1:
                axes = [axes]
            
            # Filter messages for this range, mode, and max_degree
            all_messages_filtered = messages_by_degree[(comm_range, mode, max_deg)]
            delivered_messages_filtered = delivered_by_degree[(comm_range, mode, max_deg)]
            
            if not all_messages_filtered:
                print(f"  No messages found for {mode_name} mode")
                for ax in axes:
                    ax.text(0.5, 0.5, f'No data for {mode_name_title}', 
                           ha='center', va='center', transform=ax.transAxes, fontsize=14)
                    ax.set_xticks([])
                    ax.set_yticks([])
                continue
            
            # Get runs for statistics
            runs = sorted(set(msg.run for msg in all_messages_filtered))
            
            # Plot each time threshold
            for threshold_idx, time_threshold in enumerate(time_thresholds):
                ax = axes[threshold_idx]
                
                # Calculate delivery success matrix for this threshold
                success_matrix = get_delivery_success_matrix(all_messages_filtered, delivered_messages_filtered, time_threshold)
                
                # Calculate statistics
                n_messages = len(all_messages_filtered)
                delivered_at_threshold = [msg for msg in delivered_messages_filtered if msg.delivery_time <= time_threshold]
                n_delivered = len(delivered_at_threshold)
                delivery_rate = (n_delivered / n_messages * 100) if n_messages > 0 else 0
                
                # Plot delivery success matrix
                im = ax.imshow(success_matrix, cmap='RdYlGn', interpolation='nearest', 
                              vmin=0, vmax=1, origin='lower')
                ax.set_title(f'Delivery Probability\nTime Threshold: {int(time_threshold)}s', 
                           fontsize=12, fontweight='bold')
                ax.set_xlabel('Host Index', fontsize=10)
                ax.set_ylabel('Host Index', fontsize=10)
                cbar = plt.colorbar(im, ax=ax, label='Delivery Probability')
                
                # Add statistics text
                stats_text = f"Messages: {n_messages:,}\nDelivered: {n_delivered:,}\nRate: {delivery_rate:.1f}%\nRuns: {len(runs)}"
                ax.text(0.02, 0.98, stats_text,
                       transform=ax.transAxes,
                       verticalalignment='top',
                       bbox=dict(boxstyle='round', facecolor='white', alpha=0.8),
                       fontsize=9)
                
                print(f"    Threshold {int(time_threshold)}s: {n_delivered:,}/{n_messages:,} messages delivered ({delivery_rate:.1f}%)")
            
            # Add overall title
            fig.suptitle(f'Delivery Success Probability - {mode_name_title}\nRange: {int(comm_range)}m - Max Degree: {max_deg} - {len(runs)} runs', 
                        fontsize=14, fontweight='bold', y=0.98)
            
            plt.tight_layout(rect=[0, 0, 1, 0.96])  # Leave space for suptitle
            
            # Create filename with all thresholds
            threshold_str = "_".join([f"{int(t)}s" for t in time_thresholds])
            plot_filename = f"{plots_dir}/range{int(comm_range)}_maxdeg{max_deg}_{mode_name}_thresholds_{threshold_str}.png"
            plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"  Saved: {plot_filename}")

def main():
    print("Loading message data from pickle files...")

    randomized_all_messages_path = f"all_messages_randomized1.pkl"
    with open(randomized_all_messages_path, 'rb') as f:
        randomized_all_messages: list[Message] = pickle.load(f)

    randomized_delivered_messages_path = f"delivered_messages_randomized1.pkl"
    with open(randomized_delivered_messages_path, 'rb') as f:
        randomized_delivered_messages: list[Message] = pickle.load(f)

    nonrandomized_all_messages_path = f"all_messages_randomized0.pkl"
    with open(nonrandomized_all_messages_path, 'rb') as f:
        nonrandomized_all_messages: list[Message] = pickle.load(f)

    nonrandomized_delivered_messages_path = f"fixed_delivered_messages_randomized0.pkl"
    with open(nonrandomized_delivered_messages_path, 'rb') as f:
        nonrandomized_delivered_messages: list[Message] = pickle.load(f)


    with open(f"topologies_randomized1.pkl", 'rb') as f:
        randomized_topologies: dict[Configuration, Topology] = pickle.load(f)
    with open("topologies_randomized0.pkl", 'rb') as f:
        nonrandomized_topologies: dict[Configuration, Topology] = pickle.load(f)

    print("Generating simple analysis plots...")
    plot_message_delivery_distribution(nonrandomized_all_messages, nonrandomized_delivered_messages)

    print("Generating max degree vs. throughput analysis plots...")
    plot_max_degree_vs_throughput(randomized_delivered_messages)
    plot_max_degree_vs_throughput_run_comparison(randomized_delivered_messages)

    print("Generating max degree vs. centralization metrics plots...")
    plot_metrics_vs_max_degree(randomized_delivered_messages, randomized_topologies)

    print("Generating latency vs. max degree plots...")
    plot_latency_vs_max_degree(randomized_delivered_messages, randomized_topologies)

    print("Generating latency vs. centralization metrics plots...")
    plot_latency_vs_centralization(randomized_delivered_messages, randomized_topologies)

    print("Generating centralization vs. delivery probability plots...")
    plot_centralization_vs_delivery(randomized_all_messages, randomized_delivered_messages, randomized_topologies, time_threshold=float('inf'))  # All deliveries
    plot_centralization_vs_delivery(randomized_all_messages, randomized_delivered_messages, randomized_topologies, time_threshold=10.0)
    plot_centralization_vs_delivery(randomized_all_messages, randomized_delivered_messages, randomized_topologies, time_threshold=240.0)

    print("Generating topology and distance matrix plots...")
    plot_topology_and_distance_matrices(nonrandomized_all_messages, nonrandomized_topologies)

    print("Generating delivery success probability plots...")
    plot_delivery_success_matrices(nonrandomized_all_messages, nonrandomized_delivered_messages, 10.0, 60.0)

    print("\nAll plots generated successfully!")

if __name__ == "__main__":
    main()
