import asyncio
import json
import time
import ssl
import statistics
import csv
from nats.aio.client import Client as NATS

# CONFIGURATION
# PC INDUS: "tls://100.103.71.126:4222" | WSL: "tls://10.42.1.6:4222"
NATS_URL = "tls://10.42.1.6:4222" 
NODE_ID = "WSL_CLIENT" # Changez en "WSL_CLIENT" sur l'autre
CA_CERT = "../ca.crt" # Adaptez le chemin (../ca.crt pour WSL)
CLIENT_CERT = "../client.crt"
CLIENT_KEY = "../client.key"

TOTAL_MSGS = 1000
rtt_results = []

async def main():
    nc = NATS()
    ssl_ctx = ssl.create_default_context(cafile=CA_CERT)
    ssl_ctx.load_cert_chain(certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
    ssl_ctx.check_hostname = False
    await nc.connect(NATS_URL, tls=ssl_ctx)

    print(f"🚀 {NODE_ID} lance l'envoi de télémétrie...")
    
    for i in range(TOTAL_MSGS):
        start_ts = time.time()
        try:
            # On utilise request() pour mesurer le RTT individuel précisément
            response = await nc.request("audit.telemetry.in", json.dumps({"ts": start_ts}).encode(), timeout=2)
            rtt_results.append((time.time() - start_ts) * 1000)
        except:
            pass
        await asyncio.sleep(0.005) # Envoi rapide

    # Calcul final
    avg = statistics.mean(rtt_results)
    print(f"📊 Résultat {NODE_ID} -> RTT Moyen: {avg:.2f}ms")
    
    with open(f"audit_Mto1_{NODE_ID}.csv", "w") as f:
        f.write(f"Node;Avg_RTT\n{NODE_ID};{avg}")

if __name__ == '__main__':
    asyncio.run(main())