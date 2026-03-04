import asyncio
import ssl
import json
import time
from nats.aio.client import Client as NATS

# --- CONFIGURATION ---
# IP de la VM Broker (vue depuis WSL)
NATS_URL = "tls://10.42.1.6:4222" 
TOPIC = "cascadya.routing.ping"

# Chemins des certificats WSL
CA_CERT = "../ca.crt"
CLIENT_CERT = "../client.crt"
CLIENT_KEY = "../client.key"
# ---------------------

tls_context = ssl.create_default_context(cafile=CA_CERT)
tls_context.load_cert_chain(certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
tls_context.check_hostname = False

async def measure_ping():
    nc = NATS()
    await nc.connect(NATS_URL, tls=tls_context)
    print("✅ Connecté à NATS (VM Broker). Préparation du test de latence...\n")

    valeur_test = 99
    payload = json.dumps({"compteur": valeur_test}).encode()

    print(f"📤 Envoi de la valeur {valeur_test} au Modbus via NATS...")
    
    # ⏱️ DÉBUT DU CHRONO
    start_time = time.perf_counter()

    try:
        # Envoi de la requête et attente de la réponse (Timeout 2s)
        msg = await nc.request(TOPIC, payload, timeout=2.0)
        
        # ⏱️ FIN DU CHRONO
        end_time = time.perf_counter()

        data = json.loads(msg.data.decode())
        rtt_ms = (end_time - start_time) * 1000
        latence = rtt_ms / 2

        print("-------------------------------------------------")
        print(f"✅ RÉSULTAT : {data.get('status', 'inconnu').upper()}")
        
        # --- NOUVEAU : Lecture du message d'erreur ---
        if data.get('status') == 'error':
            print(f"🛑 RAISON DE L'ERREUR (Passerelle) : {data.get('message')}")
            print("🔴 Intégrité : ÉCHEC")
        else:
            print(f"📥 Valeur renvoyée par Modbus : {data.get('valeur_retour')}")
            
            if data.get('valeur_retour') == valeur_test:
                print("🟢 Intégrité : VALIDÉE (La valeur est intacte)")
            else:
                print("🔴 Intégrité : ÉCHEC (Valeur altérée)")
                
        print(f"⏱️ Temps total (Aller-Retour) : {rtt_ms:.2f} ms")
        print(f"⚡ Latence réseau (Un sens)  : ~{latence:.2f} ms")
        print("-------------------------------------------------")

    except Exception as e:
        print(f"\n❌ Erreur ou Délai d'attente dépassé : {e}")

    await nc.drain()

if __name__ == '__main__':
    asyncio.run(measure_ping())