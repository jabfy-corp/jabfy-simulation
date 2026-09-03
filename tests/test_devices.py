"""Unit tests for device state machines."""

import pytest

from sim.devices.climate import TemperatureSensor, Thermostat
from sim.devices.lighting import DimmerLight, OnOffLight, RGBBulb
from sim.devices.security import AlarmSiren, DoorLock, MotionSensor, SmokeSensor


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_light(**kwargs):
    defaults = dict(id="test_lamp", location="salon", topic_prefix="zigbee2mqtt/test_lamp")
    return OnOffLight(**{**defaults, **kwargs})


def make_dimmer(**kwargs):
    defaults = dict(id="test_dimmer", location="salon", topic_prefix="zigbee2mqtt/test_dimmer")
    return DimmerLight(**{**defaults, **kwargs})


def make_motion(**kwargs):
    defaults = dict(id="test_motion", location="salon", topic_prefix="zigbee2mqtt/test_motion", telemetry_interval_ms=100)
    return MotionSensor(**{**defaults, **kwargs})


def make_lock(**kwargs):
    defaults = dict(id="test_lock", location="entree", topic_prefix="zigbee2mqtt/test_lock")
    return DoorLock(**{**defaults, **kwargs})


# ── OnOffLight ────────────────────────────────────────────────────────────────

class TestOnOffLight:
    def test_initial_state_off(self):
        lamp = make_light()
        assert lamp.get_state() == {"state": "OFF"}

    def test_turn_on(self):
        lamp = make_light()
        r = lamp.apply_command("turn_on")
        assert r.success
        assert lamp.get_state()["state"] == "ON"

    def test_turn_off(self):
        lamp = make_light(state=True)
        r = lamp.apply_command("turn_off")
        assert r.success
        assert lamp.get_state()["state"] == "OFF"

    def test_toggle(self):
        lamp = make_light()
        lamp.apply_command("toggle")
        assert lamp.get_state()["state"] == "ON"
        lamp.apply_command("toggle")
        assert lamp.get_state()["state"] == "OFF"

    def test_unknown_action_fails(self):
        lamp = make_light()
        r = lamp.apply_command("explode")
        assert not r.success

    def test_command_case_insensitive(self):
        lamp = make_light()
        lamp.apply_command("TURN_ON")
        assert lamp.get_state()["state"] == "ON"

    def test_topics(self):
        lamp = make_light()
        assert lamp.telemetry_topic == "zigbee2mqtt/test_lamp"
        assert lamp.command_topic == "zigbee2mqtt/test_lamp/set"


# ── DimmerLight ───────────────────────────────────────────────────────────────

class TestDimmerLight:
    def test_initial_state(self):
        d = make_dimmer()
        state = d.get_state()
        assert state["state"] == "OFF"
        assert state["brightness"] == 0

    def test_turn_on_sets_default_brightness(self):
        d = make_dimmer()
        d.apply_command("turn_on")
        state = d.get_state()
        assert state["state"] == "ON"
        assert state["brightness"] == 254

    def test_set_brightness(self):
        d = make_dimmer()
        r = d.apply_command("set_brightness", {"brightness": 128})
        assert r.success
        assert d.get_state()["brightness"] == 128
        assert d.get_state()["state"] == "ON"

    def test_brightness_zero_turns_off(self):
        d = make_dimmer(state=True, brightness=200)
        d.apply_command("set_brightness", {"brightness": 0})
        assert d.get_state()["state"] == "OFF"

    def test_brightness_clamped(self):
        d = make_dimmer()
        d.apply_command("set_brightness", {"brightness": 999})
        assert d.get_state()["brightness"] == 254
        d.apply_command("set_brightness", {"brightness": -5})
        assert d.get_state()["brightness"] == 0


# ── RGBBulb ───────────────────────────────────────────────────────────────────

class TestRGBBulb:
    def make(self):
        return RGBBulb(id="bulb", location="salon", topic_prefix="zigbee2mqtt/bulb")

    def test_initial_color(self):
        b = self.make()
        assert b.get_state()["color"] == {"r": 255, "g": 255, "b": 255}

    def test_set_color(self):
        b = self.make()
        r = b.apply_command("set_color", {"color": {"r": 255, "g": 0, "b": 0}})
        assert r.success
        assert b.get_state()["color"] == {"r": 255, "g": 0, "b": 0}


# ── MotionSensor ──────────────────────────────────────────────────────────────

