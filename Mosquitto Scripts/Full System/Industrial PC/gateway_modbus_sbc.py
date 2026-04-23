import asyncio
import json
import ssl
import time
from datetime import datetime
from pathlib import Path

from nats.aio.client import Client as NATS
from pymodbus.client import AsyncModbusTcpClient


BASE_DIR = Path(__file__).resolve().parent
CERTS_DIR = BASE_DIR / "certs"

CA_CERT = str(CERTS_DIR / "ca.crt")
CLIENT_CERT = str(CERTS_DIR / "client.crt")
CLIENT_KEY = str(CERTS_DIR / "client.key")

NATS_URL = "tls://100.103.71.126:4222"
TOPIC_PING = "cascadya.routing.ping"
TOPIC_CMD = "cascadya.routing.command"

MODBUS_IP = "192.168.50.2"
MODBUS_PORT = 502

REG_PREP_BASE = 0
REG_ENVOI_BIT = 50
REG_ENVOI_STATUS = 51
REG_DELETE_BIT = 60
REG_DELETE_STATUS = 61
REG_RESET_BIT = 62
REG_RESET_STATUS = 63

REG_SBC_SEC = 607
REG_WD_SS = 620

ACK_TIMEOUT_SEC = 4.0
POLL_INTERVAL_SEC = 0.1

STATUS_TEXT = {
    0: "ok",
    1: "queue_full",
    2: "invalid_datetime",
    3: "unknown_attribute",
    4: "order_not_found",
    98: "timeout_waiting_ack",
    99: "modbus_io_error",
}


