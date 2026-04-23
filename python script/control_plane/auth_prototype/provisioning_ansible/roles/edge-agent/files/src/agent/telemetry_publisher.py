import asyncio
import json
import os
import socket
import ssl
import struct
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


def env_int(name, default):
    value = os.getenv(name)
    if value is None or not value.strip():
        return int(default)
    return int(value)


def normalize_float_word_order(value):
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in {"low_word_first", "low_first", "lo_hi", "word_swap", "swapped"}:
        return "low_word_first"
    return "high_word_first"


def normalize_operation_mode(value):
    normalized = str(value or "simulation").strip().lower()
    aliases = {
        "sim": "simulation",
        "digital_twin": "simulation",
        "digital-twin": "simulation",
        "twin": "simulation",
        "prod": "real",
        "production": "real",
        "live": "real",
        "plant": "real",
        "lci": "real",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"simulation", "real"}:
        return "simulation"
    return normalized


MODBUS_HOST = require_env("MODBUS_HOST")
MODBUS_PORT = int(require_env("MODBUS_PORT"))
OPERATION_MODE_DEFAULT = normalize_operation_mode(os.getenv("OPERATION_MODE", "simulation"))
OPERATION_MODE_STATE_FILE = Path(
    os.getenv("OPERATION_MODE_STATE_FILE", str(BASE_DIR / "operation_mode.json"))
)
MODBUS_SIM_HOST = os.getenv("MODBUS_SIM_HOST", MODBUS_HOST)
MODBUS_SIM_PORT = env_int("MODBUS_SIM_PORT", MODBUS_PORT)
MODBUS_REAL_HOST = os.getenv("MODBUS_REAL_HOST", "192.168.1.52")
MODBUS_REAL_PORT = env_int("MODBUS_REAL_PORT", 502)
NATS_URL = require_env("NATS_URL")
NATS_TELEMETRY_SUBJECT = os.getenv(
    "NATS_TELEMETRY_SUBJECT",
    "cascadya.telemetry.live",
)
EDGE_AGENT_INSTANCE_ID = os.getenv("EDGE_AGENT_INSTANCE_ID", socket.gethostname())

REG_PLC_CLOCK_BASE = 250
REG_PLC_WATCHDOG = 256
REG_PLC_FAULT = 257
REG_PLC_FAULT_COUNT = 258
REG_PLC_ALARM = 259
REG_PLC_ALARM_COUNT = 260

REG_SIM_PRESSURE = 9000
REG_SIM_DEMAND = 9001
REG_SIM_BOILER_BASE = 9010
REG_RUNTIME_BASE = 9070
REG_RUNTIME_WORDS = 5
REG_SIM_PROCESS_OFFSET = env_int("MODBUS_SIM_PROCESS_OFFSET", 9200)

REG_REAL_PRESSURE_BASE = env_int("MODBUS_REAL_PRESSURE_BASE", 388)
REG_REAL_PRESSURE_ERROR = env_int("MODBUS_REAL_PRESSURE_ERROR", 390)
REG_REAL_PRESSURE_PERCENT = env_int("MODBUS_REAL_PRESSURE_PERCENT", 392)
REG_REAL_DEMAND_BASE = env_int("MODBUS_REAL_DEMAND_BASE", 512)
REG_REAL_PRESSURE_REGULATION_BASE = env_int("MODBUS_REAL_PRESSURE_REGULATION_BASE", 508)
REG_REAL_PRESSURE_SETPOINT = env_int("MODBUS_REAL_PRESSURE_SETPOINT", 514)
REG_REAL_PRESSURE_BOOST = env_int("MODBUS_REAL_PRESSURE_BOOST", 516)
REG_REAL_HEATER_FEEDBACK_BASE = env_int("MODBUS_REAL_HEATER_FEEDBACK_BASE", 574)
REG_REAL_HEATER_FEEDBACK_ERROR = env_int("MODBUS_REAL_HEATER_FEEDBACK_ERROR", 576)
FLOAT_WORD_ORDER = normalize_float_word_order(os.getenv("MODBUS_FLOAT_WORD_ORDER", "low_word_first"))
U32_WORD_ORDER = normalize_float_word_order(
    os.getenv("MODBUS_U32_WORD_ORDER", os.getenv("MODBUS_WORD_ORDER", "low_word_first"))
)

