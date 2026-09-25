# jabfy-sim

External simulation lab for the JABFY ecosystem. Speaks real MQTT in Zigbee2MQTT format
so `jabfy-bus`'s real adapters see it as physical hardware.

## Démarrage avec Docker (recommandé)

Prérequis : Docker avec Compose, et les dépôts `jabfy-simulation`, `jabfy-bus`
et `jabfy-core` côte à côte dans le même dossier. Aucun Python ni Ollama à
installer sur la machine hôte.

```bash
cd /chemin/vers/jabfy/jabfy-simulation
docker compose up --build -d --wait
```

Ouvrir **http://localhost:8080**. Cette commande lance quatre conteneurs :

| Service | Rôle |
| --- | --- |
| `jabfy-sim` | Interface 3D, éditeur et simulation avec le bus de vérification embarqué. |
| `mosquitto` | Échanges MQTT des appareils virtuels. |
| `core` | Inventaire dynamique et validation des propositions IA. |
| `ollama` | Serveur de modèles local, sans téléchargement automatique de modèle. |

Le premier lancement télécharge les images et construit les deux applications.
Le simulateur reste ensuite actif : ce n’est plus une démo qui s’arrête après
20 étapes. Les contrôles de santé vérifient le moteur et les connexions MQTT.

### Utiliser l’IA dans Docker

Télécharger le modèle de votre choix une fois, en remplaçant `NOM_DU_MODELE`
par son nom et son tag Ollama :

```bash
docker compose exec ollama ollama pull NOM_DU_MODELE
docker compose exec ollama ollama list
```

