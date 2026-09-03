"""Lighting device state machines."""

from __future__ import annotations

from typing import Any

from .base import CommandResult, Device


class OnOffLight(Device):
    """Simple on/off light. Accepts: turn_on, turn_off, toggle."""

    device_type = "on_off_light"

    def __init__(self, *, state: bool = False, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.state = state  # False = OFF, True = ON

    def apply_command(self, action: str, params: dict[str, Any] | None = None) -> CommandResult:
        a = action.lower()
        if a == "turn_on":
            self.state = True
            return CommandResult(True, "turned on")
        if a == "turn_off":
            self.state = False
            return CommandResult(True, "turned off")
        if a == "toggle":
            self.state = not self.state
            return CommandResult(True, f"toggled → {'ON' if self.state else 'OFF'}")
        return CommandResult(False, f"unknown action '{action}'")

    def get_state(self) -> dict[str, Any]:
        return {"state": "ON" if self.state else "OFF"}


class DimmerLight(OnOffLight):
    """Dimmable light. Adds: set_brightness (0–254)."""

    device_type = "dimmer_light"

    def __init__(self, *, brightness: int = 0, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.brightness = max(0, min(254, brightness))

    def apply_command(self, action: str, params: dict[str, Any] | None = None) -> CommandResult:
        a = action.lower()
        if a == "set_brightness":
            raw = (params or {}).get("brightness", 254)
            self.brightness = max(0, min(254, int(raw)))
            self.state = self.brightness > 0
            return CommandResult(True, f"brightness → {self.brightness}")
        result = super().apply_command(action, params)
        if result.success and self.state and self.brightness == 0:
            self.brightness = 254  # default brightness on turn_on
        return result

    def get_state(self) -> dict[str, Any]:
        return {"state": "ON" if self.state else "OFF", "brightness": self.brightness}


class RGBBulb(DimmerLight):
    """RGB + colour-temperature bulb. Adds: set_color."""

    device_type = "rgb_bulb"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.color: dict[str, int] = {"r": 255, "g": 255, "b": 255}
        self.color_temp: int = 250  # mired (warm white)

    def apply_command(self, action: str, params: dict[str, Any] | None = None) -> CommandResult:
        a = action.lower()
        if a == "set_color":
            self.color = dict((params or {}).get("color", self.color))
            return CommandResult(True, f"color → {self.color}")
        return super().apply_command(action, params)

    def get_state(self) -> dict[str, Any]:
        return {**super().get_state(), "color": self.color, "color_temp": self.color_temp}
