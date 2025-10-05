#!/usr/bin/env python3
import asyncio
import logging
import argparse
import time
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

async def scan_for_peers(scan_duration: int, log_filename: str, runs: int):
    """Scan for trusted servers. A trusted server is a server whose name begins with 'gr'."""

    def detection_callback(device: BLEDevice, advertisement_data: AdvertisementData):
        device_name: str = (advertisement_data.local_name and advertisement_data.local_name) or (device.name and device.name) or ""

        if is_trusted_peer(device_name):
            timestamp = time.time() * 1000 / 1000  # Convert to milliseconds
            rssi = advertisement_data.rssi
            line = f'{timestamp},{rssi},{device_name}'
            lines.append(line)


    scanner = BleakScanner(detection_callback=detection_callback)

    start_time = time.time()
    for run in range(runs):
        print(f"🔍 Starting scan run {run+1}/{runs} for {scan_duration} seconds...")
        lines = []
        await scanner.start()
        await asyncio.sleep(scan_duration)
        await scanner.stop()
        
        # ensure log file path exists
        full_filepath = log_filename + f"_run{run}.csv"
        Path(full_filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(full_filepath, 'a') as f:
            for line in lines:
                f.write(line + '\n')
            print(f"🤝 Counted {len(lines)} trusted advertisements.")
    elapsed_time = time.time() - start_time
    print(f"⏱️ Total elapsed time: {elapsed_time:.2f} seconds")

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='BLE Advertisement Test')
    parser.add_argument('-d', '--scan-duration', type=float, default=5.0,
                        help='Duration to scan for advertisements (default: 5.0 seconds)')
    parser.add_argument('-w', '--log-filename', default='rssi_log.csv',
                        help='Log file name (default: rssi_log.csv)')
    parser.add_argument('-r', '--runs', type=int, default=1,
                        help='Number of scan runs (default: 1)')
    return parser.parse_args()

async def main():
    args = parse_arguments()
    await scan_for_peers(scan_duration=args.scan_duration, log_filename=args.log_filename, runs=args.runs)

if __name__ == "__main__":
    asyncio.run(main())
