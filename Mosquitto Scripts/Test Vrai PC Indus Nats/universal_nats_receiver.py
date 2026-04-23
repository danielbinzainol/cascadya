import asyncio
import ssl
from nats.aio.client import Client as NATS

# --- CONFIGURATION (À adapter selon la machine) ---
NATS_URL = "tls://10.42.1.6:4222" # Utiliser 100.103.71.126 pour le PC Indus
NODE_NAME = "RECEPTEUR_1" # Ex: "PC_INDUS", "WSL_CLIENT", "WSL_QG"
TOPIC = "cascadya.routing.test"

# Chemins des certificats (Mettre "certs/ca.crt" pour le PC Indus, ou "../ca.crt" pour le WSL)
CA_CERT = "../ca.crt"
CLIENT_CERT = "../client.crt"
CLIENT_KEY = "../client.key"
# --------------------------------------------------

tls_context = ssl.create_default_context(cafile=CA_CERT)
tls_context.load_cert_chain(certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
tls_context.check_hostname = False

async def main():
    nc = NATS()
    await nc.connect(NATS_URL, tls=tls_context)
    print(f"✅ [{NODE_NAME}] Connecté ! En écoute sur le topic '{TOPIC}'...")

    async def message_handler(msg):
        print(f"📥 [{NODE_NAME}] Reçu : {msg.data.decode()}")

    await nc.subscribe(TOPIC, cb=message_handler)
    
    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        pass
    finally:
        await nc.drain()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Fin de l'écoute.")