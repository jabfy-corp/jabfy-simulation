# Installation et lancement

## Pile complète (recommandé)

Le lancement global appartient à [jabfy-deploy](https://github.com/jabfy-corp/jabfy-deploy). Les dépôts `jabfy-deploy`, `jabfy-simulation`, `jabfy-bus`, `jabfy-guard` et `jabfy-core` doivent être côte à côte, sur les branches V0.0.1 (voir [Jabfy V0.0.1](v0.0.1.md)).

```bash
cd /chemin/vers/jabfy-deploy
python3 scripts/start.py            # --no-ai pour ne pas télécharger de modèle
```

L'interface est sur `http://127.0.0.1:8080`. Deploy lance `jabfy-sim`, `mosquitto`, `core` et `ollama`. Guard est une bibliothèque Python et Bus est embarqué dans le processus du simulateur : ce ne sont pas des services séparés.

Pour les ports, l'IA dans Docker, l'arrêt et le diagnostic, voir le README du dépôt jabfy-simulation.

## Développement hors Docker

Prérequis : Python 3.11 ou plus, un broker MQTT, et les dépôts voisins `jabfy-bus` et `jabfy-guard`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e "../jabfy-guard" -e "../jabfy-bus[all]" -e ".[ui]"
docker compose -f ../jabfy-deploy/compose.local.yml up mosquitto -d
jabfy-sim ui
```

Ne pas lancer `jabfy-sim ui` en même temps que le conteneur `jabfy-sim` : deux simulateurs publieraient sur les mêmes topics.

## Commandes de la CLI

| Commande | Rôle |
|---|---|
| `jabfy-sim ui` | Interface web, éditeur 3D et simulation |
| `jabfy-sim run --config FICHIER.yaml` | Simulation pilotée par un fichier YAML (voir `scenarios/sim.example.yaml`) |
| `jabfy-sim demo` | Démo mouvement → lampe, s'arrête après 15 étapes par défaut |

Options de `ui` :

| Option | Défaut | Rôle |
|---|---|---|
| `--host` | `127.0.0.1` | Adresse d'écoute |
| `--port` | `8080` | Port HTTP |
| `--broker` | celui de la config | Broker MQTT `HOST[:PORT]` |
| `--home-file` | `data/home.json` | Maison enregistrée ; l'audit est écrit à côté, en `.audit.jsonl` |
| `--core-url` | `http://127.0.0.1:8000` | API de Jabfy Core |
| `--config` | aucune | YAML de départ (sinon maison de démonstration) |

## Dépendances optionnelles

| Extra | Contenu |
|---|---|
| `ui` | bus, guard, FastAPI, uvicorn : interface web |
| `modbus` | serveur Modbus TCP des appareils de climat |
| `http` | faux serveurs HTTP (télévision, NAS) |
| `full` | tout ce qui précède |
| `dev` | `full` plus pytest et httpx |

## Ports

| Port | Service | Exposition |
|---|---|---|
| 8080 | interface et API | loopback ; `0.0.0.0` dans le conteneur, publié sur `127.0.0.1` seulement |
| 1883 | broker MQTT | loopback via Deploy |
| 5020 | serveur Modbus TCP | `127.0.0.1` dans le conteneur |
| 8001 | faux serveur télévision | `127.0.0.1` dans le conteneur |
| 5000 | faux serveur NAS | `127.0.0.1` dans le conteneur |

Variables du conteneur : `MQTT_BROKER` (défaut `mosquitto:1883`) et `JABFY_CORE_URL` (défaut `http://core:8000`).
