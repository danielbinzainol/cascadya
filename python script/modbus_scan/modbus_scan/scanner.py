from __future__ import annotations

import math
import struct
import time
import uuid

from modbus_scan.client import ModbusTCPClient, TransportError
from modbus_scan.governor import RateGovernor
from modbus_scan.models import (
    ModbusExceptionCode,
    ModbusObjectType,
    ObjectScanSummary,
    ProfileReport,
    ReadResult,
    ScanEntry,
    ScanReport,
)
from modbus_scan.utils import utc_now_iso


def build_scan_report(
    client: ModbusTCPClient,
    host: str,
    port: int,
    unit_id: int,
    object_types: list[ModbusObjectType],
    start_address: int,
    end_address: int,
    block_size_initial: int,
    block_size_max: int,
    retries: int,
    max_rps: float,
    operating_ceiling_rps: float,
    profiling: ProfileReport | None,
    progress_callback=None,
) -> ScanReport:
    started_at = utc_now_iso()
    governor = RateGovernor(
        start_rps=profiling.recommended_req_per_sec if profiling else operating_ceiling_rps,
        ceiling_rps=operating_ceiling_rps,
        baseline_p95_ms=profiling.baseline_p95_rtt_ms if profiling else None,
    )
    entries: list[ScanEntry] = []
    object_summaries: list[ObjectScanSummary] = []
    observed_rps: list[float] = []

    for object_type in object_types:
        summary = ObjectScanSummary(object_type=object_type.value)
        object_summaries.append(summary)
        if progress_callback:
            progress_callback(f"Scanning {object_type.value} from {start_address} to {end_address}")
        _scan_object_type(
            client=client,
            unit_id=unit_id,
            object_type=object_type,
            start_address=start_address,
            end_address=end_address,
            block_size_initial=block_size_initial,
            block_size_max=block_size_max,
            retries=retries,
            governor=governor,
            entries=entries,
            summary=summary,
            observed_rps=observed_rps,
        )

    _enrich_register_decodings(entries)
    average_rps = round(sum(observed_rps) / len(observed_rps), 3) if observed_rps else 0.0
    finished_at = utc_now_iso()
    return ScanReport(
        scan_id=str(uuid.uuid4()),
        started_at=started_at,
        finished_at=finished_at,
        target=host,
        port=port,
        unit_id=unit_id,
        start_address=start_address,
        end_address=end_address,
        configured_max_rps=max_rps,
        operating_ceiling_rps=operating_ceiling_rps,
        initial_rps=profiling.recommended_req_per_sec if profiling else operating_ceiling_rps,
        average_rps=average_rps,
        profiling=profiling,
        object_summaries=object_summaries,
        entries=entries,
    )


