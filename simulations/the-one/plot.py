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

def calculate_l0_norm(node_degrees: list[float]) -> float:
    """
    Calculate the L0 norm (sparsity) of node degrees.
    
    The L0 norm counts the number of non-zero elements, indicating how many
    nodes are actively participating in the network (have at least one connection).
    
    Args:
        node_degrees: List of node degrees
        
    Returns:
        Ratio of active nodes (L0 / total nodes), ranging from 0 to 1
    """
    if not node_degrees or len(node_degrees) == 0:
        return 0.0
    
    # Remove any NaN or infinite values
    degrees = [d for d in node_degrees if np.isfinite(d)]
    
    if len(degrees) == 0:
        return 0.0
    
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

def plot_latency_cdf(delivered_messages):
    """Plot CDF of delivered message latencies"""
    # Increase figure height to accommodate labels
    fig, ax = plt.subplots(figsize=(12, 10))
    
    ranges = sorted(np.unique([msg.communication_range for msg in delivered_messages]), key=int)
    colors = plt.cm.viridis(np.linspace(0, 1, len(ranges)))
    
    special_percentiles = [50, 99.9, 99.99, 99.999, 99.9999]
    plotting_percentiles = [0] + special_percentiles
    percentile_stats = {}
    
    tick_positions = np.arange(len(special_percentiles))
    all_positions = np.arange(-1, len(special_percentiles))
    
    for i, comm_range in enumerate(ranges):
        messages_for_range = list(filter(lambda msg, r_inner=float(comm_range): 
                                      msg.communication_range == r_inner and msg.delivery_time > 0, 
                                      delivered_messages))
        
        latencies = sorted([msg.delivery_time for msg in messages_for_range])
        
        # Skip this range if no messages were delivered (empty latencies array)
        if not latencies:
            print(f"Warning: No delivered messages found for communication range {int(comm_range)}m - skipping this range in latency plot")
            continue
            
        percentiles = np.arange(1, len(latencies) + 1) / len(latencies) * 100
        
        plot_positions = []
        plot_latencies = []
        
        for j, p in enumerate(plotting_percentiles):
            if p == 0:
                # 0th percentile is the minimum latency
                latency_at_percentile = latencies[0]
                position = all_positions[j]  # -1
            else:
                latency_at_percentile = np.interp(p, percentiles, latencies)
                position = all_positions[j]
                
            plot_positions.append(position)
            plot_latencies.append(latency_at_percentile)
        
        ax.plot(plot_positions, plot_latencies, 
                label=f'{int(comm_range)}m range', 
                color=colors[i],
                linewidth=2.5,
                marker='o',
                markersize=4)
        
        percentile_stats[comm_range] = {
            p: np.interp(p, percentiles, latencies) 
            for p in special_percentiles
        }

    # Set x-axis limits to show from 0% position to highest percentile with margin
    ax.set_xlim(-1.2, len(special_percentiles) - 0.5)
    
    xticks = tick_positions 
    xticklabels = ['50%', '99.9%', '99.99%', '99.999%', '99.9999%']
    
    ax.set_xticks(xticks)
    ax.set_xticklabels(xticklabels)    
    ax.set_xlabel('Percentile (%)', fontsize=12)
    ax.set_ylabel('Latency (seconds)', fontsize=12)
    ax.set_title('Latency Percentile Distribution', fontsize=14, pad=20)
    
    ax.legend(loc='upper left', 
             fontsize=10, 
             framealpha=0.9,
             title='Communication Ranges')
    ax.set_yscale('log')
    
    # Adjust layout with more space for labels
    plt.subplots_adjust(left=0.15)  # Increase left margin
    plt.savefig(f'figures/latency_percentiles.png',
                bbox_inches='tight', dpi=300)
    plt.close()

