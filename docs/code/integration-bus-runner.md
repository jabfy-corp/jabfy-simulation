# `sim/integration/bus_runner.py`

> **Rôle** — Le pipeline jabfy-bus **propre au simulateur** : bus, audit fichier, registre, guard, exécution, réflexes, transports.

Dépôt : [jabfy-simulation](README.md) · 535 lignes · statut : **actif**

Docstring du module : *BusRunner — embeds jabfy-bus pipeline in-process with real MQTT, HTTP, and Modbus.*

## À retenir

- `BusRunner` l.213 ; `ExecutionLayer(approval_validator=consume_approval)` l.254-255.
- `ReflexEngine` l.259 ; transports zigbee/mqtt l.273-274, HTTP SmartTV, Modbus climat.
- Abonné à `zigbee2mqtt/#` comme Core : deux bus écoutent le même broker.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 69 | classe `SmartTVHttpConfig` | Config for HTTP polling of one SmartTV device. |
| 78 | classe `ClimateModbusUnit` | One climate device mapped to a Modbus unit. |
| 88 | classe `ModbusClimateConfig` | Config for Modbus polling of climate devices. |
| 100 | `_HTTP_STATE` | constante |
| 106 | `_to_http_smarttv()` | Translate a normalised command to a Samsung SmartThings-style HTTP request. |
| 146 | `_to_modbus_climate()` | Translate a climate command to a Modbus write spec. |
| 177 | `_DEFAULT_POLICIES` | constante |
| 213 | classe `BusRunner` | Wires the full jabfy-bus pipeline with MQTT, HTTP, and Modbus. — méthodes : `__init__` 220, `connect` 310, `disconnect` 340, `_http_poll_loop` 351, `_modbus_poll_loop` 360, `_build_http_adapter` 372, `_build_modbus_adapter` 398, `_mqtt_transport` 452, `_http_smarttv_transport` 458, `_modbus_climate_transport` 479, `_on_connect` 499, `_on_message` 507, `_connected` 516, `_connected` 520, `stats` 523 |

## Relations

- **Utilise** : jabfy_bus/adapters/http/adapter.py (jabfy-bus), jabfy_bus/adapters/modbus/adapter.py (jabfy-bus), jabfy_bus/adapters/modbus/registers.py (jabfy-bus), jabfy_bus/adapters/zigbee2mqtt/adapter.py (jabfy-bus), jabfy_bus/audit/log.py (jabfy-bus), jabfy_bus/core/bus.py (jabfy-bus), jabfy_bus/core/registry.py (jabfy-bus), jabfy_bus/core/types.py (jabfy-bus), jabfy_bus/execution/executor.py (jabfy-bus), jabfy_bus/execution/translators.py (jabfy-bus), jabfy_bus/verification/engine.py (jabfy-bus), jabfy_bus/verification/policies.py (jabfy-bus), jabfy_bus/verification/risk.py (jabfy-bus), [sim/config/schema.py](config-schema.md), [sim/integration/modbus_client.py](integration-modbus-client.md), [sim/integration/reflex.py](integration-reflex.md)
- **Utilisé par** : [sim/runner.py](runner.md)
- **Testé par** : `tests/test_bus_http_modbus.py`, `tests/test_home_api.py` → [tests de jabfy-simulation](tests.md)
