from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def _should_trigger_schedule(now_local: datetime) -> bool:
    return now_local.hour == 9 and now_local.minute == 0


def _last_triggered_date_in_tz(last_triggered_at, timezone: ZoneInfo):
    if last_triggered_at is None:
        return None
    return last_triggered_at.astimezone(timezone).date()
