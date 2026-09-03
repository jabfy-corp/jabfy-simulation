# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

`jabfy-sim` is the external simulation lab for the JABFY ecosystem. It speaks **real protocols**
(MQTT in Zigbee2MQTT format) so `jabfy-bus`'s real adapters process messages exactly as they would
with physical hardware. jabfy-bus has no idea it is talking to a simulator.

Unlike `jabfy-bus/jabfy_bus/simulation/` (which bypasses adapters and injects messages directly
into the bus core), jabfy-sim exercises the full stack.

## Architecture

```
jabfy-sim (Python)
  Device Engine     — state machines (lighting, security, climate, entertainment)
  MQTTEmitter       — paho-mqtt: publishes zigbee2mqtt/<id> telemetry
                                 subscribes zigbee2mqtt/<id>/set commands
  ModbusServer      — pymodbus TCP server: climate registers on port 5020
  HTTPMockServer    — FastAPI: SmartTV API (port 8001) + NAS API (port 5000)
  BusRunner         — embeds jabfy-bus pipeline in-process:
    ┌ Zigbee2MQTTAdapter  → paho MQTT → Mosquitto
    │ HTTPPollingAdapter  → urllib GET /api/v2/state (SmartTV)
    │ ModbusAdapter       → pymodbus TCP client → ModbusServer
    └────────────────────► UniversalJsonBus
         ReflexEngine (YAML rules → command.requested)
         VerificationEngine (policy check)
         ExecutionLayer → "zigbee"       transport → paho MQTT
                       → "http_smarttv" transport → POST /api/v2/power
                       → "modbus_climate" transport → pymodbus HR write
         AuditLog (SHA-256 chain)
  ReflexEngine      — YAML-rule stub for jabfy-core (replaced in Phase 2)

External:
  Mosquitto         — real MQTT broker (Docker Compose)
```

### Multi-protocol command routing

ReflexRules can target any transport via the `protocol` field:

```yaml
reflex_rules:
  - name: motion_tv_on
    trigger:
      entity_id: "binary_sensor.salon_motion_occupancy"
      value: true
    command:
      action: turn_on
      target_entity_id: "switch.salon_tv_switch"
      target_domain: switch
      protocol: http_smarttv                  # ← Samsung API
      target: "http://localhost:8001/api/v2"  # ← base URL

  - name: thermostat_raise
    trigger:
      entity_id: "sensor.salon_temp_temperature"
      value: 15.0                             # exact match for now
    command:
      action: set_temperature
      target_entity_id: "climate.salon_thermostat"
      target_domain: climate
      protocol: modbus_climate
      target: "1"                             # Modbus unit_id
      params: {temperature: 21.0}
```

## Commands

```bash
# First-time setup (with jabfy-bus integration)
pip install -e ".[dev]"

# Run unit tests (no broker needed)
pytest

# Run the hardcoded motion→light demo (needs Mosquitto on localhost:1883)
jabfy-sim demo

# Run from config file
jabfy-sim run --config scenarios/sim.example.yaml

# Override broker address
jabfy-sim demo --broker 192.168.1.5:1883
jabfy-sim run --config sim.yaml --broker localhost:1884

# Docker Compose (Mosquitto + jabfy-sim, one command)
docker compose up

# Save audit log
jabfy-sim demo --audit audit.jsonl
```

## Package Layout

