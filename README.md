# jabfy-sim

External simulation lab for the JABFY ecosystem. Speaks real MQTT in Zigbee2MQTT format
so `jabfy-bus`'s real adapters see it as physical hardware.

## Quick start

```bash
# 1. Install
pip install -e ".[dev]"

# 2. Start Mosquitto
docker compose up mosquitto -d

# 3. Run the demo (motion sensor → lamp on, full pipeline)
jabfy-sim demo
```

Or run everything with one command:

```bash
docker compose up
```

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

**Reflex Engine** (`sim/integration/reflex.py`) is a temporary stub that converts
bus events into `command.requested` proposals. It will be removed in Phase 2 when
`jabfy-core` is connected and provides the actual AI reasoning.

See `CLAUDE.md` for full architecture and development guide.