def plot_node_degree_vs_latency(messages):
    """Plot relationship between node degree and hop latency with separate curves per max node degree"""
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Create data points for each hop
    data = []
    for msg in messages:
        if msg.hops:
            for hop in msg.hops:
                if hop.hop_time > 0:
                    data.append({
                        'max_degree': msg.max_degree,
                        'node_degree': hop.from_node_degree,
                        'hop_latency': hop.hop_time
                    })
    
    df = pd.DataFrame(data)
    
    # Get unique max_degrees and create colors/markers
    max_degrees = sorted(df['max_degree'].unique())
    colors = plt.cm.viridis(np.linspace(0, 1, len(max_degrees)))
    markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h', 'H', '+', 'x']
    
    # Create binned statistics for each max_degree
    bins = np.arange(0, 51, 5)  # 0-50 in steps of 5
    
    for idx, max_deg in enumerate(max_degrees):
        # Filter data for this max_degree
        df_max_deg = df[df['max_degree'] == max_deg]
        
        bin_means = []
        bin_stds = []
        bin_centers = []
        
        for j in range(len(bins)-1):
            mask = (df_max_deg['node_degree'] >= bins[j]) & (df_max_deg['node_degree'] < bins[j+1])
            if mask.any():
                bin_means.append(df_max_deg[mask]['hop_latency'].mean())
                bin_stds.append(df_max_deg[mask]['hop_latency'].std())
                bin_centers.append((bins[j] + bins[j+1]) / 2)
        
        if bin_means:
            bin_means = np.array(bin_means)
            bin_stds = np.array(bin_stds)
            bin_centers = np.array(bin_centers)
            
            # Plot mean line with marker
            ax.plot(bin_centers, bin_means,
                    color=colors[idx],
                    linewidth=2,
                    marker=markers[idx % len(markers)],
                    markersize=8,
                    label=f'Max Degree {int(max_deg)}')
            
            # Add standard deviation band
            ax.fill_between(bin_centers,
                            bin_means - bin_stds,
                            bin_means + bin_stds,
                            alpha=0.15,
                            color=colors[idx])
    
    # Customize plot
    ax.set_xlabel('Node Degree', fontsize=12)
    ax.set_ylabel('Hop Latency (s)', fontsize=12)
    ax.set_title('Node Degree vs Hop Latency by Max Node Degree', fontsize=14)
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best', fontsize=10)
    
    plt.tight_layout()
    plt.savefig(f'figures/node_degree_vs_hoplatency_by_maxdegree.png',
                bbox_inches='tight', dpi=300)
    plt.close()

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
    
    # Calculate average throughput per group
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
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
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
    ax1.set_xlabel('Maximum Allowed Node Degree')
    ax1.set_ylabel('Average Throughput (bytes/second)')
    ax1.set_title('Average Throughput vs Maximum Node Degree (Intra-cluster)')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
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
    ax2.set_ylabel('Average Throughput (bytes/second)')
    ax2.set_title('Average Throughput vs Maximum Node Degree (Inter-cluster)')
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    plt.tight_layout()
    plt.savefig('figures/max_degree_vs_throughput.png', dpi=300, bbox_inches='tight')
    plt.close()

