"""Validated, protocol-independent layout of a simulated house."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from sim.devices import DEVICE_TYPES

Slug = Annotated[str, Field(strict=True, pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")]
Name = Annotated[str, Field(strict=True, min_length=1, max_length=100)]
Coordinate = Annotated[float, Field(strict=True, ge=-100, le=100, allow_inf_nan=False)]
LocalCoordinate = Annotated[float, Field(strict=True, ge=0, le=30, allow_inf_nan=False)]
LIGHT_TYPES = {"on_off_light", "dimmer_light", "rgb_bulb"}


class HouseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Room(HouseModel):
    id: Slug
    name: Name
    x: Coordinate = 0
    z: Coordinate = 0
    width: float = Field(default=5, strict=True, ge=1, le=30, allow_inf_nan=False)
    depth: float = Field(default=4, strict=True, ge=1, le=30, allow_inf_nan=False)
    height: float = Field(default=2.7, strict=True, ge=2, le=6, allow_inf_nan=False)
    color: str = Field(default="#dce9e2", strict=True, pattern=r"^#[0-9a-fA-F]{6}$")

    @field_validator("name")
    @classmethod
    def nonempty_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Le nom de la pièce ne peut pas être vide.")
        return value.strip()

    @model_validator(mode="after")
    def world_bounds(self) -> Room:
        if self.x + self.width > 100 or self.z + self.depth > 100:
            raise ValueError(f"La pièce '{self.name}' dépasse les limites du plan (100 m).")
        return self


class HouseDevice(HouseModel):
    id: Slug
    name: Name
    type: str
    room_id: Slug
    x: LocalCoordinate = 1
    z: LocalCoordinate = 1

    @field_validator("type")
    @classmethod
    def known_device_type(cls, value: str) -> str:
        if value not in DEVICE_TYPES:
            raise ValueError(f"Type d’appareil inconnu : '{value}'.")
        return value

    @field_validator("name")
    @classmethod
    def nonempty_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Le nom de l’appareil ne peut pas être vide.")
        return value.strip()


class Automation(HouseModel):
    id: Slug
    motion_device_id: Slug
    target_device_id: Slug


class Home(HouseModel):
    schema_version: Literal[1] = 1
    id: Slug
    name: Name
    rooms: list[Room] = Field(default_factory=list, max_length=30)
    devices: list[HouseDevice] = Field(default_factory=list, max_length=200)
    automations: list[Automation] = Field(default_factory=list, max_length=100)

    @field_validator("schema_version", mode="before")
    @classmethod
    def integer_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("schema_version doit être l’entier 1.")
        return value

    @field_validator("name")
    @classmethod
    def nonempty_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Le nom de la maison ne peut pas être vide.")
        return value.strip()

    @model_validator(mode="after")
    def coherent_layout(self) -> Home:
        for label, objects in (
            ("pièces", self.rooms), ("appareils", self.devices), ("automatismes", self.automations),
        ):
            ids = [item.id for item in objects]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Les identifiants des {label} doivent être uniques.")
        rooms = {room.id: room for room in self.rooms}
        devices = {device.id: device for device in self.devices}
        for index, room in enumerate(self.rooms):
            for other in self.rooms[index + 1:]:
                overlap_x = min(room.x + room.width, other.x + other.width) - max(room.x, other.x)
                overlap_z = min(room.z + room.depth, other.z + other.depth) - max(room.z, other.z)
                if overlap_x > 1e-9 and overlap_z > 1e-9:
                    raise ValueError(f"Les pièces '{room.name}' et '{other.name}' se chevauchent.")
        for device in self.devices:
            room = rooms.get(device.room_id)
            if room is None:
                raise ValueError(f"Pièce inconnue '{device.room_id}' pour '{device.name}'.")
            if device.x > room.width or device.z > room.depth:
                raise ValueError(f"L’appareil '{device.name}' doit rester dans la pièce '{room.name}'.")
        pairs = set()
        for automation in self.automations:
            source = devices.get(automation.motion_device_id)
            target = devices.get(automation.target_device_id)
            if source is None or source.type != "motion_sensor":
                raise ValueError(f"L’automatisme '{automation.id}' nécessite un détecteur de mouvement.")
            if target is None or target.type not in LIGHT_TYPES:
                raise ValueError(f"L’automatisme '{automation.id}' nécessite une lampe comme cible.")
            pair = (source.id, target.id)
            if pair in pairs:
                raise ValueError("Un automatisme existe déjà entre ce détecteur et cette lampe.")
            pairs.add(pair)
        return self
