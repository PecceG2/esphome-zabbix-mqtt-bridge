from unittest.mock import MagicMock, patch
from bridge.zabbix import ZabbixSender


def _make_sender():
    with patch("bridge.zabbix._ZabbixSender") as MockCls:
        mock_instance = MagicMock()
        MockCls.return_value = mock_instance
        sender = ZabbixSender("127.0.0.1", 10051, "MQTT-Bridge")
        return sender, mock_instance


def test_send_lld_uses_discovery_key():
    sender, mock_pyzabbix = _make_sender()
    sender.send_lld('{"data": []}')
    mock_pyzabbix.send.assert_called_once()
    metric = mock_pyzabbix.send.call_args[0][0][0]
    assert metric.key == "esphome.discovery"
    assert metric.host == "MQTT-Bridge"
    assert metric.value == '{"data": []}'


def test_send_value_uses_sensor_key():
    sender, mock_pyzabbix = _make_sender()
    sender.send_value("esp32_k1_temp", "23.5")
    mock_pyzabbix.send.assert_called_once()
    metric = mock_pyzabbix.send.call_args[0][0][0]
    assert metric.key == "esphome.sensor[esp32_k1_temp]"
    assert metric.host == "MQTT-Bridge"
    assert metric.value == "23.5"


def test_send_lld_does_not_raise_on_exception():
    sender, mock_pyzabbix = _make_sender()
    mock_pyzabbix.send.side_effect = Exception("Connection refused")
    sender.send_lld('{"data": []}')  # must not raise


def test_send_value_does_not_raise_on_exception():
    sender, mock_pyzabbix = _make_sender()
    mock_pyzabbix.send.side_effect = Exception("Connection refused")
    sender.send_value("esp32_k1_temp", "23.5")  # must not raise
