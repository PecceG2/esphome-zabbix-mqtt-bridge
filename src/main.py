import logging
from bridge.config import load_config
from bridge.discovery import DiscoveryRegistry
from bridge.zabbix import ZabbixSender
from bridge.mqtt_client import MQTTClient


def main():
    config = load_config()
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting esphome-zabbix-mqtt-bridge")

    registry = DiscoveryRegistry()
    sender = ZabbixSender(config.zabbix_server, config.zabbix_port, config.zabbix_host)
    client = MQTTClient(config, registry, sender)
    client.start()


if __name__ == "__main__":
    main()
