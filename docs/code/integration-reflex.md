# `sim/integration/reflex.py`

> **Rôle** — `ReflexEngine` : automatisations locales (ex. présence → lampe) proposées sur le bus du simulateur.

Dépôt : [jabfy-simulation](README.md) · 161 lignes · statut : **actif**

Docstring du module : *Reflex Engine — rule-based stub for jabfy-core.*

## À retenir

- `_on_event` l.88, `_propose` l.126, adapter `reflex_engine`.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 40 | classe `ReflexEngine` | Converts matching bus events into command.requested proposals. — méthodes : `__init__` 53, `attach` 62, `restore_unchanged_rules` 71, `_on_event` 88, `_matches` 110, `_propose` 126 |

## Relations

- **Utilise** : jabfy_bus/core/bus.py (jabfy-bus), jabfy_bus/core/message.py (jabfy-bus), jabfy_bus/core/types.py (jabfy-bus), [sim/config/schema.py](config-schema.md)
- **Utilisé par** : [sim/integration/bus_runner.py](integration-bus-runner.md)
- **Testé par** : `tests/test_bus_http_modbus.py`, `tests/test_reflex.py` → [tests de jabfy-simulation](tests.md)
