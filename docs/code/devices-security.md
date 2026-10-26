# `sim/devices/security.py`

> **Rôle** — Sécurité simulée : capteur de mouvement, serrure, détecteur de fumée, sirène.

Dépôt : [jabfy-simulation](README.md) · 133 lignes · statut : **actif**

Docstring du module : *Security device state machines.*

## À retenir

- `MotionSensor`, `DoorLock`, `SmokeSensor`, `AlarmSiren`.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 10 | classe `MotionSensor` | PIR motion sensor. Read-only: emits occupancy events. — méthodes : `__init__` 20, `trigger_motion` 27, `tick` 34, `apply_command` 49, `get_state` 52 |
| 56 | classe `DoorLock` | Smart lock. Accepts: lock, unlock. — méthodes : `__init__` 61, `apply_command` 66, `get_state` 76 |
| 83 | classe `SmokeSensor` | Smoke / fire detector. Read-only. — méthodes : `__init__` 91, `trigger_alarm` 96, `clear_alarm` 100, `apply_command` 104, `get_state` 107 |
| 111 | classe `AlarmSiren` | Alarm siren. Accepts: arm, disarm. — méthodes : `__init__` 116, `apply_command` 121, `get_state` 132 |

## Relations

- **Utilise** : [sim/devices/base.py](devices-base.md)
- **Utilisé par** : [sim/cli.py](cli.md), [sim/dashboard/runtime.py](dashboard-runtime.md)
- **Testé par** : `tests/test_config.py`, `tests/test_dashboard.py`, `tests/test_devices.py` → [tests de jabfy-simulation](tests.md)
