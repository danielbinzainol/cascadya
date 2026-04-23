import asyncio
import ssl
from nats.aio.client import Client as NATS

NATS_URL = "tls://mosquitto.cascadya.internal:4222"

msg_count = 0

tls_context = ssl.create_default_context(cafile="../ca.crt")
tls_context.load_cert_chain(certfile="../client.crt", keyfile="../client.key")
tls_context.check_hostname = False

async def monitor_throughput():
    global msg_count
    while True:
        await asyncio.sleep(1)
        print(f"💾 Débit JetStream : {msg_count} msg/s (Sauvegardés et Acquittés)")
        msg_count = 0

async def main():
    nc = NATS()
    await nc.connect(NATS_URL, tls=tls_context)
    
    # 1. Initialiser JetStream
    js = nc.jetstream()
    print("✅ Connecté au serveur JetStream en mTLS !")

    # Lancement du monitoring
    asyncio.create_task(monitor_throughput())

    # 2. S'abonner avec un nom durable (Persistance)
    print("🎧 En écoute persistante (Durable: loris_hq)...")
    sub = await js.subscribe("cascadya.site.*.telemetry", durable="loris_hq")

    # 3. Boucle de lecture des messages
    try:
        async for msg in sub.messages:
            global msg_count
            msg_count += 1
            
            # 4. TRÈS IMPORTANT : On dit à JetStream "C'est bon, j'ai lu ce message, tu peux passer au suivant"
            await msg.ack()
            
    except Exception as e:
        print(f"Erreur de lecture : {e}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Fin de l'écoute.")