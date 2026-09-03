"""Climate device state machines."""

from __future__ import annotations

import random
from typing import Any

from .base import CommandResult, Device


class TemperatureSensor(Device):
    """Temperature + humidity sensor. Read-only — drifts slightly each tick."""

    device_type = "temperature_sensor"

    def __init__(
        self,
        *,
        temperature: float = 20.0,
        humidity: float = 50.0,
        drift: float = 0.05,
        seed: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.temperature = temperature
        self.humidity = humidity
        self.drift = drift
        self._rng = random.Random(seed)

    def tick(self, elapsed_ms: int) -> bool:
        # Simulate realistic sensor drift
        self.temperature += self._rng.uniform(-self.drift, self.drift)
        self.humidity = max(0.0, min(100.0, self.humidity + self._rng.uniform(-self.drift, self.drift)))
        return super().tick(elapsed_ms)

    def apply_command(self, action: str, params: dict[str, Any] | None = None) -> CommandResult:
        return CommandResult(False, "temperature sensor is read-only")

    def get_state(self) -> dict[str, Any]:
        return {
            "temperature": round(self.temperature, 1),
            "humidity": round(self.humidity, 1),
        }


class Thermostat(Device):
    """Thermostat. Accepts: set_temperature."""

    device_type = "thermostat"

    def __init__(
        self,
        *,
        setpoint: float = 20.0,
        current_temperature: float = 18.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.setpoint = setpoint
        self.current_temperature = current_temperature
        self.heating = current_temperature < setpoint

    def apply_command(self, action: str, params: dict[str, Any] | None = None) -> CommandResult:
        a = action.lower()
        if a == "set_temperature":
            raw = (params or {}).get("temperature", self.setpoint)
            self.setpoint = float(raw)
            self.heating = self.current_temperature < self.setpoint
            return CommandResult(True, f"setpoint → {self.setpoint}°C")
        return CommandResult(False, f"unknown action '{action}'")

    def get_state(self) -> dict[str, Any]:
        return {
            "occupied_heating_setpoint": round(self.setpoint, 1),
            "local_temperature": round(self.current_temperature, 1),
            "running_state": "heat" if self.heating else "idle",
            "system_mode": "heat",
        }
