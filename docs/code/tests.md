# jabfy-simulation — tests

Total : **173 tests** répartis dans 13 fichiers (comptés par `def test_`).

| fichier | tests | code importé |
|---|---|---|
| `tests/e2e/test_ai_sequence_e2e.py` | 1 | — |
| `tests/test_bus_http_modbus.py` | 19 | jabfy_bus/adapters/http/adapter.py (jabfy-bus), jabfy_bus/adapters/modbus/adapter.py (jabfy-bus), jabfy_bus/adapters/modbus/registers.py (jabfy-bus), jabfy_bus/core/bus.py (jabfy-bus), jabfy_bus/core/message.py (jabfy-bus), jabfy_bus/core/types.py (jabfy-bus), [sim/config/schema.py](config-schema.md), [sim/devices/climate.py](devices-climate.md), [sim/devices/entertainment.py](devices-entertainment.md), [sim/emitters/http_server.py](emitters-http-server.md), [sim/integration/bus_runner.py](integration-bus-runner.md), [sim/integration/reflex.py](integration-reflex.md) |
| `tests/test_config.py` | 10 | [sim/config/loader.py](config-loader.md), [sim/config/schema.py](config-schema.md), [sim/devices/lighting.py](devices-lighting.md), [sim/devices/security.py](devices-security.md) |
| `tests/test_dashboard.py` | 12 | jabfy_bus/core/bus.py (jabfy-bus), jabfy_bus/core/message.py (jabfy-bus), [sim/cli.py](cli.md), [sim/config/schema.py](config-schema.md), [sim/dashboard/app.py](dashboard-app.md), [sim/devices/lighting.py](devices-lighting.md), [sim/devices/security.py](devices-security.md) |
| `tests/test_devices.py` | 34 | [sim/devices/climate.py](devices-climate.md), [sim/devices/lighting.py](devices-lighting.md), [sim/devices/security.py](devices-security.md) |
| `tests/test_docker.py` | 6 | [sim/config/schema.py](config-schema.md), [sim/devices/entertainment.py](devices-entertainment.md), [sim/runner.py](runner.md) |
| `tests/test_entertainment.py` | 20 | [sim/devices/entertainment.py](devices-entertainment.md) |
| `tests/test_home.py` | 15 | [sim/config/loader.py](config-loader.md), [sim/config/schema.py](config-schema.md), [sim/dashboard/defaults.py](dashboard-defaults.md), [sim/home/catalog.py](home-catalog.md) |
| `tests/test_home_api.py` | 13 | src/jabfy_guard/__init__.py (jabfy-guard), [sim/config/loader.py](config-loader.md), [sim/config/schema.py](config-schema.md), [sim/dashboard/app.py](dashboard-app.md), [sim/emitters/mqtt.py](emitters-mqtt.md), [sim/integration/bus_runner.py](integration-bus-runner.md) |
| `tests/test_http_server.py` | 18 | [sim/devices/entertainment.py](devices-entertainment.md), [sim/emitters/http_server.py](emitters-http-server.md) |
| `tests/test_modbus_server.py` | 14 | [sim/devices/climate.py](devices-climate.md), [sim/devices/lighting.py](devices-lighting.md), [sim/emitters/modbus_server.py](emitters-modbus-server.md) |
| `tests/test_reflex.py` | 7 | jabfy_bus/core/bus.py (jabfy-bus), jabfy_bus/core/message.py (jabfy-bus), jabfy_bus/core/types.py (jabfy-bus), [sim/config/schema.py](config-schema.md), [sim/integration/reflex.py](integration-reflex.md) |
| `tests/test_stack_integration.py` | 4 | app/core/openai_client.py (jabfy-core), app/main.py (jabfy-core), app/simulation/client.py (jabfy-core) |

## À retenir

- `e2e/test_ai_sequence_e2e.py` est sauté si `JABFY_E2E_URL` n'est pas défini : il demande la stack réelle.
- `test_stack_integration.py` relie émetteur MQTT et BusRunner.
