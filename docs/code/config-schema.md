# `sim/config/schema.py`

> **Rôle** — Modèles pydantic de la config YAML (broker, appareils, règles réflexes).

Dépôt : [jabfy-simulation](README.md) · 71 lignes · statut : **actif**

Docstring du module : *Pydantic models for jabfy-sim YAML configuration.*

## À retenir

- `SimConfig` l.58, ids uniques l.67.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 10 | classe `BrokerConfig` |  |
| 17 | classe `DeviceConfig` |  |
| 27 | classe `ReflexTrigger` | Condition that fires the reflex rule. |
| 37 | classe `ReflexCommand` | Command to propose when the trigger fires. |
| 52 | classe `ReflexRule` |  |
| 58 | classe `SimConfig` | Root configuration object. — méthodes : `_unique_device_ids` 67 |

## Relations

- **Utilise** : aucun fichier JABFY documenté (bibliothèques externes seulement)
- **Utilisé par** : [sim/cli.py](cli.md), [sim/config/loader.py](config-loader.md), [sim/dashboard/defaults.py](dashboard-defaults.md), [sim/emitters/mqtt.py](emitters-mqtt.md), [sim/home/conversion.py](home-conversion.md), [sim/integration/bus_runner.py](integration-bus-runner.md), [sim/integration/reflex.py](integration-reflex.md), [sim/runner.py](runner.md)
- **Testé par** : `tests/test_bus_http_modbus.py`, `tests/test_config.py`, `tests/test_dashboard.py`, `tests/test_docker.py`, `tests/test_home.py`, `tests/test_home_api.py`, `tests/test_reflex.py` → [tests de jabfy-simulation](tests.md)
