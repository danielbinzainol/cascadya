# Modbus TCP Scanner MVP

This repository contains a read-only Modbus TCP scanner MVP focused on:

- persistent TCP sessions
- safe throughput profiling
- adaptive block scanning
- JSON and CSV exports
- a local Modbus TCP simulator for testing

## Quick Start

Run the simulator in one terminal:

```powershell
python -m modbus_scan simulate --host 127.0.0.1 --port 1502
```

Profile the simulated PLC:

```powershell
python -m modbus_scan profile --host 127.0.0.1 --port 1502 --unit-id 1 --max-rps 40
```

Run a scan with profiling enabled:

```powershell
python -m modbus_scan scan --host 127.0.0.1 --port 1502 --unit-id 1 --start-address 0 --end-address 600 --max-rps 40 --output-dir output
```

Discover the unit id first if needed:

```powershell
python -m modbus_scan scan --host 127.0.0.1 --port 1502 --unit-id-start 1 --unit-id-end 5 --start-address 0 --end-address 200 --max-rps 20
```

## CLI Commands

- `python -m modbus_scan simulate`
- `python -m modbus_scan profile`
- `python -m modbus_scan scan`

## Notes

- The scanner is strictly read-only.
- The profiler uses a single persistent TCP socket and one request in flight at a time.
- If no valid probe is found for profiling, the scanner falls back to a conservative request rate.
- Start with a narrow address range for early testing. This MVP is safe and functional, but very sparse address spaces are not fully optimized yet.
