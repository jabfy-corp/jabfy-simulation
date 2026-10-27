# `sim/devices/entertainment.py`

> **Rôle** — TV connectée simulée (machine à états).

Dépôt : [jabfy-simulation](README.md) · 141 lignes · statut : **actif**

Docstring du module : *Entertainment device state machines.*

## À retenir

- `SmartTV` l.20.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 17 | `VALID_SOURCES` | constante |
| 20 | classe `SmartTV` | Samsung-style Smart TV state machine. — méthodes : `__init__` 33, `apply_command` 53, `get_state` 134 |

## Relations

- **Utilise** : [sim/devices/base.py](devices-base.md)
- **Utilisé par** : [sim/runner.py](runner.md)
- **Testé par** : `tests/test_bus_http_modbus.py`, `tests/test_docker.py`, `tests/test_entertainment.py`, `tests/test_http_server.py` → [tests de jabfy-simulation](tests.md)
