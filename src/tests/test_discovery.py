import json
from bridge.discovery import DiscoveryRegistry, classify_domain


# Real ESPHome/Home-Assistant discovery payloads use abbreviated keys.
NUMERIC_ABBREV_CFG = {
    "dev_cla": "temperature",
    "unit_of_meas": "°C",
    "stat_cla": "measurement",
    "name": "Temperatura",
    "stat_t": "zbx/sensor/temperatura/state",
    "uniq_id": "ESPsensortemperatura",
}

TEXT_ABBREV_CFG = {
    "name": "Estado Temperatura",
    "ic": "mdi:thermometer-alert",
    "stat_t": "zbx/sensor/estado_temperatura/state",
    "uniq_id": "ESPsensorestado_temperatura",
}

BINARY_ABBREV_CFG = {
    "dev_cla": "power",
    "name": "Térmica Equipo 1",
    "stat_t": "zbx/binary_sensor/t__rmica_equipo_1/state",
    "uniq_id": "ESPbinary_sensort__rmica_equipo_1",
}


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


def test_register_reads_abbreviated_keys():
    reg = DiscoveryRegistry()
    is_new, entry = reg.register("sensor", NUMERIC_ABBREV_CFG)
    assert is_new is True
    assert entry.sensor_id == "ESPsensortemperatura"
    assert entry.name == "Temperatura"
    assert entry.state_topic == "zbx/sensor/temperatura/state"
    assert entry.unit == "°C"


def test_register_abbreviated_text_has_no_unit():
    reg = DiscoveryRegistry()
    _, entry = reg.register("text_sensor", TEXT_ABBREV_CFG)
    assert entry.sensor_id == "ESPsensorestado_temperatura"
    assert entry.unit is None


def test_classify_numeric_sensor_stays_sensor():
    # Has unit_of_meas and stat_cla -> numeric.
    assert classify_domain("sensor", NUMERIC_ABBREV_CFG) == "sensor"


def test_classify_text_under_sensor_component_becomes_text_sensor():
    # ESPHome publishes text_sensors under the HA `sensor` component with no
    # unit / state_class -> must be treated as text.
    assert classify_domain("sensor", TEXT_ABBREV_CFG) == "text_sensor"


def test_classify_numeric_sensor_with_full_keys():
    assert classify_domain("sensor", SENSOR_CFG) == "sensor"


def test_classify_sensor_with_state_class_only_is_numeric():
    assert classify_domain("sensor", {"stat_cla": "measurement", "uniq_id": "x"}) == "sensor"


def test_classify_binary_sensor_passes_through():
    assert classify_domain("binary_sensor", BINARY_ABBREV_CFG) == "binary_sensor"


def test_classify_text_sensor_component_passes_through():
    assert classify_domain("text_sensor", TEXT_ABBREV_CFG) == "text_sensor"
