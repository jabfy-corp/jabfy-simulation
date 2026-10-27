# jabfy-simulation — build, Docker et CI

| fichier | ce qu'il fait |
|---|---|
| `pyproject.toml` | Python ≥ 3.11 ; commande `jabfy-sim`. |
| `Dockerfile`, `Dockerfile.dockerignore` | `python:3.11-slim` ; contexte = dossier parent pour installer guard, bus[all] et le simulateur. |
| `docker/start.py`, `docker/healthcheck.py` | Démarrage et sonde : voir leurs pages. |
| `scenarios/sim.example.yaml` | Exemple de config pour `jabfy-sim run`. |
| `jabfy-deploy/compose.local.yml` (dépôt voisin) | Lance mosquitto (127.0.0.1:1883), core (port 8000 **non publié** sur l'hôte), jabfy-sim (127.0.0.1:8080), ollama en option. Core reçoit `JABFY_SIMULATION_URL=http://jabfy-sim:8080`, `JABFY_MQTT_BROKER=mosquitto:1883`, `JABFY_LLM_BASE_URL` (défaut Ollama `/v1`). |
| `.github/workflows/ci.yml`, `pr-validation.yml`, `issue-labeler.yml` | Tests, validation de PR, étiquetage. |
