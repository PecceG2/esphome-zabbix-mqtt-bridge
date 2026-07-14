# Typed Zabbix Values + Import Template — Design Spec

**Date:** 2026-07-14

## Overview

Two related changes so that ESPHome sensors land in Zabbix as properly *typed*
items (numeric floats, numeric booleans, text) instead of a single untyped
stream, plus an importable Zabbix 7.0 template that materializes those items via
Low-Level Discovery (LLD).

This supersedes the "Zabbix template / trigger definitions" item that the
original [bridge design](./2026-07-13-bridge-design.md) left out of scope, and
changes the Zabbix integration contract (see Breaking Change below).

## Motivation

The original bridge sends every sensor — regardless of domain — with the same
item key `esphome.sensor[{sensor_id}]` and a single LLD key `esphome.discovery`.
In Zabbix a single item prototype has exactly one value type, but the three
ESPHome domains produce three different value types:

| Domain | ESPHome value | Desired Zabbix type |
|---|---|---|
| `sensor` | numeric string (`23.4`) | Numeric (float) |
| `binary_sensor` | `ON` / `OFF` | Numeric (unsigned) 0/1 |
| `text_sensor` | free text | Text |

A single prototype cannot represent all three. The fix is to split discovery and
value keys **per domain**, giving each domain its own LLD rule and item prototype
with the correct value type.

## Architecture

Data flow is unchanged in shape (ESP32 → Mosquitto → Bridge → Zabbix trapper).
What changes is the *set of keys* the bridge pushes.

### Zabbix key contract (new)

| Domain | LLD key (discovery) | Value key (per sensor) |
|---|---|---|
| `sensor` | `esphome.discovery.sensor` | `esphome.sensor[{sensor_id}]` |
| `binary_sensor` | `esphome.discovery.binary_sensor` | `esphome.binary_sensor[{sensor_id}]` |
| `text_sensor` | `esphome.discovery.text_sensor` | `esphome.text_sensor[{sensor_id}]` |

Everything is still Zabbix trapper (push); no polling, no per-device agent.

## Bridge Changes

### `bridge/discovery.py`

- `SensorEntry` gains a field `unit: Optional[str] = None`, populated from the
  ESPHome config payload's `unit_of_measurement` (present on `sensor`; absent /
  `None` for `binary_sensor` and `text_sensor`).
- `register()` reads `unit_of_measurement` when present.
- `lld_payload()` is replaced by `lld_payload(domain: str) -> str`, returning the
  LLD JSON for **only** the sensors of that domain. Macros per domain:
  - `sensor`: `{#SENSOR_ID}`, `{#SENSOR_NAME}`, `{#SENSOR_UNIT}`
  - `binary_sensor`, `text_sensor`: `{#SENSOR_ID}`, `{#SENSOR_NAME}`
- `{#SENSOR_DOMAIN}` macro is dropped — domain is now implicit in each rule. The
  domain is instead attached as a static Zabbix item tag in the template.
- `get_by_state_topic()` is unchanged; callers use `entry.domain` to route.

### `bridge/zabbix.py`

- `send_lld(domain: str, lld_json: str)` → sends to key `esphome.discovery.{domain}`.
- `send_value(domain: str, sensor_id: str, value: str)` → sends to key
  `esphome.{domain}[{sensor_id}]`.
- Failure handling unchanged: log and skip, never raise.

### `bridge/mqtt_client.py`

- On discovery of a new sensor, resend the LLD for **that sensor's domain only**:
  `send_lld(entry.domain, registry.lld_payload(entry.domain))`.
- On a state update, route by domain:
  `send_value(entry.domain, entry.sensor_id, value)`.

### `bridge/config.py` / `main.py`

- No changes required.

## Tests (TDD)

Existing tests assert the old single-key behavior and must be updated first
(red → green):

- `tests/test_discovery.py`
  - `lld_payload()` calls become `lld_payload("sensor")` / `lld_payload("binary_sensor")`.
  - New assertion: `sensor` rows include `{#SENSOR_UNIT}` (`"°C"` from `SENSOR_CFG`);
    `binary_sensor` rows do not.
  - New assertion: `lld_payload("sensor")` excludes binary/text sensors and vice versa.
  - `SensorEntry.unit` populated for `sensor`, `None` for `binary_sensor`.
- `tests/test_zabbix.py`
  - `send_lld("sensor", ...)` → key `esphome.discovery.sensor`.
  - `send_value("binary_sensor", "esp32_k1_door", "ON")` → key
    `esphome.binary_sensor[esp32_k1_door]`.
  - `send_value("sensor", "esp32_k1_temp", "23.5")` → key
    `esphome.sensor[esp32_k1_temp]` (unchanged for sensor).

## Zabbix Template

Zabbix **7.0** export, **YAML** format (importable from
*Data collection → Templates → Import*; 7.0 also accepts XML/JSON).

Delivered as a file in the repo (e.g. `zabbix/esphome-mqtt-bridge-template.yaml`).

Contents:

- **Template group:** `Templates/ESPHome`
- **Value map** `ESPHome Binary`: `1 → ON`, `0 → OFF`
- **Template** `ESPHome MQTT Bridge`, containing three trapper LLD rules:

| Discovery rule (key) | Item prototype (key) | Value type | Extras |
|---|---|---|---|
| ESPHome numeric sensors (`esphome.discovery.sensor`) | `esphome.sensor[{#SENSOR_ID}]` | Numeric (float) | `units: {#SENSOR_UNIT}`, tag `domain=sensor` |
| ESPHome binary sensors (`esphome.discovery.binary_sensor`) | `esphome.binary_sensor[{#SENSOR_ID}]` | Numeric (unsigned) | preprocessing **Boolean to decimal**, value map `ESPHome Binary`, tag `domain=binary_sensor` |
| ESPHome text sensors (`esphome.discovery.text_sensor`) | `esphome.text_sensor[{#SENSOR_ID}]` | Text | tag `domain=text_sensor` |

- Each item prototype named `{#SENSOR_NAME}`.
- Each discovery rule: *keep lost resources period* = `7d`.
- Each rule carries a **trigger prototype**
  `No data from {#SENSOR_NAME} for 30m` — expression
  `nodata(/ESPHome MQTT Bridge/<value key>,30m)=1`, priority **Warning**.

## Operational Notes (Breaking Change)

- The bridge's Zabbix key contract changes. Bridge and template **must be
  deployed together**; an old bridge with the new template (or vice versa) will
  not populate items.
- In Zabbix: create/keep the host `MQTT-Bridge` (default `ZABBIX_HOST`), import
  the template, and link it to that host. Data arrives via trapper — no Zabbix
  agent needed.
- Update `README` and the original design's Zabbix Integration section to
  document the new per-domain keys and the template import step.

## Out of Scope

- TLS / MQTT authentication (already handled elsewhere / unchanged).
- Retry queue for failed Zabbix sends.
- Additional ESPHome domains (`switch`, `cover`, `select`, …).
- `device_class`-based tagging or thresholds (could be a later enhancement).
