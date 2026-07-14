# Typed Zabbix Values + Import Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the bridge's Zabbix keys per ESPHome domain so sensors land as properly typed items (numeric float / numeric boolean / text), and ship an importable Zabbix 7.0 template that materializes them via LLD.

**Architecture:** The bridge groups discovered sensors by domain and pushes one LLD stream per domain (`esphome.discovery.<domain>`) plus per-domain value keys (`esphome.<domain>[<id>]`). The Zabbix 7.0 template defines one trapper LLD rule per domain, each with a single typed item prototype and a no-data trigger prototype.

**Tech Stack:** Python 3.11, paho-mqtt 1.6.1, py-zabbix 1.1.7, pytest 8.3.5; Zabbix 7.0 YAML export.

## Global Constraints

- Python 3.11; runtime deps limited to `paho-mqtt==1.6.1` and `py-zabbix==1.1.7` (do not add runtime deps).
- Tests run from the `src/` directory: `cd src && python -m pytest`. Package imports are `from bridge.<module> import ...`.
- Template targets Zabbix export **version `7.0`**, YAML format, importable from *Data collection → Templates → Import*.
- Zabbix key contract (exact strings): LLD `esphome.discovery.<domain>`; value `esphome.<domain>[<sensor_id>]`, where `<domain>` ∈ {`sensor`, `binary_sensor`, `text_sensor`}.
- LLD macros: `{#SENSOR_ID}`, `{#SENSOR_NAME}` for all domains; `{#SENSOR_UNIT}` additionally for `sensor`.
- TDD: write the failing test first. Commit after each task.

---

### Task 1: Per-domain LLD payload + unit in `discovery.py`

**Files:**
- Modify: `src/bridge/discovery.py`
- Test: `src/tests/test_discovery.py`

**Interfaces:**
- Consumes: nothing (leaf module).
- Produces:
  - `SensorEntry` dataclass with fields `sensor_id: str, name: str, domain: str, state_topic: str, unit: Optional[str] = None`.
  - `DiscoveryRegistry.register(domain: str, payload: dict) -> tuple[bool, SensorEntry]` (unchanged signature; now also reads `unit_of_measurement`).
  - `DiscoveryRegistry.lld_payload(domain: str) -> str` — **signature changed**, now takes a domain and returns LLD JSON for only that domain.
  - `DiscoveryRegistry.get_by_state_topic(topic: str) -> Optional[SensorEntry]` (unchanged).

- [ ] **Step 1: Rewrite the tests to the new interface**

Replace the entire contents of `src/tests/test_discovery.py` with:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd src && python -m pytest tests/test_discovery.py -v`
Expected: FAIL — `lld_payload()` currently takes no argument (`TypeError`), and `SensorEntry` has no `unit`.

- [ ] **Step 3: Rewrite `discovery.py`**

Replace the entire contents of `src/bridge/discovery.py` with:

```python
import json
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class SensorEntry:
    sensor_id: str
    name: str
    domain: str
    state_topic: str
    unit: Optional[str] = None


class DiscoveryRegistry:
    def __init__(self):
        self._sensors: Dict[str, SensorEntry] = {}

    def register(self, domain: str, payload: dict) -> tuple:
        sensor_id = payload["unique_id"]
        if sensor_id in self._sensors:
            return False, self._sensors[sensor_id]
        entry = SensorEntry(
            sensor_id=sensor_id,
            name=payload["name"],
            domain=domain,
            state_topic=payload["state_topic"],
            unit=payload.get("unit_of_measurement"),
        )
        self._sensors[sensor_id] = entry
        return True, entry

    def lld_payload(self, domain: str) -> str:
        data = []
        for e in self._sensors.values():
            if e.domain != domain:
                continue
            row = {
                "{#SENSOR_ID}": e.sensor_id,
                "{#SENSOR_NAME}": e.name,
            }
            if domain == "sensor":
                row["{#SENSOR_UNIT}"] = e.unit or ""
            data.append(row)
        return json.dumps({"data": data})

    def get_by_state_topic(self, topic: str) -> Optional[SensorEntry]:
        for entry in self._sensors.values():
            if entry.state_topic == topic:
                return entry
        return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd src && python -m pytest tests/test_discovery.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add src/bridge/discovery.py src/tests/test_discovery.py
