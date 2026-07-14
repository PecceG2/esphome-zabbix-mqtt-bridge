import json
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class SensorEntry:
    sensor_id: str        # globally unique: "<node>-<esphome unique_id>"
    name: str             # entity name, e.g. "Temperatura"
    domain: str
    state_topic: str
    device_name: str      # friendly device name for display, e.g. the board
    unit: Optional[str] = None


def _pick(payload: dict, *keys):
    """Return the first present key from an ESPHome/HA discovery payload.

    Home Assistant MQTT discovery payloads use abbreviated keys
    (e.g. `uniq_id`, `stat_t`, `unit_of_meas`); some tools emit the full
    keys. Accept either.
    """
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


def classify_domain(ha_component: str, payload: dict) -> str:
    """Map an ESPHome HA-discovery component to a bridge domain.

    Home Assistant has no `text_sensor` component, so ESPHome advertises its
    text_sensors under the `sensor` component. A `sensor` config without a
    numeric hint (unit of measurement or state class) is therefore treated as
    a text sensor; everything else keeps its component name.
    """
    if ha_component == "sensor":
        numeric = _pick(
            payload,
            "unit_of_measurement", "unit_of_meas",
            "state_class", "stat_cla",
        )
        return "sensor" if numeric else "text_sensor"
    return ha_component


class DiscoveryRegistry:
    def __init__(self):
        self._sensors: Dict[str, SensorEntry] = {}

    def register(self, domain: str, node: str, payload: dict) -> tuple:
        raw_uid = _pick(payload, "unique_id", "uniq_id")
        if raw_uid is None:
            raise KeyError("unique_id/uniq_id")
        # ESPHome's default unique_id generator is not unique across devices,
        # so scope it by the node name taken from the discovery topic.
        sensor_id = f"{node}-{raw_uid}"
        if sensor_id in self._sensors:
            return False, self._sensors[sensor_id]
        state_topic = _pick(payload, "state_topic", "stat_t")
        if state_topic is None:
            raise KeyError("state_topic/stat_t")
        dev = payload.get("dev") or payload.get("device") or {}
        device_name = (dev.get("name") if isinstance(dev, dict) else None) or node
        entry = SensorEntry(
            sensor_id=sensor_id,
            name=_pick(payload, "name") or raw_uid,
            domain=domain,
            state_topic=state_topic,
            device_name=device_name,
            unit=_pick(payload, "unit_of_measurement", "unit_of_meas"),
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
                "{#DEVICE_NAME}": e.device_name,
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
