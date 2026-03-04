import asyncio
import ssl
from nats.aio.client import Client as NATS

NATS_URL = "tls://10.42.1.6:4222"

async def main():
    nc = NATS()
    ssl_ctx = ssl.create_default_context(cafile="../ca.crt")
    ssl_ctx.load_cert_chain(certfile="../client.crt", keyfile="../client.key")
    ssl_ctx.check_hostname = False

    await nc.connect(NATS_URL, tls=ssl_ctx)
    print("✅ WSL QG prêt à recevoir la télémétrie de tous les sites...")

    async def handle_telemetry(msg):
        # On renvoie l'ACK immédiatement sur le sujet de réponse (Reply-To)
        if msg.reply:
            await nc.publish(msg.reply, msg.data)

    await nc.subscribe("audit.telemetry.in", cb=handle_telemetry)
    await asyncio.Future()

if __name__ == '__main__':
    asyncio.run(main())