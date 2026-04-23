import calendar
import os
import struct
import time
from datetime import datetime, timedelta


def normalize_float_word_order(value):
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in {"low_word_first", "low_first", "lo_hi", "word_swap", "swapped"}:
        return "low_word_first"
    return "high_word_first"


FLOAT_WORD_ORDER = normalize_float_word_order(os.getenv("MODBUS_FLOAT_WORD_ORDER", "low_word_first"))
U32_WORD_ORDER = normalize_float_word_order(
    os.getenv("MODBUS_U32_WORD_ORDER", os.getenv("MODBUS_WORD_ORDER", "low_word_first"))
)


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


class PlanificateurSBC:
    # Official Rev02 exchange table registers.
    REG_PLC_YEAR = 250
    REG_PLC_MONTH = 251
    REG_PLC_DAY = 252
    REG_PLC_HOUR = 253
    REG_PLC_MINUTE = 254
    REG_PLC_SECOND = 255
    REG_PLC_WATCHDOG = 256

    PREP_BASE = 1000
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
    QUEUE_BASE = 8120
    SLOT_STRIDE = 46
    SLOT_WORDS = 46
    MAX_ORDERS = 10

    STATUS_OK = 0
    STATUS_QUEUE_FULL = 1
    STATUS_INVALID_YEAR = 2
    STATUS_INVALID_MONTH = 3
    STATUS_DAY_CHECK_FAILED = 4
    STATUS_INVALID_DAY = 5
    STATUS_DATE_BEFORE_PLC_DATE = 6
    STATUS_TIME_BEFORE_NOW_TODAY = 7
    STATUS_MULTIPLE_TRIGGERS = 8
    STATUS_INVALID_ID = 20
    STATUS_ORDER_NOT_FOUND = 21
    STATUS_DELETE_C1_NOT_ZERO = 100
    STATUS_DELETE_C2_NOT_ZERO = 200
    STATUS_DELETE_C3_NOT_ZERO = 300
    STATUS_INTERNAL_ERROR = 900

    EXECUTION_TOLERANCE_SEC = 2.0

    MAX_POWER_LIMIT_KW = 50.0
    MAX_PRESSURE_BAR = 18.0

    PROFILE_RULES = {
        2: {"c2_1": 5, "c2_2": {0, 2}, "c2_3_zero_only": False, "c3_1": {0, 1}},
        3: {"c2_1": 0, "c2_2": {0}, "c2_3_zero_only": True, "c3_1": {0}},
        4: {"c2_1": 0, "c2_2": {0}, "c2_3_zero_only": True, "c3_1": {0}},
        5: {"c2_1": 5, "c2_2": {0, 2}, "c2_3_zero_only": False, "c3_1": {0, 1}},
        6: {"c2_1": 0, "c2_2": {0}, "c2_3_zero_only": True, "c3_1": {0}},
    }

    def __init__(self, modbus_context, cascade_controller):
        self.context = modbus_context
        self.cascade = cascade_controller

        self.orders = []
        self._initialize_registers()

    def _initialize_registers(self):
        self._write_register(self.REG_ADD_STATUS, self.STATUS_OK)
        self._write_register(self.REG_DELETE_STATUS, self.STATUS_OK)
        self._write_register(self.REG_RESET_STATUS, self.STATUS_OK)
        self._write_register(self.REG_ADD_TRIGGER, 0)
        self._write_register(self.REG_DELETE_TRIGGER, 0)
        self._write_register(self.REG_RESET_TRIGGER, 0)
        self._sync_queue_to_modbus()

    def update(self):
        self._process_exchange_bits()
        self._execute_due_orders()

    def _process_exchange_bits(self):
        active_triggers = [
            self._read_register(self.REG_ADD_TRIGGER) & 1,
            self._read_register(self.REG_DELETE_TRIGGER) & 1,
            self._read_register(self.REG_RESET_TRIGGER) & 1,
        ]

        if sum(active_triggers) > 1:
            self._write_register(self.REG_ADD_STATUS, self.STATUS_MULTIPLE_TRIGGERS)
            self._write_register(self.REG_DELETE_STATUS, self.STATUS_MULTIPLE_TRIGGERS)
            self._write_register(self.REG_RESET_STATUS, self.STATUS_MULTIPLE_TRIGGERS)
            self._clear_triggers()
            return

        if active_triggers[0]:
            self._handle_order_upsert()
        elif active_triggers[1]:
            self._handle_order_delete()
        elif active_triggers[2]:
            self._handle_queue_reset()

    def _handle_order_upsert(self):
        try:
            raw = self._read_registers(self.PREP_BASE, self.PREP_WORDS)
            order = self._decode_order(raw)

            if order["id"] <= 0:
                self._finish_action(self.REG_ADD_TRIGGER, self.REG_ADD_STATUS, self.STATUS_INVALID_ID)
                return

            datetime_status = self._validate_order_datetime(order["target_time"])
            if datetime_status != self.STATUS_OK:
                self._finish_action(self.REG_ADD_TRIGGER, self.REG_ADD_STATUS, datetime_status)
                return

            attribute_status = self._validate_order_attributes(order)
            if attribute_status != self.STATUS_OK:
                self._finish_action(self.REG_ADD_TRIGGER, self.REG_ADD_STATUS, attribute_status)
                return

            existing_idx = self._find_order_index(order["id"])
            if existing_idx is None:
                if len(self.orders) >= self.MAX_ORDERS:
                    self._finish_action(self.REG_ADD_TRIGGER, self.REG_ADD_STATUS, self.STATUS_QUEUE_FULL)
                    return
                self.orders.append(order)
            else:
                previous = self.orders[existing_idx]
                order["created_at"] = previous["created_at"]
                self.orders[existing_idx] = order

            self._sort_orders()
            self._sync_queue_to_modbus()
            self._finish_action(self.REG_ADD_TRIGGER, self.REG_ADD_STATUS, self.STATUS_OK)
        except Exception as exc:
            print(f"[SCHEDULER] upsert failed: {exc}")
            self._finish_action(self.REG_ADD_TRIGGER, self.REG_ADD_STATUS, self.STATUS_INTERNAL_ERROR)

    def _handle_order_delete(self):
        try:
            raw = self._read_registers(self.PREP_BASE, self.PREP_WORDS)
            order_id = words_to_u32(raw[0], raw[1])

            if order_id <= 0:
                self._finish_action(self.REG_DELETE_TRIGGER, self.REG_DELETE_STATUS, self.STATUS_INVALID_ID)
                return

            if any(int(value) != 0 for value in raw[2:8]):
                self._finish_action(self.REG_DELETE_TRIGGER, self.REG_DELETE_STATUS, 1)
                return

            if any(int(value) != 0 for value in raw[8:18]):
                self._finish_action(
                    self.REG_DELETE_TRIGGER,
                    self.REG_DELETE_STATUS,
                    self.STATUS_DELETE_C1_NOT_ZERO,
                )
                return

            if any(int(value) != 0 for value in raw[18:28]):
                self._finish_action(
                    self.REG_DELETE_TRIGGER,
                    self.REG_DELETE_STATUS,
                    self.STATUS_DELETE_C2_NOT_ZERO,
                )
                return

            if any(int(value) != 0 for value in raw[28:34]):
                self._finish_action(
                    self.REG_DELETE_TRIGGER,
                    self.REG_DELETE_STATUS,
                    self.STATUS_DELETE_C3_NOT_ZERO,
                )
                return

            existing_idx = self._find_order_index(order_id)
            if existing_idx is None:
                self._finish_action(self.REG_DELETE_TRIGGER, self.REG_DELETE_STATUS, self.STATUS_ORDER_NOT_FOUND)
                return

            self.orders.pop(existing_idx)
            self._sort_orders()
            self._sync_queue_to_modbus()
            self._finish_action(self.REG_DELETE_TRIGGER, self.REG_DELETE_STATUS, self.STATUS_OK)
        except Exception as exc:
            print(f"[SCHEDULER] delete failed: {exc}")
            self._finish_action(self.REG_DELETE_TRIGGER, self.REG_DELETE_STATUS, self.STATUS_INTERNAL_ERROR)

    def _handle_queue_reset(self):
        self.orders.clear()
        self._sync_queue_to_modbus()
        self._finish_action(self.REG_RESET_TRIGGER, self.REG_RESET_STATUS, self.STATUS_OK)

    def _finish_action(self, trigger_register, status_register, status_code):
        self._write_register(status_register, status_code)
        self._write_register(trigger_register, 0)

    def _clear_triggers(self):
        self._write_register(self.REG_ADD_TRIGGER, 0)
        self._write_register(self.REG_DELETE_TRIGGER, 0)
        self._write_register(self.REG_RESET_TRIGGER, 0)

    def _execute_due_orders(self):
        if not self.orders:
            return

        now = datetime.now()
        executed = 0

        while self.orders:
            next_order = self.orders[0]
            if next_order["target_time"] > now + timedelta(seconds=self.EXECUTION_TOLERANCE_SEC):
                break

            self.orders.pop(0)
            executed += 1
            self._apply_order(next_order)

        if executed > 0:
            self._sync_queue_to_modbus()

    def _apply_order(self, order):
        strategy, power_limit_kw, target_pressure = self._decode_order_controls(order)

        self.cascade.set_active_consigne(
            strategy_code=strategy,
            target_pressure=target_pressure,
            power_limit_kw=power_limit_kw,
            source_order_id=order["id"],
        )

    def _decode_order_controls(self, order):
        c1 = order["c1"]
        c2 = order["c2"]
        c3 = order["c3"]

        power_limit_kw = float(c1[1]) if float(c1[1]) > 0 else None
        elec_pressure_bar = float(c1[2])
        met_pressure_bar = float(c2[2])
        secours_enabled = int(c3[0]) == 1
        met_type = int(round(c2[1]))

        if secours_enabled:
            strategy = "C3"
            pressure_bar = met_pressure_bar if met_pressure_bar > 0 else elec_pressure_bar
        elif met_type == 2:
            strategy = "C2"
            pressure_bar = met_pressure_bar if met_pressure_bar > 0 else elec_pressure_bar
        else:
            strategy = "C1"
            pressure_bar = elec_pressure_bar

        target_pressure = pressure_bar if pressure_bar > 0 else self.cascade.target_pressure
        return strategy, power_limit_kw, target_pressure

    def _decode_order(self, raw):
        now = datetime.now()
        target_time = self._decode_target_datetime(raw)

        return {
            "id": words_to_u32(raw[0], raw[1]),
            "target_time": target_time,
            "c1": [
                int(raw[8]),
                round(words_to_float(raw[10], raw[11]), 3),
                round(words_to_float(raw[12], raw[13]), 3),
                int(raw[14]),
                int(raw[15]),
                int(raw[16]),
            ],
            "c2": [
                int(raw[18]),
                round(words_to_float(raw[20], raw[21]), 3),
                round(words_to_float(raw[22], raw[23]), 3),
                int(raw[24]),
                int(raw[25]),
                int(raw[26]),
            ],
            "c3": [int(raw[offset]) for offset in range(28, 34)],
            "created_at": now,
            "updated_at": now,
        }

    def _decode_target_datetime(self, raw):
        year = int(raw[4])
        month = int(raw[3])
        day = int(raw[2])
        hour = int(raw[5])
        minute = int(raw[6])
        second = int(raw[7])

        try:
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            # Keep the raw values available to the validator while avoiding exceptions downstream.
            return {
                "year": year,
                "month": month,
                "day": day,
                "hour": hour,
                "minute": minute,
                "second": second,
            }

    def _validate_order_datetime(self, target_time):
        now = self._plc_now()

        if isinstance(target_time, dict):
            year = target_time["year"]
            month = target_time["month"]
            day = target_time["day"]
            hour = target_time["hour"]
            minute = target_time["minute"]
            second = target_time["second"]
        else:
            year = target_time.year
            month = target_time.month
            day = target_time.day
            hour = target_time.hour
            minute = target_time.minute
            second = target_time.second

        if year < now.year or year > now.year + 1:
            return self.STATUS_INVALID_YEAR

        if month < 1 or month > 12:
            return self.STATUS_INVALID_MONTH

        try:
            max_day = calendar.monthrange(year, month)[1]
        except Exception:
            return self.STATUS_DAY_CHECK_FAILED

        if day < 1 or day > max_day:
            return self.STATUS_INVALID_DAY

        try:
            candidate = datetime(year, month, day, hour, minute, second)
        except ValueError:
            return self.STATUS_TIME_BEFORE_NOW_TODAY

        if candidate.date() < now.date():
            return self.STATUS_DATE_BEFORE_PLC_DATE

        if candidate.date() == now.date() and candidate.time() < now.time():
            return self.STATUS_TIME_BEFORE_NOW_TODAY

        return self.STATUS_OK

    def _plc_now(self):
        raw = self._read_registers(self.REG_PLC_YEAR, 6)
        try:
            return datetime(int(raw[0]), int(raw[1]), int(raw[2]), int(raw[3]), int(raw[4]), int(raw[5]))
        except ValueError:
            return datetime.now()

    def _validate_order_attributes(self, order):
        c1 = order["c1"]
        c2 = order["c2"]
        c3 = order["c3"]

        profile_code = int(c1[0])
        rules = self.PROFILE_RULES.get(profile_code)
        if rules is None:
            return 110

        if c1[1] < 0 or c1[1] > self.MAX_POWER_LIMIT_KW:
            return 120
        if c1[2] < 0 or c1[2] > self.MAX_PRESSURE_BAR:
            return 130
        if profile_code == 6 and (c1[1] != 0 or c1[2] != 0):
            return 120 if c1[1] != 0 else 130
        if int(c1[3]) != 0:
            return 140
        if int(c1[4]) != 0:
            return 150
        if int(c1[5]) != 0:
            return 160

        if int(c2[0]) != int(rules["c2_1"]):
            return 210
        if int(round(c2[1])) not in rules["c2_2"]:
            return 220
        if c2[2] < 0 or c2[2] > self.MAX_PRESSURE_BAR:
            return 230
        if rules["c2_3_zero_only"] and c2[2] != 0:
            return 230
        if int(c2[3]) != 0:
            return 240
        if int(c2[4]) != 0:
            return 250
        if int(c2[5]) != 0:
            return 260

        if int(c3[0]) not in rules["c3_1"]:
            return 310
        for index, value in enumerate(c3[1:6], start=2):
            if int(value) != 0:
                return 300 + (index * 10)

        return self.STATUS_OK

    def _find_order_index(self, order_id):
        for index, existing in enumerate(self.orders):
            if existing["id"] == order_id:
                return index
        return None

    def _sort_orders(self):
        self.orders.sort(key=lambda order: (order["target_time"], order["updated_at"]))

    def _sync_queue_to_modbus(self):
        self._write_register(self.REG_PLANNER_CRC_STATE, 1)

        planner_words = []
        for index in range(self.MAX_ORDERS):
            register = self.QUEUE_BASE + (index * self.SLOT_STRIDE)
            if index < len(self.orders):
                slot = self._serialize_order(self.orders[index])
            else:
                slot = [0] * self.SLOT_WORDS

            planner_words.extend(slot)
            self._write_registers(register, slot)

        self._write_register(self.REG_PLANNER_STATE, 1 if len(self.orders) >= self.MAX_ORDERS else 0)
        self._write_register(self.REG_PLANNER_CRC, planner_crc16(planner_words))
        self._write_register(self.REG_PLANNER_CRC_STATE, 0)

    def _serialize_order(self, order):
        order_id = int(order["id"])
        target = order["target_time"]
        slot = [0] * self.SLOT_WORDS

        slot[0:2] = u32_to_words(order_id)
        slot[2] = target.day
        slot[3] = target.month
        slot[4] = target.year
        slot[5] = target.hour
        slot[6] = target.minute
        slot[7] = target.second

        slot[8] = int(order["c1"][0])
        slot[10:12] = float_to_words(order["c1"][1])
        slot[12:14] = float_to_words(order["c1"][2])
        slot[14] = int(order["c1"][3])
        slot[15] = int(order["c1"][4])
        slot[16] = int(order["c1"][5])

        slot[18] = int(order["c2"][0])
        slot[20:22] = float_to_words(order["c2"][1])
        slot[22:24] = float_to_words(order["c2"][2])
        slot[24] = int(order["c2"][3])
        slot[25] = int(order["c2"][4])
        slot[26] = int(order["c2"][5])

        for offset, value in enumerate(order["c3"][:6], start=28):
            slot[offset] = int(value)

        slot[44] = self.STATUS_OK
        slot[45] = 0
        return slot

    def _read_register(self, address):
        return self._read_registers(address, 1)[0]

    def _read_registers(self, address, count):
        try:
            return self.context[0].getValues(3, address, count=count)
        except Exception:
            return [0] * count

    def _write_register(self, address, value):
        self._write_registers(address, [int(value)])

    def _write_registers(self, address, values):
        try:
            self.context[0].setValues(3, address, [int(value) & 0xFFFF for value in values])
        except Exception:
            return
