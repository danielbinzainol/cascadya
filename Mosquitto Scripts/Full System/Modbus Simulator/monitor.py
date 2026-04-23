import os
import time

from pymodbus.client.sync import ModbusTcpClient


STATE_MAP = {
    0: "OFF",
    1: "PURGING",
    2: "IGNITING",
    3: "RUNNING",
    4: "COOLDOWN",
    99: "FAULT",
}


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def read_regs(client, address, count):
    response = client.read_holding_registers(address, count)
    if response.isError():
        return [0] * count
    return response.registers


def run_monitor():
    client = ModbusTcpClient("127.0.0.1", port=502)

    if not client.connect():
        print("Cannot connect to local simulator on 127.0.0.1:502")
        return

    while True:
        try:
            pressure_raw = read_regs(client, 400, 1)[0]
            demand_kw = read_regs(client, 500, 1)[0]
            pressure = pressure_raw / 10.0

            h, m, s = read_regs(client, 605, 3)

            b1_state, b1_load, b1_target = read_regs(client, 410, 3)
            b2_state, b2_load, b2_target = read_regs(client, 420, 3)
            b3_state, b3_load, b3_target = read_regs(client, 430, 3)

            envoi_status = read_regs(client, 51, 1)[0]
            delete_status = read_regs(client, 61, 1)[0]
            reset_status = read_regs(client, 63, 1)[0]

            order_words = read_regs(client, 100, 2)
            first_order_id = ((order_words[0] & 0xFFFF) << 16) | (order_words[1] & 0xFFFF)

            clear_screen()
            print("==============================================================")
            print(f" DIGITAL TWIN MONITOR | SBC Time: {h:02d}:{m:02d}:{s:02d}")
            print("==============================================================")
            print(f" Steam Header Pressure : {pressure:.1f} bar")
            print(f" Factory Demand       : {demand_kw:4d} kW")
            print(f" Queue Head Order ID  : {first_order_id}")
            print("--------------------------------------------------------------")
            print(
                f" IBC1 (400kW) : {STATE_MAP.get(b1_state, 'UNKNOWN'):<9} "
                f"Load={b1_load:3d}% Target={b1_target:3d}%"
            )
            print(
                f" IBC2 (1MW)   : {STATE_MAP.get(b2_state, 'UNKNOWN'):<9} "
                f"Load={b2_load:3d}% Target={b2_target:3d}%"
            )
            print(
                f" IBC3 (1MW)   : {STATE_MAP.get(b3_state, 'UNKNOWN'):<9} "
                f"Load={b3_load:3d}% Target={b3_target:3d}%"
            )
            print("--------------------------------------------------------------")
            print(
                f" Status %MW51={envoi_status} | %MW61={delete_status} | %MW63={reset_status}"
            )
            print("Press CTRL+C to exit")

        except Exception as exc:
            print(f"Monitor read error: {exc}")

        time.sleep(0.5)


if __name__ == "__main__":
    run_monitor()
