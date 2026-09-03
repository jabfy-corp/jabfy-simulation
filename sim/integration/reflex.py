"""Reflex Engine — rule-based stub for jabfy-core.

Subscribes to bus events. When a trigger fires, proposes a
``command.requested`` on the bus. This is replaced by jabfy-core
(the actual reasoning engine) in Phase 2.

Rules are declared in YAML:

    reflex_rules:
      - name: motion_to_light
        trigger:
          entity_id: "binary_sensor.salon_motion_occupancy"
          value: true
        command:
          action: turn_on
          target_entity_id: "switch.salon_lamp_state"
          target_domain: switch
          target_mqtt_topic: "zigbee2mqtt/salon_lamp"
          target_location: salon
"""

from __future__ import annotations

import logging
from typing import Any

from jabfy_bus.core.bus import UniversalJsonBus
from jabfy_bus.core.message import BusMessage, Entity, new_message
from jabfy_bus.core.types import MessageType, TrustLevel

from sim.config.schema import ReflexRule

logger = logging.getLogger(__name__)


# Sentinel used to distinguish "never fired" from a fired value of None.
_NEVER: object = object()


class ReflexEngine:
    """Converts matching bus events into command.requested proposals.

    One-shot deduplication: a rule fires at most once per distinct trigger
    value transition. When the trigger entity's value changes away from the
    trigger value (e.g. occupancy True → False), the rule's dedup state
    resets so it can fire again on the next True.

    This prevents repeated proposals while a sensor holds a stable value
    across multiple telemetry ticks (the common case: motion sensor emits
    occupancy=True every 200ms for the duration of the motion).
    """

    def __init__(self, bus: UniversalJsonBus, rules: list[ReflexRule]) -> None:
        self.bus = bus
        self.rules = rules
        self.proposals: int = 0
        # rule.name → the trigger value that caused the last proposal
        self._last_fired: dict[str, Any] = {}
        # entity_id → last normalised value observed on that entity
        self._entity_values: dict[str, Any] = {}

    def attach(self) -> None:
        """Subscribe to bus telemetry and state-change events."""
        self.bus.subscribe(
            MessageType.TELEMETRY.value, self._on_event, name="reflex_engine"
        )
        self.bus.subscribe(
            MessageType.STATE_CHANGED.value, self._on_event, name="reflex_engine"
        )

    def _on_event(self, message: BusMessage) -> None:
        entity = message.entity
        if entity is None or message.value is None:
            return

        current_value = message.value.normalized
        entity_id = entity.id
        prev_value = self._entity_values.get(entity_id, _NEVER)

        # When a trigger entity's value changes, reset dedup for all rules
        # that watch that entity — so they can fire again on the next match.
        if prev_value is not _NEVER and current_value != prev_value:
            for rule in self.rules:
                if rule.trigger.entity_id == entity_id:
                    self._last_fired.pop(rule.name, None)

        self._entity_values[entity_id] = current_value

        for rule in self.rules:
            if self._matches(rule, message, current_value):
                self._propose(rule, message)

    def _matches(self, rule: ReflexRule, message: BusMessage, current_value: Any) -> bool:
        """Return True if this bus message satisfies the rule trigger."""
        entity = message.entity
        if entity is None:
            return False
        if entity.id != rule.trigger.entity_id:
            return False
        if rule.trigger.location and entity.location != rule.trigger.location:
            return False
        if current_value != rule.trigger.value:
            return False
        # One-shot: skip if we already proposed for this exact value in this run
        if self._last_fired.get(rule.name, _NEVER) == current_value:
            return False
        return True

    def _propose(self, rule: ReflexRule, trigger: BusMessage) -> None:
        """Publish a command.requested for this rule."""
        # Record before publishing so re-entrant bus handlers see it
        self._last_fired[rule.name] = rule.trigger.value

        cmd = rule.command
        # target: explicit override > target_mqtt_topic (for non-MQTT protocols)
        effective_target = cmd.target if cmd.target is not None else cmd.target_mqtt_topic
        request = new_message(
            MessageType.COMMAND_REQUESTED,
            adapter="reflex_engine",
            protocol="internal",
            entity=Entity(
                id=cmd.target_entity_id,
                domain=cmd.target_domain,
                location=cmd.target_location,
                name=cmd.target_entity_id,
            ),
            command={
                "action": cmd.action,
                "target": effective_target,
                "protocol": cmd.protocol,
                "params": dict(cmd.params),
            },
            trust_level=TrustLevel.INTERNAL,
            correlation_id=trigger.message_id,
            raw={"triggered_by": trigger.entity.id if trigger.entity else None, "rule": rule.name},
        )
        self.proposals += 1
        logger.info(
            "rule '%s' fired → propose %s on %s",
            rule.name,
            cmd.action,
            cmd.target_mqtt_topic,
        )
        self.bus.publish(request)
