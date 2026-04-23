import time


class BoilerState:
    OFF = 0
    PURGING = 1
    IGNITING = 2
    RUNNING = 3
    COOLDOWN = 4
    FAULT = 99


class Boiler:
    def __init__(self, boiler_id, max_power_kw, ramp_rate=2.0):
        self.id = boiler_id
        self.max_power_kw = max_power_kw
        self.ramp_rate = ramp_rate

        self.state = BoilerState.OFF
        self.current_load = 0.0
        self.target_load = 0.0

        self.state_timer = 0.0
        self.last_update_time = time.time()

        self.PURGE_TIME = 5.0
        self.IGNITE_TIME = 3.0
        self.COOLDOWN_TIME = 5.0

    def set_target_load(self, load_percent):
        self.target_load = max(0.0, min(100.0, load_percent))

    def trigger_fault(self):
        self.state = BoilerState.FAULT
        self.current_load = 0.0
        self.target_load = 0.0

    def clear_fault(self):
        if self.state == BoilerState.FAULT:
            self.state = BoilerState.OFF
            self.state_timer = 0.0

    def update(self):
        now = time.time()
        dt = now - self.last_update_time
        self.last_update_time = now

        if self.state == BoilerState.OFF:
            self.current_load = 0.0
            if self.target_load > 0:
                self.state = BoilerState.PURGING
                self.state_timer = 0.0

        elif self.state == BoilerState.PURGING:
            self.state_timer += dt
            if self.state_timer >= self.PURGE_TIME:
                self.state = BoilerState.IGNITING
                self.state_timer = 0.0
            if self.target_load == 0:
                self.state = BoilerState.OFF

        elif self.state == BoilerState.IGNITING:
            self.state_timer += dt
            if self.state_timer >= self.IGNITE_TIME:
                self.state = BoilerState.RUNNING
                self.state_timer = 0.0

        elif self.state == BoilerState.RUNNING:
            if self.target_load == 0:
                self.state = BoilerState.COOLDOWN
                self.state_timer = 0.0
            else:
                if self.current_load < self.target_load:
                    self.current_load += self.ramp_rate * dt
                    if self.current_load > self.target_load:
                        self.current_load = self.target_load
                elif self.current_load > self.target_load:
                    self.current_load -= self.ramp_rate * dt
                    if self.current_load < self.target_load:
                        self.current_load = self.target_load

        elif self.state == BoilerState.COOLDOWN:
            self.current_load = 0.0
            self.state_timer += dt
            if self.state_timer >= self.COOLDOWN_TIME:
                self.state = BoilerState.OFF
                self.state_timer = 0.0
            if self.target_load > 0:
                self.state = BoilerState.PURGING
                self.state_timer = 0.0

        elif self.state == BoilerState.FAULT:
            self.current_load = 0.0

    def get_output_kw(self):
        return (self.current_load / 100.0) * self.max_power_kw

    def get_state_modbus(self):
        return {
            "state": self.state,
            "load": int(self.current_load),
            "target": int(self.target_load),
        }
