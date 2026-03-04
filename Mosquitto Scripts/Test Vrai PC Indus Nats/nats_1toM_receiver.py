import asyncio
import ssl
import json
from nats.aio.client import Client as NATS

# --- CONFIGURATION ---
# PC INDUS: "tls://100.103.71.126:4222" | WSL: "tls://10.42.1.6:4222"
NATS_URL = "tls://10.42.1.6:4222" 
NODE_ID = "WSL_CLIENT" # Changez en "WSL_CLIENT" sur l'autre machine
# PC INDUS: "certs/ca.crt" | WSL: "../ca.crt"
CA_CERT = "../ca.crt"
CLIENT_CERT = "../client.crt"
CLIENT_KEY = "../client.key"

async def main():
    nc = NATS()
    ssl_ctx = ssl.create_default_context(cafile=CA_CERT)
    ssl_ctx.load_cert_chain(certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
    ssl_ctx.check_hostname = False

    await nc.connect(NATS_URL, tls=ssl_ctx)
    print(f"✅ {NODE_ID} prêt pour l'audit One-to-Many...")

    async def handle_ping(msg):
        # On renvoie le message avec notre ID pour que le Sender sache qui a répondu
        data = json.loads(msg.data.decode())
        data["node_id"] = NODE_ID
        await nc.publish(f"audit.ack.{NODE_ID}", json.dumps(data).encode())

    await nc.subscribe("audit.ping.broadcast", cb=handle_ping)
    await asyncio.Future()

if __name__ == '__main__':
    asyncio.run(main())