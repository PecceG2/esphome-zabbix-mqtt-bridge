import os
import re
import uuid

import yaml

TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "zabbix",
    "esphome-mqtt-bridge-template.yaml",
)


def _load():
    with open(TEMPLATE_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _template(doc):
    return doc["zabbix_export"]["templates"][0]


def _rule_by_key(doc, key):
    for rule in _template(doc)["discovery_rules"]:
        if rule["key"] == key:
            return rule
    raise AssertionError(f"discovery rule {key} not found")


def test_export_version_is_7_0():
    assert _load()["zabbix_export"]["version"] == "7.0"


def test_all_three_discovery_keys_present():
    doc = _load()
    keys = {r["key"] for r in _template(doc)["discovery_rules"]}
    assert keys == {
        "esphome.discovery.sensor",
        "esphome.discovery.binary_sensor",
        "esphome.discovery.text_sensor",
    }


def test_item_keys_match_bridge_contract():
    doc = _load()
    expected = {
        "esphome.discovery.sensor": "esphome.sensor[{#SENSOR_ID}]",
        "esphome.discovery.binary_sensor": "esphome.binary_sensor[{#SENSOR_ID}]",
        "esphome.discovery.text_sensor": "esphome.text_sensor[{#SENSOR_ID}]",
    }
    for rule_key, item_key in expected.items():
        rule = _rule_by_key(doc, rule_key)
        assert rule["item_prototypes"][0]["key"] == item_key


def test_sensor_item_is_float_with_unit_macro():
    rule = _rule_by_key(_load(), "esphome.discovery.sensor")
    proto = rule["item_prototypes"][0]
    assert proto["value_type"] == "FLOAT"
    assert proto["units"] == "{#SENSOR_UNIT}"


def test_binary_item_is_unsigned_with_bool_preprocessing_and_valuemap():
    rule = _rule_by_key(_load(), "esphome.discovery.binary_sensor")
    proto = rule["item_prototypes"][0]
    assert proto["value_type"] == "UNSIGNED"
    assert proto["valuemap"]["name"] == "ESPHome Binary"
    assert proto["preprocessing"][0]["type"] == "BOOL_TO_DECIMAL"


def test_text_item_is_text():
    rule = _rule_by_key(_load(), "esphome.discovery.text_sensor")
    assert rule["item_prototypes"][0]["value_type"] == "TEXT"


def test_all_uuids_are_valid_uuidv4():
    # Zabbix 7.0 import rejects any uuid that is not a real UUIDv4.
    with open(TEMPLATE_PATH, encoding="utf-8") as fh:
        raw = fh.read()
    hexes = re.findall(r"uuid:\s*([0-9a-f]{32})", raw)
    assert len(hexes) == 12
    for h in hexes:
        u = uuid.UUID(hex=h)
        assert u.version == 4, f"{h} is not UUIDv4 (version={u.version})"
        assert u.variant == uuid.RFC_4122, f"{h} has a non-RFC-4122 variant"
    assert len(set(hexes)) == len(hexes), "duplicate uuids found"


def test_binary_valuemap_defined():
    vm = _template(_load())["valuemaps"][0]
    assert vm["name"] == "ESPHome Binary"
    pairs = {(m["value"], m["newvalue"]) for m in vm["mappings"]}
    assert ("1", "ON") in pairs
    assert ("0", "OFF") in pairs
