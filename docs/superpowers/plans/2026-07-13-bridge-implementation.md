# esphome-zabbix-mqtt-bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Dockerized Python bridge that translates ESPHome MQTT discovery messages into Zabbix Low-Level Discovery items.

**Architecture:** A structured Python package (`bridge/`) with four modules wired together in `main.py`. Two Docker services in `docker-compose.yaml`: Mosquitto (broker) and the bridge itself. Config flows entirely through environment variables.

**Tech Stack:** Python 3.12, paho-mqtt 1.6.1, py-zabbix 1.1.7, pytest, Docker / docker-compose, eclipse-mosquitto:2.

## Global Constraints

- All source code lives under `src/`; `docker-compose.yaml`, `.env.example`, and `mosquitto/` live at the repo root.
- `src/Dockerfile` copies only `bridge/` and `main.py` — tests are never baked into the image.
- Required env vars: `MQTT_BROKER`, `DISCOVERY_PREFIX`, `ZABBIX_SERVER`. Missing any → process exits with a descriptive error before touching the network.
- Supported ESPHome domains: `sensor`, `binary_sensor`, `text_sensor`.
- LLD key: `esphome.discovery`. Item prototype key: `esphome.sensor[{#SENSOR_ID}]`.
- LLD macros: `{#SENSOR_ID}`, `{#SENSOR_NAME}`, `{#SENSOR_DOMAIN}`.
- paho-mqtt 1.6.1 `on_connect` signature: `(client, userdata, flags, rc)` — do NOT use the 2.x API.
- No co-author lines in commits.

---

## File Map

| File | Role |
|---|---|
| `docker-compose.yaml` | Defines `mosquitto` and `bridge` services |
| `.env.example` | Template for required env vars (committed; actual `.env` is not) |
| `mosquitto/config/mosquitto.conf` | Mosquitto listener config |
| `src/Dockerfile` | Builds the bridge image |
| `src/requirements.txt` | Runtime deps: paho-mqtt, py-zabbix |
| `src/requirements-dev.txt` | Dev deps: pytest |
| `src/main.py` | Entry point: wires Config → ZabbixSender → DiscoveryRegistry → MQTTClient |
| `src/bridge/__init__.py` | Empty package marker |
| `src/bridge/config.py` | Reads env vars, validates required ones, returns `Config` dataclass |
| `src/bridge/discovery.py` | `DiscoveryRegistry`: registers sensors, builds LLD JSON |
| `src/bridge/zabbix.py` | `ZabbixSender`: wraps py-zabbix, sends LLD and state values |
| `src/bridge/mqtt_client.py` | `MQTTClient`: paho-mqtt wrapper, routes discovery and state messages |
| `src/tests/__init__.py` | Empty test package marker |
| `src/tests/test_config.py` | Tests for `config.py` |
| `src/tests/test_discovery.py` | Tests for `discovery.py` |
| `src/tests/test_zabbix.py` | Tests for `zabbix.py` |
| `src/tests/test_mqtt_client.py` | Tests for `mqtt_client.py` |

---

## Task 1: Config module

**Files:**
- Create: `src/bridge/__init__.py`
- Create: `src/bridge/config.py`
- Create: `src/tests/__init__.py`
- Create: `src/tests/test_config.py`
- Create: `src/requirements.txt`
- Create: `src/requirements-dev.txt`

**Interfaces:**
- Produces: `Config` dataclass with fields `mqtt_broker: str`, `mqtt_port: int`, `discovery_prefix: str`, `zabbix_server: str`, `zabbix_port: int`, `zabbix_host: str`, `log_level: str`
- Produces: `load_config() -> Config` — raises `EnvironmentError` listing all missing required vars

- [ ] **Step 1: Create `src/requirements.txt`**

```
paho-mqtt==1.6.1
py-zabbix==1.1.7
```

- [ ] **Step 2: Create `src/requirements-dev.txt`**

```
pytest==8.3.5
```

- [ ] **Step 3: Create empty package markers**

`src/bridge/__init__.py` — empty file.
`src/tests/__init__.py` — empty file.

- [ ] **Step 4: Write the failing tests**

`src/tests/test_config.py`:
```python
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
```

- [ ] **Step 5: Run tests to verify they fail**

```bash
cd src
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/test_config.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` for `bridge.config`.

- [ ] **Step 6: Implement `src/bridge/config.py`**

