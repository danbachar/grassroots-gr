import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pickle
from load_data import Message, Hop # Hop is needed, otherwise the pickle load won't work

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
                'Message_Size': msg.size
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
                color=colors[i],
                linewidth=2.5,
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
    """Plot frequency of created messages per distance"""
    fig, ax = plt.subplots(figsize=(12, 8))
    
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
    
    message_counts = []
    for i in range(len(distance_bins)-1):
        count = sum(1 for d in distances if distance_bins[i] <= d < distance_bins[i+1])
        message_counts.append(count)
    
    bars = ax.bar(bin_centers, message_counts, 
                  width=bin_width * 0.8, 
                  alpha=0.7, 
                  color='skyblue',
                  edgecolor='navy',
                  linewidth=0.5)
    
    for bar, count in zip(bars, message_counts):
        if count > 0:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
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
    
    ax.text(0.98, 0.98, stats_text,
            transform=ax.transAxes,
            verticalalignment='top',
            horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8),
            fontsize=10)
    
    ax.set_xlabel('Distance (m)', fontsize=12)
    ax.set_ylabel('Number of Messages', fontsize=12)
    ax.set_title('Message Creation Frequency by Distance', fontsize=14)
    ax.grid(True, alpha=0.3, axis='y')
    
    # Constrain x-axis to found bins
    ax.set_xlim(min_dist - bin_width/2, max_dist + bin_width/2)
    
    plt.tight_layout()
    plt.savefig('figures/message-distance-distribution.png', 
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

def main():
    with open("delivered_messages.pkl", 'rb') as f:
        messages: list[Message] = pickle.load(f)
    
    with open("all_messages.pkl", 'rb') as f:
        all_messages: list[Message] = pickle.load(f)

    unique_ranges = sorted(set(msg.communication_range for msg in messages))
    print(f"Unique ranges: {unique_ranges}")

    df = create_dataframe(messages)
    
    plot_deliverability_vs_communication_range(all_messages, messages)
    plot_hop_counts(df)
    plot_distance_vs_hopcount_by_range(df)
    plot_latency_frequency_by_range(messages)
    plot_bitrate_vs_distance(messages)
    plot_correlation_heatmap(messages)
    plot_message_frequency_by_distance(messages)
    plot_node_degree_vs_communication_radius(messages)
    plot_node_degree_vs_hop_count(messages)
    plot_hop_latency_vs_communication_radius(messages)
    plot_hop_latency_vs_node_degree(messages)
    
    print("All plots generated successfully!")

if __name__ == "__main__":
    main()