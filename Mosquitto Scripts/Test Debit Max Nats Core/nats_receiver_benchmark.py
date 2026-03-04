import asyncio
import ssl
from nats.aio.client import Client as NATS

NATS_URL = "tls://mosquitto.cascadya.internal:4222"

msg_count = 0

# Préparation du contexte TLS (mTLS)
tls_context = ssl.create_default_context(cafile="../ca.crt")
tls_context.load_cert_chain(certfile="../client.crt", keyfile="../client.key")
tls_context.check_hostname = False
async def monitor_throughput():
    global msg_count
    while True:
        await asyncio.sleep(1)
        print(f"⚡ Débit NATS : {msg_count} messages/seconde")
        msg_count = 0

async def main():
    nc = NATS()
    
    # Ajout du paramètre tls=tls_context
    await nc.connect(NATS_URL, tls=tls_context)
    print("✅ Connecté au serveur NATS en mTLS !")

    # Le callback qui gère la réception
    async def message_handler(msg):
        global msg_count
        msg_count += 1

    # NATS route lui-même les messages grâce au wildcard *
    await nc.subscribe("cascadya.site.*.telemetry", cb=message_handler)
    print("🎧 En écoute sur 'cascadya.site.*.telemetry'...")

    # Lancement du monitoring en tâche de fond
    asyncio.create_task(monitor_throughput())

    # Garder la connexion ouverte
    while True:
        await asyncio.sleep(1)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Fin de l'écoute.")