STRATEGY_MAP = {
    0: "NONE",
    1: "C1",
    2: "C2",
    3: "C3",
}


def words_to_float(first_word, second_word):
    if FLOAT_WORD_ORDER == "low_word_first":
        high_word, low_word = second_word, first_word
    else:
        high_word, low_word = first_word, second_word
    raw = ((int(high_word) & 0xFFFF) << 16) | (int(low_word) & 0xFFFF)
    return struct.unpack(">f", struct.pack(">I", raw))[0]


def words_to_u32(first_word, second_word):
    if U32_WORD_ORDER == "low_word_first":
        high_word, low_word = second_word, first_word
    else:
        high_word, low_word = first_word, second_word
    return ((int(high_word) & 0xFFFF) << 16) | (int(low_word) & 0xFFFF)


def word_bit(word, bit):
    return bool((int(word) & 0xFFFF) & (1 << int(bit)))


def sim_process_reg(real_register):
    return REG_SIM_PROCESS_OFFSET + int(real_register)


def load_operation_mode_state(default_mode):
    try:
        if OPERATION_MODE_STATE_FILE.exists():
            payload = json.loads(OPERATION_MODE_STATE_FILE.read_text(encoding="utf-8"))
            return normalize_operation_mode(payload.get("mode", default_mode))
    except Exception as exc:
        print(f"[TELEMETRY] operation mode state ignored: {exc}")
    return normalize_operation_mode(default_mode)


def mode_config(mode):
    selected_mode = normalize_operation_mode(mode)
    if selected_mode == "real":
        return {
            "mode": "real",
            "host": MODBUS_REAL_HOST,
            "port": MODBUS_REAL_PORT,
            "telemetry_profile": "real_lci",
        }
    return {
        "mode": "simulation",
        "host": MODBUS_SIM_HOST,
        "port": MODBUS_SIM_PORT,
        "telemetry_profile": "digital_twin",
    }