class SteamSwitchGateway:
    def __init__(self):
        self.nc = NATS()
        self.modbus = None
        self.wd_counter = 0
        self.last_sbc_sec = -1
        self.last_sbc_change = time.time()

    async def run_watchdog_ss(self):
        """1Hz heartbeat written by SteamSwitch into %MW620."""
        while True:
            if self.modbus and self.modbus.connected:
                try:
                    self.wd_counter = (self.wd_counter + 1) % 32767
                    await self.modbus.write_register(address=REG_WD_SS, value=self.wd_counter)
                except Exception as exc:
                    print(f"[GATEWAY] Watchdog write error: {exc}")
            await asyncio.sleep(1)

    async def monitor_sbc_clock(self):
        """Raise alert if %MW607 does not change for >30s."""
        while True:
            if self.modbus and self.modbus.connected:
                try:
                    res = await self.modbus.read_holding_registers(address=REG_SBC_SEC, count=1)
                    if not res.isError():
                        current_sec = res.registers[0]
                        if current_sec != self.last_sbc_sec:
                            self.last_sbc_sec = current_sec
                            self.last_sbc_change = time.time()
                        elif time.time() - self.last_sbc_change > 30:
                            print("[GATEWAY] ALERT: SBC clock frozen on %MW607 (>30s).")
                except Exception as exc:
                    print(f"[GATEWAY] SBC clock read error: {exc}")
            await asyncio.sleep(1)

    async def handle_command(self, msg):
        """Handle upsert/delete/reset commands and send status ack reply."""
        try:
            payload = json.loads(msg.data.decode())
        except Exception as exc:
            result = {"status": "error", "message": f"invalid_json: {exc}"}
            await self._safe_reply(msg.reply, result)
            return

        if not self.modbus or not self.modbus.connected:
            result = {"status": "error", "message": "modbus_not_connected"}
            await self._safe_reply(msg.reply, result)
            return

        action = str(payload.get("action", "upsert")).lower().strip()

        try:
            if action in {"upsert", "add", "modify"}:
                result = await self._handle_upsert(payload)
            elif action == "delete":
                result = await self._handle_delete(payload)
            elif action in {"reset", "clear"}:
                result = await self._handle_reset()
            else:
                result = {"status": "error", "message": f"unsupported_action:{action}"}
        except Exception as exc:
            result = {"status": "error", "message": str(exc)}

        await self._safe_reply(msg.reply, result)

    async def _handle_upsert(self, payload):
        order_id = int(payload.get("id", int(time.time())))
        execute_at = self._parse_execute_at(payload)

        c1 = self._normalize_consigne(payload.get("c1", [1, 400, 53]))
        c2 = self._normalize_consigne(payload.get("c2", [2, 1000, 53]))
        c3 = self._normalize_consigne(payload.get("c3", [3, 1000, 53]))

        block = [
            (order_id >> 16) & 0xFFFF,
            order_id & 0xFFFF,
            execute_at.day,
            execute_at.month,
            execute_at.year,
            execute_at.hour,
            execute_at.minute,
            execute_at.second,
            *c1,
            *c2,
            *c3,
        ]

        await self.modbus.write_registers(address=REG_PREP_BASE, values=block)
        code = await self._commit_action(REG_ENVOI_BIT, REG_ENVOI_STATUS)

        return {
            "status": "ok" if code == 0 else "error",
            "action": "upsert",
            "order_id": order_id,
            "execute_at": execute_at.strftime("%Y-%m-%d %H:%M:%S"),
            "status_code": code,
            "status_text": STATUS_TEXT.get(code, "unknown_status"),
        }

    async def _handle_delete(self, payload):
        if "id" not in payload:
            return {"status": "error", "action": "delete", "message": "missing_id"}

        order_id = int(payload["id"])
        id_words = [(order_id >> 16) & 0xFFFF, order_id & 0xFFFF]

        await self.modbus.write_registers(address=REG_PREP_BASE, values=id_words)
        code = await self._commit_action(REG_DELETE_BIT, REG_DELETE_STATUS)

        return {
            "status": "ok" if code == 0 else "error",
            "action": "delete",
            "order_id": order_id,
            "status_code": code,
            "status_text": STATUS_TEXT.get(code, "unknown_status"),
        }

    async def _handle_reset(self):
        code = await self._commit_action(REG_RESET_BIT, REG_RESET_STATUS)
        return {
            "status": "ok" if code == 0 else "error",
            "action": "reset",
            "status_code": code,
            "status_text": STATUS_TEXT.get(code, "unknown_status"),
        }

    async def _commit_action(self, bit_reg, status_reg):
        try:
            await self.modbus.write_register(address=bit_reg, value=1)

            deadline = time.monotonic() + ACK_TIMEOUT_SEC
            while time.monotonic() < deadline:
                bit_res = await self.modbus.read_holding_registers(address=bit_reg, count=1)
                if not bit_res.isError() and bit_res.registers[0] == 0:
                    break
                await asyncio.sleep(POLL_INTERVAL_SEC)
            else:
                return 98

            status_res = await self.modbus.read_holding_registers(address=status_reg, count=1)
            if status_res.isError():
                return 99
            return int(status_res.registers[0])

        except Exception as exc:
            print(f"[GATEWAY] commit action error bit={bit_reg} status={status_reg}: {exc}")
            return 99

    def _parse_execute_at(self, payload):
        raw = payload.get("execute_at")
        if isinstance(raw, str) and raw.strip():
            value = raw.strip()
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")

            if dt.tzinfo is not None:
                dt = dt.astimezone().replace(tzinfo=None)
            return dt

        dt_fields = payload.get("datetime")
        if isinstance(dt_fields, dict):
            return datetime(
                int(dt_fields["year"]),
                int(dt_fields["month"]),
                int(dt_fields["day"]),
                int(dt_fields.get("hour", 0)),
                int(dt_fields.get("minute", 0)),
                int(dt_fields.get("second", 0)),
            )

        return datetime.now()

    def _normalize_consigne(self, values):
        if not isinstance(values, list) or len(values) != 3:
            raise ValueError(f"consigne must be a list of 3 INT words, got {values}")

        normalized = []
        for value in values:
            intval = int(value)
            if intval < 0 or intval > 65535:
                raise ValueError(f"invalid Modbus word value: {intval}")
            normalized.append(intval)

        return normalized

    async def _safe_reply(self, reply_subject, payload):
        if reply_subject:
            await self.nc.publish(reply_subject, json.dumps(payload).encode())
        print(f"[GATEWAY] command result: {payload}")

    async def ping_handler(self, msg):
        """Quick RTT diagnostic for IHM."""
        if not self.modbus or not self.modbus.connected:
            await self.nc.publish(msg.reply, json.dumps({"status": "error", "message": "modbus_not_connected"}).encode())
            return

        try:
            data = json.loads(msg.data.decode())
            value = int(data.get("compteur", 0))
            await self.modbus.write_register(address=REG_WD_SS, value=value)
            result = await self.modbus.read_holding_registers(address=REG_WD_SS, count=1)
            value_read = result.registers[0] if not result.isError() else -1

            await self.nc.publish(
                msg.reply,
                json.dumps({"status": "ok", "valeur_retour": value_read}).encode(),
            )
        except Exception as exc:
            await self.nc.publish(msg.reply, json.dumps({"status": "error", "message": str(exc)}).encode())

    async def start(self):
        self.modbus = AsyncModbusTcpClient(MODBUS_IP, port=MODBUS_PORT)

        tls_ctx = ssl.create_default_context(cafile=CA_CERT)
        tls_ctx.load_cert_chain(CLIENT_CERT, CLIENT_KEY)
        tls_ctx.check_hostname = False

        print(f"[GATEWAY] Connecting Modbus ({MODBUS_IP}:{MODBUS_PORT})...")
        await self.modbus.connect()

        print(f"[GATEWAY] Connecting NATS TLS ({NATS_URL})...")
        await self.nc.connect(NATS_URL, tls=tls_ctx)

        await self.nc.subscribe(TOPIC_PING, cb=self.ping_handler)
        await self.nc.subscribe(TOPIC_CMD, cb=self.handle_command)

        print("[GATEWAY] SteamSwitch gateway is running.")

        await asyncio.gather(
            self.run_watchdog_ss(),
            self.monitor_sbc_clock(),
        )


if __name__ == "__main__":
    gateway = SteamSwitchGateway()
    try:
        asyncio.run(gateway.start())
    except KeyboardInterrupt:
        print("\n[GATEWAY] Stopped by user.")
