import asyncio
import json
import ssl
from nats.aio.client import Client as NATS
from nats.js.errors import NotFoundError

NATS_URL = "tls://mosquitto.cascadya.internal:4222"
NUM_SITES = 200
DELAY_BETWEEN_MSGS = 0.05

tls_context = ssl.create_default_context(cafile="../ca.crt")
tls_context.load_cert_chain(certfile="../client.crt", keyfile="../client.key")
tls_context.check_hostname = False

async def main():
    nc = NATS()
    await nc.connect(NATS_URL, tls=tls_context)
    
    # 1. On initialise le contexte JetStream
    js = nc.jetstream()
    print("✅ Connecté à JetStream en mTLS !")

    # 2. On crée un "Stream" (un gros dossier) qui va capter tous les topics telemetry
    stream_name = "INDUSTRIE_TELEMETRY"
    try:
        await js.stream_info(stream_name)
    except NotFoundError:
        print(f"📦 Création du flux de stockage '{stream_name}' sur la VM...")
        await js.add_stream(name=stream_name, subjects=["cascadya.site.*.telemetry"])

    async def simulate_site(site_id):
        topic = f"cascadya.site.Site_{site_id}.telemetry"
        while True:
            payload = json.dumps({"site": f"Site_{site_id}", "status": "JETSTREAM_OK"}).encode()
            
            # 3. On publie via JetStream. Cela garantit que la VM a bien stocké le message (QoS 1)
            await js.publish(topic, payload)
            await asyncio.sleep(DELAY_BETWEEN_MSGS)

    print(f"🚀 Lancement de {NUM_SITES} sites avec persistance...")
    tasks = [simulate_site(i) for i in range(1, NUM_SITES + 1)]
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Arrêt du générateur.")