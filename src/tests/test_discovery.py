import json
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

TEXT_CFG = {
    "unique_id": "esp32_k1_status",
    "name": "Estado",
    "state_topic": "zbx/text_sensor/esp32_k1/status/state",
}


def test_register_new_sensor_returns_true_and_entry():
    reg = DiscoveryRegistry()
    is_new, entry = reg.register("sensor", SENSOR_CFG)
    assert is_new is True
    assert entry.sensor_id == "esp32_k1_temp"
    assert entry.name == "Temperatura"
    assert entry.domain == "sensor"
    assert entry.state_topic == "zbx/sensor/esp32_k1/temperatura/state"
    assert entry.unit == "°C"


def test_register_binary_has_no_unit():
    reg = DiscoveryRegistry()
    _, entry = reg.register("binary_sensor", BINARY_CFG)
    assert entry.unit is None


def test_register_duplicate_returns_false():
    reg = DiscoveryRegistry()
    reg.register("sensor", SENSOR_CFG)
    is_new, _ = reg.register("sensor", SENSOR_CFG)
    assert is_new is False


def test_lld_payload_filters_by_domain():
    reg = DiscoveryRegistry()
    reg.register("sensor", SENSOR_CFG)
    reg.register("binary_sensor", BINARY_CFG)
    reg.register("text_sensor", TEXT_CFG)

    sensor_ids = {r["{#SENSOR_ID}"] for r in json.loads(reg.lld_payload("sensor"))["data"]}
    binary_ids = {r["{#SENSOR_ID}"] for r in json.loads(reg.lld_payload("binary_sensor"))["data"]}
    text_ids = {r["{#SENSOR_ID}"] for r in json.loads(reg.lld_payload("text_sensor"))["data"]}

    assert sensor_ids == {"esp32_k1_temp"}
    assert binary_ids == {"esp32_k1_door"}
    assert text_ids == {"esp32_k1_status"}


def test_lld_payload_sensor_includes_unit_macro():
    reg = DiscoveryRegistry()
    reg.register("sensor", SENSOR_CFG)
    row = json.loads(reg.lld_payload("sensor"))["data"][0]
    assert row["{#SENSOR_ID}"] == "esp32_k1_temp"
    assert row["{#SENSOR_NAME}"] == "Temperatura"
    assert row["{#SENSOR_UNIT}"] == "°C"


def test_lld_payload_sensor_missing_unit_is_empty_string():
    reg = DiscoveryRegistry()
    reg.register("sensor", {
        "unique_id": "esp32_k1_count",
        "name": "Contador",
        "state_topic": "zbx/sensor/esp32_k1/count/state",
    })
    row = json.loads(reg.lld_payload("sensor"))["data"][0]
    assert row["{#SENSOR_UNIT}"] == ""


def test_lld_payload_binary_has_no_unit_macro():
    reg = DiscoveryRegistry()
    reg.register("binary_sensor", BINARY_CFG)
    row = json.loads(reg.lld_payload("binary_sensor"))["data"][0]
    assert "{#SENSOR_UNIT}" not in row
    assert row["{#SENSOR_ID}"] == "esp32_k1_door"
    assert row["{#SENSOR_NAME}"] == "Puerta"


def test_lld_payload_empty_domain():
    reg = DiscoveryRegistry()
    assert json.loads(reg.lld_payload("sensor"))["data"] == []


def test_get_by_state_topic_returns_entry():
    reg = DiscoveryRegistry()
    reg.register("sensor", SENSOR_CFG)
    entry = reg.get_by_state_topic("zbx/sensor/esp32_k1/temperatura/state")
    assert entry is not None
    assert entry.sensor_id == "esp32_k1_temp"


def test_get_by_state_topic_returns_none_for_unknown():
    reg = DiscoveryRegistry()
    assert reg.get_by_state_topic("zbx/sensor/unknown/topic/state") is None
