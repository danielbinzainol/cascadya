import os
import time


def normalize_word_order(value):
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in {"low_word_first", "low_first", "lo_hi", "word_swap", "swapped"}:
        return "low_word_first"
    return "high_word_first"


U32_WORD_ORDER = normalize_word_order(os.getenv("MODBUS_U32_WORD_ORDER", os.getenv("MODBUS_WORD_ORDER", "low_word_first")))


def u32_to_words(value):
    value = int(value) & 0xFFFFFFFF
    high_word = (value >> 16) & 0xFFFF
    low_word = value & 0xFFFF
    if U32_WORD_ORDER == "low_word_first":
        return [low_word, high_word]
    return [high_word, low_word]


class CascadeController:
    def __init__(self, steam_header, boilers):
        self.header = steam_header
        self.boilers = {boiler.id: boiler for boiler in boilers}

        self.target_pressure = 5.3
        self.active_strategy = "C1"
        self.kp = 2000.0

        self.active_stages = 1
        self.high_load_timer = 0.0
        self.low_load_timer = 0.0
        self.CASCADE_DELAY_SEC = 10.0

        self.dynamic_power_limit_kw = None
        self.active_order_id = 0

        self.last_update_time = time.time()

    def set_active_consigne(self, strategy_code, target_pressure, power_limit_kw=None, source_order_id=0):
        if self.active_strategy != strategy_code:
            self.active_stages = 1
            self.high_load_timer = 0.0
            self.low_load_timer = 0.0

        self.active_strategy = strategy_code
        self.target_pressure = max(0.0, float(target_pressure))
        self.dynamic_power_limit_kw = None if power_limit_kw is None or float(power_limit_kw) <= 0 else float(power_limit_kw)
        self.active_order_id = int(source_order_id or 0)

    def get_sequence_and_limits(self):
        if self.active_strategy == "C1":
            sequence = [1, 2, 3]
            limits = {1: 400.0, 2: 1000.0, 3: 1000.0}
        elif self.active_strategy == "C2":
            sequence = [2, 3, 1]
            limits = {1: 0.0, 2: 1000.0, 3: 1000.0}
        elif self.active_strategy == "C3":
            sequence = [3]
            limits = {1: 0.0, 2: 0.0, 3: 1000.0}
        else:
            sequence = [1, 2, 3]
            limits = {1: 400.0, 2: 1000.0, 3: 1000.0}

        if self.dynamic_power_limit_kw is not None and sequence:
            priority_boiler = sequence[0]
            base_limit = limits.get(priority_boiler, self.boilers[priority_boiler].max_power_kw)
            limits[priority_boiler] = min(base_limit, self.dynamic_power_limit_kw)

        return sequence, limits

    def evaluate_cascade_stages(self, dt, sequence):
        total_load_pct = 0.0
        active_boiler_count = 0

        for index in range(self.active_stages):
            if index < len(sequence):
                boiler_id = sequence[index]
                total_load_pct += self.boilers[boiler_id].current_load
                active_boiler_count += 1

        avg_load = (total_load_pct / active_boiler_count) if active_boiler_count > 0 else 0.0

        if avg_load > 80.0 and self.active_stages < len(sequence):
            self.high_load_timer += dt
            if self.high_load_timer >= self.CASCADE_DELAY_SEC:
                self.active_stages += 1
                self.high_load_timer = 0.0
        else:
            self.high_load_timer = 0.0

        if avg_load < 25.0 and self.active_stages > 1:
            self.low_load_timer += dt
            if self.low_load_timer >= self.CASCADE_DELAY_SEC:
                self.active_stages -= 1
                self.low_load_timer = 0.0
        else:
            self.low_load_timer = 0.0

    def update(self):
        now = time.time()
        dt = now - self.last_update_time
        self.last_update_time = now

        sequence, power_limits = self.get_sequence_and_limits()
        self.evaluate_cascade_stages(dt, sequence)

        error = self.target_pressure - self.header.pressure_bar
        total_required_kw = max(0.0, error * self.kp)
        remaining_kw = total_required_kw

        for index, boiler_id in enumerate(sequence):
            boiler = self.boilers.get(boiler_id)
            if not boiler:
                continue

            if index >= self.active_stages or boiler.state == 99:
                boiler.set_target_load(0.0)
                continue

            limit_kw = power_limits.get(boiler_id, boiler.max_power_kw)
            effective_max_kw = min(boiler.max_power_kw, limit_kw)

            if remaining_kw > 0:
                load_kw = min(remaining_kw, effective_max_kw)
                load_percent = (load_kw / boiler.max_power_kw) * 100.0
                boiler.set_target_load(load_percent)
                remaining_kw -= load_kw
            else:
                boiler.set_target_load(0.0)

        for boiler_id, boiler in self.boilers.items():
            if boiler_id not in sequence:
                boiler.set_target_load(0.0)

    def get_status_modbus(self):
        strategy_map = {"C1": 1, "C2": 2, "C3": 3}
        order_id_first, order_id_second = u32_to_words(self.active_order_id)
        return {
            "active_strategy": strategy_map.get(self.active_strategy, 0),
            "target_pressure_modbus": int(self.target_pressure * 10),
            "active_stages": self.active_stages,
            "active_order_id_first": order_id_first,
            "active_order_id_second": order_id_second,
        }
