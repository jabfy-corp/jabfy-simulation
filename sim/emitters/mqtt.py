"""MQTT emitter — publishes device telemetry and receives commands.

This is the *device side* of the MQTT bridge:
- Publishes Zigbee2MQTT-format telemetry to ``<topic_prefix>`` topics.
- Subscribes to ``<topic_prefix>/set`` for inbound bus commands.
- Calls ``device.apply_command()`` when a /set message arrives.

A separate paho client is used here vs. the BusRunner so the two
roles (device emitter / jabfy-bus gateway) remain independent.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

import paho.mqtt.client as paho

from sim.config.schema import BrokerConfig
from sim.devices.base import Device

logger = logging.getLogger(__name__)


class MQTTEmitter:
    """Manages the device ↔ MQTT broker connection.

    Thread-safety: paho's loop runs in a background thread.
    ``emit()`` is safe to call from the main tick thread.
    """

    def __init__(self, broker: BrokerConfig, devices: list[Device]) -> None:
        self.broker = broker
        self._devices: dict[str, Device] = {d.id: d for d in devices}
        # topic → device  (command topics only)
        self._command_topics: dict[str, Device] = {
            d.command_topic: d for d in devices
        }
        self._client = paho.Client(
            callback_api_version=paho.CallbackAPIVersion.VERSION2,
            client_id=f"{broker.client_id_prefix}-emitter",
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._lock = threading.Lock()
        self._connected = False

    # ------------------------------------------------------------------
    # Lifecycle

    def connect(self) -> None:
        self._client.connect(self.broker.host, self.broker.port, self.broker.keepalive)
        self._client.loop_start()

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    # ------------------------------------------------------------------
    # Emit telemetry

    def emit(self, device: Device) -> None:
        """Publish current device state as a Zigbee2MQTT-format message."""
        if not self._connected:
            return
        payload = json.dumps(device.get_state())
        self._client.publish(device.telemetry_topic, payload, qos=0, retain=False)
        logger.debug("emit %s → %s", device.id, payload)

    def emit_all(self) -> None:
        """Emit telemetry for all managed devices."""
        for device in self._devices.values():
            self.emit(device)

    # ------------------------------------------------------------------
    # paho callbacks

    def _on_connect(
        self,
        client: paho.Client,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        if reason_code == 0:
            self._connected = True
            # Subscribe to command topics for each device
            for topic in self._command_topics:
                client.subscribe(topic, qos=1)
                logger.info("subscribed to %s", topic)
        else:
            logger.error("MQTT connect failed: reason_code=%s", reason_code)

    def _on_message(
        self,
        client: paho.Client,
        userdata: Any,
        msg: paho.MQTTMessage,
    ) -> None:
        """Receive a /set command from jabfy-bus's execution layer."""
        topic = msg.topic
        device = self._command_topics.get(topic)
        if device is None:
            logger.warning("received /set on unknown topic: %s", topic)
            return

        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            logger.warning("could not decode payload on %s: %r", topic, msg.payload)
            return

        # Translate Zigbee2MQTT /set payload → action + params
        action, params = _payload_to_action(payload)
        if action is None:
            logger.warning("could not determine action from /set payload: %s", payload)
            return

        result = device.apply_command(action, params)
        logger.info(
            "command %s on %s → %s (%s)",
            action,
            device.id,
            "OK" if result.success else "FAIL",
            result.reason,
        )
        if result.success:
            # Re-emit telemetry immediately so the bus sees the new state
            self.emit(device)


def _payload_to_action(payload: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    """Translate a Zigbee2MQTT /set payload to (action, params).

    Examples:
        {"state": "ON"}           → ("turn_on", {})
        {"state": "OFF"}          → ("turn_off", {})
        {"brightness": 128}       → ("set_brightness", {"brightness": 128})
        {"state": "LOCK"}         → ("lock", {})
        {"state": "UNLOCK"}       → ("unlock", {})
    """
    state = payload.get("state")
    if state is not None:
        s = str(state).upper()
        if s == "ON":
            return "turn_on", {}
        if s == "OFF":
            return "turn_off", {}
        if s == "TOGGLE":
            return "toggle", {}
        if s == "LOCK":
            return "lock", {}
        if s == "UNLOCK":
            return "unlock", {}

    if "brightness" in payload:
        return "set_brightness", {"brightness": payload["brightness"]}

    if "color" in payload:
        return "set_color", {"color": payload["color"]}

    if "occupied_heating_setpoint" in payload:
        return "set_temperature", {"temperature": payload["occupied_heating_setpoint"]}

    # Generic fallback: use "action" key if present
    if "action" in payload:
        params = {k: v for k, v in payload.items() if k != "action"}
        return payload["action"], params

    return None, {}
