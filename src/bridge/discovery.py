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

    def register(self, domain: str, payload: dict) -> tuple:
        sensor_id = _pick(payload, "unique_id", "uniq_id")
        if sensor_id is None:
            raise KeyError("unique_id/uniq_id")
        if sensor_id in self._sensors:
            return False, self._sensors[sensor_id]
        state_topic = _pick(payload, "state_topic", "stat_t")
        if state_topic is None:
            raise KeyError("state_topic/stat_t")
        entry = SensorEntry(
            sensor_id=sensor_id,
            name=_pick(payload, "name") or sensor_id,
            domain=domain,
            state_topic=state_topic,
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
