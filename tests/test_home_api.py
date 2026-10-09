"""House APIs exercise the real bus pipeline with only network I/O replaced."""

from __future__ import annotations

from copy import deepcopy
import json
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("jabfy_bus")

from sim.config.loader import build_devices
from sim.config.schema import SimConfig
from sim.dashboard.app import create_app
from sim.emitters.mqtt import _payload_to_action
from sim.home import HouseStore, default_home, to_sim_config
from sim.integration.bus_runner import BusRunner


class FakeHomeRunner:
    """Keep actual devices, normalization, reflexes, verification, execution and audit."""

    def __init__(self, config):
        self.config = config
        self.devices = build_devices(config)
        self.connected = False
        self.start_calls = 0
        self.shutdown_calls = 0
        self._tick_count = 0
        self.transport_calls = []
        self.emissions = []
        self.bus_runner = BusRunner(config.broker, reflex_rules=config.reflex_rules)
        self.bus_runner._client.is_connected = lambda: self.connected
        self.bus_runner.execution.register_transport("zigbee", self.transport)
        self.emitter = SimpleNamespace(
            _client=SimpleNamespace(is_connected=lambda: self.connected), emit=self.emit,
        )

    def start(self):
        self.start_calls += 1
        self.connected = True

    def shutdown(self):
        self.shutdown_calls += 1
        self.connected = False

    def emit(self, device):
        if not self.connected:
            return
        state = device.get_state()
        self.emissions.append((device.id, deepcopy(state)))
        self.bus_runner.z2m.handle_mqtt(device.telemetry_topic, json.dumps(state).encode())

    def transport(self, target, payload):
        device = next(device for device in self.devices if device.command_topic == target)
        action, params = _payload_to_action(payload)
        self.transport_calls.append((device.id, action, deepcopy(params)))
        result = device.apply_command(action, params)
        if not result.success:
            raise RuntimeError(result.reason)
        self.emit(device)

    def _tick(self, elapsed_ms):
        self._tick_count += 1
        for device in self.devices:
            if device.tick(elapsed_ms):
                self.emit(device)


def wait_state(client, predicate):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        response = client.get("/api/state")
        assert response.status_code == 200
        data = response.json()
        if predicate(data):
            return data
        time.sleep(0.01)
    pytest.fail(f"Simulation did not reach expected state: {data}")


def device_state(snapshot, device_id):
    return next(device["state"] for device in snapshot["devices"] if device["id"] == device_id)


@pytest.fixture
def house_api(tmp_path):
    home = default_home()
    config = to_sim_config(home, SimConfig(tick_interval_ms=20))
    runner = FakeHomeRunner(config)
    store = HouseStore(tmp_path / "home.json")
    store.save(home)
    app = create_app(runner, home=home, store=store, runner_factory=FakeHomeRunner)
    with TestClient(app) as client:
        # Establish the motion sensor's initial false value before manual control.
        wait_state(client, lambda state: state["status"] == "running" and state["ticks"] >= 11)
        yield SimpleNamespace(client=client, app=app, store=store, runner=runner, home=home)


def test_home_catalog_context_and_live_inventory_share_logical_ids(house_api):
    client = house_api.client
    assert client.get("/api/home").json() == house_api.home.model_dump()
    catalog = client.get("/api/catalog").json()
    assert {item["type"] for item in catalog["device_types"]} >= {
        "motion_sensor", "dimmer_light", "thermostat", "door_lock",
    }
    context = client.get("/api/ai/context").json()
    state = client.get("/api/state").json()
    expected_ids = {device.id for device in house_api.home.devices}
    assert context["simulation"] is True
    assert context["revision"] == state["home_revision"]
    assert context["home"]["id"] == house_api.home.id
    assert {device["id"] for device in context["devices"]} == expected_ids
    assert {device["id"] for device in state["devices"]} == expected_ids
    lamp = next(device for device in context["devices"] if device["id"] == "salon_lamp")
    assert lamp["room_name"] == "Salon"
    assert {action["action"] for action in lamp["actions"]} >= {"turn_on", "set_brightness"}
    assert lamp["state"]["state"] == "OFF"


