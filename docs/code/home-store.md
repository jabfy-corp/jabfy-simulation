# `sim/home/store.py`

> **Rôle** — `HouseStore` : persiste la maison en JSON (écriture atomique).

Dépôt : [jabfy-simulation](README.md) · 45 lignes · statut : **actif**

Docstring du module : *Atomic local persistence of a validated house, with no runtime state.*

## À retenir

- `HouseStore` l.12.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 12 | classe `HouseStore` | méthodes : `__init__` 13, `load` 16, `save` 27 |

## Relations

- **Utilise** : [sim/home/models.py](home-models.md)
- **Utilisé par** : aucun import direct (point d'entrée, appelé par HTTP, CLI ou navigateur)
