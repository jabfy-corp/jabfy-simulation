# `sim/integration/modbus_client.py`

> **Rôle** — Lecteur/écrivain Modbus TCP (pymodbus) branché sur l'adapter Modbus du bus.

Dépôt : [jabfy-simulation](README.md) · 124 lignes · statut : **actif**

Docstring du module : *Pymodbus synchronous client — implements the Reader / ModbusWriter*

## À retenir

- `ModbusTcpReader` l.19, `ModbusTcpWriter` l.75.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 19 | classe `ModbusTcpReader` | Callable reader for jabfy-bus ModbusAdapter. — méthodes : `__init__` 25, `_get_client` 33, `close` 45, `__call__` 52 |
| 75 | classe `ModbusTcpWriter` | Modbus write transport for jabfy-bus ModbusAdapter. — méthodes : `__init__` 82, `_get_client` 88, `close` 99, `write` 106 |

## Relations

- **Utilise** : jabfy_bus/adapters/modbus/registers.py (jabfy-bus)
- **Utilisé par** : [sim/integration/bus_runner.py](integration-bus-runner.md)
