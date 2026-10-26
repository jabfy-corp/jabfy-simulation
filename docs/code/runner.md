# `sim/runner.py`

> **Rôle** — `SimRunner` : lance émetteurs MQTT/HTTP/Modbus et le BusRunner en mode `run`.

Dépôt : [jabfy-simulation](README.md) · 233 lignes · statut : **actif**

Docstring du module : *SimRunner — orchestrates device ticks + MQTT emitter + bus pipeline.*

## À retenir

- `start` l.129, `_tick` l.206.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 22 | `DEVICE_SERVER_HOST` | constante |
| 25 | classe `SimRunner` | Coordinates all sim components and runs the tick loop. — méthodes : `__init__` 28, `start` 129, `stop` 164, `shutdown` 167, `run` 181, `_tick` 206, `stats` 216 |

## Relations

- **Utilise** : [sim/config/loader.py](config-loader.md), [sim/config/schema.py](config-schema.md), [sim/devices/base.py](devices-base.md), [sim/devices/climate.py](devices-climate.md), [sim/devices/entertainment.py](devices-entertainment.md), [sim/emitters/http_server.py](emitters-http-server.md), [sim/emitters/modbus_server.py](emitters-modbus-server.md), [sim/emitters/mqtt.py](emitters-mqtt.md), [sim/integration/bus_runner.py](integration-bus-runner.md)
- **Utilisé par** : [sim/cli.py](cli.md)
- **Testé par** : `tests/test_docker.py` → [tests de jabfy-simulation](tests.md)
