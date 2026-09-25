"""Entertainment device state machines.

SmartTV — models a Samsung-style smart TV:
  - Power on/off
  - Volume 0–100 (muted flag)
  - Source selection (HDMI1, HDMI2, Netflix, TV)
  - App launch
"""

from __future__ import annotations

from typing import Any

from sim.devices.base import CommandResult, Device

# Valid HDMI/source names
VALID_SOURCES = {"HDMI1", "HDMI2", "HDMI3", "Netflix", "YouTube", "TV", "CABLE"}


class SmartTV(Device):
    """Samsung-style Smart TV state machine.

    State dict keys (mirrors Samsung SmartThings schema):
      switch         — "on" | "off"
      volume         — int 0–100
      mute           — bool
      inputSource    — str (see VALID_SOURCES)
      app            — str | None (currently active app)
    """

    device_type = "smart_tv"

    def __init__(
        self,
        id: str,
        location: str,
        topic_prefix: str,
        telemetry_interval_ms: int = 10_000,
        state: bool = False,
        volume: int = 30,
        muted: bool = False,
        source: str = "HDMI1",
    ) -> None:
        super().__init__(id, location, topic_prefix, telemetry_interval_ms)
        self._on: bool = state
        self._volume: int = max(0, min(100, volume))
        self._muted: bool = muted
        self._source: str = source if source in VALID_SOURCES else "HDMI1"
        self._app: str | None = None

    # ── Device API ────────────────────────────────────────────────────────────

    def apply_command(self, action: str, params: dict | None = None) -> CommandResult:
        p = params or {}
        match action.lower():
            case "turn_on":
                self._on = True
                return CommandResult(True, "TV turned on")

            case "turn_off":
                self._on = False
                self._app = None
                return CommandResult(True, "TV turned off")

            case "toggle":
                self._on = not self._on
                if not self._on:
                    self._app = None
                return CommandResult(True, f"TV toggled {'on' if self._on else 'off'}")

            case "set_volume":
                if not self._on:
                    return CommandResult(False, "TV is off")
                vol = p.get("volume")
                if not isinstance(vol, int | float):
                    return CommandResult(False, "volume parameter required (int 0-100)")
                self._volume = max(0, min(100, int(vol)))
                self._muted = self._volume == 0
                return CommandResult(True, f"Volume set to {self._volume}")

            case "volume_up":
                if not self._on:
                    return CommandResult(False, "TV is off")
                step = int(p.get("step", 5))
                self._volume = min(100, self._volume + step)
                self._muted = False
                return CommandResult(True, f"Volume up to {self._volume}")

            case "volume_down":
                if not self._on:
                    return CommandResult(False, "TV is off")
                step = int(p.get("step", 5))
                self._volume = max(0, self._volume - step)
                self._muted = self._volume == 0
                return CommandResult(True, f"Volume down to {self._volume}")

            case "mute":
                if not self._on:
                    return CommandResult(False, "TV is off")
                self._muted = True
                return CommandResult(True, "TV muted")

            case "unmute":
                if not self._on:
                    return CommandResult(False, "TV is off")
                self._muted = False
                return CommandResult(True, "TV unmuted")

            case "set_source" | "select_source":
                if not self._on:
                    return CommandResult(False, "TV is off")
                src = p.get("source", "")
                if src not in VALID_SOURCES:
                    return CommandResult(
                        False, f"Unknown source '{src}'. Valid: {sorted(VALID_SOURCES)}"
                    )
                self._source = src
                self._app = None
                return CommandResult(True, f"Source set to {src}")

            case "launch_app":
                if not self._on:
                    return CommandResult(False, "TV is off")
                app = p.get("app", "")
                if not app:
                    return CommandResult(False, "app parameter required")
                self._app = str(app)
                self._source = "Netflix" if "netflix" in app.lower() else "YouTube" if "youtube" in app.lower() else self._source
                return CommandResult(True, f"Launched app: {self._app}")

            case _:
                return CommandResult(False, f"Unknown action: {action!r}")

    def get_state(self) -> dict[str, Any]:
        return {
            "switch": "on" if self._on else "off",
            "volume": self._volume,
            "mute": self._muted,
            "inputSource": self._source,
            "app": self._app,
        }