def plot_metrics_vs_max_degree(delivered_messages: list[Message], topologies: dict[Configuration, Topology]):
    """
    Plot Gini coefficient, centralization score, and L0 norm vs max node degree,
    split by mode (intra/inter-cluster), with one curve for each communication range.
    
    Creates 6 subplots (3x2 grid):
    - Top row: Gini coefficient (intra, inter)
    - Middle row: Centralization score S (intra, inter)
    - Bottom row: L0 norm / sparsity (intra, inter)
    """
    TOTAL_NODES = 72
    
    config_keys = set()
    for msg in delivered_messages:
        config_keys.add((msg.mode, msg.communication_range, msg.max_degree))
    
    modes = sorted(set(k[0] for k in config_keys))
    ranges = sorted(set(k[1] for k in config_keys))
    max_degrees = sorted(set(k[2] for k in config_keys))
    
    # Create 3x2 subplot grid
    fig, axes = plt.subplots(3, 2, figsize=(16, 18))
    
    mode_names = {0: 'Intra-cluster', 1: 'Inter-cluster'}
    colors = plt.cm.viridis(np.linspace(0, 1, len(ranges)))
    markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h', 'H', '+', 'x']  # Different marker shapes
    
    # Plot Gini coefficient (top row)
    for mode_idx, mode in enumerate(modes):
        ax = axes[0, mode_idx]
        
        for range_idx, comm_range in enumerate(ranges):
            x_vals = []
            y_vals = []
            
            for max_deg in max_degrees:
                num_run = 1
                config = Configuration(run_number=num_run, range=comm_range, max_degree=max_deg, mode=mode)
                topology = topologies.get(config)
                
                if topology is None:
                    raise ValueError(f"Topology not found for config: {config}")
                
                degrees_list = []
                for node_id in range(TOTAL_NODES):
                    node_name = str(node_id)
                    if node_name in topology.connections:
                        degrees_list.append(len(topology.connections[node_name]))
                    else:
                        degrees_list.append(0)  # Isolated node
                
                gini_coef = calculate_gini_coefficient(degrees_list)
                x_vals.append(max_deg)
                y_vals.append(gini_coef)
            
            if x_vals:
                ax.plot(x_vals, y_vals, 
                       marker=markers[range_idx % len(markers)], 
                       markersize=8,
                       linewidth=2,
                       label=f'{int(comm_range)}m range',
                       color=colors[range_idx])
        
        ax.set_xlabel('Maximum Allowed Node Degree', fontsize=12)
        ax.set_ylabel('Gini Coefficient', fontsize=12)
        ax.set_title(f'Gini Coefficient - {mode_names[mode]}', fontsize=14)
        ax.set_ylim(0, 1)  # Gini coefficient ranges from 0 to 1
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best', fontsize=10)
    
    # Plot Centralization Score (middle row)
    for mode_idx, mode in enumerate(modes):
        ax = axes[1, mode_idx]
        
        for range_idx, comm_range in enumerate(ranges):
            x_vals = []
            y_vals = []
            
            for max_deg in max_degrees:
                # Get the actual topology to extract ALL node degrees
                num_run = 1
                config = Configuration(run_number=num_run, range=comm_range, max_degree=max_deg, mode=mode)
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
                
                if len(degrees_list) > 1:
                    num_links = topology.get_number_of_links()
                    centralization = calculate_centralization_score(degrees_list, num_links)
                    x_vals.append(max_deg)
                    y_vals.append(centralization)
            
            if x_vals:
                ax.plot(x_vals, y_vals, 
                       marker=markers[range_idx % len(markers)], 
                       markersize=8,
                       linewidth=2,
                       label=f'{int(comm_range)}m range',
                       color=colors[range_idx])
        
        ax.set_xlabel('Maximum Allowed Node Degree', fontsize=12)
        ax.set_ylabel('Centralization Score S', fontsize=12)
        ax.set_title(f'Centralization Score - {mode_names[mode]}', fontsize=14)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right', fontsize=9)
    
    # Plot L0 Norm (bottom row)
    for mode_idx, mode in enumerate(modes):
        ax = axes[2, mode_idx]
        
        for range_idx, comm_range in enumerate(ranges):
            x_vals = []
            y_vals = []
            
            for max_deg in max_degrees:
                # Get the actual topology to extract ALL node degrees
                num_run = 1
                config = Configuration(run_number=num_run, range=comm_range, max_degree=max_deg, mode=mode)
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
                
                if len(degrees_list) > 1:
                    l0_norm = calculate_l0_norm(degrees_list)
                    x_vals.append(max_deg)
                    y_vals.append(l0_norm)
            
            if x_vals:
                ax.plot(x_vals, y_vals, 
                       marker=markers[range_idx % len(markers)], 
                       markersize=8,
                       linewidth=2,
                       label=f'{int(comm_range)}m range',
                       color=colors[range_idx])
        
        ax.set_xlabel('Maximum Allowed Node Degree', fontsize=12)
        ax.set_ylabel('L0 Norm (Active Node Ratio)', fontsize=12)
        ax.set_title(f'Network Sparsity (L0) - {mode_names[mode]}', fontsize=14)
        ax.set_ylim(0, 1.05)  # L0 ratio ranges from 0 to 1
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best', fontsize=10)

    plt.suptitle('Network Centralization Metrics vs Maximum Node Degree',
                 fontsize=16, y=0.997)
    plt.tight_layout()
    plt.savefig('figures/centralization_metrics_vs_max_degree.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print("Centralization metrics plot generated successfully!")

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
        ax.set_ylabel('Average Throughput (bytes/second)')
        ax.set_title(f'Throughput vs Max Degree\nCommunication Range: {comm_range}m')
        ax.grid(True, alpha=0.3)
        ax.legend()
    
    plt.tight_layout()
    plt.savefig('figures/max_degree_vs_throughput_run_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()

def plot_message_frequency_by_distance(messages: list[Message], num_bins=20):
    """Plot frequency of created messages per distance with mode analysis"""
    # Create a figure with subplots: original plot + mode comparison
    fig = plt.figure(figsize=(16, 12))
    
    # Extract distances from all messages (including failed deliveries)
    distances = [msg.distance for msg in messages if msg.distance > 0]
    
    if not distances:
        print("No valid distance data found for message frequency plot")
        return
    
    min_dist = min(distances)
    max_dist = max(distances)
    distance_bins = np.linspace(min_dist, max_dist, num_bins + 1)
    bin_centers = (distance_bins[:-1] + distance_bins[1:]) / 2
    bin_width = distance_bins[1] - distance_bins[0]
    
    # Subplot 1: Original message frequency plot
    ax1 = plt.subplot(2, 2, (1, 2))  # Top row, spans both columns
    
    message_counts = []
    for i in range(len(distance_bins)-1):
        count = sum(1 for d in distances if distance_bins[i] <= d < distance_bins[i+1])
        message_counts.append(count)
    
    bars = ax1.bar(bin_centers, message_counts, 
                  width=bin_width * 0.8, 
                  alpha=0.7, 
                  color='skyblue',
                  edgecolor='navy',
                  linewidth=0.5)
    
    # Add count labels on top of bars
    for bar, count in zip(bars, message_counts):
        if count > 0:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                   f'{count}',
                   ha='center', va='bottom',
                   fontsize=9)
    
    total_messages = len(distances)
    mean_distance = np.mean(distances)
    std_distance = np.std(distances)
    
    stats_text = f"Statistics:\n"
    stats_text += f"Total messages: {total_messages:,}\n"
    stats_text += f"Mean distance: {mean_distance:.1f} m\n"
    stats_text += f"Std deviation: {std_distance:.1f} m\n"
    stats_text += f"Distance range: {min_dist:.1f} - {max_dist:.1f} m"
    
    ax1.text(0.98, 0.98, stats_text,
            transform=ax1.transAxes,
            verticalalignment='top',
            horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8),
            fontsize=10)
    
    ax1.set_xlabel('Distance (m)', fontsize=12)
    ax1.set_ylabel('Number of Messages', fontsize=12)
    ax1.set_title('Message Creation Frequency by Distance', fontsize=14)
    ax1.grid(True, alpha=0.3, axis='y')
    ax1.set_xlim(min_dist - bin_width/2, max_dist + bin_width/2)
    
    # Subplot 2: Intra-cluster messages
    ax2 = plt.subplot(2, 2, 3)
    
    intra_messages = [msg for msg in messages if msg.distance > 0 and msg.mode == 0]
    intra_distances = [msg.distance for msg in intra_messages]
    
    if intra_distances:
        intra_counts = []
        for i in range(len(distance_bins)-1):
            count = sum(1 for d in intra_distances if distance_bins[i] <= d < distance_bins[i+1])
            intra_counts.append(count)
        
        bars_intra = ax2.bar(bin_centers, intra_counts,
                            width=bin_width * 0.8,
                            alpha=0.7,
                            color='lightgreen',
                            edgecolor='darkgreen',
                            linewidth=0.5)
        
        # Add count labels on top of bars for intra-cluster
        for bar, count in zip(bars_intra, intra_counts):
            if count > 0:
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height,
                       f'{count}',
                       ha='center', va='bottom',
                       fontsize=8)
        
        ax2.set_title('Intra-cluster Messages', fontsize=12, color='darkgreen')
        ax2.text(0.02, 0.98, f'Total: {len(intra_distances):,}',
                transform=ax2.transAxes,
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8),
                fontsize=10)
    else:
        ax2.text(0.5, 0.5, 'No intra-cluster\nmessages found',
                transform=ax2.transAxes,
                ha='center', va='center',
                fontsize=12)
        ax2.set_title('Intra-cluster Messages', fontsize=12, color='darkgreen')
    
    ax2.set_xlabel('Distance (m)', fontsize=10)
    ax2.set_ylabel('Number of Messages', fontsize=10)
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.set_xlim(min_dist - bin_width/2, max_dist + bin_width/2)
    
    # Subplot 3: Inter-cluster messages
    ax3 = plt.subplot(2, 2, 4)
    
    inter_messages = [msg for msg in messages if msg.distance > 0 and msg.mode == 1]
    inter_distances = [msg.distance for msg in inter_messages]
    
    if inter_distances:
        inter_counts = []
        for i in range(len(distance_bins)-1):
            count = sum(1 for d in inter_distances if distance_bins[i] <= d < distance_bins[i+1])
            inter_counts.append(count)
        
        bars_inter = ax3.bar(bin_centers, inter_counts,
                            width=bin_width * 0.8,
                            alpha=0.7,
                            color='lightcoral',
                            edgecolor='darkred',
                            linewidth=0.5)
        
        # Add count labels on top of bars for inter-cluster
        for bar, count in zip(bars_inter, inter_counts):
            if count > 0:
                height = bar.get_height()
                ax3.text(bar.get_x() + bar.get_width()/2., height,
                       f'{count}',
                       ha='center', va='bottom',
                       fontsize=8)
        
        ax3.set_title('Inter-cluster Messages', fontsize=12, color='darkred')
        ax3.text(0.02, 0.98, f'Total: {len(inter_distances):,}',
                transform=ax3.transAxes,
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.8),
                fontsize=10)
    else:
        ax3.text(0.5, 0.5, 'No inter-cluster\nmessages found',
                transform=ax3.transAxes,
                ha='center', va='center',
                fontsize=12)
        ax3.set_title('Inter-cluster Messages', fontsize=12, color='darkred')
    
    ax3.set_xlabel('Distance (m)', fontsize=10)
    ax3.set_ylabel('Number of Messages', fontsize=10)
    ax3.grid(True, alpha=0.3, axis='y')
    ax3.set_xlim(min_dist - bin_width/2, max_dist + bin_width/2)
    
    plt.tight_layout()
    plt.savefig('figures/message-distance-distribution.png', 
                bbox_inches='tight', dpi=300)
    plt.close()

