# `sim/cli.py`

> **Rôle** — Commande `jabfy-sim` : `demo`, `run`, `ui`.

Dépôt : [jabfy-simulation](README.md) · 232 lignes · statut : **actif**

Docstring du module : *CLI for jabfy-sim.*

## À retenir

- `cmd_ui` l.144 : store, audit `home.audit.jsonl`, uvicorn hôte 127.0.0.1 par défaut.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 18 | `cmd_demo()` | Hardcoded demo: motion sensor triggers lamp turn-on through the full pipeline. |
| 113 | `cmd_run()` | Run jabfy-sim from a YAML config file. |
| 136 | `_parse_broker()` | Parse 'host:port' or 'host' string. |
| 144 | `cmd_ui()` | Serve a local dashboard and run its real-protocol simulation. |
| 182 | `build_parser()` |  |
| 222 | `main()` |  |

## Relations

- **Utilise** : [sim/config/loader.py](config-loader.md), [sim/config/schema.py](config-schema.md), [sim/dashboard/app.py](dashboard-app.md), [sim/devices/security.py](devices-security.md), [sim/runner.py](runner.md)
- **Utilisé par** : aucun import direct (point d'entrée, appelé par HTTP, CLI ou navigateur)
- **Testé par** : `tests/test_dashboard.py` → [tests de jabfy-simulation](tests.md)
