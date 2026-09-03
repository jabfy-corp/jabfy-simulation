"""Load a YAML config file and instantiate devices."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sim.devices import DEVICE_TYPES, Device
from sim.config.schema import DeviceConfig, SimConfig


def _read_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError("PyYAML is required: pip install pyyaml") from exc
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"config root must be a mapping, got {type(data).__name__}")
    return data


def load_config(path: str | Path) -> SimConfig:
    """Parse a YAML/JSON config file into a validated SimConfig."""
    data = _read_file(Path(path))
    return SimConfig.model_validate(data)


def build_device(cfg: DeviceConfig) -> Device:
    """Instantiate a Device from its DeviceConfig."""
    device_cls = DEVICE_TYPES.get(cfg.type)
    if device_cls is None:
        known = ", ".join(sorted(DEVICE_TYPES))
        raise ValueError(
            f"unknown device type '{cfg.type}' for device '{cfg.id}'. "
            f"Known types: {known}"
        )
    return device_cls(
        id=cfg.id,
        location=cfg.location,
        topic_prefix=cfg.topic_prefix,
        telemetry_interval_ms=cfg.telemetry_interval_ms,
        **cfg.init,
    )


def build_devices(config: SimConfig) -> list[Device]:
    """Build all devices declared in the config."""
    return [build_device(cfg) for cfg in config.devices]
