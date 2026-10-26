# `sim/home/catalog.py`

> **Rôle** — Catalogue des types d'appareils, de leurs actions et domaines bus.

Dépôt : [jabfy-simulation](README.md) · 85 lignes · statut : **actif**

Docstring du module : *Device capabilities and bounded command parameters shared by API clients.*

## À retenir

- Lampes en domaine `switch`, serrure `lock`, sirène `alarm`, thermostat `climate`.
- `validate_command` l.79.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 10 | classe `NoParams` |  |
| 14 | classe `BrightnessParams` |  |
| 18 | classe `TemperatureParams` |  |
| 22 | classe `Color` |  |
| 28 | classe `ColorParams` |  |
| 32 | `_ACTIONS` | constante |
| 44 | `_POWER` | constante |
| 45 | `_TYPES` | constante |
| 59 | `device_capabilities()` | Return a fresh catalog entry, including JSON Schema for each action. |
| 75 | `catalog()` |  |
| 79 | `validate_command()` | Validate capability and parameters; authorization remains the bus's job. |

## Relations

- **Utilise** : aucun fichier JABFY documenté (bibliothèques externes seulement)
- **Utilisé par** : [sim/dashboard/app.py](dashboard-app.md), [sim/dashboard/commands.py](dashboard-commands.md), [sim/dashboard/guard.py](dashboard-guard.md), [sim/dashboard/runtime.py](dashboard-runtime.md)
- **Testé par** : `tests/test_home.py` → [tests de jabfy-simulation](tests.md)
