# `sim/dashboard/commands.py`

> **Rôle** — Exécute une commande manuelle via le bus du simulateur et attend son résultat.

Dépôt : [jabfy-simulation](README.md) · 76 lignes · statut : **actif**

Docstring du module : *One command path for manual controls and accepted AI proposals.*

## À retenir

- `entity_id` l.14 : `{domain}.{wire_id}_state`.
- `execute_command` l.28 : adapter `simulation_dashboard`, trust INTERNAL, résultat par `correlation_id`.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 14 | `entity_id()` |  |
| 21 | `install_home_policies()` | Replace legacy policy evaluation, never add a bypass around Guard. |
| 28 | `execute_command()` |  |

## Relations

- **Utilise** : jabfy_bus/core/message.py (jabfy-bus), jabfy_bus/core/types.py (jabfy-bus), [sim/dashboard/guard.py](dashboard-guard.md), [sim/home/catalog.py](home-catalog.md)
- **Utilisé par** : [sim/dashboard/guard.py](dashboard-guard.md), [sim/dashboard/runtime.py](dashboard-runtime.md)
