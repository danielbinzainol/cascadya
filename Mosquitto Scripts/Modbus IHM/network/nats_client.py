import asyncio
import ssl
import json
import time
from nats.aio.client import Client as NATS
from config import settings

class AsyncNatsClient:
    def __init__(self):
        self.nc = NATS()
        # Chargement du contexte TLS depuis settings.py
        self.tls_context = ssl.create_default_context(cafile=settings.CA_CERT)
        self.tls_context.load_cert_chain(certfile=settings.CLIENT_CERT, keyfile=settings.CLIENT_KEY)
        self.tls_context.check_hostname = False

    async def connect(self):
        """Établit la connexion au Broker NATS"""
        try:
            await self.nc.connect(settings.NATS_URL, tls=self.tls_context)
            print("✅ [NATS] Connecté au Broker.")
            return True
        except Exception as e:
            print(f"❌ [NATS] Erreur de connexion : {e}")
            return False

    async def disconnect(self):
        """Ferme proprement la connexion"""
        if self.nc.is_connected:
            await self.nc.drain()
            print("🛑 [NATS] Déconnecté du Broker.")

    async def ping_watchdog(self, valeur):
        """Envoie la valeur au Modbus et chronomètre le RTT"""
        payload = json.dumps({"compteur": valeur}).encode()
        start_time = time.perf_counter()

        try:
            msg = await self.nc.request(settings.TOPIC_PING, payload, timeout=2.0)
            end_time = time.perf_counter()
            rtt_ms = (end_time - start_time) * 1000
            
            # On récupère le JSON renvoyé par le PC Industriel
            data = json.loads(msg.data.decode())
            data["rtt_ms"] = rtt_ms  # On ajoute la latence aux données
            return data

        except Exception as e:
            return {"status": "error", "message": str(e), "rtt_ms": 0.0}