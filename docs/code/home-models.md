# `sim/home/models.py`

> **Rôle** — Modèles de la maison éditable : pièces, appareils, automatisations.

Dépôt : [jabfy-simulation](README.md) · 131 lignes · statut : **actif**

Docstring du module : *Validated, protocol-independent layout of a simulated house.*

## À retenir

- `Room` l.22, `HouseDevice` l.46, `Automation` l.69, `Home` l.75.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 15 | `LIGHT_TYPES` | constante |
| 18 | classe `HouseModel` |  |
| 22 | classe `Room` | méthodes : `nonempty_name` 34, `world_bounds` 40 |
| 46 | classe `HouseDevice` | méthodes : `known_device_type` 56, `nonempty_name` 63 |
| 69 | classe `Automation` |  |
| 75 | classe `Home` | méthodes : `integer_version` 85, `nonempty_name` 92, `coherent_layout` 98 |

## Relations

- **Utilise** : aucun fichier JABFY documenté (bibliothèques externes seulement)
- **Utilisé par** : [sim/dashboard/app.py](dashboard-app.md), [sim/home/conversion.py](home-conversion.md), [sim/home/store.py](home-store.md)
