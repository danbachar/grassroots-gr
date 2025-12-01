#!/usr/bin/env python3
# python plot.py --input-dir ./ranges --output-dir ./plots
from pathlib import Path
from os import listdir, makedirs
from typing import Optional
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict
import re

def parse_summary_file(filepath: Path) -> dict[int, tuple[float, float]]:
    """
    Parse a summary file and extract start/end timestamps for each run.
    
    Returns:
        dict mapping run_number -> (start_timestamp, end_timestamp)
    """
    timestamps = {}
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    current_run = None
    start_ts = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check for start timestamp
        if 'Start Timestamp:' in line:
            match = re.search(r'Run (\d+) Start Timestamp:\s*([\d.]+)', line)
            if match:
                current_run = int(match.group(1))
                start_ts = float(match.group(2))
        
        # Check for end timestamp
        elif 'End Timestamp:' in line and current_run is not None:
            match = re.search(r'Run \d+ End Timestamp:\s*([\d.]+)', line)
            if match:
                end_ts = float(match.group(1))
                timestamps[current_run] = (start_ts, end_ts)
                current_run = None
                start_ts = None
    
    return timestamps

def plot_rssi_vs_distance(distance_rssi_data: dict[float, list[float]], output_dir: str):
    distances: list[float] = []
    mean_rssi: list[float] = []
    std_rssi: list[float] = []
    all_rssi_points: list[float] = []
    all_distance_points: list[float] = []
    
    print("\nRSSI Statistics by Distance:")
    print("Distance (m)\tMin RSSI\tMean RSSI\tMax RSSI")
    print("-" * 60)
    
    for distance in sorted(distance_rssi_data.keys()):
        rssi_values = distance_rssi_data[distance]
        if rssi_values:
            mean_value = float(np.mean(rssi_values))
            min_value = float(np.min(rssi_values))
            max_value = float(np.max(rssi_values))
            distances.append(distance)
            mean_rssi.append(mean_value)
            std_rssi.append(float(np.std(rssi_values)))
            
            print(f"{distance:8.1f}\t{min_value:8.2f}\t{mean_value:9.2f}\t{max_value:8.2f}")

            # For scatter plot of all points
            all_rssi_points.extend(rssi_values)
            all_distance_points.extend([distance] * len(rssi_values))
    
    plt.figure(figsize=(12, 8))
    plt.scatter(all_distance_points, all_rssi_points, alpha=0.3, s=10, color='lightblue', label='Individual measurements')
    
    # Plot mean RSSI with error bars
    plt.errorbar(distances, mean_rssi, yerr=std_rssi, fmt='o-', color='red', 
                capsize=5, capthick=2, linewidth=2, markersize=8, label='Mean RSSI ± Std Dev')
    
    plt.xlabel('Distance (meters)')
    plt.ylabel('RSSI (dBm)')
    plt.title('RSSI vs Distance')
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    plt.tight_layout()
    fpath=f'{output_dir}/rssi_vs_distance.png'
    plt.savefig(fpath, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"\nSaved RSSI vs distance plot to {fpath}")

