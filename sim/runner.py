"""SimRunner — orchestrates device ticks + MQTT emitter + bus pipeline.

The tick loop runs in the main thread. paho event loops for both the
MQTTEmitter and BusRunner run in background threads (via loop_start()).
The Modbus server and HTTP mock server each run in their own daemon threads.
"""

from __future__ import annotations

import logging
import signal
import time
from typing import Any

from sim.config.schema import SimConfig
from sim.config.loader import build_devices
from sim.devices.base import Device
from sim.emitters.mqtt import MQTTEmitter

logger = logging.getLogger(__name__)
# Device servers and their gateway live in this process/container, not on the broker.
DEVICE_SERVER_HOST = "127.0.0.1"


class SimRunner:
    """Coordinates all sim components and runs the tick loop."""

    def __init__(
        self,
        config: SimConfig,
        devices: list[Device] | None = None,
    ) -> None:
        self.config = config
        self.devices: list[Device] = devices or build_devices(config)
        self.emitter = MQTTEmitter(config.broker, self.devices)

        # Bus runner is optional — requires jabfy-bus installed
        self.bus_runner = None
        try:
            from sim.integration.bus_runner import (  # noqa: PLC0415
                BusRunner, ClimateModbusUnit, ModbusClimateConfig, SmartTVHttpConfig,
            )
            from sim.devices.entertainment import SmartTV          # noqa: PLC0415
            from sim.devices.climate import TemperatureSensor, Thermostat  # noqa: PLC0415

            # Build HTTP config for each SmartTV device
            http_cfgs: list = []
            tv_port = getattr(config, "tv_api_port", 8001)
            for dev in self.devices:
                if isinstance(dev, SmartTV):
                    http_cfgs.append(SmartTVHttpConfig(
                        entity_id=f"switch.{dev.id}",
                        location=dev.location,
                        base_url=f"http://{DEVICE_SERVER_HOST}:{tv_port}/api/v2",
                    ))

            # Build Modbus config for climate devices
            # Unit IDs mirror the ModbusServer assignment (index order)
            climate_types = (TemperatureSensor, Thermostat)
            modbus_units: list = []
            unit_id = 1
            for dev in self.devices:
                if isinstance(dev, climate_types):
                    modbus_units.append(ClimateModbusUnit(
                        unit_id=unit_id,
                        device_id=dev.id,
                        location=dev.location,
                        has_humidity=isinstance(dev, TemperatureSensor),
                        has_setpoint=isinstance(dev, Thermostat),
                    ))
                    unit_id += 1

            modbus_cfg = None
            if modbus_units:
                modbus_port = getattr(config, "modbus_port", 5020)
                modbus_cfg = ModbusClimateConfig(
                    host=DEVICE_SERVER_HOST,
                    port=modbus_port,
                    units=modbus_units,
                )

            self.bus_runner = BusRunner(
                broker=config.broker,
                reflex_rules=config.reflex_rules,
                audit_path=config.audit_path,
                http_configs=http_cfgs or None,
                modbus_config=modbus_cfg,
            )
        except ImportError:
            logger.warning(
                "jabfy-bus not installed — running emitter-only mode. "
                "Install with: pip install -e '.[bus]'"
            )

        # Modbus TCP server — optional (requires pymodbus)
        self.modbus_server = None
        try:
            from sim.emitters.modbus_server import ModbusServer  # noqa: PLC0415
            self.modbus_server = ModbusServer(
                devices=self.devices,
                host=DEVICE_SERVER_HOST,
                port=getattr(config, "modbus_port", 5020),
            )
        except ImportError:
            logger.debug("pymodbus not installed — Modbus TCP server disabled")

        # HTTP mock server — optional (requires fastapi + uvicorn)
        self.http_server = None
        try:
            from sim.emitters.http_server import HTTPMockServer  # noqa: PLC0415
            from sim.devices.entertainment import SmartTV  # noqa: PLC0415
            tv_devices = [d for d in self.devices if isinstance(d, SmartTV)]
            tv = tv_devices[0] if tv_devices else None
            self.http_server = HTTPMockServer(
                tv_device=tv,
                host=DEVICE_SERVER_HOST,
                tv_port=getattr(config, "tv_api_port", 8001),
                nas_port=getattr(config, "nas_api_port", 5000),
            )
        except ImportError:
            logger.debug("fastapi/uvicorn not installed — HTTP mock servers disabled")

        self._running = False
        self._tick_count = 0

    # ------------------------------------------------------------------
    # Lifecycle

    def start(self) -> None:
        """Connect to broker and start background threads."""
        broker = self.config.broker
        try:
            self.emitter.connect()
        except ConnectionRefusedError:
            raise ConnectionRefusedError(
                f"Cannot connect to MQTT broker at {broker.host}:{broker.port}. "
                "Start Mosquitto first: docker compose up mosquitto -d"
            ) from None
        # Start device-side servers before the gateway begins polling them.
        if self.modbus_server:
            self.modbus_server.start()

        if self.http_server:
            self.http_server.start()
            # Give uvicorn a moment to bind
            time.sleep(0.5)

        if self.bus_runner:
            try:
                self.bus_runner.connect()
            except ConnectionRefusedError:
                raise ConnectionRefusedError(
                    f"BusRunner cannot connect to MQTT broker at {broker.host}:{broker.port}."
                ) from None
            # Let the gateway subscribe before device telemetry begins.
            time.sleep(0.3)

        logger.info(
            "SimRunner started — %d device(s), tick_interval=%dms",
            len(self.devices),
            self.config.tick_interval_ms,
        )

    def stop(self) -> None:
        self._running = False

    def shutdown(self) -> None:
        """Disconnect from broker cleanly."""
        self.emitter.disconnect()
        if self.bus_runner:
            self.bus_runner.disconnect()
        if self.modbus_server:
            self.modbus_server.stop()
        if self.http_server:
            self.http_server.stop()
        logger.info("SimRunner stopped — %d ticks completed", self._tick_count)

    # ------------------------------------------------------------------
    # Tick loop

    def run(self) -> None:
        """Block and run the tick loop until stopped or SIGINT/SIGTERM."""
        self._running = True

        # Graceful shutdown on Ctrl-C
        def _handle_signal(sig: int, frame: Any) -> None:
            logger.info("signal %d received — stopping", sig)
            self.stop()

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

        self.start()

        interval_s = self.config.tick_interval_ms / 1000.0
        try:
            while self._running:
                t0 = time.monotonic()
                self._tick(self.config.tick_interval_ms)
                elapsed = time.monotonic() - t0
                sleep_s = max(0.0, interval_s - elapsed)
                time.sleep(sleep_s)
        finally:
            self.shutdown()

    def _tick(self, elapsed_ms: int) -> None:
        self._tick_count += 1
        for device in self.devices:
            should_emit = device.tick(elapsed_ms)
            if should_emit:
                self.emitter.emit(device)

    # ------------------------------------------------------------------
    # Introspection

    def stats(self) -> dict[str, Any]:
        stats: dict[str, Any] = {
            "ticks": self._tick_count,
            "devices": len(self.devices),
        }
        if self.bus_runner:
            stats["bus"] = self.bus_runner.stats()
        if self.modbus_server:
            stats["modbus"] = {
                "port": self.modbus_server.port_in_use,
                "units": self.modbus_server.unit_map(),
            }
        if self.http_server:
            stats["http"] = {
                "tv_port": self.http_server.tv_port,
                "nas_port": self.http_server.nas_port,
            }
        return stats
