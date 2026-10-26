# `sim/devices/climate.py`

> **Rôle** — Climat simulé : capteur température/humidité, thermostat.

Dépôt : [jabfy-simulation](README.md) · 79 lignes · statut : **actif**

Docstring du module : *Climate device state machines.*

## À retenir

- `Thermostat` l.47 accepte `set_temperature`.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 11 | classe `TemperatureSensor` | Temperature + humidity sensor. Read-only — drifts slightly each tick. — méthodes : `__init__` 16, `tick` 31, `apply_command` 37, `get_state` 40 |
| 47 | classe `Thermostat` | Thermostat. Accepts: set_temperature. — méthodes : `__init__` 52, `apply_command` 64, `get_state` 73 |

## Relations

- **Utilise** : [sim/devices/base.py](devices-base.md)
- **Utilisé par** : [sim/emitters/modbus_server.py](emitters-modbus-server.md), [sim/runner.py](runner.md)
- **Testé par** : `tests/test_bus_http_modbus.py`, `tests/test_devices.py`, `tests/test_modbus_server.py` → [tests de jabfy-simulation](tests.md)
