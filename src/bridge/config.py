import os
from dataclasses import dataclass


@dataclass
class Config:
    mqtt_broker: str
    mqtt_port: int
    discovery_prefix: str
    zabbix_server: str
    zabbix_port: int
    zabbix_host: str
    log_level: str


def load_config() -> Config:
    required = ["MQTT_BROKER", "DISCOVERY_PREFIX", "ZABBIX_SERVER"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}"
        )
    return Config(
        mqtt_broker=os.environ["MQTT_BROKER"],
        mqtt_port=int(os.environ.get("MQTT_PORT", "1883")),
        discovery_prefix=os.environ["DISCOVERY_PREFIX"],
        zabbix_server=os.environ["ZABBIX_SERVER"],
        zabbix_port=int(os.environ.get("ZABBIX_PORT", "10051")),
        zabbix_host=os.environ.get("ZABBIX_HOST", "MQTT-Bridge"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
