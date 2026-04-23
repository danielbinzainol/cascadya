"""
IEC 104 Server with NATS bridge.

Received values are forwarded as NATS messages:
  Subject: iec104.cmd.AFRR_CTRL_ENABLE      Payload: {"value": <bool>, "ts": <iso>}
  Subject: iec104.cmd.activation_perc  Payload: {"value": <int>,  "ts": <iso>}
"""

import asyncio
import json
import logging
import os
import signal
import threading
import ssl
from datetime import datetime, timezone

import c104
import nats

# ---------------------------------------------------------------------------
# Configuration (env-overridable)
# ---------------------------------------------------------------------------
IEC104_BIND_IP   = os.getenv("IEC104_BIND_IP",   "0.0.0.0")
IEC104_PORT      = int(os.getenv("IEC104_PORT",   "2404"))
IEC104_CA        = int(os.getenv("IEC104_CA",     "1"))       # Common Address
NATS_URL         = os.getenv("NATS_URL",          "nats://nats:4222")
NATS_SUBJECT_PFX = os.getenv("NATS_SUBJECT_PFX", "iec104.cmd")
LOG_LEVEL        = os.getenv("LOG_LEVEL",         "INFO")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
log = logging.getLogger("iec104-bridge")


# ---------------------------------------------------------------------------
# TLS configuration (optional, env-overridable)
# ---------------------------------------------------------------------------
NATS_TLS_ENABLED  = os.getenv("NATS_TLS_ENABLED",  "false").lower() == "true"
NATS_TLS_CA       = os.getenv("NATS_TLS_CA",       "/certs/ca.crt")
NATS_TLS_CERT     = os.getenv("NATS_TLS_CERT",     "/certs/client.crt")
NATS_TLS_KEY      = os.getenv("NATS_TLS_KEY",      "/certs/client.key")


# ---------------------------------------------------------------------------
# Build optional TLS context
# ---------------------------------------------------------------------------
tls_context = None
if NATS_TLS_ENABLED:
    tls_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=NATS_TLS_CA)
    tls_context.load_cert_chain(certfile=NATS_TLS_CERT, keyfile=NATS_TLS_KEY)
    log.info("NATS TLS enabled")

# ---------------------------------------------------------------------------
# Shared async NATS publisher (called from sync c104 callbacks via thread)
# ---------------------------------------------------------------------------
class NatsBridge:
    """Thread-safe wrapper around an async NATS connection."""

    def __init__(self) -> None:
        self._nc: nats.aio.client.Client | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()

    def attach(self, loop: asyncio.AbstractEventLoop, nc: nats.aio.client.Client) -> None:
        self._loop = loop
        self._nc   = nc
        self._ready.set()

    def publish(self, subject: str, payload: dict) -> None:
        """Fire-and-forget publish from any thread."""
        if not self._ready.is_set():
            log.warning("NATS not ready – dropping message on %s", subject)
            return
        data = json.dumps(payload).encode()
        asyncio.run_coroutine_threadsafe(
            self._nc.publish(subject, data),
            self._loop,
        )
        log.debug("NATS ▶ %s  %s", subject, payload)


bridge = NatsBridge()


# ---------------------------------------------------------------------------
# c104 callback helpers
# ---------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def on_receive_point(point: c104.Point, previous_info: c104.Information, message: c104.IncomingMessage) -> c104.ResponseState:
    """
    Called by c104 whenever a command / setpoint is received from a client.
    We forward the value to NATS and ACK the command.
    """
    ioa   = point.io_address
    value = point.value

    log.info("⬇  Received IOA=%d  value=%s  type=%s", ioa, value, point.type)

    if ioa == 3000:
        # AFRR_CTRL_ENABLE
        bridge.publish(
            f"{NATS_SUBJECT_PFX}.AFRR_CTRL_ENABLE",
            {"value": bool(value), "ts": _now_iso()},
        )
    elif ioa == 3001:
        # SYS_CTRL_REMOTE_ENABLE
        bridge.publish(
            f"{NATS_SUBJECT_PFX}.SYS_CTRL_REMOTE_ENABLE",
            {"value": bool(value), "ts": _now_iso()},
        )
    elif ioa == 3002:
        # SYS_CTRL_FAULT_RESET
        bridge.publish(
            f"{NATS_SUBJECT_PFX}.SYS_CTRL_FAULT_RESET",
            {"value": bool(value), "ts": _now_iso()},
        )
    elif ioa == 4002:
        # AFRR_SP_ACTIVATION
        bridge.publish(
            f"{NATS_SUBJECT_PFX}.AFRR_SP_ACTIVATION",
            {"value": int(value), "ts": _now_iso()},
        )

    else:
        log.warning("Received unexpected IOA=%d – ignoring", ioa)

    return c104.ResponseState.SUCCESS


