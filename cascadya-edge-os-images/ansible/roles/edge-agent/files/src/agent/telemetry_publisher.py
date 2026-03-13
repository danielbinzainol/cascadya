import asyncio
import json
import os
import ssl
from datetime import datetime, timezone
from pathlib import Path

import nats
from pymodbus.client import ModbusTcpClient


BASE_DIR = Path(__file__).resolve().parent
CERTS_DIR = Path(os.getenv("EDGE_AGENT_CERTS_DIR", str(BASE_DIR / "certs")))

CA_CERT = str(CERTS_DIR / "ca.crt")
CLIENT_CERT = str(CERTS_DIR / "client.crt")
CLIENT_KEY = str(CERTS_DIR / "client.key")


def require_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


MODBUS_HOST = require_env("MODBUS_HOST")
MODBUS_PORT = int(require_env("MODBUS_PORT"))
NATS_URL = require_env("NATS_URL")
NATS_TELEMETRY_SUBJECT = os.getenv(
    "NATS_TELEMETRY_SUBJECT",
    "cascadya.telemetry.live",
)


def read_modbus_telemetry(client):
    try:
        res_pressure = client.read_holding_registers(400, count=1)
        res_demand = client.read_holding_registers(500, count=1)
        res_order = client.read_holding_registers(100, count=1)
        res_b1 = client.read_holding_registers(410, count=3)
        res_b2 = client.read_holding_registers(420, count=3)
        res_b3 = client.read_holding_registers(430, count=3)

        pressure = res_pressure.registers[0] / 10.0 if not res_pressure.isError() else 0.0
        demand_kw = res_demand.registers[0] if not res_demand.isError() else 0
        active_order = res_order.registers[0] if not res_order.isError() else 0

        b1_state, b1_load, b1_target = (0, 0, 0) if res_b1.isError() else res_b1.registers
        b2_state, b2_load, b2_target = (0, 0, 0) if res_b2.isError() else res_b2.registers
        b3_state, b3_load, b3_target = (0, 0, 0) if res_b3.isError() else res_b3.registers

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pressure_bar": pressure,
            "demand_kw": demand_kw,
            "active_order": active_order,
            "ibc1": {"state": b1_state, "load_pct": b1_load, "target_pct": b1_target},
            "ibc2": {"state": b2_state, "load_pct": b2_load, "target_pct": b2_target},
            "ibc3": {"state": b3_state, "load_pct": b3_load, "target_pct": b3_target},
        }
    except Exception as exc:
        print(f"[TELEMETRY] Modbus read failed: {exc}")
        return None


def build_tls_context():
    tls_ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=CA_CERT)
    tls_ctx.load_cert_chain(certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
    tls_ctx.check_hostname = False
    tls_ctx.verify_mode = ssl.CERT_REQUIRED
    return tls_ctx


async def main():
    print(f"[TELEMETRY] Connecting Modbus {MODBUS_HOST}:{MODBUS_PORT}")
    modbus_client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)
    if not modbus_client.connect():
        print("[TELEMETRY] Modbus connection failed.")
        return

    tls_ctx = build_tls_context()
    nc = None

    try:
        print(f"[TELEMETRY] Connecting NATS {NATS_URL}")
        nc = await nats.connect(
            NATS_URL,
            tls=tls_ctx,
            connect_timeout=20,
            name="telemetry_publisher_edge",
        )
        print("[TELEMETRY] Publishing live telemetry.")

        while True:
            data = read_modbus_telemetry(modbus_client)
            if data:
                payload = json.dumps(data).encode("utf-8")
                await nc.publish(NATS_TELEMETRY_SUBJECT, payload)
                print(
                    "[TELEMETRY] "
                    f"{datetime.now().strftime('%H:%M:%S')} pressure={data['pressure_bar']} bar"
                )
            await asyncio.sleep(1)
    except Exception as exc:
        print(f"[TELEMETRY] Runtime failure: {exc}")
    finally:
        modbus_client.close()
        if nc is not None:
            await nc.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[TELEMETRY] Stopped.")
