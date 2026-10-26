# `docker/start.py`

> **Rôle** — Démarrage du conteneur : attend MQTT (60 s) puis lance `jabfy-sim ui` sur 0.0.0.0:8080.

Dépôt : [jabfy-simulation](README.md) · 30 lignes · statut : **actif**

Docstring du module : *Start the container UI once MQTT is listening, including after a Docker restart.*

## À retenir

- Core visé par `JABFY_CORE_URL`, défaut `http://core:8000`.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 8 | `main()` |  |

## Relations

- **Utilise** : aucun fichier JABFY documenté (bibliothèques externes seulement)
- **Utilisé par** : aucun import direct (point d'entrée, appelé par HTTP, CLI ou navigateur)
