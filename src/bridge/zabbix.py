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
