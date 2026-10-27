# Architecture du prototype de maison

La maison est un document indépendant de l’affichage et des protocoles. Il décrit
ce qui existe et où se trouvent les objets. Le moteur de simulation possède les
états vivants. La scène 3D, les commandes manuelles et l’IA utilisent ces deux sources.

```text
Document Home ──► conversion en configuration ──► SimRunner
    │                                              │
    ├──► éditeur / scène 3D ◄──── état vivant ───────┤
    └──► inventaire IA ◄───────────────────────────┘
               │
         Jabfy Core + Ollama
               │ propositions validées
               ▼
Interface ──► commande par ID ──► vérification ──► MQTT ──► appareil simulé
                                       └──────────────────► audit
```

## Modules

| Module | Responsabilité |
| --- | --- |
| `sim/home/models.py` | Contrat `Home`, pièces, appareils, automatismes ; validation des références, dimensions et positions. |
| `sim/home/catalog.py` | Types d’appareils, commandes, événements de capteurs et schémas de paramètres. |
| `sim/home/store.py` | Lecture et remplacement atomique du fichier JSON local. |
| `sim/home/conversion.py` | Passage du document indépendant des protocoles à la configuration MQTT ; import limité du YAML existant. |
| `sim/dashboard/app.py` | Routes HTTP et validation des requêtes. |
| `sim/dashboard/runtime.py` | Boucle de simulation, file de travail, snapshots, journal et remplacement de la maison. |
| `sim/dashboard/commands.py` | Résolution d’un ID logique vers l’appareil simulé et publication de `command.requested`. |
| `sim/dashboard/core_client.py` | Appels HTTP à Core, à une adresse configurée par le serveur. |
| `sim/dashboard/static/` | Modules ES de l’éditeur, de la scène 3D, des commandes et des propositions IA. |
| `jabfy-core/app/simulation/` | Lecture du contexte courant, prompt dynamique, validation de toutes les commandes proposées. |

Les bibliothèques graphiques sont isolées dans `static/vendor` avec leur licence.
Le code applicatif n’a ni framework de composants, ni bundler, ni dépendance à un CDN.

## Exécution en conteneurs

`jabfy-deploy/compose.local.yml` lance `jabfy-sim` (interface et moteur), `mosquitto`,
`core` et `ollama` sur le même réseau Docker. Deploy seul possède l'orchestration ;
Simulation fournit son image. Guard est une bibliothèque Python intégrée au runtime.
Le bus reste embarqué dans le moteur :
aucun second bus ne doit exécuter les mêmes commandes. Core lit
`http://jabfy-sim:8080/api/ai/context`, interroge `http://ollama:11434` et reçoit
les demandes via le proxy du simulateur vers `http://core:8000`.
Les serveurs d’appareils HTTP/Modbus et leurs clients restent sur `127.0.0.1`
dans le conteneur du simulateur, indépendamment de l’adresse du broker MQTT.

La maison et l’audit sont montés depuis `../jabfy-simulation/data` (depuis Deploy),
jamais copiés dans l’image.
Les modèles restent dans le volume `ollama-models`. Le contexte de construction
du simulateur est limité par `Dockerfile.dockerignore` aux sources de Simulation,
Bus et Guard ;
les autres dépôts, secrets, environnements virtuels et données sont exclus.

Compose attend la disponibilité de MQTT et de Core avant de lancer l’interface.
`docker/start.py` attend aussi MQTT lors d’un redémarrage direct des conteneurs,
puis remplace son processus par celui de l’application pour transmettre les signaux.
`docker/healthcheck.py` vérifie le moteur et ses deux connexions MQTT. Un contrôle
de santé en échec est visible depuis Deploy dans `docker compose -f compose.local.yml ps` ; il ne redémarre pas à lui
seul un processus encore vivant. Les processus arrêtés bénéficient de
`restart: unless-stopped`.

L’interface et MQTT sont publiés uniquement sur loopback. Core et Ollama n’ont
aucun port hôte publié. Aucune configuration GPU n'est imposée. Le lanceur de Deploy
télécharge un modèle sauf avec `--no-ai` ; Compose seul n'en télécharge aucun.

## Document Home v1

