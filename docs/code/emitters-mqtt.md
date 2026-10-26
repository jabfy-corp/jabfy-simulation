# `sim/emitters/mqtt.py`

> **Rôle** — Émetteur MQTT : publie l'état des appareils et applique les commandes reçues sur `/set`.

Dépôt : [jabfy-simulation](README.md) · 173 lignes · statut : **actif**

Docstring du module : *MQTT emitter — publishes device telemetry and receives commands.*

## À retenir

- `_on_connect` l.80 s'abonne aux `/set` en qos 1 ; `_on_message` l.97 → `apply_command` → ré-émission de l'état.
- C'est ici que la lampe « s'allume » quand Core publie.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 27 | classe `MQTTEmitter` | Manages the device ↔ MQTT broker connection. — méthodes : `__init__` 34, `connect` 53, `disconnect` 57, `emit` 64, `emit_all` 72, `_on_connect` 80, `_on_message` 97 |
| 135 | `_payload_to_action()` | Translate a Zigbee2MQTT /set payload to (action, params). |

## Relations

- **Utilise** : [sim/config/schema.py](config-schema.md), [sim/devices/base.py](devices-base.md)
- **Utilisé par** : [sim/runner.py](runner.md)
- **Testé par** : `tests/test_home_api.py` → [tests de jabfy-simulation](tests.md)
