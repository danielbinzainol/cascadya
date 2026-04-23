import math
import os
import struct
import time


def normalize_float_word_order(value):
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in {"low_word_first", "low_first", "lo_hi", "word_swap", "swapped"}:
        return "low_word_first"
    return "high_word_first"


FLOAT_WORD_ORDER = normalize_float_word_order(os.getenv("MODBUS_FLOAT_WORD_ORDER", "low_word_first"))


def float_to_words(value):
    packed = struct.pack(">f", float(value))
    raw = struct.unpack(">I", packed)[0]
    high_word = (raw >> 16) & 0xFFFF
    low_word = raw & 0xFFFF
    if FLOAT_WORD_ORDER == "low_word_first":
        return [low_word, high_word]
    return [high_word, low_word]


class Rev02ProcessMirror:
    """Expose the Rev02 process registers in a shifted simulator namespace.

    This class intentionally does not touch the official planner contract
    (%MW1000+, %MW1044/%MW1056/%MW1068, %MW8100+, %MW8120+). It also does not
    write the real LCI process registers (%MW0-%MW581). Every process value is
    shifted to the high simulator area to create an addressing safety barrier.
    """

    SIM_PROCESS_OFFSET = 9200

    REG_GLOBAL_FAULT = 257
    REG_GLOBAL_FAULT_COUNT = 258
    REG_GLOBAL_ALARM = 259
    REG_GLOBAL_ALARM_COUNT = 260
    REG_GLOBAL_EVENT = 261
    REG_GLOBAL_EVENT_COUNT = 262

    REG_PT01_PRESSURE = 388
    REG_PT01_ERROR = 390
    REG_PT01_PERCENT = 392
    REG_PT01_THRESH_HIGH = 394
    REG_PT01_THRESH_LOW = 395

    REG_RP08_STATE_BASE = 508
    REG_RP08_LOAD = 512
    REG_RP08_SETPOINT = 514
    REG_RP08_BOOST = 516
    REG_RP08_BOOST_ON_1 = 518
    REG_RP08_BOOST_OFF_1 = 520
    REG_RP08_BOOST_ON_2 = 522
    REG_RP08_BOOST_OFF_2 = 524

    REG_TT42_TEMP = 544
    REG_TT42_ERROR = 546
    REG_TT42_PERCENT = 548
    REG_TT42_THRESH_HIGH = 550
    REG_TT42_THRESH_LOW = 551

    REG_TT43_TEMP = 554
    REG_TT43_ERROR = 556
    REG_TT43_PERCENT = 558
    REG_TT43_THRESH_HIGH = 560
    REG_TT43_THRESH_LOW = 561

    REG_TV21_TEMP = 564
    REG_TV21_ERROR = 566
    REG_TV21_PERCENT = 568
    REG_TV21_THRESH_HIGH = 570
    REG_TV21_THRESH_LOW = 571

    REG_ZT16_FEEDBACK = 574
    REG_ZT16_ERROR = 576
    REG_ZT16_PERCENT = 578
    REG_ZT16_THRESH_HIGH = 580
    REG_ZT16_THRESH_LOW = 581

    @classmethod
    def sim_register(cls, real_register):
        return cls.SIM_PROCESS_OFFSET + int(real_register)

    def __init__(self, modbus_context, steam_header, cascade_controller, boilers):
        self.context = modbus_context
        self.header = steam_header
        self.cascade = cascade_controller
        self.boilers = boilers

        self.start_time = time.time()
        self.last_update_time = time.time()
        self.water_level_pct = 66.0
        self.condensate_level_pct = 48.0
        self.feedwater_pump_running = False
        self.feedwater_pump_starts = 0
        self.thermo_start_count = 0
        self.thermo_running_previous = False
        self.thermo_runtime_sec = 0.0

    def update(self):
        now = time.time()
        dt = max(0.0, now - self.last_update_time)
        self.last_update_time = now

        total_output_kw = sum(boiler.get_output_kw() for boiler in self.boilers)
        total_capacity_kw = sum(boiler.max_power_kw for boiler in self.boilers) or 1.0
        load_pct = max(0.0, min(100.0, (total_output_kw / total_capacity_kw) * 100.0))
        target_pressure = float(self.cascade.target_pressure)
        pressure_bar = float(self.header.pressure_bar)
        pressure_pct = max(0.0, min(100.0, (pressure_bar / 18.0) * 100.0))

        self._update_water_balance(dt, total_output_kw)

        water_temp_c = max(20.0, min(190.0, 96.0 + (pressure_bar * 9.0) + (load_pct * 0.08)))
        flue_temp_c = max(45.0, min(280.0, 70.0 + (load_pct * 2.1)))
        steam_temp_c = max(20.0, min(180.0, water_temp_c - 8.0))

        thermo_running = load_pct > 1.0
        if thermo_running and not self.thermo_running_previous:
            self.thermo_start_count += 1
        self.thermo_running_previous = thermo_running
        if thermo_running:
            self.thermo_runtime_sec += dt

        alarm_active = self.water_level_pct < 25.0 or pressure_bar > 6.3
        fault_active = self.water_level_pct < 12.0 or pressure_bar > 6.6

        words = {}
        self._write_feedwater_and_condensate(words)
        self._write_counters(words)
        self._write_conditions_and_safety(words, pressure_bar, alarm_active, fault_active)
        self._write_global_state(words, alarm_active, fault_active)
        self._write_levels(words)
        self._write_pressure_sensors(words, pressure_bar, pressure_pct)
        self._write_rp08(words, load_pct, target_pressure, pressure_bar)
        self._write_temperatures(words, water_temp_c, flue_temp_c, steam_temp_c, load_pct)

        self._commit(words)

    def _update_water_balance(self, dt, total_output_kw):
        demand_kw = float(self.header.current_demand_kw)

        if self.feedwater_pump_running:
            if self.water_level_pct > 68.0:
                self.feedwater_pump_running = False
        elif self.water_level_pct < 45.0:
            self.feedwater_pump_running = True
            self.feedwater_pump_starts += 1

        steam_draw = (demand_kw / 9000.0) * dt
        evaporation = (total_output_kw / 18000.0) * dt
        feedwater = (1.1 if self.feedwater_pump_running else 0.0) * dt
        natural_return = 0.03 * math.sin((time.time() - self.start_time) / 45.0) * dt

        self.water_level_pct += feedwater + natural_return - steam_draw - evaporation
        self.water_level_pct = max(5.0, min(95.0, self.water_level_pct))

        self.condensate_level_pct = 52.0 + math.sin((time.time() - self.start_time) / 75.0) * 8.0

    def _write_feedwater_and_condensate(self, words):
        self._set_bool(words, 0, 0, True)       # BA05_Z0_AUTO_0
        self._set_bool(words, 0, 8, False)      # BA05_Z0_MANU_0
        self._set_bool(words, 1, 0, False)      # BA05_Z0_DESACT_0
        self._set_word(words, 2, 4)             # BA05_Z0_CFBA_0: PID level with analog valve
        self._set_bool(words, 3, 0, self.feedwater_pump_running)
        self._set_bool(words, 3, 8, not self.feedwater_pump_running)
        self._set_bool(words, 10, 0, self.water_level_pct < 20.0)
        self._set_bool(words, 10, 8, self.water_level_pct > 78.0)
        self._set_bool(words, 11, 0, self.water_level_pct > 90.0)
        self._set_bool(words, 11, 8, self.water_level_pct < 12.0)
        self._set_bool(words, 12, 0, False)
        self._set_bool(words, 12, 8, False)

        self._set_word(words, 50, 2)            # BB02_CONFIG: automatic pump alternation
        self._set_bool(words, 51, 0, True)
        self._set_bool(words, 51, 8, False)
        self._set_bool(words, 52, 0, False)
        self._set_bool(words, 52, 8, self.feedwater_pump_running)
        self._set_bool(words, 53, 0, not self.feedwater_pump_running)
        self._set_bool(words, 53, 8, self.feedwater_pump_running)
        self._set_bool(words, 54, 0, not self.feedwater_pump_running)
        self._set_bool(words, 54, 8, False)
        self._set_bool(words, 55, 0, False)
        self._set_bool(words, 55, 8, False)
        self._set_bool(words, 56, 0, False)
        self._set_bool(words, 56, 8, False)
        self._set_bool(words, 57, 0, True)
        self._set_bool(words, 57, 8, False)
        self._set_bool(words, 58, 0, self.condensate_level_pct > 90.0)
        self._set_bool(words, 58, 8, self.condensate_level_pct < 12.0)
        self._set_bool(words, 59, 0, False)
        self._set_bool(words, 59, 8, False)

    def _write_counters(self, words):
        elapsed_h = (time.time() - self.start_time) / 3600.0
        thermo_h = self.thermo_runtime_sec / 3600.0
        thermo_min = self.thermo_runtime_sec / 60.0

        self._set_real(words, 88, self.thermo_start_count)
        self._set_real(words, 90, self.thermo_start_count)
        self._set_real(words, 92, self.thermo_start_count)
        self._set_real(words, 94, thermo_h)
        self._set_real(words, 96, thermo_h)
        self._set_real(words, 98, thermo_min)
        self._set_real(words, 100, thermo_h)
        self._set_real(words, 102, 0.0)
        self._set_real(words, 104, 0.0)
        self._set_real(words, 106, 0.0)

        self._set_real(words, 110, self.feedwater_pump_starts)
        self._set_real(words, 112, self.feedwater_pump_starts)
        self._set_real(words, 114, 0.0)
        self._set_real(words, 116, self.feedwater_pump_starts)
        self._set_real(words, 118, elapsed_h if self.feedwater_pump_running else 0.0)
        self._set_real(words, 120, elapsed_h if self.feedwater_pump_running else 0.0)
        self._set_real(words, 122, elapsed_h if self.feedwater_pump_running else 0.0)
        self._set_real(words, 124, elapsed_h * 60.0 if self.feedwater_pump_running else 0.0)
        self._set_real(words, 126, 0.0)
        self._set_real(words, 128, 0.0)

        makeup_m3 = max(0.0, self.feedwater_pump_starts * 0.08 + elapsed_h * 0.15)
        self._set_real(words, 132, makeup_m3)
        self._set_real(words, 134, makeup_m3)
        self._set_real(words, 136, 0.0)
        self._set_real(words, 138, makeup_m3)
        self._set_bool(words, 142, 0, self.thermo_running_previous)

        self._set_real(words, 276, self.thermo_start_count)
        self._set_real(words, 278, self.thermo_start_count)
        self._set_real(words, 280, self.thermo_start_count)
        self._set_real(words, 282, thermo_h)
        self._set_real(words, 284, thermo_h)
        self._set_real(words, 286, thermo_min)
        self._set_real(words, 288, thermo_h)
        self._set_real(words, 290, 0.0)
        self._set_real(words, 292, 0.0)
        self._set_real(words, 294, 0.0)

    def _write_conditions_and_safety(self, words, pressure_bar, alarm_active, fault_active):
        self._set_bool(words, 150, 0, False)
        self._set_bool(words, 150, 8, False)
        self._set_bool(words, 152, 0, False)
        self._set_bool(words, 154, 0, False)
        self._set_bool(words, 156, 0, False)
        self._set_bool(words, 158, 0, self.water_level_pct > 90.0)
        self._set_bool(words, 160, 0, False)
        self._set_bool(words, 160, 8, False)
        self._set_bool(words, 162, 0, self.water_level_pct < 20.0)
        self._set_bool(words, 162, 8, False)
        self._set_bool(words, 164, 0, False)
        self._set_bool(words, 166, 0, False)
        self._set_bool(words, 166, 8, False)
        self._set_bool(words, 168, 0, False)
        self._set_bool(words, 168, 8, False)

        # CS10 uses several inverse safety bits: 1 means normal for these rows.
        self._set_bool(words, 170, 0, True)
        self._set_bool(words, 170, 8, self.water_level_pct >= 12.0)
        self._set_bool(words, 171, 0, self.water_level_pct >= 12.0)
        self._set_bool(words, 172, 0, pressure_bar <= 6.6)
        self._set_bool(words, 173, 0, True)
        self._set_bool(words, 173, 8, True)
        self._set_bool(words, 174, 0, not fault_active)
        self._set_bool(words, 185, 0, False)
        self._set_word(words, 187, 7)
        self._set_word(words, 189, 7)
        self._set_word(words, 190, 7)
        self._set_word(words, 198, 7)
        self._set_bool(words, 201, 0, not fault_active)

        self._set_bool(words, 274, 0, False)
        self._set_bool(words, 274, 8, False)

        self._set_bool(words, 328, 0, False)
        self._set_bool(words, 328, 8, False)
        self._set_bool(words, 329, 0, False)
        self._set_bool(words, 329, 8, False)
        self._set_bool(words, 330, 0, False)
        self._set_bool(words, 330, 8, False)
        self._set_bool(words, 331, 0, False)
        self._set_bool(words, 331, 8, False)

        self._set_bool(words, 372, 0, self.water_level_pct < 12.0)
        self._set_bool(words, 372, 8, False)
        self._set_bool(words, 373, 0, False)
        self._set_bool(words, 373, 8, False)
        self._set_bool(words, 374, 0, False)
        self._set_bool(words, 374, 8, self.feedwater_pump_running)
        self._set_real(words, 376, 100.0 if self.feedwater_pump_running else 0.0)
        self._set_real(words, 378, pressure_bar)
        self._set_bool(words, 380, 0, False)
        self._set_bool(words, 380, 8, alarm_active)
        self._set_bool(words, 381, 0, False)
        self._set_bool(words, 381, 8, fault_active)

    def _write_global_state(self, words, alarm_active, fault_active):
        self._set_bool(words, self.REG_GLOBAL_FAULT, 0, fault_active)
        self._set_word(words, self.REG_GLOBAL_FAULT_COUNT, 1 if fault_active else 0)
        self._set_bool(words, self.REG_GLOBAL_ALARM, 0, alarm_active)
        self._set_word(words, self.REG_GLOBAL_ALARM_COUNT, 1 if alarm_active else 0)
        self._set_bool(words, self.REG_GLOBAL_EVENT, 0, True)
        self._set_word(words, self.REG_GLOBAL_EVENT_COUNT, int(time.time() - self.start_time) & 0xFFFF)

        self._set_bool(words, 263, 0, True)
        self._set_bool(words, 263, 8, False)
        self._set_bool(words, 264, 0, alarm_active)
        self._set_bool(words, 264, 8, fault_active)
        self._set_bool(words, 265, 0, False)
        self._set_bool(words, 265, 8, False)

    def _write_levels(self, words):
        level_pct = self.water_level_pct
        condensate = self.condensate_level_pct

        self._set_real(words, 298, level_pct)
        self._set_bool(words, 300, 0, False)
        self._set_real(words, 302, level_pct)
        self._set_bool(words, 304, 0, level_pct > 90.0)
        self._set_bool(words, 304, 8, level_pct > 78.0)
        self._set_bool(words, 305, 0, level_pct < 30.0)
        self._set_bool(words, 305, 8, level_pct < 15.0)

        level_mbar = max(0.0, level_pct * 1.2)
        self._set_real(words, 308, level_mbar)
        self._set_bool(words, 310, 0, False)
        self._set_real(words, 312, level_pct)
        self._set_bool(words, 314, 0, level_pct > 90.0)
        self._set_bool(words, 314, 8, level_pct > 78.0)
        self._set_bool(words, 315, 0, level_pct < 30.0)
        self._set_bool(words, 315, 8, level_pct < 15.0)

        self._set_real(words, 318, condensate * 1.1)
        self._set_bool(words, 320, 0, False)
        self._set_real(words, 322, condensate)
        self._set_bool(words, 324, 0, condensate > 92.0)
        self._set_bool(words, 324, 8, condensate > 80.0)
        self._set_bool(words, 325, 0, condensate < 25.0)
        self._set_bool(words, 325, 8, condensate < 12.0)

        self._set_bool(words, 490, 0, level_pct < 30.0)
        self._set_bool(words, 490, 8, level_pct > 78.0)
        self._set_bool(words, 491, 0, level_pct > 90.0)
        self._set_bool(words, 491, 8, False)
        self._set_bool(words, 492, 0, False)
        self._set_bool(words, 492, 8, True)
        self._set_bool(words, 493, 0, self.feedwater_pump_running)
        self._set_bool(words, 493, 8, not self.feedwater_pump_running)
        self._set_bool(words, 494, 0, self.feedwater_pump_running)
        self._set_bool(words, 494, 8, not self.feedwater_pump_running)
        self._set_bool(words, 495, 0, False)
        self._set_bool(words, 495, 8, level_pct < 15.0)
        self._set_real(words, 496, level_pct)

    def _write_pressure_sensors(self, words, pressure_bar, pressure_pct):
        sensors = [
            (388, 390, 392, 394, 395, pressure_bar),
            (398, 400, 402, 404, 405, pressure_bar + 0.03),
            (408, 410, 412, 414, 415, pressure_bar + 0.01),
            (418, 420, 422, 424, 425, pressure_bar - 0.02),
            (428, 430, 432, 434, 435, pressure_bar),
        ]

        for measure, error, percent, high, low, value in sensors:
            pct = max(0.0, min(100.0, (value / 18.0) * 100.0))
            self._set_real(words, measure, value)
            self._set_bool(words, error, 0, False)
            self._set_real(words, percent, pct if percent != 392 else pressure_pct)
            self._set_bool(words, high, 0, value > 6.4)
            self._set_bool(words, high, 8, value > 5.8)
            self._set_bool(words, low, 0, value < 1.0)
            self._set_bool(words, low, 8, value < 0.5)

    def _write_rp08(self, words, load_pct, target_pressure, pressure_bar):
        boost_active = pressure_bar < target_pressure - 0.4
        limiting = pressure_bar > target_pressure + 0.4

        self._set_bool(words, self.REG_RP08_STATE_BASE, 0, load_pct > 1.0)
        self._set_bool(words, self.REG_RP08_STATE_BASE, 8, load_pct < 5.0 and boost_active)
        self._set_bool(words, self.REG_RP08_STATE_BASE + 1, 0, limiting)
        self._set_bool(words, self.REG_RP08_STATE_BASE + 1, 8, True)
        self._set_bool(words, self.REG_RP08_STATE_BASE + 2, 0, False)
        self._set_bool(words, self.REG_RP08_STATE_BASE + 2, 8, False)
        self._set_real(words, self.REG_RP08_LOAD, load_pct)
        self._set_real(words, self.REG_RP08_SETPOINT, target_pressure)
        self._set_bool(words, self.REG_RP08_BOOST, 0, boost_active)
        self._set_real(words, self.REG_RP08_BOOST_ON_1, max(0.0, target_pressure - 0.5))
        self._set_real(words, self.REG_RP08_BOOST_OFF_1, target_pressure - 0.1)
        self._set_real(words, self.REG_RP08_BOOST_ON_2, max(0.0, target_pressure - 0.8))
        self._set_real(words, self.REG_RP08_BOOST_OFF_2, target_pressure)

    def _write_temperatures(self, words, water_temp_c, flue_temp_c, steam_temp_c, load_pct):
        temperatures = [
            (self.REG_TT42_TEMP, self.REG_TT42_ERROR, self.REG_TT42_PERCENT, self.REG_TT42_THRESH_HIGH, self.REG_TT42_THRESH_LOW, water_temp_c, 190.0),
            (self.REG_TT43_TEMP, self.REG_TT43_ERROR, self.REG_TT43_PERCENT, self.REG_TT43_THRESH_HIGH, self.REG_TT43_THRESH_LOW, flue_temp_c, 280.0),
            (self.REG_TV21_TEMP, self.REG_TV21_ERROR, self.REG_TV21_PERCENT, self.REG_TV21_THRESH_HIGH, self.REG_TV21_THRESH_LOW, steam_temp_c, 190.0),
        ]

        for measure, error, percent, high, low, value, max_value in temperatures:
            self._set_real(words, measure, value)
            self._set_bool(words, error, 0, False)
            self._set_real(words, percent, max(0.0, min(100.0, (value / max_value) * 100.0)))
            self._set_bool(words, high, 0, value > max_value * 0.95)
            self._set_bool(words, high, 8, value > max_value * 0.85)
            self._set_bool(words, low, 0, value < max_value * 0.20)
            self._set_bool(words, low, 8, value < max_value * 0.10)

        self._set_real(words, self.REG_ZT16_FEEDBACK, load_pct)
        self._set_bool(words, self.REG_ZT16_ERROR, 0, False)
        self._set_real(words, self.REG_ZT16_PERCENT, load_pct)
        self._set_bool(words, self.REG_ZT16_THRESH_HIGH, 0, load_pct > 95.0)
        self._set_bool(words, self.REG_ZT16_THRESH_HIGH, 8, load_pct > 80.0)
        self._set_bool(words, self.REG_ZT16_THRESH_LOW, 0, load_pct < 5.0)
        self._set_bool(words, self.REG_ZT16_THRESH_LOW, 8, load_pct < 1.0)

    def _set_word(self, words, address, value):
        words[int(address)] = int(value) & 0xFFFF

    def _set_bool(self, words, address, bit, active):
        address = int(address)
        bit = int(bit)
        current = words.get(address, 0)
        mask = 1 << bit
        if active:
            current |= mask
        else:
            current &= ~mask
        words[address] = current & 0xFFFF

    def _set_real(self, words, address, value):
        first_word, second_word = float_to_words(value)
        words[int(address)] = first_word
        words[int(address) + 1] = second_word

    def _commit(self, words):
        for address in sorted(words):
            try:
                self.context[0].setValues(3, self.sim_register(address), [words[address] & 0xFFFF])
            except Exception:
                continue
