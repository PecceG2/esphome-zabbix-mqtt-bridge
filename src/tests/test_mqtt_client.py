import json
from unittest.mock import MagicMock, patch
from bridge.config import Config
from bridge.discovery import DiscoveryRegistry
from bridge.zabbix import ZabbixSender
from bridge.mqtt_client import MQTTClient


CONFIG = Config(
    mqtt_broker="localhost",
    mqtt_port=1883,
    discovery_prefix="zbx",
    zabbix_server="127.0.0.1",
    zabbix_port=10051,
    zabbix_host="MQTT-Bridge",
    log_level="INFO",
)

DISCOVERY_PAYLOAD = json.dumps({
    "unique_id": "esp32_k1_temp",
    "name": "Temperatura",
    "state_topic": "zbx/sensor/esp32_k1/temperatura/state",
}).encode()


def make_client():
    registry = DiscoveryRegistry()
    sender = MagicMock(spec=ZabbixSender)
    with patch("bridge.mqtt_client.mqtt.Client") as MockMQTT:
        mock_paho = MagicMock()
        MockMQTT.return_value = mock_paho
        client = MQTTClient(CONFIG, registry, sender)
    client._client = mock_paho
    return client, registry, sender, mock_paho


def test_on_connect_subscribes_to_all_three_domains():
    client, _, _, mock_paho = make_client()
    client._on_connect(mock_paho, None, None, 0)
    subscribed = [c.args[0] for c in mock_paho.subscribe.call_args_list]
    assert "zbx/sensor/+/+/config" in subscribed
    assert "zbx/binary_sensor/+/+/config" in subscribed
    assert "zbx/text_sensor/+/+/config" in subscribed


def test_on_connect_failed_rc_does_not_subscribe():
    client, _, _, mock_paho = make_client()
    client._on_connect(mock_paho, None, None, 5)
    mock_paho.subscribe.assert_not_called()


def test_handle_discovery_registers_sensor_and_sends_lld():
    client, registry, sender, mock_paho = make_client()
    client._handle_discovery("zbx/sensor/esp32_k1/temperatura/config", DISCOVERY_PAYLOAD)
    assert registry.get_by_state_topic("zbx/sensor/esp32_k1/temperatura/state") is not None
    sender.send_lld.assert_called_once()
    domain_arg, payload_arg = sender.send_lld.call_args[0]
    assert domain_arg == "sensor"
    ids = {r["{#SENSOR_ID}"] for r in json.loads(payload_arg)["data"]}
    assert ids == {"esp32_k1_temp"}
    mock_paho.subscribe.assert_called_with("zbx/sensor/esp32_k1/temperatura/state")


def test_handle_discovery_duplicate_skips_lld_and_subscribe():
    client, _, sender, mock_paho = make_client()
    client._handle_discovery("zbx/sensor/esp32_k1/temperatura/config", DISCOVERY_PAYLOAD)
    mock_paho.reset_mock()
    sender.reset_mock()
    client._handle_discovery("zbx/sensor/esp32_k1/temperatura/config", DISCOVERY_PAYLOAD)
    sender.send_lld.assert_not_called()
    mock_paho.subscribe.assert_not_called()


def test_handle_state_sends_value_for_known_topic():
    client, _, sender, mock_paho = make_client()
    client._handle_discovery("zbx/sensor/esp32_k1/temperatura/config", DISCOVERY_PAYLOAD)
    sender.reset_mock()
    client._handle_state("zbx/sensor/esp32_k1/temperatura/state", b"23.5")
    sender.send_value.assert_called_once_with("sensor", "esp32_k1_temp", "23.5")


def test_handle_state_ignores_unknown_topic():
    client, _, sender, _ = make_client()
    client._handle_state("zbx/sensor/unknown/topic/state", b"42")
    sender.send_value.assert_not_called()


def test_on_message_routes_config_to_discovery():
    client, registry, sender, mock_paho = make_client()
    msg = MagicMock()
    msg.topic = "zbx/sensor/esp32_k1/temperatura/config"
    msg.payload = DISCOVERY_PAYLOAD
    client._on_message(mock_paho, None, msg)
    sender.send_lld.assert_called_once()


def test_on_message_routes_state_to_value():
    client, _, sender, mock_paho = make_client()
    client._handle_discovery("zbx/sensor/esp32_k1/temperatura/config", DISCOVERY_PAYLOAD)
    sender.reset_mock()
    msg = MagicMock()
    msg.topic = "zbx/sensor/esp32_k1/temperatura/state"
    msg.payload = b"21.0"
    client._on_message(mock_paho, None, msg)
    sender.send_value.assert_called_once_with("sensor", "esp32_k1_temp", "21.0")


def test_credentials_set_when_provided():
    registry = DiscoveryRegistry()
    sender = MagicMock(spec=ZabbixSender)
    config_with_creds = Config(
        mqtt_broker="localhost",
        mqtt_port=1883,
        discovery_prefix="zbx",
        zabbix_server="127.0.0.1",
        zabbix_port=10051,
        zabbix_host="MQTT-Bridge",
        log_level="INFO",
        mqtt_user="myuser",
        mqtt_password="secret",
    )
    with patch("bridge.mqtt_client.mqtt.Client") as MockMQTT:
        mock_paho = MagicMock()
        MockMQTT.return_value = mock_paho
        MQTTClient(config_with_creds, registry, sender)
    mock_paho.username_pw_set.assert_called_once_with("myuser", "secret")


def test_credentials_not_set_when_absent():
    client, _, _, mock_paho = make_client()
    mock_paho.username_pw_set.assert_not_called()


def test_start_retries_on_connect_exception():
    client, _, _, mock_paho = make_client()
    mock_paho.connect.side_effect = [OSError("Name resolution failed"), None]
    mock_paho.loop_forever.return_value = None
    client.start()
    assert mock_paho.connect.call_count == 2
