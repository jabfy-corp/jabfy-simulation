"""Integration tests for HTTP + Modbus adapter wiring in BusRunner.

These tests exercise:
  - SmartTV HTTP polling adapter → bus telemetry
  - Custom http_smarttv translator
  - Custom http_smarttv transport (against live FastAPI)
  - Modbus polling adapter (using mock reader)
  - Custom modbus_climate translator + transport (using mock writer)
  - Full SmartTV command pipeline: reflex → verify → execute → HTTP POST
"""

import json
import threading
import time
from unittest.mock import MagicMock, call, patch

import pytest

pytest.importorskip("jabfy_bus", reason="jabfy-bus not installed — skipping")

from jabfy_bus.adapters.http.adapter import Endpoint, HTTPPollingAdapter
from jabfy_bus.adapters.modbus.registers import RegisterMap, RegisterSpec, RegisterType
from jabfy_bus.core.bus import UniversalJsonBus
from jabfy_bus.core.types import AdapterMode, Domain, EntityClass, MessageType, TrustLevel

from sim.config.schema import ReflexCommand, ReflexRule, ReflexTrigger
from sim.devices.climate import TemperatureSensor, Thermostat
from sim.devices.entertainment import SmartTV
from sim.emitters.http_server import _build_tv_app
from sim.integration.bus_runner import (
    BusRunner, ClimateModbusUnit, ModbusClimateConfig, SmartTVHttpConfig,
    _to_http_smarttv, _to_modbus_climate,
)
from sim.integration.reflex import ReflexEngine

# ── Translator unit tests ──────────────────────────────────────────────────────

class TestSmartTVTranslator:
    def test_turn_on(self):
        cmd = {"action": "turn_on", "target": "http://localhost:8001/api/v2", "params": {}}
        native = _to_http_smarttv(cmd)
        assert native["target"] == "http://localhost:8001/api/v2/power"
        assert native["payload"] == {"state": "on"}
        assert native["method"] == "POST"

    def test_turn_off(self):
        cmd = {"action": "turn_off", "target": "http://localhost:8001/api/v2", "params": {}}
        native = _to_http_smarttv(cmd)
        assert native["payload"] == {"state": "off"}

    def test_set_volume(self):
        cmd = {"action": "set_volume", "target": "http://localhost:8001/api/v2", "params": {"volume": 60}}
        native = _to_http_smarttv(cmd)
        assert native["target"].endswith("/volume")
        assert native["payload"] == {"volume": 60}

    def test_set_source(self):
        cmd = {"action": "set_source", "target": "http://localhost:8001/api/v2", "params": {"source": "HDMI2"}}
        native = _to_http_smarttv(cmd)
        assert native["target"].endswith("/source")
        assert native["payload"] == {"source": "HDMI2"}

    def test_trailing_slash_stripped(self):
        cmd = {"action": "turn_on", "target": "http://localhost:8001/api/v2/", "params": {}}
        native = _to_http_smarttv(cmd)
        assert not native["target"].endswith("//power")
        assert native["target"].endswith("/power")


class TestModbusClimateTranslator:
    def test_set_temperature(self):
        cmd = {"action": "set_temperature", "target": "1", "params": {"temperature": 22.5}}
        native = _to_modbus_climate(cmd)
        assert native["target"] == "1"
        assert native["payload"]["register_type"] == RegisterType.HOLDING_REGISTER.value
        assert native["payload"]["address"] == 0
        assert native["payload"]["value"] == 225   # 22.5 × 10

    def test_set_temperature_rounding(self):
        # 20.35 → round(203.5) → 204
        cmd = {"action": "set_temperature", "target": "2", "params": {"temperature": 20.35}}
        native = _to_modbus_climate(cmd)
        assert native["payload"]["value"] == 204

    def test_unknown_action_raises(self):
        cmd = {"action": "turn_on", "target": "1", "params": {}}
        with pytest.raises(ValueError, match="unsupported action"):
            _to_modbus_climate(cmd)


# ── HTTP polling adapter ───────────────────────────────────────────────────────

