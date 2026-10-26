# `sim/config/loader.py`

> **Rôle** — Lit une config YAML/JSON et instancie les appareils.

Dépôt : [jabfy-simulation](README.md) · 54 lignes · statut : **actif**

Docstring du module : *Load a YAML config file and instantiate devices.*

## À retenir

- `load_config` l.28, `build_device` l.34.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 13 | `_read_file()` |  |
| 28 | `load_config()` | Parse a YAML/JSON config file into a validated SimConfig. |
| 34 | `build_device()` | Instantiate a Device from its DeviceConfig. |
| 52 | `build_devices()` | Build all devices declared in the config. |

## Relations

- **Utilise** : [sim/config/schema.py](config-schema.md)
- **Utilisé par** : [sim/cli.py](cli.md), [sim/runner.py](runner.md)
- **Testé par** : `tests/test_config.py`, `tests/test_home.py`, `tests/test_home_api.py` → [tests de jabfy-simulation](tests.md)
