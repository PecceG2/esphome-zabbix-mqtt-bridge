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
