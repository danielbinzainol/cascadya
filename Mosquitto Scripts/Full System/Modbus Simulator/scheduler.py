import time
from datetime import datetime, timedelta


class PlanificateurSBC:
    """
    Modbus exchange table + scheduler logic for the SBC.

    This class implements:
    - Order preparation area (%MW0-%MW16)
    - Upsert trigger/status (%MW50/%MW51)
    - Delete trigger/status (%MW60/%MW61)
    - Full reset trigger/status (%MW62/%MW63)
    - Queue exposure in %MW100 + 20*n (17 words used per slot)
    """

    PREP_BASE = 0
    PREP_SIZE = 17

    REG_ENVOI_BIT = 50
    REG_ENVOI_STATUS = 51

    REG_DELETE_BIT = 60
    REG_DELETE_STATUS = 61

    REG_RESET_BIT = 62
    REG_RESET_STATUS = 63

    QUEUE_BASE = 100
    SLOT_STRIDE = 20
    SLOT_SIZE = 17
    MAX_ORDERS = 20

    REG_WD_SS = 620

    STATUS_OK = 0
    STATUS_QUEUE_FULL = 1
    STATUS_BAD_DATETIME = 2
    STATUS_UNKNOWN_ATTRIBUTE = 3
    STATUS_ORDER_NOT_FOUND = 4

    EXECUTION_TOLERANCE_SEC = 2.0
    WD_TIMEOUT_SEC = 30.0

    def __init__(self, modbus_context, cascade_controller):
        self.context = modbus_context
        self.cascade = cascade_controller

        self.orders = []

        self._last_envoi_bit = 0
        self._last_delete_bit = 0
        self._last_reset_bit = 0

        self._last_watchdog_value = None
        self._last_watchdog_change = time.time()
        self._watchdog_alarm_raised = False

        self._initialize_registers()

    def _initialize_registers(self):
        self._write_register(self.REG_ENVOI_STATUS, self.STATUS_OK)
        self._write_register(self.REG_DELETE_STATUS, self.STATUS_OK)
        self._write_register(self.REG_RESET_STATUS, self.STATUS_OK)
        self._write_register(self.REG_ENVOI_BIT, 0)
        self._write_register(self.REG_DELETE_BIT, 0)
        self._write_register(self.REG_RESET_BIT, 0)
        self._sync_queue_to_modbus()

    def update(self):
        self._process_exchange_bits()
        self._execute_due_orders()
        self._monitor_steam_switch_watchdog()

    def _process_exchange_bits(self):
        envoi_bit = self._read_register(self.REG_ENVOI_BIT)
        if envoi_bit == 1 and self._last_envoi_bit == 0:
            self._handle_order_upsert()
        self._last_envoi_bit = envoi_bit

        delete_bit = self._read_register(self.REG_DELETE_BIT)
        if delete_bit == 1 and self._last_delete_bit == 0:
            self._handle_order_delete()
        self._last_delete_bit = delete_bit

        reset_bit = self._read_register(self.REG_RESET_BIT)
        if reset_bit == 1 and self._last_reset_bit == 0:
            self._handle_queue_reset()
        self._last_reset_bit = reset_bit

    def _handle_order_upsert(self):
        raw = self._read_registers(self.PREP_BASE, self.PREP_SIZE)
        order = self._decode_order(raw)

        if order is None:
            self._write_register(self.REG_ENVOI_STATUS, self.STATUS_BAD_DATETIME)
            self._write_register(self.REG_ENVOI_BIT, 0)
            print("[SCHEDULER] Rejected order: invalid datetime.")
            return

        if not self._validate_order_attributes(order):
            self._write_register(self.REG_ENVOI_STATUS, self.STATUS_UNKNOWN_ATTRIBUTE)
            self._write_register(self.REG_ENVOI_BIT, 0)
            print(f"[SCHEDULER] Rejected order {order['id']}: unknown attribute values.")
            return

        existing_idx = self._find_order_index(order["id"])
        if existing_idx is None:
            if len(self.orders) >= self.MAX_ORDERS:
                self._write_register(self.REG_ENVOI_STATUS, self.STATUS_QUEUE_FULL)
                self._write_register(self.REG_ENVOI_BIT, 0)
                print(f"[SCHEDULER] Queue full. Cannot insert order {order['id']}.")
                return
            self.orders.append(order)
            print(f"[SCHEDULER] Inserted order {order['id']} for {order['target_time']}.")
        else:
            previous = self.orders[existing_idx]
            order["created_at"] = previous["created_at"]
            self.orders[existing_idx] = order
            print(f"[SCHEDULER] Updated order {order['id']} for {order['target_time']}.")

        self._sort_orders()
        self._sync_queue_to_modbus()

        self._write_register(self.REG_ENVOI_STATUS, self.STATUS_OK)
        self._write_register(self.REG_ENVOI_BIT, 0)

    def _handle_order_delete(self):
        id_words = self._read_registers(self.PREP_BASE, 2)
        order_id = ((id_words[0] & 0xFFFF) << 16) | (id_words[1] & 0xFFFF)

        if order_id == 0:
            self._write_register(self.REG_DELETE_STATUS, self.STATUS_UNKNOWN_ATTRIBUTE)
            self._write_register(self.REG_DELETE_BIT, 0)
            print("[SCHEDULER] Delete rejected: order id is 0.")
            return

        existing_idx = self._find_order_index(order_id)
        if existing_idx is None:
            self._write_register(self.REG_DELETE_STATUS, self.STATUS_ORDER_NOT_FOUND)
            self._write_register(self.REG_DELETE_BIT, 0)
            print(f"[SCHEDULER] Delete ignored: order {order_id} not found.")
            return

        self.orders.pop(existing_idx)
        self._sort_orders()
        self._sync_queue_to_modbus()

        self._write_register(self.REG_DELETE_STATUS, self.STATUS_OK)
        self._write_register(self.REG_DELETE_BIT, 0)
        print(f"[SCHEDULER] Deleted order {order_id}.")

    def _handle_queue_reset(self):
        self.orders.clear()
        self._sync_queue_to_modbus()

        self._write_register(self.REG_RESET_STATUS, self.STATUS_OK)
        self._write_register(self.REG_RESET_BIT, 0)
        print("[SCHEDULER] Queue reset requested by SteamSwitch.")

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
        consigne = self._select_consigne(order)
        strategy, power_limit_kw, target_pressure = self._decode_consigne(consigne)

        if strategy is None:
            print(f"[SCHEDULER] Order {order['id']} skipped: no supported strategy in selected consigne.")
            return

        self.cascade.set_active_consigne(
            strategy_code=strategy,
            target_pressure=target_pressure,
            power_limit_kw=power_limit_kw,
            source_order_id=order["id"],
        )
        print(
            f"[SCHEDULER] Executed order {order['id']} -> strategy={strategy}, "
            f"limit={power_limit_kw}, target={target_pressure:.1f} bar"
        )

    def _select_consigne(self, order):
        # Simple degraded-mode logic:
        # - If priority boiler is faulted -> use C3
        # - If secondary boiler is faulted -> use C2
        # - Otherwise use C1
        primary_fault = self._is_boiler_faulted(1)
        secondary_fault = self._is_boiler_faulted(2)

        if primary_fault:
            return order["c3"]
        if secondary_fault:
            return order["c2"]
        return order["c1"]

    def _is_boiler_faulted(self, boiler_id):
        boiler = self.cascade.boilers.get(boiler_id)
        if boiler is None:
            return False
        return boiler.state == 99

    def _decode_consigne(self, consigne):
        mode_code = int(consigne[0])
        power_limit_kw = int(consigne[1]) if int(consigne[1]) > 0 else None

        pressure_raw = int(consigne[2])
        target_pressure = (pressure_raw / 10.0) if pressure_raw > 0 else self.cascade.target_pressure

        strategy_map = {
            0: self.cascade.active_strategy,
            1: "C1",
            2: "C2",
            3: "C3",
        }
        strategy = strategy_map.get(mode_code)
        return strategy, power_limit_kw, target_pressure

    def _decode_order(self, raw):
        order_id = ((raw[0] & 0xFFFF) << 16) | (raw[1] & 0xFFFF)
        if order_id == 0:
            order_id = int(time.time())

        try:
            target_time = datetime(
                int(raw[4]),
                int(raw[3]),
                int(raw[2]),
                int(raw[5]),
                int(raw[6]),
                int(raw[7]),
            )
        except ValueError:
            return None

        now = datetime.now()
        return {
            "id": order_id,
            "target_time": target_time,
            "c1": [int(raw[8]), int(raw[9]), int(raw[10])],
            "c2": [int(raw[11]), int(raw[12]), int(raw[13])],
            "c3": [int(raw[14]), int(raw[15]), int(raw[16])],
            "created_at": now,
            "updated_at": now,
        }

    def _validate_order_attributes(self, order):
        all_attrs = order["c1"] + order["c2"] + order["c3"]
        for value in all_attrs:
            if value < 0 or value > 10000:
                return False

        # Keep pressure fields in a realistic industrial range [0.0, 20.0] bar
        for pressure_word in (order["c1"][2], order["c2"][2], order["c3"][2]):
            if pressure_word < 0 or pressure_word > 200:
                return False

        return True

    def _find_order_index(self, order_id):
        for idx, existing in enumerate(self.orders):
            if existing["id"] == order_id:
                return idx
        return None

    def _sort_orders(self):
        self.orders.sort(key=lambda o: (o["target_time"], o["updated_at"]))

    def _sync_queue_to_modbus(self):
        for idx in range(self.MAX_ORDERS):
            reg = self.QUEUE_BASE + (idx * self.SLOT_STRIDE)

            if idx < len(self.orders):
                payload = self._serialize_order(self.orders[idx])
                slot = payload + ([0] * (self.SLOT_STRIDE - len(payload)))
            else:
                slot = [0] * self.SLOT_STRIDE

            self._write_registers(reg, slot)

    def _serialize_order(self, order):
        order_id = int(order["id"])
        target = order["target_time"]

        return [
            (order_id >> 16) & 0xFFFF,
            order_id & 0xFFFF,
            target.day,
            target.month,
            target.year,
            target.hour,
            target.minute,
            target.second,
            int(order["c1"][0]),
            int(order["c1"][1]),
            int(order["c1"][2]),
            int(order["c2"][0]),
            int(order["c2"][1]),
            int(order["c2"][2]),
            int(order["c3"][0]),
            int(order["c3"][1]),
            int(order["c3"][2]),
        ]

    def _monitor_steam_switch_watchdog(self):
        wd_value = self._read_register(self.REG_WD_SS)
        now = time.time()

        if wd_value != self._last_watchdog_value:
            self._last_watchdog_value = wd_value
            self._last_watchdog_change = now
            if self._watchdog_alarm_raised:
                self._watchdog_alarm_raised = False
                print("[WATCHDOG] SteamSwitch link recovered (%MW620 moving again).")
            return

        if (now - self._last_watchdog_change) > self.WD_TIMEOUT_SEC and not self._watchdog_alarm_raised:
            self._watchdog_alarm_raised = True
            print("[WATCHDOG] ALERT: SteamSwitch watchdog (%MW620) frozen for >30s.")

    def _read_register(self, address):
        return self._read_registers(address, 1)[0]

    def _read_registers(self, address, count):
        try:
            return self.context[0].getValues(3, address, count=count)
        except Exception as exc:
            print(f"[SCHEDULER] Read error at {address} ({count}): {exc}")
            return [0] * count

    def _write_register(self, address, value):
        self._write_registers(address, [int(value)])

    def _write_registers(self, address, values):
        try:
            self.context[0].setValues(3, address, list(values))
        except Exception as exc:
            print(f"[SCHEDULER] Write error at {address} ({len(values)}): {exc}")
