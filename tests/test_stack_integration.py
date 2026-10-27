"""Cross-repository contracts. Install sibling jabfy-core[dev] to run these tests."""
import json
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

pytest.importorskip("app.main", reason="Install sibling jabfy-core for complete stack tests")
from app.main import create_app
from app.core.openai_client import OpenAICompatibleClient
from app.simulation.client import SimulationClient
from .test_home_api import house_api  # real devices/Bus with fake MQTT transport


def test_core_proposal_guard_execution_audit_and_refusal(house_api):
    simulated = house_api.client
    runner = house_api.runner
    command = {"device_id": "salon_lamp", "action": "set_brightness", "params": {"brightness": 87}}

    def model(request):
        body = json.loads(request.content)
        assert body["response_format"]["type"] == "json_schema"
        assert "salon_lamp" in body["messages"][0]["content"]
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "explanation": "Test", "commands": [command]
        })}}]})

    llm = OpenAICompatibleClient("http://model.test/v1", transport=httpx.MockTransport(model))
    with patch("app.main.build_llm_client", return_value=llm):
        core_app = create_app()
    core_app.state.simulation_client = SimulationClient("http://sim.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(
            200, json=simulated.get("/api/ai/context").json())))
    with TestClient(core_app) as core:
        before = len(runner.transport_calls)
        proposal = core.post("/simulation/propose", json={"model": "test", "prompt": "Eclaire le salon"})
        assert proposal.status_code == 200, proposal.text
        assert len(runner.transport_calls) == before
        response = simulated.post("/api/devices/salon_lamp/commands", json={
            "action": command["action"], "params": command["params"],
            "context_revision": proposal.json()["context_revision"],
        })
        assert response.json()["status"] == "executed", response.text
        assert runner.bus_runner.verification.decisions[-1].policy == "guard:ALLOWED"
        assert runner.bus_runner.audit.verify()
        runner.bus_runner.verification.authorizer.mode = "restricted"
        before = len(runner.transport_calls)
        denied = simulated.post("/api/devices/salon_lamp/commands", json={"action": "turn_on"})
        assert denied.json()["status"] == "rejected"
        assert len(runner.transport_calls) == before
        assert runner.bus_runner.verification.decisions[-1].policy == "guard:RESTRICTED_MODE"


def test_audit_failure_blocks_a_manual_command(house_api, monkeypatch):
    def fail(message):
        raise OSError("disk full")
    monkeypatch.setattr(house_api.runner.bus_runner.audit, "record_message", fail)
    before = len(house_api.runner.transport_calls)
    result = house_api.client.post("/api/devices/salon_lamp/commands", json={"action": "turn_on"})
    assert result.json()["status"] != "executed"
    assert len(house_api.runner.transport_calls) == before


def test_rate_limit_is_enforced_before_transport(house_api):
    import time
    guard = house_api.runner.bus_runner.verification.authorizer
    guard.counts[("simulation_dashboard", "virtual-salon_lamp")].extend([time.time()] * 60)
    before = len(house_api.runner.transport_calls)
    result = house_api.client.post("/api/devices/salon_lamp/commands", json={"action": "turn_on"})
    assert result.json()["status"] == "rejected"
    assert len(house_api.runner.transport_calls) == before
    assert house_api.runner.bus_runner.verification.decisions[-1].policy == "guard:RATE_LIMIT"


def test_rgb_and_guard_survive_house_reload(house_api):
    document = house_api.home.model_dump()
    lamp = next(device for device in document["devices"] if device["id"] == "salon_lamp")
    lamp["type"] = "rgb_bulb"
    old_audit = house_api.runner.bus_runner.audit
    response = house_api.client.put("/api/home", json=document)
    assert response.status_code == 200, response.text
    runner = house_api.app.state.dashboard.runner
    assert runner.bus_runner.audit is old_audit
    assert runner.bus_runner.verification.authorizer is not None
    result = house_api.client.post("/api/devices/salon_lamp/commands", json={
        "action": "set_color", "params": {"color": {"r": 100, "g": 50, "b": 20}},
    })
    assert result.json()["status"] == "executed", result.text
    assert runner.bus_runner.verification.decisions[-1].policy == "guard:ALLOWED"
    assert old_audit.verify()
