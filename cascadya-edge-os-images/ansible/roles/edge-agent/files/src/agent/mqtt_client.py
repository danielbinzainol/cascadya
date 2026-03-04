import json
import logging
import asyncio
import ssl
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

log = logging.getLogger("mqtt")


class MqttClient:
    def __init__(
        self,
        executor,
        site_id: str,
        host: str,
        port: int,
        ca_path: str,
        cert_path: str,
        key_path: str,
        client_id: str,
    ):
        self.executor = executor
        self.site_id = site_id
        self.host = host
        self.port = port

        # 🔒 Client MQTT
        self.client = mqtt.Client(
            client_id=client_id,
            clean_session=False,
            protocol=mqtt.MQTTv311,
        )

        # 🔐 TLS mTLS (cert client + clé)
        self.client.tls_set(
            ca_certs=ca_path,
            certfile=cert_path,
            keyfile=key_path,
            tls_version=ssl.PROTOCOL_TLSv1_2,
        )

        # ⚠️ CA auto-signée → Python trop strict sinon
        self.client.tls_insecure_set(True)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self._last_seq = -1
        self.loop = asyncio.get_running_loop()

    # ------------------------
    def start(self):
        log.info("Connecting to MQTT %s:%s", self.host, self.port)
        self.client.connect(self.host, self.port, keepalive=30)
        self.client.loop_start()

    # ------------------------
    def on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            log.error("MQTT connection failed rc=%s", rc)
            return

        topic = f"cmd/{self.site_id}/setpoint"
        log.info("MQTT CONNECTED ✅ subscribing to %s", topic)
        client.subscribe(topic, qos=1)

    # ------------------------
    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())

            seq = int(payload["seq"])
            p_kw = float(payload["p_kw"])
            valid_to_ts = int(payload["valid_to"])
            grace_s = float(payload.get("grace_period_s", 0))

            if seq <= self._last_seq:
                log.warning("DROP old seq=%s last_seq=%s", seq, self._last_seq)
                return

            self._last_seq = seq
            valid_to = datetime.fromtimestamp(valid_to_ts, tz=timezone.utc)

            log.info("🔥 SETPOINT RECEIVED seq=%s p_kw=%.2f", seq, p_kw)

            # === LATENCE MQTT (5G) ===
            ts_send = payload.get("ts_send")
            if ts_send is not None:
                latency_ms = (time.time() - float(ts_send)) * 1000.0
                log.info("📡 MQTT latency (5G) = %.2f ms", latency_ms)

            self.loop.create_task(
                self.executor.schedule_write_setpoint(
                    p_kw=p_kw,
                    valid_to=valid_to,
                    grace_period_s=grace_s,
                )
            )

        except Exception:
            log.exception("Invalid MQTT message")

    # ------------------------
    def publish_json(self, topic: str, payload: dict, qos: int = 0):
        self.client.publish(topic, json.dumps(payload), qos=qos)

    def publish_raw(self, topic: str, payload: bytes, qos: int = 1):
        self.client.publish(topic, payload, qos=qos)
