# `sim/dashboard/guard.py`

> **Rôle** — `HomeGuard` : autorisation jabfy-guard pour le bus du simulateur.

Dépôt : [jabfy-simulation](README.md) · 99 lignes · statut : **actif**

Docstring du module : *Trusted adapter from the virtual house and Bus messages to jabfy-guard.*

## À retenir

- Une règle par appareil, max 60/min.
- `allow_sensitive_simulation=True` partout : un `unlock` manuel est autorisé côté simulateur, contrairement à Core.
- Sources acceptées : `simulation_dashboard`, `reflex_engine`.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 20 | `_parameters()` |  |
| 37 | classe `HomeGuard` | méthodes : `__init__` 38, `__call__` 67 |

## Relations

- **Utilise** : jabfy_bus/core/types.py (jabfy-bus), jabfy_bus/verification/policies.py (jabfy-bus), src/jabfy_guard/__init__.py (jabfy-guard), [sim/dashboard/commands.py](dashboard-commands.md), [sim/home/catalog.py](home-catalog.md), [sim/home/conversion.py](home-conversion.md)
- **Utilisé par** : [sim/dashboard/commands.py](dashboard-commands.md)