# ---------------------------------------------------------------------------
# Build the c104 server
# ---------------------------------------------------------------------------
def build_server() -> tuple[c104.Server, dict[int, c104.Point]]:
    server = c104.Server(ip=IEC104_BIND_IP, port=IEC104_PORT)
    server.max_connections = 10

    station = server.add_station(common_address=IEC104_CA)

    points: dict[int, c104.Point] = {}

    # -- Monitored (published) single-point information ---------------------
    sp_ioas = {
        1000:  "SYS_STAT_PC_HEALTHY",
        1001:  "AFRR_STAT_AVAILABLE",
        1002:  "AFRR_STAT_ENABLED",
        1003:  "SYS_STAT_MAJOR_FAULT",
        1004:  "SYS_STAT_LOCAL_MODE",
        1005:  "SYS_STAT_EDGE_COMMS_OK",
        1006: "SYS_STAT_LIMIT_ACTIVE",
    }

    me_ioas = {
        2000: "AFRR_PWR_MEAS_TOTAL",
        2001: "AFRR_PWR_APPLIED",
        2002: "AFRR_CAP_UP",
        2003: "AFRR_CAP_DOWN",
        2004: "AFRR_ACTIVATION_LEVEL",
    }

    sys_ioas = {
        2101: "SYS_DIAG_LAST_ACTIVATION_RCVD",
    }

    for ioa, name in sp_ioas.items():
        pt = station.add_point(
            io_address  = ioa,
            type        = c104.Type.M_SP_NA_1,
            report_ms   = 0,      # spontaneous on value change
        )
        pt.value = False          # initialise to OFF / healthy
        points[ioa] = pt
        log.debug("Registered monitored point IOA=%d  (%s)", ioa, name)

    for ioa, name in me_ioas.items():
        pt = station.add_point(
            io_address  = ioa,
            type        = c104.Type.M_ME_NC_1,
            report_ms   = 200,
        )
        pt.value = 0.0
        points[ioa] = pt
        log.debug("Registered monitored point IOA=%d  (%s)", ioa, name)

    # -- Controllable: AFRR_CTRL_ENABLE (Single Command) 
    AFRR_CTRL_ENABLE = station.add_point(
        io_address = 3000,
        type       = c104.Type.C_SC_NA_1,
        report_ms  = 0,
    )
    AFRR_CTRL_ENABLE.on_receive(callable=on_receive_point)
    points[3000] = AFRR_CTRL_ENABLE
    log.debug("Registered command point IOA=3000 (AFRR_CTRL_ENABLE)")

    # -- Controllable: SYS_CTRL_REMOTE_ENABLE (Single Command)
    SYS_CTRL_REMOTE_ENABLE = station.add_point(
        io_address = 3001,
        type       = c104.Type.C_SC_NA_1,   # setpoint – scaled value (int16)
        report_ms  = 0,
    )
    SYS_CTRL_REMOTE_ENABLE.on_receive(callable=on_receive_point)
    points[3001] = SYS_CTRL_REMOTE_ENABLE
    log.debug("Registered setpoint point IOA=3001 (SYS_CTRL_REMOTE_ENABLE)")

    # -- Controllable: SYS_CTRL_FAULT_RESET (Single Command)
    SYS_CTRL_FAULT_RESET = station.add_point(
        io_address = 3002,
        type       = c104.Type.C_SC_NA_1,   # setpoint – scaled value (int16)
        report_ms  = 0,
    )
    SYS_CTRL_FAULT_RESET.on_receive(callable=on_receive_point)
    points[3002] = SYS_CTRL_FAULT_RESET
    log.debug("Registered setpoint point IOA=3002 (SYS_CTRL_FAULT_RESET)")

    # -- Controllable: AFRR_SP_ACTIVATION (Set Value)
    AFRR_SP_ACTIVATION = station.add_point(
        io_address = 4002,
        type       = c104.Type.C_SE_NB_1,   # setpoint – scaled value (int16)
        report_ms  = 0,
    )
    AFRR_SP_ACTIVATION.on_receive(callable=on_receive_point)
    points[4002] = AFRR_SP_ACTIVATION
    log.debug("Registered setpoint point IOA=4002 (AFRR_SP_ACTIVATION)")

    return server, points