git commit -m "feat: per-domain LLD payload with unit macro in discovery registry"
```

---

### Task 2: Per-domain keys in `zabbix.py`

**Files:**
- Modify: `src/bridge/zabbix.py`
- Test: `src/tests/test_zabbix.py`

**Interfaces:**
- Consumes: nothing (wraps `py-zabbix`).
- Produces:
  - `ZabbixSender.send_lld(domain: str, lld_json: str) -> None` → sends metric key `esphome.discovery.<domain>`.
  - `ZabbixSender.send_value(domain: str, sensor_id: str, value: str) -> None` → sends metric key `esphome.<domain>[<sensor_id>]`.
  - Both swallow exceptions (log, never raise).

- [ ] **Step 1: Rewrite the tests to the new interface**

Replace the entire contents of `src/tests/test_zabbix.py` with:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd src && python -m pytest tests/test_zabbix.py -v`
Expected: FAIL — `send_lld`/`send_value` do not accept a `domain` argument yet (`TypeError`).

- [ ] **Step 3: Rewrite `zabbix.py`**

Replace the entire contents of `src/bridge/zabbix.py` with:

```python
import logging
from pyzabbix import ZabbixMetric
from pyzabbix import ZabbixSender as _ZabbixSender

logger = logging.getLogger(__name__)


class ZabbixSender:
    def __init__(self, server: str, port: int, host: str):
        self._sender = _ZabbixSender(server, port)
        self._host = host

    def send_lld(self, domain: str, lld_json: str) -> None:
        key = f"esphome.discovery.{domain}"
        try:
            metric = ZabbixMetric(self._host, key, lld_json)
            response = self._sender.send([metric])
            logger.info("LLD sent (%s): %s", domain, response)
        except Exception as exc:
            logger.error("Failed to send LLD for %s: %s", domain, exc)

    def send_value(self, domain: str, sensor_id: str, value: str) -> None:
        key = f"esphome.{domain}[{sensor_id}]"
        try:
            metric = ZabbixMetric(self._host, key, value)
            response = self._sender.send([metric])
            logger.debug("Value sent for %s: %s", key, response)
        except Exception as exc:
            logger.error("Failed to send value for %s: %s", key, exc)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd src && python -m pytest tests/test_zabbix.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bridge/zabbix.py src/tests/test_zabbix.py
git commit -m "feat: per-domain discovery and value keys in ZabbixSender"
```

---

### Task 3: Route by domain in `mqtt_client.py`

**Files:**
- Modify: `src/bridge/mqtt_client.py:41-61` (the `_handle_discovery` and `_handle_state` methods)
- Test: `src/tests/test_mqtt_client.py` (create)

**Interfaces:**
- Consumes: `DiscoveryRegistry.lld_payload(domain)`, `SensorEntry.domain` (Task 1); `ZabbixSender.send_lld(domain, json)`, `ZabbixSender.send_value(domain, sensor_id, value)` (Task 2).
- Produces: no new public API — wires discovery/state handling to the per-domain calls.

- [ ] **Step 1: Write the failing test**

Create `src/tests/test_mqtt_client.py`:

