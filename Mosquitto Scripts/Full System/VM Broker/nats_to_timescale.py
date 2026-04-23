import asyncio
import json
import ssl
import asyncpg
from nats.aio.client import Client as NATS
from datetime import datetime

# --- CONFIGURATION NATS ---
# Le broker tourne en local (Docker) sur cette VM (10.42.1.6)
NATS_URL = "tls://10.42.1.6:4222" 
TOPIC = "cascadya.telemetry.live"

# Chemins absolus recommandés pour le service SystemD
CA_CERT = "/home/ubuntu/ca.crt"
CLIENT_CERT = "/home/ubuntu/server.crt"
CLIENT_KEY = "/home/ubuntu/server.key"

# --- CONFIGURATION BASE DE DONNÉES (Paramètres explicites) ---
DB_CONFIG = {
    "host": "10.42.2.2",
    "port": 5432,
    "user": "cascadya",
    "password": "C4sc4dy4_Louvre!!2025",
    "database": "cascadya_telemetry"
}

async def main():
    print(f"🔌 Connexion à PostgreSQL ({DB_CONFIG['host']})...")
    try:
        # Utilisation des arguments nommés pour éviter les erreurs de parsing d'URL (caractères spéciaux)
        pool = await asyncpg.create_pool(**DB_CONFIG)
        print("✅ Connecté à PostgreSQL.")
    except Exception as e:
        print(f"❌ Erreur DB détaillée : {e}")
        return

    # Configuration TLS pour NATS
    tls_context = ssl.create_default_context(cafile=CA_CERT)
    tls_context.load_cert_chain(certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
    tls_context.check_hostname = False

    nc = NATS()
    print(f"📡 Connexion à NATS ({NATS_URL})...")
    try:
        await nc.connect(NATS_URL, tls=tls_context)
        print(f"✅ Connecté à NATS. En écoute sur '{TOPIC}'...")
    except Exception as e:
        print(f"❌ Erreur NATS : {e}")
        return

    async def message_handler(msg):
        try:
            # Décoder le message JSON
            data = json.loads(msg.data.decode())
            
            # Convertir le string timestamp en objet datetime Python pour TimescaleDB
            dt = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

            # On utilise get() avec une valeur par défaut de 0 au cas où l'edge n'est pas encore mis à jour
            active_order = data.get("active_order", 0)

            query = """
                INSERT INTO telemetry_sbc (
                    time, pressure_bar, demand_kw, active_order,
                    ibc1_state, ibc1_load_pct, ibc1_target_pct,
                    ibc2_state, ibc2_load_pct, ibc2_target_pct,
                    ibc3_state, ibc3_load_pct, ibc3_target_pct
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """
            
            async with pool.acquire() as connection:
                await connection.execute(
                    query,
                    dt,                      # $1
                    data["pressure_bar"],    # $2
                    data["demand_kw"],       # $3
                    active_order,            # $4 <-- NOUVEAU PARAMÈTRE
                    data["ibc1"]["state"],   # $5
                    data["ibc1"]["load_pct"],# $6
                    data["ibc1"]["target_pct"], # $7
                    data["ibc2"]["state"],   # $8
                    data["ibc2"]["load_pct"],# $9
                    data["ibc2"]["target_pct"], # $10
                    data["ibc3"]["state"],   # $11
                    data["ibc3"]["load_pct"],# $12
                    data["ibc3"]["target_pct"]  # $13
                )
            print(f"💾 Inséré en DB : {dt} | {data['pressure_bar']} Bar | Ordre: C{active_order}")
            
        except Exception as e:
            print(f"⚠️ Erreur lors du traitement du message : {e}")

    # Inscription au sujet NATS
    await nc.subscribe(TOPIC, cb=message_handler)

    # Maintenir le script en vie
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        print("🛑 Fermeture des connexions...")
        await nc.drain()
        await pool.close()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass