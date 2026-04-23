from __future__ import annotations

import argparse
from pathlib import Path

from modbus_scan.client import ModbusTCPClient, TransportError
from modbus_scan.exporters import export_scan_report
from modbus_scan.models import ModbusObjectType, ProbeTarget
from modbus_scan.profiler import (
    ThroughputProfiler,
    discover_probe,
    discover_unit_id,
    fallback_profile,
)
from modbus_scan.scanner import build_scan_report
from modbus_scan.simulator import run_simulator_from_cli


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return args.func(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Modbus TCP scanner MVP")
    subparsers = parser.add_subparsers(dest="command", required=True)

    simulate_parser = subparsers.add_parser("simulate", help="Run a local Modbus TCP simulator")
    _add_simulator_args(simulate_parser)
    simulate_parser.set_defaults(func=run_simulator_from_cli)

    profile_parser = subparsers.add_parser("profile", help="Run safe throughput profiling only")
    _add_connection_args(profile_parser)
    _add_unit_id_args(profile_parser)
    _add_probe_args(profile_parser)
    profile_parser.add_argument("--max-rps", type=float, default=20.0)
    profile_parser.add_argument("--baseline-samples", type=int, default=5)
    profile_parser.add_argument("--step-samples", type=int, default=12)
    profile_parser.set_defaults(func=_run_profile)

    scan_parser = subparsers.add_parser("scan", help="Run throughput profiling and adaptive scanning")
    _add_connection_args(scan_parser)
    _add_unit_id_args(scan_parser)
    _add_probe_args(scan_parser)
    scan_parser.add_argument("--start-address", type=int, default=0)
    scan_parser.add_argument("--end-address", type=int, default=255)
    scan_parser.add_argument("--objects", default="holding_registers,input_registers,coils,discrete_inputs")
    scan_parser.add_argument("--block-size-initial", type=int, default=4)
    scan_parser.add_argument("--block-size-max", type=int, default=64)
    scan_parser.add_argument("--retries", type=int, default=2)
    scan_parser.add_argument("--max-rps", type=float, default=20.0)
    scan_parser.add_argument("--baseline-samples", type=int, default=5)
    scan_parser.add_argument("--step-samples", type=int, default=12)
    scan_parser.add_argument("--skip-profile", action="store_true")
    scan_parser.add_argument("--output-dir", default="output")
    scan_parser.set_defaults(func=_run_scan)

    return parser


def _add_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=502)
    parser.add_argument("--timeout", type=float, default=1.0)


def _add_unit_id_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--unit-id", type=int)
    parser.add_argument("--unit-id-start", type=int, default=1)
    parser.add_argument("--unit-id-end", type=int, default=5)


def _add_probe_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--probe-object", choices=[item.value for item in ModbusObjectType])
    parser.add_argument("--probe-address", type=int)
    parser.add_argument("--probe-budget", type=int, default=32)


def _add_simulator_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1502)
    parser.add_argument("--unit-id", type=int, default=1)
    parser.add_argument("--base-delay-ms", type=float, default=3.0)
    parser.add_argument("--load-threshold-rps", type=float, default=25.0)
    parser.add_argument("--overload-delay-ms", type=float, default=6.0)


def _run_profile(args: argparse.Namespace) -> int:
    with ModbusTCPClient(args.host, args.port, args.timeout) as client:
        unit_id = _resolve_unit_id(client, args)
        if unit_id is None:
            print("No responding unit id found")
            return 2

        probe = _resolve_probe(client, args, unit_id)
        if probe is None:
            report = fallback_profile(args.max_rps, stop_reason="probe_not_found")
        else:
            report = ThroughputProfiler(
                client=client,
                unit_id=unit_id,
                probe=probe,
                max_rps=args.max_rps,
                baseline_samples=args.baseline_samples,
                step_samples=args.step_samples,
            ).run()

    print(f"Unit ID: {unit_id}")
    print(f"Probe: {report.probe_object_type}@{report.probe_address}")
    print(f"Recommended req/s: {report.recommended_req_per_sec}")
    print(f"Last stable req/s: {report.last_stable_req_per_sec}")
    print(f"Stop reason: {report.stop_reason}")
    return 0


def _run_scan(args: argparse.Namespace) -> int:
    object_types = [ModbusObjectType.from_cli_value(item) for item in args.objects.split(",") if item.strip()]
    with ModbusTCPClient(args.host, args.port, args.timeout) as client:
        unit_id = _resolve_unit_id(client, args)
        if unit_id is None:
            print("No responding unit id found")
            return 2

        profiling = None
        operating_ceiling_rps = args.max_rps
        if not args.skip_profile:
            probe = _resolve_probe(client, args, unit_id, object_types, args.start_address, args.end_address)
            if probe is None:
                profiling = fallback_profile(args.max_rps, stop_reason="probe_not_found")
            else:
                try:
                    profiling = ThroughputProfiler(
                        client=client,
                        unit_id=unit_id,
                        probe=probe,
                        max_rps=args.max_rps,
                        baseline_samples=args.baseline_samples,
                        step_samples=args.step_samples,
                    ).run()
                except TransportError as exc:
                    profiling = fallback_profile(args.max_rps, probe=probe, stop_reason=exc.kind)
            operating_ceiling_rps = profiling.recommended_req_per_sec

        report = build_scan_report(
            client=client,
            host=args.host,
            port=args.port,
            unit_id=unit_id,
            object_types=object_types,
            start_address=args.start_address,
            end_address=args.end_address,
            block_size_initial=args.block_size_initial,
            block_size_max=args.block_size_max,
            retries=args.retries,
            max_rps=args.max_rps,
            operating_ceiling_rps=operating_ceiling_rps,
            profiling=profiling,
            progress_callback=print,
        )

    exported = export_scan_report(report, Path(args.output_dir))
    print(f"Unit ID: {unit_id}")
    print(f"Entries exported: {len(report.entries)}")
    print(f"Average req/s: {report.average_rps}")
    print(f"JSON export: {exported['json']}")
    print(f"CSV export: {exported['csv']}")
    return 0


def _resolve_unit_id(client: ModbusTCPClient, args: argparse.Namespace) -> int | None:
    if args.unit_id is not None:
        return args.unit_id
    return discover_unit_id(client, args.unit_id_start, args.unit_id_end)


def _resolve_probe(
    client: ModbusTCPClient,
    args: argparse.Namespace,
    unit_id: int,
    object_types: list[ModbusObjectType] | None = None,
    start_address: int = 0,
    end_address: int = 1023,
):
    if args.probe_object and args.probe_address is not None:
        return ProbeTarget(
            object_type=ModbusObjectType.from_cli_value(args.probe_object),
            address=args.probe_address,
        )
    candidate_types = object_types or ModbusObjectType.ordered_defaults()
    search_end = min(end_address, start_address + max(args.probe_budget - 1, 0))
    return discover_probe(client, unit_id, candidate_types, start_address, search_end, args.probe_budget)
