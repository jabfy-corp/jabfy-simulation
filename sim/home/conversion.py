"""Translate the visual house into the simulator's existing MQTT configuration."""

from __future__ import annotations

from copy import deepcopy
import math
import re
import unicodedata

from sim.config.schema import DeviceConfig, ReflexCommand, ReflexRule, ReflexTrigger, SimConfig
from sim.home.models import Automation, Home, HouseDevice, LIGHT_TYPES, Room

_COLORS = ("#dce9e2", "#f2e4d2", "#e1e6ef", "#ece0ed", "#e5e9d3")
_INITIAL = {
    "door_lock": {"locked": True},
    "temperature_sensor": {"temperature": 20.5, "humidity": 48.0, "seed": 42},
    "thermostat": {"setpoint": 21.0, "current_temperature": 19.5},
}
_DEVICE_NAMES = {
    "salon_lamp": "Lampe du salon", "kitchen_light": "Éclairage cuisine",
    "salon_motion": "Mouvement salon", "front_door": "Porte d’entrée",
    "smoke_detector": "Détecteur de fumée", "salon_temp": "Température salon",
    "salon_thermostat": "Thermostat salon",
}


def default_home() -> Home:
    """A small furnished layout matching the original seven-device dashboard."""
    return Home(
        id="maison", name="Ma maison",
        rooms=[
            Room(id="salon", name="Salon", x=0, z=0, width=6, depth=5, color=_COLORS[0]),
            Room(id="cuisine", name="Cuisine", x=6, z=0, width=4, depth=5, color=_COLORS[1]),
            Room(id="entree", name="Entrée", x=0, z=5, width=10, depth=2, color=_COLORS[2]),
        ],
        devices=[
            HouseDevice(id=device_id, name=_DEVICE_NAMES[device_id], type=kind,
                        room_id=room, x=x, z=z)
            for device_id, kind, room, x, z in [
                ("salon_lamp", "dimmer_light", "salon", 3, 2.5),
                ("kitchen_light", "on_off_light", "cuisine", 2, 2),
                ("salon_motion", "motion_sensor", "salon", 1, 4),
                ("front_door", "door_lock", "entree", 5, 1),
                ("smoke_detector", "smoke_sensor", "cuisine", 3, 4),
                ("salon_temp", "temperature_sensor", "salon", 1, 1),
                ("salon_thermostat", "thermostat", "salon", 5, 1),
            ]
        ],
        automations=[Automation(id="salon_presence", motion_device_id="salon_motion",
                                target_device_id="salon_lamp")],
    )


def device_wire_id(home: Home, device_id: str) -> str:
    """Stable namespace separating this home's simulated endpoints from legacy topics."""
    return f"sim_{home.id}_{device_id}"


def to_sim_config(home: Home, base_config: SimConfig) -> SimConfig:
    """Generate device topics and reflex rules on the server, retaining runtime settings."""
    home = Home.model_validate(home.model_dump())
    config = base_config.model_copy(deep=True)
    config.broker.client_id_prefix = f"jabfy-sim-{home.id}"
    original = {device.id: device for device in base_config.devices}
    config.devices = []
    for device in home.devices:
        previous = original.get(device.id)
        initial = _INITIAL.get(device.type, {})
        if previous is not None and previous.type == device.type:
            initial = previous.init
        config.devices.append(DeviceConfig(
            id=device.id, type=device.type, location=device.room_id,
            topic_prefix=f"zigbee2mqtt/{device_wire_id(home, device.id)}",
            telemetry_interval_ms=200 if device.type == "motion_sensor" else 5000,
            init=deepcopy(initial),
        ))
    config.reflex_rules = []
    devices = {device.id: device for device in home.devices}
    for automation in home.automations:
        target = devices[automation.target_device_id]
        source_wire = device_wire_id(home, automation.motion_device_id)
        target_wire = device_wire_id(home, target.id)
        for occupied, action in ((True, "turn_on"), (False, "turn_off")):
            config.reflex_rules.append(ReflexRule(
                name=f"{automation.id}_{'on' if occupied else 'off'}",
                trigger=ReflexTrigger(
                    entity_id=f"binary_sensor.{source_wire}_occupancy",
                    value=occupied,
                ),
                command=ReflexCommand(
                    action=action, target_entity_id=f"switch.{target_wire}_state",
                    target_domain="switch", target_location=target.room_id,
                    target_mqtt_topic=f"zigbee2mqtt/{target_wire}",
                ),
            ))
    return config


def _room_slug(name: str, used: set[str]) -> str:
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    stem = re.sub(r"[^a-z0-9_-]+", "_", plain).strip("_-")[:55] or "piece"
    candidate = stem
    suffix = 2
    while candidate in used:
        candidate = f"{stem}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def from_sim_config(config: SimConfig) -> Home:
    """Import devices and only exact, paired motion-to-light rules.

    Other trigger values, transport routes or one-sided rules are not represented
    as two-way automations: doing so would invent behavior absent from the source.
    """
    rooms = []
    devices = []
    used: set[str] = set()
    locations = list(dict.fromkeys(device.location for device in config.devices))
    for index, location in enumerate(locations):
        room_id = _room_slug(location, used)
        room = Room(id=room_id, name=location or "Pièce", x=(index % 5) * 8,
                    z=(index // 5) * 7, width=7, depth=6, color=_COLORS[index % len(_COLORS)])
        rooms.append(room)
        members = [device for device in config.devices if device.location == location]
        columns = max(1, math.ceil(math.sqrt(len(members))))
        rows = math.ceil(len(members) / columns)
        for ordinal, device in enumerate(members):
            devices.append(HouseDevice(
                id=device.id, name=_DEVICE_NAMES.get(device.id, device.id.replace("_", " ")),
                type=device.type, room_id=room_id,
                x=(ordinal % columns + 1) * room.width / (columns + 1),
                z=(ordinal // columns + 1) * room.depth / (rows + 1),
            ))
    source_ids = {f"binary_sensor.{device.topic_prefix.rsplit('/', 1)[-1]}_occupancy": device
                  for device in config.devices if device.type == "motion_sensor"}
    target_ids = {f"switch.{device.topic_prefix.rsplit('/', 1)[-1]}_state": device
                  for device in config.devices if device.type in LIGHT_TYPES}
    pairs: dict[tuple[str, str], set[bool]] = {}
    for rule in config.reflex_rules:
        source = source_ids.get(rule.trigger.entity_id)
        target = target_ids.get(rule.command.target_entity_id)
        if source is None or target is None or type(rule.trigger.value) is not bool:
            continue
        occupied = rule.trigger.value
        command = rule.command
        if (command.action != ("turn_on" if occupied else "turn_off")
                or command.protocol != "zigbee" or command.params
                or command.target_domain != "switch"
                or (command.target or command.target_mqtt_topic) != target.topic_prefix
                or rule.trigger.location not in (None, source.location)
                or command.target_location not in (None, target.location)):
            continue
        pairs.setdefault((source.id, target.id), set()).add(occupied)
    automations = [
        Automation(id=f"presence_{index + 1}", motion_device_id=source, target_device_id=target)
        for index, ((source, target), values) in enumerate(pairs.items()) if values == {True, False}
    ]
    return Home(id="maison", name="Ma maison", rooms=rooms, devices=devices,
                automations=automations)
