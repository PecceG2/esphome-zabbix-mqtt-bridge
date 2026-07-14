# esphome-zabbix-mqtt-bridge — Design Spec

**Date:** 2026-07-13

> **Note (2026-07-14):** The Zabbix integration described here (single `esphome.discovery` LLD key and single `esphome.sensor[...]` item key) has been superseded by per-domain typed keys. See [2026-07-14-typed-values-and-template-design.md](./2026-07-14-typed-values-and-template-design.md).

## Overview

A Dockerized Python bridge that listens for ESPHome's native MQTT discovery messages and automatically registers sensors as Zabbix items via Low-Level Discovery (LLD). No Home Assistant required.

## Architecture

```
ESP32 (ESPHome) → Mosquitto (Docker) → Bridge Python (Docker) → Zabbix Server
```

The bridge is the only component that speaks MQTT. Zabbix receives only trapper (push) data — no polling, no per-device Zabbix Agent configuration.

## Repository Structure

```
esphome-zabbix-mqtt-bridge/
├── docker-compose.yaml
├── .env.example
├── mosquitto/
│   └── config/
│       └── mosquitto.conf
├── src/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   └── bridge/
│       ├── __init__.py
│       ├── config.py        # reads env vars, validates, exposes Config dataclass
│       ├── discovery.py     # DiscoveryRegistry: registers sensors, builds LLD payload
│       ├── mqtt_client.py   # paho-mqtt wrapper: connect, subscribe, callbacks
│       └── zabbix.py        # ZabbixSender: wraps py-zabbix, sends LLD and values
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-07-13-bridge-design.md
```

## Docker Setup

Two services in `docker-compose.yaml`:

- **mosquitto** — `eclipse-mosquitto:2`, ports `1883:1883`, volumes for config/data/log
- **bridge** — built from `./src`, `restart: unless-stopped`, `depends_on: mosquitto`

Sensitive values (`ZABBIX_SERVER`, etc.) are sourced from a `.env` file in the repo root (not committed). Values with sensible defaults (`ZABBIX_PORT`, `ZABBIX_HOST`) can be overridden.

## Configuration (Environment Variables)

| Variable | Required | Default | Description |
|---|---|---|---|
| `MQTT_BROKER` | yes | — | Hostname of the MQTT broker |
| `MQTT_PORT` | no | `1883` | MQTT broker port |
| `DISCOVERY_PREFIX` | yes | — | ESPHome discovery prefix (e.g. `zbx`) |
| `ZABBIX_SERVER` | yes | — | Zabbix Server IP or hostname |
| `ZABBIX_PORT` | no | `10051` | Zabbix trapper port |
| `ZABBIX_HOST` | no | `MQTT-Bridge` | Zabbix host name that receives trapper data |
| `LOG_LEVEL` | no | `INFO` | Python logging level |

`config.py` validates all required variables at startup and exits with a clear error message if any are missing.

## Data Flow

1. `main.py` loads `Config` → instantiates `ZabbixSender` and `DiscoveryRegistry` → starts `MQTTClient`.
2. `MQTTClient` subscribes to discovery topics for three domains:
   - `{prefix}/sensor/+/+/config`
   - `{prefix}/binary_sensor/+/+/config`
   - `{prefix}/text_sensor/+/+/config`
3. On each `/config` message: `DiscoveryRegistry` registers the sensor → `ZabbixSender` pushes updated LLD JSON → `MQTTClient` subscribes to the sensor's `state_topic`.
4. On each state update: `ZabbixSender` sends the value as Zabbix trapper data.

## Zabbix Integration

- **Protocol:** Zabbix Sender protocol via `py-zabbix` library (no `zabbix_sender` binary required).
- **LLD key:** `esphome.discovery`
- **Item prototype key:** `esphome.sensor[{#SENSOR_ID}]`
- **LLD macros exposed:** `{#SENSOR_ID}`, `{#SENSOR_NAME}`, `{#SENSOR_DOMAIN}` (sensor / binary_sensor / text_sensor)

## ESPHome Domains Supported

| Domain | Discovery topic pattern | State value type |
|---|---|---|
| `sensor` | `{prefix}/sensor/+/+/config` | Numeric (float) |
| `binary_sensor` | `{prefix}/binary_sensor/+/+/config` | String (`ON`/`OFF`) |
| `text_sensor` | `{prefix}/text_sensor/+/+/config` | String |

## Error Handling & Resilience

- **MQTT reconnection:** paho-mqtt reconnects automatically with exponential backoff (1s → 128s). On reconnect, Mosquitto replays retained discovery messages so `DiscoveryRegistry` repopulates without manual intervention.
- **Zabbix send failures:** logged and skipped — the MQTT loop continues. No retry queue; stale sensor values have no monitoring value.
- **Config validation:** fails fast at startup with a descriptive message if required env vars are missing.
- **Logging:** structured log lines for every significant event: sensor discovered, LLD sent, value forwarded, errors.

## Mosquitto Configuration

`mosquitto/config/mosquitto.conf`:
```
listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
log_dest file /mosquitto/log/mosquitto.log
```

Allows anonymous connections (suitable for a private network). TLS and authentication are out of scope for this version.

## Out of Scope

- TLS / MQTT authentication
- Retry queue for failed Zabbix sends
- Additional ESPHome domains (`switch`, `cover`, `select`, etc.) — extensible by adding subscriptions in `mqtt_client.py` and handlers in `discovery.py`
- Zabbix template / trigger definitions
