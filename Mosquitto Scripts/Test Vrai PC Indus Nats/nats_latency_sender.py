import asyncio
import json
import time
import ssl
import csv
import statistics
from nats.aio.client import Client as NATS

# ⚠️ À MODIFIER si nécessaire
NATS_URL = "tls://mosquitto.cascadya.internal:4222"

# Chemins des certificats côté WSL
tls_context = ssl.create_default_context(cafile="../ca.crt")
tls_context.load_cert_chain(certfile="../client.crt", keyfile="../client.key")
tls_context.check_hostname = False

# --- CONFIGURATION DU TEST ---
TOTAL_MESSAGES = 1000
SLEEP_BETWEEN_MSGS = 0.002 # 2ms entre chaque envoi pour éviter d'engorger le buffer local
# -----------------------------

rtt_results = []
received_count = 0

async def main():
    global received_count
    nc = NATS()
    await nc.connect(NATS_URL, tls=tls_context)
    print("✅ WSL Connecté en mTLS. Prêt pour l'audit.")

    test_complete = asyncio.Event()

    # 1. Callback de réception des ACKs
    async def ack_handler(msg):
        global received_count
        receive_ts = time.time()
        try:
            payload = json.loads(msg.data.decode())
            send_ts = payload.get("send_ts")
            
            if send_ts:
                rtt_ms = (receive_ts - send_ts) * 1000 # Conversion en millisecondes
                rtt_results.append(rtt_ms)
                received_count += 1
                
                # Feedback visuel
                if received_count % 200 == 0:
                    print(f"📥 {received_count}/{TOTAL_MESSAGES} ACKs reçus...")
                    
                if received_count == TOTAL_MESSAGES:
                    test_complete.set()
        except Exception:
            pass

    # Abonnement aux ACKs
    await nc.subscribe("cascadya.ack.pc_indus", cb=ack_handler)
    
    print(f"🚀 Début de l'envoi de {TOTAL_MESSAGES} pings vers le PC Industriel...")
    start_time = time.time()
    
    # 2. Envoi en rafale
    for i in range(TOTAL_MESSAGES):
        payload = {
            "instruction": "PING_ACTION",
            "send_ts": time.time(),
            "id": i
        }
        await nc.publish("cascadya.command.pc_indus", json.dumps(payload).encode())
        await asyncio.sleep(SLEEP_BETWEEN_MSGS)
        
    print("📤 Tous les messages ont été expédiés. Attente des derniers retours...")
    
    # Attente maximale de 5 secondes après le dernier envoi pour récupérer les retards
    try:
        await asyncio.wait_for(test_complete.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        print("⚠️ Timeout : Certains paquets se sont perdus en route.")

    end_time = time.time()
    total_test_duration = end_time - start_time

    # 3. Calcul des Métriques & Génération Excel
    if len(rtt_results) > 0:
        avg_rtt = statistics.mean(rtt_results)
        max_rtt = max(rtt_results)
        min_rtt = min(rtt_results)
        jitter = statistics.stdev(rtt_results) if len(rtt_results) > 1 else 0.0
        
        packet_loss = ((TOTAL_MESSAGES - received_count) / TOTAL_MESSAGES) * 100
        throughput = received_count / total_test_duration

        # Affichage Terminal
        print("\n" + "="*50)
        print("📊 RÉSULTATS DE L'AUDIT NATS mTLS (EDGE <-> HQ)")
        print("="*50)
        print(f"Messages envoyés : {TOTAL_MESSAGES}")
        print(f"Messages reçus   : {received_count}")
        print(f"Perte de paquets : {packet_loss:.2f} %")
        print(f"Débit global     : {throughput:.2f} msg/sec")
        print("-" * 50)
        print(f"Latence Moyenne  : {avg_rtt:.2f} ms")
        print(f"Latence Min      : {min_rtt:.2f} ms")
        print(f"Latence Max      : {max_rtt:.2f} ms")
        print(f"Jitter (Gigue)   : {jitter:.2f} ms")
        print("="*50)

        # Création du fichier CSV
        csv_filename = "audit_metrics_rtt.csv"
        with open(csv_filename, mode='w', newline='') as file:
            writer = csv.writer(file, delimiter=';') # Point-virgule idéal pour Excel FR
            writer.writerow(["Metrique", "Valeur", "Unite"])
            writer.writerow(["Messages Envoyes", TOTAL_MESSAGES, "msg"])
            writer.writerow(["Messages Recus", received_count, "msg"])
            writer.writerow(["Perte de paquets", round(packet_loss, 2), "%"])
            writer.writerow(["Debit Global", round(throughput, 2), "msg/sec"])
            writer.writerow(["Latence Moyenne (RTT)", round(avg_rtt, 2), "ms"])
            writer.writerow(["Latence Minimum", round(min_rtt, 2), "ms"])
            writer.writerow(["Latence Maximum", round(max_rtt, 2), "ms"])
            writer.writerow(["Jitter (Stabilité)", round(jitter, 2), "ms"])
            
        print(f"\n📁 Fichier d'audit Excel généré avec succès : {csv_filename}")
    else:
        print("❌ Aucun ACK reçu, impossible de calculer les métriques.")

    await nc.drain()

if __name__ == '__main__':
    asyncio.run(main())