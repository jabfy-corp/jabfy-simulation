# `sim/emitters/modbus_server.py`

> **Rôle** — Serveur Modbus TCP (port 5020) exposant les registres des appareils climat.

Dépôt : [jabfy-simulation](README.md) · 253 lignes · statut : **actif**

Docstring du module : *Modbus TCP server — serves climate device registers over real Modbus TCP.*

## À retenir

- `ModbusServer` l.122.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 41 | `_IR_TEMP` | constante |
| 42 | `_IR_HUM` | constante |
| 43 | `_HR_SP` | constante |
| 44 | `_HR_HEAT` | constante |
| 51 | `_make_action()` | Return an async action callback for a single climate device. |
| 122 | classe `ModbusServer` | Modbus TCP server that exposes climate device state as live registers. — méthodes : `__init__` 137, `start` 164, `stop` 187, `unit_map` 199, `port_in_use` 204, `_build_sim_devices` 209, `_run_loop` 239, `_serve` 248 |

## Relations

- **Utilise** : [sim/devices/base.py](devices-base.md), [sim/devices/climate.py](devices-climate.md)
- **Utilisé par** : [sim/runner.py](runner.md)
- **Testé par** : `tests/test_modbus_server.py` → [tests de jabfy-simulation](tests.md)
