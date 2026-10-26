# `sim/dashboard/app.py`

> **Rôle** — Serveur FastAPI du simulateur : UI 3D, API maison, commandes manuelles, et passerelle vers Core pour l'onglet IA.

Dépôt : [jabfy-simulation](README.md) · 123 lignes · statut : **actif**

Docstring du module : *HTTP routes for the house document, live simulation, controls and AI bridge.*

## À retenir

- `same_origin` l.43 protège les routes du simulateur (pas Core).
- `GET /api/ai/context` l.98 : inventaire lu par Core.
- `POST /api/ai/prompt` l.110 → Core `/prompt` ; `GET /api/ai/runs/{run_id}` l.114 → Core `/prompts/{id}`.
- `POST /api/devices/{id}/commands` l.82 : commande manuelle, qui passe par le bus **du simulateur**.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 17 | `STATIC` | constante |
| 20 | classe `InputModel` |  |
| 24 | classe `MotionInput` |  |
| 28 | classe `CommandInput` |  |
| 34 | classe `SensorInput` |  |
| 38 | classe `ProposalInput` |  |
| 43 | `same_origin()` |  |
| 49 | `create_app()` |  |

## Relations

- **Utilise** : [sim/dashboard/core_client.py](dashboard-core-client.md), [sim/dashboard/runtime.py](dashboard-runtime.md), [sim/home/catalog.py](home-catalog.md), [sim/home/models.py](home-models.md)
- **Utilisé par** : [sim/cli.py](cli.md)
- **Testé par** : `tests/test_dashboard.py`, `tests/test_home_api.py` → [tests de jabfy-simulation](tests.md)
