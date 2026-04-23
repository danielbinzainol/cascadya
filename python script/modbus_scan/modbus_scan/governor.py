from __future__ import annotations

import time

from modbus_scan.utils import percentile


class RateGovernor:
    def __init__(
        self,
        start_rps: float,
        ceiling_rps: float,
        baseline_p95_ms: float | None = None,
        min_rps: float = 1.0,
        window_size: int = 12,
    ):
        self.current_rps = max(min_rps, float(start_rps))
        self.ceiling_rps = max(self.current_rps, float(ceiling_rps))
        self.baseline_p95_ms = baseline_p95_ms
        self.min_rps = min_rps
        self.window_size = window_size
        self._next_slot_at = time.monotonic()
        self._window_rtts: list[float] = []
        self._recent_issues = 0

    def wait_for_slot(self) -> None:
        now = time.monotonic()
        if self._next_slot_at > now:
            time.sleep(self._next_slot_at - now)
            now = time.monotonic()
        interval = 1.0 / max(self.current_rps, self.min_rps)
        self._next_slot_at = max(self._next_slot_at, now) + interval

    def observe_success(self, rtt_ms: float) -> None:
        self._window_rtts.append(rtt_ms)
        if len(self._window_rtts) < self.window_size:
            return
        recent_p95 = percentile(self._window_rtts, 95)
        if self._should_slow_down(recent_p95):
            self.current_rps = max(self.min_rps, self.current_rps * 0.70)
            self._recent_issues += 1
        elif self._recent_issues > 0:
            self._recent_issues -= 1
        else:
            self.current_rps = min(self.ceiling_rps, self.current_rps + max(1.0, self.current_rps * 0.10))
        self._window_rtts.clear()

    def observe_transport_error(self) -> None:
        self.current_rps = max(self.min_rps, self.current_rps * 0.50)
        self._window_rtts.clear()
        self._recent_issues = min(self._recent_issues + 1, 5)

    def _should_slow_down(self, recent_p95: float) -> bool:
        if self.baseline_p95_ms is None:
            return False
        threshold = max(self.baseline_p95_ms * 2.5, self.baseline_p95_ms + 15.0)
        return recent_p95 > threshold

