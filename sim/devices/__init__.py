"""Simulated device state machines."""

from .base import CommandResult, Device
from .climate import TemperatureSensor, Thermostat
from .entertainment import SmartTV
from .lighting import DimmerLight, OnOffLight, RGBBulb
from .security import AlarmSiren, DoorLock, MotionSensor, SmokeSensor

DEVICE_TYPES: dict[str, type[Device]] = {
    "on_off_light": OnOffLight,
    "dimmer_light": DimmerLight,
    "rgb_bulb": RGBBulb,
    "motion_sensor": MotionSensor,
    "door_lock": DoorLock,
    "smoke_sensor": SmokeSensor,
    "alarm_siren": AlarmSiren,
    "temperature_sensor": TemperatureSensor,
    "thermostat": Thermostat,
    "smart_tv": SmartTV,
}

__all__ = [
    "Device",
    "CommandResult",
    "OnOffLight",
    "DimmerLight",
    "RGBBulb",
    "MotionSensor",
    "DoorLock",
    "SmokeSensor",
    "AlarmSiren",
    "TemperatureSensor",
    "Thermostat",
    "SmartTV",
    "DEVICE_TYPES",
]
