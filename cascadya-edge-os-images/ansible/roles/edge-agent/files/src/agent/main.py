import asyncio
import logging
from datetime import datetime, timezone

from agent.config import load_settings
from agent.logging_setup import setup_logging
from agent.models import Job
from agent.modbus_executor import ModbusExecutor
from agent.mqtt_client import MqttClient
from agent.telemetry_hot import telemetry_hot_loop
from agent.telemetry_cold import telemetry_cold_loop, spool_drain_loop


async def simulate_cold_reads(queue: asyncio.PriorityQueue):
    """
    Simule des lectures Modbus lentes (cold path)
    Utile tant que le vrai Modbus n'est pas branché
    """
    while True:
        await asyncio.sleep(0.2)
        job = Job(
            priority=10,
            created_at=datetime.now(timezone.utc),
            kind="read",
            payload={},
            valid_to=None,
            grace_period_s=0.0,
        )
        await queue.put(job)


async def main():
    # --------------------
    # Config & logs
    # --------------------
    settings = load_settings()
    setup_logging(settings.log_level)

    log = logging.getLogger("main")
    log.info("Cascadya-Agent starting")

    # --------------------
    # Modbus executor
    # --------------------
    queue = asyncio.PriorityQueue()
    executor = ModbusExecutor(
        queue=queue,
        safe_fallback_kw=settings.safe_fallback_kw,
    )

    # --------------------
    # MQTT client (mTLS)
    # --------------------
    mqtt_client = MqttClient(
        executor=executor,
        site_id=settings.site_id,
        host=settings.mqtt_host,
        port=settings.mqtt_port,
        ca_path=settings.mqtt_ca_path,
        cert_path=settings.mqtt_cert_path,
        key_path=settings.mqtt_key_path,
        client_id=settings.mqtt_client_id,
    )
    mqtt_client.start()

    # --------------------
    # Async tasks
    # --------------------
    tasks = [
        asyncio.create_task(executor.worker(), name="modbus-worker"),
        asyncio.create_task(executor.watchdog(), name="watchdog"),
        asyncio.create_task(simulate_cold_reads(queue), name="simulated-reads"),

        asyncio.create_task(
            telemetry_hot_loop(
                modbus_executor=executor,
                mqtt_client=mqtt_client,
                site_id=settings.site_id,
            ),
            name="telemetry-hot",
        ),
        asyncio.create_task(
            telemetry_cold_loop(
                mqtt_client=mqtt_client,
                site_id=settings.site_id,
            ),
            name="telemetry-cold",
        ),
        asyncio.create_task(
            spool_drain_loop(
                mqtt_client=mqtt_client,
                site_id=settings.site_id,
            ),
            name="spool-drain",
        ),
    ]

    log.info("All tasks started")

    # Run forever
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
