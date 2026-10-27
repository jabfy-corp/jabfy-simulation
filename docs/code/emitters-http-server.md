# `sim/emitters/http_server.py`

> **Rôle** — Faux serveurs REST (SmartTV port 8001, NAS port 5000) pour tester l'adapter HTTP.

Dépôt : [jabfy-simulation](README.md) · 283 lignes · statut : **actif**

Docstring du module : *HTTP mock server — mimics real device REST APIs for testing jabfy-bus.*

## À retenir

- `HTTPMockServer` l.38.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 38 | classe `HTTPMockServer` | Runs SmartTV + NAS mock REST APIs in a background thread. — méthodes : `__init__` 56, `start` 80, `stop` 111 |
| 126 | `_build_tv_app()` | Build FastAPI app that wraps a SmartTV device. |
| 191 | `_default_nas_data()` |  |
| 207 | `_build_nas_app()` | Build a Synology DSM-style FastAPI app (read-only stub). |

## Relations

- **Utilise** : aucun fichier JABFY documenté (bibliothèques externes seulement)
- **Utilisé par** : [sim/runner.py](runner.md)
- **Testé par** : `tests/test_bus_http_modbus.py`, `tests/test_http_server.py` → [tests de jabfy-simulation](tests.md)
