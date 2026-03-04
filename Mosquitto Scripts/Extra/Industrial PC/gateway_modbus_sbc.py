import asyncio
import ssl
import json
import time
import os
from datetime import datetime
from pathlib import Path
from nats.aio.client import Client as NATS
from pymodbus.client import AsyncModbusTcpClient

# ==========================================
# 📂 CONFIGURATION DES CHEMINS
# ==========================================
BASE_DIR = Path(__file__).resolve().parent
CERTS_DIR = BASE_DIR / "certs"

CA_CERT     = str(CERTS_DIR / "ca.crt")
CLIENT_CERT = str(CERTS_DIR / "client.crt")
CLIENT_KEY  = str(CERTS_DIR / "client.key")

# ==========================================
# ⚙️ CONFIGURATION RÉSEAU
# ==========================================
NATS_URL   = "tls://100.103.71.126:4222" 
TOPIC_PING = "cascadya.routing.ping"
TOPIC_CMD  = "cascadya.routing.command"

MODBUS_IP   = "192.168.50.2"
MODBUS_PORT = 502

# ==========================================
# 🏗️ MAPPING REGISTRES (Note Technique)
# ==========================================
REG_ID_PREP    = 0    # %MW0 : ID unique UDINT (2 reg) [cite: 182]
REG_DATE_PREP  = 2    # %MW2-7 : Date préparation (6 reg) [cite: 182]
REG_C1_ATTR    = 8    # %MW8-10 : Consigne C1 (3 reg) [cite: 182, 202]
REG_C2_ATTR    = 11   # %MW11-13 : Consigne C2 (3 reg) [cite: 182, 202]
REG_C3_ATTR    = 14   # %MW14-16 : Consigne C3 (3 reg) [cite: 182, 202]
REG_ENVOI_BIT  = 50   # %MW50.0 : Bit d'envoi [cite: 188]
REG_SBC_SEC    = 607  # %MW607 : Secondes SBC (Watchdog) [cite: 316, 319]
REG_WD_SS      = 620  # %MW620 : Watchdog SteamSwitch (1Hz) [cite: 326, 327]

class SteamSwitchGateway:
    def __init__(self):
        self.nc = NATS()
        self.modbus = None
        self.wd_counter = 0
        self.last_sbc_sec = -1
        self.last_sbc_change = time.time()

    async def run_watchdog_ss(self):
        """Boucle 1Hz : Incrémente %MW620 pour prouver la vie du SteamSwitch """
        while True:
            if self.modbus and self.modbus.connected:
                try:
                    self.wd_counter = (self.wd_counter + 1) % 32767
                    # Retrait de 'slave' pour compatibilité directe
                    await self.modbus.write_register(address=REG_WD_SS, value=self.wd_counter)
                except Exception as e:
                    print(f"❌ Erreur Écriture Watchdog: {e}")
            await asyncio.sleep(1)

    async def monitor_sbc_clock(self):
        """Surveille %MW607. Alarme si l'automate est figé > 30s [cite: 320, 322, 331]"""
        while True:
            if self.modbus and self.modbus.connected:
                try:
                    res = await self.modbus.read_holding_registers(address=REG_SBC_SEC, count=1)
                    if not res.isError():
                        current_sec = res.registers[0]
                        if current_sec != self.last_sbc_sec:
                            self.last_sbc_sec = current_sec
                            self.last_sbc_change = time.time()
                        elif time.time() - self.last_sbc_change > 30:
                            print(f"⚠️ ALERTE : Liaison SBC perdue (Pas de changement en %MW607)")
                except Exception as e:
                    print(f"❌ Erreur Lecture Horloge: {e}")
            await asyncio.sleep(1)

    async def handle_command(self, msg):
        """Injecte l'ordre structuré dans le planificateur [cite: 141, 156]"""
        try:
            payload = json.loads(msg.data.decode())
            order_id = payload.get("id", int(time.time()))
            now = datetime.now()

            print(f"📥 Traitement Ordre ID {order_id}...")

            # 1. Écriture ID (UDINT sur 2 registres) [cite: 182]
            await self.modbus.write_registers(address=REG_ID_PREP, values=[order_id >> 16, order_id & 0xFFFF])
            
            # 2. Écriture DateHeure (6 registres) [cite: 182]
            await self.modbus.write_registers(address=REG_DATE_PREP, values=[now.day, now.month, now.year, now.hour, now.minute, now.second])

            # 3. Écriture Attributs C1, C2, C3 (3 registres chacun) [cite: 182]
            await self.modbus.write_registers(address=REG_C1_ATTR, values=payload.get("c1", [0, 0, 0]))
            await self.modbus.write_registers(address=REG_C2_ATTR, values=payload.get("c2", [0, 0, 0]))
            await self.modbus.write_registers(address=REG_C3_ATTR, values=payload.get("c3", [0, 0, 0]))

            # 4. Envoi final (bit 50) [cite: 188]
            await self.modbus.write_register(address=REG_ENVOI_BIT, value=1)
            print(f"🚀 Ordre {order_id} validé vers l'automate.")

        except Exception as e:
            print(f"❌ Erreur Commande : {e}")

    async def ping_handler(self, msg):
        """Diagnostic rapide pour l'IHM"""
        try:
            data = json.loads(msg.data.decode())
            valeur = data.get("compteur", 0)
            await self.modbus.write_register(address=REG_WD_SS, value=valeur)
            result = await self.modbus.read_holding_registers(address=REG_WD_SS, count=1)
            valeur_lue = result.registers[0] if not result.isError() else -1
            await self.nc.publish(msg.reply, json.dumps({"valeur_retour": valeur_lue, "status": "ok"}).encode())
        except Exception as e:
            await self.nc.publish(msg.reply, json.dumps({"status": "error", "message": str(e)}).encode())

    async def start(self):
        self.modbus = AsyncModbusTcpClient(MODBUS_IP, port=MODBUS_PORT)
        
        tls_ctx = ssl.create_default_context(cafile=CA_CERT)
        tls_ctx.load_cert_chain(CLIENT_CERT, CLIENT_KEY)
        tls_ctx.check_hostname = False

        print(f"🔄 Connexion Modbus ({MODBUS_IP})...")
        await self.modbus.connect()
        print(f"🔄 Connexion NATS TLS ({NATS_URL})...")
        await self.nc.connect(NATS_URL, tls=tls_ctx)
        
        await self.nc.subscribe(TOPIC_PING, cb=self.ping_handler)
        await self.nc.subscribe(TOPIC_CMD, cb=self.handle_command)
        
        print("✅ Passerelle SteamSwitch Opérationnelle.")

        await asyncio.gather(
            self.run_watchdog_ss(),
            self.monitor_sbc_clock()
        )

if __name__ == '__main__':
    gateway = SteamSwitchGateway()
    try:
        asyncio.run(gateway.start())
    except KeyboardInterrupt:
        print("\n🛑 Arrêt.")