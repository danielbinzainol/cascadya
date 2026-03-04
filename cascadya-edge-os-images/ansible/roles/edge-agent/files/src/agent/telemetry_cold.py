import asyncio
import gzip
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("telemetry_cold")

SPOOL_DIR = Path("data/spool")
SPOOL_MAX_MB = 200


def spool_size_mb():
    return sum(f.stat().st_size for f in SPOOL_DIR.glob("*.gz")) / (1024 * 1024)


async def telemetry_cold_loop(mqtt_client, site_id: str):
    """
    Cold telemetry:
    - accumulate in RAM
    - every 60s gzip + publish QoS1
    - if MQTT fails -> spool to disk
    """
    buffer = []
    last_flush = datetime.now(timezone.utc)

    log.info("Telemetry COLD loop started")

    while True:
        try:
            buffer.append({
                "ts": datetime.now(timezone.utc).isoformat(),
                "temp": 60.0,  # TODO vraie donnée
                "pressure": 3.2,
            })

            now = datetime.now(timezone.utc)
            if (now - last_flush).total_seconds() >= 60:
                payload = gzip.compress(json.dumps(buffer).encode())
                buffer.clear()
                last_flush = now

                try:
                    await mqtt_client.publish(
                        f"cold/telemetry/{site_id}",
                        payload=payload,
                        qos=1,
                    )
                    log.info("COLD batch sent (%d bytes)", len(payload))
                except Exception:
                    ts = now.strftime("%Y%m%d_%H%M%S")
                    path = SPOOL_DIR / f"{site_id}_{ts}.json.gz"

                    if spool_size_mb() < SPOOL_MAX_MB:
                        path.write_bytes(payload)
                        log.warning("MQTT down -> spooled %s", path)
                    else:
                        log.error("SPOOL FULL -> dropping batch")

        except Exception as e:
            log.exception("COLD telemetry error: %s", e)

        await asyncio.sleep(1.0)


async def spool_drain_loop(mqtt_client, site_id: str):
    log.info("Spool drain loop started")

    while True:
        for f in sorted(SPOOL_DIR.glob("*.gz")):
            try:
                await mqtt_client.publish(
                    f"cold/telemetry/{site_id}",
                    payload=f.read_bytes(),
                    qos=1,
                )
                f.unlink()
                log.info("Spool flushed %s", f.name)
            except Exception:
                break  # MQTT toujours down

        await asyncio.sleep(10)
