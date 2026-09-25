"""House geometry, persistence and safe translation to the existing simulator."""

from copy import deepcopy

import pytest

from sim.config.loader import build_devices
from sim.config.schema import SimConfig
from sim.dashboard.defaults import home_config
from sim.devices import DEVICE_TYPES
from sim.home import (
    Home, HouseStore, catalog, default_home, device_capabilities, device_wire_id,
    from_sim_config, to_sim_config, validate_command,
)


def test_default_home_builds_isolated_protocol_devices_and_paired_rules():
    home = default_home()
    base = home_config()
    original = base.model_dump()
    config = to_sim_config(home, base)
    devices = build_devices(config)
    assert len(home.rooms) == 3
    assert len(devices) == 7
    assert [device.id for device in devices] == [device.id for device in home.devices]
    assert {device.telemetry_topic for device in devices} == {
        f"zigbee2mqtt/sim_maison_{device.id}" for device in home.devices
    }
    assert config.broker.client_id_prefix == "jabfy-sim-maison"
    assert [rule.trigger.value for rule in config.reflex_rules] == [True, False]
    assert [rule.command.action for rule in config.reflex_rules] == ["turn_on", "turn_off"]
    assert all(rule.trigger.entity_id == "binary_sensor.sim_maison_salon_motion_occupancy"
               for rule in config.reflex_rules)
    assert all(rule.command.target_entity_id == "switch.sim_maison_salon_lamp_state"
               for rule in config.reflex_rules)
    assert all(rule.command.target_mqtt_topic == "zigbee2mqtt/sim_maison_salon_lamp"
               for rule in config.reflex_rules)
    assert next(device for device in devices if device.id == "salon_temp").temperature == 20.5
    assert base.model_dump() == original
    assert device_wire_id(home, "salon_lamp") == "sim_maison_salon_lamp"


def test_empty_home_has_no_devices_or_automations():
    home = Home(id="vide", name="Maison vide")
    config = to_sim_config(home, home_config())
    assert config.devices == []
    assert config.reflex_rules == []


@pytest.mark.parametrize("category, index, field, value", [
    ("rooms", 0, "x", float("nan")),
    ("rooms", 0, "depth", float("inf")),
    ("rooms", 0, "height", True),
    ("rooms", 0, "width", 31),
    ("rooms", 0, "height", 1.9),
    ("rooms", 0, "x", -101),
    ("rooms", 0, "color", "red"),
    ("rooms", 0, "name", "  "),
    ("devices", 0, "x", -0.01),
    ("devices", 0, "z", 6),
    ("devices", 0, "room_id", "missing"),
    ("devices", 0, "type", "unknown"),
    ("devices", 0, "id", "../../real-lamp"),
    ("devices", 0, "topic_prefix", "zigbee2mqtt/real-lamp"),
    ("automations", 0, "motion_device_id", "salon_temp"),
    ("automations", 0, "target_device_id", "front_door"),
])
def test_house_rejects_invalid_geometry_references_and_protocol_fields(category, index, field, value):
    data = default_home().model_dump()
    data[category][index][field] = value
    with pytest.raises(ValueError):
        Home.model_validate(data)


@pytest.mark.parametrize("category", ["rooms", "devices", "automations"])
def test_house_rejects_duplicate_ids(category):
    data = default_home().model_dump()
    data[category].append(deepcopy(data[category][0]))
    with pytest.raises(ValueError, match="uniques"):
        Home.model_validate(data)


def test_room_interiors_cannot_overlap_but_shared_walls_are_allowed():
    data = default_home().model_dump()
    Home.model_validate(data)
    data["rooms"][1]["x"] = 5.9
    with pytest.raises(ValueError, match="chevauchent"):
        Home.model_validate(data)


@pytest.mark.parametrize("version", [2, True, 1.0, "1"])
def test_schema_version_is_explicit(version):
    with pytest.raises(ValueError):
        Home(id="home", name="Home", schema_version=version)


def test_house_size_is_bounded():
    data = default_home().model_dump()
    data["devices"] = data["devices"] * 29
    with pytest.raises(ValueError, match="200"):
        Home.model_validate(data)


