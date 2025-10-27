from typing import Optional
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pickle
from load_data import Message, Hop, HostInfo, Topology, Configuration # types needed otherwise the pickle load won't work
import os
import matplotlib.pyplot as plt

# Disclaimer: Claude 4.0 helped writing this code, especially in plotting. 
# Data processing and loading was done by us

def create_dataframe(messages: list[Message]):
    """Create a pandas DataFrame from Message objects for analysis"""
    data = []
    for msg in messages:
        if msg.hops:  # Only include messages that have hop data
            data.append({
                'Communication_Range': msg.communication_range,
                'Hop_Count': len(msg.hops),
                'Distance': msg.distance,
                'Delivery_Time': msg.delivery_time,
                'Message_Size': msg.size,
                'Source': msg.source,
                'Target': msg.target,
                'Mode': 'intra' if msg.mode == 0 else 'inter'
            })
    return pd.DataFrame(data)

def plot_hop_counts(df):
    """Plot hop count distributions for each communication range using a grouped bar plot"""
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Get unique communication ranges and create color map
    ranges = sorted(df['Communication_Range'].unique(), key=int)
    colors = plt.cm.viridis(np.linspace(0, 1, len(ranges)))
    
    # Get unique hop counts that actually exist in the data
    unique_hop_counts = sorted(df['Hop_Count'].unique())
    
    # Width of each bar and positions of bar groups
    bar_width = 0.8 / len(ranges)  # Adjust total width of group
    
    # Store frequencies for statistics
    all_frequencies = {}
    
    # First pass: calculate all frequencies to determine which hop counts to show
    hop_counts_to_show = set()
    for i, comm_range in enumerate(ranges):
        range_data = df[df['Communication_Range'] == comm_range]['Hop_Count']
        
        unique, counts = np.unique(range_data, return_counts=True)
        freq_pct = (counts / len(range_data)) * 100
        all_frequencies[comm_range] = dict(zip(unique, freq_pct))
        
        # Add hop counts that have >= 1% frequency for at least one range
        for hop_count, freq in zip(unique, freq_pct):
            if freq >= 1.0:
                hop_counts_to_show.add(hop_count)
    
    # Filter to only hop counts that will actually be displayed
    unique_hop_counts = sorted(list(hop_counts_to_show))
    
    # Plot bars for each communication range
    for i, comm_range in enumerate(ranges):
        # Use pre-calculated frequencies
        x = np.array(unique_hop_counts) + i * bar_width - (len(ranges)-1) * bar_width/2
        
        freq_array = np.zeros(len(unique_hop_counts))
        for j, hop_count in enumerate(unique_hop_counts):
            freq_value = all_frequencies[comm_range].get(hop_count, 0)
            # Only show bars with frequency >= 1%
            freq_array[j] = freq_value if freq_value >= 1.0 else 0
        
        bars = ax.bar(x, freq_array, bar_width, 
                     label=f'{int(comm_range)}m range',
                     color=colors[i],
                     alpha=0.7)
        
        # Add value labels on top of bars
        for bar, freq in zip(bars, freq_array):
            if freq > 0:  # Only add label if there's a non-zero frequency
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{freq:.1f}%',
                       ha='center', va='bottom',
                       rotation=90,
                       fontsize=8)

    ax.set_xlabel('Hop Count')
    ax.set_ylabel('Frequency (%)')
    ax.set_title('Hop Count Distribution by Communication Range')
    ax.set_xticks(unique_hop_counts)
    ax.set_xlim(min(unique_hop_counts) - 0.5, max(unique_hop_counts) + 0.5)  # Limit x-axis to observed hop counts
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_yscale('log')  # Make y-axis logarithmic to better show small frequencies
    
    plt.tight_layout()
    plt.savefig(f'figures/hopcount_distribution_by_range.png', 
                bbox_inches='tight', dpi=300)
    plt.close()

def plot_distance_vs_hopcount_by_range(df, num_bins = 20):
    fig, ax = plt.subplots(figsize=(12, 8))
    ranges: list[int] = sorted(df['Communication_Range'].unique(), key=int)
    colors = plt.cm.viridis(np.linspace(0, 1, len(ranges)))

    for comm_index, comm_range in enumerate(ranges):
        range_data = df[df['Communication_Range'] == comm_range]
        
        # Create distance bins
        min_dist = range_data['Distance'].min()
        max_dist = range_data['Distance'].max()
        distance_bins = np.linspace(min_dist, max_dist, num_bins)
        bin_centers = (distance_bins[:-1] + distance_bins[1:]) / 2
        
        mean_hops = []
        std_hops = []
        
        # Calculate mean and std for each bin
        for i in range(len(distance_bins)-1):
            mask = (range_data['Distance'] >= distance_bins[i]) & (range_data['Distance'] < distance_bins[i+1])
            bin_data = range_data[mask]['Hop_Count']
            if len(bin_data) > 0:  # Only include bins with data
                mean_hops.append(bin_data.mean())
                std_hops.append(bin_data.std())
            else:
                mean_hops.append(np.nan)
                std_hops.append(np.nan)
        
        mean_hops = np.array(mean_hops)
        std_hops = np.array(std_hops)
        
        # Remove NaN values for plotting
        valid_mask = ~np.isnan(mean_hops)
        valid_centers = bin_centers[valid_mask]
        valid_means = mean_hops[valid_mask]
        valid_stds = std_hops[valid_mask]

        line = ax.plot(valid_centers, valid_means, 
                        label=f'{int(comm_range)}m range',
                        color=colors[comm_index],
                        linewidth=2)
        
        # Plot standard deviation as shaded area
        ax.fill_between(valid_centers, 
                        valid_means - valid_stds, 
                        valid_means + valid_stds, 
                        alpha=0.2, 
                        color=line[0].get_color())
    ax.set_xlabel('Distance (m)')
    ax.set_ylabel('Average Hop Count')
    ax.set_title('Distance vs Average Hop Count by Communication Range')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f'figures/distance_hopcount_per_range.png', dpi=300, bbox_inches='tight')

def plot_latency_frequency_by_range(messages):
    """Plot percentile distribution of latencies"""
    # Increase figure height to accommodate labels
    fig, ax = plt.subplots(figsize=(12, 10))
    
    ranges = sorted(np.unique([msg.communication_range for msg in messages]), key=int)
    colors = plt.cm.viridis(np.linspace(0, 1, len(ranges)))
    
    special_percentiles = [50, 99.9, 99.99, 99.999, 99.9999]
    plotting_percentiles = [0] + special_percentiles
    percentile_stats = {}
    
    tick_positions = np.arange(len(special_percentiles))
    all_positions = np.arange(-1, len(special_percentiles))
    
    for i, comm_range in enumerate(ranges):
        messages_for_range = list(filter(lambda msg, r_inner=float(comm_range): 
                                      msg.communication_range == r_inner and msg.delivery_time > 0, 
                                      messages))
        
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
    """Plot relationship between node degree and hop latency aggregated across all communication ranges"""
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Create data points for each hop
    data = []
    for msg in messages:
        if msg.hops:
            for hop in msg.hops:
                if hop.hop_time > 0:
                    data.append({
                        'size': msg.size,
                        'node_degree': hop.from_node_degree,
                        'hop_latency': hop.hop_time
                    })
    
    df = pd.DataFrame(data)
    
    # Create binned statistics
    bins = np.arange(0, 51, 5)  # 0-50 in steps of 5
    bin_means = []
    bin_stds = []
    bin_centers = []
    bin_counts = []
    
    for j in range(len(bins)-1):
        mask = (df['node_degree'] >= bins[j]) & (df['node_degree'] < bins[j+1])
        if mask.any():
            bin_means.append(df[mask]['hop_latency'].mean())
            bin_stds.append(df[mask]['hop_latency'].std())
            bin_centers.append((bins[j] + bins[j+1]) / 2)
            bin_counts.append(len(df[mask]))
    
    bin_means = np.array(bin_means)
    bin_stds = np.array(bin_stds)
    bin_centers = np.array(bin_centers)
    
    # Plot mean line and standard deviation band
    ax.plot(bin_centers, bin_means,
            color='blue',
            linewidth=2.5)
    
    ax.fill_between(bin_centers,
                    bin_means - bin_stds,
                    bin_means + bin_stds,
                    alpha=0.2,
                    color='blue')
    
    # Set more frequent y-axis ticks (every 25 seconds)
    max_y = max(bin_means + bin_stds) + 25  # Add some padding
    y_ticks = np.arange(0, max_y, 25)
    ax.set_yticks(y_ticks)
    ax.set_yticklabels([f'{y:.0f}' for y in y_ticks])
    
    # Customize plot
    ax.set_xlabel('Node Degree')
    ax.set_ylabel('Hop Latency (s)')
    ax.set_title('Node Degree vs Hop Latency (All Communication Ranges)')
    ax.grid(True, alpha=0.3)
    
    # Add statistics in text box
    stats_text = "Statistics:\n"
    stats_text += f"Total hops: {len(df):,}\n"
    stats_text += f"Mean latency: {df['hop_latency'].mean():.2f}s\n\n"
    stats_text += "By node degree range:\n"
    
    degree_ranges = [(0, 10), (11, 20), (21, 30), (31, 40), (41, 50)]
    for min_deg, max_deg in degree_ranges:
        mask = (df['node_degree'] >= min_deg) & (df['node_degree'] <= max_deg)
        if mask.any():
            mean_lat = df[mask]['hop_latency'].mean()
            std_lat = df[mask]['hop_latency'].std()
            count = mask.sum()
            stats_text += f"Degree {min_deg}-{max_deg}:\n"
            stats_text += f"  Mean: {mean_lat:.2f}s\n"
            stats_text += f"  Std Dev: {std_lat:.2f}s\n"
            stats_text += f"  Sample size: {count:,}\n"
    
    # Add sample sizes to plot
    for x, y, count in zip(bin_centers, bin_means, bin_counts):
        ax.text(x, y + bin_stds[bin_centers == x][0], 
                f'n={count:,}',
                ha='center', va='bottom',
                fontsize=8)
    
    ax.text(1.05, 0.5, stats_text,
            transform=ax.transAxes,
            verticalalignment='center',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8),
            fontsize=9)
    
    plt.tight_layout()
    plt.savefig(f'figures/node_degree_vs_hoplatency_aggregate.png',
                bbox_inches='tight', dpi=300)
    plt.close()

