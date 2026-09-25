"""Device capabilities and bounded command parameters shared by API clients."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NoParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BrightnessParams(NoParams):
    brightness: int = Field(strict=True, ge=0, le=254)


class TemperatureParams(NoParams):
    temperature: float = Field(strict=True, ge=5, le=35, allow_inf_nan=False)


class Color(NoParams):
    r: int = Field(strict=True, ge=0, le=255)
    g: int = Field(strict=True, ge=0, le=255)
    b: int = Field(strict=True, ge=0, le=255)


class ColorParams(NoParams):
    color: Color


_ACTIONS = {
    "turn_on": ("Allumer", NoParams),
    "turn_off": ("Éteindre", NoParams),
    "toggle": ("Basculer", NoParams),
    "set_brightness": ("Régler la luminosité", BrightnessParams),
    "set_color": ("Changer la couleur", ColorParams),
    "set_temperature": ("Régler la consigne", TemperatureParams),
    "lock": ("Verrouiller", NoParams),
    "unlock": ("Déverrouiller", NoParams),
    "arm": ("Armer", NoParams),
    "disarm": ("Désarmer", NoParams),
}
_POWER = ("turn_on", "turn_off", "toggle")
_TYPES = {
    "on_off_light": ("Lampe", "switch", _POWER, ()),
    "dimmer_light": ("Lampe à variation", "switch", (*_POWER, "set_brightness"), ()),
    "rgb_bulb": ("Ampoule RGB", "switch", (*_POWER, "set_brightness", "set_color"), ()),
    "motion_sensor": ("Détecteur de mouvement", "binary_sensor", (), ("motion",)),
    "door_lock": ("Serrure", "lock", ("lock", "unlock"), ()),
    "smoke_sensor": ("Détecteur de fumée", "binary_sensor", (), ("smoke_on", "smoke_off")),
    "alarm_siren": ("Sirène", "alarm", ("arm", "disarm"), ()),
    "temperature_sensor": ("Capteur de température", "sensor", (), ()),
    "thermostat": ("Thermostat", "climate", ("set_temperature",), ()),
    "smart_tv": ("Télévision", "switch", ("turn_on", "turn_off"), ()),
}


def device_capabilities(kind: str) -> dict[str, Any]:
    """Return a fresh catalog entry, including JSON Schema for each action."""
    if kind not in _TYPES:
        raise ValueError(f"Type d’appareil inconnu : '{kind}'.")
    label, domain, actions, events = _TYPES[kind]
    return {
        "type": kind, "label": label, "domain": domain,
        "actions": [
            {"action": action, "label": _ACTIONS[action][0],
             "params": _ACTIONS[action][1].model_json_schema()}
            for action in actions
        ],
        "sensor_events": list(events),
    }


def catalog() -> dict[str, Any]:
    return {"device_types": [device_capabilities(kind) for kind in _TYPES]}


def validate_command(kind: str, action: str, params: dict[str, Any]) -> dict[str, Any]:
    """Validate capability and parameters; authorization remains the bus's job."""
    if kind not in _TYPES:
        raise ValueError(f"Type d’appareil inconnu : '{kind}'.")
    if action not in _TYPES[kind][2]:
        raise ValueError(f"L’action '{action}' n’est pas disponible pour cet appareil.")
    return _ACTIONS[action][1].model_validate(params).model_dump()
