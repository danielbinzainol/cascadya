import math
import random
import time


class SteamHeader:
    def __init__(self, initial_pressure=5.0, volume_factor=0.0005, boiler_output_gain=14.0):
        self.pressure_bar = initial_pressure
        self.volume_factor = volume_factor
        self.boiler_output_gain = boiler_output_gain

        self.MAX_PRESSURE = 6.5
        self.MIN_PRESSURE = 0.0
        self.relief_valve_open = False

        self.start_time = time.time()
        self.base_demand_kw = 420.0
        self.current_demand_kw = self.base_demand_kw

        self.last_update_time = time.time()
        self.manual_override_until = 0.0

    def set_factory_demand(self, demand_kw):
        self.current_demand_kw = max(0.0, demand_kw)
        self.manual_override_until = time.time() + 15.0

    def simulate_factory_cycle(self):
        if time.time() < self.manual_override_until:
            return

        elapsed = time.time() - self.start_time
        cycle = math.sin(elapsed / 60.0) * 160.0
        noise = random.uniform(-25.0, 25.0)
        total_demand = self.base_demand_kw + cycle + noise
        self.current_demand_kw = max(180.0, min(total_demand, 620.0))

    def update(self, total_boiler_output_kw):
        now = time.time()
        dt = now - self.last_update_time
        self.last_update_time = now

        self.simulate_factory_cycle()

        # C1-2 stays faithful to the Rev02 exchange table ([0;50] kW). The
        # simulator maps that command scale to an equivalent steam effect so the
        # digital twin remains demonstrable without changing the register contract.
        effective_boiler_output_kw = total_boiler_output_kw * self.boiler_output_gain
        net_energy_kw = effective_boiler_output_kw - self.current_demand_kw
        delta_p = net_energy_kw * self.volume_factor * dt
        self.pressure_bar += delta_p

        if self.pressure_bar >= self.MAX_PRESSURE:
            self.pressure_bar = self.MAX_PRESSURE
            self.relief_valve_open = True
        else:
            self.relief_valve_open = False

        if self.pressure_bar <= self.MIN_PRESSURE:
            self.pressure_bar = self.MIN_PRESSURE

    def get_pressure_modbus(self):
        return int(self.pressure_bar * 10)

    def get_demand_modbus(self):
        return int(self.current_demand_kw)
