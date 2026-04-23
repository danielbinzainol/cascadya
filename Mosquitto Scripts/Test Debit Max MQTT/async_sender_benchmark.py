import asyncio
import aiomqtt
import ssl
import json
import time

BROKER_HOST = "mosquitto.cascadya.internal"
BROKER_PORT = 8883

# ==========================================
# ⚙️ REGLAGES DU TEST DE CHARGE
# ==========================================
NUM_SITES = 200             # Nombre de sites connectés en même temps
DELAY_BETWEEN_MSGS = 0.1    # 0.1 seconde = 10 messages par seconde par site
                            # Total théorique : 200 * 10 = 2000 msg/sec
# ==========================================

tls_context = ssl.create_default_context(cafile="../ca.crt")
tls_context.load_cert_chain(certfile="../client.crt", keyfile="../client.key")

async def simulate_site(site_id: int):
    client_id = f"bench-site-{site_id}"
    topic = f"cascadya/site/Site_{site_id}/telemetry"
    
    try:
        async with aiomqtt.Client(
            hostname=BROKER_HOST, 
            port=BROKER_PORT, 
            identifier=client_id, 
            tls_context=tls_context
        ) as client:
            
            while True:
                payload = {"site": f"Site_{site_id}", "status": "BENCHMARK"}
                # QoS 0 pour envoyer massivement sans attendre la confirmation
                await client.publish(topic, json.dumps(payload), qos=0)
                await asyncio.sleep(DELAY_BETWEEN_MSGS)
                
    except Exception:
        # On passe les erreurs sous silence pour ne pas polluer l'écran pendant le test
        pass

async def main():
    print(f"🚀 Démarrage du Stress Test...")
    print(f"🏭 Sites simulés : {NUM_SITES}")
    print(f"⏱️ Cadence prévue : {NUM_SITES * (1/DELAY_BETWEEN_MSGS):.0f} msg/seconde au total")
    
    tasks = [simulate_site(i) for i in range(1, NUM_SITES + 1)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Arrêt du générateur.")