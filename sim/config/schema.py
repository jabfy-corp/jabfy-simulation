"""Pydantic models for jabfy-sim YAML configuration."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class BrokerConfig(BaseModel):
    host: str = "localhost"
    port: int = 1883
    keepalive: int = 60
    client_id_prefix: str = "jabfy-sim"


class DeviceConfig(BaseModel):
    id: str
    type: str  # must match a key in DEVICE_TYPES
    location: str
    topic_prefix: str
    telemetry_interval_ms: int = 5000
    # Device-specific initial state (passed to constructor as kwargs)
    init: dict[str, Any] = Field(default_factory=dict)


class ReflexTrigger(BaseModel):
    """Condition that fires the reflex rule."""
    # Match on bus message entity_id (after Zigbee2MQTT normalization)
    entity_id: str
    # Value to match on (as python literal: true/false/number/string)
    value: Any = True
    # Optional: only match messages in this location
    location: str | None = None


class ReflexCommand(BaseModel):
    """Command to propose when the trigger fires."""
    action: str                  # e.g. "turn_on"
    target_entity_id: str        # bus entity id — used for verification policy matching
    target_domain: str           # "switch" / "light" / "lock" …
    target_mqtt_topic: str = "" # e.g. "zigbee2mqtt/salon_lamp" (for zigbee protocol)
    target_location: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    # Transport protocol — "zigbee" (default), "http_smarttv", "modbus_climate", etc.
    protocol: str = "zigbee"
    # Override transport target (for non-MQTT protocols).
    # If omitted, target_mqtt_topic is used.
    target: str | None = None


class ReflexRule(BaseModel):
    name: str
    trigger: ReflexTrigger
    command: ReflexCommand


class SimConfig(BaseModel):
    """Root configuration object."""
    broker: BrokerConfig = Field(default_factory=BrokerConfig)
    tick_interval_ms: int = 100   # how fast the device engine runs
    devices: list[DeviceConfig] = Field(default_factory=list)
    reflex_rules: list[ReflexRule] = Field(default_factory=list)
    audit_path: str | None = None  # JSONL file for audit log

    @model_validator(mode="after")
    def _unique_device_ids(self) -> "SimConfig":
        ids = [d.id for d in self.devices]
        if len(ids) != len(set(ids)):
            raise ValueError("device ids must be unique")
        return self
