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
