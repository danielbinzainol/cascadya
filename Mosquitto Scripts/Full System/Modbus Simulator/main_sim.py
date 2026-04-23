import time
from threading import Thread

from pymodbus.datastore import ModbusServerContext, ModbusSequentialDataBlock, ModbusSlaveContext
from pymodbus.server.sync import StartTcpServer

from boiler_model import Boiler
from cascade_logic import CascadeController
from physics import SteamHeader
from scheduler import PlanificateurSBC


class SBCSimulator:
    def __init__(self):
        # Modbus memory block (1000 holding registers)
        self.store = ModbusSlaveContext(hr=ModbusSequentialDataBlock(0, [0] * 1000))
        self.context = ModbusServerContext(slaves=self.store, single=True)

        # Plant model
        self.header = SteamHeader(initial_pressure=5.0)
        self.header.set_factory_demand(800.0)

        self.boiler1 = Boiler(boiler_id=1, max_power_kw=400, ramp_rate=5.0)
        self.boiler2 = Boiler(boiler_id=2, max_power_kw=1000, ramp_rate=2.0)
        self.boiler3 = Boiler(boiler_id=3, max_power_kw=1000, ramp_rate=2.0)
        self.boilers = [self.boiler1, self.boiler2, self.boiler3]

        # L2 logic blocks
        self.cascade = CascadeController(self.header, self.boilers)
        self.scheduler = PlanificateurSBC(self.context, self.cascade)

    def modbus_telemetry_loop(self):
        """Continuously map simulator telemetry to Modbus registers."""
        while True:
            try:
                now = time.localtime()
                clock_data = [now.tm_mday, now.tm_mon, now.tm_year, now.tm_hour, now.tm_min, now.tm_sec]
                self.context[0].setValues(3, 602, clock_data)

                status = self.cascade.get_status_modbus()
                self.context[0].setValues(3, 100, [status["active_strategy"]])
                self.context[0].setValues(3, 400, [self.header.get_pressure_modbus()])
                self.context[0].setValues(3, 500, [self.header.get_demand_modbus()])

                for boiler in self.boilers:
                    base_reg = 400 + (boiler.id * 10)  # 410, 420, 430
                    state_data = boiler.get_state_modbus()
                    self.context[0].setValues(
                        3,
                        base_reg,
                        [state_data["state"], state_data["load"], state_data["target"]],
                    )
            except Exception as exc:
                print(f"[TELEMETRY ERROR] {exc}")

            time.sleep(1)

    def physics_and_control_loop(self):
        """Fast loop for scheduler + cascade + boiler + pressure model."""
        while True:
            try:
                #self.header.add_noise_to_demand(max_variation_kw=20)

                try:
                    manual_demand = self.context[0].getValues(3, 500, count=1)[0]
                    if abs(manual_demand - self.header.current_demand_kw) > 50:
                        self.header.set_factory_demand(manual_demand)
                except Exception:
                    pass

                self.scheduler.update()
                self.cascade.update()

                total_kw = 0.0
                for boiler in self.boilers:
                    boiler.update()
                    total_kw += boiler.get_output_kw()

                self.header.update(total_boiler_output_kw=total_kw)

            except Exception as exc:
                # Keep loop alive so command bits are still processed after transient errors.
                print(f"[PHYSICS LOOP ERROR] {exc}")

            time.sleep(0.5)

    def start(self):
        print("[SIM] Starting SBC/IBC physical simulator...")

        Thread(target=self.modbus_telemetry_loop, daemon=True).start()
        Thread(target=self.physics_and_control_loop, daemon=True).start()

        StartTcpServer(self.context, address=("0.0.0.0", 502))


if __name__ == "__main__":
    sim = SBCSimulator()
    sim.start()
