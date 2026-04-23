import asyncio
import inspect
import json
import os
import socket
import ssl
import struct
import time
from datetime import datetime, timezone
from pathlib import Path

from nats.aio.client import Client as NATS
from pymodbus.client import AsyncModbusTcpClient


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


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


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
        raise ValueError(f"invalid_operation_mode:{value}")
    return normalized


NATS_URL = require_env("NATS_URL")
TOPIC_PING = os.getenv("NATS_PING_SUBJECT", "cascadya.routing.ping")
TOPIC_CMD = os.getenv("NATS_COMMAND_SUBJECT", "cascadya.routing.command")
EDGE_AGENT_INSTANCE_ID = os.getenv("EDGE_AGENT_INSTANCE_ID", socket.gethostname())
COMMAND_TARGET_FIELDS = ("asset_name", "target_asset", "edge_instance_id", "inventory_hostname")

MODBUS_HOST = require_env("MODBUS_HOST")
MODBUS_PORT = int(require_env("MODBUS_PORT"))
OPERATION_MODE_DEFAULT = normalize_operation_mode(os.getenv("OPERATION_MODE", "simulation"))
OPERATION_MODE_STATE_FILE = Path(
    os.getenv("OPERATION_MODE_STATE_FILE", str(BASE_DIR / "operation_mode.json"))
)
OPERATION_MODE_REAL_CONFIRMATION = os.getenv("OPERATION_MODE_REAL_CONFIRMATION", "LCI LIVE")

MODBUS_SIM_HOST = os.getenv("MODBUS_SIM_HOST", MODBUS_HOST)
MODBUS_SIM_PORT = env_int("MODBUS_SIM_PORT", MODBUS_PORT)
MODBUS_REAL_HOST = os.getenv("MODBUS_REAL_HOST", "192.168.1.52")
MODBUS_REAL_PORT = env_int("MODBUS_REAL_PORT", 502)

WATCHDOG_FREEZE_THRESHOLD_SEC = float(os.getenv("WATCHDOG_FREEZE_THRESHOLD_SEC", "30"))
WATCHDOG_STRICT_SIMULATION = env_bool("WATCHDOG_STRICT_SIMULATION", False)
WATCHDOG_STRICT_REAL = env_bool("WATCHDOG_STRICT_REAL", True)

# Rev02 official register contract from Table d'echange concept Rev 02 (2026-04-15).
REG_PLC_YEAR = 250
REG_PLC_MONTH = 251
REG_PLC_DAY = 252
REG_PLC_HOUR = 253
REG_PLC_MINUTE = 254
REG_PLC_SECOND = 255
REG_PLC_WATCHDOG = 256
REG_PLC_FAULT = 257
REG_PLC_FAULT_COUNT = 258
REG_PLC_ALARM = 259
REG_PLC_ALARM_COUNT = 260

REG_DT_WRITE_BASE = 600
REG_PREP_BASE = 1000
PREP_WORDS = 44

REG_ADD_TRIGGER = 1044
REG_ADD_STATUS = 1045
REG_DELETE_TRIGGER = 1056
REG_DELETE_STATUS = 1057
REG_RESET_TRIGGER = 1068
REG_RESET_STATUS = 1069

REG_PLANNER_STATE = 8100
REG_PLANNER_CRC = 8101
REG_PLANNER_CRC_STATE = 8102
REG_QUEUE_BASE = 8120
QUEUE_SLOT_STRIDE = 46
QUEUE_SLOT_WORDS = 46
QUEUE_MAX_ORDERS = 10
REG_QUEUE_REGISTER_CHECK_END = 8578

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

ACK_TIMEOUT_SEC = 4.0
POLL_INTERVAL_SEC = 0.1

STATUS_TEXT = {
    0: "ok",
    1: "queue_full",
    2: "invalid_year",
    3: "invalid_month",
    4: "invalid_day_check",
    5: "invalid_day",
    6: "datetime_before_plc_date",
    7: "time_before_current_time_today",
    8: "multiple_triggers",
    20: "invalid_id",
    21: "order_not_found",
    98: "timeout_waiting_ack",
    99: "modbus_io_error",
    100: "delete_c1_not_zero",
    110: "invalid_c1_1",
    120: "invalid_c1_2",
    130: "invalid_c1_3",
    140: "invalid_c1_4",
    150: "invalid_c1_5",
    160: "invalid_c1_6",
    200: "delete_c2_not_zero",
    210: "invalid_c2_1",
    220: "invalid_c2_2",
    230: "invalid_c2_3",
    240: "invalid_c2_4",
    250: "invalid_c2_5",
    260: "invalid_c2_6",
    300: "delete_c3_not_zero",
    310: "invalid_c3_1",
    320: "invalid_c3_2",
    330: "invalid_c3_3",
    340: "invalid_c3_4",
    350: "invalid_c3_5",
    360: "invalid_c3_6",
    900: "planner_internal_error",
}

PROFILE_LABELS = {
    2: "2.5.*",
    3: "3.0.0",
    4: "4.0.0",
    5: "5.5.*",
    6: "6.0.0",
}

QUEUE_SLOT_WORD_LABELS = [
    "ORDER_ID_LO",
    "ORDER_ID_HI",
    "EXECUTE_DAY",
    "EXECUTE_MONTH",
    "EXECUTE_YEAR",
    "EXECUTE_HOUR",
    "EXECUTE_MINUTE",
    "EXECUTE_SECOND",
    "C1_ATT1_PROFILE",
    "C1_PADDING",
    "C1_ATT2_POWER_LIMIT_REAL_LO",
    "C1_ATT2_POWER_LIMIT_REAL_HI",
    "C1_ATT3_ELEC_PRESSURE_REAL_LO",
    "C1_ATT3_ELEC_PRESSURE_REAL_HI",
    "C1_ATT4_RESERVED",
    "C1_ATT5_RESERVED",
    "C1_ATT6_RESERVED",
    "C2_PADDING",
    "C2_ATT1_MET_ACTIVATION",
    "C2_PADDING",
    "C2_ATT2_MET_TYPE_REAL_LO",
    "C2_ATT2_MET_TYPE_REAL_HI",
    "C2_ATT3_MET_PRESSURE_REAL_LO",
    "C2_ATT3_MET_PRESSURE_REAL_HI",
    "C2_ATT4_RESERVED",
    "C2_ATT5_RESERVED",
    "C2_ATT6_RESERVED",
    "C3_PADDING",
    "C3_ATT1_SECOURS",
    "C3_ATT2_RESERVED",
    "C3_ATT3_RESERVED",
    "C3_ATT4_RESERVED",
    "C3_ATT5_RESERVED",
    "C3_ATT6_RESERVED",
    "RESERVED_0",
    "RESERVED_1",
    "RESERVED_2",
    "RESERVED_3",
    "RESERVED_4",
    "RESERVED_5",
    "RESERVED_6",
    "RESERVED_7",
    "RESERVED_8",
    "RESERVED_9",
    "ORDER_STATUS",
    "SLOT_PADDING_NOT_IN_EXCEL",
]

MAX_POWER_LIMIT_KW = 50.0
MAX_PRESSURE_BAR = 18.0

PROFILE_RULES = {
    2: {"c2_1": 5, "c2_2": {0, 2}, "c2_3_zero_only": False, "c3_1": {0, 1}},
    3: {"c2_1": 0, "c2_2": {0}, "c2_3_zero_only": True, "c3_1": {0}},
    4: {"c2_1": 0, "c2_2": {0}, "c2_3_zero_only": True, "c3_1": {0}},
    5: {"c2_1": 5, "c2_2": {0, 2}, "c2_3_zero_only": False, "c3_1": {0, 1}},
    6: {"c2_1": 0, "c2_2": {0}, "c2_3_zero_only": True, "c3_1": {0}},
}