Les dimensions sont en mètres. Le plan utilise X/Z, Y étant la hauteur. X/Z d’une
pièce sont globaux ; X/Z d’un appareil sont relatifs à sa pièce. Les identifiants
restent stables lors d’un renommage et sont distincts des noms affichés.

```json
{
  "schema_version": 1,
  "id": "maison",
  "name": "Mon appartement",
  "rooms": [
    {"id": "salon", "name": "Salon", "x": 0, "z": 0,
     "width": 6, "depth": 5, "height": 2.7, "color": "#dce9e2"}
  ],
  "devices": [
    {"id": "lampe", "name": "Lampe du canapé", "type": "dimmer_light",
     "room_id": "salon", "x": 3, "z": 2}
  ],
  "automations": []
}
```

Le modèle refuse les IDs en double, appareils hors pièce, références inexistantes,
pièces qui se chevauchent, types inconnus et valeurs non finies. Une automatisation
v1 relie `motion_device_id` à `target_device_id` : présence ON, absence OFF. Le fichier
ne contient aucune adresse réseau, secret, décision de sécurité ou état de session.

## Contrat HTTP

| Route | Fonction |
| --- | --- |
| `GET /api/home` | Document enregistré actif. |
| `PUT /api/home` | Valide et applique un document complet, puis le sauvegarde. |
| `GET /api/catalog` | Types, commandes, schémas JSON des paramètres et événements autorisés. |
| `GET /api/state` | États, connexion, événements récents et révision de la maison. |
| `POST /api/devices/{id}/commands` | `{action, params, context_revision?}` ; résultat `executed`, `rejected` ou `failed`. |
| `POST /api/devices/{id}/events` | `{event}` : `motion`, `smoke_on` ou `smoke_off` selon le capteur. |
| `POST /api/devices/{id}/motion` | Compatibilité : détection avec `duration_ms` bornée. |
| `GET /api/ai/context` | Maison, pièces, appareils, capacités, états et révision pour l’IA. |
| `GET /api/ai/models` | Modèles disponibles via Core. |
| `POST /api/ai/propose` | `{model, prompt}` transmis à `/simulation/propose` de Core. |

Une proposition IA contient `explanation`, `commands` et `context_revision`. Chaque
commande contient `device_id`, `action` et `params`. Core recharge l’inventaire à
chaque demande et rejette entièrement une proposition invalide. Il n’exécute aucune
commande. Les requêtes d’application repassent par la validation locale et le bus.
`executed` confirme le passage par le transport ; l’état publié par l’appareil est
ensuite affiché lors du prochain rafraîchissement.

## Édition et cohérence

Le navigateur garde un brouillon. Une sauvegarde validée est placée dans la file de
travail du moteur : seul ce thread remplace le runner et injecte les événements de
capteurs. Les appareils de même ID/type gardent leur état ; les règles inchangées
gardent leur détection des transitions. En cas d’échec d’application ou d’écriture,
la maison précédente est conservée et son moteur est relancé. Le fichier est remplacé
atomiquement pour éviter un JSON partiellement écrit.

Les lecteurs reçoivent des copies des snapshots. La révision est une empreinte du
document, pas du temps de simulation : déplacer/renommer un appareil invalide une
proposition IA antérieure, tandis que les mesures continuent d’évoluer normalement.
Les requêtes navigateur de modification refusent les origines différentes.

## Limite entre simulation et maison réelle

Les topics virtuels sont construits par le serveur :
`zigbee2mqtt/sim_<home.id>_<device.id>`. Les commandes ne peuvent fournir ni destination,
ni niveau de confiance, ni approbation. Une politique par appareil virtuel autorise
ses capacités connues, avec des paramètres bornés. Le moteur de vérification et
l’audit existants restent sur le chemin de chaque commande.

Pour raccorder ultérieurement le matériel réel, ajouter un adaptateur d’inventaire
et de transport derrière ces IDs, avec découverte, authentification et politiques
propres au matériel. Ne pas réutiliser automatiquement les permissions du laboratoire.
L’éditeur et la scène pourront conserver le même document. Plusieurs étages ou des
murs libres nécessiteront une évolution versionnée du schéma ; ce prototype ne les
implémente pas.
