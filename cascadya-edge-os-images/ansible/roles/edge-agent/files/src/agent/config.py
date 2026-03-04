from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseModel):
    site_id: str

    mqtt_host: str
    mqtt_port: int = 8883
    mqtt_client_id: str = "cascadya-agent"

    mqtt_ca_path: str
    mqtt_cert_path: str
    mqtt_key_path: str

    log_level: str = "INFO"

    max_setpoint_kw: float = 100.0
    safe_fallback_kw: float = 0.0


def load_settings() -> Settings:
    return Settings(
        site_id=os.environ["SITE_ID"],
        mqtt_host=os.environ["MQTT_HOST"],
        mqtt_port=int(os.environ.get("MQTT_PORT", "8883")),
        mqtt_client_id=os.environ.get("MQTT_CLIENT_ID", "cascadya-agent"),

        mqtt_ca_path=os.environ["MQTT_CA_PATH"],
        mqtt_cert_path=os.environ["MQTT_CERT_PATH"],
        mqtt_key_path=os.environ["MQTT_KEY_PATH"],

        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        max_setpoint_kw=float(os.environ.get("MAX_SETPOINT_KW", "100.0")),
        safe_fallback_kw=float(os.environ.get("SAFE_FALLBACK_KW", "0.0")),
    )
