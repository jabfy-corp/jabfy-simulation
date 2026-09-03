"""Tests for config loading and device building."""

import pytest
import yaml
import json
import tempfile
from pathlib import Path

from sim.config.schema import BrokerConfig, DeviceConfig, SimConfig
from sim.config.loader import build_device, build_devices, load_config
from sim.devices.lighting import DimmerLight
from sim.devices.security import MotionSensor


class TestSchemaValidation:
    def test_valid_config(self):
        config = SimConfig(
            devices=[
                DeviceConfig(
                    id="lamp",
                    type="dimmer_light",
                    location="salon",
                    topic_prefix="zigbee2mqtt/lamp",
                )
            ]
        )
        assert len(config.devices) == 1

    def test_duplicate_device_ids_rejected(self):
        with pytest.raises(ValueError, match="unique"):
            SimConfig(
                devices=[
                    DeviceConfig(id="lamp", type="on_off_light", location="a", topic_prefix="z/a"),
                    DeviceConfig(id="lamp", type="on_off_light", location="b", topic_prefix="z/b"),
                ]
            )

    def test_default_broker(self):
        config = SimConfig()
        assert config.broker.host == "localhost"
        assert config.broker.port == 1883


class TestBuildDevice:
    def test_builds_dimmer(self):
        cfg = DeviceConfig(
            id="salon_lamp",
            type="dimmer_light",
            location="salon",
            topic_prefix="zigbee2mqtt/salon_lamp",
            telemetry_interval_ms=2000,
        )
        device = build_device(cfg)
        assert isinstance(device, DimmerLight)
        assert device.id == "salon_lamp"
        assert device.location == "salon"
        assert device.telemetry_interval_ms == 2000

    def test_builds_motion_sensor(self):
        cfg = DeviceConfig(
            id="motion",
            type="motion_sensor",
            location="couloir",
            topic_prefix="zigbee2mqtt/motion",
        )
        device = build_device(cfg)
        assert isinstance(device, MotionSensor)

    def test_unknown_type_raises(self):
        cfg = DeviceConfig(
            id="x",
            type="flying_saucer",
            location="roof",
            topic_prefix="zigbee2mqtt/x",
        )
        with pytest.raises(ValueError, match="unknown device type"):
            build_device(cfg)

    def test_init_kwargs_passed(self):
        cfg = DeviceConfig(
            id="lamp",
            type="on_off_light",
            location="salon",
            topic_prefix="zigbee2mqtt/lamp",
            init={"state": True},
        )
        device = build_device(cfg)
        assert device.get_state()["state"] == "ON"


class TestLoadConfig:
    def _write_yaml(self, data: dict) -> Path:
        f = tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w")
        yaml.dump(data, f)
        f.close()
        return Path(f.name)

    def test_load_yaml(self):
        data = {
            "devices": [
                {
                    "id": "lamp",
                    "type": "on_off_light",
                    "location": "salon",
                    "topic_prefix": "zigbee2mqtt/lamp",
                }
            ]
        }
        path = self._write_yaml(data)
        config = load_config(path)
        assert len(config.devices) == 1
        assert config.devices[0].id == "lamp"

    def test_load_with_broker_override(self):
        data = {
            "broker": {"host": "192.168.1.10", "port": 1884},
            "devices": [],
        }
        path = self._write_yaml(data)
        config = load_config(path)
        assert config.broker.host == "192.168.1.10"
        assert config.broker.port == 1884

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.yaml")
