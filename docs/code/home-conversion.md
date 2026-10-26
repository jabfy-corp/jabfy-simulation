# `sim/home/conversion.py`

> **Rôle** — Convertit la maison éditable en config de simulation (topics, règles réflexes) et inversement.

Dépôt : [jabfy-simulation](README.md) · 161 lignes · statut : **actif**

Docstring du module : *Translate the visual house into the simulator's existing MQTT configuration.*

## À retenir

- `default_home` l.27 avec l'automatisation `salon_presence` l.49.
- `device_wire_id` l.54 → `sim_{home}_{device}` ; `to_sim_config` l.59.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 13 | `_COLORS` | constante |
| 14 | `_INITIAL` | constante |
| 19 | `_DEVICE_NAMES` | constante |
| 27 | `default_home()` | A small furnished layout matching the original seven-device dashboard. |
| 54 | `device_wire_id()` | Stable namespace separating this home's simulated endpoints from legacy topics. |
| 59 | `to_sim_config()` | Generate device topics and reflex rules on the server, retaining runtime settings. |
| 99 | `_room_slug()` |  |
| 111 | `from_sim_config()` | Import devices and only exact, paired motion-to-light rules. |

## Relations

- **Utilise** : [sim/config/schema.py](config-schema.md), [sim/home/models.py](home-models.md)
- **Utilisé par** : [sim/dashboard/guard.py](dashboard-guard.md), [sim/dashboard/runtime.py](dashboard-runtime.md)
