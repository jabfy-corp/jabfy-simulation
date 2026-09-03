"""BusRunner — embeds jabfy-bus pipeline in-process with real MQTT, HTTP, and Modbus.

Architecture:

    ┌─────────────────────────────────────────────────────────────────────┐
    │ Protocol sources                                                    │
    │                                                                     │
    │  Mosquitto ──paho──► Zigbee2MQTTAdapter ──┐                        │
    │  SmartTV HTTP ──────► HTTPPollingAdapter ──┤                        │
    │  Modbus TCP ────────► ModbusAdapter ───────┤                        │
    │                                            ▼                        │
    │                                    UniversalJsonBus                 │
    │                                            │                        │
    │                              ReflexEngine (proposes)               │
    │                                            │ command.requested      │
    │                             VerificationEngine (verifies)          │
    │                                            │ command.approved       │
    │                               ExecutionLayer                        │
    │                          ┌─────────────────┤                        │
    │                          │                 │                        │
    │  Mosquitto ◄─paho────────┘ "zigbee"        │ "http_smarttv"        │
    │  SmartTV HTTP POST ◄──────────────────────┘  ◄── urllib.request    │
    │  Modbus TCP write ◄── "modbus_climate" ◄── ModbusTcpWriter         │
    │                                                                     │
    │                                   AuditLog (SHA-256 chain)         │
    └─────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any

import paho.mqtt.client as paho

from jabfy_bus.adapters.http.adapter import Endpoint, HTTPPollingAdapter
from jabfy_bus.adapters.modbus.adapter import ModbusAdapter
from jabfy_bus.adapters.modbus.registers import RegisterMap, RegisterSpec, RegisterType
from jabfy_bus.adapters.zigbee2mqtt.adapter import Zigbee2MQTTAdapter
from jabfy_bus.audit.log import AuditLog
from jabfy_bus.core.bus import UniversalJsonBus
from jabfy_bus.core.registry import EntityRegistry
from jabfy_bus.core.types import (
    Action, AdapterMode, Domain, EntityClass, RiskLevel, TrustLevel,
)
from jabfy_bus.execution.executor import ExecutionLayer
from jabfy_bus.execution.translators import TRANSLATORS
from jabfy_bus.verification.engine import VerificationEngine
from jabfy_bus.verification.policies import Policy
from jabfy_bus.verification.risk import classify_risk

from sim.config.schema import BrokerConfig, ReflexRule
from sim.integration.modbus_client import ModbusTcpReader, ModbusTcpWriter
from sim.integration.reflex import ReflexEngine

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Configuration dataclasses
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class SmartTVHttpConfig:
    """Config for HTTP polling of one SmartTV device."""
    entity_id: str           # e.g. "switch.living_tv"
    location: str
    base_url: str            # e.g. "http://localhost:8001/api/v2"
    poll_interval_s: float = 5.0


@dataclass
class ClimateModbusUnit:
    """One climate device mapped to a Modbus unit."""
    unit_id: int
    device_id: str           # jabfy-sim device id (for logging)
    location: str
    has_humidity: bool = False   # True for TemperatureSensor
    has_setpoint: bool = False   # True for Thermostat


@dataclass
class ModbusClimateConfig:
    """Config for Modbus polling of climate devices."""
    host: str = "localhost"
    port: int = 5020
    units: list[ClimateModbusUnit] = field(default_factory=list)
    poll_interval_s: float = 10.0


# ──────────────────────────────────────────────────────────────────────────────
# Custom translators (registered into jabfy-bus at import time)
# ──────────────────────────────────────────────────────────────────────────────

_HTTP_STATE = {
    Action.TURN_ON: "on",
    Action.TURN_OFF: "off",
}


def _to_http_smarttv(command: dict[str, Any]) -> dict[str, Any]:
    """Translate a normalised command to a Samsung SmartThings-style HTTP request.

    Returns: {"target": full_url, "payload": json_body, "method": "POST"}
    """
    action_str = command["action"]
    base_url = command["target"].rstrip("/")   # e.g. http://localhost:8001/api/v2
    params = command.get("params", {})

    try:
        action = Action(action_str)
    except ValueError:
        action = None

    if action in _HTTP_STATE:
        return {
            "target": f"{base_url}/power",
            "payload": {"state": _HTTP_STATE[action]},
            "method": "POST",
        }
    if action_str == "set_volume":
        return {
            "target": f"{base_url}/volume",
            "payload": {"volume": params.get("volume", 30)},
            "method": "POST",
        }
    if action_str in ("set_source", "select_source"):
        return {
            "target": f"{base_url}/source",
            "payload": {"source": params.get("source", "HDMI1")},
            "method": "POST",
        }
    # Generic fallback
    return {
        "target": f"{base_url}/command",
        "payload": {"action": action_str, **params},
        "method": "POST",
    }


def _to_modbus_climate(command: dict[str, Any]) -> dict[str, Any]:
    """Translate a climate command to a Modbus write spec.

    Returns: {"target": unit_id_str, "payload": {register_type, address, value}}
    """
    action_str = command["action"]
    unit_id_str = command["target"]  # unit_id as string
    params = command.get("params", {})

    if action_str == "set_temperature":
        temp = float(params.get("temperature", 20.0))
        return {
            "target": unit_id_str,
            "payload": {
                "register_type": RegisterType.HOLDING_REGISTER.value,
                "address": 0,          # HR 0 = setpoint × 10
                "value": round(temp * 10),
            },
        }
    raise ValueError(f"modbus_climate: unsupported action '{action_str}'")


# Register custom translators into jabfy-bus (module-level mutation is safe)
TRANSLATORS["http_smarttv"] = _to_http_smarttv
TRANSLATORS["modbus_climate"] = _to_modbus_climate


# ──────────────────────────────────────────────────────────────────────────────
# Default verification policies
# ──────────────────────────────────────────────────────────────────────────────

_DEFAULT_POLICIES = [
    Policy(
        name="sim_lights_medium_v1",
        effect="allow",
        max_risk=RiskLevel.MEDIUM,
        domains={Domain.SWITCH.value, Domain.LIGHT.value},
        actions={
            Action.TURN_ON.value, Action.TURN_OFF.value,
            Action.TOGGLE.value, Action.SET_BRIGHTNESS.value,
        },
        min_trust=TrustLevel.INTERNAL,
    ),
    Policy(
        name="sim_climate_medium_v1",
        effect="allow",
        max_risk=RiskLevel.MEDIUM,
        domains={Domain.CLIMATE.value},
        actions={Action.SET_TEMPERATURE.value},
        min_trust=TrustLevel.INTERNAL,
    ),
    # SmartTV power via HTTP: treated as switch domain
    Policy(
        name="sim_tv_medium_v1",
        effect="allow",
        max_risk=RiskLevel.MEDIUM,
        domains={Domain.SWITCH.value},
        actions={Action.TURN_ON.value, Action.TURN_OFF.value, Action.TOGGLE.value},
        min_trust=TrustLevel.INTERNAL,
    ),
]


# ──────────────────────────────────────────────────────────────────────────────
# BusRunner
# ──────────────────────────────────────────────────────────────────────────────

class BusRunner:
    """Wires the full jabfy-bus pipeline with MQTT, HTTP, and Modbus.

    All adapters connect to the same in-process UniversalJsonBus.
    Polling threads are daemon threads — they die when the process exits.
    """

    def __init__(
        self,
        broker: BrokerConfig,
        reflex_rules: list[ReflexRule] | None = None,
        audit_path: str | None = None,
        policies: list[Policy] | None = None,
        http_configs: list[SmartTVHttpConfig] | None = None,
        modbus_config: ModbusClimateConfig | None = None,
    ) -> None:
        # ── jabfy-bus core pipeline ──────────────────────────────────────
        self.bus = UniversalJsonBus()

        self.audit = AuditLog(audit_path)
        self.audit.attach(self.bus)

        self.registry = EntityRegistry()
        self.registry.attach(self.bus)

        self.z2m = Zigbee2MQTTAdapter(
            self.bus,
            base_topic="zigbee2mqtt",
            name="sim_z2m_adapter",
            trust_level=TrustLevel.LOCAL_GATEWAY,
        )
        self.z2m.start()

        self.verification = VerificationEngine(
            self.bus,
            policies=policies or _DEFAULT_POLICIES,
        )
        self.verification.attach()

        self.execution = ExecutionLayer(self.bus, audit=self.audit)
        self.execution.attach()

        # ── Reflex Engine (jabfy-core stub) ──────────────────────────────
        self.reflex = ReflexEngine(self.bus, rules=reflex_rules or [])
        self.reflex.attach()

        # ── paho MQTT client (Zigbee2MQTT gateway) ───────────────────────
        self.broker = broker
        self._client = paho.Client(
            callback_api_version=paho.CallbackAPIVersion.VERSION2,
            client_id=f"{broker.client_id_prefix}-bus",
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._connected = False

        # Register MQTT/Zigbee transport
        self.execution.register_transport("zigbee", self._mqtt_transport)
        self.execution.register_transport("mqtt",   self._mqtt_transport)

        # ── HTTP adapter (SmartTV polling) ───────────────────────────────
        self._http_adapters: list[HTTPPollingAdapter] = []
        self._http_configs: list[SmartTVHttpConfig] = http_configs or []
        self._poll_threads: list[threading.Thread] = []

        for cfg in self._http_configs:
            adapter = self._build_http_adapter(cfg)
            adapter.start()
            self._http_adapters.append(adapter)

        # Register SmartTV HTTP transport
        self.execution.register_transport("http_smarttv", self._http_smarttv_transport)

        # ── Modbus adapter (climate polling) ─────────────────────────────
        self._modbus_adapters: list[ModbusAdapter] = []
        self._modbus_reader: ModbusTcpReader | None = None
        self._modbus_writer: ModbusTcpWriter | None = None
        self._modbus_config: ModbusClimateConfig | None = modbus_config

        if modbus_config and modbus_config.units:
            self._modbus_reader = ModbusTcpReader(modbus_config.host, modbus_config.port)
            self._modbus_writer = ModbusTcpWriter(modbus_config.host, modbus_config.port)
            for unit in modbus_config.units:
                adapter = self._build_modbus_adapter(unit, modbus_config)
                adapter.start()
                self._modbus_adapters.append(adapter)

        # Register Modbus climate transport
        self.execution.register_transport("modbus_climate", self._modbus_climate_transport)

        self._running = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Connect to MQTT broker, start background threads."""
        self._client.connect(self.broker.host, self.broker.port, self.broker.keepalive)
        self._client.loop_start()
        logger.info("BusRunner connecting to %s:%s", self.broker.host, self.broker.port)

        self._running = True

        # Start HTTP polling threads
        for i, (adapter, cfg) in enumerate(zip(self._http_adapters, self._http_configs)):
            t = threading.Thread(
                target=self._http_poll_loop,
                args=(adapter, cfg.poll_interval_s),
                daemon=True,
                name=f"http-poll-{i}",
            )
            t.start()
            self._poll_threads.append(t)

        # Start Modbus polling thread (one thread polls all units)
        if self._modbus_adapters and self._modbus_config:
            t = threading.Thread(
                target=self._modbus_poll_loop,
                args=(self._modbus_adapters, self._modbus_config.poll_interval_s),
                daemon=True,
                name="modbus-poll",
            )
            t.start()
            self._poll_threads.append(t)

    def disconnect(self) -> None:
        self._running = False
        self._client.loop_stop()
        self._client.disconnect()
        if self._modbus_reader:
            self._modbus_reader.close()
        if self._modbus_writer:
            self._modbus_writer.close()

    # ── Polling loops (daemon threads) ────────────────────────────────────────

    def _http_poll_loop(self, adapter: HTTPPollingAdapter, interval_s: float) -> None:
        while self._running:
            try:
                n = adapter.poll_once()
                logger.debug("HTTP poll: %d messages emitted", n)
            except Exception as exc:  # noqa: BLE001
                logger.warning("HTTP poll error: %s", exc)
            time.sleep(interval_s)

    def _modbus_poll_loop(self, adapters: list[ModbusAdapter], interval_s: float) -> None:
        while self._running:
            for adapter in adapters:
                try:
                    n = adapter.poll_once()
                    logger.debug("Modbus poll (%s): %d messages emitted", adapter.name, n)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Modbus poll error (%s): %s", adapter.name, exc)
            time.sleep(interval_s)

    # ── Adapter builders ──────────────────────────────────────────────────────

    def _build_http_adapter(self, cfg: SmartTVHttpConfig) -> HTTPPollingAdapter:
        """Build an HTTPPollingAdapter for a SmartTV device."""
        state_url = f"{cfg.base_url.rstrip('/')}/state"
        endpoints = [
            Endpoint(
                url=state_url,
                entity_id=f"{cfg.entity_id}_switch",
                domain=Domain.SWITCH,
                value_path="switch",
                capabilities=["read", "write"],
            ),
            Endpoint(
                url=state_url,
                entity_id=f"{cfg.entity_id}_volume",
                domain=Domain.SENSOR,
                value_path="volume",
            ),
        ]
        return HTTPPollingAdapter(
            self.bus,
            endpoints=endpoints,
            name=f"http_{cfg.entity_id}",
            mode=AdapterMode.READ_WRITE,
            trust_level=TrustLevel.LOCAL_NETWORK,
        )

    def _build_modbus_adapter(
        self, unit: ClimateModbusUnit, cfg: ModbusClimateConfig
    ) -> ModbusAdapter:
        """Build a ModbusAdapter for one climate unit."""
        specs: list[RegisterSpec] = [
            RegisterSpec(
                address=0,
                register_type=RegisterType.INPUT_REGISTER,
                entity_id=f"sensor.{unit.device_id}_temperature",
                domain=Domain.SENSOR,
                entity_class=EntityClass.TEMPERATURE,
                unit="°C",
                scale=0.1,    # raw 235 → 23.5 °C
                asset=unit.location,
            ),
        ]
        if unit.has_humidity:
            specs.append(RegisterSpec(
                address=1,
                register_type=RegisterType.INPUT_REGISTER,
                entity_id=f"sensor.{unit.device_id}_humidity",
                domain=Domain.SENSOR,
                entity_class=EntityClass.HUMIDITY,
                unit="%",
                scale=0.1,    # raw 550 → 55.0 %
                asset=unit.location,
            ))
        if unit.has_setpoint:
            specs.append(RegisterSpec(
                address=0,
                register_type=RegisterType.HOLDING_REGISTER,
                entity_id=f"climate.{unit.device_id}_setpoint",
                domain=Domain.CLIMATE,
                unit="°C",
                scale=0.1,
                write_allowed=True,
                asset=unit.location,
            ))

        rmap = RegisterMap(unit_id=unit.unit_id, specs=specs)
        return ModbusAdapter(
            self.bus,
            register_map=rmap,
            host=cfg.host,
            port=cfg.port,
            reader=self._modbus_reader,
            writer=self._modbus_writer,
            name=f"modbus_{unit.device_id}",
            mode=AdapterMode.READ_WRITE if unit.has_setpoint else AdapterMode.READ_ONLY,
            trust_level=TrustLevel.LOCAL_NETWORK,
        )

    # ── Custom transports ─────────────────────────────────────────────────────

    def _mqtt_transport(self, target: str, payload: Any) -> None:
        """Publish a command to the MQTT broker (zigbee/mqtt protocols)."""
        body = payload if isinstance(payload, str) else json.dumps(payload)
        self._client.publish(target, body, qos=1, retain=False)
        logger.debug("bus → mqtt: %s %s", target, body)

    def _http_smarttv_transport(self, target: str, payload: Any) -> None:
        """POST a command to the SmartTV REST API (http_smarttv protocol).

        target: full URL, e.g. http://localhost:8001/api/v2/power
        payload: JSON-serialisable dict body
        """
        data = json.dumps(payload).encode() if payload else b""
        req = urllib.request.Request(
            target,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
                resp.read()
            logger.debug("http_smarttv → POST %s OK", target)
        except Exception as exc:  # noqa: BLE001
            logger.warning("http_smarttv transport failed: %s → %s", target, exc)
            raise

    def _modbus_climate_transport(self, target: str, payload: Any) -> None:
        """Write a register via the Modbus TCP writer (modbus_climate protocol).

        target: unit_id as string, e.g. "1"
        payload: {register_type, address, value}
        """
        if self._modbus_writer is None:
            raise RuntimeError("No Modbus writer configured")
        unit_id = int(target)
        reg_type = RegisterType(payload["register_type"])
        address = int(payload["address"])
        value = int(payload["value"])
        self._modbus_writer.write(unit_id, reg_type, address, value)
        logger.debug(
            "modbus_climate → write unit=%d %s@%d = %d",
            unit_id, reg_type.value, address, value,
        )

    # ── paho callbacks ────────────────────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code == 0:
            self._connected = True
            client.subscribe("zigbee2mqtt/#", qos=0)
            logger.info("BusRunner connected — subscribed to zigbee2mqtt/#")
        else:
            logger.error("BusRunner MQTT connect failed: %s", reason_code)

    def _on_message(self, client, userdata, msg) -> None:
        try:
            self.z2m.handle_mqtt(msg.topic, msg.payload)
        except Exception:  # noqa: BLE001
            logger.exception("error handling MQTT message on %s", msg.topic)

    # ── Stats ─────────────────────────────────────────────────────────────────

    @property
    def _connected(self) -> bool:
        return getattr(self, "_connected_flag", False)

    @_connected.setter
    def _connected(self, v: bool) -> None:
        self._connected_flag = v

    def stats(self) -> dict[str, Any]:
        return {
            "connected": self._connected,
            "entities": len(self.registry),
            "decisions": len(self.verification.decisions),
            "executed": self.execution.executed,
            "failed": self.execution.failed,
            "proposals": self.reflex.proposals,
            "audit_records": len(self.audit),
            "audit_valid": self.audit.verify(),
            "http_adapters": len(self._http_adapters),
            "modbus_adapters": len(self._modbus_adapters),
        }
