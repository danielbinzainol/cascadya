import asyncio
from datetime import datetime, timedelta, timezone

from agent.modbus_executor import ModbusExecutor

async def main():
    q = asyncio.PriorityQueue()
    executor = ModbusExecutor(queue=q, safe_fallback_kw=0.0)

    asyncio.create_task(executor.worker())
    asyncio.create_task(executor.watchdog())

    # 1) On planifie des lectures (COLD)
    for _ in range(3):
        await executor.schedule_read()

    # 2) Puis une écriture HOT
    await asyncio.sleep(0.05)
    await executor.schedule_write_setpoint(
        p_kw=50,
        valid_to=datetime.now(timezone.utc) + timedelta(seconds=2),
        grace_period_s=3,
    )

    await asyncio.sleep(8)

asyncio.run(main())