def plot_density(distance_rssi_data: dict[float, list[float]], output_dir: str, bin_size: int = 30, ranges_to_plot: Optional[list[float]]=None):
    """Plot probability density of RSSI values for each distance in separate subplots
    
    Args:
        distance_rssi_data: Dictionary mapping distances to RSSI values
        output_dir: Directory to save the plot
        bin_size: Number of bins for the histogram (default: 30)
        ranges_to_plot: Optional list of distances to plot. If None, plots all distances.
    """
    # Filter distances if ranges_to_plot is provided
    if ranges_to_plot is not None:
        distances_to_plot = [d for d in sorted(distance_rssi_data.keys()) if d in ranges_to_plot]
    else:
        distances_to_plot = sorted(distance_rssi_data.keys())
    
    # Only include distances that have sufficient data
    distances_with_data: list[float] = []
    for distance in distances_to_plot:
        rssi_values = distance_rssi_data[distance]
        if len(rssi_values) > 1:
            distances_with_data.append(distance)
    
    n_plots = len(distances_with_data)
    
    if n_plots == 0:
        print("No distances to plot")
        return
    
    # Determine number of columns based on total number of plots
    if n_plots <= 12:
        n_cols = 3
    elif n_plots <= 15:
        n_cols = 4
    else:
        n_cols = 5
    
    n_rows = int(np.ceil(n_plots / n_cols))

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(4 * n_cols, 4 * n_rows), squeeze=False)
    axes = axes.flatten()  # Flatten the 2D array of axes to easily iterate
    
    for i, distance in enumerate(distances_with_data):
        ax = axes[i]
        rssi_values = distance_rssi_data[distance]
        
        # Create histogram
        counts, bin_edges = np.histogram(rssi_values, bins=bin_size, density=True)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        
        # Plot as line
        ax.plot(bin_centers, counts, color='steelblue')
        
        ax.set_xlabel('RSSI (dBm)', fontsize=10)
        ax.set_ylabel('Probability Density', fontsize=10)
        ax.set_title(f'{distance:.1f}m' if distance < 10 else f'{int(distance)}m', fontsize=11)
        ax.grid(True, alpha=0.3, linewidth=0.5)
        ax.tick_params(labelsize=9)

    # Hide unused subplots
    for i in range(n_plots, len(axes)):
        axes[i].set_visible(False)

    plt.tight_layout()
    plt.savefig(f'{output_dir}/rssi_density.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved density plot to {output_dir}/rssi_density.png")

def plot_cdf(distance_rssi_data: dict[float, list[float]], output_dir: str):
    """Plot CDF of RSSI values for each distance"""
    plt.figure(figsize=(12, 8))
    
    colors: list[str] = plt.cm.viridis(np.linspace(0, 1, len(distance_rssi_data)))
    markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h', 'H', '+', 'x']

    global_min_rssi = min([val for values in distance_rssi_data.values() for val in values])
    
    for i, distance in enumerate(sorted(distance_rssi_data.keys())):
        rssi_values = distance_rssi_data[distance]
        if rssi_values:
            # Sort RSSI values for CDF
            sorted_rssi = np.sort(rssi_values)
            # Calculate CDF
            y = np.arange(1, len(sorted_rssi) + 1) / len(sorted_rssi)

            plot_x = np.concatenate(([global_min_rssi], sorted_rssi))
            plot_y = np.concatenate(([0], y))

            plt.step(plot_x, plot_y, label=f'{distance}m', color=colors[i], 
                    marker=markers[i % len(markers)], markersize=4, markevery=max(1, len(sorted_rssi)//20), 
                    linewidth=2, where='post')
    
    plt.xlabel('RSSI (dBm)', fontsize=18)
    plt.ylabel('Cumulative Probability', fontsize=18)
    plt.grid(True, alpha=0.3)
    plt.legend(loc="lower right", fontsize=18)
    plt.tight_layout()
    fpath=f'{output_dir}/rssi_cdf.png'
    plt.savefig(fpath, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved CDF plot to {fpath}")

def plot_rssi_vs_time(distance_time_rssi_data: dict[float, dict[float, list[float]]], output_dir: str):
    """Plot RSSI vs time for each distance with one line per distance"""
    distances = sorted(distance_time_rssi_data.keys())
    
    if len(distances) == 0:
        print("No data to plot for RSSI vs time")
        return
    
    plt.figure(figsize=(12, 8))
    
    colors = plt.cm.viridis(np.linspace(0, 1, len(distances)))
    markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h', 'H', '+', 'x']
    
    for i, distance in enumerate(distances):
        time_rssi_data = distance_time_rssi_data[distance]
        
        timestamps = sorted(time_rssi_data.keys())
        if not timestamps:
            continue
            
        relative_times = np.array(timestamps)
        all_rssi_by_time = [time_rssi_data[t] for t in timestamps]
        
        # Bin the data to reduce noise - group by 1-second intervals
        bin_size = 1  # seconds
        max_time = max(relative_times)
        bins = np.arange(0, max_time + bin_size, bin_size)

        binned_times: list[float] = []
        binned_rssi_mean: list[float] = []
        binned_rssi_std: list[float] = []

        for j in range(len(bins) - 1):
            bin_start = bins[j]
            bin_end = bins[j + 1]
            
            # Use searchsorted for efficient range lookup (O(log n) instead of O(n))
            start_idx = np.searchsorted(relative_times, bin_start, side='left')
            end_idx = np.searchsorted(relative_times, bin_end, side='left')
            
            if start_idx < end_idx:
                # Collect all RSSI values in this bin
                bin_rssi_values: list[float] = []
                for k in range(start_idx, end_idx):
                    bin_rssi_values.extend(all_rssi_by_time[k])
                
                if bin_rssi_values:
                    binned_times.append((bin_start + bin_end) / 2)  # Use middle of bin
                    binned_rssi_mean.append(float(np.mean(bin_rssi_values)))
                    binned_rssi_std.append(float(np.std(bin_rssi_values)))
        
        if binned_times:
            # Convert to numpy arrays for easier manipulation
            binned_times = np.array(binned_times)
            binned_rssi_mean = np.array(binned_rssi_mean)
            binned_rssi_std = np.array(binned_rssi_std)
            
            # Plot the line
            plt.plot(binned_times, binned_rssi_mean, label=f'{distance}m', 
                    color=colors[i], marker=markers[i % len(markers)], markersize=6,
                    linewidth=2, alpha=0.9, markevery=max(1, len(binned_times)//15))
            
            # Add shaded error region (mean ± std)
            plt.fill_between(binned_times, 
                           binned_rssi_mean - binned_rssi_std,
                           binned_rssi_mean + binned_rssi_std,
                           color=colors[i], alpha=0.2)
    
    plt.xlabel('Time (seconds)')
    plt.ylabel('RSSI (dBm)')
    plt.title('RSSI vs Time by Distance (1-second bins with std deviation)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f'{output_dir}/rssi_vs_time.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved RSSI vs time plot to {output_dir}/rssi_vs_time.png")

def plot_timestamp_diff_vs_time(distance_time_rssi_data: dict[float, dict[float, list[float]]], output_dir: str, num_bins: int = 20):
    """Plot the mean difference in timestamp between consecutive advertisements against time."""
    distances = sorted(distance_time_rssi_data.keys())
    
    if len(distances) == 0:
        print("No data to plot for timestamp differences vs time")
        return
    
    plt.figure(figsize=(12, 8))
    
    colors = plt.cm.viridis(np.linspace(0, 1, len(distances)))
    markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h', 'H', '+', 'x']
    
    for i, distance in enumerate(distances):
        time_rssi_data = distance_time_rssi_data[distance]
        
        timestamps = sorted(time_rssi_data.keys())
        
        if len(timestamps) < 2:
            continue
            
        # Calculate differences between consecutive timestamps (in seconds)
        diffs = np.diff(timestamps) * 1000  # Convert to milliseconds
        # The time for each diff is the time of the second measurement
        diff_times = timestamps[1:]
        
        # Timestamps are in relative time (seconds)
        start_time = timestamps[0]
        relative_times = [t - start_time for t in diff_times]
        
        # Bin the data into a fixed number of bins
        max_time = max(relative_times) if relative_times else 0
        bins = np.linspace(0, max_time, num_bins + 1)

        binned_times: list[float] = []
        binned_diffs_mean: list[float] = []
        binned_diffs_std: list[float] = []

        for j in range(len(bins) - 1):
            bin_start = bins[j]
            bin_end = bins[j + 1]
            
            # Find all data points in this bin
            bin_indices = [k for k, t in enumerate(relative_times) if bin_start <= t < bin_end]
            
            if bin_indices:
                bin_diff_values = diffs[np.array(bin_indices)]
                
                if len(bin_diff_values) > 0:
                    binned_times.append((bin_start + bin_end) / 2)
                    binned_diffs_mean.append(np.mean(bin_diff_values))
                    binned_diffs_std.append(np.std(bin_diff_values))
        
        if binned_times:
            binned_times = np.array(binned_times)
            binned_diffs_mean = np.array(binned_diffs_mean)
            binned_diffs_std = np.array(binned_diffs_std)
            
            plt.plot(binned_times, binned_diffs_mean, label=f'{distance}m', 
                    color=colors[i], marker=markers[i % len(markers)], markersize=6,
                    linewidth=2, alpha=0.9, markevery=max(1, len(binned_times)//15))
            
            plt.fill_between(binned_times, 
                           binned_diffs_mean - binned_diffs_std,
                           binned_diffs_mean + binned_diffs_std,
                           color=colors[i], alpha=0.2)
    
    plt.xlabel('Time (seconds)')
    plt.ylabel('Mean Time Difference (ms)')
    plt.title(f'Mean Time Between Consecutive Advertisements ({num_bins} bins)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f'{output_dir}/timestamp_diff_vs_time.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved timestamp diff plot to {output_dir}/timestamp_diff_vs_time.png")

def plot_advertisements_per_distance(distance_rssi_data: dict[float, list[float]], distance_run_timestamps: dict[float, dict[int, list[float]]], output_dir: str):
    """
    Plot advertisement delivery success probability vs. distance using two different calculation methods.
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7, 8))

    # --- Subplot 1: Success probability relative to advertisements received at 0.0m ---
    if 0.0 not in distance_rssi_data or not distance_rssi_data[0.0]:
        print("Error: No data for distance 0.0, cannot calculate relative success probability.")
        ax1.text(0.5, 0.5, "No data for distance 0.0", ha='center', va='center')
    else:
        # Calculate per-run statistics for error bars
        # First, organize data by run
        run_counts: dict[int, dict[float, int]] = defaultdict(lambda: defaultdict(int))
        for distance, timestamps_by_run in distance_run_timestamps.items():
            for run, timestamps in timestamps_by_run.items():
                run_counts[run][distance] = len(timestamps)
        
        # Get the baseline (distance 0.0) per run
        total_received_at_zero = len(distance_rssi_data[0.0])

        distances1: list[float] = []
        probabilities1: list[float] = []
        counts1: list[int] = []
        std_devs1: list[float] = []
        for distance in sorted(distance_rssi_data.keys()):
            received_count = len(distance_rssi_data[distance])
            if received_count > 0:
                # Calculate per-run success probabilities
                run_probs: list[float] = []
                for run in run_counts.keys():
                    if 0.0 in run_counts[run] and run_counts[run][0.0] > 0:
                        run_total_at_zero = run_counts[run][0.0]
                        run_count_at_distance = run_counts[run].get(distance, 0)
                        run_probs.append(run_count_at_distance / run_total_at_zero)
                
                distances1.append(distance)
                probabilities1.append(received_count / total_received_at_zero)
                counts1.append(received_count)
                std_devs1.append(float(np.std(run_probs) if run_probs else 0.0))
        
        x_pos1 = np.arange(len(distances1)) * 1.3
        ax1.bar(x_pos1, probabilities1, width=0.8, color='skyblue', edgecolor='black', alpha=0.7,
                yerr=std_devs1, capsize=5, error_kw={'elinewidth': 1, 'capthick': 1})
        ax1.set_ylabel('Success Probability')
        ax1.set_title('Ad Delivery Success Rate (Based on Ads received at 0m)')
        ax1.grid(True, alpha=0.3, axis='y')
        ax1.set_ylim(0, 1.1)
        ax1.set_xticks(x_pos1)
        ax1.set_xticklabels([f'{d:.1f}' if d < 10 else f'{int(d)}' for d in distances1], rotation=45, ha='right')
        for i, (prob, count) in enumerate(zip(probabilities1, counts1)):
            ax1.text(x_pos1[i], prob, f'{prob:.1%}\n(n={count})', ha='center', va='bottom', fontsize=9)

    # --- Subplot 2: Success probability based on estimated total sent (25ms interval) ---
    if 0.0 not in distance_run_timestamps:
        print("Error: No timestamp data for distance 0.0, cannot estimate total sent.")
        ax2.text(0.5, 0.5, "No timestamp data for distance 0.0", ha='center', va='center')
    else:
        # Calculate per-run statistics for error bars
        run_durations: dict[int, float] = {}
        for run, timestamps in distance_run_timestamps[0.0].items():
            if len(timestamps) > 1:
                run_durations[run] = max(timestamps) - min(timestamps)
        
        total_duration_ms = sum(run_durations.values())
        
        if total_duration_ms == 0:
            print("Error: Could not calculate total duration from 0.0m runs.")
            ax2.text(0.5, 0.5, "Could not calculate total duration", ha='center', va='center')
        else:
            estimated_total_sent = total_duration_ms / 25.0

            distances2: list[float] = []
            probabilities2: list[float] = []
            counts2: list[int] = []
            std_devs2: list[float] = []
            for distance in sorted(distance_rssi_data.keys()):
                received_count = len(distance_rssi_data[distance])
                if received_count > 0:
                    # Calculate per-run success probabilities
                    run_probs: list[float] = []
                    for run in run_durations.keys():
                        if run in run_durations:
                            run_estimated_sent = run_durations[run] / 25.0
                            run_count_at_distance = len(distance_run_timestamps[distance].get(run, []))
                            run_probs.append(run_count_at_distance / run_estimated_sent if run_estimated_sent > 0 else 0)
                    
                    distances2.append(distance)
                    probabilities2.append(received_count / estimated_total_sent)
                    counts2.append(received_count)
                    std_devs2.append(float(np.std(run_probs) if run_probs else 0.0))

            x_pos2 = np.arange(len(distances2)) * 1.3
            ax2.bar(x_pos2, probabilities2, width=0.8, color='green', edgecolor='black', alpha=0.7,
                    yerr=std_devs2, capsize=5, error_kw={'elinewidth': 1, 'capthick': 1})
            ax2.set_xlabel('Distance (meters)')
            ax2.set_ylabel('Success Probability')
            ax2.set_title('Ad Delivery Success Rate (Based on 25ms Ad Interval)')
            ax2.grid(True, alpha=0.3, axis='y')
            ax2.set_ylim(0, 1.1)
            ax2.set_xticks(x_pos2)
            ax2.set_xticklabels([f'{d:.1f}' if d < 10 else f'{int(d)}' for d in distances2], rotation=45, ha='right')
            for i, (prob, count) in enumerate(zip(probabilities2, counts2)):
                ax2.text(x_pos2[i], prob, f'{prob:.1%}\n(n={count})', ha='center', va='bottom', fontsize=9)

    plt.tight_layout(pad=3.0)
    plt.savefig(f'{output_dir}/advertisement_success_probability.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved advertisement success probability plot to {output_dir}/advertisement_success_probability.png")

def print_run_durations(distance_run_timestamps: dict[float, dict[int, list[float]]]):
    """Prints the duration of each run for each distance."""
    print("\nRun Durations (ms):")
    print("=" * 80)
    
    for distance in sorted(distance_run_timestamps.keys()):
        print(f"\nDistance: {distance:.1f}m")
        print("-" * 80)

        run_durations: list[float] = []
        for run, timestamps in sorted(distance_run_timestamps[distance].items()):
            if len(timestamps) > 1:
                duration = max(timestamps) - min(timestamps)
                run_durations.append(duration)
                print(f"  Run {run:2d}: {duration:12.2f} ms ({duration/1000:.2f} s)")
            else:
                print(f"  Run {run:2d}: (insufficient data)")
        
        if run_durations:
            print(f"\n  Mean duration: {np.mean(run_durations):12.2f} ms ({np.mean(run_durations)/1000:.2f} s)")
            print(f"  Total duration: {np.sum(run_durations):12.2f} ms ({np.sum(run_durations)/1000:.2f} s)")

def print_timestamp_diff_overview(distance_run_timestamps: dict[float, dict[int, list[float]]]):
    """Prints an overview of timestamp differences for each distance."""
    print("\nTimestamp Difference Overview (ms):")
    print("Distance (m)\tMin Diff\tMean Diff\tMedian Diff\tMax Diff")
    print("-" * 80)

    for distance in sorted(distance_run_timestamps.keys()):
        all_diffs: list[float] = []
        run_diffs_data = {}

        for run, timestamps in distance_run_timestamps[distance].items():
            if len(timestamps) > 1:
                sorted_stamps = sorted(timestamps)
                diffs = np.diff(sorted_stamps)
                all_diffs.extend(diffs)
                run_diffs_data[run] = diffs
        
        if not all_diffs:
            print(f"{distance:8.1f}\t(no data)")
            continue

        mean_diff = np.mean(all_diffs)
        median_diff = np.median(all_diffs)
        std_diff = np.std(all_diffs)
        min_diff = np.min(all_diffs)
        max_diff = np.max(all_diffs)

        outlier_runs = []
        for run, diffs in run_diffs_data.items():
            # Check if any diff in this run is an outlier
            if np.any(np.abs(diffs - median_diff) > 10):
                outlier_runs.append(str(run))
                # if run == 0 and distance == 0.0:
                #     print(f"Debug: Distance {distance}, Run {run}, Diffs: {diffs}")
        
        outlier_str = ", ".join(outlier_runs) if outlier_runs else "None"

        # print(f"{distance:8.1f}\t{min_diff:8.2f}\t{mean_diff:9.2f}\t{median_diff:9.2f}\t{max_diff:8.2f}\t{outlier_str}")
        print(f"{distance:8.1f}\t{min_diff:8.2f}\t{mean_diff:9.2f}\t{median_diff:9.2f}\t{max_diff:8.2f}")

def parse_arguments():
    import argparse
    parser = argparse.ArgumentParser(description="Plot RSSI data from log files")
    parser.add_argument("--input-dir", type=str, default="./ranges", help="Directory containing range subdirectories with log files")
    parser.add_argument("--output-dir", type=str, default="./plots", help="Directory to save plots")
    return parser.parse_args()

def process_data(input_dir: Path, ranges: list[str]):
    distance_rssi_data: dict[float, list[float]] = {}
    distance_time_rssi_data: dict[float, dict[float, list[float]]] = defaultdict(lambda: defaultdict(list))
    distance_run_timestamps: dict[float, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list)) # Map distance to run to timestamp differences

    for range_dir in ranges:
        distance = float(range_dir)
        distance_rssi_data[distance] = []

        path_to_range_directory = input_dir / range_dir
        
        # Read summary file to get run timestamps
        summary_file = path_to_range_directory / "rssi_log.csv_summary.csv"
        if not summary_file.exists():
            print(f"Warning: No summary file for distance {distance}m, skipping...")
            continue
        
        run_timestamps = parse_summary_file(summary_file)
        if not run_timestamps:
            print(f"Warning: No valid run timestamps in summary file for distance {distance}m, skipping...")
            continue

        # Process each run using timestamps from summary file
        for run_idx, (run_start_ts, run_end_ts) in run_timestamps.items():
            log_filenames = [f for f in listdir(path_to_range_directory) if f"_run{run_idx}.csv" in f]
            if not log_filenames:
                continue
            
            log_filename = log_filenames[0]
            full_path_to_logfile = path_to_range_directory / log_filename

            run_start_timestamp_ms = run_start_ts * 1000  # Convert to milliseconds
            run_end_timestamp_ms = run_end_ts * 1000      # Convert to milliseconds
            run_duration_ms = run_end_timestamp_ms - run_start_timestamp_ms
            valid_samples_count = 0
            skipped_samples_count = 0

            with open(full_path_to_logfile, "r") as log_file:
                for i, line in enumerate(log_file):
                    content = line.strip()
                    
                    # format is timestamp in milliseconds, rssi, device name
                    parts = content.split(",")
                    if len(parts) == 4:
                        timestamp, rssi, device_name, tx_power = parts
                    elif len(parts) == 3:
                        timestamp, rssi, device_name = parts
                    else:
                        print(f"Warning: Unexpected line format in {full_path_to_logfile}: {line}")
                        raise ValueError("Unexpected line format")

                    timestamp_ms = float(timestamp) * 1000  # convert to milliseconds
                    rssi_value = float(rssi)
                    
                    # Only include timestamps within the run's time window from summary
                    if run_start_timestamp_ms <= timestamp_ms <= run_end_timestamp_ms:
                        # Store for CDF plot
                        distance_rssi_data[distance].append(rssi_value)
                        
                        # Store for time-based plot using RELATIVE time so runs can be combined
                        # Use relative time in seconds as the key
                        time_since_start = timestamp_ms - run_start_timestamp_ms
                        relative_time_s = time_since_start / 1000
                        distance_time_rssi_data[distance][relative_time_s].append(rssi_value)
                        
                        # Store timestamps per run for diff analysis (keep absolute timestamps here)
                        distance_run_timestamps[distance][run_idx].append(timestamp_ms)
                        valid_samples_count += 1
                    else:
                        skipped_samples_count += 1
            
            if skipped_samples_count > 0:
                run_duration_s = run_duration_ms / 1000
                print(f"Distance {distance:6.1f}m, Run {run_idx:2d}: kept {valid_samples_count:5d} samples, skipped {skipped_samples_count:5d} samples (outside {run_duration_s:.0f}s window)")

    return distance_rssi_data, distance_time_rssi_data, distance_run_timestamps

def main():
    args = parse_arguments()
    ranges: list[str] = list(listdir(args.input_dir))
    makedirs(args.output_dir, exist_ok=True)

    distance_rssi_data, distance_time_rssi_data, distance_run_timestamps = process_data(Path(args.input_dir), ranges)

    plot_rssi_vs_distance(distance_rssi_data, args.output_dir)
    plot_density(distance_rssi_data, args.output_dir, 30)
    plot_cdf(distance_rssi_data, args.output_dir)
    plot_rssi_vs_time(distance_time_rssi_data, args.output_dir)
    plot_timestamp_diff_vs_time(distance_time_rssi_data, args.output_dir)
    plot_advertisements_per_distance(distance_rssi_data, distance_run_timestamps, args.output_dir)
    print_run_durations(distance_run_timestamps)
    print_timestamp_diff_overview(distance_run_timestamps)

if __name__ == "__main__":
    main()
