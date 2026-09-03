"""Tests for the Modbus TCP server and its action callbacks.

The action callback is the core mechanism that syncs device state ↔ registers.
We test the callback directly (no network sockets needed).
"""

import asyncio
import pytest

from sim.devices.climate import TemperatureSensor, Thermostat
from sim.emitters.modbus_server import ModbusServer, _make_action


def make_sensor(**kwargs) -> TemperatureSensor:
    defaults = dict(
        id="temp_sensor",
        location="salon",
        topic_prefix="zigbee2mqtt/temp",
        temperature=23.5,
        humidity=55.0,
        seed=42,
    )
    return TemperatureSensor(**{**defaults, **kwargs})


def make_thermostat(**kwargs) -> Thermostat:
    defaults = dict(
        id="thermostat",
        location="salon",
        topic_prefix="zigbee2mqtt/thermo",
        setpoint=20.0,
        current_temperature=18.5,
    )
    return Thermostat(**{**defaults, **kwargs})


def run_action(device, fc, start_address, count, current_registers, set_values=None):
    """Run the action callback synchronously."""
    action = _make_action(device)
    return asyncio.run(action(fc, start_address, 0, count, current_registers, set_values))


# ── Action callback — reads ───────────────────────────────────────────────────

class TestActionCallbackRead:
    def test_ir_temperature_refreshed(self):
        """FC4 read → current_registers[0] = temperature × 10."""
        sensor = make_sensor(temperature=23.5)
        regs = [0, 0]
        run_action(sensor, fc=4, start_address=0, count=2, current_registers=regs)
        assert regs[0] == 235   # 23.5 × 10
        assert regs[1] == 550   # 55.0 × 10

    def test_ir_humidity_refreshed(self):
        sensor = make_sensor(temperature=20.0, humidity=60.0)
        regs = [0, 0]
        run_action(sensor, fc=4, start_address=0, count=2, current_registers=regs)
        assert regs[1] == 600   # 60.0 × 10

    def test_ir_partial_read_single_register(self):
        """Read only register 0 — register 1 should not be touched."""
        sensor = make_sensor(temperature=19.0)
        regs = [0]  # only asking for 1 register
        run_action(sensor, fc=4, start_address=0, count=1, current_registers=regs)
        assert regs[0] == 190   # 19.0 × 10

    def test_hr_setpoint_refreshed(self):
        """FC3 read → current_registers[0] = setpoint × 10."""
        thermo = make_thermostat(setpoint=21.5)
        regs = [0, 0]
        run_action(thermo, fc=3, start_address=0, count=2, current_registers=regs)
        assert regs[0] == 215   # 21.5 × 10

    def test_hr_heating_state_refreshed(self):
        """FC3 read → current_registers[1] = 1 when running_state == 'heat'."""
        thermo = make_thermostat(setpoint=25.0, current_temperature=18.0)
        assert thermo.heating is True
        assert thermo.get_state()["running_state"] == "heat"
        regs = [0, 0]
        run_action(thermo, fc=3, start_address=0, count=2, current_registers=regs)
        assert regs[1] == 1   # heat = 1

    def test_hr_not_heating(self):
        thermo = make_thermostat(setpoint=15.0, current_temperature=18.0)
        assert thermo.heating is False
        regs = [0, 0]
        run_action(thermo, fc=3, start_address=0, count=2, current_registers=regs)
        assert regs[1] == 0   # not heating

    def test_sensor_hr_read_returns_zeros(self):
        """TemperatureSensor has no setpoint — HR regs should be 0."""
        sensor = make_sensor()
        regs = [0, 0]
        run_action(sensor, fc=3, start_address=0, count=2, current_registers=regs)
        assert regs[0] == 0
        assert regs[1] == 0


# ── Action callback — writes ──────────────────────────────────────────────────

class TestActionCallbackWrite:
    def test_hr_write_setpoint(self):
        """FC6 write → device.apply_command('set_temperature')."""
        thermo = make_thermostat(setpoint=20.0)
        run_action(
            thermo, fc=6, start_address=0, count=1,
            current_registers=[200], set_values=[225],  # 22.5 °C
        )
        assert thermo.setpoint == 22.5

    def test_hr_write_multiple_registers(self):
        """FC16 write → first register is setpoint."""
        thermo = make_thermostat(setpoint=20.0)
        run_action(
            thermo, fc=16, start_address=0, count=2,
            current_registers=[200, 1], set_values=[180, 0],  # 18.0 °C
        )
        assert thermo.setpoint == 18.0

    def test_sensor_write_ignored(self):
        """Writing setpoint to a read-only TemperatureSensor does nothing."""
        sensor = make_sensor()
        # TemperatureSensor has no apply_command for set_temperature
        run_action(
            sensor, fc=6, start_address=0, count=1,
            current_registers=[0], set_values=[250],
        )
        # Should not crash — no setpoint to update

    def test_write_non_setpoint_register_ignored(self):
        """Writing to register 1 (heating_state) is ignored gracefully."""
        thermo = make_thermostat(setpoint=20.0)
        run_action(
            thermo, fc=6, start_address=1, count=1,
            current_registers=[0], set_values=[1],
        )
        # setpoint unchanged
        assert thermo.setpoint == 20.0


# ── ModbusServer construction ─────────────────────────────────────────────────

class TestModbusServerConstruction:
    def test_no_climate_devices(self):
        from sim.devices.lighting import OnOffLight
        lamp = OnOffLight(id="l", location="s", topic_prefix="z/l")
        server = ModbusServer([lamp])
        assert server.unit_map() == {}

    def test_climate_devices_get_unit_ids(self):
        sensor = make_sensor()
        thermo = make_thermostat()
        server = ModbusServer([sensor, thermo])
        units = server.unit_map()
        assert len(units) == 2
        assert 1 in units
        assert 2 in units

    def test_mixed_devices_only_climate_units(self):
        from sim.devices.lighting import OnOffLight
        lamp = OnOffLight(id="l", location="s", topic_prefix="z/l")
        sensor = make_sensor()
        server = ModbusServer([lamp, sensor])
        units = server.unit_map()
        assert len(units) == 1
        assert list(units.values())[0] == "temp_sensor"