```python
import json
from unittest.mock import MagicMock, patch

from bridge.config import Config
from bridge.discovery import DiscoveryRegistry
from bridge.mqtt_client import MQTTClient


def _make_client():
    config = Config(
        mqtt_broker="localhost",
        mqtt_port=1883,
        discovery_prefix="zbx",
        zabbix_server="127.0.0.1",
        zabbix_port=10051,
        zabbix_host="MQTT-Bridge",
        log_level="INFO",
    )
    registry = DiscoveryRegistry()
    sender = MagicMock()
    with patch("bridge.mqtt_client.mqtt.Client") as MockClient:
        MockClient.return_value = MagicMock()
        client = MQTTClient(config, registry, sender)
    return client, registry, sender


def test_discovery_sends_lld_for_that_domain():
    client, registry, sender = _make_client()
    cfg = {
        "unique_id": "esp_door",
        "name": "Puerta",
        "state_topic": "zbx/binary_sensor/esp/puerta/state",
    }
    client._handle_discovery(
        "zbx/binary_sensor/esp/puerta/config", json.dumps(cfg).encode()
    )
    sender.send_lld.assert_called_once()
    domain_arg, payload_arg = sender.send_lld.call_args[0]
    assert domain_arg == "binary_sensor"
    ids = {r["{#SENSOR_ID}"] for r in json.loads(payload_arg)["data"]}
    assert ids == {"esp_door"}


def test_state_routes_value_by_domain():
    client, registry, sender = _make_client()
    registry.register("sensor", {
        "unique_id": "esp_temp",
        "name": "Temp",
        "state_topic": "zbx/sensor/esp/temp/state",
        "unit_of_measurement": "°C",
    })
    client._handle_state("zbx/sensor/esp/temp/state", b"23.5")
    sender.send_value.assert_called_once_with("sensor", "esp_temp", "23.5")


def test_state_unknown_topic_is_ignored():
    client, registry, sender = _make_client()
    client._handle_state("zbx/sensor/esp/unknown/state", b"1")
    sender.send_value.assert_not_called()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src && python -m pytest tests/test_mqtt_client.py -v`
Expected: FAIL — `_handle_discovery` calls `self._registry.lld_payload()` with no argument and `_handle_state` calls `self._sender.send_value(entry.sensor_id, value)` without the domain, so the assertions on call args fail.

- [ ] **Step 3: Update `_handle_discovery` and `_handle_state`**

In `src/bridge/mqtt_client.py`, replace the `send_lld` line inside `_handle_discovery` (currently `self._sender.send_lld(self._registry.lld_payload())`) with:

```python
            self._sender.send_lld(entry.domain, self._registry.lld_payload(entry.domain))
```

And replace the last line of `_handle_state` (currently `self._sender.send_value(entry.sensor_id, value)`) with:

```python
        self._sender.send_value(entry.domain, entry.sensor_id, value)
```

For reference, the two methods should read exactly:

```python
    def _handle_discovery(self, topic: str, payload: bytes):
        try:
            cfg = json.loads(payload)
            domain = topic.split("/")[1]
            is_new, entry = self._registry.register(domain, cfg)
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
```

- [ ] **Step 4: Run the full suite to verify everything passes**

Run: `cd src && python -m pytest -v`
Expected: PASS (all files: discovery, zabbix, mqtt_client).

- [ ] **Step 5: Commit**

```bash
git add src/bridge/mqtt_client.py src/tests/test_mqtt_client.py
git commit -m "feat: route LLD and values by domain in MQTT client"
```

---

### Task 4: Zabbix 7.0 import template

**Files:**
- Create: `zabbix/esphome-mqtt-bridge-template.yaml`
- Modify: `src/requirements-dev.txt` (add `PyYAML`)
- Test: `src/tests/test_template.py` (create)

**Interfaces:**
- Consumes: the key contract from Tasks 1–2 (`esphome.discovery.<domain>`, `esphome.<domain>[{#SENSOR_ID}]`).
- Produces: an importable template file; a structural test asserting the file's keys match the bridge contract.

- [ ] **Step 1: Create the template file**

Create `zabbix/esphome-mqtt-bridge-template.yaml`:

