"""Trusted adapter from the virtual house and Bus messages to jabfy-guard.

Only server-created virtual devices enter this catalog. No HTTP-supplied identity,
transport address, policy or simulation flag is used to establish authority.
"""

from collections import defaultdict, deque
import os
import time

from jabfy_guard import Capability, Command, Context, Device, Parameter, Policy, PolicySet, evaluate
from jabfy_bus.core.types import RiskLevel
from jabfy_bus.verification.policies import PolicyDecision

from sim.dashboard.commands import entity_id
from sim.home.catalog import device_capabilities
from sim.home.conversion import device_wire_id


def _parameters(schema, definitions=None):
    definitions = definitions or schema.get("$defs", {})
    if "$ref" in schema:
        schema = definitions[schema["$ref"].removeprefix("#/$defs/")]
    result = {}
    for name, value in schema.get("properties", {}).items():
        if "$ref" in value:
            value = definitions[value["$ref"].removeprefix("#/$defs/")]
        result[name] = Parameter(
            type=value["type"], required=name in schema.get("required", []),
            minimum=value.get("minimum"), maximum=value.get("maximum"),
            choices=value.get("enum"),
            properties=_parameters(value, definitions) if value["type"] == "object" else {},
        )
    return result


class HomeGuard:
    def __init__(self, runner, home):
        self.home_id = home.id
        self.mode = os.getenv("JABFY_GUARD_MODE", "normal")
        if self.mode not in {"normal", "restricted"}:
            raise ValueError("JABFY_GUARD_MODE must be normal or restricted")
        self.devices = {}
        self.targets = {}
        self.counts = defaultdict(deque)
        rules = []
        expected = {device.id for device in home.devices}
        for device in runner.devices:
            topic = f"zigbee2mqtt/{device_wire_id(home, device.id)}"
            if device.id not in expected or device.telemetry_topic != topic:
                raise ValueError("Guard accepts only this house's virtual device namespace")
            capabilities = device_capabilities(device.device_type)
            self.targets[entity_id(device)] = (device.id, topic)
            self.devices[device.id] = Device(domain=capabilities["domain"], actions={
                item["action"]: Capability(parameters=_parameters(item["params"]))
                for item in capabilities["actions"]
            })
            if capabilities["actions"]:
                rules.append(Policy(
                    id=f"virtual-{device.id}", effect="allow", home_id=home.id,
                    roles=["simulation"], devices=[device.id],
                    actions=list(self.devices[device.id].actions), max_per_minute=60,
                    allow_sensitive_simulation=True,
                ))
        self.policies = PolicySet(version="virtual-home-0.0.1", rules=rules)

    def __call__(self, message):
        # VerificationEngine serializes this call and the synchronous admission.
        source = message.source.adapter
        entity = message.entity.id if message.entity else None
        target = self.targets.get(entity)
        wire = message.command or {}
        if (source not in {"simulation_dashboard", "reflex_engine"} or target is None
                or wire.get("protocol") != "zigbee" or wire.get("target") != target[1]
                or set(wire) - {"action", "params", "protocol", "target"}):
            return PolicyDecision("rejected", "guard:UNTRUSTED_TARGET",
                                  "Source ou cible hors de la maison simulée.", RiskLevel.CRITICAL)
        now = time.time()
        counts = {}
        for rule in self.policies.rules:
            history = self.counts[(source, rule.id)]
            while history and history[0] <= now - 60:
                history.popleft()
            counts[rule.id] = len(history)
        context = Context(home_id=self.home_id, actor_id=source, roles=["simulation"],
                          mode=self.mode, simulation=True, observed_at=now,
                          devices=self.devices, recent_counts=counts)
        decision = evaluate(
            {"correlation_id": message.message_id, "home_id": self.home_id,
             "device_id": target[0], "action": wire.get("action"), "params": wire.get("params", {})},
            context, self.policies, now=now,
        )
        if decision.allowed:
            for rule_id in decision.policy_ids:
                self.counts[(source, rule_id)].append(now)
        return PolicyDecision("approved" if decision.allowed else "rejected",
                              f"guard:{decision.code}",
                              f"{decision.reason} [{', '.join(decision.policy_ids)}]",
                              RiskLevel(decision.risk or "critical"))
