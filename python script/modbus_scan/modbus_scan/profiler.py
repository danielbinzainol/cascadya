from __future__ import annotations

import statistics
import time

from modbus_scan.client import ModbusTCPClient, TransportError
from modbus_scan.models import (
    ModbusExceptionCode,
    ModbusObjectType,
    ProbeTarget,
    ProfileReport,
    ProfileStep,
)
from modbus_scan.utils import percentile


DEFAULT_FALLBACK_RPS = 3.0


def discover_unit_id(
    client: ModbusTCPClient,
    start_unit_id: int,
    end_unit_id: int,
    probe_address: int = 0,
) -> int | None:
    for unit_id in range(start_unit_id, end_unit_id + 1):
        for object_type in (ModbusObjectType.HOLDING_REGISTERS, ModbusObjectType.COILS):
            try:
                result = client.read(object_type, probe_address, 1, unit_id)
            except TransportError:
                continue
            if result.is_success or result.exception_code in {
                ModbusExceptionCode.ILLEGAL_DATA_ADDRESS,
                ModbusExceptionCode.ILLEGAL_FUNCTION,
            }:
                return unit_id
    return None


def discover_probe(
    client: ModbusTCPClient,
    unit_id: int,
    object_types: list[ModbusObjectType],
    start_address: int,
    end_address: int,
    budget: int,
) -> ProbeTarget | None:
    tested = 0
    for object_type in object_types:
        for address in range(start_address, end_address + 1):
            if tested >= budget:
                return None
            tested += 1
            try:
                result = client.read(object_type, address, 1, unit_id)
            except TransportError:
                continue
            if result.is_success:
                return ProbeTarget(object_type=object_type, address=address)
            if result.exception_code == ModbusExceptionCode.ILLEGAL_FUNCTION:
                break
    return None


class ThroughputProfiler:
    def __init__(
        self,
        client: ModbusTCPClient,
        unit_id: int,
        probe: ProbeTarget,
        max_rps: float,
        baseline_samples: int = 5,
        step_samples: int = 12,
        baseline_interval_s: float = 0.5,
        safety_factor: float = 0.70,
    ):
        self.client = client
        self.unit_id = unit_id
        self.probe = probe
        self.max_rps = max_rps
        self.baseline_samples = baseline_samples
        self.step_samples = step_samples
        self.baseline_interval_s = baseline_interval_s
        self.safety_factor = safety_factor

    def run(self) -> ProfileReport:
        baseline_rtts = self._collect_samples(rps=max(1.0, 1.0 / self.baseline_interval_s), samples=self.baseline_samples)
        baseline_median = statistics.median(baseline_rtts)
        baseline_p95 = percentile(baseline_rtts, 95)
        threshold_p95 = max(baseline_p95 * 3.0, baseline_p95 + 15.0)
        threshold_median = max(baseline_median * 2.5, baseline_median + 10.0)

        steps: list[ProfileStep] = []
        last_stable = 1.0
        stop_reason = "max_rps_reached"

        for requested_rps in _build_step_schedule(self.max_rps):
            step = ProfileStep(requested_rps=requested_rps, sample_count=self.step_samples)
            try:
                rtts = self._collect_samples(rps=requested_rps, samples=self.step_samples)
            except TransportError as exc:
                step.status = "transport_error"
                step.stop_reason = exc.kind
                steps.append(step)
                stop_reason = exc.kind
                break

            step.median_rtt_ms = statistics.median(rtts)
            step.p95_rtt_ms = percentile(rtts, 95)
            steps.append(step)

            if step.median_rtt_ms > threshold_median or step.p95_rtt_ms > threshold_p95:
                step.status = "latency_threshold_exceeded"
                step.stop_reason = "latency_deviation"
                stop_reason = "latency_deviation"
                break

            last_stable = requested_rps

        recommended = max(1.0, min(self.max_rps, round(last_stable * self.safety_factor, 2)))
        return ProfileReport(
            probe_object_type=self.probe.object_type.value,
            probe_address=self.probe.address,
            baseline_median_rtt_ms=round(baseline_median, 3),
            baseline_p95_rtt_ms=round(baseline_p95, 3),
            last_stable_req_per_sec=round(last_stable, 2),
            recommended_req_per_sec=recommended,
            configured_max_req_per_sec=self.max_rps,
            stop_reason=stop_reason,
            tested_steps=steps,
            fallback_used=False,
        )

    def _collect_samples(self, rps: float, samples: int) -> list[float]:
        interval = 1.0 / max(rps, 1.0)
        next_slot = time.monotonic()
        rtts: list[float] = []
        for _ in range(samples):
            now = time.monotonic()
            if next_slot > now:
                time.sleep(next_slot - now)
            result = self.client.read(self.probe.object_type, self.probe.address, 1, self.unit_id)
            if not result.is_success:
                raise TransportError(
                    "probe_exception",
                    f"Probe returned Modbus exception {result.exception_name or result.exception_code}",
                )
            rtts.append(result.response_time_ms)
            next_slot = max(next_slot, time.monotonic()) + interval
        return rtts


def fallback_profile(max_rps: float, probe: ProbeTarget | None = None, stop_reason: str = "probe_not_found") -> ProfileReport:
    recommended = min(max_rps, DEFAULT_FALLBACK_RPS)
    return ProfileReport(
        probe_object_type=probe.object_type.value if probe else None,
        probe_address=probe.address if probe else None,
        baseline_median_rtt_ms=None,
        baseline_p95_rtt_ms=None,
        last_stable_req_per_sec=recommended,
        recommended_req_per_sec=recommended,
        configured_max_req_per_sec=max_rps,
        stop_reason=stop_reason,
        tested_steps=[],
        fallback_used=True,
    )


def _build_step_schedule(max_rps: float) -> list[float]:
    base_steps = [2, 5, 10, 15, 20, 30, 40, 50, 75, 100, 150, 200]
    steps = [float(step) for step in base_steps if step <= max_rps]
    if not steps or steps[-1] != float(max_rps):
        steps.append(float(max_rps))
    return steps