```yaml
zabbix_export:
  version: '7.0'
  template_groups:
    - uuid: 7b3e1a2c4d5f6089a1b2c3d4e5f60718
      name: Templates/ESPHome
  templates:
    - uuid: 8c4f2b3d5e6a719b2c3d4e5f60718293
      template: 'ESPHome MQTT Bridge'
      name: 'ESPHome MQTT Bridge'
      description: |
        Auto-discovers ESPHome sensors relayed by esphome-zabbix-mqtt-bridge.
        One trapper LLD rule per ESPHome domain (sensor / binary_sensor /
        text_sensor), each with a typed item prototype. Link this template to
        the trapper host that receives the bridge's data (default: MQTT-Bridge).
      groups:
        - name: Templates/ESPHome
      discovery_rules:
        - uuid: 1d2e3f405162738495a6b7c8d9e0f102
          name: 'ESPHome numeric sensors'
          type: TRAP
          key: esphome.discovery.sensor
          lifetime: 7d
          description: 'Discovers ESPHome `sensor` domain entities as numeric (float) items.'
          item_prototypes:
            - uuid: 2e3f405162738495061728394051627a
              name: '{#SENSOR_NAME}'
              type: TRAP
              key: 'esphome.sensor[{#SENSOR_ID}]'
              value_type: FLOAT
              units: '{#SENSOR_UNIT}'
              tags:
                - tag: domain
                  value: sensor
          trigger_prototypes:
            - uuid: 3f405162738495a0617283940516273a
              expression: 'nodata(/ESPHome MQTT Bridge/esphome.sensor[{#SENSOR_ID}],30m)=1'
              name: 'No data from {#SENSOR_NAME} for 30m'
              priority: WARNING
        - uuid: 4051627384950617283940516273849b
          name: 'ESPHome binary sensors'
          type: TRAP
          key: esphome.discovery.binary_sensor
          lifetime: 7d
          description: 'Discovers ESPHome `binary_sensor` domain entities as numeric (0/1) items.'
          item_prototypes:
            - uuid: 51627384950617283940516273849abc
              name: '{#SENSOR_NAME}'
              type: TRAP
              key: 'esphome.binary_sensor[{#SENSOR_ID}]'
              value_type: UNSIGNED
              valuemap:
                name: 'ESPHome Binary'
              preprocessing:
                - type: BOOL_TO_DECIMAL
              tags:
                - tag: domain
                  value: binary_sensor
          trigger_prototypes:
            - uuid: 627384950617283940516273849abcd0
              expression: 'nodata(/ESPHome MQTT Bridge/esphome.binary_sensor[{#SENSOR_ID}],30m)=1'
              name: 'No data from {#SENSOR_NAME} for 30m'
              priority: WARNING
        - uuid: 7384950617283940516273849abcd012
          name: 'ESPHome text sensors'
          type: TRAP
          key: esphome.discovery.text_sensor
          lifetime: 7d
          description: 'Discovers ESPHome `text_sensor` domain entities as text items.'
          item_prototypes:
            - uuid: 84950617283940516273849abcd01234
              name: '{#SENSOR_NAME}'
              type: TRAP
              key: 'esphome.text_sensor[{#SENSOR_ID}]'
              value_type: TEXT
              tags:
                - tag: domain
                  value: text_sensor
          trigger_prototypes:
            - uuid: 950617283940516273849abcd0123456
              expression: 'nodata(/ESPHome MQTT Bridge/esphome.text_sensor[{#SENSOR_ID}],30m)=1'
              name: 'No data from {#SENSOR_NAME} for 30m'
              priority: WARNING
      valuemaps:
        - uuid: a0617283940516273849abcd01234567
          name: 'ESPHome Binary'
          mappings:
            - value: '0'
              newvalue: 'OFF'
            - value: '1'
              newvalue: 'ON'
```

- [ ] **Step 2: Add PyYAML to dev requirements**

Edit `src/requirements-dev.txt` to read:

```
pytest==8.3.5
PyYAML==6.0.2
```

Then install it: `pip install PyYAML==6.0.2`

- [ ] **Step 3: Write the structural test**

Create `src/tests/test_template.py`:

```python
import os
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


def test_binary_valuemap_defined():
    vm = _template(_load())["valuemaps"][0]
    assert vm["name"] == "ESPHome Binary"
    pairs = {(m["value"], m["newvalue"]) for m in vm["mappings"]}
    assert ("1", "ON") in pairs
    assert ("0", "OFF") in pairs
```

- [ ] **Step 4: Run the template test to verify it passes**

