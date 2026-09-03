"""Tests for the Reflex Engine (requires jabfy-bus installed)."""

import pytest

pytest.importorskip("jabfy_bus", reason="jabfy-bus not installed — skipping reflex tests")

from jabfy_bus.core.bus import UniversalJsonBus
from jabfy_bus.core.message import Entity, Value, new_message
from jabfy_bus.core.types import Domain, MessageType, TrustLevel

from sim.config.schema import ReflexCommand, ReflexRule, ReflexTrigger
from sim.integration.reflex import ReflexEngine


def make_bus() -> UniversalJsonBus:
    return UniversalJsonBus()


def make_rule(entity_id: str, value: object, action: str, target_topic: str, name: str | None = None) -> ReflexRule:
    return ReflexRule(
        name=name or f"rule_{entity_id}_{action}",
        trigger=ReflexTrigger(entity_id=entity_id, value=value),
        command=ReflexCommand(
            action=action,
            target_entity_id=f"switch.{target_topic.split('/')[-1]}_state",
            target_domain="switch",
            target_mqtt_topic=target_topic,
        ),
    )


def make_motion_message(bus: UniversalJsonBus, entity_id: str, occupied: bool):
    return new_message(
        MessageType.TELEMETRY,
        adapter="test",
        protocol="zigbee",
        entity=Entity(
            id=entity_id,
            domain=Domain.BINARY_SENSOR.value,
            location="salon",
        ),
        value=Value(raw=occupied, normalized=occupied, datatype="bool"),
        trust_level=TrustLevel.LOCAL_GATEWAY,
    )


class TestReflexEngine:
    def test_fires_on_matching_event(self):
        bus = make_bus()
        rule = make_rule(
            entity_id="binary_sensor.salon_motion_occupancy",
            value=True,
            action="turn_on",
            target_topic="zigbee2mqtt/salon_lamp",
        )
        engine = ReflexEngine(bus, rules=[rule])
        engine.attach()

        proposals: list = []
        bus.subscribe(MessageType.COMMAND_REQUESTED.value, proposals.append, name="spy")

        msg = make_motion_message(bus, "binary_sensor.salon_motion_occupancy", occupied=True)
        bus.publish(msg)

        assert len(proposals) == 1
        assert engine.proposals == 1
        assert proposals[0].command["action"] == "turn_on"
        assert proposals[0].command["target"] == "zigbee2mqtt/salon_lamp"
        assert proposals[0].command["protocol"] == "zigbee"

    def test_does_not_fire_on_wrong_entity(self):
        bus = make_bus()
        rule = make_rule("binary_sensor.salon_motion_occupancy", True, "turn_on", "z/lamp")
        engine = ReflexEngine(bus, rules=[rule])
        engine.attach()

        proposals: list = []
        bus.subscribe(MessageType.COMMAND_REQUESTED.value, proposals.append, name="spy")

        msg = make_motion_message(bus, "binary_sensor.OTHER_motion", occupied=True)
        bus.publish(msg)

        assert len(proposals) == 0

    def test_does_not_fire_on_wrong_value(self):
        bus = make_bus()
        rule = make_rule("binary_sensor.salon_motion_occupancy", True, "turn_on", "z/lamp")
        engine = ReflexEngine(bus, rules=[rule])
        engine.attach()

        proposals: list = []
        bus.subscribe(MessageType.COMMAND_REQUESTED.value, proposals.append, name="spy")

        msg = make_motion_message(bus, "binary_sensor.salon_motion_occupancy", occupied=False)
        bus.publish(msg)

        assert len(proposals) == 0

    def test_multiple_rules(self):
        bus = make_bus()
        rules = [
            make_rule("binary_sensor.motion_a", True, "turn_on", "z/lamp_a"),
            make_rule("binary_sensor.motion_b", True, "turn_on", "z/lamp_b"),
        ]
        engine = ReflexEngine(bus, rules=rules)
        engine.attach()

        proposals: list = []
        bus.subscribe(MessageType.COMMAND_REQUESTED.value, proposals.append, name="spy")

        msg_a = make_motion_message(bus, "binary_sensor.motion_a", occupied=True)
        msg_b = make_motion_message(bus, "binary_sensor.motion_b", occupied=True)
        bus.publish(msg_a)
        bus.publish(msg_b)

        assert len(proposals) == 2
        targets = {p.command["target"] for p in proposals}
        assert targets == {"z/lamp_a", "z/lamp_b"}

    def test_deduplication_same_value(self):
        """Rule must NOT re-fire while trigger value stays the same."""
        bus = make_bus()
        rule = make_rule("binary_sensor.m", True, "turn_on", "z/lamp")
        engine = ReflexEngine(bus, rules=[rule])
        engine.attach()

        proposals: list = []
        bus.subscribe(MessageType.COMMAND_REQUESTED.value, proposals.append, name="spy")

        # Publish same event three times (simulates repeated telemetry ticks)
        for _ in range(3):
            msg = make_motion_message(bus, "binary_sensor.m", occupied=True)
            bus.publish(msg)

        assert len(proposals) == 1, "rule must fire only once while value stays True"

    def test_deduplication_resets_on_value_change(self):
        """After value changes, rule may fire again when it returns."""
        bus = make_bus()
        rule = make_rule("binary_sensor.m", True, "turn_on", "z/lamp")
        engine = ReflexEngine(bus, rules=[rule])
        engine.attach()

        proposals: list = []
        bus.subscribe(MessageType.COMMAND_REQUESTED.value, proposals.append, name="spy")

        # First motion — fires
        bus.publish(make_motion_message(bus, "binary_sensor.m", occupied=True))
        assert len(proposals) == 1

        # Motion clears — does NOT fire (value=False, trigger=True)
        bus.publish(make_motion_message(bus, "binary_sensor.m", occupied=False))
        assert len(proposals) == 1

        # Motion detected again — fires again (value changed back)
        bus.publish(make_motion_message(bus, "binary_sensor.m", occupied=True))
        assert len(proposals) == 2

    def test_correlation_id_set(self):
        bus = make_bus()
        rule = make_rule("binary_sensor.m", True, "turn_on", "z/l")
        engine = ReflexEngine(bus, rules=[rule])
        engine.attach()

        proposals: list = []
        bus.subscribe(MessageType.COMMAND_REQUESTED.value, proposals.append, name="spy")

        msg = make_motion_message(bus, "binary_sensor.m", occupied=True)
        bus.publish(msg)

        # The proposal's correlation_id should trace back to the trigger
        assert proposals[0].correlation_id == msg.message_id
