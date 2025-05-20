#!/usr/bin/env python3

import asyncio
import csv
import datetime
import logging
import os
import sys
from typing import Dict, Optional, Set

import click
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from govee_ble.parser import GoveeBluetoothDeviceData
from home_assistant_bluetooth import BluetoothServiceInfo

logging.basicConfig(
    level=logging.WARN,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

temp_data: Dict[str, Dict[int, float]] = {}

processed_devices = set()

found_h5055 = False
h5055_address = None

monitoring_start_time = None

def format_elapsed_time(start_time: datetime.datetime) -> str:
    elapsed_seconds = (datetime.datetime.now() - start_time).total_seconds()
    elapsed_hours = int(elapsed_seconds // 3600)
    elapsed_minutes = int((elapsed_seconds % 3600) // 60)
    display_seconds = int(elapsed_seconds % 60)
    return f"{elapsed_hours}:{elapsed_minutes:02d}:{display_seconds:02d}"


class TemperatureCapturingParser(GoveeBluetoothDeviceData):
    def __init__(self, device_address: str):
        super().__init__()
        self.device_address = device_address
    
    def update_temp_probe(self, temp: float, probe_id: int) -> None:
        super().update_temp_probe(temp, probe_id)
        
        if self.device_address not in temp_data:
            temp_data[self.device_address] = {}
        
        temp_data[self.device_address][probe_id] = temp
        logger.info(f"Updated device {self.device_address}, probe {probe_id}: {temp}°C")
    
    def update_temp_probe_with_alarm(self, temp: float, alarm_temp: float | None, probe_id: int, low_alarm_temp: float | None = None) -> None:
        super().update_temp_probe_with_alarm(temp, alarm_temp, probe_id, low_alarm_temp)
        
        if self.device_address not in temp_data:
            temp_data[self.device_address] = {}
        
        if temp is not None and temp > 0:
            temp_data[self.device_address][probe_id] = temp
            logger.info(f"Updated device {self.device_address}, probe {probe_id}: {temp}°C (alarm: {alarm_temp}°C, low alarm: {low_alarm_temp}°C)")


def process_advertisement(
    device: BLEDevice, advertisement_data: AdvertisementData
) -> None:
    name = str(device.name) if device.name else ""
    address = str(device.address)
    
    service_uuids = [str(uuid) for uuid in advertisement_data.service_uuids]
    
    if address not in processed_devices:
        logger.info(f"Device {address} advertisement data:")
        logger.info(f"  Name: {name}")
        logger.info(f"  UUIDs: {service_uuids}")
        logger.info(f"  Manufacturer Data: {advertisement_data.manufacturer_data}")
    
    service_info = BluetoothServiceInfo(
        name=name,
        address=address,
        rssi=advertisement_data.rssi,
        manufacturer_data=advertisement_data.manufacturer_data,
        service_data=advertisement_data.service_data,
        service_uuids=service_uuids,
        source="",
    )
    
    parser = TemperatureCapturingParser(address)
    
    parser._start_update(service_info)

    if parser.device_type == "H5055" and address not in processed_devices:
        processed_devices.add(address)
        logger.info(f"Found Govee H5055 device: {address}")
        global found_h5055, h5055_address
        found_h5055 = True
        h5055_address = address


def print_temperature_readings(csv_path: str) -> None:
    """Print the current temperature readings and write to CSV file."""
    if not temp_data:
        print("No Govee H5055 temperature readings available.")
        return
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    global monitoring_start_time
    if monitoring_start_time is None:
        monitoring_start_time = datetime.datetime.now()
    
    t_plus = format_elapsed_time(monitoring_start_time)
    
    for device_addr, probes in temp_data.items():
        if not probes:
            print("No temperature readings available")
            continue
            
        print(f"\n[{timestamp}] T+{t_plus} Device: {device_addr}")
        for probe_id, temp in sorted(probes.items()):
            print(f"  Probe {probe_id}: {temp:.1f}°C")
        
        row_data = {
            't_plus': t_plus,
            'device': device_addr
        }
        
        for probe_id, temp in sorted(probes.items()):
            row_data[f'probe_{probe_id}'] = f"{temp:.1f}"
        
        file_exists = os.path.isfile(csv_path)
        
        all_probe_ids = set()
        for dev_probes in temp_data.values():
            all_probe_ids.update(dev_probes.keys())
        
        fieldnames = ['t_plus', 'device']
        for probe_id in sorted(all_probe_ids):
            fieldnames.append(f'probe_{probe_id}')
        
        with open(csv_path, 'a', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerow(row_data)


async def scan_for_devices() -> bool:
    """Scan for BLE devices and process advertisements.
    
    Returns:
        bool: True if an H5055 device was found, False otherwise.
    """
    # Clear the set of processed devices at the start of each scan
    processed_devices.clear()
    global found_h5055
    found_this_scan = False
    
    def callback(device: BLEDevice, advertisement_data: AdvertisementData) -> None:
        try:
            process_advertisement(device, advertisement_data)
            # If we found an H5055 in this callback, remember it
            nonlocal found_this_scan
            if found_h5055:
                found_this_scan = True
        except Exception as e:
            logger.error(f"Error processing advertisement from {device.address}: {e}", exc_info=True)
    
    try:
        scanner = BleakScanner(callback)
        await scanner.start()
        
        # Scan for up to 10 seconds or until we find an H5055
        for _ in range(10):
            if found_h5055:
                break
            await asyncio.sleep(1)
            
        await scanner.stop()
        return found_this_scan or found_h5055
    except Exception as e:
        logger.error(f"Error during BLE scanning: {e}", exc_info=True)
        return False


async def scan_specific_device(device_address: str, timeout: int = 5) -> None:
    def callback(device: BLEDevice, advertisement_data: AdvertisementData) -> None:
        try:
            if str(device.address) == device_address:
                process_advertisement(device, advertisement_data)
        except Exception as e:
            logger.error(f"Error processing advertisement from {device.address}: {e}", exc_info=True)
    
    try:
        scanner = BleakScanner(callback)
        await scanner.start()
        await asyncio.sleep(timeout)
        await scanner.stop()
    except Exception as e:
        logger.error(f"Error during BLE scanning: {e}", exc_info=True)


async def main_loop(interval: int, csv_path: str) -> None:
    """Main program loop."""
    scan_count = 0
    try:
        while not found_h5055:
            scan_count += 1
            logger.info(f"\nStarting scan #{scan_count} to find H5055 device...")
            found = await scan_for_devices()
            if found:
                logger.info(f"H5055 device found! Address: {h5055_address}")
                print(f"Found H5055 device: {h5055_address}")
                break
            else:
                logger.info("No H5055 device found. Trying again...")
                await asyncio.sleep(1)
        
        logger.info(f"Switching to temperature monitoring mode with {interval} second interval")
        print(f"\nMonitoring temperatures from H5055 device every {interval} seconds...")
        
        global monitoring_start_time
        monitoring_start_time = datetime.datetime.now()
        print(f"Monitoring started at: {monitoring_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        while True:
            processed_devices.clear()
            await scan_specific_device(h5055_address, timeout=interval-1)
            print_temperature_readings(csv_path)
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        logger.error(f"Error in main loop: {e}", exc_info=True)
        sys.exit(1)


@click.command()
@click.option(
    "--interval",
    type=int,
    default=60,
    help="Interval between temperature readings in seconds (default: 60)",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging",
)
@click.option(
    "--output",
    type=click.Path(),
    default="govee_temperatures.csv",
    help="Path to output CSV file (default: govee_temperatures.csv)",
)
def main(interval: int, debug: bool, output: str) -> None:
    """Monitor temperatures from Govee H5055 meat thermometers."""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("Scanning for Govee H5055 devices...")
    print(f"Output CSV file: {output}")
    print("Once found, will monitor temperatures at the specified interval.")
    print("Press Ctrl+C to exit")
    
    try:
        asyncio.run(main_loop(interval, output))
    except KeyboardInterrupt:
        print("\nExiting...")


if __name__ == "__main__":
    main()
