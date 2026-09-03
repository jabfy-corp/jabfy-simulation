"""Pymodbus synchronous client — implements the Reader / ModbusWriter
protocols expected by jabfy-bus's ModbusAdapter.

Both classes are thin wrappers around a shared pymodbus ModbusTcpClient.
They handle connect-on-demand and transparent reconnect so the polling
thread never crashes on a transient Modbus server restart.
"""

from __future__ import annotations

import logging
import threading

from jabfy_bus.adapters.modbus.registers import RegisterType

logger = logging.getLogger(__name__)


class ModbusTcpReader:
    """Callable reader for jabfy-bus ModbusAdapter.

    Signature: reader(unit_id, register_type, address) -> int | bool
    """

    def __init__(self, host: str, port: int = 5020) -> None:
        self.host = host
        self.port = port
        self._lock = threading.Lock()
        self._client = None

    # -- connection -----------------------------------------------------------

    def _get_client(self):
        """Return a connected pymodbus client, connecting if needed."""
        from pymodbus.client import ModbusTcpClient  # noqa: PLC0415
        if self._client is None or not self._client.connected:
            client = ModbusTcpClient(self.host, port=self.port, timeout=2)
            if not client.connect():
                raise ConnectionError(
                    f"Cannot connect to Modbus server at {self.host}:{self.port}"
                )
            self._client = client
        return self._client

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    # -- Reader protocol ------------------------------------------------------

    def __call__(self, unit_id: int, register_type: RegisterType, address: int) -> int | bool:
        with self._lock:
            client = self._get_client()
            match register_type:
                case RegisterType.INPUT_REGISTER:
                    resp = client.read_input_registers(address, count=1, device_id=unit_id)
                case RegisterType.HOLDING_REGISTER:
                    resp = client.read_holding_registers(address, count=1, device_id=unit_id)
                case RegisterType.COIL:
                    resp = client.read_coils(address, count=1, device_id=unit_id)
                case RegisterType.DISCRETE_INPUT:
                    resp = client.read_discrete_inputs(address, count=1, device_id=unit_id)
                case _:
                    raise ValueError(f"Unsupported register type: {register_type}")
            if resp.isError():
                raise IOError(
                    f"Modbus read error: unit={unit_id} {register_type}@{address} → {resp}"
                )
            if register_type in (RegisterType.COIL, RegisterType.DISCRETE_INPUT):
                return bool(resp.bits[0])
            return int(resp.registers[0])


class ModbusTcpWriter:
    """Modbus write transport for jabfy-bus ModbusAdapter.

    Implements the ModbusWriter protocol:
        write(unit_id, register_type, address, value) -> None
    """

    def __init__(self, host: str, port: int = 5020) -> None:
        self.host = host
        self.port = port
        self._lock = threading.Lock()
        self._client = None

    def _get_client(self):
        from pymodbus.client import ModbusTcpClient  # noqa: PLC0415
        if self._client is None or not self._client.connected:
            client = ModbusTcpClient(self.host, port=self.port, timeout=2)
            if not client.connect():
                raise ConnectionError(
                    f"Cannot connect to Modbus server at {self.host}:{self.port}"
                )
            self._client = client
        return self._client

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    # -- ModbusWriter protocol ------------------------------------------------

    def write(self, unit_id: int, register_type: RegisterType, address: int, value: int) -> None:
        with self._lock:
            client = self._get_client()
            match register_type:
                case RegisterType.HOLDING_REGISTER:
                    resp = client.write_register(address, value, device_id=unit_id)
                case RegisterType.COIL:
                    resp = client.write_coil(address, bool(value), device_id=unit_id)
                case _:
                    raise ValueError(
                        f"Cannot write to {register_type.value} (not writable)"
                    )
            if resp.isError():
                raise IOError(
                    f"Modbus write error: unit={unit_id} {register_type}@{address}={value} → {resp}"
                )
            logger.debug(
                "Modbus write OK: unit=%d %s@%d = %d", unit_id, register_type.value, address, value
            )