def calculate_theoretical_bitrate(message_size: np.floating, distance: np.floating) -> np.floating: 
    """
    Calculate theoretical maximum bitrate based on speed of light limit.
    
    This represents the absolute physical upper bound for information transmission,
    assuming instantaneous processing and the speed of light as the only constraint.
    
    Args:
        message_size: Size of the message in bytes
        distance: Distance the message travels
    
    Returns:
        Theoretical maximum bitrate (bytes/second) based on speed of light
    """
    SPEED_OF_LIGHT = 299792458  # m/s in vacuum
    
    # Time based on speed of light (absolute physical limit)
    light_time = distance / SPEED_OF_LIGHT
    
    # Ensure minimum time to avoid division by zero
    total_time = max(float(light_time), 1e-9)  # At least 1 nanosecond

    return message_size / total_time

def plot_bitrate_vs_distance(messages: list[Message], num_bins=20, remove_outliers=True):
    """Plot bitrate vs distance - creates both aggregated and per-communication-range plots"""
    
    comm_ranges = sorted(set(msg.communication_range for msg in messages), key=int)
    all_distances = [msg.distance for msg in messages if msg.distance > 0 and msg.delivery_time > 0]
    min_dist = min(all_distances)
    max_dist = max(all_distances)
    distance_bins = np.linspace(min_dist, max_dist, num_bins)
    bin_centers = (distance_bins[:-1] + distance_bins[1:]) / 2
    distance_range = np.linspace(min_dist, max_dist, 100)
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    data = []
    for msg in messages:
        if msg.distance > 0 and msg.delivery_time > 0:
            bitrate = msg.size / msg.delivery_time
            data.append({
                'Distance': msg.distance,
                'Bitrate': bitrate,
            })
    
    df = pd.DataFrame(data)
    
    median_bitrates = []
    q1_bitrates = []
    q3_bitrates = []
    bin_counts = []
    
    # Calculate statistics for each bin
    for i in range(len(distance_bins)-1):
        mask = (df['Distance'] >= distance_bins[i]) & (df['Distance'] < distance_bins[i+1])
        bin_data = df[mask]['Bitrate']
        
        if len(bin_data) > 0:
            if remove_outliers:
                # Remove outliers using IQR method
                Q1 = bin_data.quantile(0.25)
                Q3 = bin_data.quantile(0.75)
                IQR = Q3 - Q1
                bin_data = bin_data[
                    (bin_data >= Q1 - 1.5 * IQR) & 
                    (bin_data <= Q3 + 1.5 * IQR)
                ]
            
            if len(bin_data) > 0:
                median_bitrates.append(bin_data.median())
                q1_bitrates.append(bin_data.quantile(0.25))
                q3_bitrates.append(bin_data.quantile(0.75))
                bin_counts.append(len(bin_data))
            else:
                median_bitrates.append(np.nan)
                q1_bitrates.append(np.nan)
                q3_bitrates.append(np.nan)
                bin_counts.append(0)
        else:
            median_bitrates.append(np.nan)
            q1_bitrates.append(np.nan)
            q3_bitrates.append(np.nan)
            bin_counts.append(0)
    
    median_bitrates = np.array(median_bitrates)
    q1_bitrates = np.array(q1_bitrates)
    q3_bitrates = np.array(q3_bitrates)
    
    # Remove NaN values for plotting
    valid_mask = ~np.isnan(median_bitrates)
    valid_centers = bin_centers[valid_mask]
    valid_medians = median_bitrates[valid_mask]
    valid_q1 = q1_bitrates[valid_mask]
    valid_q3 = q3_bitrates[valid_mask]
    valid_counts = np.array(bin_counts)[valid_mask]
    
    # Plot median line
    ax.plot(valid_centers, valid_medians, 
            color='blue',
            linewidth=2.5,
            label='Median achieved bitrate')
    
    # Plot IQR as shaded area
    ax.fill_between(valid_centers, 
                   valid_q1, 
                   valid_q3, 
                   alpha=0.2,
                   color='blue',
                   label='IQR (25th-75th percentile)')
    
    # Add theoretical maximum bitrate curve (speed of light upper bound)
    avg_message_size = np.mean([msg.size for msg in messages])
    theoretical_bitrates = [calculate_theoretical_bitrate(avg_message_size, d) for d in distance_range]
    
    ax.plot(distance_range, theoretical_bitrates,
            color='red',
            linewidth=2.0,
            linestyle='--',
            label='Theoretical maximum\n(speed of light limit)')
    
    for x, y, count in zip(valid_centers, valid_medians, valid_counts):
        ax.text(x, y * 1.1,  # Multiply by 1.1 for log scale positioning
                f'n={count:,}',
                ha='center', va='bottom',
                fontsize=8)
    
    ax.set_xlabel('Distance (m)')
    ax.set_ylabel('Bitrate (bytes/second)')
    ax.set_title('Bitrate vs Distance: Achieved vs Theoretical Maximum (Aggregated)')
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_yscale('log')
    
    plt.tight_layout()
    plt.savefig('figures/bitrate_vs_distance_aggregate.png', 
                bbox_inches='tight', dpi=300)
    plt.close()
    
    fig, ax = plt.subplots(figsize=(12, 8))
    colors = plt.cm.viridis(np.linspace(0, 1, len(comm_ranges)))
    markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h', 'H', '+', 'x']
    
    for i, comm_range in enumerate(comm_ranges):
        # Filter messages for this communication range
        range_messages = [msg for msg in messages 
                        if msg.communication_range == comm_range and msg.distance > 0 and msg.delivery_time > 0]
        
        if not range_messages:
            continue
            
        # Create DataFrame for this communication range
        range_data = []
        for msg in range_messages:
            bitrate = msg.size / msg.delivery_time
            range_data.append({
                'Distance': msg.distance,
                'Bitrate': bitrate,
            })
        
        df_range = pd.DataFrame(range_data)
        
        median_bitrates = []
        q1_bitrates = []
        q3_bitrates = []
        
        # Calculate statistics for each bin
        for j in range(len(distance_bins)-1):
            mask = (df_range['Distance'] >= distance_bins[j]) & (df_range['Distance'] < distance_bins[j+1])
            bin_data = df_range[mask]['Bitrate']
            
            if len(bin_data) > 0:
                if remove_outliers:
                    # Remove outliers using IQR method
                    Q1 = bin_data.quantile(0.25)
                    Q3 = bin_data.quantile(0.75)
                    IQR = Q3 - Q1
                    bin_data = bin_data[
                        (bin_data >= Q1 - 1.5 * IQR) & 
                        (bin_data <= Q3 + 1.5 * IQR)
                    ]
                
                if len(bin_data) > 0:
                    median_bitrates.append(bin_data.median())
                    q1_bitrates.append(bin_data.quantile(0.25))
                    q3_bitrates.append(bin_data.quantile(0.75))
                else:
                    median_bitrates.append(np.nan)
                    q1_bitrates.append(np.nan)
                    q3_bitrates.append(np.nan)
            else:
                median_bitrates.append(np.nan)
                q1_bitrates.append(np.nan)
                q3_bitrates.append(np.nan)
        
        median_bitrates = np.array(median_bitrates)
        q1_bitrates = np.array(q1_bitrates)
        q3_bitrates = np.array(q3_bitrates)
        
        valid_mask = ~np.isnan(median_bitrates)
        valid_centers = bin_centers[valid_mask]
        valid_medians = median_bitrates[valid_mask]
        valid_q1 = q1_bitrates[valid_mask]
        valid_q3 = q3_bitrates[valid_mask]
        
        if len(valid_centers) == 0:
            continue
            
        # Plot median line for this communication range
        ax.plot(valid_centers, valid_medians, 
                marker=markers[i % len(markers)],
                color=colors[i],
                linewidth=2.5,
                markersize=6,
                markevery=max(1, len(valid_centers)//10),  # Show markers periodically
                label=f'{int(comm_range)}m range (median)')
        
        # Plot IQR as shaded area
        ax.fill_between(valid_centers, 
                       valid_q1, 
                       valid_q3, 
                       alpha=0.15,
                       color=colors[i])
    
    # Add single theoretical maximum bitrate curve (speed of light upper bound)
    # Use average message size across all communication ranges for consistency
    avg_message_size = np.mean([msg.size for msg in messages])
    theoretical_bitrates = [calculate_theoretical_bitrate(avg_message_size, d) for d in distance_range]
    
    ax.plot(distance_range, theoretical_bitrates,
            color='red',
            linewidth=2.0,
            linestyle='--',
            label='Theoretical maximum\n(speed of light limit)')
    
    ax.set_xlabel('Distance (m)')
    ax.set_ylabel('Bitrate (bytes/second)')
    ax.set_title('Bitrate vs Distance by Communication Range: Achieved vs Theoretical')
    ax.grid(True, alpha=0.3)
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', 
              fontsize=9, framealpha=0.9)
    ax.set_yscale('log')
    
    plt.tight_layout()
    plt.savefig('figures/bitrate_vs_distance_by_range.png', 
                bbox_inches='tight', dpi=300)
    plt.close()

