import os
import struct
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

STRATEGY_MAP = {
    0: "NONE",
    1: "C1",
    2: "C2",
    3: "C3",
}

PROFILE_LABELS = {
    2: "2.5.*",
    3: "3.0.0",
    4: "4.0.0",
    5: "5.5.*",
    6: "6.0.0",
}

REG_PLC_CLOCK_BASE = 250
REG_PLC_WATCHDOG = 256
REG_SIM_PROCESS_OFFSET = 9200
REG_PLC_FAULT = 257
REG_PLC_FAULT_COUNT = 258
REG_PLC_ALARM = 259
REG_PLC_ALARM_COUNT = 260
REG_ADD_STATUS = 1045
REG_DELETE_STATUS = 1057
REG_RESET_STATUS = 1069

REG_REAL_PRESSURE_BASE = 388
REG_REAL_PRESSURE_ERROR = 390
REG_REAL_PRESSURE_PERCENT = 392
REG_REAL_LEVEL_BASE = 298
REG_REAL_CONDENSATE_LEVEL_BASE = 318
REG_REAL_RP08_STATE_BASE = 508
REG_REAL_RP08_LOAD = 512
REG_REAL_RP08_SETPOINT = 514
REG_REAL_RP08_BOOST = 516
REG_REAL_TT42_TEMP = 544
REG_REAL_TT43_TEMP = 554
REG_REAL_TV21_TEMP = 564
REG_REAL_ZT16_FEEDBACK = 574
REG_REAL_ZT16_ERROR = 576

REG_PLANNER_STATE = 8100
REG_PLANNER_CRC = 8101
REG_PLANNER_CRC_STATE = 8102
REG_QUEUE_BASE = 8120
QUEUE_SLOT_WORDS = 46

REG_SIM_PRESSURE = 9000
REG_SIM_DEMAND = 9001
REG_SIM_BOILER_BASE = 9010
REG_RUNTIME_BASE = 9070


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def read_regs(client, address, count):
    response = client.read_holding_registers(address, count)
    if response.isError():
        return [0] * count
    return response.registers


def sim_reg(real_register):
    return REG_SIM_PROCESS_OFFSET + int(real_register)


def normalize_float_word_order(value):
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in {"low_word_first", "low_first", "lo_hi", "word_swap", "swapped"}:
        return "low_word_first"
    return "high_word_first"


FLOAT_WORD_ORDER = normalize_float_word_order(os.getenv("MODBUS_FLOAT_WORD_ORDER", "low_word_first"))
U32_WORD_ORDER = normalize_float_word_order(
    os.getenv("MODBUS_U32_WORD_ORDER", os.getenv("MODBUS_WORD_ORDER", "low_word_first"))
)


def words_to_u32(first_word, second_word):
    if U32_WORD_ORDER == "low_word_first":
        high_word, low_word = second_word, first_word
    else:
        high_word, low_word = first_word, second_word
    return ((int(high_word) & 0xFFFF) << 16) | (int(low_word) & 0xFFFF)


def words_to_float(first_word, second_word):
    if FLOAT_WORD_ORDER == "low_word_first":
        high_word, low_word = second_word, first_word
    else:
        high_word, low_word = first_word, second_word
    raw = ((int(high_word) & 0xFFFF) << 16) | (int(low_word) & 0xFFFF)
    return struct.unpack(">f", struct.pack(">I", raw))[0]


def word_bit(word, bit):
    return 1 if (int(word) & (1 << int(bit))) else 0


def read_float(client, address):
    first_word, second_word = read_regs(client, address, 2)
    return words_to_float(first_word, second_word)


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


def decode_queue_head(words):
    order_id = words_to_u32(words[0], words[1])
    if order_id == 0:
        return {
            "id": 0,
            "profile": 0,
            "profile_label": "n/a",
            "power_limit_kw": 0.0,
            "elec_pressure_bar": 0.0,
            "met_type": 0,
            "met_pressure_bar": 0.0,
            "secours": 0,
            "status": 0,
            "crc16": 0,
        }

    profile = int(words[8])
    return {
        "id": order_id,
        "profile": profile,
        "profile_label": PROFILE_LABELS.get(profile, "unknown"),
        "power_limit_kw": round(words_to_float(words[10], words[11]), 3),
        "elec_pressure_bar": round(words_to_float(words[12], words[13]), 3),
        "met_type": int(round(words_to_float(words[20], words[21]))),
        "met_pressure_bar": round(words_to_float(words[22], words[23]), 3),
        "secours": int(words[28]),
        "status": int(words[44]),
        "crc16": planner_crc16(words),
    }


