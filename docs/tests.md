# Tests

## Lancer les tests

Les tests ont besoin des dépôts voisins `jabfy-bus` et `jabfy-guard` sur les branches V0.0.1. Aucun broker n'est nécessaire.

```bash
pip install -e ../jabfy-guard -e "../jabfy-bus[all]" -e ".[dev]"
pytest                                  # tous les tests
pytest tests/test_devices.py            # un fichier
pytest tests/test_devices.py::test_name # un seul test
```

Dernière exécution vérifiée sur `sim-3-core-ai-tab`, avec `guard-4-v001-deployment` et `bus-5-core-integration-support` : **218 passés, 4 ignorés**. Les ignorés sont les tests qui demandent la pile réelle.

## Ce que couvre chaque fichier

| Fichier | Sujet |
|---|---|
| `test_devices.py`, `test_entertainment.py` | Machines à états des appareils |
| `test_config.py`, `test_home.py` | Chargement YAML, modèle Home, catalogue |
| `test_home_api.py`, `test_dashboard.py` | API HTTP et interface |
| `test_http_server.py`, `test_modbus_server.py` | Faux serveurs HTTP et Modbus |
| `test_bus_http_modbus.py` | Adapters HTTP et Modbus de jabfy-bus face au simulateur |
| `test_reflex.py` | Automatismes de réflexe |
| `test_stack_integration.py` | Émetteur MQTT et BusRunner ensemble |
| `test_docker.py` | Configuration du conteneur |
| `e2e/test_ai_sequence_e2e.py` | Séquence IA de bout en bout |

Le détail test par test et les fichiers de code importés est dans [la page des tests de la documentation du code](code/tests.md).

## Tests de bout en bout

`tests/e2e/test_ai_sequence_e2e.py` est ignoré tant que `JABFY_E2E_URL` n'est pas défini. Il demande la pile réelle lancée par jabfy-deploy :

```bash
JABFY_E2E_URL=http://127.0.0.1:8080 pytest tests/e2e
```

## Points d'attention

- Le workflow `.github/workflows/ci.yml` du dépôt installe Node et lance `npm run lint` et `npm run build`. Il ne lance pas `pytest` : les tests ne sont donc pas exécutés par la CI.
- Le nombre de tests de [code/tests.md](code/tests.md) (173) date d'avant les derniers ajouts.