def plot_node_degree_vs_communication_radius(messages: list[Message]):
    """Plot relationship between communication range and node degree (aggregated)"""
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Extract data for all hops
    data = []
    for msg in messages:
        if msg.hops:
            for hop in msg.hops:
                if hop.hop_time > 0:
                    data.append({
                        'node_degree': hop.from_node_degree,
                        'communication_range': msg.communication_range
                    })
    
    df = pd.DataFrame(data)
    
    # Get unique communication ranges and calculate statistics
    comm_ranges = sorted(df['communication_range'].unique(), key=int)
    mean_degrees = []
    std_degrees = []
    median_degrees = []
    q1_degrees = []
    q3_degrees = []
    sample_counts = []
    
    for comm_range in comm_ranges:
        range_data = df[df['communication_range'] == comm_range]['node_degree']
        
        mean_degrees.append(range_data.mean())
        std_degrees.append(range_data.std())
        median_degrees.append(range_data.median())
        q1_degrees.append(range_data.quantile(0.25))
        q3_degrees.append(range_data.quantile(0.75))
        sample_counts.append(len(range_data))
    
    mean_degrees = np.array(mean_degrees)
    std_degrees = np.array(std_degrees)
    median_degrees = np.array(median_degrees)
    q1_degrees = np.array(q1_degrees)
    q3_degrees = np.array(q3_degrees)
    
    # Plot median line with IQR band
    ax.plot(comm_ranges, median_degrees, 
            color='red', 
            linewidth=2, 
            linestyle='--',
            marker='s', 
            markersize=6,
            label='Median node degree')
    
    ax.fill_between(comm_ranges, 
                   q1_degrees, 
                   q3_degrees, 
                   alpha=0.15, 
                   color='red',
                   label='IQR (25th-75th percentile)')
    
    # Add sample size annotations
    for x, y, count in zip(comm_ranges, mean_degrees, sample_counts):
        ax.text(x, y + 0.1, 
                f'n={count:,}',
                ha='center', va='bottom',
                fontsize=8,
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))
    
    ax.set_xlabel('Communication Range (m)', fontsize=12)
    ax.set_ylabel('Node Degree', fontsize=12)
    ax.set_title('Node Degree vs. Communication Range', fontsize=14)
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper left', fontsize=10, framealpha=0.9)
    
    plt.tight_layout()
    plt.savefig('figures/node_degree_vs_communication_radius.png', 
                bbox_inches='tight', dpi=300)
    plt.close()

def plot_node_degree_vs_hop_count(messages: list[Message]):
    """Plot relationship between node degree and hop count (aggregated)"""
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Extract data for each hop along message paths
    data = []
    for msg in messages:
        if msg.hops and len(msg.hops) > 0:
            total_hops = len(msg.hops)
            for hop in msg.hops:
                if hop.hop_time > 0:
                    data.append({
                        'node_degree': hop.from_node_degree,
                        'hop_count': total_hops
                    })
    
    df = pd.DataFrame(data)
    
    # Create node degree bins
    degree_bins = np.arange(0, 51, 5)  # 0-50 in steps of 5
    median_hops = []
    q1_hops = []
    q3_hops = []
    bin_centers = []
    sample_counts = []
    
    for i in range(len(degree_bins)-1):
        mask = (df['node_degree'] >= degree_bins[i]) & (df['node_degree'] < degree_bins[i+1])
        if mask.any():
            bin_data = df[mask]['hop_count']
            median_hops.append(bin_data.median())
            q1_hops.append(bin_data.quantile(0.25))
            q3_hops.append(bin_data.quantile(0.75))
            bin_centers.append((degree_bins[i] + degree_bins[i+1]) / 2)
            sample_counts.append(len(bin_data))
    
    median_hops = np.array(median_hops)
    q1_hops = np.array(q1_hops)
    q3_hops = np.array(q3_hops)
    bin_centers = np.array(bin_centers)
    
    # Plot median line with IQR band
    ax.plot(bin_centers, median_hops, 
            color='blue', 
            linewidth=3, 
            marker='o', 
            markersize=8,
            label='Median hop count')
    
    ax.fill_between(bin_centers, 
                   q1_hops, 
                   q3_hops, 
                   alpha=0.2, 
                   color='blue',
                   label='IQR (25th-75th percentile)')
    
    # Add sample size annotations
    for x, y, count in zip(bin_centers, median_hops, sample_counts):
        ax.text(x, y + 0.1, 
                f'n={count:,}',
                ha='center', va='bottom',
                fontsize=8,
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))
    
    ax.set_xlabel('Node Degree', fontsize=12)
    ax.set_ylabel('Hop Count', fontsize=12)
    ax.set_title('Node Degree vs Hop Count (Aggregated)', fontsize=14)
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper right', fontsize=10, framealpha=0.9)
    
    plt.tight_layout()
    plt.savefig('figures/node_degree_vs_hop_count.png',
                bbox_inches='tight', dpi=300)
    plt.close()

def plot_hop_latency_vs_communication_radius(messages: list[Message]):
    """Plot relationship between hop latency and communication radius as smooth aggregated line"""
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Extract data for all hops
    data = []
    for msg in messages:
        if msg.hops:
            for hop in msg.hops:
                if hop.hop_time > 0:
                    data.append({
                        'hop_latency': hop.hop_time,
                        'communication_range': msg.communication_range
                    })
    
    df = pd.DataFrame(data)
    
    # Get unique communication ranges and calculate statistics
    comm_ranges = sorted(df['communication_range'].unique(), key=int)
    mean_latencies = []
    std_latencies = []
    median_latencies = []
    q1_latencies = []
    q3_latencies = []
    sample_counts = []
    
    for comm_range in comm_ranges:
        range_data = df[df['communication_range'] == comm_range]['hop_latency']
        
        mean_latencies.append(range_data.mean())
        std_latencies.append(range_data.std())
        median_latencies.append(range_data.median())
        q1_latencies.append(range_data.quantile(0.25))
        q3_latencies.append(range_data.quantile(0.75))
        sample_counts.append(len(range_data))
    
    mean_latencies = np.array(mean_latencies)
    std_latencies = np.array(std_latencies)
    median_latencies = np.array(median_latencies)
    q1_latencies = np.array(q1_latencies)
    q3_latencies = np.array(q3_latencies)
    
    # Plot median line with IQR band
    ax.plot(comm_ranges, median_latencies, 
            color='red', 
            linewidth=2, 
            linestyle='--',
            marker='s', 
            markersize=6,
            label='Median hop latency')
    
    ax.fill_between(comm_ranges, 
                   q1_latencies, 
                   q3_latencies, 
                   alpha=0.15, 
                   color='red',
                   label='IQR (25th-75th percentile)')
    
    ax.set_xlabel('Communication Range (m)', fontsize=12)
    ax.set_ylabel('Hop Latency (s)', fontsize=12)
    ax.set_title('Median Hop Latency vs. Communication Range', fontsize=14)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('figures/hop_latency_vs_communication_radius.png',
                bbox_inches='tight', dpi=300)
    plt.close()

