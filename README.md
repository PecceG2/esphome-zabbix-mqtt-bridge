# esphome-zabbix-mqtt-bridge
A lightweight MQTT bridge that listens for ESPHome's native discovery messages and automatically registers sensors as Zabbix items via Low-Level Discovery (LLD) — no Home Assistant required.

## Why this exists

ESPHome is great at exposing sensor data, but every existing path into Zabbix falls short in one way or another:

- **ESPHome's `web_server` REST API** has no endpoint that lists all sensors on a device — you can only query `/sensor/<id>` if you already know the id exists. There is no way to ask a device "what do you have?" over plain HTTP. This is a [known, acknowledged limitation](https://github.com/esphome/feature-requests/issues/3095), not a misconfiguration.
- **Zabbix Agent2's built-in MQTT plugin (`mqtt.get`)** can read a specific topic you already know about, but it does not discover anything — every sensor on every device has to be declared by hand.
- **Prometheus (`prometheus:` component in ESPHome)** solves the "list everything" problem via a single `/metrics` endpoint, and Zabbix can parse it with the built-in Prometheus preprocessing steps. It's a valid alternative, but it adds flash/RAM footprint on the ESP and doesn't fit environments already standardized on MQTT.
- **Existing community MQTT↔Zabbix relays** (`mqtt-zabbix`, `MQTT2Zabbix`, `zbx_mqtt`, `wb-mqtt-zabbix`) all predate ESPHome/Home-Assistant-style MQTT discovery. They either require manually mapping topics to Zabbix keys, or (in the case of `wb-mqtt-zabbix`) implement real LLD support but for a completely different discovery/topic convention (Wirenboard controllers), not the `<prefix>/sensor/<device_id>/<object_id>/config` JSON payload that ESPHome publishes.

ESPHome, meanwhile, already does the hard part for free: when `mqtt: discovery: true` is set, every entity announces itself over MQTT with a retained config payload describing its name, unique ID, and state topic — the same mechanism Home Assistant uses to auto-populate devices. **This project is the missing piece that translates that self-announcement into Zabbix's discovery model**, so that:

- a new ESP32/ESP8266 flashed with ESPHome shows up in Zabbix with no manual item configuration,
- a new sensor added to an existing device's YAML shows up in Zabbix on next deploy, automatically,
- none of this requires installing or running Home Assistant — the bridge is a standalone MQTT subscriber.

## How it works

```
ESPHome device --MQTT--> Broker (Mosquitto) --MQTT--> bridge --Zabbix Sender protocol--> Zabbix Server
```

1. The bridge subscribes to the ESPHome discovery prefix (e.g. `zbx/sensor/+/+/config`).
2. On each new discovery payload, it registers the sensor internally, subscribes to its `state_topic`, and pushes a Low-Level Discovery JSON to Zabbix (via `zabbix_sender`) so the corresponding item is created from an item prototype.
3. On each subsequent state update, it forwards the value to Zabbix as trapper data.

The bridge is the only component that speaks MQTT. Zabbix only ever receives trapper (push) data — no polling, no per-device Zabbix Agent configuration.

## Usage

### 1. Configure ESPHome

Add the following to your device's YAML. Use a discovery prefix that won't conflict with other MQTT consumers (e.g. `zbx` instead of the default `homeassistant`):

```yaml
mqtt:
  broker: <mosquitto-ip>
  discovery: true
  discovery_prefix: zbx
```

Supported entity domains: `sensor`, `binary_sensor`, `text_sensor`.

### 2. Configure the bridge

```bash
git clone https://github.com/PecceG2/esphome-zabbix-mqtt-bridge.git
cd esphome-zabbix-mqtt-bridge
cp .env.example .env
```

Edit `.env` with your values:

```env
ZABBIX_SERVER=192.168.1.10   # IP or hostname of your Zabbix Server
ZABBIX_HOST=MQTT-Bridge      # name of the Zabbix host that receives trapper data
DISCOVERY_PREFIX=zbx         # must match ESPHome's discovery_prefix
```

See `.env.example` for all available options and their defaults.

### 3. Start the stack

**Option A — use the pre-built image from Docker Hub (recommended):**

```bash
docker compose up -d
```

The `docker-compose.yaml` pulls `pecceg2/esphome-zabbix-mqtt-bridge:latest` automatically — no build step needed.

**Option B — build locally from source:**

```bash
docker compose up -d --build
```

This starts Mosquitto on port 1883 and the bridge. Mosquitto data and logs are persisted under `mosquitto/data/` and `mosquitto/log/` (both gitignored).

### 4. Configure Zabbix

Create a host named `MQTT-Bridge` (or whatever you set as `ZABBIX_HOST`) with no agent interface — it only receives trapper data.

**Discovery rule:**
- Type: Zabbix trapper
- Key: `esphome.discovery`

**Item prototype** (inside the discovery rule):
- Type: Zabbix trapper
- Key: `esphome.sensor[{#SENSOR_ID}]`
- Name: `{#SENSOR_NAME}`
- Available macros: `{#SENSOR_ID}`, `{#SENSOR_NAME}`, `{#SENSOR_DOMAIN}`

Once a device comes online and publishes its discovery payload, the bridge sends the LLD to Zabbix, the item prototype fires, and values start flowing — no manual item configuration required.

## Scope

- Targets ESPHome devices with `mqtt: discovery: true` configured.
- Covers `sensor`, `binary_sensor`, and `text_sensor` domains. Extending to other entity types (`switch`, `cover`, etc.) is a matter of subscribing to additional discovery wildcards.
- Not a general-purpose MQTT-to-Zabbix relay — it specifically understands ESPHome/Home-Assistant-style discovery payloads, which is what none of the existing community tools do out of the box.

## Status

This project is currently being used in production to monitor medication temperature systems and electrical power consumption across multiple companies, 24/7, without issues.

If you encounter any bugs or would like to request a new feature, feel free to do so through the GitHub Issues page.