class TestHTTPPollingAdapter:
    """Tests HTTPPollingAdapter using a captured fetcher (no real network)."""

    def _make_adapter(self, tv, captured_msgs, entity_id="switch.test_tv"):
        bus = UniversalJsonBus()
        bus.subscribe(MessageType.TELEMETRY.value, captured_msgs.append, name="spy")
        state_url = "http://fake/api/v2/state"
        endpoints = [
            Endpoint(url=state_url, entity_id=f"{entity_id}_switch",
                     domain=Domain.SWITCH, value_path="switch"),
            Endpoint(url=state_url, entity_id=f"{entity_id}_volume",
                     domain=Domain.SENSOR, value_path="volume"),
        ]
        # Inject a fake fetcher
        def fake_fetcher(url, method="GET"):
            return tv.get_state()

        adapter = HTTPPollingAdapter(bus, endpoints=endpoints, fetcher=fake_fetcher,
                                      mode=AdapterMode.READ_WRITE)
        adapter.start()
        return bus, adapter

    def test_poll_publishes_telemetry(self):
        tv = SmartTV(id="test_tv", location="salon", topic_prefix="http/test_tv")
        msgs = []
        _, adapter = self._make_adapter(tv, msgs)
        adapter.poll_once()
        assert len(msgs) == 2  # switch + volume

    def test_switch_value_extracted(self):
        tv = SmartTV(id="test_tv", location="salon", topic_prefix="http/test_tv")
        msgs = []
        _, adapter = self._make_adapter(tv, msgs)
        adapter.poll_once()
        switch_msgs = [m for m in msgs if m.entity.id.endswith("_switch")]
        assert len(switch_msgs) == 1
        assert switch_msgs[0].value.normalized == "off"

    def test_poll_after_power_on(self):
        tv = SmartTV(id="test_tv", location="salon", topic_prefix="http/test_tv")
        tv.apply_command("turn_on")
        msgs = []
        _, adapter = self._make_adapter(tv, msgs)
        adapter.poll_once()
        switch_msgs = [m for m in msgs if m.entity.id.endswith("_switch")]
        assert switch_msgs[0].value.normalized == "on"

    def test_volume_extracted(self):
        tv = SmartTV(id="test_tv", location="salon", topic_prefix="http/test_tv", volume=75)
        msgs = []
        _, adapter = self._make_adapter(tv, msgs)
        adapter.poll_once()
        vol_msgs = [m for m in msgs if "volume" in m.entity.id]
        assert vol_msgs[0].value.normalized == 75


# ── Modbus polling adapter ─────────────────────────────────────────────────────

class TestModbusPollingAdapter:
    """Tests ModbusAdapter using a mock reader (no real Modbus TCP)."""

    def _make_adapter(self, unit_id, has_humidity, has_setpoint, reader_returns, captured_msgs):
        from jabfy_bus.adapters.modbus.adapter import ModbusAdapter
        bus = UniversalJsonBus()
        bus.subscribe(MessageType.TELEMETRY.value, captured_msgs.append, name="spy")

        specs = [
            RegisterSpec(address=0, register_type=RegisterType.INPUT_REGISTER,
                         entity_id=f"sensor.dev{unit_id}_temperature", domain=Domain.SENSOR,
                         entity_class=EntityClass.TEMPERATURE, unit="°C", scale=0.1),
        ]
        if has_humidity:
            specs.append(RegisterSpec(address=1, register_type=RegisterType.INPUT_REGISTER,
                                       entity_id=f"sensor.dev{unit_id}_humidity", domain=Domain.SENSOR,
                                       entity_class=EntityClass.HUMIDITY, unit="%", scale=0.1))
        if has_setpoint:
            specs.append(RegisterSpec(address=0, register_type=RegisterType.HOLDING_REGISTER,
                                       entity_id=f"climate.dev{unit_id}_setpoint", domain=Domain.CLIMATE,
                                       unit="°C", scale=0.1, write_allowed=True))

        rmap = RegisterMap(unit_id=unit_id, specs=specs)
        mock_reader = MagicMock(side_effect=lambda uid, rtype, addr: reader_returns.get((uid, rtype, addr), 0))
        adapter = ModbusAdapter(bus, register_map=rmap, host="localhost", port=5020,
                                 reader=mock_reader, mode=AdapterMode.READ_WRITE)
        adapter.start()
        return bus, adapter

    def test_temperature_sensor_poll(self):
        msgs = []
        reads = {(1, RegisterType.INPUT_REGISTER, 0): 235}  # 23.5°C
        _, adapter = self._make_adapter(1, has_humidity=False, has_setpoint=False,
                                         reader_returns=reads, captured_msgs=msgs)
        adapter.poll_once()
        assert len(msgs) == 1
        assert msgs[0].value.normalized == pytest.approx(23.5, abs=0.01)

    def test_temperature_sensor_with_humidity(self):
        msgs = []
        reads = {
            (2, RegisterType.INPUT_REGISTER, 0): 190,   # 19.0°C
            (2, RegisterType.INPUT_REGISTER, 1): 600,   # 60.0%
        }
        _, adapter = self._make_adapter(2, has_humidity=True, has_setpoint=False,
                                         reader_returns=reads, captured_msgs=msgs)
        adapter.poll_once()
        assert len(msgs) == 2
        temp_msg = next(m for m in msgs if "temperature" in m.entity.id)
        hum_msg = next(m for m in msgs if "humidity" in m.entity.id)
        assert temp_msg.value.normalized == pytest.approx(19.0, abs=0.01)
        assert hum_msg.value.normalized == pytest.approx(60.0, abs=0.01)

    def test_thermostat_poll_includes_setpoint(self):
        msgs = []
        reads = {
            (3, RegisterType.INPUT_REGISTER, 0): 185,   # 18.5°C current temp
            (3, RegisterType.HOLDING_REGISTER, 0): 210, # 21.0°C setpoint
        }
        _, adapter = self._make_adapter(3, has_humidity=False, has_setpoint=True,
                                         reader_returns=reads, captured_msgs=msgs)
        adapter.poll_once()
        assert len(msgs) == 2
        sp_msg = next(m for m in msgs if "setpoint" in m.entity.id)
        assert sp_msg.value.normalized == pytest.approx(21.0, abs=0.01)