STRATEGY_LABELS = {
    0: "NONE",
    1: "C1",
    2: "C2",
    3: "C3",
}

IBC_STATE_LABELS = {
    0: "OFF",
    1: "PURGING",
    2: "IGNITING",
    3: "RUNNING",
    4: "COOLDOWN",
    99: "FAULT",
}


def u32_to_words(value):
    value = int(value) & 0xFFFFFFFF
    high_word = (value >> 16) & 0xFFFF
    low_word = value & 0xFFFF
    if U32_WORD_ORDER == "low_word_first":
        return [low_word, high_word]
    return [high_word, low_word]


def words_to_u32(first_word, second_word):
    if U32_WORD_ORDER == "low_word_first":
        high_word, low_word = second_word, first_word
    else:
        high_word, low_word = first_word, second_word
    return ((int(high_word) & 0xFFFF) << 16) | (int(low_word) & 0xFFFF)


def float_to_words(value):
    packed = struct.pack(">f", float(value))
    raw = struct.unpack(">I", packed)[0]
    high_word = (raw >> 16) & 0xFFFF
    low_word = raw & 0xFFFF
    if FLOAT_WORD_ORDER == "low_word_first":
        return [low_word, high_word]
    return [high_word, low_word]


def words_to_float(first_word, second_word):
    if FLOAT_WORD_ORDER == "low_word_first":
        high_word, low_word = second_word, first_word
    else:
        high_word, low_word = first_word, second_word
    raw = ((int(high_word) & 0xFFFF) << 16) | (int(low_word) & 0xFFFF)
    return struct.unpack(">f", struct.pack(">I", raw))[0]


def word_bit(word, bit):
    return bool((int(word) & 0xFFFF) & (1 << int(bit)))


def sim_process_reg(real_register):
    return REG_SIM_PROCESS_OFFSET + int(real_register)


def planner_crc16(words):
    crc = 0xFFFF
    for word in words:
        for byte in (((int(word) >> 8) & 0xFF), int(word) & 0xFF):
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
    return crc & 0xFFFF


def save_operation_mode_state(mode):
    try:
        OPERATION_MODE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "mode": normalize_operation_mode(mode),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "edge_instance_id": EDGE_AGENT_INSTANCE_ID,
        }
        OPERATION_MODE_STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"[GATEWAY] operation mode state write failed: {exc}")


