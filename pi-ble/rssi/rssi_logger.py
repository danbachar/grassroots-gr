# python rssi_logger.py --runs 20 -w ranges/0.0/rssi_log.csv -d 60
#!/usr/bin/env python3
import asyncio
import logging
import argparse
import time
import numpy as np
from pathlib import Path
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class textcolor:
    GREEN = '\033[92m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    YELLOW = '\033[93m'
    GOLD = '\033[33m'
    BOLD = '\033[1m'
    END = '\033[0m'

def is_trusted_peer(name: str) -> bool:
    return name.startswith("gr")

async def scan_for_peers(scan_duration: int, log_filename: str, runs: int, start_run: int):
    """Scan for trusted servers. A trusted server is a server whose name begins with 'gr'."""

    def detection_callback(device: BLEDevice, advertisement_data: AdvertisementData):
        device_name: str = (advertisement_data.local_name and advertisement_data.local_name) or (device.name and device.name) or ""

        if is_trusted_peer(device_name):
            timestamp = time.time()
            rssi = advertisement_data.rssi
            tx_power = advertisement_data.tx_power or float('-inf')
            line = f'{timestamp},{rssi},{device_name},{tx_power}'
            lines.append(line)

    scanner = BleakScanner(detection_callback=detection_callback)
    total_count = 0
    start_time = time.time()

    for run in range(start_run, start_run + runs):
        print(f"🔍 Starting scan {run+1}/{runs} for {scan_duration} seconds...")
        lines: list[str] = []
        run_start_timestamp = time.time()
        await scanner.start()
        await asyncio.sleep(scan_duration)
        await scanner.stop()
        run_end_timestamp = time.time()
        
        # ensure log file path exists
        full_filepath = log_filename + f"_run{run}.csv"
        Path(full_filepath).parent.mkdir(parents=True, exist_ok=True)
        
        run_rssi_values = []
        if lines:
            try:
                run_rssi_values = [float(line.split(',')[1]) for line in lines]
            except (IndexError, ValueError) as e:
                print(f"Could not parse RSSI from lines: {e}")

        summary_full_filepath = log_filename + f"_summary.csv"
        Path(summary_full_filepath).parent.mkdir(parents=True, exist_ok=True)

        with open(summary_full_filepath, 'a') as summary_file:
            with open(full_filepath, 'a') as f:
                summary_file.write(f"# Run {run} Start Timestamp: {run_start_timestamp}\n")
                summary_file.write(f"# Run {run} End Timestamp: {run_end_timestamp}\n")
                for line in lines:
                    f.write(line + '\n')
            
            if run_rssi_values:
                mean = np.mean(run_rssi_values)
                std = np.std(run_rssi_values)
                count = len(run_rssi_values)
                total_count += count

                summary = (f"🤝 Run {run+1} complete. Samples: {count}, Mean RSSI: {mean:.2f} ± {std:.2f} dBm.")
            else:
                summary = (f"🤝 Run {run+1} complete. No trusted advertisements found.")
            print(summary)
            summary_file.write(summary + '\n')
    elapsed_time = time.time() - start_time
    summary = f"⏱️ Total elapsed time: {elapsed_time:.2f} seconds, total ads: {total_count}, writing summary to {summary_full_filepath}"
    with open(summary_full_filepath, 'a') as summary_file:
        summary_file.write(summary + "\n")
    print(summary)
    
def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='BLE Advertisement Test')
    parser.add_argument('-s', '--start', type=int, default=0,
                        help='Start run (default: 0)')
    parser.add_argument('-d', '--scan-duration', type=float, default=60.0,
                        help='Duration to scan for advertisements (default: 60.0 seconds)')
    parser.add_argument('-w', '--log-filename', default='rssi_log.csv',
                        help='Log file name (default: rssi_log.csv)')
    parser.add_argument('-r', '--runs', type=int, default=20,
                        help='Number of scan runs (default: 20)')
    return parser.parse_args()

async def main():
    args = parse_arguments()
    await scan_for_peers(scan_duration=args.scan_duration, log_filename=args.log_filename, runs=args.runs, start_run=args.start)

if __name__ == "__main__":
    asyncio.run(main())