def _scan_object_type(
    client: ModbusTCPClient,
    unit_id: int,
    object_type: ModbusObjectType,
    start_address: int,
    end_address: int,
    block_size_initial: int,
    block_size_max: int,
    retries: int,
    governor: RateGovernor,
    entries: list[ScanEntry],
    summary: ObjectScanSummary,
    observed_rps: list[float],
) -> None:
    current_address = start_address
    current_block_size = max(1, min(block_size_initial, block_size_max, object_type.max_count))

    while current_address <= end_address:
        count = min(current_block_size, block_size_max, object_type.max_count, end_address - current_address + 1)
        result = _perform_read_with_retries(
            client=client,
            unit_id=unit_id,
            object_type=object_type,
            address=current_address,
            count=count,
            retries=retries,
            governor=governor,
        )

        observed_rps.append(governor.current_rps)
        if result is None:
            summary.transport_errors += 1
            if count > 1:
                current_block_size = max(1, count // 2)
                continue
            summary.addresses_tested += 1
            _append_error_entry(
                entries=entries,
                unit_id=unit_id,
                object_type=object_type,
                address=current_address,
                error_type="transport_error",
                response_time_ms=None,
                current_rps=governor.current_rps,
            )
            current_address += 1
            current_block_size = max(1, min(block_size_initial, 2))
            continue

        if result.is_success:
            summary.addresses_tested += count
            summary.values_read += len(result.values)
            for offset, raw_value in enumerate(result.values):
                address = current_address + offset
                entries.append(
                    ScanEntry(
                        timestamp=utc_now_iso(),
                        unit_id=unit_id,
                        object_type=object_type.value,
                        address=address,
                        status="ok",
                        raw_value=raw_value,
                        raw_words=[raw_value],
                        response_time_ms=round(result.response_time_ms, 3),
                        effective_requests_per_second=round(governor.current_rps, 3),
                        candidate_decodings=_decode_single_value(object_type, raw_value),
                    )
                )
            current_address += count
            current_block_size = min(block_size_max, object_type.max_count, max(1, count * 2))
            governor.observe_success(result.response_time_ms)
            continue

        if result.exception_code == ModbusExceptionCode.ILLEGAL_FUNCTION:
            summary.supported = False
            summary.illegal_function_errors += 1
            break

        if result.exception_code == ModbusExceptionCode.ILLEGAL_DATA_ADDRESS:
            summary.illegal_data_address_errors += 1
            governor.observe_success(result.response_time_ms)
            if count > 1:
                current_block_size = max(1, count // 2)
                continue
            summary.addresses_tested += 1
            summary.invalid_addresses += 1
            _append_error_entry(
                entries=entries,
                unit_id=unit_id,
                object_type=object_type,
                address=current_address,
                error_type="illegal_data_address",
                response_time_ms=result.response_time_ms,
                current_rps=governor.current_rps,
            )
            current_address += 1
            current_block_size = max(1, min(block_size_initial, 2))
            continue

        governor.observe_success(result.response_time_ms)
        if count > 1:
            current_block_size = max(1, count // 2)
            continue
        summary.addresses_tested += 1
        _append_error_entry(
            entries=entries,
            unit_id=unit_id,
            object_type=object_type,
            address=current_address,
            error_type=result.exception_name or "modbus_exception",
            response_time_ms=result.response_time_ms,
            current_rps=governor.current_rps,
        )
        current_address += 1


def _perform_read_with_retries(
    client: ModbusTCPClient,
    unit_id: int,
    object_type: ModbusObjectType,
    address: int,
    count: int,
    retries: int,
    governor: RateGovernor,
) -> ReadResult | None:
    for attempt in range(retries + 1):
        governor.wait_for_slot()
        try:
            return client.read(object_type, address, count, unit_id)
        except TransportError:
            governor.observe_transport_error()
            if attempt >= retries:
                return None
            time.sleep(min(0.25 * (attempt + 1), 1.0))
            try:
                client.reconnect()
            except TransportError:
                continue
    return None


def _append_error_entry(
    entries: list[ScanEntry],
    unit_id: int,
    object_type: ModbusObjectType,
    address: int,
    error_type: str,
    response_time_ms: float | None,
    current_rps: float,
) -> None:
    entries.append(
        ScanEntry(
            timestamp=utc_now_iso(),
            unit_id=unit_id,
            object_type=object_type.value,
            address=address,
            status="error",
            error_type=error_type,
            response_time_ms=round(response_time_ms, 3) if response_time_ms is not None else None,
            effective_requests_per_second=round(current_rps, 3),
        )
    )


def _decode_single_value(object_type: ModbusObjectType, raw_value: int) -> dict[str, object]:
    if object_type.is_bit_access:
        return {"bool": bool(raw_value)}
    signed = raw_value if raw_value < 0x8000 else raw_value - 0x10000
    bytes_two = raw_value.to_bytes(2, byteorder="big", signed=False)
    ascii_hint = "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in bytes_two)
    return {
        "uint16": raw_value,
        "int16": signed,
        "hex": f"0x{raw_value:04X}",
        "bits": f"{raw_value:016b}",
        "ascii_hint": ascii_hint,
    }


def _enrich_register_decodings(entries: list[ScanEntry]) -> None:
    register_entries = [entry for entry in entries if entry.status == "ok" and "registers" in entry.object_type]
    entry_map = {(entry.object_type, entry.address): entry for entry in register_entries}
    for entry in register_entries:
        next_entry = entry_map.get((entry.object_type, entry.address + 1))
        if not next_entry or next_entry.raw_value is None or entry.raw_value is None:
            continue
        entry.candidate_decodings["pair_with_next"] = _decode_register_pair(entry.raw_value, next_entry.raw_value)


def _decode_register_pair(word_a: int, word_b: int) -> dict[str, object]:
    data_ab = word_a.to_bytes(2, "big") + word_b.to_bytes(2, "big")
    data_ba = word_b.to_bytes(2, "big") + word_a.to_bytes(2, "big")
    uint32_ab = int.from_bytes(data_ab, byteorder="big", signed=False)
    uint32_ba = int.from_bytes(data_ba, byteorder="big", signed=False)
    int32_ab = int.from_bytes(data_ab, byteorder="big", signed=True)
    int32_ba = int.from_bytes(data_ba, byteorder="big", signed=True)
    float_ab = struct.unpack(">f", data_ab)[0]
    float_ba = struct.unpack(">f", data_ba)[0]
    ascii_ab = "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in data_ab)
    return {
        "uint32_ab": uint32_ab,
        "uint32_ba": uint32_ba,
        "int32_ab": int32_ab,
        "int32_ba": int32_ba,
        "float32_ab": _safe_float(float_ab),
        "float32_ba": _safe_float(float_ba),
        "ascii_hint_ab": ascii_ab,
    }


def _safe_float(value: float) -> float | None:
    return round(value, 6) if math.isfinite(value) else None

