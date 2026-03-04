import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from agent.models import Job

log = logging.getLogger("modbus")


class ModbusExecutor:
    def __init__(self, queue: asyncio.PriorityQueue, safe_fallback_kw: float):
        self.queue = queue
        self.safe_fallback_kw = safe_fallback_kw
        self._last_write_job: Optional[Job] = None

    async def schedule_write_setpoint(
        self,
        p_kw: float,
        valid_to=None,
        grace_period_s: float = 0.0,
    ):
        """
        HOT write (priority 0)
        """
        now = datetime.now(timezone.utc)
        job = Job(
            priority=0,
            created_at=now,
            kind="write",
            payload={"p_kw": float(p_kw)},
            valid_to=valid_to,
            grace_period_s=float(grace_period_s),
        )
        await self.queue.put(job)

    async def schedule_read(self):
        """
        COLD read (priority 10)
        """
        job = Job(
            priority=10,
            created_at=datetime.now(timezone.utc),
            kind="read",
            payload={},
            valid_to=None,
            grace_period_s=0.0,
        )
        await self.queue.put(job)

    async def worker(self):
        log.info("Modbus worker started")
        while True:
            job: Job = await self.queue.get()
            try:
                await self._handle(job)
            finally:
                self.queue.task_done()

    async def _handle(self, job: Job):
        now = datetime.now(timezone.utc)

        # Drop stale jobs
        if job.valid_to and now > job.valid_to:
            log.warning(
                "DROP stale job | now=%s valid_to=%s payload=%s",
                now, job.valid_to, job.payload
            )
            return

        if job.kind == "write":
            self._last_write_job = job
            await self._write(job)
        else:
            await self._read(job)

    async def _write(self, job: Job):
        log.info("🔥 WRITE HOT executed | payload=%s", job.payload)
        await asyncio.sleep(0.05)

    async def _read(self, job: Job):
        log.info("❄️ READ COLD executed")
        await asyncio.sleep(0.3)

    async def watchdog(self):
        """
        Safety watchdog
        """
        while True:
            await asyncio.sleep(1.0)

            if not self._last_write_job or not self._last_write_job.valid_to:
                continue

            now = datetime.now(timezone.utc)
            valid_to = self._last_write_job.valid_to
            grace = timedelta(seconds=self._last_write_job.grace_period_s or 0.0)

            if now <= valid_to:
                continue

            if now <= valid_to + grace:
                log.warning(
                    "GRACE | holding last setpoint until %s (+%ss)",
                    valid_to, grace.total_seconds()
                )
                continue

            log.error(
                "SAFE | forcing fallback setpoint %.3f kW",
                self.safe_fallback_kw
            )

            safe_job = Job(
                priority=0,
                created_at=now,
                kind="write",
                payload={"p_kw": self.safe_fallback_kw},
                valid_to=None,
                grace_period_s=0.0,
            )
            await self.queue.put(safe_job)
            self._last_write_job = None
