from unittest.mock import MagicMock, patch
from bridge.zabbix import ZabbixSender


def _make_sender():
    with patch("bridge.zabbix._ZabbixSender") as MockCls:
        mock_instance = MagicMock()
        MockCls.return_value = mock_instance
        sender = ZabbixSender("127.0.0.1", 10051, "MQTT-Bridge")
        return sender, mock_instance


def test_send_lld_uses_per_domain_discovery_key():
    sender, mock_pyzabbix = _make_sender()
    sender.send_lld("binary_sensor", '{"data": []}')
    mock_pyzabbix.send.assert_called_once()
    metric = mock_pyzabbix.send.call_args[0][0][0]
    assert metric.key == "esphome.discovery.binary_sensor"
    assert metric.host == "MQTT-Bridge"
    assert metric.value == '{"data": []}'


def test_send_value_sensor_key_unchanged():
    sender, mock_pyzabbix = _make_sender()
    sender.send_value("sensor", "esp32_k1_temp", "23.5")
    metric = mock_pyzabbix.send.call_args[0][0][0]
    assert metric.key == "esphome.sensor[esp32_k1_temp]"
    assert metric.host == "MQTT-Bridge"
    assert metric.value == "23.5"


def test_send_value_binary_key_per_domain():
    sender, mock_pyzabbix = _make_sender()
    sender.send_value("binary_sensor", "esp32_k1_door", "ON")
    metric = mock_pyzabbix.send.call_args[0][0][0]
    assert metric.key == "esphome.binary_sensor[esp32_k1_door]"
    assert metric.value == "ON"


def test_send_value_text_key_per_domain():
    sender, mock_pyzabbix = _make_sender()
    sender.send_value("text_sensor", "esp32_k1_status", "online")
    metric = mock_pyzabbix.send.call_args[0][0][0]
    assert metric.key == "esphome.text_sensor[esp32_k1_status]"


def test_send_lld_does_not_raise_on_exception():
    sender, mock_pyzabbix = _make_sender()
    mock_pyzabbix.send.side_effect = Exception("Connection refused")
    sender.send_lld("sensor", '{"data": []}')  # must not raise


def test_send_value_does_not_raise_on_exception():
    sender, mock_pyzabbix = _make_sender()
    mock_pyzabbix.send.side_effect = Exception("Connection refused")
    sender.send_value("sensor", "esp32_k1_temp", "23.5")  # must not raise
