"""CLI for jabfy-sim.

    jabfy-sim demo                            # hardcoded motion→light scenario
    jabfy-sim run --config sim.yaml           # run from YAML config
    jabfy-sim run --config sim.yaml --broker localhost:1883
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path


def cmd_demo(args: argparse.Namespace) -> int:
    """Hardcoded demo: motion sensor triggers lamp turn-on through the full pipeline."""
    from sim.config.schema import BrokerConfig, DeviceConfig, ReflexCommand, ReflexRule, ReflexTrigger, SimConfig
    from sim.devices.security import MotionSensor
    from sim.runner import SimRunner

    host, port = _parse_broker(args.broker)

    config = SimConfig(
        broker=BrokerConfig(host=host, port=port),
        tick_interval_ms=200,
        devices=[
            DeviceConfig(
                id="salon_motion",
                type="motion_sensor",
                location="salon",
                topic_prefix="zigbee2mqtt/salon_motion",
                telemetry_interval_ms=200,
            ),
            DeviceConfig(
                id="salon_lamp",
                type="dimmer_light",
                location="salon",
                topic_prefix="zigbee2mqtt/salon_lamp",
                telemetry_interval_ms=1000,
            ),
        ],
        reflex_rules=[
            ReflexRule(
                name="motion_to_light",
                trigger=ReflexTrigger(
                    entity_id="binary_sensor.salon_motion_occupancy",
                    value=True,
                ),
                command=ReflexCommand(
                    action="turn_on",
                    target_entity_id="switch.salon_lamp_state",
                    target_domain="switch",
                    target_mqtt_topic="zigbee2mqtt/salon_lamp",
                    target_location="salon",
                ),
            )
        ],
        audit_path=args.audit or None,
    )

    runner = SimRunner(config)
    runner.start()

    # Find the motion sensor and lamp devices
    motion = next(d for d in runner.devices if d.id == "salon_motion")
    lamp = next(d for d in runner.devices if d.id == "salon_lamp")

    print("\n── jabfy-sim demo ─────────────────────────────────────────")
    print(f"  broker    : {host}:{port}")
    print(f"  devices   : {[d.id for d in runner.devices]}")
    print(f"  pipeline  : {'jabfy-bus embedded' if runner.bus_runner else 'emitter-only (no jabfy-bus)'}")
    print("────────────────────────────────────────────────────────────\n")

    steps = args.steps
    for step in range(steps):
        # Trigger motion at step 3
        if step == 3:
            print(f"  [step {step:02d}] 🚶 motion detected in salon!")
            motion.trigger_motion(duration_ms=2000)

        runner._tick(config.tick_interval_ms)
        time.sleep(config.tick_interval_ms / 1000.0)

        if step in (3, 4, 5, steps - 1):
            lamp_state = lamp.get_state()
            print(
                f"  [step {step:02d}] lamp={lamp_state.get('state', '?')} "
                f"brightness={lamp_state.get('brightness', '?')}"
            )

    time.sleep(0.5)  # let MQTT callbacks settle

    print("\n── results ─────────────────────────────────────────────────")
    stats = runner.stats()
    print(f"  ticks     : {stats['ticks']}")
    if runner.bus_runner:
        b = stats["bus"]
        print(f"  proposals : {b['proposals']}")
        print(f"  decisions : {b['decisions']}")
        print(f"  executed  : {b['executed']}")
        print(f"  audit     : {'✅ valid' if b['audit_valid'] else '❌ broken'}")
    print(f"  lamp      : {lamp.get_state()}")
    success = lamp.get_state().get("state") == "ON"
    print(f"\n{'✅ PASS — lamp turned on via full pipeline' if success else '❌ FAIL — lamp did not turn on'}\n")

    runner.shutdown()
    return 0 if success else 1


def cmd_run(args: argparse.Namespace) -> int:
    """Run jabfy-sim from a YAML config file."""
    from sim.config.loader import load_config
    from sim.runner import SimRunner

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"error: config file not found: {config_path}", file=sys.stderr)
        return 1

    config = load_config(config_path)

    # Override broker from CLI if specified
    if args.broker:
        host, port = _parse_broker(args.broker)
        config.broker.host = host
        config.broker.port = port

    runner = SimRunner(config)
    runner.run()  # blocks until SIGINT/SIGTERM
    return 0


def _parse_broker(broker_str: str) -> tuple[str, int]:
    """Parse 'host:port' or 'host' string."""
    if ":" in broker_str:
        host, port_str = broker_str.rsplit(":", 1)
        return host, int(port_str)
    return broker_str, 1883


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jabfy-sim",
        description="JABFY Simulation Lab — real-protocol smart home emulator",
    )
    parser.add_argument("--version", action="version", version="jabfy-sim 0.1.0")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="logging verbosity (default: INFO)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # jabfy-sim demo
    demo = sub.add_parser("demo", help="run the hardcoded motion→light pipeline demo")
    demo.add_argument("--broker", default="localhost:1883", metavar="HOST[:PORT]")
    demo.add_argument("--steps", type=int, default=15, help="number of simulation steps")
    demo.add_argument("--audit", default=None, metavar="FILE", help="write audit log to JSONL file")
    demo.set_defaults(func=cmd_demo)

    # jabfy-sim run
    run = sub.add_parser("run", help="run from a YAML config file")
    run.add_argument("--config", required=True, metavar="FILE")
    run.add_argument("--broker", default=None, metavar="HOST[:PORT]", help="override broker address")
    run.set_defaults(func=cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    )
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