class SteamSwitchGateway:
    def __init__(self):
        self.nc = NATS()
        self.modbus = None
        # Gateway startup follows systemd/Ansible config, not a stale runtime file.
        # The state file is only the bridge that lets telemetry_publisher follow
        # successful hot switches performed by this process.
        self.operation_mode = normalize_operation_mode(OPERATION_MODE_DEFAULT)
        self.last_plc_second = -1
        self.last_plc_second_change = time.time()
        self.last_plc_watchdog = -1
        self.last_plc_watchdog_change = time.time()

    def _mode_config(self, mode=None):
        selected_mode = normalize_operation_mode(mode or self.operation_mode)
        if selected_mode == "real":
            return {
                "mode": "real",
                "label": "LIVE: PHYSICAL PLANT (LCI)",
                "safe_badge": "LIVE: PHYSICAL PLANT (LCI)",
                "target_host": MODBUS_REAL_HOST,
                "target_port": MODBUS_REAL_PORT,
                "telemetry_profile": "real_lci",
                "watchdog_strict": WATCHDOG_STRICT_REAL,
                "telemetry_registers": {
                    "plc_health": {
                        "base": REG_PLC_FAULT,
                        "words": 4,
                        "variables": ["GE00_DEFAUT", "GE00_NBDEFAUT", "GE00_ALARME", "GE00_NBALARME"],
                    },
                    "pressure_bar": {
                        "base": REG_REAL_PRESSURE_BASE,
                        "words": 2,
                        "type": "REAL_FLOAT32_BE_WORD_SWAP",
                        "word_order": FLOAT_WORD_ORDER,
                        "variable": "PT01_MESURE",
                        "unit": "Bar",
                    },
                    "pressure_sensor": {
                        "error": REG_REAL_PRESSURE_ERROR,
                        "percent": REG_REAL_PRESSURE_PERCENT,
                        "variables": ["PT01_ERREUR", "PT01_MESUREPRCT"],
                    },
                    "load_pct": {
                        "base": REG_REAL_DEMAND_BASE,
                        "words": 2,
                        "type": "REAL_FLOAT32_BE_WORD_SWAP",
                        "word_order": FLOAT_WORD_ORDER,
                        "variable": "RP08_CHARGE",
                        "unit": "%",
                        "note": "No direct factory-demand kW register in Rev02; using thermoplongeur load.",
                    },
                    "pressure_regulation": {
                        "base": REG_REAL_PRESSURE_REGULATION_BASE,
                        "setpoint": REG_REAL_PRESSURE_SETPOINT,
                        "boost": REG_REAL_PRESSURE_BOOST,
                        "variables": [
                            "ETAT_THERMO",
                            "MINI_TECHNIQUE",
                            "POS_LIMITEUR",
                            "RP08_AUTO",
                            "RP08_MANU",
                            "RP08_DESACTIVE",
                            "RP08_CONSIGNE",
                            "RP08_BOOST",
                        ],
                    },
                    "heater_feedback": {
                        "base": REG_REAL_HEATER_FEEDBACK_BASE,
                        "error": REG_REAL_HEATER_FEEDBACK_ERROR,
                        "variables": ["ZT16_MESURE", "ZT16_ERREUR"],
                    },
                },
            }

        return {
            "mode": "simulation",
            "label": "ENVIRONMENT: DIGITAL TWIN (SAFE)",
            "safe_badge": "ENVIRONMENT: DIGITAL TWIN (SAFE)",
            "target_host": MODBUS_SIM_HOST,
            "target_port": MODBUS_SIM_PORT,
            "telemetry_profile": "digital_twin",
            "watchdog_strict": WATCHDOG_STRICT_SIMULATION,
            "telemetry_registers": {
                "pressure_bar": {
                    "base": REG_SIM_PRESSURE,
                    "words": 1,
                    "type": "UINT16_DECIBAR",
                    "variable": "SIM_PRESSURE",
                    "unit": "Bar",
                },
                "demand_kw": {
                    "base": REG_SIM_DEMAND,
                    "words": 1,
                    "type": "UINT16_KW",
                    "variable": "SIM_FACTORY_DEMAND",
                    "unit": "kW",
                },
                "ibc_base": {
                    "base": REG_SIM_BOILER_BASE,
                    "stride": 10,
                    "type": "SIMULATED_IBC_STATE_LOAD_TARGET",
                },
                "rev02_process_mapping": {
                    "offset": REG_SIM_PROCESS_OFFSET,
                    "rule": "sim_register = real_register + offset",
                    "plc_health": {
                        "sim_base": sim_process_reg(REG_PLC_FAULT),
                        "real_base": REG_PLC_FAULT,
                        "words": 4,
                    },
                    "pressure_bar": {
                        "sim_base": sim_process_reg(REG_REAL_PRESSURE_BASE),
                        "real_base": REG_REAL_PRESSURE_BASE,
                        "type": "REAL_FLOAT32_BE_WORD_SWAP",
                        "word_order": FLOAT_WORD_ORDER,
                        "variable": "PT01_MESURE",
                    },
                    "pressure_regulation": {
                        "sim_base": sim_process_reg(REG_REAL_PRESSURE_REGULATION_BASE),
                        "real_base": REG_REAL_PRESSURE_REGULATION_BASE,
                        "setpoint_sim": sim_process_reg(REG_REAL_PRESSURE_SETPOINT),
                        "setpoint_real": REG_REAL_PRESSURE_SETPOINT,
                    },
                    "heater_feedback": {
                        "sim_base": sim_process_reg(REG_REAL_HEATER_FEEDBACK_BASE),
                        "real_base": REG_REAL_HEATER_FEEDBACK_BASE,
                    },
                },
            },
        }

    def _operation_mode_payload(self, action="operation_mode_status", previous_mode=None):
        config = self._mode_config()
        return {
            "status": "ok",
            "action": action,
            "mode": config["mode"],
            "previous_mode": previous_mode,
            "label": config["label"],
            "safe_badge": config["safe_badge"],
            "target_host": config["target_host"],
            "target_port": config["target_port"],
            "modbus_connected": bool(self.modbus and self.modbus.connected),
            "telemetry_profile": config["telemetry_profile"],
            "telemetry_registers": config["telemetry_registers"],
            "watchdog_strict": bool(config["watchdog_strict"]),
            "watchdog_freeze_threshold_sec": WATCHDOG_FREEZE_THRESHOLD_SEC,
            "state_file": str(OPERATION_MODE_STATE_FILE),
            "fixed_rev02_contract": {
                "preparation": [REG_PREP_BASE, REG_PREP_BASE + PREP_WORDS - 1],
                "triggers": [REG_ADD_TRIGGER, REG_DELETE_TRIGGER, REG_RESET_TRIGGER],
                "statuses": [REG_ADD_STATUS, REG_DELETE_STATUS, REG_RESET_STATUS],
                "planner": [REG_PLANNER_STATE, REG_PLANNER_CRC, REG_PLANNER_CRC_STATE],
                "queue_base": REG_QUEUE_BASE,
                "queue_slot_stride": QUEUE_SLOT_STRIDE,
                "queue_max_orders": QUEUE_MAX_ORDERS,
            },
        }

    async def _close_modbus_client(self):
        if self.modbus is None:
            return
        close_result = self.modbus.close()
        if inspect.isawaitable(close_result):
            await close_result

    async def _connect_modbus_for_mode(self, mode):
        selected_mode = normalize_operation_mode(mode)
        config = self._mode_config(selected_mode)
        print(
            "[GATEWAY] Connecting Modbus "
            f"mode={selected_mode} target={config['target_host']}:{config['target_port']}..."
        )
        new_client = AsyncModbusTcpClient(config["target_host"], port=config["target_port"])
        await new_client.connect()
        if not new_client.connected:
            close_result = new_client.close()
            if inspect.isawaitable(close_result):
                await close_result
            raise RuntimeError(
                f"modbus_connect_failed mode={selected_mode} "
                f"target={config['target_host']}:{config['target_port']}"
            )

        old_client = self.modbus
        self.modbus = new_client
        if old_client is not None and old_client is not new_client:
            close_result = old_client.close()
            if inspect.isawaitable(close_result):
                await close_result

        self.operation_mode = selected_mode
        self.last_plc_second = -1
        self.last_plc_second_change = time.time()
        self.last_plc_watchdog = -1
        self.last_plc_watchdog_change = time.time()
        save_operation_mode_state(selected_mode)

    async def monitor_plc_watchdog(self):
        while True:
            if self.modbus and self.modbus.connected:
                try:
                    res = await self.modbus.read_holding_registers(address=REG_PLC_WATCHDOG, count=1)
                    if not res.isError():
                        current_value = int(res.registers[0])
                        if current_value != self.last_plc_watchdog:
                            self.last_plc_watchdog = current_value
                            self.last_plc_watchdog_change = time.time()
                        elif time.time() - self.last_plc_watchdog_change > 30:
                            print("[GATEWAY] ALERT: PLC watchdog frozen on %MW256 (>30s).")
                except Exception as exc:
                    print(f"[GATEWAY] PLC watchdog read error: {exc}")
            await asyncio.sleep(1)

    async def monitor_plc_clock(self):
        while True:
            if self.modbus and self.modbus.connected:
                try:
                    res = await self.modbus.read_holding_registers(address=REG_PLC_SECOND, count=1)
                    if not res.isError():
                        current_sec = int(res.registers[0])
                        if current_sec != self.last_plc_second:
                            self.last_plc_second = current_sec
                            self.last_plc_second_change = time.time()
                        elif time.time() - self.last_plc_second_change > 30:
                            print("[GATEWAY] ALERT: PLC clock frozen on %MW255 (>30s).")
                except Exception as exc:
                    print(f"[GATEWAY] PLC clock read error: {exc}")
            await asyncio.sleep(1)

    async def handle_command(self, msg):
        target_info = None

        try:
            payload = json.loads(msg.data.decode())
        except Exception as exc:
            result = {
                "status": "error",
                "message": f"invalid_json: {exc}",
                "edge_instance_id": EDGE_AGENT_INSTANCE_ID,
            }
            await self._safe_reply(msg.reply, result)
            return

        action = str(payload.get("action", "upsert")).lower().strip()
        modbus_optional_actions = {"operation_mode_status", "mode_status", "set_operation_mode", "switch_mode"}

        if action not in modbus_optional_actions and (not self.modbus or not self.modbus.connected):
            result = {
                "status": "error",
                "message": "modbus_not_connected",
                "edge_instance_id": EDGE_AGENT_INSTANCE_ID,
                "operation_mode": self._operation_mode_payload(),
            }
            await self._safe_reply(msg.reply, result)
            return

        try:
            target_info = self._assert_target_matches(payload)
            if action in {"operation_mode_status", "mode_status"}:
                result = self._operation_mode_payload()
            elif action in {"set_operation_mode", "switch_mode"}:
                result = await self._handle_set_operation_mode(payload)
            elif action in {"upsert", "add", "modify"}:
                result = await self._handle_upsert(payload)
            elif action == "delete":
                result = await self._handle_delete(payload)
            elif action in {"reset", "clear"}:
                result = await self._handle_reset()
            elif action in {"read_plan", "queue_snapshot", "list_orders"}:
                result = await self._handle_read_plan()
            elif action in {"register_check", "planner_register_check", "queue_register_check"}:
                result = await self._handle_planner_register_check()
            elif action in {"monitor_snapshot", "simulator_snapshot", "digital_twin_monitor"}:
                result = await self._handle_monitor_snapshot()
            else:
                result = {"status": "error", "message": f"unsupported_action:{action}"}
        except Exception as exc:
            result = {
                "status": "error",
                "message": str(exc),
                "edge_instance_id": EDGE_AGENT_INSTANCE_ID,
            }

        if isinstance(result, dict):
            result.setdefault("edge_instance_id", EDGE_AGENT_INSTANCE_ID)
            result.setdefault("operation_mode_name", self.operation_mode)
            if target_info is not None:
                result.setdefault("target_field", target_info["target_field"])
                result.setdefault("target_value", target_info["target_value"])

        await self._safe_reply(msg.reply, result)

    async def _handle_upsert(self, payload):
        await self._assert_commands_allowed()
        order_id = self._parse_required_order_id(payload)
        execute_at = self._parse_execute_at(payload)

        c1 = self._normalize_consigne(self._require_payload_field(payload, "c1"), "c1")
        c2 = self._normalize_consigne(self._require_payload_field(payload, "c2"), "c2")
        c3 = self._normalize_consigne(self._require_payload_field(payload, "c3"), "c3", force_int=True)
        validation_errors = self._collect_exchange_table_errors(c1, c2, c3)
        validation_bypass = self._validation_bypass_requested(payload)
        if validation_errors and not validation_bypass:
            raise ValueError(validation_errors[0]["message"])

        block = self._build_preparation_block(order_id, execute_at, c1, c2, c3)
        await self._write_and_verify_preparation(block)
        code = await self._commit_action(REG_ADD_TRIGGER, REG_ADD_STATUS)

        return {
            "status": "ok" if code == 0 else "error",
            "action": "upsert",
            "order_id": order_id,
            "execute_at": execute_at.strftime("%Y-%m-%d %H:%M:%S"),
            "status_code": code,
            "status_text": STATUS_TEXT.get(code, "unknown_status"),
            "register_base": REG_PREP_BASE,
            "trigger_register": REG_ADD_TRIGGER,
            "status_register": REG_ADD_STATUS,
            "gateway_validation": "bypassed" if validation_errors and validation_bypass else "passed",
            "gateway_validation_enforced": not validation_bypass,
            "gateway_validation_errors": validation_errors,
        }

    async def _handle_delete(self, payload):
        await self._assert_commands_allowed()
        order_id = self._parse_required_order_id(payload)
        block = [0] * PREP_WORDS
        block[0:2] = u32_to_words(order_id)

        await self._write_and_verify_preparation(block)
        code = await self._commit_action(REG_DELETE_TRIGGER, REG_DELETE_STATUS)

        return {
            "status": "ok" if code == 0 else "error",
            "action": "delete",
            "order_id": order_id,
            "status_code": code,
            "status_text": STATUS_TEXT.get(code, "unknown_status"),
            "trigger_register": REG_DELETE_TRIGGER,
            "status_register": REG_DELETE_STATUS,
        }

    async def _handle_reset(self):
        await self._assert_commands_allowed()
        code = await self._commit_action(REG_RESET_TRIGGER, REG_RESET_STATUS)
        return {
            "status": "ok" if code == 0 else "error",
            "action": "reset",
            "status_code": code,
            "status_text": STATUS_TEXT.get(code, "unknown_status"),
            "trigger_register": REG_RESET_TRIGGER,
            "status_register": REG_RESET_STATUS,
        }

    async def _handle_set_operation_mode(self, payload):
        raw_mode = payload.get("mode") or payload.get("operation_mode") or payload.get("target_mode")
        if raw_mode is None:
            raise ValueError("missing_operation_mode")

        requested_mode = normalize_operation_mode(
            raw_mode
        )
        previous_mode = self.operation_mode

        if requested_mode == "real":
            confirmation = str(payload.get("confirmation") or payload.get("confirm") or "").strip()
            if confirmation != OPERATION_MODE_REAL_CONFIRMATION:
                raise ValueError(
                    "real_mode_requires_confirmation "
                    f"expected='{OPERATION_MODE_REAL_CONFIRMATION}'"
                )

        await self._connect_modbus_for_mode(requested_mode)
        return self._operation_mode_payload(action="set_operation_mode", previous_mode=previous_mode)

    async def _handle_read_plan(self):
        state = await self._read_single_register(REG_PLANNER_STATE)
        remote_crc = await self._read_single_register(REG_PLANNER_CRC)
        crc_state = await self._read_single_register(REG_PLANNER_CRC_STATE)

        orders = []
        planner_words = []

        for index in range(QUEUE_MAX_ORDERS):
            register = REG_QUEUE_BASE + (index * QUEUE_SLOT_STRIDE)
            result = await self.modbus.read_holding_registers(address=register, count=QUEUE_SLOT_WORDS)
            if result.isError():
                raise RuntimeError(f"queue_read_error:slot_{index}")

            raw = [int(word) & 0xFFFF for word in result.registers]
            planner_words.extend(raw)
            order = self._decode_queue_slot(raw)
            if order is not None:
                order["slot_index"] = index
                order["register_base"] = register
                orders.append(order)

        calculated_crc = planner_crc16(planner_words)

        return {
            "status": "ok",
            "action": "read_plan",
            "planner_state": state,
            "planner_state_text": "ok" if state == 0 else "full_or_locked",
            "planner_crc16": remote_crc,
            "planner_crc16_calculated": calculated_crc,
            "planner_crc16_matches": remote_crc == calculated_crc,
            "planner_crc_state": crc_state,
            "planner_crc_state_text": "complete" if crc_state == 0 else "in_progress",
            "count": len(orders),
            "planner_word_count": len(planner_words),
            "slot_stride": QUEUE_SLOT_STRIDE,
            "slot_words": QUEUE_SLOT_WORDS,
            "planner_register_check": self._build_planner_register_check(planner_words),
            "orders": orders,
        }

    async def _handle_planner_register_check(self):
        planner_words = []
        for index in range(QUEUE_MAX_ORDERS):
            register = REG_QUEUE_BASE + (index * QUEUE_SLOT_STRIDE)
            raw = await self._read_registers_checked(register, QUEUE_SLOT_WORDS)
            planner_words.extend(raw)

        return {
            "status": "ok",
            "action": "register_check",
            "scope": "planner_queue",
            "range_start": REG_QUEUE_BASE,
            "range_end": REG_QUEUE_REGISTER_CHECK_END,
            "word_count": REG_QUEUE_REGISTER_CHECK_END - REG_QUEUE_BASE + 1,
            "slot_stride": QUEUE_SLOT_STRIDE,
            "slot_words_read": QUEUE_SLOT_WORDS,
            "slot_count": QUEUE_MAX_ORDERS,
            "planner_register_check": self._build_planner_register_check(planner_words),
        }

    def _build_planner_register_check(self, planner_words):
        official_word_count = REG_QUEUE_REGISTER_CHECK_END - REG_QUEUE_BASE + 1
        words = [int(word) & 0xFFFF for word in planner_words[:official_word_count]]
        rows = []
        for index, value in enumerate(words):
            address = REG_QUEUE_BASE + index
            slot_index = index // QUEUE_SLOT_STRIDE
            slot_offset = index % QUEUE_SLOT_STRIDE
            rows.append(
                {
                    "register": address,
                    "register_label": f"%MW{address}",
                    "slot_index": slot_index,
                    "slot_offset": slot_offset,
                    "field": QUEUE_SLOT_WORD_LABELS[slot_offset]
                    if slot_offset < len(QUEUE_SLOT_WORD_LABELS)
                    else f"SLOT_OFFSET_{slot_offset}",
                    "value": value,
                }
            )

        return {
            "range_start": REG_QUEUE_BASE,
            "range_end": REG_QUEUE_REGISTER_CHECK_END,
            "word_count": official_word_count,
            "rows": rows,
        }

    async def _handle_monitor_snapshot(self):
        clock_words = await self._read_registers_checked(REG_PLC_YEAR, 6)
        watchdog = await self._read_single_register(REG_PLC_WATCHDOG)
        operation_status = {
            "add": await self._read_single_register(REG_ADD_STATUS),
            "delete": await self._read_single_register(REG_DELETE_STATUS),
            "reset": await self._read_single_register(REG_RESET_STATUS),
        }
        planner_state = await self._read_single_register(REG_PLANNER_STATE)
        planner_crc = await self._read_single_register(REG_PLANNER_CRC)
        planner_crc_state = await self._read_single_register(REG_PLANNER_CRC_STATE)

        orders = []
        planner_words = []
        queue_head_words = []

        for index in range(QUEUE_MAX_ORDERS):
            register = REG_QUEUE_BASE + (index * QUEUE_SLOT_STRIDE)
            raw = await self._read_registers_checked(register, QUEUE_SLOT_WORDS)
            if index == 0:
                queue_head_words = raw
            planner_words.extend(raw)
            order = self._decode_queue_slot(raw)
            if order is not None:
                order["slot_index"] = index
                order["register_base"] = register
                orders.append(order)

        queue_head = self._decode_queue_slot(queue_head_words)
        queue_head_crc = planner_crc16(queue_head_words) if queue_head is not None else 0
        calculated_planner_crc = planner_crc16(planner_words)

        telemetry = await self._read_telemetry_snapshot()
        if self._mode_config()["mode"] == "real":
            pressure_regulation = telemetry.get("pressure_regulation", {})
            runtime_source = "real_lci_derived_from_rp08"
            active_strategy = 0
            active_order_id = 0
            target_pressure_bar = float(pressure_regulation.get("setpoint_bar", 0.0) or 0.0)
            active_stages = 1 if pressure_regulation.get("thermo_running") else 0
        else:
            runtime_source = "digital_twin_%MW9070"
            runtime_words = await self._read_registers_checked(REG_RUNTIME_BASE, REG_RUNTIME_WORDS)
            active_strategy = int(runtime_words[0])
            active_order_id = words_to_u32(runtime_words[1], runtime_words[2])
            target_pressure_bar = round(int(runtime_words[3]) / 10.0, 3)
            active_stages = int(runtime_words[4])

        return {
            "status": "ok",
            "action": "monitor_snapshot",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation_mode": self._operation_mode_payload(),
            "plc_clock": {
                "year": int(clock_words[0]),
                "month": int(clock_words[1]),
                "day": int(clock_words[2]),
                "hour": int(clock_words[3]),
                "minute": int(clock_words[4]),
                "second": int(clock_words[5]),
            },
            "plc_watchdog": int(watchdog),
            "operation_status": operation_status,
            "planner": {
                "state": planner_state,
                "state_text": "ok" if planner_state == 0 else "full_or_locked",
                "crc16": planner_crc,
                "crc16_calculated": calculated_planner_crc,
                "crc16_matches": planner_crc == calculated_planner_crc,
                "crc_state": planner_crc_state,
                "crc_state_text": "complete" if planner_crc_state == 0 else "in_progress",
                "queue_head_crc16": queue_head_crc,
                "count": len(orders),
                "word_count": len(planner_words),
                "slot_limit": QUEUE_MAX_ORDERS,
                "slot_stride": QUEUE_SLOT_STRIDE,
                "slot_words": QUEUE_SLOT_WORDS,
            },
            "queue_head": queue_head,
            "queue_head_raw": queue_head_words,
            "orders": orders,
            "steam_header": {
                "pressure_bar": telemetry["pressure_bar"],
                "pressure_label": telemetry.get("pressure_label"),
                "pressure_register": telemetry.get("pressure_register"),
                "pressure_register_label": telemetry.get("pressure_register_label"),
                "pressure_maps_to": telemetry.get("pressure_maps_to"),
                "pressure_raw": telemetry.get("pressure_raw"),
                "pressure_words": telemetry.get("pressure_words"),
                "demand_kw": telemetry["demand_kw"],
                "load_pct": telemetry.get("load_pct"),
                "demand_label": telemetry.get("demand_label"),
                "demand_unit": telemetry.get("demand_unit"),
                "demand_register": telemetry.get("demand_register"),
                "demand_register_label": telemetry.get("demand_register_label"),
                "demand_note": telemetry.get("demand_note"),
                "demand_words": telemetry.get("demand_words"),
                "telemetry_profile": telemetry["telemetry_profile"],
            },
            "plc_health": telemetry.get("plc_health", {}),
            "pressure_sensor": telemetry.get("pressure_sensor", {}),
            "pressure_regulation": telemetry.get("pressure_regulation", {}),
            "heater_feedback": telemetry.get("heater_feedback", {}),
            "runtime": {
                "active_strategy_code": active_strategy,
                "active_strategy": STRATEGY_LABELS.get(active_strategy, "UNKNOWN"),
                "active_order_id": active_order_id,
                "target_pressure_bar": target_pressure_bar,
                "active_stages": active_stages,
                "register_base": REG_RUNTIME_BASE,
                "source": runtime_source,
            },
            "ibcs": telemetry["ibcs"],
            "register_map": {
                "plc_clock_base": REG_PLC_YEAR,
                "plc_watchdog": REG_PLC_WATCHDOG,
                "operation_status": [REG_ADD_STATUS, REG_DELETE_STATUS, REG_RESET_STATUS],
                "planner": [REG_PLANNER_STATE, REG_PLANNER_CRC, REG_PLANNER_CRC_STATE],
                "queue_head": REG_QUEUE_BASE,
                "telemetry": self._mode_config()["telemetry_registers"],
                "runtime_base": REG_RUNTIME_BASE,
            },
        }

    async def _read_single_register(self, address):
        result = await self.modbus.read_holding_registers(address=address, count=1)
        if result.isError():
            raise RuntimeError(f"modbus_read_error:{address}")
        return int(result.registers[0])

    async def _read_registers_checked(self, address, count):
        result = await self.modbus.read_holding_registers(address=address, count=count)
        if result.isError():
            raise RuntimeError(f"modbus_read_error:{address}:{count}")
        return [int(word) & 0xFFFF for word in result.registers]

    async def _read_telemetry_snapshot(self):
        config = self._mode_config()
        if config["mode"] == "real":
            plc_health_words = await self._read_registers_checked(REG_PLC_FAULT, 4)
            pressure_words = await self._read_registers_checked(REG_REAL_PRESSURE_BASE, 2)
            pressure_error_word = (await self._read_registers_checked(REG_REAL_PRESSURE_ERROR, 1))[0]
            pressure_percent_words = await self._read_registers_checked(REG_REAL_PRESSURE_PERCENT, 2)
            pressure_regulation_words = await self._read_registers_checked(REG_REAL_PRESSURE_REGULATION_BASE, 9)
            demand_words = await self._read_registers_checked(REG_REAL_DEMAND_BASE, 2)
            heater_feedback_words = await self._read_registers_checked(REG_REAL_HEATER_FEEDBACK_BASE, 3)
            load_pct = round(words_to_float(demand_words[0], demand_words[1]), 3)
            setpoint_bar = round(words_to_float(pressure_regulation_words[6], pressure_regulation_words[7]), 3)
            heater_feedback_pct = round(words_to_float(heater_feedback_words[0], heater_feedback_words[1]), 3)
            pressure_regulation_mode = "disabled"
            if word_bit(pressure_regulation_words[1], 8):
                pressure_regulation_mode = "auto"
            elif word_bit(pressure_regulation_words[2], 0):
                pressure_regulation_mode = "manual"
            elif not word_bit(pressure_regulation_words[2], 8):
                pressure_regulation_mode = "unknown"
            return {
                "telemetry_profile": config["telemetry_profile"],
                "pressure_bar": round(words_to_float(pressure_words[0], pressure_words[1]), 3),
                "pressure_label": "PT01_MESURE",
                "pressure_register": REG_REAL_PRESSURE_BASE,
                "pressure_register_label": f"%MW{REG_REAL_PRESSURE_BASE}",
                "pressure_words": pressure_words,
                "plc_health": {
                    "fault": word_bit(plc_health_words[0], 0),
                    "fault_count": int(plc_health_words[1]),
                    "alarm": word_bit(plc_health_words[2], 0),
                    "alarm_count": int(plc_health_words[3]),
                    "registers": {
                        "fault": f"%MW{REG_PLC_FAULT}.0",
                        "fault_count": f"%MW{REG_PLC_FAULT_COUNT}",
                        "alarm": f"%MW{REG_PLC_ALARM}.0",
                        "alarm_count": f"%MW{REG_PLC_ALARM_COUNT}",
                    },
                    "raw": plc_health_words,
                },
                "pressure_sensor": {
                    "error": word_bit(pressure_error_word, 0),
                    "error_register_label": f"%MW{REG_REAL_PRESSURE_ERROR}.0",
                    "percent": round(words_to_float(pressure_percent_words[0], pressure_percent_words[1]), 3),
                    "percent_register_label": f"%MW{REG_REAL_PRESSURE_PERCENT}",
                    "raw_error_word": int(pressure_error_word),
                    "raw_percent_words": pressure_percent_words,
                },
                # Compatibility key kept for dashboards that still read demand_kw.
                "demand_kw": load_pct,
                "load_pct": load_pct,
                "demand_label": "RP08_CHARGE",
                "demand_unit": "%",
                "demand_register": REG_REAL_DEMAND_BASE,
                "demand_register_label": f"%MW{REG_REAL_DEMAND_BASE}",
                "demand_note": "LCI Rev02 exposes thermoplongeur load here, not a kW factory-demand register.",
                "demand_words": demand_words,
                "pressure_regulation": {
                    "thermo_running": word_bit(pressure_regulation_words[0], 0),
                    "mini_technique": word_bit(pressure_regulation_words[0], 8),
                    "limiter_position": word_bit(pressure_regulation_words[1], 0),
                    "mode": pressure_regulation_mode,
                    "mode_auto": word_bit(pressure_regulation_words[1], 8),
                    "mode_manual": word_bit(pressure_regulation_words[2], 0),
                    "mode_disabled": word_bit(pressure_regulation_words[2], 8),
                    "load_pct": load_pct,
                    "load_register_label": f"%MW{REG_REAL_DEMAND_BASE}",
                    "setpoint_bar": setpoint_bar,
                    "setpoint_register_label": f"%MW{REG_REAL_PRESSURE_SETPOINT}",
                    "boost": word_bit(pressure_regulation_words[8], 0),
                    "boost_register_label": f"%MW{REG_REAL_PRESSURE_BOOST}.0",
                    "raw_words": pressure_regulation_words,
                },
                "heater_feedback": {
                    "load_pct": heater_feedback_pct,
                    "load_register_label": f"%MW{REG_REAL_HEATER_FEEDBACK_BASE}",
                    "error": word_bit(heater_feedback_words[2], 0),
                    "error_register_label": f"%MW{REG_REAL_HEATER_FEEDBACK_ERROR}.0",
                    "raw_words": heater_feedback_words,
                },
                "ibcs": {
                    f"ibc{index}": {
                        "state": 3 if index == 1 and word_bit(pressure_regulation_words[0], 0) else 0,
                        "state_label": (
                            "THERMO_RUNNING"
                            if index == 1 and word_bit(pressure_regulation_words[0], 0)
                            else "REAL_NOT_MAPPED"
                        ),
                        "load_pct": load_pct if index == 1 else 0,
                        "target_pct": heater_feedback_pct if index == 1 else 0,
                        "register_base": REG_REAL_PRESSURE_REGULATION_BASE if index == 1 else None,
                    }
                    for index in range(1, 4)
                },
            }

        pressure_raw = (await self._read_registers_checked(REG_SIM_PRESSURE, 1))[0]
        demand_kw = (await self._read_registers_checked(REG_SIM_DEMAND, 1))[0]
        plc_health_words = await self._read_registers_checked(sim_process_reg(REG_PLC_FAULT), 4)
        pressure_words = await self._read_registers_checked(sim_process_reg(REG_REAL_PRESSURE_BASE), 2)
        pressure_error_word = (await self._read_registers_checked(sim_process_reg(REG_REAL_PRESSURE_ERROR), 1))[0]
        pressure_percent_words = await self._read_registers_checked(sim_process_reg(REG_REAL_PRESSURE_PERCENT), 2)
        pressure_regulation_words = await self._read_registers_checked(
            sim_process_reg(REG_REAL_PRESSURE_REGULATION_BASE),
            9,
        )
        demand_words = await self._read_registers_checked(sim_process_reg(REG_REAL_DEMAND_BASE), 2)
        heater_feedback_words = await self._read_registers_checked(
            sim_process_reg(REG_REAL_HEATER_FEEDBACK_BASE),
            3,
        )
        process_pressure_bar = round(words_to_float(pressure_words[0], pressure_words[1]), 3)
        process_load_pct = round(words_to_float(demand_words[0], demand_words[1]), 3)
        setpoint_bar = round(words_to_float(pressure_regulation_words[6], pressure_regulation_words[7]), 3)
        heater_feedback_pct = round(words_to_float(heater_feedback_words[0], heater_feedback_words[1]), 3)
        pressure_regulation_mode = "disabled"
        if word_bit(pressure_regulation_words[1], 8):
            pressure_regulation_mode = "auto"
        elif word_bit(pressure_regulation_words[2], 0):
            pressure_regulation_mode = "manual"
        elif not word_bit(pressure_regulation_words[2], 8):
            pressure_regulation_mode = "unknown"

        ibcs = {}
        for boiler_index in range(3):
            base = REG_SIM_BOILER_BASE + (boiler_index * 10)
            state, load_pct, target_pct = await self._read_registers_checked(base, 3)
            ibcs[f"ibc{boiler_index + 1}"] = {
                "state": int(state),
                "state_label": IBC_STATE_LABELS.get(int(state), "UNKNOWN"),
                "load_pct": int(load_pct),
                "target_pct": int(target_pct),
                "register_base": base,
            }

        return {
            "telemetry_profile": config["telemetry_profile"],
            "pressure_bar": process_pressure_bar if process_pressure_bar > 0 else round(int(pressure_raw) / 10.0, 3),
            "pressure_label": "PT01_MESURE simulated mirror",
            "pressure_register": sim_process_reg(REG_REAL_PRESSURE_BASE),
            "pressure_register_label": f"%MW{sim_process_reg(REG_REAL_PRESSURE_BASE)}",
            "pressure_maps_to": f"%MW{REG_REAL_PRESSURE_BASE}",
            "pressure_raw": int(pressure_raw),
            "demand_kw": int(demand_kw),
            "demand_label": "Factory Demand",
            "demand_unit": "kW",
            "demand_register": REG_SIM_DEMAND,
            "demand_register_label": f"%MW{REG_SIM_DEMAND}",
            "plc_health": {
                "fault": word_bit(plc_health_words[0], 0),
                "fault_count": int(plc_health_words[1]),
                "alarm": word_bit(plc_health_words[2], 0),
                "alarm_count": int(plc_health_words[3]),
                "registers": {
                    "fault": f"%MW{sim_process_reg(REG_PLC_FAULT)}.0 -> real %MW{REG_PLC_FAULT}.0",
                    "fault_count": f"%MW{sim_process_reg(REG_PLC_FAULT_COUNT)} -> real %MW{REG_PLC_FAULT_COUNT}",
                    "alarm": f"%MW{sim_process_reg(REG_PLC_ALARM)}.0 -> real %MW{REG_PLC_ALARM}.0",
                    "alarm_count": f"%MW{sim_process_reg(REG_PLC_ALARM_COUNT)} -> real %MW{REG_PLC_ALARM_COUNT}",
                },
                "raw": plc_health_words,
            },
            "pressure_sensor": {
                "error": word_bit(pressure_error_word, 0),
                "error_register_label": f"%MW{sim_process_reg(REG_REAL_PRESSURE_ERROR)}.0",
                "maps_to": f"%MW{REG_REAL_PRESSURE_ERROR}.0",
                "percent": round(words_to_float(pressure_percent_words[0], pressure_percent_words[1]), 3),
                "percent_register_label": f"%MW{sim_process_reg(REG_REAL_PRESSURE_PERCENT)}",
                "raw_error_word": int(pressure_error_word),
                "raw_percent_words": pressure_percent_words,
            },
            "load_pct": process_load_pct,
            "process_load_register_label": f"%MW{sim_process_reg(REG_REAL_DEMAND_BASE)}",
            "process_load_maps_to": f"%MW{REG_REAL_DEMAND_BASE}",
            "pressure_regulation": {
                "thermo_running": word_bit(pressure_regulation_words[0], 0),
                "mini_technique": word_bit(pressure_regulation_words[0], 8),
                "limiter_position": word_bit(pressure_regulation_words[1], 0),
                "mode": pressure_regulation_mode,
                "mode_auto": word_bit(pressure_regulation_words[1], 8),
                "mode_manual": word_bit(pressure_regulation_words[2], 0),
                "mode_disabled": word_bit(pressure_regulation_words[2], 8),
                "load_pct": process_load_pct,
                "load_register_label": f"%MW{sim_process_reg(REG_REAL_DEMAND_BASE)}",
                "load_maps_to": f"%MW{REG_REAL_DEMAND_BASE}",
                "setpoint_bar": setpoint_bar,
                "setpoint_register_label": f"%MW{sim_process_reg(REG_REAL_PRESSURE_SETPOINT)}",
                "setpoint_maps_to": f"%MW{REG_REAL_PRESSURE_SETPOINT}",
                "boost": word_bit(pressure_regulation_words[8], 0),
                "boost_register_label": f"%MW{sim_process_reg(REG_REAL_PRESSURE_BOOST)}.0",
                "boost_maps_to": f"%MW{REG_REAL_PRESSURE_BOOST}.0",
                "raw_words": pressure_regulation_words,
            },
            "heater_feedback": {
                "load_pct": heater_feedback_pct,
                "load_register_label": f"%MW{sim_process_reg(REG_REAL_HEATER_FEEDBACK_BASE)}",
                "load_maps_to": f"%MW{REG_REAL_HEATER_FEEDBACK_BASE}",
                "error": word_bit(heater_feedback_words[2], 0),
                "error_register_label": f"%MW{sim_process_reg(REG_REAL_HEATER_FEEDBACK_ERROR)}.0",
                "error_maps_to": f"%MW{REG_REAL_HEATER_FEEDBACK_ERROR}.0",
                "raw_words": heater_feedback_words,
            },
            "ibcs": ibcs,
        }

    async def _refresh_plc_watchdog_once(self):
        result = await self.modbus.read_holding_registers(address=REG_PLC_WATCHDOG, count=1)
        if result.isError():
            return False

        current_value = int(result.registers[0])
        if current_value != self.last_plc_watchdog:
            self.last_plc_watchdog = current_value
            self.last_plc_watchdog_change = time.time()
        return True

    async def _assert_commands_allowed(self):
        config = self._mode_config()
        if not config["watchdog_strict"]:
            return

        if not await self._refresh_plc_watchdog_once():
            raise RuntimeError("watchdog_strict_blocked:cannot_read_mw256")

        if self.last_plc_watchdog < 0:
            raise RuntimeError("watchdog_strict_blocked:no_watchdog_sample")

        frozen_for = time.time() - self.last_plc_watchdog_change
        if frozen_for > WATCHDOG_FREEZE_THRESHOLD_SEC:
            raise RuntimeError(
                "watchdog_strict_blocked:"
                f"mw256_frozen_for_{round(frozen_for, 1)}s"
            )

    async def _commit_action(self, bit_reg, status_reg):
        try:
            await self.modbus.write_register(address=bit_reg, value=1)

            deadline = time.monotonic() + ACK_TIMEOUT_SEC
            while time.monotonic() < deadline:
                bit_res = await self.modbus.read_holding_registers(address=bit_reg, count=1)
                if not bit_res.isError() and int(bit_res.registers[0]) == 0:
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

    async def _write_and_verify_preparation(self, values):
        expected = [int(word) & 0xFFFF for word in values]

        await self.modbus.write_registers(address=REG_PREP_BASE, values=expected)
        readback = await self.modbus.read_holding_registers(address=REG_PREP_BASE, count=len(expected))

        if readback.isError():
            raise RuntimeError("prep_readback_error")

        actual = [int(word) & 0xFFFF for word in readback.registers]
        if actual != expected:
            raise RuntimeError(f"prep_readback_mismatch expected={expected} actual={actual}")

    def _build_preparation_block(self, order_id, execute_at, c1, c2, c3):
        block = [0] * PREP_WORDS
        block[0:2] = u32_to_words(order_id)
        block[2] = execute_at.day
        block[3] = execute_at.month
        block[4] = execute_at.year
        block[5] = execute_at.hour
        block[6] = execute_at.minute
        block[7] = execute_at.second

        block[8] = int(c1[0])
        block[10:12] = float_to_words(c1[1])
        block[12:14] = float_to_words(c1[2])
        block[14] = int(c1[3])
        block[15] = int(c1[4])
        block[16] = int(c1[5])

        block[18] = int(c2[0])
        block[20:22] = float_to_words(c2[1])
        block[22:24] = float_to_words(c2[2])
        block[24] = int(c2[3])
        block[25] = int(c2[4])
        block[26] = int(c2[5])

        for offset, value in enumerate(c3[:6], start=28):
            block[offset] = int(value)

        return block

    def _decode_queue_slot(self, raw):
        order_id = words_to_u32(raw[0], raw[1])
        if order_id == 0:
            return None

        try:
            execute_at = datetime(
                int(raw[4]),
                int(raw[3]),
                int(raw[2]),
                int(raw[5]),
                int(raw[6]),
                int(raw[7]),
            )
        except ValueError:
            execute_at_text = "invalid_datetime"
        else:
            execute_at_text = execute_at.strftime("%Y-%m-%d %H:%M:%S")

        c1 = [
            int(raw[8]),
            round(words_to_float(raw[10], raw[11]), 3),
            round(words_to_float(raw[12], raw[13]), 3),
            int(raw[14]),
            int(raw[15]),
            int(raw[16]),
        ]
        c2 = [
            int(raw[18]),
            round(words_to_float(raw[20], raw[21]), 3),
            round(words_to_float(raw[22], raw[23]), 3),
            int(raw[24]),
            int(raw[25]),
            int(raw[26]),
        ]
        c3 = [int(raw[offset]) for offset in range(28, 34)]

        return {
            "id": order_id,
            "execute_at": execute_at_text,
            "c1": c1,
            "c2": c2,
            "c3": c3,
            "mode_profile_code": c1[0],
            "mode_profile_label": PROFILE_LABELS.get(c1[0], "unknown"),
            "power_limit_kw": c1[1],
            "elec_pressure_bar": c1[2],
            "met_activation": c2[0],
            "met_type": int(round(c2[1])),
            "met_pressure_bar": c2[2],
            "secours_enabled": bool(c3[0]),
            "order_status": int(raw[44]),
            "crc16": planner_crc16(raw[:QUEUE_SLOT_WORDS]),
            "raw_words": [int(word) & 0xFFFF for word in raw[:QUEUE_SLOT_WORDS]],
        }

    def _require_payload_field(self, payload, field_name):
        if field_name not in payload:
            raise ValueError(f"missing_{field_name}")
        return payload[field_name]

    def _assert_target_matches(self, payload):
        target_field = None
        target_value = None

        for field_name in COMMAND_TARGET_FIELDS:
            candidate = payload.get(field_name)
            if candidate is None:
                continue

            cleaned = str(candidate).strip()
            if cleaned:
                target_field = field_name
                target_value = cleaned
                break

        if target_value is None:
            raise ValueError(f"missing_target expected={EDGE_AGENT_INSTANCE_ID}")

        if target_value.casefold() != EDGE_AGENT_INSTANCE_ID.casefold():
            raise ValueError(f"target_mismatch expected={EDGE_AGENT_INSTANCE_ID} received={target_value}")

        return {"target_field": target_field, "target_value": target_value}

    def _parse_required_order_id(self, payload):
        raw = self._require_payload_field(payload, "id")

        order_id = int(raw)
        if order_id <= 0 or order_id > 0xFFFFFFFF:
            raise ValueError(f"invalid_id:{order_id}")
        return order_id

    def _parse_execute_at(self, payload):
        raw = payload.get("execute_at")
        if isinstance(raw, str) and raw.strip():
            value = raw.strip()
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")

            if dt.tzinfo is not None:
                # The Rev02 simulator/PLC clock is exposed in UTC on %MW250-%MW255.
                # Do not convert to the IPC host timezone; that can turn a valid
                # browser order into a past PLC time and produce status %MW1045=7.
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
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

        raise ValueError("missing_execute_at")

    def _normalize_consigne(self, values, field_name="consigne", force_int=False):
        if not isinstance(values, list) or len(values) not in {3, 6}:
            raise ValueError(f"{field_name}_must_be_list_of_3_or_6_values:{values}")

        padded = list(values) + ([0] * (6 - len(values)))
        normalized = []
        for index, value in enumerate(padded):
            normalized.append(int(value) if force_int or index in {0, 3, 4, 5} else float(value))
        return normalized

    def _validation_bypass_requested(self, payload):
        mode = str(payload.get("validation_mode") or payload.get("safety_validation_mode") or "").strip().lower()
        value = payload.get("allow_invalid_order_for_test", payload.get("bypass_gateway_validation", False))
        if isinstance(value, bool):
            allow_invalid = value
        else:
            allow_invalid = str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

        reason = str(payload.get("validation_bypass_reason") or "").strip()
        return (
            mode in {"observe_only", "standby"}
            and allow_invalid
            and reason == "operator_requested_plc_security_test"
        )

    def _collect_exchange_table_errors(self, c1, c2, c3):
        errors = []

        def add(code, field, message):
            errors.append(
                {
                    "code": code,
                    "status_text": STATUS_TEXT.get(code, "gateway_validation_error"),
                    "field": field,
                    "message": message,
                }
            )

        profile_code = int(c1[0])
        rules = PROFILE_RULES.get(profile_code)
        if rules is None:
            add(110, "c1[0]", f"invalid_c1_1_profile:{profile_code}")
            return errors

        if c1[1] < 0 or c1[1] > MAX_POWER_LIMIT_KW:
            add(120, "c1[1]", f"invalid_c1_2_power_limit_kw:{c1[1]}")
        if c1[2] < 0 or c1[2] > MAX_PRESSURE_BAR:
            add(130, "c1[2]", f"invalid_c1_3_elec_pressure_bar:{c1[2]}")
        if profile_code == 6 and (c1[1] != 0 or c1[2] != 0):
            add(120 if c1[1] != 0 else 130, "c1", "profile_6_requires_c1_2_and_c1_3_zero")
        if any(int(value) != 0 for value in c1[3:6]):
            add(140, "c1[3:6]", f"invalid_c1_reserved_expected_zero:{c1[3:6]}")

        if int(c2[0]) != int(rules["c2_1"]):
            add(210, "c2[0]", f"invalid_c2_1_expected_{rules['c2_1']}:got_{c2[0]}")
        if int(round(c2[1])) not in rules["c2_2"]:
            add(220, "c2[1]", f"invalid_c2_2_met_type:{c2[1]}")
        if c2[2] < 0 or c2[2] > MAX_PRESSURE_BAR:
            add(230, "c2[2]", f"invalid_c2_3_met_pressure_bar:{c2[2]}")
        if rules["c2_3_zero_only"] and c2[2] != 0:
            add(230, "c2[2]", f"invalid_c2_3_expected_zero_for_profile_{profile_code}:{c2[2]}")
        if any(int(value) != 0 for value in c2[3:6]):
            add(240, "c2[3:6]", f"invalid_c2_reserved_expected_zero:{c2[3:6]}")

        if int(c3[0]) not in rules["c3_1"]:
            add(310, "c3[0]", f"invalid_c3_1_secours:{c3[0]}")
        for index, value in enumerate(c3[1:6], start=2):
            if int(value) != 0:
                add(300 + (index * 10), f"c3[{index - 1}]", f"invalid_c3_{index}_expected_zero:{value}")

        return errors

    def _validate_exchange_table(self, c1, c2, c3):
        errors = self._collect_exchange_table_errors(c1, c2, c3)
        if errors:
            raise ValueError(errors[0]["message"])

    async def _safe_reply(self, reply_subject, payload):
        if reply_subject:
            await self.nc.publish(reply_subject, json.dumps(payload).encode())
        print(f"[GATEWAY] command result: {payload}")

    async def ping_handler(self, msg):
        if not self.modbus or not self.modbus.connected:
            await self.nc.publish(
                msg.reply,
                json.dumps(
                    {
                        "status": "error",
                        "message": "modbus_not_connected",
                        "edge_instance_id": EDGE_AGENT_INSTANCE_ID,
                    }
                ).encode(),
            )
            return

        try:
            data = json.loads(msg.data.decode())
            request_id = data.get("request_id")
            received_at = datetime.now(timezone.utc).isoformat()
            result = await self.modbus.read_holding_registers(address=REG_PLC_WATCHDOG, count=1)
            value_read = int(result.registers[0]) if not result.isError() else -1

            await self.nc.publish(
                msg.reply,
                json.dumps(
                    {
                        "status": "ok",
                        "valeur_retour": value_read,
                        "request_id": request_id,
                        "edge_instance_id": EDGE_AGENT_INSTANCE_ID,
                        "edge_received_at": received_at,
                        "edge_replied_at": datetime.now(timezone.utc).isoformat(),
                        "register": REG_PLC_WATCHDOG,
                        "note": "Rev02 GE00_WATCHDOG is read-only from SteamSwitch perspective.",
                    }
                ).encode(),
            )
        except Exception as exc:
            await self.nc.publish(
                msg.reply,
                json.dumps(
                    {
                        "status": "error",
                        "message": str(exc),
                        "edge_instance_id": EDGE_AGENT_INSTANCE_ID,
                    }
                ).encode(),
            )

    async def start(self):
        tls_ctx = ssl.create_default_context(cafile=CA_CERT)
        tls_ctx.load_cert_chain(CLIENT_CERT, CLIENT_KEY)
        tls_ctx.check_hostname = False

        await self._connect_modbus_for_mode(self.operation_mode)

        print(f"[GATEWAY] Connecting NATS TLS ({NATS_URL})...")
        await self.nc.connect(NATS_URL, tls=tls_ctx, name=f"gateway_modbus_edge:{EDGE_AGENT_INSTANCE_ID}")

        await self.nc.subscribe(TOPIC_PING, cb=self.ping_handler)
        await self.nc.subscribe(TOPIC_CMD, cb=self.handle_command)

        print(
            "[GATEWAY] SteamSwitch gateway is running with Rev02 register map "
            f"and operation mode={self.operation_mode}."
        )

        await asyncio.gather(
            self.monitor_plc_watchdog(),
            self.monitor_plc_clock(),
        )


if __name__ == "__main__":
    gateway = SteamSwitchGateway()
    try:
        asyncio.run(gateway.start())
    except KeyboardInterrupt:
        print("\n[GATEWAY] Stopped by user.")