def plot_delivery_under_threshold_matrices(all_messages: list[Message], delivered_messages: list[Message], topologies: dict[Configuration, Topology], time_threshold: float = 10.0):
    """
    Generate distance, delivery success, and topology matrix plots for each range and max_degree.
    
    Creates combined plots with both modes (intra-cluster and inter-cluster) as subplots.
    Layout: 2 rows × 3 columns (6 subplots total)
    - Top row: intra-cluster (Distance, Delivery, Topology)
    - Bottom row: inter-cluster (Distance, Delivery, Topology)
    
    Since host locations are fixed (not randomized per run), we aggregate delivery statistics
    across all runs for better statistical significance.
    
    Args:
        all_messages: All created messages
        delivered_messages: Successfully delivered messages
        topologies: Dictionary mapping configuration (range, mode, max_degree, run) to topology
        time_threshold: Time threshold for delivery success calculation
    """
    
    # Create directory for plots
    plots_dir = "figures/matrix_plots_by_degree"
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
            print(f"Processing range {comm_range}m, max_degree={max_deg}...")
            
            # Create figure with 2 rows × 3 columns
            fig, axes = plt.subplots(2, 3, figsize=(20, 13))
            
            # Store statistics for both modes
            stats_info = {}
            
            for mode_idx, mode in enumerate(modes):
                mode_name = "intra" if mode == 0 else "inter"
                
                # Filter messages for this range, mode, and max_degree (across all runs)
                # all_messages_filtered = [msg for msg in all_messages 
                #                         if msg.communication_range == comm_range 
                #                         and msg.mode == mode
                #                         and msg.max_degree == max_deg]
                # delivered_messages_filtered = [msg for msg in delivered_messages 
                #                               if msg.communication_range == comm_range 
                #                               and msg.mode == mode
                #                               and msg.max_degree == max_deg]
                all_messages_filtered = messages_by_degree[(comm_range, mode, max_deg)]
                delivered_messages_filtered = delivered_by_degree[(comm_range, mode, max_deg)]
                
                if not all_messages_filtered:
                    print(f"  No messages found for {mode_name} mode")
                    # Mark axes as empty
                    for col_idx in range(3):
                        ax = axes[mode_idx, col_idx]
                        ax.text(0.5, 0.5, f'No data for {mode_name}-cluster', 
                               ha='center', va='center', transform=ax.transAxes, fontsize=14)
                        ax.set_xticks([])
                        ax.set_yticks([])
                    continue
                
                # Get runs for statistics
                runs = sorted(set(msg.run for msg in all_messages_filtered))
                
                # Get topology from first run
                topology_key = Configuration(range=comm_range, mode=mode, max_degree=max_deg, run_number=runs[0])
                if topology_key in topologies:
                    topology: Topology = topologies[topology_key]
                    topology_matrix = get_topology_matrix_from_connectivity(topology)
                else:
                    configurations: list[Configuration] = topologies.keys()
                    other_topologies = [config.__str__() for config in configurations if config.range == comm_range and config.mode == mode]
                    print(f"    Warning: No topology found for range {comm_range}, mode {mode}, max_degree {max_deg}, run {runs[0]}")
                    print(f"    Others: {other_topologies}")
                    raise ValueError(f"No topology found for range {comm_range}, mode {mode}, max_degree {max_deg}, run {runs[0]}")
                    topology_matrix = np.zeros((72, 72))
                
                # Calculate matrices
                distance_matrix = get_host_distance_matrix(all_messages_filtered)
                success_matrix = get_delivery_success_matrix(all_messages_filtered, delivered_messages_filtered, time_threshold)
                
                # Calculate statistics
                n_messages = len(all_messages_filtered)
                n_delivered = len(delivered_messages_filtered)
                delivery_rate = (n_delivered / n_messages * 100) if n_messages > 0 else 0
                stats_info[mode_name] = {
                    'n_messages': n_messages,
                    'n_delivered': n_delivered,
                    'delivery_rate': delivery_rate,
                    'n_runs': len(runs)
                }
                
                # Plot distance matrix (column 0)
                ax_dist = axes[mode_idx, 0]
                im1 = ax_dist.imshow(distance_matrix, cmap='viridis', interpolation='nearest', origin='lower')
                ax_dist.set_title(f'Distance Matrix - {mode_name.title()}-cluster', 
                                fontsize=11, fontweight='bold')
                ax_dist.set_xlabel('Host Index', fontsize=10)
                ax_dist.set_ylabel('Host Index', fontsize=10)
                cbar1 = plt.colorbar(im1, ax=ax_dist, label='Distance (m)')
                
                # Plot delivery success matrix (column 1)
                ax_delivery = axes[mode_idx, 1]
                im2 = ax_delivery.imshow(success_matrix, cmap='RdYlGn', interpolation='nearest', 
                                       vmin=0, vmax=1, origin='lower')
                ax_delivery.set_title(f'Delivery Probability - {mode_name.title()}-cluster - Time Threshold: {int(time_threshold)}s', 
                                    fontsize=11, fontweight='bold')
                ax_delivery.set_xlabel('Host Index', fontsize=10)
                ax_delivery.set_ylabel('Host Index', fontsize=10)
                cbar2 = plt.colorbar(im2, ax=ax_delivery, label='Delivery Probability')
                
                # Plot topology matrix (column 2)
                ax_topo = axes[mode_idx, 2]
                im3 = ax_topo.imshow(topology_matrix, cmap='binary', interpolation='nearest', 
                                   vmin=0, vmax=1, origin='lower')
                ax_topo.set_title(f'Topology - {mode_name.title()}-cluster', 
                                fontsize=11, fontweight='bold')
                ax_topo.set_xlabel('Host Index', fontsize=10)
                ax_topo.set_ylabel('Host Index', fontsize=10)
                cbar3 = plt.colorbar(im3, ax=ax_topo, label='Link', ticks=[0, 1])
                
                print(f"    {mode_name.title()}-cluster: {n_messages:,} messages, {delivery_rate:.1f}% delivery rate")
            
            # Add overall title
            fig.suptitle(f'Communication Range: {int(comm_range)}m - Max Degree: {max_deg} - {len(runs)} runs', 
                        fontsize=14, fontweight='bold', y=0.995)
            
            plt.tight_layout(rect=[0, 0, 1, 0.99])  # Leave space for suptitle
            
            plot_filename = f"{plots_dir}/range{int(comm_range)}_maxdeg{max_deg}_threshold{int(time_threshold)}s.png"
            plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"  Saved: {plot_filename}")

