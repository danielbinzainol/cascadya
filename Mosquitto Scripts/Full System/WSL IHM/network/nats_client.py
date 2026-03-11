import json
import os
import ssl
import time

from nats.aio.client import Client as NATS

from config import settings


class AsyncNatsClient:
    def __init__(self):
        self.nc = NATS()
        self.tls_context = None

    def _build_tls_context(self):
        """Build TLS context only when connect is called to avoid startup hard-crash."""
        missing = [
            path
            for path in (settings.CA_CERT, settings.CLIENT_CERT, settings.CLIENT_KEY)
            if not os.path.exists(path)
        ]
        if missing:
            raise FileNotFoundError(
                "Missing TLS files: "
                + ", ".join(missing)
                + ". You can set STEAMSWITCH_CERTS_DIR or STEAMSWITCH_CA_CERT/STEAMSWITCH_CLIENT_CERT/STEAMSWITCH_CLIENT_KEY."
            )

        context = ssl.create_default_context(cafile=settings.CA_CERT)
        context.load_cert_chain(certfile=settings.CLIENT_CERT, keyfile=settings.CLIENT_KEY)
        context.check_hostname = False
        return context

    async def connect(self):
        """Connect to the NATS broker."""
        try:
            self.tls_context = self._build_tls_context()
            await self.nc.connect(settings.NATS_URL, tls=self.tls_context)
            print("[IHM] NATS connected")
            return True
        except Exception as exc:
            print(f"[IHM] NATS connection error: {exc}")
            return False

    async def disconnect(self):
        """Close NATS connection gracefully."""
        if self.nc.is_connected:
            await self.nc.drain()
            print("[IHM] NATS disconnected")

    async def ping_watchdog(self, value):
        """Round-trip test on ping topic."""
        payload = json.dumps({"compteur": value}).encode()
        start_time = time.perf_counter()

        try:
            msg = await self.nc.request(settings.TOPIC_PING, payload, timeout=2.0)
            end_time = time.perf_counter()
            rtt_ms = (end_time - start_time) * 1000

            data = json.loads(msg.data.decode())
            data["rtt_ms"] = rtt_ms
            return data
        except Exception as exc:
            return {"status": "error", "message": str(exc), "rtt_ms": 0.0}

    async def send_command(self, payload_dict):
        """Send a planification command and wait for gateway acknowledgment."""
        payload = json.dumps(payload_dict).encode()

        try:
            msg = await self.nc.request(settings.TOPIC_COMMAND, payload, timeout=settings.COMMAND_TIMEOUT_SEC)
            return json.loads(msg.data.decode())
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