```python
import os
from dataclasses import dataclass


@dataclass
class Config:
    mqtt_broker: str
    mqtt_port: int
    discovery_prefix: str
    zabbix_server: str
    zabbix_port: int
    zabbix_host: str
    log_level: str


def load_config() -> Config:
    required = ["MQTT_BROKER", "DISCOVERY_PREFIX", "ZABBIX_SERVER"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}"
        )
    return Config(
        mqtt_broker=os.environ["MQTT_BROKER"],
        mqtt_port=int(os.environ.get("MQTT_PORT", "1883")),
        discovery_prefix=os.environ["DISCOVERY_PREFIX"],
        zabbix_server=os.environ["ZABBIX_SERVER"],
        zabbix_port=int(os.environ.get("ZABBIX_PORT", "10051")),
        zabbix_host=os.environ.get("ZABBIX_HOST", "MQTT-Bridge"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: 4 tests PASSED.

- [ ] **Step 8: Commit**

```bash
git add src/bridge/__init__.py src/bridge/config.py src/tests/__init__.py src/tests/test_config.py src/requirements.txt src/requirements-dev.txt
git commit -m "feat: add config module with env var loading and validation"
```

---

## Task 2: DiscoveryRegistry

**Files:**
- Create: `src/bridge/discovery.py`
- Create: `src/tests/test_discovery.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (standalone)
- Produces:
  - `SensorEntry` dataclass: `sensor_id: str`, `name: str`, `domain: str`, `state_topic: str`
  - `DiscoveryRegistry` class:
    - `register(domain: str, payload: dict) -> tuple[bool, SensorEntry]` — `True` if newly registered
    - `lld_payload() -> str` — JSON string `{"data": [{"{#SENSOR_ID}": ..., "{#SENSOR_NAME}": ..., "{#SENSOR_DOMAIN}": ...}]}`
    - `get_by_state_topic(topic: str) -> SensorEntry | None`

- [ ] **Step 1: Write the failing tests**

`src/tests/test_discovery.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_discovery.py -v
```

Expected: `ImportError` for `bridge.discovery`.

- [ ] **Step 3: Implement `src/bridge/discovery.py`**

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
        )
        self._sensors[sensor_id] = entry
        return True, entry

    def lld_payload(self) -> str:
        data = [
            {
                "{#SENSOR_ID}": e.sensor_id,
                "{#SENSOR_NAME}": e.name,
                "{#SENSOR_DOMAIN}": e.domain,
            }
            for e in self._sensors.values()
        ]
        return json.dumps({"data": data})

    def get_by_state_topic(self, topic: str) -> Optional[SensorEntry]:
        for entry in self._sensors.values():
            if entry.state_topic == topic:
                return entry
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_discovery.py -v
```

Expected: 7 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/bridge/discovery.py src/tests/test_discovery.py
git commit -m "feat: add DiscoveryRegistry for sensor tracking and LLD payload generation"
```

---

## Task 3: ZabbixSender wrapper

**Files:**
- Create: `src/bridge/zabbix.py`
- Create: `src/tests/test_zabbix.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (standalone)
- Produces:
  - `ZabbixSender(server: str, port: int, host: str)`
    - `send_lld(lld_json: str) -> None` — sends to key `esphome.discovery`; swallows exceptions, logs error
    - `send_value(sensor_id: str, value: str) -> None` — sends to key `esphome.sensor[{sensor_id}]`; swallows exceptions, logs error

- [ ] **Step 1: Write the failing tests**

`src/tests/test_zabbix.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_zabbix.py -v
```

Expected: `ImportError` for `bridge.zabbix`.

- [ ] **Step 3: Implement `src/bridge/zabbix.py`**

```python
import logging
from pyzabbix import ZabbixMetric
from pyzabbix import ZabbixSender as _ZabbixSender

logger = logging.getLogger(__name__)


class ZabbixSender:
    def __init__(self, server: str, port: int, host: str):
        self._sender = _ZabbixSender(server, port)
        self._host = host

    def send_lld(self, lld_json: str) -> None:
        try:
            metric = ZabbixMetric(self._host, "esphome.discovery", lld_json)
            response = self._sender.send([metric])
            logger.info("LLD sent: %s", response)
        except Exception as exc:
            logger.error("Failed to send LLD: %s", exc)

    def send_value(self, sensor_id: str, value: str) -> None:
        try:
            metric = ZabbixMetric(self._host, f"esphome.sensor[{sensor_id}]", value)
            response = self._sender.send([metric])
            logger.debug("Value sent for %s: %s", sensor_id, response)
        except Exception as exc:
            logger.error("Failed to send value for %s: %s", sensor_id, exc)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_zabbix.py -v
```

Expected: 4 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/bridge/zabbix.py src/tests/test_zabbix.py
git commit -m "feat: add ZabbixSender wrapper using py-zabbix native protocol"
```

---

## Task 4: MQTTClient

**Files:**
- Create: `src/bridge/mqtt_client.py`
- Create: `src/tests/test_mqtt_client.py`

**Interfaces:**
- Consumes:
  - `Config` dataclass from `bridge.config` (fields: `mqtt_broker`, `mqtt_port`, `discovery_prefix`)
  - `DiscoveryRegistry` from `bridge.discovery` (methods: `register`, `lld_payload`, `get_by_state_topic`)
  - `ZabbixSender` from `bridge.zabbix` (methods: `send_lld`, `send_value`)
- Produces:
  - `MQTTClient(config: Config, registry: DiscoveryRegistry, sender: ZabbixSender)`
    - `start() -> None` — connects to broker and blocks in `loop_forever()`

- [ ] **Step 1: Write the failing tests**

