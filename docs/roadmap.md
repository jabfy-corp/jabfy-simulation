# État actuel et feuille de route

## État

- Maison personnalisable : éditeur de plan, scène 3D, visite à hauteur d'homme, automatisations capteur → appareil.
- Dix types d'appareils virtuels, émulés en MQTT (Zigbee2MQTT), Modbus TCP et HTTP.
- Bus et guard embarqués avec audit chaîné.
- Onglet IA : envoi des prompts à Core et suivi de l'exécution.
- Image Docker, lancée par jabfy-deploy ; la pile V0.0.1 ne pilote que des appareils virtuels.

## Limites connues

- Un seul étage et des pièces rectangulaires ; plusieurs étages ou des murs libres demandent une nouvelle version du schéma.
- Une seule automatisation en v1 : un détecteur de mouvement vers une cible (présence allume, absence éteint).
- Le bus est embarqué dans le processus : ce n'est pas un service réseau.
- Pas d'accélération GPU dans la configuration portable.
- Pas d'authentification sur l'interface.
- La CI du dépôt ne lance pas les tests (voir [Tests](tests.md)).

## À faire

- Faire exécuter `pytest` par la CI.
- Utiliser le simulateur pour des benchmarks reproductibles lancés en CI (objectif performance du projet).
- Raccorder du matériel réel derrière les mêmes identifiants, avec un adaptateur d'inventaire et de transport, de la découverte, de l'authentification et des politiques propres au matériel.
- Choisir avec Core si `/api/ai/propose` reste à côté de `/api/ai/prompt` : les deux routes de Core existent sur `main`.
