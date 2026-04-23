import asyncio
import json
import time
import ssl
import csv
import statistics
from nats.aio.client import Client as NATS

NATS_URL = "tls://10.42.1.6:4222"
TOTAL_PINGS = 1000
# On attend les réponses de ces deux IDs
EXPECTED_NODES = ["PC_INDUS", "WSL_CLIENT"]

results = {node: [] for node in EXPECTED_NODES}

async def main():
    nc = NATS()
    ssl_ctx = ssl.create_default_context(cafile="../ca.crt")
    ssl_ctx.load_cert_chain(certfile="../client.crt", keyfile="../client.key")
    ssl_ctx.check_hostname = False
    await nc.connect(NATS_URL, tls=ssl_ctx)

    async def ack_handler(msg):
        receive_ts = time.time()
        data = json.loads(msg.data.decode())
        node_id = data.get("node_id")
        send_ts = data.get("send_ts")
        if node_id in results:
            results[node_id].append((receive_ts - send_ts) * 1000)

    # On écoute les ACKs de tous les nœuds
    for node in EXPECTED_NODES:
        await nc.subscribe(f"audit.ack.{node}", cb=ack_handler)

    print(f"🚀 Diffusion de {TOTAL_PINGS} pings vers {EXPECTED_NODES}...")
    for i in range(TOTAL_PINGS):
        payload = {"send_ts": time.time(), "id": i}
        await nc.publish("audit.ping.broadcast", json.dumps(payload).encode())
        await asyncio.sleep(0.01)

    print("Wait for ACKs...")
    await asyncio.sleep(3)

    # Export CSV
    with open("audit_nats_1toM.csv", "w", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Node", "Avg RTT (ms)", "Min", "Max", "Jitter", "Loss %"])
        for node, rtts in results.items():
            loss = ((TOTAL_PINGS - len(rtts)) / TOTAL_PINGS) * 100
            avg = statistics.mean(rtts) if rtts else 0
            jitter = statistics.stdev(rtts) if len(rtts) > 1 else 0
            writer.writerow([node, round(avg,2), round(min(rtts or [0]),2), round(max(rtts or [0]),2), round(jitter,2), round(loss,2)])
            print(f"📊 {node} -> RTT Moyen: {avg:.2f}ms | Loss: {loss:.2f}%")

if __name__ == '__main__':
    asyncio.run(main())