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
