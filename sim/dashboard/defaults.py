"""Small built-in home, usable from an installed wheel without a config file."""

from sim.config.schema import DeviceConfig, ReflexCommand, ReflexRule, ReflexTrigger, SimConfig


def home_config() -> SimConfig:
    config = SimConfig(tick_interval_ms=200)
    for device_id, kind, room, initial in [
        ("salon_lamp", "dimmer_light", "salon", {}),
        ("kitchen_light", "on_off_light", "cuisine", {}),
        ("salon_motion", "motion_sensor", "salon", {}),
        ("front_door", "door_lock", "entree", {"locked": True}),
        ("smoke_detector", "smoke_sensor", "cuisine", {}),
        ("salon_temp", "temperature_sensor", "salon",
         {"temperature": 20.5, "humidity": 48.0, "seed": 42}),
        ("salon_thermostat", "thermostat", "salon",
         {"setpoint": 21.0, "current_temperature": 19.5}),
    ]:
        config.devices.append(DeviceConfig(
            id=device_id, type=kind, location=room,
            topic_prefix=f"zigbee2mqtt/{device_id}",
            telemetry_interval_ms=200 if kind == "motion_sensor" else 5000,
            init=initial,
        ))
    for occupied, action in [(True, "turn_on"), (False, "turn_off")]:
        config.reflex_rules.append(ReflexRule(
            name="motion_to_light" if occupied else "no_motion_off_light",
            trigger=ReflexTrigger(entity_id="binary_sensor.salon_motion_occupancy", value=occupied),
            command=ReflexCommand(
                action=action, target_entity_id="switch.salon_lamp_state",
                target_domain="switch", target_mqtt_topic="zigbee2mqtt/salon_lamp",
                target_location="salon",
            ),
        ))
    return config
