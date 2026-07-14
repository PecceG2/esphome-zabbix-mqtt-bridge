import json
import logging
import paho.mqtt.client as mqtt

from bridge.config import Config
from bridge.discovery import DiscoveryRegistry, classify_domain
from bridge.zabbix import ZabbixSender

logger = logging.getLogger(__name__)

DOMAINS = ["sensor", "binary_sensor", "text_sensor"]


class MQTTClient:
    def __init__(self, config: Config, registry: DiscoveryRegistry, sender: ZabbixSender):
        self._config = config
        self._registry = registry
        self._sender = sender
        self._client = mqtt.Client()
        if config.mqtt_user:
            self._client.username_pw_set(config.mqtt_user, config.mqtt_password)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            logger.error("MQTT connection failed with code %d", rc)
            return
        logger.info("Connected to MQTT broker at %s:%d", self._config.mqtt_broker, self._config.mqtt_port)
        for domain in DOMAINS:
            topic = f"{self._config.discovery_prefix}/{domain}/+/+/config"
            client.subscribe(topic)
            logger.info("Subscribed to %s", topic)

    def _on_message(self, client, userdata, msg):
        if msg.topic.endswith("/config"):
            self._handle_discovery(msg.topic, msg.payload)
        else:
            self._handle_state(msg.topic, msg.payload)

    def _handle_discovery(self, topic: str, payload: bytes):
        try:
            cfg = json.loads(payload)
            parts = topic.split("/")
            ha_component = parts[1]
            node = parts[2]
            domain = classify_domain(ha_component, cfg)
            is_new, entry = self._registry.register(domain, node, cfg)
            if not is_new:
                return
            logger.info("New sensor discovered: %s (%s, domain=%s)", entry.sensor_id, entry.name, entry.domain)
            self._sender.send_lld(entry.domain, self._registry.lld_payload(entry.domain))
            self._client.subscribe(entry.state_topic)
            logger.info("Subscribed to state topic: %s", entry.state_topic)
        except Exception as exc:
            logger.error("Error handling discovery on %s: %s", topic, exc)

    def _handle_state(self, topic: str, payload: bytes):
        entry = self._registry.get_by_state_topic(topic)
        if entry is None:
            return
        value = payload.decode()
        logger.debug("State update: %s = %s", entry.sensor_id, value)
        self._sender.send_value(entry.domain, entry.sensor_id, value)

    def start(self):
        import time
        self._client.reconnect_delay_set(min_delay=1, max_delay=128)
        delay = 1
        while True:
            try:
                self._client.connect(self._config.mqtt_broker, self._config.mqtt_port)
                break
            except Exception as exc:
                logger.error("Cannot connect to broker %s:%d, retrying in %ds: %s",
                             self._config.mqtt_broker, self._config.mqtt_port, delay, exc)
                time.sleep(delay)
                delay = min(delay * 2, 128)
        self._client.loop_forever()
