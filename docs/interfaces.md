# Interfaces

## API HTTP

Servie par `sim/dashboard/app.py`. Les routes qui modifient l'état refusent les requêtes dont l'en-tête `Origin` diffère de l'adresse du serveur (403).

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/state` | États, connexion, événements récents, révision de la maison |
| GET | `/api/home` | Document de la maison enregistrée |
| PUT | `/api/home` | Valide, applique et sauvegarde une maison complète |
| GET | `/api/catalog` | Types d'appareils, commandes, schémas de paramètres, événements |
| POST | `/api/devices/{id}/commands` | `{action, params, context_revision?}` ; résultat `executed`, `rejected` ou `failed` |
| POST | `/api/devices/{id}/events` | `{event}` : `motion`, `smoke_on`, `smoke_off` (202) |
| POST | `/api/devices/{id}/motion` | Compatibilité : détection avec `duration_ms` (202) |
| GET | `/api/ai/context` | Inventaire complet pour l'IA, avec révision |
| GET | `/api/ai/models` | Modèles disponibles, via `GET /models` de Core |
| POST | `/api/ai/propose` | `{model, prompt}` transmis à `POST /simulation/propose` de Core |
| POST | `/api/ai/prompt` | `{model, prompt}` transmis à `POST /prompt` de Core (202) |
| GET | `/api/ai/runs/{run_id}` | Suivi d'une exécution, via `GET /prompts/{id}` de Core |

`prompt` fait de 1 à 4000 caractères. `/api/ai/prompt` et `/api/ai/runs/{id}` demandent un Core qui expose `/prompt` (branche `core-12-bus-integration`). `/api/ai/propose` correspond à la V0.0.1 de Core (`core-3`). Le détail du contrat est dans [Architecture du prototype de maison](house-architecture.md).

## Types d'appareils

| Type | Domaine | Commandes ou événements |
|---|---|---|
| `on_off_light` | switch | allumer, éteindre, basculer |
| `dimmer_light` | switch | + luminosité |
| `rgb_bulb` | switch | + luminosité, couleur |
| `motion_sensor` | binary_sensor | événement `motion` |
| `door_lock` | lock | verrouiller, déverrouiller |
| `smoke_sensor` | binary_sensor | événements `smoke_on`, `smoke_off` |
| `alarm_siren` | alarm | armer, désarmer |
| `temperature_sensor` | sensor | lecture seule |
| `thermostat` | climate | régler la consigne |
| `smart_tv` | switch | allumer, éteindre |

La liste de référence est servie par `GET /api/catalog`.

## MQTT

- Télémétrie : `zigbee2mqtt/<id>`
- Commandes : `zigbee2mqtt/<id>/set` (abonnement en qos 1)
- Pour une maison créée dans l'interface, le serveur construit lui-même le topic : `zigbee2mqtt/sim_<home.id>_<device.id>`. Une commande ne peut pas fournir sa destination.

## Modbus et HTTP

- Modbus TCP, port 5020 : registres de climat (température, humidité, consigne, chauffage).
- HTTP, port 8001 : faux serveur de télévision (`/api/v2/state`, `/api/v2/power`) ; port 5000 : faux NAS en lecture seule.

## Configuration YAML

`jabfy-sim run` et `ui --config` lisent un fichier YAML (broker, `tick_interval_ms`, `audit_path`, `devices`, `reflex_rules`). Exemple commenté : `scenarios/sim.example.yaml`.