# ---------------------------------------------------------------------------
# Public API – update a monitored point value
# ---------------------------------------------------------------------------
def set_point(points: dict[int, c104.Point], ioa: int, value: bool, quality: c104.Quality = c104.Quality(0)) -> None:
    """Update a monitored data point and trigger spontaneous transmission."""
    if ioa not in points:
        log.error("set_point: IOA=%d not found", ioa)
        return
    pt = points[ioa]
    pt.value = value
    pt.quality = quality
    pt.transmit(cause=c104.Cot.SPONTANEOUS)
    log.info("⬆  Transmitted IOA=%d  value=%s  quality=%s", ioa, value, quality)


# ---------------------------------------------------------------------------
# NATS subscriber – incoming messages can update monitored points
# (optional: listen on iec104.status.* to push fresh values)
# ---------------------------------------------------------------------------
async def nats_status_subscriber(
    nc: nats.aio.client.Client,
    points: dict[int, c104.Point],
) -> None:
    """
    Subscribe to aFRR.telemetry.* so external services can push new
    values for the monitored data points over NATS.

    Expected subject pattern:  aFRR.telemetry.<name>
    Expected payload:          {"value": <bool>}
    """
    name_to_ioa = {
        "SYS_STAT_PC_HEALTHY":      1000,
        "AFRR_STAT_AVAILABLE":      1001,
        "AFRR_STAT_ENABLED":        1002,
        "SYS_STAT_MAJOR_FAULT":     1003,
        "SYS_STAT_LOCAL_MODE":      1004,
        "SYS_STAT_EDGE_COMMS_OK":   1005,
        "SYS_STAT_LIMIT_ACTIVE":    1006,

        "AFRR_PWR_MEAS_TOTAL":      2000,
        "AFRR_PWR_APPLIED":         2001,
        "AFRR_CAP_UP":              2002,
        "AFRR_CAP_DOWN":            2003,
        "AFRR_ACTIVATION_LEVEL":    2004,
        
        "SYS_DIAG_LAST_ACTIVATION_RCVD": 2101,
    }

    async def handler(msg: nats.aio.client.Msg) -> None:
        try:
            parts = msg.subject.split(".")
            name  = parts[-1]
            if name not in name_to_ioa:
                log.warning("Unknown status name '%s' in subject %s", name, msg.subject)
                return
            payload = json.loads(msg.data)
            ioa     = name_to_ioa[name]
            pt      = points[ioa]

            # Value is optional – keep current if not provided
            value = payload.get("value", pt.value)

            # QDS flags – any combination of the standard IEC 104 quality bits
            # Accepts a single string or a list: "INVALID", "NON_TOPICAL", "SUBSTITUTED", "BLOCKED", "OVERFLOW"
            quality_raw = payload.get("quality", None)
            if quality_raw is None:
                quality = c104.Quality(0)  # no flags = GOOD
            elif isinstance(quality_raw, list):
                quality = c104.Quality(0)
                for q in quality_raw:
                    quality |= getattr(c104.Quality, q.capitalize())
            else:
                quality = getattr(c104.Quality, quality_raw.capitalize())

            set_point(points, ioa, value, quality)
        except Exception as exc:
            log.exception("Error handling NATS message: %s", exc)

    await nc.subscribe("aFRR.telemetry.*", cb=handler)
    log.info("NATS subscribed to aFRR.telemetry.*")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    log.info("Building IEC 104 server on %s:%d  CA=%d", IEC104_BIND_IP, IEC104_PORT, IEC104_CA)
    iec_server, points = build_server()

    log.info("Connecting to NATS at %s", NATS_URL)
    async def _on_error(e: Exception) -> None:
        log.error("NATS error: %s", e)

    async def _on_disconnected() -> None:
        log.warning("NATS disconnected")

    async def _on_reconnected() -> None:
        log.info("NATS reconnected")

    nc = await nats.connect(
        NATS_URL,
        name="iec104-bridge",
        reconnect_time_wait=2,
        max_reconnect_attempts=-1,
        error_cb=_on_error,
        disconnected_cb=_on_disconnected,
        reconnected_cb=_on_reconnected,
        tls=tls_context,
    )
    log.info("NATS connected")

    # Wire the NATS client into the sync bridge
    bridge.attach(asyncio.get_running_loop(), nc)

    # Subscribe for incoming status updates
    await nats_status_subscriber(nc, points)

    # Start the IEC 104 server (non-blocking)
    iec_server.start()
    log.info("IEC 104 server started – listening on %s:%d", IEC104_BIND_IP, IEC104_PORT)

    # Graceful shutdown on SIGTERM / SIGINT
    stop_event = asyncio.Event()

    def _shutdown(sig: signal.Signals) -> None:
        log.info("Received %s – shutting down", sig.name)
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown, sig)

    await stop_event.wait()

    log.info("Stopping IEC 104 server …")
    iec_server.stop()
    log.info("Closing NATS connection …")
    await nc.drain()
    log.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
