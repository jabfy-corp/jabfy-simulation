"""Dashboard behavior without a network broker or a running web server."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from sim.cli import build_parser
from sim.config.schema import SimConfig
from sim.dashboard.app import create_app
from sim.devices.lighting import DimmerLight
from sim.devices.security import MotionSensor


class FakeRunner:
    """Run actual device clocks while replacing only network components."""

    def __init__(self, *, failure: str | None = None) -> None:
        self.config = SimConfig(tick_interval_ms=20)
        self.devices = [
            MotionSensor(id="motion", location="salon", topic_prefix="zigbee2mqtt/motion"),
            DimmerLight(id="lamp", location="salon", topic_prefix="zigbee2mqtt/lamp"),
        ]
        self.published: list[tuple[str, dict]] = []
        self.emitter = SimpleNamespace(
            is_connected=True,
            _client=SimpleNamespace(is_connected=lambda: True),
            emit=Mock(side_effect=lambda device: self.published.append(
                (device.id, device.get_state()),
            )),
        )
        self.bus_runner = None
        self._tick_count = 0
        self._running = False
        self.failure = failure
        self.start_calls = 0
        self.shutdown_calls = 0

    def start(self) -> None:
        self.start_calls += 1
        if self.failure == "start":
            raise ConnectionRefusedError("Cannot connect to MQTT broker at localhost:1883")

    def _tick(self, elapsed_ms: int) -> None:
        if self.failure == "tick":
            raise RuntimeError("device clock failed")
        self._tick_count += 1
        for device in self.devices:
            device.tick(elapsed_ms)

    def stop(self) -> None:
        self._running = False

    def shutdown(self) -> None:
        self.shutdown_calls += 1

    def stats(self) -> dict:
        result = {"ticks": self._tick_count, "devices": len(self.devices)}
        if self.bus_runner:
            result["bus"] = self.bus_runner.stats()
        return result


def wait_for_state(client: TestClient, predicate) -> dict:
    """Wait on observable progress, never on an assumed worker scheduling delay."""
    deadline = time.monotonic() + 3
    while True:
        response = client.get("/api/state")
        assert response.status_code == 200
        state = response.json()
        if predicate(state):
            return state
        if time.monotonic() >= deadline:
            pytest.fail(f"Dashboard did not reach expected state: {state}")
        time.sleep(0.01)


@pytest.fixture
def runner() -> FakeRunner:
    return FakeRunner()


@pytest.fixture
def client(runner):
    with TestClient(create_app(runner)) as client:
        wait_for_state(client, lambda state: state["status"] == "running")
        yield client


def test_snapshot_tracks_real_device_state_and_worker_lifecycle(runner):
    app = create_app(runner)
    with TestClient(app) as client:
        initial = wait_for_state(client, lambda state: state["ticks"] > 0)
        assert initial["status"] == "running"
        assert initial["error"] is None
        assert initial["pipeline"] is False
        assert initial["broker"] == {"host": "localhost", "port": 1883, "connected": True}
        assert initial["rules"] == []
        lamp = next(device for device in initial["devices"] if device["id"] == "lamp")
        assert lamp["type"] == "dimmer_light"
        assert lamp["location"] == "salon"
        assert lamp["protocol"] == "mqtt"
        assert lamp["state"]["state"] == "OFF"

        runner.devices[1].apply_command("set_brightness", {"brightness": 128})
        latest = wait_for_state(client, lambda state: state["ticks"] > initial["ticks"])
        lamp = next(device for device in latest["devices"] if device["id"] == "lamp")
        assert lamp["state"] == {"state": "ON", "brightness": 128}
        assert latest["stats"]["devices"] == 2

    assert runner.start_calls == 1
    assert runner.shutdown_calls == 1
    assert TestClient(app).get("/api/state").json()["status"] == "stopped"


def test_motion_input_triggers_sensor_without_commanding_lamp(client, runner):
    lamp = runner.devices[1]
    lamp.apply_command = Mock(wraps=lamp.apply_command)

    response = client.post("/api/devices/motion/motion", json={"duration_ms": 5000})

    assert response.status_code == 202
    snapshot = wait_for_state(
        client,
        lambda state: any(
            device["id"] == "motion" and device["state"]["occupancy"]
            for device in state["devices"]
        ),
    )
    assert next(device for device in snapshot["devices"] if device["id"] == "lamp")[
        "state"
    ]["state"] == "OFF"
    lamp.apply_command.assert_not_called()
    assert ("motion", {"occupancy": True, "battery": 100}) in runner.published


def test_short_motion_is_emitted_before_its_duration_expires(runner):
    runner.config.tick_interval_ms = 200
    with TestClient(create_app(runner)) as client:
        initial = wait_for_state(client, lambda state: state["ticks"] > 0)
        response = client.post("/api/devices/motion/motion", json={"duration_ms": 200})
        assert response.status_code == 202
        wait_for_state(client, lambda state: state["ticks"] > initial["ticks"])
        assert ("motion", {"occupancy": True, "battery": 100}) in runner.published
        assert runner.devices[0].get_state()["occupancy"] is False


@pytest.mark.parametrize("duration", [199, 60001, -1, True, 500.5, "5000", None])
def test_motion_rejects_invalid_duration(client, runner, duration):
    response = client.post("/api/devices/motion/motion", json={"duration_ms": duration})
    assert response.status_code == 422
    assert runner.devices[0].get_state()["occupancy"] is False


@pytest.mark.parametrize("device_id, expected", [("missing", 404), ("lamp", 400)])
def test_motion_requires_an_existing_motion_sensor(client, device_id, expected):
    response = client.post(f"/api/devices/{device_id}/motion", json={"duration_ms": 5000})
    assert response.status_code == expected


def test_motion_rejects_cross_origin_requests_but_accepts_same_origin(client, runner):
    response = client.post(
        "/api/devices/motion/motion",
        json={"duration_ms": 5000},
        headers={"Origin": "https://another-site.example"},
    )
    assert response.status_code == 403
    assert runner.devices[0].get_state()["occupancy"] is False
    response = client.post(
        "/api/devices/motion/motion",
        json={"duration_ms": 5000},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 202


def test_motion_requires_json(client, runner):
    response = client.post("/api/devices/motion/motion", data={"duration_ms": "5000"})
    assert response.status_code in (415, 422)
    assert runner.devices[0].get_state()["occupancy"] is False


def test_motion_rejected_when_simulation_is_not_running(runner):
    client = TestClient(create_app(runner))
    response = client.post("/api/devices/motion/motion", json={"duration_ms": 5000})
    assert response.status_code == 409
    assert runner.devices[0].get_state()["occupancy"] is False


@pytest.mark.parametrize("failure, error", [("start", "MQTT broker"), ("tick", "device clock")])
def test_worker_failure_stays_visible_and_cleans_up(failure, error):
    runner = FakeRunner(failure=failure)
    with TestClient(create_app(runner)) as client:
        state = wait_for_state(client, lambda state: state["status"] == "error")
        assert error in state["error"]
        assert len(state["devices"]) == 2
        response = client.post("/api/devices/motion/motion", json={"duration_ms": 5000})
        assert response.status_code == 409
    assert runner.shutdown_calls == 1


def test_bus_journal_is_bounded_ordered_and_unsubscribes_on_shutdown(runner):
    pytest.importorskip("jabfy_bus")
    from jabfy_bus.core.bus import UniversalJsonBus
    from jabfy_bus.core.message import Entity, new_message

    bus = UniversalJsonBus()
    runner.bus_runner = SimpleNamespace(
        bus=bus,
        _client=SimpleNamespace(is_connected=lambda: True),
        reflex=SimpleNamespace(proposals=0),
        verification=SimpleNamespace(decisions=[]),
        execution=SimpleNamespace(executed=0, failed=0),
    )
    messages = []
    origin = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for index in range(100):
        message = new_message(
            "command.requested",
            adapter="test",
            protocol="zigbee",
            entity=Entity(id="switch.lamp_state", domain="switch"),
            command={"action": "turn_on", "target": "zigbee2mqtt/lamp"},
        )
        message.timestamp = (origin + timedelta(seconds=index)).isoformat()
        messages.append(message)
    # Nested bus handlers can deliver commands out of timestamp order.
    messages[-2], messages[-1] = messages[-1], messages[-2]

    with TestClient(create_app(runner)) as client:
        wait_for_state(client, lambda state: state["status"] == "running")
        for message in messages:
            assert bus.publish(message) == 1
        state = client.get("/api/state").json()
        assert state["pipeline"] is True
        events = state["events"]
        assert len(events) == 80
        expected = sorted(messages[-80:], key=lambda message: message.timestamp, reverse=True)
        assert [event["id"] for event in events] == [message.message_id for message in expected]
        assert events[0]["entity"] == "switch.lamp_state"
        assert events[0]["action"] == "turn_on"

        failure = new_message(
            "command.executed",
            adapter="test",
            protocol="zigbee",
            command={"action": "turn_on"},
            raw={"success": False, "error": "Lamp unavailable"},
        )
        failure.timestamp = (origin + timedelta(seconds=100)).isoformat()
        bus.publish(failure)
        event = client.get("/api/state").json()["events"][0]
        assert event["type"] == "command.failed"
        assert event["reason"] == "Lamp unavailable"

    assert bus.publish(new_message(
        "command.requested", adapter="test", protocol="zigbee", command={"action": "turn_on"},
    )) == 0


def test_dashboard_serves_its_local_assets(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    for path, content_type in [("/static/app.css", "text/css"), ("/static/app.js", "javascript")]:
        assert path in response.text
        asset = client.get(path)
        assert asset.status_code == 200
        assert content_type in asset.headers["content-type"]
        assert asset.text.strip()


def test_ui_parser_defaults_and_overrides():
    parser = build_parser()
    defaults = parser.parse_args(["ui"])
    assert defaults.host == "127.0.0.1"
    assert defaults.port == 8080
    assert defaults.config is None

    args = parser.parse_args([
        "ui", "--config", "house.yaml", "--broker", "localhost:1884",
        "--host", "0.0.0.0", "--port", "8082",
    ])
    assert args.config == "house.yaml"
    assert args.broker == "localhost:1884"
    assert args.host == "0.0.0.0"
    assert args.port == 8082
