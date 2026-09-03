"""Device base class — state machine contract for all simulated devices."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class CommandResult:
    success: bool
    reason: str = ""

    def __repr__(self) -> str:
        status = "OK" if self.success else "FAIL"
        return f"CommandResult({status}: {self.reason})"


class Device(ABC):
    """Base class for every simulated device.

    Each device is a deterministic state machine:
    - ``tick(elapsed_ms)`` advances time and returns True when telemetry is due.
    - ``apply_command(action, params)`` mutates state from an incoming bus command.
    - ``get_state()`` returns the current state in Zigbee2MQTT JSON format.
    """

    device_type: str = "device"
    protocol: str = "mqtt"

    def __init__(
        self,
        id: str,
        location: str,
        topic_prefix: str,
        telemetry_interval_ms: int = 5000,
    ) -> None:
        self.id = id
        self.location = location
        self.topic_prefix = topic_prefix.rstrip("/")
        self.telemetry_interval_ms = telemetry_interval_ms
        self._tick_count: int = 0
        self._elapsed_since_telemetry: int = 0

    # ------------------------------------------------------------------
    # Time

    def tick(self, elapsed_ms: int) -> bool:
        """Advance the device clock. Returns True if telemetry should be emitted now."""
        self._tick_count += 1
        self._elapsed_since_telemetry += elapsed_ms
        if self._elapsed_since_telemetry >= self.telemetry_interval_ms:
            self._elapsed_since_telemetry = 0
            return True
        return False

    def force_telemetry(self) -> None:
        """Force next tick() to emit telemetry regardless of interval."""
        self._elapsed_since_telemetry = self.telemetry_interval_ms

    # ------------------------------------------------------------------
    # Interface

    @abstractmethod
    def apply_command(self, action: str, params: dict[str, Any] | None = None) -> CommandResult:
        """Apply an incoming command from the bus. Returns result."""
        ...

    @abstractmethod
    def get_state(self) -> dict[str, Any]:
        """Current device state in Zigbee2MQTT payload format."""
        ...

    # ------------------------------------------------------------------
    # MQTT topics

    @property
    def telemetry_topic(self) -> str:
        """Topic for outbound telemetry: ``zigbee2mqtt/<id>``."""
        return self.topic_prefix

    @property
    def command_topic(self) -> str:
        """Topic for inbound commands: ``zigbee2mqtt/<id>/set``."""
        return f"{self.topic_prefix}/set"

    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id!r}, location={self.location!r})"
