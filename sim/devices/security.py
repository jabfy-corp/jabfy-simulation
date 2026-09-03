"""Security device state machines."""

from __future__ import annotations

from typing import Any

from .base import CommandResult, Device


class MotionSensor(Device):
    """PIR motion sensor. Read-only: emits occupancy events.

    Call ``trigger_motion(duration_ms)`` to simulate a detection.
    The sensor auto-clears after the given duration.
    """

    device_type = "motion_sensor"
    telemetry_interval_ms = 100  # fast — motion changes matter quickly

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("telemetry_interval_ms", 100)
        super().__init__(**kwargs)
        self.occupancy: bool = False
        self._remaining_ms: int = 0
        self._state_changed: bool = False

    def trigger_motion(self, duration_ms: int = 5000) -> None:
        """Simulate a motion detection event lasting ``duration_ms`` milliseconds."""
        self.occupancy = True
        self._remaining_ms = duration_ms
        self._state_changed = True
        self.force_telemetry()

    def tick(self, elapsed_ms: int) -> bool:
        if self._remaining_ms > 0:
            self._remaining_ms -= elapsed_ms
            if self._remaining_ms <= 0:
                self._remaining_ms = 0
                if self.occupancy:
                    self.occupancy = False
                    self._state_changed = True
                    self.force_telemetry()
        emit = super().tick(elapsed_ms)
        if self._state_changed:
            self._state_changed = False
            return True
        return emit

    def apply_command(self, action: str, params: dict[str, Any] | None = None) -> CommandResult:
        return CommandResult(False, "motion sensor is read-only")

    def get_state(self) -> dict[str, Any]:
        return {"occupancy": self.occupancy, "battery": 100}


class DoorLock(Device):
    """Smart lock. Accepts: lock, unlock."""

    device_type = "door_lock"

    def __init__(self, *, locked: bool = True, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.locked = locked
        self.door_state = "closed"

    def apply_command(self, action: str, params: dict[str, Any] | None = None) -> CommandResult:
        a = action.lower()
        if a == "lock":
            self.locked = True
            return CommandResult(True, "locked")
        if a == "unlock":
            self.locked = False
            return CommandResult(True, "unlocked")
        return CommandResult(False, f"unknown action '{action}'")

    def get_state(self) -> dict[str, Any]:
        return {
            "state": "LOCK" if self.locked else "UNLOCK",
            "door_state": self.door_state,
        }


class SmokeSensor(Device):
    """Smoke / fire detector. Read-only.

    Call ``trigger_alarm()`` / ``clear_alarm()`` to simulate events.
    """

    device_type = "smoke_sensor"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.smoke_detected: bool = False
        self.battery: int = 100

    def trigger_alarm(self) -> None:
        self.smoke_detected = True
        self.force_telemetry()

    def clear_alarm(self) -> None:
        self.smoke_detected = False
        self.force_telemetry()

    def apply_command(self, action: str, params: dict[str, Any] | None = None) -> CommandResult:
        return CommandResult(False, "smoke sensor is read-only")

    def get_state(self) -> dict[str, Any]:
        return {"smoke": self.smoke_detected, "battery": self.battery}


class AlarmSiren(Device):
    """Alarm siren. Accepts: arm, disarm."""

    device_type = "alarm_siren"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.armed: bool = False
        self.triggered: bool = False

    def apply_command(self, action: str, params: dict[str, Any] | None = None) -> CommandResult:
        a = action.lower()
        if a == "arm":
            self.armed = True
            return CommandResult(True, "armed")
        if a == "disarm":
            self.armed = False
            self.triggered = False
            return CommandResult(True, "disarmed")
        return CommandResult(False, f"unknown action '{action}'")

    def get_state(self) -> dict[str, Any]:
        return {"state": "armed" if self.armed else "disarmed", "alarm": self.triggered}
