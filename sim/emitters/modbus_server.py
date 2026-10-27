"""Modbus TCP server — serves climate device registers over real Modbus TCP.

Register layout (one Modbus unit per climate device):

  Input Registers (FC 4, read-only for clients):
    addr 0  — temperature × 10   (int,  e.g. 235 = 23.5 °C)
    addr 1  — humidity × 10      (int,  e.g. 500 = 50.0 %; 0 for thermostat)

  Holding Registers (FC 3 / 6 / 16, readable+writable):
    addr 0  — setpoint × 10      (int,  thermostat only; 0 for sensor)
    addr 1  — heating_state       (0 = idle, 1 = heating)

The server runs in a background asyncio event loop (daemon thread).
Register values are refreshed live via a SimDevice ``action`` callback —
no periodic sync needed.  Write-back (setpoint change from a Modbus
client) is applied to the device in the same callback.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from functools import partial
from typing import TYPE_CHECKING

from pymodbus.server import ModbusTcpServer
from pymodbus.simulator.simdata import DataType, SimData
from pymodbus.simulator.simdevice import SimDevice

from sim.devices.base import Device

if TYPE_CHECKING:
    from sim.devices.climate import TemperatureSensor, Thermostat

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Register addresses
# ──────────────────────────────────────────────────────────────────────────────
_IR_TEMP = 0    # Input reg 0 — temperature × 10
_IR_HUM  = 1    # Input reg 1 — humidity × 10
_HR_SP   = 0    # Holding reg 0 — setpoint × 10
_HR_HEAT = 1    # Holding reg 1 — heating_state (0/1)


# ──────────────────────────────────────────────────────────────────────────────
# Action callback factory
# ──────────────────────────────────────────────────────────────────────────────

def _make_action(device: Device):
    """Return an async action callback for a single climate device.

    The callback is called by pymodbus on every register access:
    - READ  (set_values is None)  → update current_registers from device state
    - WRITE (set_values is list)  → apply the written values to the device
    """

    async def _action(
        function_code: int,
        start_address: int,
        address: int,
        count: int,
        current_registers: list,
        set_values: list | None,
    ):
        state = device.get_state()

        if set_values is None:
            # ── READ ──────────────────────────────────────────────────────────
            if function_code == 4:  # Input Registers — temperature / humidity
                temp_raw = int(round(
                    state.get("local_temperature", state.get("temperature", 0)) * 10
                ))
                hum_raw = int(round(state.get("humidity", 0) * 10))
                ir_map = [max(0, temp_raw), max(0, hum_raw)]
                for i in range(count):
                    reg_addr = start_address + i
                    if 0 <= i < len(current_registers) and 0 <= reg_addr < len(ir_map):
                        current_registers[i] = ir_map[reg_addr]

            elif function_code == 3:  # Holding Registers — setpoint / heating
                sp_raw = int(round(state.get("occupied_heating_setpoint", 0) * 10))
                heat = 1 if state.get("running_state") == "heat" else 0
                hr_map = [sp_raw, heat]
                for i in range(count):
                    reg_addr = start_address + i
                    if 0 <= i < len(current_registers) and 0 <= reg_addr < len(hr_map):
                        current_registers[i] = hr_map[reg_addr]

        else:
            # ── WRITE (holding registers only) ────────────────────────────────
            if function_code in (6, 16):  # Write Single / Multiple Holding Regs
                for i, val in enumerate(set_values):
                    reg_addr = start_address + i
                    if reg_addr == _HR_SP:
                        new_sp = val / 10.0
                        result = device.apply_command(
                            "set_temperature", {"temperature": new_sp}
                        )
                        if result.success:
                            logger.info(
                                "Modbus write → %s setpoint %.1f°C",
                                device.id,
                                new_sp,
                            )
                        else:
                            logger.warning(
                                "Modbus write → %s set_temperature failed: %s",
                                device.id,
                                result.reason,
                            )
        return None  # success

    return _action


# ──────────────────────────────────────────────────────────────────────────────
# ModbusServer
# ──────────────────────────────────────────────────────────────────────────────

class ModbusServer:
    """Modbus TCP server that exposes climate device state as live registers.

    Each climate device (TemperatureSensor or Thermostat) gets a dedicated
    Modbus unit ID (1, 2, 3 …).  Devices are mapped in the order they appear
    in ``devices`` — only climate devices consume unit IDs.

    Usage::

        server = ModbusServer(devices, host="localhost", port=5020)
        server.start()   # non-blocking; background thread
        # … run simulation …
        server.stop()    # graceful shutdown
    """

    def __init__(
        self,
        devices: list[Device],
        host: str = "localhost",
        port: int = 5020,
    ) -> None:
        self.host = host
        self.port = port

        # Only climate devices get Modbus units (lazy import to avoid hard dep)
        try:
            from sim.devices.climate import TemperatureSensor, Thermostat  # noqa: PLC0415
            climate_types = (TemperatureSensor, Thermostat)
        except ImportError:
            climate_types = ()  # type: ignore[assignment]

        self._units: dict[int, Device] = {
            idx + 1: dev
            for idx, dev in enumerate(dev for dev in devices if isinstance(dev, climate_types))
        }

        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._server: ModbusTcpServer | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the server in a background daemon thread."""
        if not self._units:
            logger.info("No climate devices — Modbus server not started")
            return

        sim_devices = self._build_sim_devices()
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            args=(sim_devices,),
            daemon=True,
            name="modbus-server",
        )
        self._thread.start()
        logger.info(
            "Modbus TCP server starting on %s:%d — %d unit(s): %s",
            self.host,
            self.port,
            len(self._units),
            {uid: dev.id for uid, dev in self._units.items()},
        )

    def stop(self) -> None:
        """Gracefully shut down the server."""
        if self._server and self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(
                self._loop.create_task, self._server.shutdown()
            )
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Modbus TCP server stopped")

    # ── Introspection ─────────────────────────────────────────────────────────

    def unit_map(self) -> dict[int, str]:
        """Return {unit_id: device_id} mapping."""
        return {uid: dev.id for uid, dev in self._units.items()}

    @property
    def port_in_use(self) -> int:
        return self.port

    # ── Internals ─────────────────────────────────────────────────────────────

    def _build_sim_devices(self) -> list[SimDevice]:
        """Build one SimDevice per climate device."""
        sim_devices = []
        for unit_id, device in self._units.items():
            state = device.get_state()
            temp_raw = int(round(
                state.get("local_temperature", state.get("temperature", 0)) * 10
            ))
            hum_raw = int(round(state.get("humidity", 0) * 10))
            sp_raw  = int(round(state.get("occupied_heating_setpoint", 0) * 10))
            heat    = 1 if state.get("running_state") == "heat" else 0

            coils = [SimData(address=0, count=1, values=False, datatype=DataType.BITS)]
            di    = [SimData(address=0, count=1, values=False, datatype=DataType.BITS)]
            hr    = [
                SimData(address=0, values=max(0, sp_raw),   datatype=DataType.REGISTERS),
                SimData(address=1, values=heat,             datatype=DataType.REGISTERS),
            ]
            ir    = [
                SimData(address=0, values=max(0, temp_raw), datatype=DataType.REGISTERS),
                SimData(address=1, values=max(0, hum_raw),  datatype=DataType.REGISTERS),
            ]
            sim_dev = SimDevice(
                id=unit_id,
                simdata=(coils, di, hr, ir),
                action=_make_action(device),
            )
            sim_devices.append(sim_dev)
        return sim_devices

    def _run_loop(self, sim_devices: list[SimDevice]) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve(sim_devices))
        except Exception as exc:  # noqa: BLE001
            logger.error("Modbus server loop exited: %s", exc)
        finally:
            self._loop.close()

    async def _serve(self, sim_devices: list[SimDevice]) -> None:
        self._server = ModbusTcpServer(
            context=sim_devices,
            address=(self.host, self.port),
        )
        await self._server.serve_forever()
