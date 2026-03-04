import asyncio
import aiomqtt
import ssl
import json
import random

BROKER_HOST = "mosquitto.cascadya.internal"
BROKER_PORT = 8883
NUM_SITES = 200

# Préparation du contexte SSL pour la librairie asynchrone
tls_context = ssl.create_default_context(cafile="../ca.crt")
tls_context.load_cert_chain(certfile="../client.crt", keyfile="../client.key")

async def simulate_site(site_id: int):
    """Gère un site industriel de manière asynchrone"""
    client_id = f"async-site-{site_id}"
    topic = f"cascadya/site/Site_{site_id}/telemetry"
    
    try:
        # aiomqtt v2.0+ utilise "identifier" au lieu de "client_id"
        async with aiomqtt.Client(
            hostname=BROKER_HOST, 
            port=BROKER_PORT, 
            identifier=client_id,  # <-- Le correctif est ici !
            tls_context=tls_context
        ) as client:
            
            print(f"✅ Connecté : Site_{site_id}")
            
            while True:
                payload = {
                    "site": f"Site_{site_id}",
                    "production_rate": round(random.uniform(50.0, 100.0), 2),
                    "status": "ASYNC_OK"
                }
                
                # Envoi du message de manière non bloquante
                await client.publish(topic, json.dumps(payload), qos=1)
                
                # Pause asynchrone aléatoire (entre 2 et 10 secondes)
                await asyncio.sleep(random.uniform(2.0, 10.0))
                
    except Exception as e:
        print(f"❌ Déconnexion ou Erreur sur Site_{site_id}: {e}")

async def main():
    """Point d'entrée de la boucle asynchrone"""
    print(f"🚀 Lancement de la simulation asynchrone pour {NUM_SITES} sites...")
    
    # On crée la liste des 200 coroutines (tâches) à exécuter en parallèle
    tasks = [simulate_site(i) for i in range(1, NUM_SITES + 1)]
    
    # asyncio.gather lance tout en même temps
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        # Lancement de l'Event Loop
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Arrêt de la simulation de masse.")