def main():
    print("Loading message data from pickle files...")
    
    try:
        with open("delivered_messages.pkl", 'rb') as f:
            delivered_messages: list[Message] = pickle.load(f)
        
        with open("all_messages.pkl", 'rb') as f:
            all_messages: list[Message] = pickle.load(f)
        
        with open("topologies.pkl", 'rb') as f:
            topologies: dict[Configuration, Topology] = pickle.load(f)
            
        print(f"Loaded {len(delivered_messages)} delivered messages, {len(all_messages)} total messages")
        print(f"Loaded {len(topologies)} topology snapshots")
    except FileNotFoundError as e:
        print(f"Error: Could not find pickle files. Please run load_data.py first to generate them.")
        print(f"Missing file: {e.filename}")
        return

    print("Generating simple analysis plots...")
    plot_latency_cdf(delivered_messages)
    plot_node_degree_vs_latency(delivered_messages)
    plot_max_degree_vs_throughput(delivered_messages)
    plot_message_frequency_by_distance(delivered_messages)

    print("Generating max degree vs. throughput analysis plots...")
    plot_max_degree_vs_throughput(delivered_messages)
    plot_max_degree_vs_throughput_run_comparison(delivered_messages)

    print("Generating max degree vs. centralization metrics plots...")
    plot_metrics_vs_max_degree(delivered_messages, topologies)

    print("Generating topological delivery success plots...")
    plot_delivery_under_threshold_matrices(all_messages, delivered_messages, topologies, time_threshold=10.0)
    plot_delivery_under_threshold_matrices(all_messages, delivered_messages, topologies, time_threshold=60.0)
    plot_delivery_under_threshold_matrices(all_messages, delivered_messages, topologies, time_threshold=240.0)

    print("\nAll plots generated successfully!")

if __name__ == "__main__":
    main()
