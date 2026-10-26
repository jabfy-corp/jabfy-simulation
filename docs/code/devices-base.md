# `sim/devices/base.py`

> **Rôle** — `Device` : classe de base des machines à états d'appareils simulés.

Dépôt : [jabfy-simulation](README.md) · 91 lignes · statut : **actif**

Docstring du module : *Device base class — state machine contract for all simulated devices.*

## À retenir

- `Device` l.20.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 11 | classe `CommandResult` | méthodes : `__repr__` 15 |
| 20 | classe `Device` | Base class for every simulated device. — méthodes : `__init__` 32, `tick` 49, `force_telemetry` 58, `apply_command` 66, `get_state` 71, `telemetry_topic` 79, `command_topic` 84, `__repr__` 90 |

## Relations

- **Utilise** : aucun fichier JABFY documenté (bibliothèques externes seulement)
- **Utilisé par** : [sim/devices/climate.py](devices-climate.md), [sim/devices/entertainment.py](devices-entertainment.md), [sim/devices/lighting.py](devices-lighting.md), [sim/devices/security.py](devices-security.md), [sim/emitters/modbus_server.py](emitters-modbus-server.md), [sim/emitters/mqtt.py](emitters-mqtt.md), [sim/runner.py](runner.md)