def plot_hop_latency_vs_node_degree(messages: list[Message]):
    """Plot relationship between hop latency and node degree"""
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Extract data for all hops
    data = []
    for msg in messages:
        if msg.hops:
            for hop in msg.hops:
                if hop.hop_time > 0:
                    data.append({
                        'hop_latency': hop.hop_time,
                        'node_degree': hop.from_node_degree
                    })
    
    df = pd.DataFrame(data)
    
    degree_bins = np.arange(0, 51, 5)
    median_latencies = []
    q1_latencies = []
    q3_latencies = []
    bin_centers = []
    sample_counts = []
    
    for i in range(len(degree_bins)-1):
        mask = (df['node_degree'] >= degree_bins[i]) & (df['node_degree'] < degree_bins[i+1])
        if mask.any():
            bin_data = df[mask]['hop_latency']
            median_latencies.append(bin_data.median())
            q1_latencies.append(bin_data.quantile(0.25))
            q3_latencies.append(bin_data.quantile(0.75))
            bin_centers.append((degree_bins[i] + degree_bins[i+1]) / 2)
            sample_counts.append(len(bin_data))
    
    median_latencies = np.array(median_latencies)
    q1_latencies = np.array(q1_latencies)
    q3_latencies = np.array(q3_latencies)
    bin_centers = np.array(bin_centers)
    
    # Plot median line with IQR band
    ax.plot(bin_centers, median_latencies,
            color='blue',
            linewidth=3,
            marker='o',
            markersize=8,
            label='Median hop latency')
    
    ax.fill_between(bin_centers, 
                   q1_latencies, 
                   q3_latencies, 
                   alpha=0.2, 
                   color='blue',
                   label='IQR (25th-75th percentile)')
    
    # Add sample size annotations
    for x, y, count in zip(bin_centers, median_latencies, sample_counts):
        ax.text(x, y + 1, 
                f'n={count:,}',
                ha='center', va='bottom',
                fontsize=8,
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))
    
    ax.set_xlabel('Node Degree', fontsize=12)
    ax.set_ylabel('Hop Latency (s)', fontsize=12)
    ax.set_title('Hop Latency vs. Node Degree', fontsize=14)
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper right', fontsize=10, framealpha=0.9)
    
    plt.tight_layout()
    plt.savefig('figures/hop_latency_vs_node_degree.png',
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
        num_edges: Number of edges
        
    Returns:
        Centralization score (higher means more centralized)
    """
    if not node_degrees or len(node_degrees) == 0:
        return 0.0
    
    # Remove any NaN or infinite values
    degrees = [d for d in node_degrees if np.isfinite(d)]
    
    if len(degrees) == 0:
        return 0.0

    C = num_edges if num_edges > 0 else 1  # Avoid division by zero

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

def plot_metrics_vs_max_degree(delivered_messages: list[Message], topologies: dict[Configuration, Topology]):
    """
    Plot Gini coefficient, centralization score, and L0 norm vs max node degree,
    split by mode (intra/inter-cluster), with one curve for each communication range.
    
    Creates 6 subplots (3x2 grid):
    - Top row: Gini coefficient (intra, inter)
    - Middle row: Centralization score S (intra, inter)
    - Bottom row: L0 norm / sparsity (intra, inter)
    """
    # Group node degrees by mode, communication_range, and max_degree
    # Use dict of dicts to track unique node degrees per node
    degree_data = {}
    
    # Total number of nodes in the network
    TOTAL_NODES = 72
    
    for msg in delivered_messages:
        if not msg.hops:
            continue
            
        key = (msg.mode, msg.communication_range, msg.max_degree)
        if key not in degree_data:
            # Store node_id -> degree mapping to avoid counting same node multiple times
            degree_data[key] = {}
        
        # Collect node degrees from all hops in this message
        for hop in msg.hops:
            node_id = hop.from_node
            # Update with the degree (may overwrite, but should be consistent)
            degree_data[key][node_id] = hop.from_node_degree
    
    # Get unique values
    modes = sorted(set(k[0] for k in degree_data.keys()))
    ranges = sorted(set(k[1] for k in degree_data.keys()))
    max_degrees = sorted(set(k[2] for k in degree_data.keys()))
    
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
                key = (mode, comm_range, max_deg)
                if key in degree_data and len(degree_data[key]) > 1:
                    degrees_list = list(degree_data[key].values())
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
                key = (mode, comm_range, max_deg)
                if key in degree_data and len(degree_data[key]) > 1:
                    # Convert dict to list of degrees for calculation
                    degrees_list = list(degree_data[key].values())
                    # all runs have the same topology 
                    num_run=0
                    # both modes have the same topology
                    mode=0
                    config = Configuration(run_number=num_run, range=comm_range, max_degree=max_deg, mode=mode)
                    topology = topologies[config]
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
                key = (mode, comm_range, max_deg)
                if key in degree_data and len(degree_data[key]) > 0:
                    # Create full degree list: observed nodes + zeros for unobserved nodes
                    observed_degrees = list(degree_data[key].values())
                    num_observed = len(degree_data[key])
                    num_unobserved = TOTAL_NODES - num_observed
                    
                    # Unobserved nodes have degree 0 (not connected or didn't forward messages)
                    full_degrees = observed_degrees + [0] * num_unobserved
                    
                    l0_norm = calculate_l0_norm(full_degrees)
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

def plot_throughput_vs_gini_tradeoff(delivered_messages: list[Message]):
    """
    Plot the trade-off between throughput and fairness (Gini coefficient).
    Shows which max_degree settings achieve target throughput with best fairness.

    Arguments:
        delivered_messages: List of delivered messages.
    
    Creates separate plots for intra and inter-cluster modes.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
    
    # Group by mode, communication_range, and max_degree
    configs = {}
    
    for msg in delivered_messages:
        if not msg.hops or msg.delivery_time <= 0:
            continue
            
        key = (msg.mode, msg.communication_range, msg.max_degree)
        if key not in configs:
            configs[key] = {
                'throughputs': [],
                'node_degrees': []
            }
        
        throughput = msg.size / msg.delivery_time
        configs[key]['throughputs'].append(throughput)
        
        # Collect node degrees from all hops
        for hop in msg.hops:
            if hop.from_node_degree > 0:
                configs[key]['node_degrees'].append(hop.from_node_degree)
    
    # Calculate metrics per configuration
    results = []
    for key, data in configs.items():
        mode, comm_range, max_degree = key
        
        avg_throughput = np.mean(data['throughputs'])
        gini = calculate_gini_coefficient(data['node_degrees'])
        
        results.append({
            'mode': mode,
            'comm_range': comm_range,
            'max_degree': max_degree,
            'avg_throughput': avg_throughput,
            'gini': gini
        })
    
    df = pd.DataFrame(results)
    
    modes = [0, 1]
    mode_names = {0: 'Intra-cluster', 1: 'Inter-cluster'}
    axes = [ax1, ax2]
    
    for mode_idx, mode in enumerate(modes):
        ax = axes[mode_idx]
        df_mode = df[df['mode'] == mode]
        
        if df_mode.empty:
            continue
        
        # Get unique values - swap color/shape mapping
        # Colors now represent max_degree
        # Shapes now represent comm_range
        max_degrees = sorted(df_mode['max_degree'].unique())
        ranges = sorted(df_mode['comm_range'].unique())
        
        colors = plt.cm.viridis(np.linspace(0, 1, len(max_degrees)))
        markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h', 'H', '+']
        
        # Plot each max_degree with its own color
        for deg_idx, max_deg in enumerate(max_degrees):
            df_degree = df_mode[df_mode['max_degree'] == max_deg]
            
            # Plot each communication range with different marker
            for range_idx, comm_range in enumerate(ranges):
                df_point = df_degree[df_degree['comm_range'] == comm_range]
                
                if df_point.empty:
                    continue
                
                # Scatter plot - one point per (max_degree, comm_range) combination
                scatter = ax.scatter(
                    df_point['avg_throughput'], 
                    df_point['gini'],
                    s=120,  # Fixed size for clarity
                    marker=markers[range_idx % len(markers)],
                    color=colors[deg_idx],
                    alpha=0.7,
                    edgecolors='black',
                    linewidths=1.5,
                    label=f'd={int(max_deg)}, r={int(comm_range)}m' if range_idx == 0 else None
                )
            
            # Connect points of same max_degree to show how range affects the tradeoff
            df_degree_sorted = df_degree.sort_values('comm_range')
            if len(df_degree_sorted) > 1:
                ax.plot(
                    df_degree_sorted['avg_throughput'], 
                    df_degree_sorted['gini'],
                    color=colors[deg_idx],
                    alpha=0.3,
                    linewidth=1.5,
                    linestyle='-'
                )
        
        # Add example target throughput lines
        if not df_mode.empty:
            throughput_targets = [
                np.percentile(df_mode['avg_throughput'], 25),
                np.percentile(df_mode['avg_throughput'], 50),
                np.percentile(df_mode['avg_throughput'], 75)
            ]
            
            # for target in throughput_targets:
            #     ax.axvline(x=target, color='red', linestyle=':', 
            #               alpha=0.5, linewidth=1)
            #     ax.text(target, ax.get_ylim()[1] * 0.95, 
            #            f'{target:.1f}\nbytes/s',
            #            ha='center', fontsize=8,
            #            bbox=dict(boxstyle='round,pad=0.3', 
            #                    facecolor='white', alpha=0.7))
        
        ax.set_xlabel('Average Throughput (bytes/second)', fontsize=12)
        ax.set_ylabel('Gini Coefficient (lower = more fair)', fontsize=12)
        ax.set_title(f'{mode_names[mode]} - Throughput vs Gini Trade-off', 
                    fontsize=13, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best', fontsize=9)
        
        # Add arrow pointing toward ideal region (high throughput, low Gini)
        ax.annotate('', xy=(ax.get_xlim()[1], ax.get_ylim()[0]),
                   xytext=(ax.get_xlim()[0], ax.get_ylim()[1]),
                   arrowprops=dict(arrowstyle='->', lw=2, color='green', alpha=0.3))
    
    plt.suptitle('Throughput vs. Centralization\n' +
                'Point size indicates max_degree constraint', 
                fontsize=14)
    plt.tight_layout()
    plt.savefig('figures/throughput_vs_gini_tradeoff.png', 
                dpi=300, bbox_inches='tight')
    plt.close()
    
    # Print recommendation table
    print("\n" + "="*80)
    print("THROUGHPUT vs GINI RECOMMENDATIONS")
    print("="*80)
    
    for mode in modes:
        print(f"\n{mode_names[mode]} Mode:")
        print("-" * 80)
        df_mode = df[df['mode'] == mode]
        
        # Find Pareto-optimal configurations
        # (configurations where you can't improve one metric without worsening the other)
        pareto_optimal = []
        for _, row1 in df_mode.iterrows():
            is_dominated = False
            for _, row2 in df_mode.iterrows():
                # row2 dominates row1 if it has both better throughput AND better (lower) Gini
                if (row2['avg_throughput'] >= row1['avg_throughput'] and 
                    row2['gini'] <= row1['gini'] and
                    (row2['avg_throughput'] > row1['avg_throughput'] or row2['gini'] < row1['gini'])):
                    is_dominated = True
                    break
            if not is_dominated:
                pareto_optimal.append(row1)
        
        pareto_df = pd.DataFrame(pareto_optimal).sort_values('avg_throughput')
        
        print(f"\n{'Range':<8} {'MaxDeg':<8} {'Throughput':<15} {'Gini':<10} {'Status':<15}")
        print("-" * 80)
        
        for _, row in pareto_df.iterrows():
            print(f"{int(row['comm_range']):<8} {int(row['max_degree']):<8} "
                  f"{row['avg_throughput']:<15.2f} {row['gini']:<10.4f} {'Pareto-optimal':<15}")
    
    print("\n" + "="*80)


def plot_max_degree_vs_throughput_run_comparison(delivered_messages: list[Message]):
    """
    Plot node degree vs throughput for mode 0 (intra-cluster), comparing:
    - Single run (run 1) data
    - Aggregated normalized data from 10 runs
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
        
        # Extract first 10 runs (or however many are available)
        runs_to_aggregate = sorted([r for r in available_runs if r <= 10])
        
        # Group by max_degree
        run1_by_degree = {}
        for msg in run1_data:
            degree = msg['max_degree']
            if degree not in run1_by_degree:
                run1_by_degree[degree] = []
            run1_by_degree[degree].append(msg['throughput'])
        
        # Aggregate across runs 1-10
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

def plot_correlation_heatmap(messages: list[Message]):
    data = []
    for msg in messages:
        if msg.hops:
            for hop in msg.hops:
                data.append({
                    'Communication_Range': msg.communication_range,
                    'Total_Distance': msg.distance,
                    'Total_Hops': len(msg.hops),
                    'Total_Latency': msg.delivery_time,
                    'Hop_Latency': hop.hop_time,
                    'Node_Degree': hop.from_node_degree,
                })
    
    df = pd.DataFrame(data)
    
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna()
    
    correlation_matrix = df.corr()
    
    fig, ax = plt.subplots(figsize=(12, 10))
    im = ax.imshow(correlation_matrix.values, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
    cbar = plt.colorbar(im)
    cbar.set_label('Correlation Coefficient', rotation=270, labelpad=20)
    
    # Set ticks and labels
    ax.set_xticks(range(len(correlation_matrix.columns)))
    ax.set_yticks(range(len(correlation_matrix.columns)))
    ax.set_xticklabels(correlation_matrix.columns, rotation=45, ha='right')
    ax.set_yticklabels(correlation_matrix.columns)
    
    # Add correlation values as text annotations
    for i in range(len(correlation_matrix.columns)):
        for j in range(len(correlation_matrix.columns)):
            value = correlation_matrix.iloc[i, j]
            color = 'black'
            ax.text(j, i, f'{value:.3f}', 
                   ha='center', va='center',
                   color=color, fontweight='bold', 
                   fontsize=10)
    
    plt.title('Correlation Matrix: Network Factors vs Latency', pad=20, fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(f'figures/correlation_heatmap.png', bbox_inches='tight', dpi=300)
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

def plot_delivery_probability_vs_distance_by_range(all_messages: list[Message], delivered_messages: list[Message], 
                                                  time_threshold: float = 60.0, num_bins: int = 20):
    """
    Plot delivery probability within time_threshold vs distance for each communication range.
    
    Creates a separate plot for each communication range showing:
    - X-axis: Distance the message has to travel
    - Y-axis: Percentage of messages delivered within time_threshold seconds
    - Vertical asymptote at the communication range limit
    
    Args:
        all_messages: All created messages (including undelivered)
        delivered_messages: Only successfully delivered messages
        time_threshold: Time threshold in seconds for delivery probability calculation
        num_bins: Number of distance bins to use for analysis
    """
    # Get all unique communication ranges
    comm_ranges = sorted(set(msg.communication_range for msg in all_messages), key=int)
    
    # Create a subplot for each communication range
    n_ranges = len(comm_ranges)
    cols = min(3, n_ranges)  # Max 3 columns
    rows = (n_ranges + cols - 1) // cols  # Calculate needed rows
    
    fig, axes = plt.subplots(rows, cols, figsize=(6*cols, 5*rows))
    if n_ranges == 1:
        axes = [axes]
    elif rows == 1:
        axes = [axes] if n_ranges == 1 else axes
    else:
        axes = axes.flatten()
    
    # Hide extra subplots if we have more subplots than ranges
    for i in range(n_ranges, len(axes)):
        axes[i].set_visible(False)
    
    for idx, comm_range in enumerate(comm_ranges):
        ax = axes[idx]
        
        # Filter messages for this communication range
        all_msgs_range = [msg for msg in all_messages if msg.communication_range == comm_range and msg.distance > 0]
        # Filter all messages that were delivered within the time threshold (not just from delivered_messages)
        delivered_msgs_range = [msg for msg in all_msgs_range 
                               if msg.is_delivered and msg.delivery_time <= time_threshold and msg.delivery_time > 0]
        
        if not all_msgs_range:
            ax.text(0.5, 0.5, f'No data for {int(comm_range)}m range', 
                   ha='center', va='center', transform=ax.transAxes)
            ax.set_title(f'Communication Range: {int(comm_range)}m')
            continue
        
        # Get distance range and create bins
        distances = [msg.distance for msg in all_msgs_range]
        min_dist = min(distances)
        # max_dist = min(max(distances), comm_range * 1.2)  # Limit to slightly beyond comm range
        max_dist = max(distances) * 1.2
        
        distance_bins = np.linspace(min_dist, max_dist, num_bins + 1)
        bin_centers = (distance_bins[:-1] + distance_bins[1:]) / 2
        
        delivery_percentages = []
        sample_counts = []
        
        # Calculate delivery percentage for each distance bin
        for i in range(len(distance_bins)-1):
            # Count all messages in this distance bin
            all_in_bin = [msg for msg in all_msgs_range 
                         if distance_bins[i] <= msg.distance < distance_bins[i+1]]
            
            # Count delivered messages in this distance bin (within time threshold)
            delivered_in_bin = [msg for msg in delivered_msgs_range 
                               if distance_bins[i] <= msg.distance < distance_bins[i+1]]
            
            if len(all_in_bin) > 0:
                percentage = (len(delivered_in_bin) / len(all_in_bin)) * 100
                delivery_percentages.append(percentage)
                sample_counts.append(len(all_in_bin))
            else:
                delivery_percentages.append(0)
                sample_counts.append(0)
        
        # Plot delivery percentage vs distance
        valid_indices = [i for i, count in enumerate(sample_counts) if count > 0]
        if valid_indices:
            valid_centers = [bin_centers[i] for i in valid_indices]
            valid_percentages = [delivery_percentages[i] for i in valid_indices]
            valid_counts = [sample_counts[i] for i in valid_indices]
            
            # Plot line with markers
            ax.plot(valid_centers, valid_percentages, 'bo-', linewidth=2, markersize=6, 
                   label=f'Delivery within {time_threshold}s')
            
            # Add sample size annotations
            for x, y, count in zip(valid_centers, valid_percentages, valid_counts):
                ax.annotate(f'n={count}', (x, y), xytext=(0, 10), 
                           textcoords='offset points', ha='center', fontsize=8,
                           bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
        
        # Add vertical line at communication range (asymptote)
        ax.axvline(x=comm_range, color='red', linestyle='--', linewidth=2, alpha=0.8,
                  label=f'Comm range ({int(comm_range)}m)')
        
        # Formatting
        ax.set_xlabel('Distance (m)')
        ax.set_ylabel('Delivery Probability (%)')
        ax.set_title(f'Communication Range: {int(comm_range)}m')
        ax.set_ylim(0, 105)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
        
        # Set x-axis limit to show communication range
        ax.set_xlim(min_dist * 0.9, min(max_dist * 1.1, comm_range * 1.3))
    
    # Overall title
    fig.suptitle(f'Delivery Probability vs Distance by Communication Range\n'
                f'(Messages delivered within {time_threshold} seconds)', fontsize=16)
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(f'figures/delivery_probability_vs_distance_by_range_{int(time_threshold)}s.png',
                bbox_inches='tight', dpi=300)
    plt.close()

def plot_delivery_probability_vs_distance_aggregated(all_messages: list[Message], delivered_messages: list[Message], 
                                                   time_threshold: float = 60.0, num_bins: int = 20):
    """
    Plot delivery probability within time_threshold vs distance for all communication ranges on one plot.
    
    Creates a single plot showing all communication ranges overlaid:
    - X-axis: Distance the message has to travel
    - Y-axis: Percentage of messages delivered within time_threshold seconds
    - Different colored lines for each communication range
    - Vertical lines showing each communication range limit
    
    Args:
        all_messages: All created messages (including undelivered)
        delivered_messages: Only successfully delivered messages
        time_threshold: Time threshold in seconds for delivery probability calculation
        num_bins: Number of distance bins to use for analysis
    """
    fig, ax = plt.subplots(figsize=(14, 10))
    
    # Get all unique communication ranges
    comm_ranges = sorted(set(msg.communication_range for msg in all_messages), key=int)
    colors = plt.cm.viridis(np.linspace(0, 1, len(comm_ranges)))
    
    # Find global distance range
    all_distances = [msg.distance for msg in all_messages if msg.distance > 0]
    global_min_dist = min(all_distances)
    global_max_dist = max(all_distances)
    
    for idx, comm_range in enumerate(comm_ranges):
        # Filter messages for this communication range
        all_msgs_range = [msg for msg in all_messages if msg.communication_range == comm_range and msg.distance > 0]
        # Filter all messages that were delivered within the time threshold (not just from delivered_messages)
        delivered_msgs_range = [msg for msg in all_msgs_range 
                               if msg.is_delivered and msg.delivery_time <= time_threshold and msg.delivery_time > 0]
        
        if not all_msgs_range:
            continue
        
        # Get distance range for this communication range
        distances = [msg.distance for msg in all_msgs_range]
        min_dist = min(distances)
        max_dist = max(distances)
        
        # Create bins for this range (use range-specific binning for better resolution)
        distance_bins = np.linspace(min_dist, max_dist, num_bins + 1)
        bin_centers = (distance_bins[:-1] + distance_bins[1:]) / 2
        
        delivery_percentages = []
        sample_counts = []
        
        # Calculate delivery percentage for each distance bin
        for i in range(len(distance_bins)-1):
            # Count all messages in this distance bin
            all_in_bin = [msg for msg in all_msgs_range 
                         if distance_bins[i] <= msg.distance < distance_bins[i+1]]
            
            # Count delivered messages in this distance bin (within time threshold)
            delivered_in_bin = [msg for msg in delivered_msgs_range 
                               if distance_bins[i] <= msg.distance < distance_bins[i+1]]
            
            if len(all_in_bin) > 0:
                percentage = (len(delivered_in_bin) / len(all_in_bin)) * 100
                delivery_percentages.append(percentage)
                sample_counts.append(len(all_in_bin))
            else:
                delivery_percentages.append(0)
                sample_counts.append(0)
        
        # Plot delivery percentage vs distance for this communication range
        valid_indices = [i for i, count in enumerate(sample_counts) if count > 0]
        if valid_indices:
            valid_centers = [bin_centers[i] for i in valid_indices]
            valid_percentages = [delivery_percentages[i] for i in valid_indices]
            
            # Plot line with markers
            ax.plot(valid_centers, valid_percentages, 'o-', 
                   color=colors[idx], linewidth=2.5, markersize=5,
                   label=f'{int(comm_range)}m range')
        
        # Add vertical line at communication range (asymptote)
        ax.axvline(x=comm_range, color=colors[idx], linestyle='--', 
                  linewidth=1.5, alpha=0.7)
    
    # Formatting
    ax.set_xlabel('Distance (m)', fontsize=12)
    ax.set_ylabel('Delivery Probability (%)', fontsize=12)
    ax.set_title(f'Delivery Probability vs Distance by Communication Range\n'
                f'(Messages delivered within {time_threshold} seconds)', fontsize=14)
    ax.set_ylim(0, 105)
    ax.grid(True, alpha=0.3)
    
    # Legend with communication range indicators
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc='upper right', fontsize=10, 
             title='Communication Ranges\n(dashed lines show limits)')
    
    # Set reasonable x-axis limits
    ax.set_xlim(global_min_dist * 0.95, min(global_max_dist * 1.05, max(comm_ranges) * 1.2))
    
    plt.tight_layout()
    plt.savefig(f'figures/delivery_probability_vs_distance_aggregated_{int(time_threshold)}s.png',
                bbox_inches='tight', dpi=300)
    plt.close()

def plot_deliverability_vs_communication_range(all_messages: list[Message], delivered_messages: list[Message]):
    """Plot deliverability percentage vs communication range"""
    fig, ax = plt.subplots(figsize=(12, 8))
    
    all_ranges = sorted(set(msg.communication_range for msg in all_messages), key=int)
    delivered_ranges = sorted(set(msg.communication_range for msg in delivered_messages), key=int)
    
    total_counts = {}
    delivered_counts = {}
    
    for comm_range in all_ranges:
        total_counts[comm_range] = len([msg for msg in all_messages if msg.communication_range == comm_range])
        delivered_counts[comm_range] = len([msg for msg in delivered_messages if msg.communication_range == comm_range])
    
    ranges = []
    percentages = []
    raw_counts = []
    
    for comm_range in all_ranges:
        total = total_counts.get(comm_range, 0)
        delivered = delivered_counts.get(comm_range, 0)
        
        if total > 0:
            percentage = (delivered / total) * 100
            ranges.append(comm_range)
            percentages.append(percentage)
            raw_counts.append((delivered, total))
    
    colors = plt.cm.viridis(np.linspace(0, 1, len(ranges)))
    bars = ax.bar(range(len(ranges)), percentages, color=colors, alpha=0.7, edgecolor='black', linewidth=0.5)
    
    # Add percentage labels on top of bars
    for i, (bar, percentage, (delivered, total)) in enumerate(zip(bars, percentages, raw_counts)):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                f'{percentage:.1f}%',
                ha='center', va='bottom',
                fontsize=10)
        
        # Add count labels inside bars
        ax.text(bar.get_x() + bar.get_width()/2., height/2,
                f'{delivered:,}',
                ha='center', va='center',
                fontsize=8,
                color='black')
    
    ax.set_xlabel('Communication Range (m)', fontsize=12)
    ax.set_ylabel('Deliverability (%)', fontsize=12)
    ax.set_title('Message Deliverability vs Communication Range', fontsize=14)
    ax.set_xticks(range(len(ranges)))
    ax.set_xticklabels([f'{int(r)}m' for r in ranges])
    ax.set_ylim(0, 105)  # Set y-axis from 0 to 105%
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig('figures/deliverability_vs_communication_range.png',
                bbox_inches='tight', dpi=300)
    plt.close()

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

# def plot_host_distance_and_delivery_matrices(all_messages: list[Message], delivered_messages: list[Message], 
#                                             mode: int = 0, time_threshold: float = 10.0):
#     """
#     Plot distance and delivery success matrices for a specific communication mode.
    
#     Args:
#         all_messages: All created messages
#         delivered_messages: Successfully delivered messages
#         mode: 0 for intra-cluster, 1 for inter-cluster
#         time_threshold: Time threshold for successful delivery
#     """
#     mode_name = "Intra-cluster" if mode == 0 else "Inter-cluster"
    
#     fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8))
    
#     # Distance matrix (absolute values, no binning)
#     distance_matrix, hosts = get_host_distance_matrix(delivered_messages)
    
#     if len(hosts) > 0:
#         # Use absolute distance values without binning
#         im1 = ax1.imshow(distance_matrix, cmap='viridis', aspect='auto')
#         ax1.set_title(f'{mode_name} Host Distance Matrix\n(Absolute Distances)', fontsize=14)
#         ax1.set_xlabel('Destination Host Index')
#         ax1.set_ylabel('Source Host Index')
        
#         # Create colorbar for distance
#         cbar1 = plt.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)
#         cbar1.set_label('Distance (meters)')
        
#         # Add text annotations for small matrices (if not too many hosts)
#         if len(hosts) <= 20:
#             for i in range(len(hosts)):
#                 for j in range(len(hosts)):
#                     if not np.isnan(distance_matrix[i, j]):
#                         text = ax1.text(j, i, f'{distance_matrix[i, j]:.0f}',
#                                        ha='center', va='center', color='white', fontsize=8)
        
#         # Add host labels on axes for small matrices
#         if len(hosts) <= 20:
#             ax1.set_xticks(range(len(hosts)))
#             ax1.set_yticks(range(len(hosts)))
#             ax1.set_xticklabels([f'H{h}' for h in hosts], rotation=45, ha='right')
#             ax1.set_yticklabels([f'H{h}' for h in hosts])
#     else:
#         ax1.text(0.5, 0.5, f'No {mode_name.lower()} distance data available', 
#                 ha='center', va='center', transform=ax1.transAxes, fontsize=14)
#         ax1.set_title(f'{mode_name} Host Distance Matrix')
    
#     # Delivery success matrix
#     success_matrix, success_hosts, success_host_to_index = get_delivery_success_matrix(
#         all_messages, delivered_messages, mode=mode, time_threshold=time_threshold)
    
#     if not len(success_hosts):
#         raise ValueError("No successful deliveries data found")

#     im2 = ax2.imshow(success_matrix, cmap='RdYlGn', vmin=0, vmax=1, aspect='auto')
#     ax2.set_title(f'{mode_name} Delivery Success Probability\n(within {time_threshold}s)', fontsize=14)
#     ax2.set_xlabel('Destination Host Index')
#     ax2.set_ylabel('Source Host Index')
    
#     # Create colorbar for success probability
#     cbar2 = plt.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)
#     cbar2.set_label('Success Probability')
    
#     # Add text annotations for small matrices
#     if len(success_hosts) <= 20:
#         for i in range(len(success_hosts)):
#             for j in range(len(success_hosts)):
#                 if not np.isnan(success_matrix[i, j]):
#                     text = ax2.text(j, i, f'{success_matrix[i, j]:.2f}',
#                                     ha='center', va='center', 
#                                     color='black' if success_matrix[i, j] > 0.5 else 'white', 
#                                     fontsize=8)
    
#     # Add host labels on axes for small matrices
#     if len(success_hosts) <= 20:
#         ax2.set_xticks(range(len(success_hosts)))
#         ax2.set_yticks(range(len(success_hosts)))
#         ax2.set_xticklabels([f'H{h}' for h in success_hosts], rotation=45, ha='right')
#         ax2.set_yticklabels([f'H{h}' for h in success_hosts])
    
#     plt.tight_layout()
#     mode_suffix = "intra" if mode == 0 else "inter"
#     plt.savefig(f'figures/host_distance_and_delivery_matrices_{mode_suffix}_{int(time_threshold)}s.png', 
#                 bbox_inches='tight', dpi=300)
#     plt.close()

# def plot_host_distance_matrices(messages: list[Message]):
#     """Plot distance matrices as heatmaps for both intra and inter-cluster modes"""
#     fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8))
    
#     # Intra-cluster distance matrix
#     intra_matrix, intra_hosts = get_host_distance_matrix(messages, mode=0)
    
#     if len(intra_hosts) > 0:
#         # Use smaller bins for intra-cluster (shorter distances)
#         intra_bins = np.arange(0, np.nanmax(intra_matrix) + 10, 5)  # 5m bins
#         intra_binned = np.digitize(intra_matrix, intra_bins)
#         intra_binned = np.where(np.isnan(intra_matrix), np.nan, intra_binned)
        
#         im1 = ax1.imshow(intra_binned, cmap='viridis', aspect='auto')
#         ax1.set_title('Intra-cluster Host Distance Matrix\n(5m bins)', fontsize=14)
#         ax1.set_xlabel('Destination Host Index')
#         ax1.set_ylabel('Source Host Index')
        
#         # Create custom colorbar for intra-cluster
#         cbar1 = plt.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)
#         cbar1.set_label('Distance Bin (5m increments)')
        
#         # Add text annotations for small matrices (if not too many hosts)
#         if len(intra_hosts) <= 20:
#             for i in range(len(intra_hosts)):
#                 for j in range(len(intra_hosts)):
#                     if not np.isnan(intra_matrix[i, j]):
#                         text = ax1.text(j, i, f'{intra_matrix[i, j]:.0f}',
#                                        ha='center', va='center', color='white', fontsize=8)
#     else:
#         ax1.text(0.5, 0.5, 'No intra-cluster data available', 
#                 ha='center', va='center', transform=ax1.transAxes, fontsize=14)
#         ax1.set_title('Intra-cluster Host Distance Matrix')
    
#     # Inter-cluster distance matrix
#     inter_matrix, inter_hosts, _ = get_host_distance_matrix(messages, mode=1)
    
#     if len(inter_hosts) > 0:
#         # Use larger bins for inter-cluster (longer distances)
#         inter_bins = np.arange(0, np.nanmax(inter_matrix) + 20, 20)  # 20m bins
#         inter_binned = np.digitize(inter_matrix, inter_bins)
#         inter_binned = np.where(np.isnan(inter_matrix), np.nan, inter_binned)
        
#         im2 = ax2.imshow(inter_binned, cmap='plasma', aspect='auto')
#         ax2.set_title('Inter-cluster Host Distance Matrix\n(20m bins)', fontsize=14)
#         ax2.set_xlabel('Destination Host Index')
#         ax2.set_ylabel('Source Host Index')
        
#         # Create custom colorbar for inter-cluster
#         cbar2 = plt.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)
#         cbar2.set_label('Distance Bin (20m increments)')
        
#         # Add text annotations for small matrices (if not too many hosts)
#         if len(inter_hosts) <= 20:
#             for i in range(len(inter_hosts)):
#                 for j in range(len(inter_hosts)):
#                     if not np.isnan(inter_matrix[i, j]):
#                         text = ax2.text(j, i, f'{inter_matrix[i, j]:.0f}',
#                                        ha='center', va='center', color='white', fontsize=8)
#     else:
#         ax2.text(0.5, 0.5, 'No inter-cluster data available', 
#                 ha='center', va='center', transform=ax2.transAxes, fontsize=14)
#         ax2.set_title('Inter-cluster Host Distance Matrix')
    
#     plt.tight_layout()
#     plt.savefig('figures/host_distance_matrices.png', bbox_inches='tight', dpi=300)
#     plt.close()

# def plot_delivery_success_matrices(all_messages: list[Message], delivered_messages: list[Message], 
#                                   time_threshold: float = 10.0):
#     """Plot delivery success probability matrices as heatmaps for both intra and inter-cluster modes"""
#     fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8))
    
#     # Intra-cluster delivery success matrix
#     intra_matrix, intra_hosts = get_delivery_success_matrix(all_messages, delivered_messages, time_threshold=time_threshold)
    
#     if len(intra_hosts) > 0:
#         im1 = ax1.imshow(intra_matrix, cmap='RdYlGn', vmin=0, vmax=1, aspect='auto')
#         ax1.set_title(f'Intra-cluster Delivery Success Probability\n(within {time_threshold}s)', fontsize=14)
#         ax1.set_xlabel('Destination Host Index')
#         ax1.set_ylabel('Source Host Index')
        
#         cbar1 = plt.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)
#         cbar1.set_label('Success Probability')
        
#         # Add text annotations for small matrices
#         if len(intra_hosts) <= 20:
#             for i in range(len(intra_hosts)):
#                 for j in range(len(intra_hosts)):
#                     if not np.isnan(intra_matrix[i, j]):
#                         text = ax1.text(j, i, f'{intra_matrix[i, j]:.2f}',
#                                        ha='center', va='center', 
#                                        color='black' if intra_matrix[i, j] > 0.5 else 'white', 
#                                        fontsize=8)
#     else:
#         ax1.text(0.5, 0.5, 'No intra-cluster data available', 
#                 ha='center', va='center', transform=ax1.transAxes, fontsize=14)
#         ax1.set_title(f'Intra-cluster Delivery Success Probability\n(within {time_threshold}s)')
    
#     # Inter-cluster delivery success matrix
#     inter_matrix, inter_hosts = get_delivery_success_matrix(all_messages, delivered_messages, 
#                                                               mode=1, time_threshold=time_threshold)
    
#     if len(inter_hosts) > 0:
#         im2 = ax2.imshow(inter_matrix, cmap='RdYlGn', vmin=0, vmax=1, aspect='auto')
#         ax2.set_title(f'Inter-cluster Delivery Success Probability\n(within {time_threshold}s)', fontsize=14)
#         ax2.set_xlabel('Destination Host Index')
#         ax2.set_ylabel('Source Host Index')
        
#         cbar2 = plt.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)
#         cbar2.set_label('Success Probability')
        
#         # Add text annotations for small matrices
#         if len(inter_hosts) <= 20:
#             for i in range(len(inter_hosts)):
#                 for j in range(len(inter_hosts)):
#                     if not np.isnan(inter_matrix[i, j]):
#                         text = ax2.text(j, i, f'{inter_matrix[i, j]:.2f}',
#                                        ha='center', va='center', 
#                                        color='black' if inter_matrix[i, j] > 0.5 else 'white', 
#                                        fontsize=8)
#     else:
#         ax2.text(0.5, 0.5, 'No inter-cluster data available', 
#                 ha='center', va='center', transform=ax2.transAxes, fontsize=14)
#         ax2.set_title(f'Inter-cluster Delivery Success Probability\n(within {time_threshold}s)')
    
#     plt.tight_layout()
#     plt.savefig(f'figures/delivery_success_matrices_{int(time_threshold)}s.png', 
#                 bbox_inches='tight', dpi=300)
#     plt.close()

def plot_deliverability_vs_communication_range(all_messages: list[Message], delivered_messages: list[Message]):
    """Plot deliverability percentage vs communication range"""
    fig, ax = plt.subplots(figsize=(12, 8))
    
    all_ranges = sorted(set(msg.communication_range for msg in all_messages), key=int)
    delivered_ranges = sorted(set(msg.communication_range for msg in delivered_messages), key=int)
    
    total_counts = {}
    delivered_counts = {}
    
    for comm_range in all_ranges:
        total_counts[comm_range] = len([msg for msg in all_messages if msg.communication_range == comm_range])
        delivered_counts[comm_range] = len([msg for msg in delivered_messages if msg.communication_range == comm_range])
    
    ranges = []
    percentages = []
    raw_counts = []
    
    for comm_range in all_ranges:
        total = total_counts.get(comm_range, 0)
        delivered = delivered_counts.get(comm_range, 0)
        
        if total > 0:
            percentage = (delivered / total) * 100
            ranges.append(comm_range)
            percentages.append(percentage)
            raw_counts.append((delivered, total))
    
    colors = plt.cm.viridis(np.linspace(0, 1, len(ranges)))
    bars = ax.bar(range(len(ranges)), percentages, color=colors, alpha=0.7, edgecolor='black', linewidth=0.5)
    
    # Add percentage labels on top of bars
    for i, (bar, percentage, (delivered, total)) in enumerate(zip(bars, percentages, raw_counts)):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                f'{percentage:.1f}%',
                ha='center', va='bottom',
                fontsize=10)
        
        # Add count labels inside bars
        ax.text(bar.get_x() + bar.get_width()/2., height/2,
                f'{delivered:,}',
                ha='center', va='center',
                fontsize=8,
                color='black')
    
    ax.set_xlabel('Communication Range (m)', fontsize=12)
    ax.set_ylabel('Deliverability (%)', fontsize=12)
    ax.set_title('Message Deliverability vs Communication Range', fontsize=14)
    ax.set_xticks(range(len(ranges)))
    ax.set_xticklabels([f'{int(r)}m' for r in ranges])
    ax.set_ylim(0, 105)  # Set y-axis from 0 to 105%
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig('figures/deliverability_vs_communication_range.png',
                bbox_inches='tight', dpi=300)
    plt.close()

def get_topology_matrix_from_connectivity(topology: dict[str, set[str]], n_hosts: int = 72):
    """
    Create a topology matrix from connectivity report data.
    
    Args:
        topology: Dictionary mapping node_id -> set of neighbor node_ids
        n_hosts: Number of hosts in the network (default 72)
        
    Returns:
        Binary topology matrix (1 if link exists, 0 otherwise)
    """
    topology_matrix = np.zeros((n_hosts, n_hosts))
    
    for node_id_str, neighbors in topology.items():
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

def generate_matrices_aggregated_by_range(all_messages: list[Message], delivered_messages: list[Message], topologies: dict, time_threshold: float = 10.0):
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
        topologies: Dictionary mapping (range, mode, max_degree, run) -> topology dict
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
        
    for comm_range in ranges:
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
                topology_key = (comm_range, mode, max_deg, runs[0])
                if topology_key in topologies:
                    topology = topologies[topology_key]
                    topology_matrix = get_topology_matrix_from_connectivity(topology)
                else:
                    print(f"    Warning: No topology found for range {comm_range}, mode {mode}, max_degree {max_deg}, run {runs[0]}")
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
                ax_topo.set_title(f'Topology - {mode_name.title()}-cluster)', 
                                fontsize=11, fontweight='bold')
                ax_topo.set_xlabel('Host Index', fontsize=10)
                ax_topo.set_ylabel('Host Index', fontsize=10)
                cbar3 = plt.colorbar(im3, ax=ax_topo, label='Link', ticks=[0, 1])
                
                print(f"    {mode_name.title()}-cluster: {n_messages:,} messages, {delivery_rate:.1f}% delivery rate")
            
            # Add overall title
            fig.suptitle(f'Communication Range: {int(comm_range)}m - Max Degree: {max_deg} - {len(runs)} runs', 
                        fontsize=14, fontweight='bold', y=0.995)
            
            plt.tight_layout(rect=[0, 0, 1, 0.99])  # Leave space for suptitle
            
            # Save figure
            plot_filename = f"{plots_dir}/range{int(comm_range)}_maxdeg{max_deg}_threshold{int(time_threshold)}s.png"
            plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"  Saved: {plot_filename}")

