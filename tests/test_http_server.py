"""Tests for the HTTP mock server (SmartTV + NAS APIs).

Uses FastAPI's TestClient — no actual uvicorn threads needed.
"""

import pytest
from fastapi.testclient import TestClient

from sim.devices.entertainment import SmartTV
from sim.emitters.http_server import _build_tv_app, _build_nas_app, _default_nas_data


@pytest.fixture
def tv() -> SmartTV:
    return SmartTV(id="test_tv", location="salon", topic_prefix="http/test_tv", state=False)


@pytest.fixture
def tv_client(tv) -> TestClient:
    app = _build_tv_app(tv)
    return TestClient(app)


@pytest.fixture
def nas_client() -> TestClient:
    app = _build_nas_app(_default_nas_data())
    return TestClient(app)


# ── SmartTV API ───────────────────────────────────────────────────────────────

class TestSmartTVApi:
    def test_device_info(self, tv_client):
        r = tv_client.get("/api/v2/")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == "test_tv"
        assert "Samsung" in data["type"]

    def test_get_state(self, tv_client):
        r = tv_client.get("/api/v2/state")
        assert r.status_code == 200
        state = r.json()
        assert state["switch"] == "off"
        assert state["volume"] == 30

    def test_power_on(self, tv_client, tv):
        r = tv_client.post("/api/v2/power", json={"state": "on"})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert tv.get_state()["switch"] == "on"

    def test_power_off(self, tv_client, tv):
        tv.apply_command("turn_on")
        r = tv_client.post("/api/v2/power", json={"state": "off"})
        assert r.status_code == 200
        assert tv.get_state()["switch"] == "off"

    def test_power_invalid_state(self, tv_client):
        r = tv_client.post("/api/v2/power", json={"state": "standby"})
        assert r.status_code == 400

    def test_set_volume(self, tv_client, tv):
        tv.apply_command("turn_on")
        r = tv_client.post("/api/v2/volume", json={"volume": 75})
        assert r.status_code == 200
        assert r.json()["volume"] == 75

    def test_set_volume_when_off(self, tv_client):
        # TV is off — volume command should fail with 422
        r = tv_client.post("/api/v2/volume", json={"volume": 50})
        assert r.status_code == 422

    def test_set_volume_missing_field(self, tv_client):
        r = tv_client.post("/api/v2/volume", json={})
        assert r.status_code == 400

    def test_set_source(self, tv_client, tv):
        tv.apply_command("turn_on")
        r = tv_client.post("/api/v2/source", json={"source": "HDMI2"})
        assert r.status_code == 200
        assert r.json()["inputSource"] == "HDMI2"

    def test_set_invalid_source(self, tv_client, tv):
        tv.apply_command("turn_on")
        r = tv_client.post("/api/v2/source", json={"source": "VHS"})
        assert r.status_code == 422

    def test_mute(self, tv_client, tv):
        tv.apply_command("turn_on")
        r = tv_client.post("/api/v2/mute", json={"mute": True})
        assert r.status_code == 200
        assert r.json()["mute"] is True

    def test_unmute(self, tv_client, tv):
        tv.apply_command("turn_on")
        tv.apply_command("mute")
        r = tv_client.post("/api/v2/mute", json={"mute": False})
        assert r.status_code == 200
        assert r.json()["mute"] is False

    def test_state_reflects_commands(self, tv_client, tv):
        """State endpoint reflects all previous command changes."""
        tv_client.post("/api/v2/power", json={"state": "on"})
        tv_client.post("/api/v2/volume", json={"volume": 60})
        tv_client.post("/api/v2/source", json={"source": "Netflix"})

        r = tv_client.get("/api/v2/state")
        state = r.json()
        assert state["switch"] == "on"
        assert state["volume"] == 60
        assert state["inputSource"] == "Netflix"


# ── NAS API ───────────────────────────────────────────────────────────────────

class TestNasApi:
    def test_api_info(self, nas_client):
        r = nas_client.get("/webapi/entry.cgi", params={"api": "SYNO.API.Info"})
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert "SYNO.Info" in data["data"]

    def test_system_info(self, nas_client):
        r = nas_client.get("/webapi/entry.cgi", params={"api": "SYNO.Info"})
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["data"]["hostname"] == "jabfy-sim-nas"
        assert "DS923+" in data["data"]["model"]

    def test_volume_list(self, nas_client):
        r = nas_client.get("/webapi/entry.cgi", params={"api": "SYNO.Storage.Volume"})
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        volumes = data["data"]["volumes"]
        assert len(volumes) == 2
        assert volumes[0]["vol_path"] == "/volume1"
        assert int(volumes[0]["total_size"]) > 0

    def test_file_list(self, nas_client):
        r = nas_client.get("/webapi/entry.cgi", params={"api": "SYNO.FileStation.List"})
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        files = data["data"]["files"]
        assert len(files) == 2
        names = {f["name"] for f in files}
        assert "jabfy-recordings" in names

    def test_unknown_api(self, nas_client):
        r = nas_client.get("/webapi/entry.cgi", params={"api": "SYNO.Unknown.Thing"})
        assert r.status_code == 400
        assert r.json()["success"] is False