Dans l’onglet **IA**, cliquer sur **Actualiser**, puis sélectionner le modèle.
Les modèles sont conservés dans le volume `ollama-models`. Sans modèle, l’édition,
la 3D et le pilotage manuel fonctionnent normalement. La configuration portable
utilise le CPU ; elle ne configure pas d’accélération GPU.
Les fonctionnalités cloud d’Ollama sont désactivées avec `OLLAMA_NO_CLOUD=1`
([documentation Ollama](https://docs.ollama.com/faq#how-do-i-disable-ollama-cloud-features)).

### Arrêter, relancer et diagnostiquer

```bash
docker compose stop              # arrêter tous les services, sans effacer les données
docker compose up -d --wait       # relancer
docker compose logs -f jabfy-sim core
docker compose ps
```

Les services redémarrent avec Docker sauf s’ils ont été arrêtés explicitement.
Après modification du code, utiliser de nouveau `docker compose up --build -d --wait`.
Le plan et l’audit existants sont conservés dans **`./data`**, monté dans le
conteneur : aucune migration du fichier `data/home.json` n’est nécessaire.
`docker compose down` conserve ce dossier et le volume des modèles ; ne pas ajouter
`--volumes` si vous souhaitez garder les modèles téléchargés.

Seuls l’interface (8080) et MQTT (1883) sont publiés, sur **127.0.0.1** uniquement.
Core et Ollama sont accessibles entre conteneurs, pas depuis le réseau local.
1883 n’est pas une page web. Si un port est déjà occupé, ne pas lancer une seconde
simulation locale ; arrêter l’ancienne ou choisir d’autres ports :

```bash
SIM_PORT=8082 MQTT_PORT=1884 docker compose up -d --wait
```

Dans ce cas, ouvrir http://localhost:8082 et réutiliser les mêmes variables pour
les lancements suivants (ou les enregistrer dans un fichier `.env` local).
La stack `jabfy-deploy` du site vitrine est indépendante et peut déjà occuper 8080.

L’ancienne démo reste disponible à la demande, sans la faire tourner en parallèle
avec la maison active :

```bash
docker compose stop jabfy-sim
docker compose run --rm --no-deps jabfy-sim jabfy-sim demo --broker mosquitto:1883
docker compose up -d jabfy-sim
```

## Maison personnalisable et vue 3D

L’interface française permet de créer son plan, placer des appareils, visiter la
maison en 3D et piloter la simulation. Le même inventaire alimente l’éditeur, la
scène et Jabfy Core. Three.js est fourni localement, avec sa licence ; aucun CDN,
compte externe ou build JavaScript n’est nécessaire.

Alternative hors Docker pour le développement : depuis ce dossier, avec le dépôt
voisin `jabfy-bus` disponible (ne pas lancer en parallèle du conteneur `jabfy-sim`) :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e "../jabfy-bus[all]" -e ".[ui]"
docker compose up mosquitto -d
jabfy-sim ui
```

Ouvrir **http://127.0.0.1:8080** :

1. Dans **Maison**, nommer les pièces, régler dimensions et positions, puis ajouter
   des appareils. Les modifications sont un brouillon jusqu’à **Enregistrer la maison**.
2. Tourner et zoomer autour de la scène, ou choisir **Visiter** pour se déplacer à
   hauteur d’homme. Les raccourcis des pièces permettent de s’y rendre directement.
3. Sélectionner un appareil dans la scène ou dans **Appareil**, puis utiliser ses
   commandes : éclairage, luminosité, couleur, consigne, serrure, sirène ou télévision.
4. Relier un détecteur à une lampe dans **Automatisations**, puis simuler un mouvement.
   La détection dure cinq secondes ; l’absence éteint la lampe associée.
5. Exporter/importer le fichier JSON pour conserver ou échanger un plan.

La maison est sauvegardée dans `data/home.json`, ignoré par Git. Les changements de
plan conservent l’état des appareils dont l’identifiant et le type sont inchangés.
Un redémarrage complet repart des états initiaux ; le plan, lui, est conservé.

Pour utiliser un autre fichier ou importer un scénario YAML :

```bash
jabfy-sim ui --home-file data/ma-maison.json
jabfy-sim ui --config scenarios/sim.example.yaml --home-file data/importee.json
jabfy-sim ui --broker localhost:1884 --port 8081
```

Le fichier maison existant est prioritaire. `--config` initialise uniquement un
nouveau fichier : les appareils sont disposés automatiquement et seules les règles
compatibles « présence → lampe ON / absence → OFF » sont importées. Les scénarios
YAML avancés restent utilisables avec la commande `run` existante.

`ui` démarre sa propre simulation. Les topics sont générés sous
`zigbee2mqtt/sim_<maison>_<appareil>` ; le navigateur ne choisit jamais d’adresse
MQTT. Ne pas lancer deux instances de la même maison sur le même broker. Mosquitto
ou un autre broker MQTT doit être démarré avant l’interface. Ctrl-C arrête la
simulation ; après un échec de démarrage, corriger la connexion puis relancer.

### Connecter l’IA Jabfy

**Avec Docker, cette connexion est déjà configurée**, via les noms de services
`core`, `ollama` et `jabfy-sim`. Les étapes suivantes concernent uniquement le
lancement hors Docker.

Dans le dépôt voisin `jabfy-core`, installer ses dépendances puis démarrer :

```bash
JABFY_SIMULATION_URL=http://127.0.0.1:8080 \
  uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`GET http://127.0.0.1:8000/simulation/home` permet de vérifier la découverte des
pièces, appareils, états et capacités, même sans modèle IA. Pour proposer des
actions depuis l’onglet **IA**, démarrer également Ollama avec un modèle disponible.
Le modèle propose, Jabfy Core valide les capacités, puis le bouton d’application
envoie chaque commande au moteur de vérification du simulateur. Un changement du
plan invalide les anciennes propositions. L’absence de Core ou d’Ollama est affichée
explicitement ; aucune réponse de modèle n’est simulée.

L’adresse de Core se règle côté serveur : `jabfy-sim ui --core-url http://127.0.0.1:8000`.
L’ancien endpoint `/act` de Core reste indépendant ; les propositions fondées sur
cette maison utilisent `/simulation/propose`.

### Limites de cette première version

Un étage, pièces rectangulaires, ouvertures et objets 3D schématiques. La visite
permet des déplacements libres, sans gestion des collisions. Le plan se
dessine manuellement : pas de scan automatique, de simulation physique de bâtiment,
de comptes utilisateurs ou de raccordement au matériel réel. Les commandes pilotent
les appareils **simulés** uniquement. Le serveur écoute sur loopback par défaut et
n’a pas d’authentification ; cette version est destinée à un usage local.

Le journal visuel conserve 80 événements. L’audit complet est enregistré dans le
fichier voisin `data/home.audit.jsonl` par défaut. Les autorisations de la maison
sont explicites et limitées à ses appareils virtuels et à leurs capacités ; les
politiques des anciens scénarios restent inchangées.

Voir [l’architecture et le contrat HTTP](docs/house-architecture.md) pour poursuivre
le développement.

## What it does

```
jabfy-sim emits motion event (MQTT)
  → Mosquitto broker
    → jabfy-bus Zigbee2MQTT adapter (parses Zigbee2MQTT format)
      → jabfy-bus Verification Engine (approves low-to-medium risk)
        → jabfy-bus Execution Layer (translates back to MQTT command)
          → Mosquitto broker
            → jabfy-sim receives /set command
              → device state updates (lamp: ON)
                → jabfy-sim re-emits telemetry
```

## Configuration

Copy `scenarios/sim.example.yaml` and customize:

```yaml
broker:
  host: localhost
  port: 1883

devices:
  - id: salon_lamp
    type: dimmer_light
    location: salon
    topic_prefix: zigbee2mqtt/salon_lamp

reflex_rules:
  - name: motion_to_light
    trigger:
      entity_id: binary_sensor.salon_motion_occupancy
      value: true
    command:
      action: turn_on
      target_entity_id: switch.salon_lamp_state
      target_domain: switch
      target_mqtt_topic: zigbee2mqtt/salon_lamp
```

Run with: `jabfy-sim run --config your_config.yaml`

## Device types

| Type | Key state | Commands |
|---|---|---|
| `on_off_light` | `state: ON/OFF` | turn_on, turn_off, toggle |
| `dimmer_light` | `state`, `brightness: 0–254` | + set_brightness |
| `rgb_bulb` | + `color: {r,g,b}` | + set_color |
| `motion_sensor` | `occupancy: bool` | (read-only) |
| `door_lock` | `state: LOCK/UNLOCK` | lock, unlock |
| `smoke_sensor` | `smoke: bool` | (read-only) |
| `alarm_siren` | `state: armed/disarmed` | arm, disarm |
| `temperature_sensor` | `temperature`, `humidity` | (read-only) |
| `thermostat` | `setpoint`, `local_temperature` | set_temperature |

## Tests

```bash
pytest              # device + config tests (no broker needed)
```

## Architecture notes

`jabfy-sim` embeds `jabfy-bus` as a Python dependency and runs the full pipeline
in-process. The MQTT broker (Mosquitto) is the only external dependency.

**Reflex Engine** (`sim/integration/reflex.py`) applies deterministic motion rules.
The house UI also connects to `jabfy-core` for AI proposals through the same verified
command path. Neither the 3D view nor the language model executes device methods.

See `CLAUDE.md` for full architecture and development guide.
