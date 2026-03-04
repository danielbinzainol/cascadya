import asyncio
import logging
from datetime import datetime, timezone

log = logging.getLogger("telemetry_hot")


async def telemetry_hot_loop(modbus_executor, mqtt_client, site_id: str):
    """
    HOT path telemetry:
    - Lecture rapide (simulée pour l’instant)
    - Publish MQTT QoS 0 (fire & forget)
    """
    log.info("Telemetry HOT loop started")

    while True:
        try:
            await asyncio.sleep(1.0)

            # 🔹 Simule une mesure rapide (P_fast)
            p_fast = 12.3  # TODO: vraie lecture Modbus

            payload = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "p_fast_kw": p_fast,
            }

            # 🔹 Publish QoS 0 (non bloquant)
            mqtt_client.publish_json(
                topic=f"telemetry/{site_id}/hot/meas",
                payload=payload,
                qos=0,
            )

        except Exception as e:
            log.exception("HOT telemetry error: %s", e)