class TestMotionSensor:
    def test_initial_no_occupancy(self):
        m = make_motion()
        assert m.get_state()["occupancy"] is False

    def test_trigger_motion(self):
        m = make_motion()
        m.trigger_motion(duration_ms=500)
        assert m.get_state()["occupancy"] is True

    def test_motion_clears_after_duration(self):
        m = make_motion()
        m.trigger_motion(duration_ms=100)
        # Tick 200ms — should clear
        m.tick(200)
        assert m.get_state()["occupancy"] is False

    def test_motion_not_cleared_before_duration(self):
        m = make_motion()
        m.trigger_motion(duration_ms=1000)
        m.tick(200)
        assert m.get_state()["occupancy"] is True

    def test_read_only(self):
        m = make_motion()
        r = m.apply_command("turn_on")
        assert not r.success

    def test_trigger_forces_telemetry(self):
        m = make_motion(telemetry_interval_ms=60000)
        m.trigger_motion()
        assert m.tick(10) is True  # forced by trigger


# ── DoorLock ──────────────────────────────────────────────────────────────────

class TestDoorLock:
    def test_initially_locked(self):
        lock = make_lock()
        assert lock.get_state()["state"] == "LOCK"

    def test_unlock(self):
        lock = make_lock()
        r = lock.apply_command("unlock")
        assert r.success
        assert lock.get_state()["state"] == "UNLOCK"

    def test_lock(self):
        lock = make_lock(locked=False)
        r = lock.apply_command("lock")
        assert r.success
        assert lock.get_state()["state"] == "LOCK"


# ── SmokeSensor ───────────────────────────────────────────────────────────────

class TestSmokeSensor:
    def make(self):
        return SmokeSensor(id="smoke", location="cuisine", topic_prefix="zigbee2mqtt/smoke")

    def test_no_smoke_initially(self):
        s = self.make()
        assert s.get_state()["smoke"] is False

    def test_trigger_and_clear(self):
        s = self.make()
        s.trigger_alarm()
        assert s.get_state()["smoke"] is True
        s.clear_alarm()
        assert s.get_state()["smoke"] is False

    def test_read_only(self):
        s = self.make()
        r = s.apply_command("turn_off")
        assert not r.success


# ── TemperatureSensor ─────────────────────────────────────────────────────────

class TestTemperatureSensor:
    def make(self):
        return TemperatureSensor(
            id="temp", location="salon", topic_prefix="zigbee2mqtt/temp",
            temperature=20.0, humidity=50.0, seed=42,
        )

    def test_initial_state(self):
        s = self.make()
        state = s.get_state()
        assert state["temperature"] == 20.0
        assert state["humidity"] == 50.0

    def test_drifts_after_tick(self):
        # Tick many times — drift accumulates and will differ from 20.0
        s = TemperatureSensor(
            id="temp", location="salon", topic_prefix="zigbee2mqtt/temp",
            temperature=20.0, humidity=50.0, drift=0.5, seed=42,
        )
        for _ in range(20):
            s.tick(1000)
        state = s.get_state()
        assert state["temperature"] != 20.0  # drifted

    def test_read_only(self):
        s = self.make()
        r = s.apply_command("set_temperature", {"temperature": 25.0})
        assert not r.success


# ── Thermostat ────────────────────────────────────────────────────────────────

class TestThermostat:
    def make(self):
        return Thermostat(
            id="thermo", location="salon", topic_prefix="zigbee2mqtt/thermo",
            setpoint=20.0, current_temperature=18.0,
        )

    def test_initial_heating(self):
        t = self.make()
        assert t.heating is True  # 18 < 20

    def test_set_temperature(self):
        t = self.make()
        r = t.apply_command("set_temperature", {"temperature": 15.0})
        assert r.success
        assert t.setpoint == 15.0
        assert t.heating is False  # 18 > 15

    def test_state_keys(self):
        t = self.make()
        state = t.get_state()
        assert "occupied_heating_setpoint" in state
        assert "local_temperature" in state
        assert "running_state" in state


# ── Tick loop ─────────────────────────────────────────────────────────────────

class TestTickLoop:
    def test_telemetry_interval(self):
        lamp = OnOffLight(
            id="l", location="s", topic_prefix="z/l", telemetry_interval_ms=1000
        )
        # Should not emit before interval
        assert lamp.tick(500) is False
        assert lamp.tick(400) is False
        # Should emit at interval
        assert lamp.tick(200) is True  # 500+400+200=1100 ≥ 1000
        # Should not emit again immediately
        assert lamp.tick(100) is False

    def test_force_telemetry(self):
        lamp = OnOffLight(
            id="l", location="s", topic_prefix="z/l", telemetry_interval_ms=60000
        )
        lamp.force_telemetry()
        assert lamp.tick(1) is True
