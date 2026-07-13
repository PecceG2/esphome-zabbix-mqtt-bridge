import json
import pytest
from bridge.discovery import DiscoveryRegistry


SENSOR_CFG = {
    "unique_id": "esp32_k1_temp",
    "name": "Temperatura",
    "state_topic": "zbx/sensor/esp32_k1/temperatura/state",
    "unit_of_measurement": "°C",
}

BINARY_CFG = {
    "unique_id": "esp32_k1_door",
    "name": "Puerta",
    "state_topic": "zbx/binary_sensor/esp32_k1/puerta/state",
}


def test_register_new_sensor_returns_true_and_entry():
    reg = DiscoveryRegistry()
    is_new, entry = reg.register("sensor", SENSOR_CFG)
    assert is_new is True
    assert entry.sensor_id == "esp32_k1_temp"
    assert entry.name == "Temperatura"
    assert entry.domain == "sensor"
    assert entry.state_topic == "zbx/sensor/esp32_k1/temperatura/state"


def test_register_duplicate_returns_false():
    reg = DiscoveryRegistry()
    reg.register("sensor", SENSOR_CFG)
    is_new, _ = reg.register("sensor", SENSOR_CFG)
    assert is_new is False


def test_lld_payload_contains_all_registered_sensors():
    reg = DiscoveryRegistry()
    reg.register("sensor", SENSOR_CFG)
    reg.register("binary_sensor", BINARY_CFG)
    data = json.loads(reg.lld_payload())["data"]
    assert len(data) == 2
    ids = {item["{#SENSOR_ID}"] for item in data}
    assert "esp32_k1_temp" in ids
    assert "esp32_k1_door" in ids


def test_lld_payload_includes_all_macros():
    reg = DiscoveryRegistry()
    reg.register("sensor", SENSOR_CFG)
    item = json.loads(reg.lld_payload())["data"][0]
    assert item["{#SENSOR_ID}"] == "esp32_k1_temp"
    assert item["{#SENSOR_NAME}"] == "Temperatura"
    assert item["{#SENSOR_DOMAIN}"] == "sensor"


def test_lld_payload_empty_registry():
    reg = DiscoveryRegistry()
    data = json.loads(reg.lld_payload())["data"]
    assert data == []


def test_get_by_state_topic_returns_entry():
    reg = DiscoveryRegistry()
    reg.register("sensor", SENSOR_CFG)
    entry = reg.get_by_state_topic("zbx/sensor/esp32_k1/temperatura/state")
    assert entry is not None
    assert entry.sensor_id == "esp32_k1_temp"


def test_get_by_state_topic_returns_none_for_unknown():
    reg = DiscoveryRegistry()
    assert reg.get_by_state_topic("zbx/sensor/unknown/topic/state") is None
