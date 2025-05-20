# Govee Thermometer Monitor

A Quick and Dirty Python command-line tool to monitor temperature readings from Govee H5055 meat thermometers and save
the time-series data in a CSV.

## Installation

```bash
# Clone the repository
git clone https://github.com/jacoby6000/govee-thermometer.git
cd govee-thermometer

# Install with Poetry
poetry install
```

## Usage

### Parameters

| Parameter    | Type     | Default                  | Description |
|--------------|----------|--------------------------|-------------|
| `interval` | Argument | `60`                     | The time in seconds between readings. A number that is too low will result in more missed readings/failures. |
| `output`   | Argument | `govee_temperatures.csv` | The desired file path of the CSV output. |
| `debug`    | Flag     |                          | Enables verbose logging. |

### Examples

```bash
# Check temperatures every 60 seconds (default) with the default CSV location
poetry run govee-thermometer

# Check temperatures every 30 seconds with the default CSV location
poetry run govee-thermometer --interval 30

# Save temperature data to a custom CSV file with the default interval
poetry run govee-thermometer --output my_temperatures.csv

# Run with the default interval and CSV location and debug logging
poetry run govee-thermometer --debug
```

## Output

### Terminal Output
The tool displays real-time temperature readings in the terminal with the following format:

```
[2025-05-19 17:25:42] T+0:10 Device: B22D944F-87F5-95FC-404A-CD8DB152188C
  Probe 1: 73.1°C
  Probe 2: 68.9°C
```

### CSV Output
The tool automatically saves temperature readings to a CSV file (default: `govee_temperatures.csv`).
The CSV format includes:

```csv
t_plus,device,probe_1,probe_2
0:00,B22D944F-87F5-95FC-404A-CD8DB152188C,72.5,68.2
0:10,B22D944F-87F5-95FC-404A-CD8DB152188C,73.1,68.9
0:20,B22D944F-87F5-95FC-404A-CD8DB152188C,73.8,69.5
```

Each row represents a single time point with:
- Elapsed time since monitoring began (`t_plus`)
- Device ID
- Temperature readings for each probe in separate columns

## How It Works

This tool uses Bluetooth Low Energy (BLE) to monitor Govee H5055 meat thermometers:

1. **Device Discovery**: It first scans for any Govee H5055 meat thermometer in range.
2. **Continuous Monitoring**: Once a device is found, it switches to monitoring mode and scans for temperature updates.
3. **Data Display**: Temperature readings from all connected probes are displayed in the terminal.
4. **Data Logging**: All temperature data is saved to a CSV file for later analysis.

The tool performs these steps at the interval specified by the `--interval` parameter (in seconds).

## Requirements

- Python 3.10 or later
- Bluetooth adapter that supports BLE
- Govee H5055 meat thermometer

## Troubleshooting

If no devices are found:
- Ensure your Bluetooth adapter is enabled
- Verify that the H5055 thermometer is powered on
- Try running with `--debug` for more detailed logging