@pytest.mark.parametrize("device_id, action, params, field, expected", [
    ("salon_lamp", "turn_on", {}, "state", "ON"),
    ("salon_lamp", "set_brightness", {"brightness": 87}, "brightness", 87),
    ("salon_thermostat", "set_temperature", {"temperature": 23},
     "occupied_heating_setpoint", 23),
    ("front_door", "unlock", {}, "state", "UNLOCK"),
])
def test_manual_controls_traverse_verification_execution_and_audit(
    house_api, device_id, action, params, field, expected,
):
    response = house_api.client.post(
        f"/api/devices/{device_id}/commands", json={"action": action, "params": params},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "executed", result
    wait_state(house_api.client, lambda state: device_state(state, device_id).get(field) == expected)
    bus = house_api.runner.bus_runner
    request_id = result["request_id"]
    messages = [message for message in bus.bus.history("command.*")
                if message.message_id == request_id or message.correlation_id == request_id]
    assert {message.message_type for message in messages} == {
        "command.requested", "command.approved", "command.executed",
    }
    request = next(message for message in messages if message.message_type == "command.requested")
    assert request.source.adapter == "simulation_dashboard"
    assert request.raw["device_id"] == device_id
    assert request.command["target"] == f"zigbee2mqtt/sim_maison_{device_id}"
    assert any(call[0] == device_id and call[1] == action
               for call in house_api.runner.transport_calls)
    assert bus.audit.verify()


@pytest.mark.parametrize("device_id, payload, expected_status", [
    ("salon_motion", {"action": "turn_on"}, 422),
    ("missing", {"action": "turn_on"}, 404),
    ("salon_lamp", {"action": "set_brightness", "params": {"brightness": 255}}, 422),
    ("salon_lamp", {"action": "turn_on", "target": "zigbee2mqtt/real-lamp"}, 422),
    ("salon_lamp", {"action": "turn_on", "params": {"target": "real-lamp"}}, 422),
])
def test_invalid_controls_cannot_reach_the_transport(
    house_api, device_id, payload, expected_status,
):
    before = len(house_api.runner.transport_calls)
    response = house_api.client.post(f"/api/devices/{device_id}/commands", json=payload)
    assert response.status_code == expected_status
    assert len(house_api.runner.transport_calls) == before


def test_sensor_events_use_telemetry_and_drive_the_original_reflex_pipeline(house_api):
    client = house_api.client
    response = client.post("/api/devices/salon_motion/events", json={"event": "motion"})
    assert response.status_code == 202
    wait_state(client, lambda state: device_state(state, "salon_lamp")["state"] == "ON")
    assert any(device == "salon_motion" and state["occupancy"]
               for device, state in house_api.runner.emissions)
    assert any(message.source.adapter == "reflex_engine"
               and message.command["action"] == "turn_on"
               for message in house_api.runner.bus_runner.bus.history("command.requested"))
    for event, expected in (("smoke_on", True), ("smoke_off", False)):
        response = client.post("/api/devices/smoke_detector/events", json={"event": event})
        assert response.status_code == 202
        wait_state(client, lambda state: device_state(state, "smoke_detector")["smoke"] == expected)


def test_edit_updates_disk_inventory_and_revision_and_preserves_device_state(house_api):
    client = house_api.client
    original_revision = client.get("/api/ai/context").json()["revision"]
    assert client.post("/api/devices/salon_thermostat/commands", json={
        "action": "set_temperature", "params": {"temperature": 24},
    }).json()["status"] == "executed"
    house = client.get("/api/home").json()
    house["name"] = "Maison de test"
    house["devices"] = [device for device in house["devices"] if device["id"] != "kitchen_light"]
    response = client.put("/api/home", json=house)
    assert response.status_code == 200, response.text
    assert response.json() == house
    assert json.loads(house_api.store.path.read_text()) == house
    state = client.get("/api/state").json()
    context = client.get("/api/ai/context").json()
    assert context["home"]["name"] == "Maison de test"
    assert context["revision"] != original_revision
    assert context["revision"] == state["home_revision"]
    assert "kitchen_light" not in {device["id"] for device in context["devices"]}
    assert "kitchen_light" not in {device["id"] for device in state["devices"]}
    assert device_state(state, "salon_thermostat")["occupied_heating_setpoint"] == 24
    assert house_api.runner.shutdown_calls == 1
    response = client.post("/api/devices/kitchen_light/commands", json={"action": "turn_on"})
    assert response.status_code == 404


def test_stale_context_after_edit_rejects_commands_without_transport(house_api):
    client = house_api.client
    previous_revision = client.get("/api/ai/context").json()["revision"]
    house = client.get("/api/home").json()
    house["name"] = "Nouveau nom"
    assert client.put("/api/home", json=house).status_code == 200
    runner = house_api.app.state.dashboard.runner
    before = len(runner.transport_calls)
    response = client.post("/api/devices/salon_lamp/commands", json={
        "action": "turn_on", "context_revision": previous_revision,
    })
    assert response.status_code == 409
    assert len(runner.transport_calls) == before


def test_invalid_layout_does_not_replace_disk_or_running_house(house_api):
    client = house_api.client
    before = house_api.store.path.read_bytes()
    house = client.get("/api/home").json()
    house["rooms"][1]["x"] = 1
    response = client.put("/api/home", json=house)
    assert response.status_code == 422
    assert house_api.store.path.read_bytes() == before
    assert client.get("/api/home").json() == house_api.home.model_dump()
    assert house_api.runner.shutdown_calls == 0


def test_save_failure_restores_previous_runtime_and_control(house_api, monkeypatch):
    client = house_api.client
    before = house_api.store.path.read_bytes()
    previous_revision = client.get("/api/ai/context").json()["revision"]
    house = client.get("/api/home").json()
    house["name"] = "Not saved"

    def fail_save(home):
        raise OSError("disk unavailable")

    monkeypatch.setattr(house_api.store, "save", fail_save)
    response = client.put("/api/home", json=house)
    assert response.status_code == 503
    assert "disk unavailable" in response.json()["detail"]
    assert house_api.store.path.read_bytes() == before
    assert client.get("/api/home").json() == house_api.home.model_dump()
    assert client.get("/api/ai/context").json()["revision"] == previous_revision
    assert house_api.app.state.dashboard.runner is house_api.runner
    assert house_api.runner.start_calls == 2
    response = client.post("/api/devices/front_door/commands", json={"action": "unlock"})
    assert response.status_code == 200
    assert response.json()["status"] == "executed"
    wait_state(client, lambda state: device_state(state, "front_door")["state"] == "UNLOCK")


def test_disconnected_broker_rejects_commands(house_api):
    house_api.runner.connected = False
    before = len(house_api.runner.transport_calls)
    response = house_api.client.post("/api/devices/salon_lamp/commands", json={"action": "turn_on"})
    assert response.status_code == 409
    assert len(house_api.runner.transport_calls) == before


def test_edit_preserves_manual_light_state_across_new_sensor_telemetry(house_api):
    client = house_api.client
    assert client.post("/api/devices/salon_lamp/commands", json={"action": "turn_on"}).json()[
        "status"
    ] == "executed"
    wait_state(client, lambda state: device_state(state, "salon_lamp")["state"] == "ON")
    house = client.get("/api/home").json()
    house["name"] = "Même maison"
    assert client.put("/api/home", json=house).status_code == 200
    state = wait_state(client, lambda state: state["ticks"] >= 12)
    assert device_state(state, "salon_lamp")["state"] == "ON"


def test_new_catalog_devices_are_persisted_discovered_and_controllable(house_api):
    client = house_api.client
    home = client.get("/api/home").json()
    for device_id, kind in (("rgb", "rgb_bulb"), ("alarm", "alarm_siren"), ("tv", "smart_tv")):
        home["devices"].append({
            "id": device_id, "name": device_id, "type": kind,
            "room_id": "salon", "x": 2, "z": 2,
        })
    assert client.put("/api/home", json=home).status_code == 200
    context = client.get("/api/ai/context").json()
    assert {device["id"] for device in context["devices"]} >= {"rgb", "alarm", "tv"}
    commands = [
        ("rgb", "set_color", {"color": {"r": 255, "g": 0, "b": 42}}, "color",
         {"r": 255, "g": 0, "b": 42}),
        ("alarm", "arm", {}, "state", "armed"),
        ("tv", "turn_on", {}, "switch", "on"),
    ]
    for device_id, action, params, field, expected in commands:
        result = client.post(f"/api/devices/{device_id}/commands", json={
            "action": action, "params": params,
        })
        assert result.status_code == 200
        assert result.json()["status"] == "executed", result.text
        wait_state(client, lambda state: device_state(state, device_id)[field] == expected)
    assert house_api.app.state.dashboard.runner.bus_runner.audit.verify()


def test_a_bus_policy_rejection_does_not_execute_manual_control(house_api):
    from jabfy_guard import Policy

    runner = house_api.runner
    runner.bus_runner.verification.authorizer.policies.rules.insert(0, Policy(
        id="test_explicit_deny", effect="deny", home_id=house_api.home.id,
        roles=["simulation"], devices=["salon_lamp"], actions=["turn_on"],
    ))
    before = len(runner.transport_calls)
    response = house_api.client.post(
        "/api/devices/salon_lamp/commands", json={"action": "turn_on"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert "test_explicit_deny" in response.json()["reason"]
    assert len(runner.transport_calls) == before
    assert runner.bus_runner.audit.verify()
