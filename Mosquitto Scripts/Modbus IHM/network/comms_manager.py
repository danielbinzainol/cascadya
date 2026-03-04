import threading
import asyncio
import queue
import json
from network.nats_client import AsyncNatsClient

class CommsManager:
    def __init__(self):
        # La file d'attente sécurisée entre le Thread Réseau et le Thread IHM
        self.rx_queue = queue.Queue() 
        self.client = AsyncNatsClient()
        self.loop = None
        self.thread = None
        self._is_running = False

    def start(self):
        """Lance le réseau dans un Thread séparé pour ne pas bloquer l'IHM"""
        self._is_running = True
        self.thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.thread.start()

    def _run_async_loop(self):
        """La boucle temporelle asynchrone qui tourne en arrière-plan"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # 1. Connexion initiale
        self.loop.run_until_complete(self.client.connect())
        
        # 2. Maintien en vie (Keep-Alive)
        async def keep_alive():
            while self._is_running:
                await asyncio.sleep(0.1)
            await self.client.disconnect()

        self.loop.run_until_complete(keep_alive())
        self.loop.close()

    def stop(self):
        """Arrête proprement le thread réseau"""
        self._is_running = False
        if self.thread:
            self.thread.join(timeout=2)

    # ==========================================
    # 📥 COMMANDES DEPUIS L'IHM
    # ==========================================
    def trigger_ping(self, valeur):
        """L'IHM appelle ça pour lancer un ping. C'est non-bloquant."""
        if not self.loop:
            return
        
        # On demande à la boucle asynchrone d'exécuter la fonction _async_ping
        asyncio.run_coroutine_threadsafe(self._async_ping(valeur), self.loop)

    async def _async_ping(self, valeur):
        """Exécuté dans le Thread réseau, puis envoyé dans la file d'attente"""
        resultat = await self.client.ping_watchdog(valeur)
        
        # On emballe le résultat et on le pousse dans le "tuyau" vers l'IHM
        message = {
            "type": "ping_result",
            "valeur_envoyee": valeur,
            "data": resultat
        }
        self.rx_queue.put(message)
    
    def send_command(self, topic, payload_dict):
        """Envoie une commande JSON vers n'importe quel topic NATS"""
        if not self.loop: return
        
        async def _async_send():
            payload = json.dumps(payload_dict).encode()
            # On utilise publish car on n'attend pas forcément de réponse immédiate ici
            await self.client.nc.publish(topic, payload)
            print(f"📤 [NATS] Commande publiée sur {topic}")

        asyncio.run_coroutine_threadsafe(_async_send(), self.loop)