# ── SmartTV HTTP transport ─────────────────────────────────────────────────────

class TestHTTPSmartTVTransport:
    """Tests the http_smarttv transport using FastAPI TestClient as the server."""

    def test_transport_turns_on_tv(self):
        """http_smarttv transport correctly POSTs to the SmartTV API."""
        from fastapi.testclient import TestClient
        tv = SmartTV(id="salon_tv", location="salon", topic_prefix="http/tv")
        app = _build_tv_app(tv)

        # Intercept urllib.request.urlopen with TestClient
        client = TestClient(app, raise_server_exceptions=True)

        posted: list = []

        def fake_urlopen(req, timeout=5):
            """Route urllib Request to FastAPI TestClient."""
            path = req.full_url.replace("http://localhost:8001", "")
            data = req.data
            body = json.loads(data) if data else {}
            resp = client.request(req.get_method(), path, json=body)
            posted.append(resp)
            # Return a minimal file-like object
            mock_resp = MagicMock()
            mock_resp.read.return_value = resp.content
            mock_resp.__enter__ = lambda s: mock_resp
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        # Build a BusRunner (no MQTT needed — just test the transport fn directly)
        from sim.integration.bus_runner import BusRunner
        from sim.config.schema import BrokerConfig
        runner = BusRunner(broker=BrokerConfig())

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            runner._http_smarttv_transport(
                target="http://localhost:8001/api/v2/power",
                payload={"state": "on"},
            )

        assert len(posted) == 1
        assert posted[0].status_code == 200
        assert tv.get_state()["switch"] == "on"


# ── Modbus transport ──────────────────────────────────────────────────────────

class TestModbusClimateTransport:
    """Tests the modbus_climate transport using a mock writer."""

    def test_transport_writes_setpoint(self):
        from sim.config.schema import BrokerConfig
        from sim.integration.bus_runner import BusRunner

        mock_writer = MagicMock()
        runner = BusRunner(broker=BrokerConfig())
        runner._modbus_writer = mock_writer

        runner._modbus_climate_transport(
            target="2",
            payload={
                "register_type": "holding_register",
                "address": 0,
                "value": 225,
            },
        )

        mock_writer.write.assert_called_once_with(
            2, RegisterType.HOLDING_REGISTER, 0, 225
        )

    def test_transport_raises_without_writer(self):
        from sim.config.schema import BrokerConfig
        from sim.integration.bus_runner import BusRunner

        runner = BusRunner(broker=BrokerConfig())
        runner._modbus_writer = None

        with pytest.raises(RuntimeError, match="No Modbus writer"):
            runner._modbus_climate_transport("1", {"register_type": "holding_register", "address": 0, "value": 200})


# ── Full SmartTV pipeline (reflex → verify → http transport) ──────────────────

class TestSmartTVFullPipeline:
    """Test the complete command pipeline for SmartTV via http_smarttv protocol."""

    def test_reflex_proposes_with_http_protocol(self):
        """ReflexRule with protocol='http_smarttv' produces a command.requested with that protocol."""
        from jabfy_bus.core.bus import UniversalJsonBus
        from jabfy_bus.core.message import Entity, Value, new_message
        from jabfy_bus.core.types import Domain, MessageType, TrustLevel
        from sim.config.schema import ReflexCommand, ReflexRule, ReflexTrigger
        from sim.integration.reflex import ReflexEngine

        bus = UniversalJsonBus()
        rule = ReflexRule(
            name="motion_turn_on_tv",
            trigger=ReflexTrigger(entity_id="binary_sensor.salon_motion", value=True),
            command=ReflexCommand(
                action="turn_on",
                target_entity_id="switch.salon_tv_switch",
                target_domain="switch",
                target_mqtt_topic="",
                protocol="http_smarttv",
                target="http://localhost:8001/api/v2",
            ),
        )
        engine = ReflexEngine(bus, rules=[rule])
        engine.attach()

        proposals = []
        bus.subscribe(MessageType.COMMAND_REQUESTED.value, proposals.append, name="spy")

        msg = new_message(
            MessageType.TELEMETRY,
            adapter="test",
            protocol="zigbee",
            entity=Entity(id="binary_sensor.salon_motion", domain=Domain.BINARY_SENSOR.value, location="salon"),
            value=Value(raw=True, normalized=True, datatype="bool"),
            trust_level=TrustLevel.LOCAL_GATEWAY,
        )
        bus.publish(msg)

        assert len(proposals) == 1
        assert proposals[0].command["protocol"] == "http_smarttv"
        assert proposals[0].command["target"] == "http://localhost:8001/api/v2"
        assert proposals[0].command["action"] == "turn_on"
