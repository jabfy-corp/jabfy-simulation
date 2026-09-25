"""One command path for manual controls and accepted AI proposals.

HTTP clients supply logical device IDs and validated parameters, never transport
addresses, trust levels, policy names or pre-approved bus messages.
"""

from typing import Any

from fastapi import HTTPException

from sim.home.catalog import device_capabilities, validate_command


def entity_id(device) -> str:
    domain = device_capabilities(device.device_type)["domain"]
    wire_id = device.telemetry_topic.rsplit("/", 1)[-1]
    suffix = "setpoint" if domain == "climate" else "state"
    return f"{domain}.{wire_id}_{suffix}"


def install_home_policies(runner) -> None:
    """Explicit policies limited to the virtual appliances in this home.

They are added only for the house editor's generated simulation namespace.
Legacy YAML runs retain their original policies. Real hardware is not registered
through this editor or addressable through its command endpoint.
"""
    from jabfy_bus.core.types import RiskLevel, TrustLevel
    from jabfy_bus.verification.policies import Policy

    installed = {policy.name for policy in runner.bus_runner.verification.policies}
    for device in runner.devices:
        if not device.telemetry_topic.startswith("zigbee2mqtt/sim_"):
            continue
        capabilities = device_capabilities(device.device_type)
        actions = {item["action"] for item in capabilities["actions"]}
        if actions and f"sim_home_{device.id}" not in installed:
            runner.bus_runner.verification.policies.append(Policy(
                name=f"sim_home_{device.id}", effect="allow", max_risk=RiskLevel.HIGH,
                entities={entity_id(device)}, domains={capabilities["domain"]},
                actions=actions, min_trust=TrustLevel.INTERNAL,
            ))


def execute_command(runner, device_id: str, action: str, params: dict[str, Any]) -> dict:
    from jabfy_bus.core.message import Entity, new_message
    from jabfy_bus.core.types import TrustLevel

    device = next((device for device in runner.devices if device.id == device_id), None)
    if device is None:
        raise HTTPException(404, "Appareil introuvable.")
    try:
        params = validate_command(device.device_type, action, params)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not runner.bus_runner:
        raise HTTPException(409, "Le bus de vérification doit être connecté pour piloter un appareil.")

    capabilities = device_capabilities(device.device_type)
    request = new_message(
        "command.requested", adapter="simulation_dashboard", protocol="internal",
        trust_level=TrustLevel.INTERNAL,
        entity=Entity(id=entity_id(device), domain=capabilities["domain"], location=device.location),
        command={"action": action, "params": params,
                 "protocol": "zigbee", "target": device.telemetry_topic},
        raw={"origin": "home_controls", "device_id": device.id},
    )
    outcomes = []

    def collect(message):
        if message.correlation_id == request.message_id:
            outcomes.append(message)

    bus = runner.bus_runner.bus
    subscription = bus.subscribe("command.*", collect, name="home_command_result")
    try:
        bus.publish(request)
    finally:
        bus.unsubscribe(subscription)

    for result in outcomes:
        if result.message_type == "command.executed":
            success = result.raw.get("success") is True
            return {
                "status": "executed" if success else "failed",
                "reason": "Commande transmise à l’appareil simulé." if success else result.raw.get("error"),
                "request_id": request.message_id,
            }
        if result.message_type == "command.rejected":
            return {"status": "rejected", "reason": result.raw.get("decision", {}).get("reason"),
                    "request_id": request.message_id}
    return {"status": "failed", "reason": "Le bus n’a pas confirmé l’exécution.",
            "request_id": request.message_id}