def run_monitor():
    client = ModbusTcpClient("127.0.0.1", port=502)

    if not client.connect():
        print("Cannot connect to local simulator on 127.0.0.1:502")
        return

    while True:
        try:
            pressure_raw = read_regs(client, REG_SIM_PRESSURE, 1)[0]
            demand_kw = read_regs(client, REG_SIM_DEMAND, 1)[0]
            pressure = pressure_raw / 10.0
            plc_fault, plc_fault_count, plc_alarm, plc_alarm_count = read_regs(
                client,
                sim_reg(REG_PLC_FAULT),
                4,
            )

            real_pressure = read_float(client, sim_reg(REG_REAL_PRESSURE_BASE))
            real_pressure_error = read_regs(client, sim_reg(REG_REAL_PRESSURE_ERROR), 1)[0]
            real_pressure_pct = read_float(client, sim_reg(REG_REAL_PRESSURE_PERCENT))
            water_level = read_float(client, sim_reg(REG_REAL_LEVEL_BASE))
            condensate_level = read_float(client, sim_reg(REG_REAL_CONDENSATE_LEVEL_BASE))

            rp08_state = read_regs(client, sim_reg(REG_REAL_RP08_STATE_BASE), 9)
            rp08_load = words_to_float(rp08_state[4], rp08_state[5])
            rp08_setpoint = words_to_float(rp08_state[6], rp08_state[7])
            rp08_boost = word_bit(rp08_state[8], 0)

            water_temp = read_float(client, sim_reg(REG_REAL_TT42_TEMP))
            flue_temp = read_float(client, sim_reg(REG_REAL_TT43_TEMP))
            steam_temp = read_float(client, sim_reg(REG_REAL_TV21_TEMP))
            zt16_feedback = read_float(client, sim_reg(REG_REAL_ZT16_FEEDBACK))
            zt16_error = read_regs(client, sim_reg(REG_REAL_ZT16_ERROR), 1)[0]

            year, month, day, hour, minute, second = read_regs(client, REG_PLC_CLOCK_BASE, 6)
            watchdog = read_regs(client, REG_PLC_WATCHDOG, 1)[0]

            b1_state, b1_load, b1_target = read_regs(client, REG_SIM_BOILER_BASE, 3)
            b2_state, b2_load, b2_target = read_regs(client, REG_SIM_BOILER_BASE + 10, 3)
            b3_state, b3_load, b3_target = read_regs(client, REG_SIM_BOILER_BASE + 20, 3)

            add_status = read_regs(client, REG_ADD_STATUS, 1)[0]
            delete_status = read_regs(client, REG_DELETE_STATUS, 1)[0]
            reset_status = read_regs(client, REG_RESET_STATUS, 1)[0]

            planner_state = read_regs(client, REG_PLANNER_STATE, 1)[0]
            planner_crc = read_regs(client, REG_PLANNER_CRC, 1)[0]
            planner_crc_state = read_regs(client, REG_PLANNER_CRC_STATE, 1)[0]

            queue_head = decode_queue_head(read_regs(client, REG_QUEUE_BASE, QUEUE_SLOT_WORDS))
            runtime_words = read_regs(client, REG_RUNTIME_BASE, 5)
            active_strategy = runtime_words[0]
            active_order_id = words_to_u32(runtime_words[1], runtime_words[2])
            target_pressure = runtime_words[3] / 10.0
            active_stages = runtime_words[4]

            clear_screen()
            print("==============================================================")
            print(
                " DIGITAL TWIN MONITOR | "
                f"SBC Time: {year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d} "
                f"| WD=%MW256:{watchdog}"
            )
            print("==============================================================")
            print(f" Steam Header Pressure : {pressure:.1f} bar       [%MW9000]")
            print(f" Factory Demand       : {demand_kw:4d} kW        [%MW9001]")
            print(
                " Rev02 PT01/RP08      : "
                f"PT01={real_pressure:.2f} bar ({real_pressure_pct:.1f}%) "
                f"[sim %MW{sim_reg(388)} -> real %MW388] | "
                f"RP08 load={rp08_load:.1f}% setpoint={rp08_setpoint:.2f} bar boost={rp08_boost} "
                f"[sim %MW{sim_reg(508)}-%MW{sim_reg(516)} -> real %MW508-%MW516]"
            )
            print(
                " Rev02 Levels/Temps   : "
                f"LT01={water_level:.1f}% [sim %MW{sim_reg(298)}] | "
                f"RN/LT27={condensate_level:.1f}% [sim %MW{sim_reg(318)}] | "
                f"TT42={water_temp:.1f}C TT43={flue_temp:.1f}C TV21={steam_temp:.1f}C"
            )
            print(
                " Rev02 PLC Health     : "
                f"defaut={word_bit(plc_fault, 0)} nb={plc_fault_count} | "
                f"alarme={word_bit(plc_alarm, 0)} nb={plc_alarm_count} | "
                f"PT01_err={word_bit(real_pressure_error, 0)} ZT16={zt16_feedback:.1f}% "
                f"ZT16_err={word_bit(zt16_error, 0)} "
                f"[sim %MW{sim_reg(257)}-%MW{sim_reg(260)} / %MW{sim_reg(574)}]"
            )
            print(
                " Planner State        : "
                f"state={planner_state} crc={planner_crc} crc_state={planner_crc_state} "
                "[%MW8100-%MW8102]"
            )
            print(f" Queue Head Order ID  : {queue_head['id']}         [slot0 %MW8120]")
            print(
                " Queue Head Profile   : "
                f"{queue_head['profile_label']} ({queue_head['profile']}) "
                f"C1-2={queue_head['power_limit_kw']}kW C1-3={queue_head['elec_pressure_bar']}bar "
                f"C2-2={queue_head['met_type']} C2-3={queue_head['met_pressure_bar']}bar "
                f"C3-1={queue_head['secours']} slot_status={queue_head['status']} "
                f"CRC16={queue_head['crc16']}"
            )
            print(
                f" Active Runtime       : strategy={STRATEGY_MAP.get(active_strategy, 'UNKNOWN'):<7} "
                f"order_id={active_order_id:<10d} target={target_pressure:>4.1f} bar "
                f"stages={active_stages} [%MW9070-%MW9074]"
            )
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
            print(f" Status %MW1045={add_status} | %MW1057={delete_status} | %MW1069={reset_status}")
            print("Press CTRL+C to exit")
        except Exception as exc:
            print(f"Monitor read error: {exc}")

        time.sleep(0.5)


if __name__ == "__main__":
    run_monitor()
