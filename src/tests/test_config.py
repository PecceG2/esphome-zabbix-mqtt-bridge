import pytest
from bridge.config import load_config


def test_raises_on_missing_required_vars(monkeypatch):
    for var in ("MQTT_BROKER", "DISCOVERY_PREFIX", "ZABBIX_SERVER"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(EnvironmentError) as exc:
        load_config()
    msg = str(exc.value)
    assert "MQTT_BROKER" in msg
    assert "DISCOVERY_PREFIX" in msg
    assert "ZABBIX_SERVER" in msg


def test_raises_lists_only_missing_vars(monkeypatch):
    monkeypatch.setenv("MQTT_BROKER", "localhost")
    monkeypatch.setenv("DISCOVERY_PREFIX", "zbx")
    monkeypatch.delenv("ZABBIX_SERVER", raising=False)
    with pytest.raises(EnvironmentError) as exc:
        load_config()
    assert "ZABBIX_SERVER" in str(exc.value)
    assert "MQTT_BROKER" not in str(exc.value)


def test_uses_defaults_for_optional_vars(monkeypatch):
    monkeypatch.setenv("MQTT_BROKER", "localhost")
    monkeypatch.setenv("DISCOVERY_PREFIX", "zbx")
    monkeypatch.setenv("ZABBIX_SERVER", "127.0.0.1")
    for var in ("MQTT_PORT", "ZABBIX_PORT", "ZABBIX_HOST", "LOG_LEVEL"):
        monkeypatch.delenv(var, raising=False)
    config = load_config()
    assert config.mqtt_port == 1883
    assert config.zabbix_port == 10051
    assert config.zabbix_host == "MQTT-Bridge"
    assert config.log_level == "INFO"


def test_reads_all_vars(monkeypatch):
    monkeypatch.setenv("MQTT_BROKER", "mosquitto")
    monkeypatch.setenv("MQTT_PORT", "1884")
    monkeypatch.setenv("DISCOVERY_PREFIX", "zbx")
    monkeypatch.setenv("ZABBIX_SERVER", "192.168.1.10")
    monkeypatch.setenv("ZABBIX_PORT", "10052")
    monkeypatch.setenv("ZABBIX_HOST", "MyBridge")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    config = load_config()
    assert config.mqtt_broker == "mosquitto"
    assert config.mqtt_port == 1884
    assert config.discovery_prefix == "zbx"
    assert config.zabbix_server == "192.168.1.10"
    assert config.zabbix_port == 10052
    assert config.zabbix_host == "MyBridge"
    assert config.log_level == "DEBUG"
