# `sim/devices/lighting.py`

> **Rôle** — Lampes simulées : on/off, variateur, RGB.

Dépôt : [jabfy-simulation](README.md) · 79 lignes · statut : **actif**

Docstring du module : *Lighting device state machines.*

## À retenir

- `OnOffLight` l.10 accepte `turn_on`, `turn_off`, `toggle`.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 10 | classe `OnOffLight` | Simple on/off light. Accepts: turn_on, turn_off, toggle. — méthodes : `__init__` 15, `apply_command` 19, `get_state` 32 |
| 36 | classe `DimmerLight` | Dimmable light. Adds: set_brightness (0–254). — méthodes : `__init__` 41, `apply_command` 45, `get_state` 57 |
| 61 | classe `RGBBulb` | RGB + colour-temperature bulb. Adds: set_color. — méthodes : `__init__` 66, `apply_command` 71, `get_state` 78 |

## Relations

- **Utilise** : [sim/devices/base.py](devices-base.md)
- **Utilisé par** : aucun import direct (point d'entrée, appelé par HTTP, CLI ou navigateur)
- **Testé par** : `tests/test_config.py`, `tests/test_dashboard.py`, `tests/test_devices.py`, `tests/test_modbus_server.py` → [tests de jabfy-simulation](tests.md)
