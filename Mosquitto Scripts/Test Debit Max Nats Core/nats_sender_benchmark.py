import asyncio
import json
import ssl
from nats.aio.client import Client as NATS

# Attention : bien utiliser tls://
NATS_URL = "tls://mosquitto.cascadya.internal:4222"
NUM_SITES = 200
DELAY_BETWEEN_MSGS = 0.05 # 20 msg/sec par site = 4000 msg/sec total !

# Préparation du contexte TLS (mTLS)
tls_context = ssl.create_default_context(cafile="../ca.crt")
tls_context.load_cert_chain(certfile="../client.crt", keyfile="../client.key")
tls_context.check_hostname = False
async def main():
    nc = NATS()
    
    print(f"🔌 Connexion à NATS ({NATS_URL})...")
    # Ajout du paramètre tls=tls_context
    await nc.connect(NATS_URL, tls=tls_context)
    print("✅ Connecté en mTLS !")

    async def simulate_site(site_id):
        topic = f"cascadya.site.Site_{site_id}.telemetry"
        while True:
            payload = json.dumps({"site": f"Site_{site_id}", "status": "NATS_BENCHMARK"}).encode()
            # NATS publie nativement en asynchrone, ultra rapide
            await nc.publish(topic, payload)
            await asyncio.sleep(DELAY_BETWEEN_MSGS)

    print(f"🚀 Lancement de {NUM_SITES} sites...")
    tasks = [simulate_site(i) for i in range(1, NUM_SITES + 1)]
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Arrêt du test NATS.")