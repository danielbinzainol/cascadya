from pymodbus.client.sync import ModbusTcpClient


def inject_perturbation():
    client = ModbusTcpClient('127.0.0.1', port=502)
    client.connect()

    # Disturbance entrypoint defined by the simulator: %MW500 (factory demand in kW).
    demand_kw = 1200

    print(f"Injecting factory demand: {demand_kw} kW on %MW500...")
    client.write_register(500, demand_kw)

    client.close()
    print("Done. Observe pressure drop and cascade reaction in monitor.py.")


if __name__ == "__main__":
    inject_perturbation()
