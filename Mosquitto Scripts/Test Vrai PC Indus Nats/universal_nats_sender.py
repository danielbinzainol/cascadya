import asyncio
import ssl
from nats.aio.client import Client as NATS

# --- CONFIGURATION (À adapter selon la machine) ---
NATS_URL = "tls://10.42.1.6:4222" # Utiliser 100.103.71.126 pour le PC Indus
NODE_NAME = "EMETTEUR_1" # Ex: "PC_INDUS", "WSL_CLIENT", "WSL_QG"
TOPIC = "cascadya.routing.test"

# Chemins des certificats
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
    print(f"✅ [{NODE_NAME}] Connecté ! Prêt à diffuser...")

    for i in range(1, 6):
        payload = f"Message #{i} en provenance de {NODE_NAME}"
        await nc.publish(TOPIC, payload.encode())
        print(f"📤 [{NODE_NAME}] Publié : {payload}")
        await asyncio.sleep(1)

    await nc.drain()

if __name__ == '__main__':
    asyncio.run(main())