def read_modbus_telemetry(client, operation_mode):
    try:
        selected_mode = normalize_operation_mode(operation_mode)
        res_clock = client.read_holding_registers(REG_PLC_CLOCK_BASE, count=6)
        res_watchdog = client.read_holding_registers(REG_PLC_WATCHDOG, count=1)
        res_runtime = client.read_holding_registers(REG_RUNTIME_BASE, count=REG_RUNTIME_WORDS)

        clock_words = [0, 0, 0, 0, 0, 0] if res_clock.isError() else res_clock.registers
        watchdog_value = -1 if res_watchdog.isError() else res_watchdog.registers[0]

        if selected_mode == "real":
            res_plc_health = client.read_holding_registers(REG_PLC_FAULT, count=4)
            res_pressure = client.read_holding_registers(REG_REAL_PRESSURE_BASE, count=2)
            res_pressure_error = client.read_holding_registers(REG_REAL_PRESSURE_ERROR, count=1)
            res_pressure_percent = client.read_holding_registers(REG_REAL_PRESSURE_PERCENT, count=2)
            res_demand = client.read_holding_registers(REG_REAL_DEMAND_BASE, count=2)
            res_pressure_regulation = client.read_holding_registers(REG_REAL_PRESSURE_REGULATION_BASE, count=9)
            res_heater_feedback = client.read_holding_registers(REG_REAL_HEATER_FEEDBACK_BASE, count=3)
            plc_health_words = [0, 0, 0, 0] if res_plc_health.isError() else res_plc_health.registers
            pressure_words = [0, 0] if res_pressure.isError() else res_pressure.registers
            pressure_error_word = 0 if res_pressure_error.isError() else res_pressure_error.registers[0]
            pressure_percent_words = [0, 0] if res_pressure_percent.isError() else res_pressure_percent.registers
            demand_words = [0, 0] if res_demand.isError() else res_demand.registers
            pressure_regulation_words = (
                [0] * 9 if res_pressure_regulation.isError() else res_pressure_regulation.registers
            )
            heater_feedback_words = [0, 0, 0] if res_heater_feedback.isError() else res_heater_feedback.registers
            pressure = round(words_to_float(pressure_words[0], pressure_words[1]), 3)
            demand_kw = round(words_to_float(demand_words[0], demand_words[1]), 3)
            pressure_percent = round(words_to_float(pressure_percent_words[0], pressure_percent_words[1]), 3)
            setpoint_bar = round(words_to_float(pressure_regulation_words[6], pressure_regulation_words[7]), 3)
            heater_feedback_pct = round(words_to_float(heater_feedback_words[0], heater_feedback_words[1]), 3)
            regulation_mode = "disabled"
            if word_bit(pressure_regulation_words[1], 8):
                regulation_mode = "auto"
            elif word_bit(pressure_regulation_words[2], 0):
                regulation_mode = "manual"
            elif not word_bit(pressure_regulation_words[2], 8):
                regulation_mode = "unknown"
            demand_label = "RP08_CHARGE"
            demand_unit = "%"
            pressure_label = "PT01_MESURE"
            pressure_register_label = f"%MW{REG_REAL_PRESSURE_BASE}"
            demand_register_label = f"%MW{REG_REAL_DEMAND_BASE}"
            b1_state, b1_load, b1_target = (0, 0, 0)
            b2_state, b2_load, b2_target = (0, 0, 0)
            b3_state, b3_load, b3_target = (0, 0, 0)
        else:
            res_pressure = client.read_holding_registers(REG_SIM_PRESSURE, count=1)
            res_demand = client.read_holding_registers(REG_SIM_DEMAND, count=1)
            res_plc_health = client.read_holding_registers(sim_process_reg(REG_PLC_FAULT), count=4)
            res_process_pressure = client.read_holding_registers(sim_process_reg(REG_REAL_PRESSURE_BASE), count=2)
            res_pressure_error = client.read_holding_registers(sim_process_reg(REG_REAL_PRESSURE_ERROR), count=1)
            res_pressure_percent = client.read_holding_registers(sim_process_reg(REG_REAL_PRESSURE_PERCENT), count=2)
            res_process_demand = client.read_holding_registers(sim_process_reg(REG_REAL_DEMAND_BASE), count=2)
            res_pressure_regulation = client.read_holding_registers(
                sim_process_reg(REG_REAL_PRESSURE_REGULATION_BASE),
                count=9,
            )
            res_heater_feedback = client.read_holding_registers(
                sim_process_reg(REG_REAL_HEATER_FEEDBACK_BASE),
                count=3,
            )
            res_b1 = client.read_holding_registers(REG_SIM_BOILER_BASE, count=3)
            res_b2 = client.read_holding_registers(REG_SIM_BOILER_BASE + 10, count=3)
            res_b3 = client.read_holding_registers(REG_SIM_BOILER_BASE + 20, count=3)
            pressure_words = [0, 0] if res_process_pressure.isError() else res_process_pressure.registers
            pressure = (
                round(words_to_float(pressure_words[0], pressure_words[1]), 3)
                if pressure_words != [0, 0]
                else (res_pressure.registers[0] / 10.0 if not res_pressure.isError() else 0.0)
            )
            demand_kw = res_demand.registers[0] if not res_demand.isError() else 0
            demand_label = "Factory Demand"
            demand_unit = "kW"
            pressure_label = "PT01_MESURE simulated mirror"
            pressure_register_label = f"%MW{sim_process_reg(REG_REAL_PRESSURE_BASE)}"
            demand_register_label = f"%MW{REG_SIM_DEMAND}"
            plc_health_words = [0, 0, 0, 0] if res_plc_health.isError() else res_plc_health.registers
            pressure_error_word = 0 if res_pressure_error.isError() else res_pressure_error.registers[0]
            pressure_percent_words = [0, 0] if res_pressure_percent.isError() else res_pressure_percent.registers
            pressure_percent = round(words_to_float(pressure_percent_words[0], pressure_percent_words[1]), 3)
            process_demand_words = [0, 0] if res_process_demand.isError() else res_process_demand.registers
            pressure_regulation_words = (
                [0] * 9 if res_pressure_regulation.isError() else res_pressure_regulation.registers
            )
            heater_feedback_words = [0, 0, 0] if res_heater_feedback.isError() else res_heater_feedback.registers
            process_load_pct = round(words_to_float(process_demand_words[0], process_demand_words[1]), 3)
            setpoint_bar = round(words_to_float(pressure_regulation_words[6], pressure_regulation_words[7]), 3)
            heater_feedback_pct = round(words_to_float(heater_feedback_words[0], heater_feedback_words[1]), 3)
            regulation_mode = "disabled"
            if word_bit(pressure_regulation_words[1], 8):
                regulation_mode = "auto"
            elif word_bit(pressure_regulation_words[2], 0):
                regulation_mode = "manual"
            elif not word_bit(pressure_regulation_words[2], 8):
                regulation_mode = "unknown"
            b1_state, b1_load, b1_target = (0, 0, 0) if res_b1.isError() else res_b1.registers
            b2_state, b2_load, b2_target = (0, 0, 0) if res_b2.isError() else res_b2.registers
            b3_state, b3_load, b3_target = (0, 0, 0) if res_b3.isError() else res_b3.registers

        runtime_words = [0] * REG_RUNTIME_WORDS if res_runtime.isError() else res_runtime.registers
        active_strategy_code = runtime_words[0]
        active_order = words_to_u32(runtime_words[1], runtime_words[2])
        target_pressure_bar = runtime_words[3] / 10.0
        active_stages = runtime_words[4]
        if selected_mode == "real":
            active_strategy_code = 0
            active_order = 0
            target_pressure_bar = setpoint_bar
            active_stages = 1 if word_bit(pressure_regulation_words[0], 0) else 0

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation_mode": selected_mode,
            "telemetry_profile": mode_config(selected_mode)["telemetry_profile"],
            "plc_clock": {
                "year": clock_words[0],
                "month": clock_words[1],
                "day": clock_words[2],
                "hour": clock_words[3],
                "minute": clock_words[4],
                "second": clock_words[5],
            },
            "plc_watchdog": watchdog_value,
            "pressure_bar": pressure,
            "pressure_label": pressure_label,
            "pressure_register_label": pressure_register_label,
            "demand_kw": demand_kw,
            "load_pct": demand_kw if selected_mode == "real" else locals().get("process_load_pct"),
            "demand_label": demand_label,
            "demand_unit": demand_unit,
            "demand_register_label": demand_register_label,
            "plc_health": {
                "fault": word_bit(plc_health_words[0], 0),
                "fault_count": int(plc_health_words[1]),
                "alarm": word_bit(plc_health_words[2], 0),
                "alarm_count": int(plc_health_words[3]),
                "registers": {
                    "fault": (
                        f"%MW{REG_PLC_FAULT}.0"
                        if selected_mode == "real"
                        else f"%MW{sim_process_reg(REG_PLC_FAULT)}.0 -> real %MW{REG_PLC_FAULT}.0"
                    ),
                    "fault_count": (
                        f"%MW{REG_PLC_FAULT_COUNT}"
                        if selected_mode == "real"
                        else f"%MW{sim_process_reg(REG_PLC_FAULT_COUNT)} -> real %MW{REG_PLC_FAULT_COUNT}"
                    ),
                    "alarm": (
                        f"%MW{REG_PLC_ALARM}.0"
                        if selected_mode == "real"
                        else f"%MW{sim_process_reg(REG_PLC_ALARM)}.0 -> real %MW{REG_PLC_ALARM}.0"
                    ),
                    "alarm_count": (
                        f"%MW{REG_PLC_ALARM_COUNT}"
                        if selected_mode == "real"
                        else f"%MW{sim_process_reg(REG_PLC_ALARM_COUNT)} -> real %MW{REG_PLC_ALARM_COUNT}"
                    ),
                },
            },
            "pressure_sensor": {
                "error": word_bit(pressure_error_word, 0),
                "error_register_label": (
                    f"%MW{REG_REAL_PRESSURE_ERROR}.0"
                    if selected_mode == "real"
                    else f"%MW{sim_process_reg(REG_REAL_PRESSURE_ERROR)}.0"
                ),
                "percent": pressure_percent,
                "percent_register_label": (
                    f"%MW{REG_REAL_PRESSURE_PERCENT}"
                    if selected_mode == "real"
                    else f"%MW{sim_process_reg(REG_REAL_PRESSURE_PERCENT)}"
                ),
            },
            "pressure_regulation": {
                "thermo_running": word_bit(pressure_regulation_words[0], 0),
                "mini_technique": word_bit(pressure_regulation_words[0], 8),
                "limiter_position": word_bit(pressure_regulation_words[1], 0),
                "mode": regulation_mode,
                "mode_auto": word_bit(pressure_regulation_words[1], 8),
                "mode_manual": word_bit(pressure_regulation_words[2], 0),
                "mode_disabled": word_bit(pressure_regulation_words[2], 8),
                "load_pct": demand_kw if selected_mode == "real" else locals().get("process_load_pct", 0),
                "load_register_label": (
                    f"%MW{REG_REAL_DEMAND_BASE}"
                    if selected_mode == "real"
                    else f"%MW{sim_process_reg(REG_REAL_DEMAND_BASE)}"
                ),
                "setpoint_bar": setpoint_bar,
                "setpoint_register_label": (
                    f"%MW{REG_REAL_PRESSURE_SETPOINT}"
                    if selected_mode == "real"
                    else f"%MW{sim_process_reg(REG_REAL_PRESSURE_SETPOINT)}"
                ),
                "boost": word_bit(pressure_regulation_words[8], 0),
                "boost_register_label": (
                    f"%MW{REG_REAL_PRESSURE_BOOST}.0"
                    if selected_mode == "real"
                    else f"%MW{sim_process_reg(REG_REAL_PRESSURE_BOOST)}.0"
                ),
            },
            "heater_feedback": {
                "load_pct": heater_feedback_pct,
                "load_register_label": (
                    f"%MW{REG_REAL_HEATER_FEEDBACK_BASE}"
                    if selected_mode == "real"
                    else f"%MW{sim_process_reg(REG_REAL_HEATER_FEEDBACK_BASE)}"
                ),
                "error": word_bit(heater_feedback_words[2], 0),
                "error_register_label": (
                    f"%MW{REG_REAL_HEATER_FEEDBACK_ERROR}.0"
                    if selected_mode == "real"
                    else f"%MW{sim_process_reg(REG_REAL_HEATER_FEEDBACK_ERROR)}.0"
                ),
            },
            "active_order": active_order,
            "active_order_id": active_order,
            "active_strategy_code": active_strategy_code,
            "active_strategy": STRATEGY_MAP.get(active_strategy_code, "UNKNOWN"),
            "target_pressure_bar": target_pressure_bar,
            "active_stages": active_stages,
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
    tls_ctx = build_tls_context()
    nc = None
    modbus_client = None
    active_mode = None
    active_target = None

    try:
        print(f"[TELEMETRY] Connecting NATS {NATS_URL}")
        nc = await nats.connect(
            NATS_URL,
            tls=tls_ctx,
            connect_timeout=20,
            name=f"telemetry_publisher_edge:{EDGE_AGENT_INSTANCE_ID}",
        )
        print("[TELEMETRY] Publishing live telemetry.")

        while True:
            requested_mode = load_operation_mode_state(OPERATION_MODE_DEFAULT)
            config = mode_config(requested_mode)
            requested_target = (config["host"], config["port"])

            if (
                modbus_client is None
                or not modbus_client.connected
                or active_mode != config["mode"]
                or active_target != requested_target
            ):
                if modbus_client is not None:
                    modbus_client.close()
                active_mode = config["mode"]
                active_target = requested_target
                print(
                    "[TELEMETRY] Connecting Modbus "
                    f"mode={active_mode} target={config['host']}:{config['port']}"
                )
                modbus_client = ModbusTcpClient(config["host"], port=config["port"])
                if not modbus_client.connect():
                    print("[TELEMETRY] Modbus connection failed; retrying.")
                    await asyncio.sleep(2)
                    continue

            data = read_modbus_telemetry(modbus_client, active_mode)
            if data:
                payload = json.dumps(data).encode("utf-8")
                await nc.publish(NATS_TELEMETRY_SUBJECT, payload)
                print(
                    "[TELEMETRY] "
                    f"{datetime.now().strftime('%H:%M:%S')} mode={active_mode} "
                    f"pressure={data['pressure_bar']} bar"
                )
            await asyncio.sleep(1)
    except Exception as exc:
        print(f"[TELEMETRY] Runtime failure: {exc}")
    finally:
        if modbus_client is not None:
            modbus_client.close()
        if nc is not None:
            await nc.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[TELEMETRY] Stopped.")
