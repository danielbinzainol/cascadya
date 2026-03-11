import asyncio
import json
import ssl
import os
from datetime import datetime, timezone
from pathlib import Path
from pymodbus.client import ModbusTcpClient
import nats

# --- CONFIGURATION DYNAMIQUE DES CHEMINS ---
BASE_DIR = Path(__file__).resolve().parent
CERTS_DIR = BASE_DIR / "certs"

CA_CERT     = str(CERTS_DIR / "ca.crt")
CLIENT_CERT = str(CERTS_DIR / "client.crt")
CLIENT_KEY  = str(CERTS_DIR / "client.key")

# --- CONFIGURATION RÉSEAU (Alignée sur la Gateway) ---
MODBUS_IP = "192.168.50.2"
MODBUS_PORT = 502
# Utilisation de l'IP Tailscale qui est confirmée comme fonctionnelle
NATS_URL = "tls://100.103.71.126:4222" 
NATS_TOPIC = "cascadya.telemetry.live"

def read_modbus_telemetry(client):
    """Lit les registres Modbus et retourne un dictionnaire de données."""
    try:
        # Lecture Pression (%MW400) et Demande (%MW500)
        res_pressure = client.read_holding_registers(400, count=1)
        res_demand = client.read_holding_registers(500, count=1)
        
        pressure = res_pressure.registers[0] / 10.0 if not res_pressure.isError() else 0.0
        demand_kw = res_demand.registers[0] if not res_demand.isError() else 0

        # LECTURE DE L'ORDRE STEAMSWITCH (%MW100)
        res_order = client.read_holding_registers(100, count=1)
        active_order = res_order.registers[0] if not res_order.isError() else 0

        # ---> LIGNE DE DEBUG À AJOUTER JUSTE ICI <---
        print(f"🛠️ DEBUG MW100 | Valeur lue: {active_order} | Erreur de lecture: {res_order.isError()}")
        # --------------------------------------------

        # Lecture IBC 1, 2, 3 (%MW410 à %MW432)
        res_b1 = client.read_holding_registers(410, count=3)
        res_b2 = client.read_holding_registers(420, count=3)
        res_b3 = client.read_holding_registers(430, count=3)

        b1_state, b1_load, b1_target = (0,0,0) if res_b1.isError() else res_b1.registers
        b2_state, b2_load, b2_target = (0,0,0) if res_b2.isError() else res_b2.registers
        b3_state, b3_load, b3_target = (0,0,0) if res_b3.isError() else res_b3.registers

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pressure_bar": pressure,
            "demand_kw": demand_kw,
            "active_order": active_order,
            "ibc1": {"state": b1_state, "load_pct": b1_load, "target_pct": b1_target},
            "ibc2": {"state": b2_state, "load_pct": b2_load, "target_pct": b2_target},
            "ibc3": {"state": b3_state, "load_pct": b3_load, "target_pct": b3_target}
        }
    except Exception as e:
        print(f"[ERREUR MODBUS] {e}")
        return None

async def main():
    print(f"🚀 Télémétrie : Connexion Modbus {MODBUS_IP}...")
    modbus_client = ModbusTcpClient(MODBUS_IP, port=MODBUS_PORT)
    if not modbus_client.connect():
        print("❌ Échec de la connexion Modbus.")
        return

    print(f"🔐 Initialisation mTLS vers {NATS_URL}...")
    
    # Configuration TLS Robuste
    tls_ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=CA_CERT)
    tls_ctx.load_cert_chain(certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
    
    # Obligatoire pour les connexions par IP
    tls_ctx.check_hostname = False
    tls_ctx.verify_mode = ssl.CERT_REQUIRED 

    try:
        print("📡 Connexion à NATS...")
        # On ajoute un connect_timeout important pour absorber la latence du VPN
        nc = await nats.connect(
            NATS_URL, 
            tls=tls_ctx, 
            connect_timeout=20,
            name="telemetry_publisher_edge"
        )
        print("✅ Connecté à NATS. Début de la publication (1Hz).")
        
        while True:
            data = read_modbus_telemetry(modbus_client)
            if data:
                payload = json.dumps(data).encode('utf-8')
                await nc.publish(NATS_TOPIC, payload)
                print(f"📊 {datetime.now().strftime('%H:%M:%S')} | Pression: {data['pressure_bar']} Bar")
            
            await asyncio.sleep(1)

    except Exception as e:
        print(f"❌ Erreur NATS/mTLS : {e}")
    finally:
        modbus_client.close()
        if 'nc' in locals():
            await nc.close()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nArrêt demandé.")