def test_store_creates_roundtrips_and_revalidates_nested_mutations(tmp_path):
    path = tmp_path / "nested" / "maison.json"
    store = HouseStore(path)
    initial = default_home()
    assert store.load(initial) == initial
    assert "Porte d’entrée" in path.read_text(encoding="utf-8")
    saved = path.read_bytes()
    initial.devices[0].room_id = "missing"
    with pytest.raises(ValueError):
        store.save(initial)
    assert path.read_bytes() == saved
    assert store.load(default_home()) == default_home()


def test_store_keeps_previous_file_and_removes_temp_on_replace_failure(tmp_path, monkeypatch):
    path = tmp_path / "maison.json"
    store = HouseStore(path)
    store.save(default_home())
    before = path.read_bytes()

    def fail_replace(*args):
        raise OSError("disk unavailable")

    monkeypatch.setattr("sim.home.store.os.replace", fail_replace)
    with pytest.raises(OSError, match="disk unavailable"):
        store.save(Home(id="another", name="Another house"))
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_invalid_saved_house_is_not_overwritten(tmp_path):
    path = tmp_path / "maison.json"
    path.write_text('{"schema_version": 99}', encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Maison invalide"):
        HouseStore(path).load(default_home())
    assert path.read_bytes() == before


def test_import_keeps_paired_rules_and_does_not_invent_shutoff_for_one_sided_rule():
    config = home_config()
    imported = from_sim_config(config)
    assert len(imported.rooms) == 3
    assert len(imported.devices) == 7
    assert len(imported.automations) == 1
    assert imported.automations[0].target_device_id == "salon_lamp"
    config.reflex_rules = config.reflex_rules[:1]
    assert from_sim_config(config).automations == []


def test_import_recognizes_namespaced_topics_without_accepting_uncertain_routes():
    config = to_sim_config(default_home(), SimConfig())
    assert len(from_sim_config(config).automations) == 1
    config.reflex_rules[0].command.target = "zigbee2mqtt/unrelated"
    assert from_sim_config(config).automations == []


def test_catalog_matches_all_device_types_and_returns_independent_values():
    data = catalog()
    assert {item["type"] for item in data["device_types"]} == set(DEVICE_TYPES)
    assert device_capabilities("motion_sensor")["sensor_events"] == ["motion"]
    assert device_capabilities("smoke_sensor")["sensor_events"] == ["smoke_on", "smoke_off"]
    assert device_capabilities("door_lock")["domain"] == "lock"
    data["device_types"].clear()
    assert len(catalog()["device_types"]) == len(DEVICE_TYPES)


@pytest.mark.parametrize("kind, action, params", [
    ("on_off_light", "set_brightness", {"brightness": 30}),
    ("motion_sensor", "turn_on", {}),
    ("on_off_light", "turn_on", {"target": "real-device"}),
    ("dimmer_light", "set_brightness", {"brightness": True}),
    ("dimmer_light", "set_brightness", {"brightness": 255}),
    ("dimmer_light", "set_brightness", {"brightness": "30"}),
    ("thermostat", "set_temperature", {"temperature": float("nan")}),
    ("thermostat", "set_temperature", {"temperature": 36}),
    ("thermostat", "set_temperature", {"temperature": True}),
    ("rgb_bulb", "set_color", {"color": {"r": -1, "g": 0, "b": 0}}),
    ("rgb_bulb", "set_color", {"color": {"r": 1, "g": 2, "b": 3, "a": 4}}),
    ("unknown", "turn_on", {}),
])
def test_commands_reject_unsupported_actions_and_invalid_parameters(kind, action, params):
    with pytest.raises(ValueError):
        validate_command(kind, action, params)


def test_commands_normalize_valid_payloads_without_authorizing_them():
    assert validate_command("door_lock", "unlock", {}) == {}
    assert validate_command("smart_tv", "turn_on", {}) == {}
    assert validate_command("thermostat", "set_temperature", {"temperature": 21}) == {
        "temperature": 21.0,
    }
    assert validate_command("dimmer_light", "set_brightness", {"brightness": 254}) == {
        "brightness": 254,
    }
    color = {"color": {"r": 255, "g": 128, "b": 0}}
    assert validate_command("rgb_bulb", "set_color", color) == color