Run: `cd src && python -m pytest tests/test_template.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Verify the template imports into Zabbix (manual)**

In a Zabbix 7.0 instance: *Data collection → Templates → Import* → select `zabbix/esphome-mqtt-bridge-template.yaml`. Expected: import succeeds with no errors and creates the `ESPHome MQTT Bridge` template with three discovery rules under group `Templates/ESPHome`. (If no Zabbix 7.0 instance is available, note this step as deferred to the reviewer.)

- [ ] **Step 6: Commit**

```bash
git add zabbix/esphome-mqtt-bridge-template.yaml src/requirements-dev.txt src/tests/test_template.py
git commit -m "feat: add Zabbix 7.0 import template with typed per-domain LLD"
```

---

### Task 5: Documentation update

**Files:**
- Modify: `README.md:82-96` (the "4. Configure Zabbix" section)
- Modify: `docs/superpowers/specs/2026-07-13-bridge-design.md` (note the superseding spec)

**Interfaces:**
- Consumes: the finished key contract and template from Tasks 1–4.
- Produces: no code — docs only.

- [ ] **Step 1: Replace the "Configure Zabbix" section in `README.md`**

Replace everything from the `### 4. Configure Zabbix` heading through the paragraph ending `no manual item configuration required.` (lines 82–96) with:

````markdown
### 4. Configure Zabbix

Create a host named `MQTT-Bridge` (or whatever you set as `ZABBIX_HOST`) with no agent interface — it only receives trapper data.

Import the bundled template and link it to that host:

1. In Zabbix (7.0+), go to **Data collection → Templates → Import**.
2. Select `zabbix/esphome-mqtt-bridge-template.yaml` from this repo and import it.
3. Open the `MQTT-Bridge` host → **Templates** → link **ESPHome MQTT Bridge**.

The template creates three Zabbix trapper Low-Level Discovery rules — one per ESPHome domain — each with a typed item prototype:

| ESPHome domain | Discovery rule key | Item key | Zabbix value type |
|---|---|---|---|
| `sensor` | `esphome.discovery.sensor` | `esphome.sensor[{#SENSOR_ID}]` | Numeric (float), unit from `{#SENSOR_UNIT}` |
| `binary_sensor` | `esphome.discovery.binary_sensor` | `esphome.binary_sensor[{#SENSOR_ID}]` | Numeric (unsigned) 0/1, mapped `ON`/`OFF` |
| `text_sensor` | `esphome.discovery.text_sensor` | `esphome.text_sensor[{#SENSOR_ID}]` | Text |

Available LLD macros: `{#SENSOR_ID}`, `{#SENSOR_NAME}` (all domains) and `{#SENSOR_UNIT}` (`sensor` only). Each rule also ships a `nodata(...,30m)` trigger prototype that fires when a discovered sensor stops reporting.

Once a device comes online and publishes its discovery payload, the bridge sends the LLD to Zabbix, the matching item prototype fires, and values start flowing — no manual item configuration required.
````

- [ ] **Step 2: Add a superseding note to the original design spec**

At the top of `docs/superpowers/specs/2026-07-13-bridge-design.md`, immediately after the `**Date:** 2026-07-13` line, insert:

```markdown

> **Note (2026-07-14):** The Zabbix integration described here (single `esphome.discovery` LLD key and single `esphome.sensor[...]` item key) has been superseded by per-domain typed keys. See [2026-07-14-typed-values-and-template-design.md](./2026-07-14-typed-values-and-template-design.md).
```

- [ ] **Step 3: Verify the full test suite still passes**

Run: `cd src && python -m pytest -v`
Expected: PASS (all tests across discovery, zabbix, mqtt_client, template).

- [ ] **Step 4: Commit**

```bash
git add README.md docs/superpowers/specs/2026-07-13-bridge-design.md
git commit -m "docs: document per-domain keys and Zabbix template import"
```

---

## Notes for the implementer

- The `°C` literals in tests are UTF-8; ensure files are saved as UTF-8 (no BOM).
- `BOOL_TO_DECIMAL` preprocessing recognizes `on`/`off` case-insensitively, which is exactly what ESPHome `binary_sensor` publishes (`ON`/`OFF`).
- Do not re-add the `{#SENSOR_DOMAIN}` macro — domain is now implicit per rule and carried as a static item tag in the template.
