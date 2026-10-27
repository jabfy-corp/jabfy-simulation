# `sim/dashboard/core_client.py`

> **Rôle** — Client HTTP du simulateur vers Core.

Dépôt : [jabfy-simulation](README.md) · 30 lignes · statut : **actif**

Docstring du module : *Small HTTP bridge to Jabfy Core. The destination is server configuration.*

## À retenir

- Timeout 150 s en POST, 5 s en GET ; erreurs → 502/503.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 10 | classe `CoreClient` | méthodes : `__init__` 11, `request` 14 |

## Relations

- **Utilise** : aucun fichier JABFY documenté (bibliothèques externes seulement)
- **Utilisé par** : [sim/dashboard/app.py](dashboard-app.md)
