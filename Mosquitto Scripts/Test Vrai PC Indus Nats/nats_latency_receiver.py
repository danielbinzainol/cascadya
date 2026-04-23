import asyncio
import ssl
from nats.aio.client import Client as NATS

# ⚠️ À MODIFIER : Remplacez par l'IP de votre VM Broker si le DNS ne marche pas
NATS_URL = "tls://mosquitto.cascadya.internal:4222" 

# Chemins relatifs adaptés au PC Industriel (dossier certs/)
tls_context = ssl.create_default_context(cafile="certs/ca.crt")
tls_context.load_cert_chain(certfile="certs/client.crt", keyfile="certs/client.key")
tls_context.check_hostname = False

async def main():
    nc = NATS()
    try:
        await nc.connect(NATS_URL, tls=tls_context)
        print("✅ PC Industriel Connecté en mTLS (Nœud Écho prêt) !")
    except Exception as e:
        print(f"❌ Erreur de connexion : {e}")
        return

    async def command_handler(msg):
        # Renvoi immédiat du payload exact vers le topic ACK (pour le calcul du RTT)
        await nc.publish("cascadya.ack.pc_indus", msg.data)

    await nc.subscribe("cascadya.command.pc_indus", cb=command_handler)
    print("🎧 En attente des pings du WSL...")

    # Maintient le script en vie
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