```
sim/
  devices/          # Device state machines (no network deps)
    base.py         # Device ABC: tick(), apply_command(), get_state()
    lighting.py     # OnOffLight, DimmerLight, RGBBulb
    security.py     # MotionSensor, DoorLock, SmokeSensor, AlarmSiren
    climate.py      # TemperatureSensor, Thermostat
    entertainment.py# SmartTV (power/volume/source/app — Samsung-style)
  config/           # YAML config loading (Pydantic models)
    schema.py       # SimConfig, DeviceConfig, ReflexRule
    loader.py       # load_config() → SimConfig, build_device()
  emitters/
    mqtt.py         # MQTTEmitter — device-side paho client (Zigbee2MQTT format)
    modbus_server.py# Modbus TCP server — climate devices as live registers
    http_server.py  # HTTP mock servers: SmartTV (Samsung API) + NAS (Synology DSM)
  integration/      # Requires jabfy-bus installed
    bus_runner.py   # BusRunner — jabfy-bus pipeline with real MQTT
    reflex.py       # ReflexEngine — rule-based command proposal stub
  runner.py         # SimRunner — orchestrates all components
  cli.py            # CLI entry point (jabfy-sim demo | run)
scenarios/
  sim.example.yaml  # Full example config (copy and customize)
```

## Modbus TCP Server

Climate devices (TemperatureSensor, Thermostat) are automatically served as Modbus
registers over TCP. One unit ID per device (unit 1 = first climate device, etc.).

**Register layout per unit:**

| Type | FC | Addr | Description |
|------|-----|------|-------------|
| Input Register | 4 | 0 | Temperature × 10 (e.g. 235 = 23.5°C) |
| Input Register | 4 | 1 | Humidity × 10 (e.g. 500 = 50.0%; 0 for thermostat) |
| Holding Register | 3/6 | 0 | Setpoint × 10 (thermostat only; writable) |
| Holding Register | 3/6 | 1 | Heating state (0 = idle, 1 = heating; read-only) |

The server listens on **port 5020** (localhost by default). Registers update live via
pymodbus SimDevice `action` callbacks — no polling needed. Writing HR 0 (setpoint)
updates the Thermostat device and is applied to the real device state.

## HTTP Mock Servers

SmartTV API (Samsung SmartThings-style) — **port 8001**:
```
GET  /api/v2/          → device info
GET  /api/v2/state     → full state JSON
POST /api/v2/power     → {"state": "on"|"off"}
POST /api/v2/volume    → {"volume": 0–100}
POST /api/v2/source    → {"source": "HDMI1"|"HDMI2"|"Netflix"|…}
POST /api/v2/mute      → {"mute": true|false}
```

NAS API (Synology DSM-style) — **port 5000**:
```
GET /webapi/entry.cgi?api=SYNO.API.Info        → API registry
GET /webapi/entry.cgi?api=SYNO.Info            → system info (hostname, model)
GET /webapi/entry.cgi?api=SYNO.Storage.Volume  → volume list (size, usage)
GET /webapi/entry.cgi?api=SYNO.FileStation.List → file listing
```

## Key Design Rules

- **Device state machines have zero network deps** — they can be tested without paho-mqtt or jabfy-bus.
- **MQTTEmitter and BusRunner use separate paho clients** — clean separation of device emitter vs. bus gateway.
- **ReflexEngine is temporary** — it is the stub for jabfy-core. When jabfy-core is connected (Phase 2), delete ReflexEngine and connect jabfy-core to the bus HTTP API exposed by BusRunner.
- **Protocol for zigbee commands**: `"protocol": "zigbee"` → jabfy-bus `to_mqtt` translator → publishes to `<topic>/set`.
- **`turn_on` risk = MEDIUM** — the default VerificationEngine policy requires an explicit `allow` policy for MEDIUM risk. `_DEFAULT_POLICIES` in `bus_runner.py` covers lights and climate for the sim.

## Adding New Device Types

1. Implement `Device` subclass in `sim/devices/`.
2. Register it in `sim/devices/__init__.py → DEVICE_TYPES`.
3. Add unit tests in the appropriate `tests/test_*.py` file.
4. Add to `scenarios/sim.example.yaml` as a usage example.
5. If the device needs its own server protocol, add a module in `sim/emitters/` and wire it in `SimRunner`.

## CI

`pytest` runs on every PR to `main`. PRs require `Closes #<issue-number>`. Branch prefix: `sim-`.

## Contribution

Branch: `sim-<issue-number>-<short-description>`
Every PR must include `Closes #<issue-number>`. See `CONTRIBUTING.md`.