def main():
    # Load message data from pickle files
    print("Loading message data from pickle files...")
    
    try:
        with open("delivered_messages.pkl", 'rb') as f:
            messages: list[Message] = pickle.load(f)
        
        with open("all_messages.pkl", 'rb') as f:
            all_messages: list[Message] = pickle.load(f)
        
        with open("topologies.pkl", 'rb') as f:
            topologies: dict[Configuration, Topology] = pickle.load(f)
            
        print(f"Loaded {len(messages)} delivered messages, {len(all_messages)} total messages")
        print(f"Loaded {len(topologies)} topology snapshots")
    except FileNotFoundError as e:
        print(f"Error: Could not find pickle files. Please run load_data.py first to generate them.")
        print(f"Missing file: {e.filename}")
        return
    
    print("\nGenerating standard analysis plots...")
    
    # df = create_dataframe(messages)

    # plot_deliverability_vs_communication_range(all_messages, messages)
    # plot_delivery_probability_vs_distance_by_range(all_messages, messages, time_threshold=10.0)
    # plot_delivery_probability_vs_distance_aggregated(all_messages, messages, time_threshold=10.0)
    # plot_delivery_probability_vs_distance_by_range(all_messages, messages, time_threshold=60.0)
    # plot_delivery_probability_vs_distance_aggregated(all_messages, messages, time_threshold=60.0)
    # plot_delivery_probability_vs_distance_by_range(all_messages, messages, time_threshold=120.0)
    # plot_delivery_probability_vs_distance_aggregated(all_messages, messages, time_threshold=120.0)
    # plot_hop_counts(df)
    # plot_distance_vs_hopcount_by_range(df)
    # plot_latency_frequency_by_range(messages)
    # plot_bitrate_vs_distance(messages)
    # plot_correlation_heatmap(messages)
    plot_message_frequency_by_distance(messages)
    # plot_node_degree_vs_communication_radius(messages)
    # plot_node_degree_vs_hop_count(messages)
    # plot_hop_latency_vs_communication_radius(messages)
    # plot_hop_latency_vs_node_degree(messages)

    # print("\nGenerating aggregated matrices (distance, delivery probability, topology)...")
    # generate_matrices_aggregated_by_range(all_messages, messages, topologies, time_threshold=10.0)
    # generate_matrices_aggregated_by_range(all_messages, messages, topologies, time_threshold=60.0)
    # generate_matrices_aggregated_by_range(all_messages, messages, topologies, time_threshold=120.0)
    # generate_matrices_aggregated_by_range(all_messages, messages, topologies, time_threshold=240.0)

    plot_max_degree_vs_throughput(messages)
    plot_max_degree_vs_throughput_run_comparison(messages)
    plot_metrics_vs_max_degree(messages, topologies)
    # plot_throughput_vs_gini_tradeoff(messages)

    print("\nAll plots generated successfully!")

if __name__ == "__main__":
    main()