`src/tests/test_mqtt_client.py`:
```python
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
    sender.send_value.assert_called_once_with("esp32_k1_temp", "23.5")


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
    sender.send_value.assert_called_once_with("esp32_k1_temp", "21.0")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_mqtt_client.py -v
```

Expected: `ImportError` for `bridge.mqtt_client`.

- [ ] **Step 3: Implement `src/bridge/mqtt_client.py`**

```python
import json
import logging
import paho.mqtt.client as mqtt

from bridge.config import Config
from bridge.discovery import DiscoveryRegistry
from bridge.zabbix import ZabbixSender

logger = logging.getLogger(__name__)

DOMAINS = ["sensor", "binary_sensor", "text_sensor"]


class MQTTClient:
    def __init__(self, config: Config, registry: DiscoveryRegistry, sender: ZabbixSender):
        self._config = config
        self._registry = registry
        self._sender = sender
        self._client = mqtt.Client()
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
            domain = topic.split("/")[1]
            is_new, entry = self._registry.register(domain, cfg)
            if not is_new:
                return
            logger.info("New sensor discovered: %s (%s, domain=%s)", entry.sensor_id, entry.name, entry.domain)
            self._sender.send_lld(self._registry.lld_payload())
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
        self._sender.send_value(entry.sensor_id, value)

    def start(self):
        self._client.reconnect_delay_set(min_delay=1, max_delay=128)
        self._client.connect(self._config.mqtt_broker, self._config.mqtt_port)
        self._client.loop_forever()
```

- [ ] **Step 4: Run all tests to verify they pass**

```bash
pytest tests/ -v
```

Expected: all tests PASSED (no failures across all four test files).

- [ ] **Step 5: Commit**

```bash
git add src/bridge/mqtt_client.py src/tests/test_mqtt_client.py
git commit -m "feat: add MQTTClient with discovery and state routing"
```

---

## Task 5: Main entrypoint and Docker infrastructure

**Files:**
- Create: `src/main.py`
- Create: `src/Dockerfile`
- Create: `docker-compose.yaml`
- Create: `mosquitto/config/mosquitto.conf`
- Create: `.env.example`

**Interfaces:**
- Consumes: `load_config` from `bridge.config`, `DiscoveryRegistry` from `bridge.discovery`, `ZabbixSender` from `bridge.zabbix`, `MQTTClient` from `bridge.mqtt_client`
- Produces: a runnable Docker Compose stack (`docker compose up --build`)

- [ ] **Step 1: Create `src/main.py`**

```python
import logging
from bridge.config import load_config
from bridge.discovery import DiscoveryRegistry
from bridge.zabbix import ZabbixSender
from bridge.mqtt_client import MQTTClient


def main():
    config = load_config()
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting esphome-zabbix-mqtt-bridge")

    registry = DiscoveryRegistry()
    sender = ZabbixSender(config.zabbix_server, config.zabbix_port, config.zabbix_host)
    client = MQTTClient(config, registry, sender)
    client.start()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create `src/Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bridge/ ./bridge/
COPY main.py .
CMD ["python", "main.py"]
```

- [ ] **Step 3: Create `mosquitto/config/mosquitto.conf`**

```
listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
log_dest file /mosquitto/log/mosquitto.log
```

- [ ] **Step 4: Create `.env.example`**

```
# Copy this file to .env and fill in your values.
# .env is gitignored — never commit it.

ZABBIX_SERVER=192.168.1.10
ZABBIX_PORT=10051
ZABBIX_HOST=MQTT-Bridge

MQTT_BROKER=mosquitto
MQTT_PORT=1883
DISCOVERY_PREFIX=zbx

LOG_LEVEL=INFO
```

- [ ] **Step 5: Create `docker-compose.yaml`**

```yaml
services:
  mosquitto:
    image: eclipse-mosquitto:2
    ports:
      - "1883:1883"
    volumes:
      - ./mosquitto/config:/mosquitto/config
      - ./mosquitto/data:/mosquitto/data
      - ./mosquitto/log:/mosquitto/log

  bridge:
    build: ./src
    restart: unless-stopped
    depends_on:
      - mosquitto
    environment:
      MQTT_BROKER: mosquitto
      MQTT_PORT: ${MQTT_PORT:-1883}
      DISCOVERY_PREFIX: ${DISCOVERY_PREFIX:-zbx}
      ZABBIX_SERVER: ${ZABBIX_SERVER}
      ZABBIX_PORT: ${ZABBIX_PORT:-10051}
      ZABBIX_HOST: ${ZABBIX_HOST:-MQTT-Bridge}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
```

- [ ] **Step 6: Add `.env` to `.gitignore`**

Create `.gitignore` at the repo root:
```
.env
mosquitto/data/
mosquitto/log/
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 7: Verify the Docker image builds**

```bash
docker compose build
```

Expected: `bridge` image builds successfully with no errors.

- [ ] **Step 8: Commit**

```bash
git add src/main.py src/Dockerfile docker-compose.yaml mosquitto/config/mosquitto.conf .env.example .gitignore
git commit -m "feat: add main entrypoint, Dockerfile, docker-compose, and Mosquitto config"
```
