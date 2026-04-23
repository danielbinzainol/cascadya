import time
from threading import Thread

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext
from pymodbus.server.sync import ModbusTcpServer, StartTcpServer

from boiler_model import Boiler
from cascade_logic import CascadeController
from physics import SteamHeader
from rev02_process import Rev02ProcessMirror
from scheduler import PlanificateurSBC


REG_PLC_MODE = 238
REG_PLC_PLANIF = 245
REG_PLC_CLOCK_BASE = 250
REG_PLC_WATCHDOG = 256

# Digital-twin-only extension area. The official Rev02 table owns the low and
# planner ranges, so simulator telemetry is kept high to avoid collisions.
REG_SIM_PRESSURE = 9000
REG_SIM_DEMAND = 9001
REG_SIM_BOILER_BASE = 9010
REG_RUNTIME_BASE = 9070
REG_ACTIVE_STRATEGY = REG_RUNTIME_BASE + 0
REG_ACTIVE_ORDER_ID_FIRST = REG_RUNTIME_BASE + 1
REG_ACTIVE_ORDER_ID_SECOND = REG_RUNTIME_BASE + 2
REG_TARGET_PRESSURE = REG_RUNTIME_BASE + 3
REG_ACTIVE_STAGES = REG_RUNTIME_BASE + 4


class SBCSimulator:
    def __init__(self):
        self.store = ModbusSlaveContext(hr=ModbusSequentialDataBlock(0, [0] * 10000))
        self.context = ModbusServerContext(slaves=self.store, single=True)
        self.watchdog_counter = 0

        self.header = SteamHeader(initial_pressure=5.0)
        self.header.set_factory_demand(420.0)

        self.boiler1 = Boiler(boiler_id=1, max_power_kw=400, ramp_rate=5.0)
        self.boiler2 = Boiler(boiler_id=2, max_power_kw=1000, ramp_rate=2.0)
        self.boiler3 = Boiler(boiler_id=3, max_power_kw=1000, ramp_rate=2.0)
        self.boilers = [self.boiler1, self.boiler2, self.boiler3]

        self.cascade = CascadeController(self.header, self.boilers)
        self.scheduler = PlanificateurSBC(self.context, self.cascade)
        self.rev02_process = Rev02ProcessMirror(self.context, self.header, self.cascade, self.boilers)

    def modbus_telemetry_loop(self):
        while True:
            try:
                now = time.localtime()
                clock_data = [now.tm_year, now.tm_mon, now.tm_mday, now.tm_hour, now.tm_min, now.tm_sec]
                self.watchdog_counter = (self.watchdog_counter + 1) & 0xFFFF

                self.context[0].setValues(3, REG_PLC_MODE, [1])
                self.context[0].setValues(3, REG_PLC_PLANIF, [1 << 8])
                self.context[0].setValues(3, REG_PLC_CLOCK_BASE, clock_data)
                self.context[0].setValues(3, REG_PLC_WATCHDOG, [self.watchdog_counter])

                status = self.cascade.get_status_modbus()
                self.context[0].setValues(
                    3,
                    REG_RUNTIME_BASE,
                    [
                        status["active_strategy"],
                        status["active_order_id_first"],
                        status["active_order_id_second"],
                        status["target_pressure_modbus"],
                        status["active_stages"],
                    ],
                )
                self.context[0].setValues(3, REG_SIM_PRESSURE, [self.header.get_pressure_modbus()])
                self.context[0].setValues(3, REG_SIM_DEMAND, [self.header.get_demand_modbus()])

                for boiler in self.boilers:
                    base_reg = REG_SIM_BOILER_BASE + ((boiler.id - 1) * 10)
                    state_data = boiler.get_state_modbus()
                    self.context[0].setValues(
                        3,
                        base_reg,
                        [state_data["state"], state_data["load"], state_data["target"]],
                    )

                self.rev02_process.update()
            except Exception as exc:
                print(f"[TELEMETRY ERROR] {exc}")

            time.sleep(1)

    def physics_and_control_loop(self):
        while True:
            try:
                try:
                    manual_demand = self.context[0].getValues(3, REG_SIM_DEMAND, count=1)[0]
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
                print(f"[PHYSICS LOOP ERROR] {exc}")

            time.sleep(0.5)

    def start(self):
        print("[SIM] Starting SBC/IBC physical simulator...")
        Thread(target=self.modbus_telemetry_loop, daemon=True).start()
        Thread(target=self.physics_and_control_loop, daemon=True).start()
        ModbusTcpServer.allow_reuse_address = True
        StartTcpServer(self.context, address=("0.0.0.0", 502))


if __name__ == "__main__":
    SBCSimulator().start()
