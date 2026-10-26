# `sim/dashboard/defaults.py`

> **Rôle** — Maison par défaut du dashboard (7 appareils, règle mouvement → lumière).

Dépôt : [jabfy-simulation](README.md) · 35 lignes · statut : **actif**

Docstring du module : *Small built-in home, usable from an installed wheel without a config file.*

## À retenir

- `home_config`.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 6 | `home_config()` |  |

## Relations

- **Utilise** : [sim/config/schema.py](config-schema.md)
- **Utilisé par** : aucun import direct (point d'entrée, appelé par HTTP, CLI ou navigateur)
- **Testé par** : `tests/test_home.py` → [tests de jabfy-simulation](tests.md)
