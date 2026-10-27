"""Container configuration contracts; these tests do not require Docker."""

from contextlib import nullcontext
import io
import json
from pathlib import Path
import runpy
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_simulation_does_not_own_stack_orchestration():
    assert not (ROOT / "docker-compose.yml").exists()
    assert not (ROOT / "scripts/start.py").exists()


def test_container_start_waits_for_mqtt_then_executes_ui(monkeypatch):
    module = runpy.run_path(str(ROOT / "docker/start.py"))
    connect = Mock(side_effect=[OSError("starting"), nullcontext()])
    execute = Mock()
    monkeypatch.setattr(module["socket"], "create_connection", connect)
    monkeypatch.setattr(module["time"], "sleep", Mock())
    monkeypatch.setattr(module["os"], "execvp", execute)
    monkeypatch.setenv("MQTT_BROKER", "broker:1884")
    monkeypatch.setenv("JABFY_CORE_URL", "http://test-core:8000")
    module["main"]()
    assert connect.call_count == 2
    assert connect.call_args.args[0] == ("broker", 1884)
    args = execute.call_args.args
    assert args[0] == "jabfy-sim"
    assert args[1] == [
        "jabfy-sim", "ui", "--host", "0.0.0.0", "--port", "8080",
        "--broker", "broker:1884", "--home-file", "/app/data/home.json",
        "--core-url", "http://test-core:8000",
    ]


def test_container_start_exits_when_mqtt_never_starts(monkeypatch):
    module = runpy.run_path(str(ROOT / "docker/start.py"))
    monkeypatch.setattr(module["socket"], "create_connection", Mock(side_effect=OSError))
    monkeypatch.setattr(module["time"], "monotonic", Mock(side_effect=[0, 61]))
    with pytest.raises(SystemExit, match="MQTT is unavailable"):
        module["main"]()


def test_healthcheck_rejects_stack_without_guard(monkeypatch):
    module = runpy.run_path(str(ROOT / "docker/healthcheck.py"))
    state = {"status": "running", "broker": {"connected": True},
             "stats": {"bus": {"connected": True}}, "guard": {"enabled": False}}
    monkeypatch.setitem(module["main"].__globals__, "urlopen",
                        lambda *args, **kwargs: io.StringIO(json.dumps(state)))
    with pytest.raises(SystemExit) as result:
        module["main"]()
    assert result.value.code == 1


@pytest.mark.parametrize("status,emitter,bus,expected", [
    ("running", True, True, 0),
    ("error", True, True, 1),
    ("starting", True, True, 1),
    ("running", False, True, 1),
    ("running", True, False, 1),
])
def test_healthcheck_requires_a_working_simulation(monkeypatch, status, emitter, bus, expected):
    module = runpy.run_path(str(ROOT / "docker/healthcheck.py"))
    state = {"status": status, "broker": {"connected": emitter},
             "guard": {"enabled": True},
             "stats": {"bus": {"connected": bus}}}
    monkeypatch.setitem(module["main"].__globals__, "urlopen",
                        lambda *args, **kwargs: io.StringIO(json.dumps(state)))
    with pytest.raises(SystemExit) as result:
        module["main"]()
    assert result.value.code == expected


def test_device_servers_are_local_when_mqtt_is_in_another_container():
    from sim.config.schema import BrokerConfig, SimConfig
    from sim.home import default_home, to_sim_config
    from sim.devices.entertainment import SmartTV
    from sim.runner import SimRunner

    config = to_sim_config(default_home(), SimConfig(broker=BrokerConfig(host="mosquitto")))
    runner = SimRunner(config)
    assert runner.emitter.broker.host == "mosquitto"
    assert runner.modbus_server.host == "127.0.0.1"
    assert runner.http_server.host == "127.0.0.1"
    assert runner.bus_runner._modbus_config.host == "127.0.0.1"

    television = SmartTV(id="tv", location="salon", topic_prefix="zigbee2mqtt/tv")
    tv_runner = SimRunner(config, devices=[television])
    assert tv_runner.http_server.host == "127.0.0.1"
    assert tv_runner.bus_runner._http_configs[0].base_url == "http://127.0.0.1:8001/api/v2"
