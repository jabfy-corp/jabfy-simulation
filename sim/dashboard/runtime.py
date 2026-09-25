"""Live local dashboard. Sensor inputs are queued onto the simulator tick thread.

Actuators remain controlled by the existing reflex → verification → execution
pipeline. This module never calls an actuator's apply_command().
"""

from __future__ import annotations

from collections import deque
from concurrent.futures import Future, TimeoutError as FutureTimeout
from copy import deepcopy
from datetime import datetime, timezone
import logging
import hashlib
from queue import Empty, Full, Queue
import threading
import time
from typing import Any, Callable
from uuid import uuid4

from fastapi import HTTPException

from sim.devices.security import MotionSensor, SmokeSensor

logger = logging.getLogger(__name__)
EVENT_LIMIT = 80


class Dashboard:
    """A bounded event feed and immutable snapshots shared with HTTP readers."""

    def __init__(self, runner: Any, *, home=None, store=None, runner_factory=None) -> None:
        self.runner = runner
        self.home = home
        self.store = store
        self.runner_factory = runner_factory
        self.base_config = runner.config.model_copy(deep=True)
        self.revision = self._revision(home)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._inputs: Queue[tuple[MotionSensor, int]] = Queue(maxsize=32)
        self._jobs: Queue[tuple[Future, Callable]] = Queue(maxsize=32)
        self._events: deque[dict[str, Any]] = deque(maxlen=EVENT_LIMIT)
        self._status = "starting"
        self._error: str | None = None
        self._snapshot: dict[str, Any] = {}
        self._previous: dict[str, dict[str, Any]] = {}
        self._subscription = None
        self._thread: threading.Thread | None = None
        self._capture()

    def start(self) -> None:
        self._attach()
        self._thread = threading.Thread(target=self._run, name="simulation-dashboard", daemon=True)
        self._thread.start()

    def _attach(self) -> None:
        if self.runner.bus_runner:
            self._subscription = self.runner.bus_runner.bus.subscribe(
                "command.*", self._on_message, name="simulation_dashboard"
            )
            if self.home:
                from sim.dashboard.commands import install_home_policies
                install_home_policies(self.runner)

    def _detach(self) -> None:
        if self._subscription is not None:
            self.runner.bus_runner.bus.unsubscribe(self._subscription)
            self._subscription = None

    def close(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=15)
        self._detach()

    @staticmethod
    def _revision(home) -> str:
        return hashlib.sha256(home.model_dump_json().encode()).hexdigest()[:16] if home else "legacy"

    def _event(self, kind: str, entity: str | None = None, **fields: Any) -> None:
        entry = {
            "id": str(uuid4()), "time": datetime.now(timezone.utc).isoformat(),
            "type": kind, "entity": entity, "action": None, "value": None,
            "reason": None, **fields,
        }
        with self._lock:
            self._events.append(entry)

    def _on_message(self, message: Any) -> None:
        kind = message.message_type
        if kind == "command.executed" and message.raw.get("success") is False:
            kind = "command.failed"
        self._event(
            kind, message.entity.id if message.entity else None,
            id=message.message_id, time=message.timestamp,
            action=(message.command or {}).get("action"),
            reason=message.raw.get("error") or message.raw.get("decision", {}).get("reason"),
        )

    def _capture(self) -> None:
        runner = self.runner
        devices = []
        definitions = {device.id: device for device in self.home.devices} if self.home else {}
        for device in runner.devices:
            state = deepcopy(device.get_state())
            devices.append({
                "id": device.id, "type": device.device_type, "location": device.location,
                "protocol": device.protocol, "state": state,
                "name": definitions[device.id].name if device.id in definitions else device.id,
                "room_id": device.location,
            })
            # Keep the journal useful: discrete changes, not every temperature sample.
            discrete = {key: value for key, value in state.items()
                        if key in {"state", "occupancy", "smoke", "switch", "running_state", "alarm"}}
            if device.id in self._previous and discrete != self._previous[device.id]:
                self._event("state.changed", device.id, value=state)
            self._previous[device.id] = discrete

        stats: dict[str, Any] = {"ticks": runner._tick_count, "devices": len(devices)}
        if runner.bus_runner:
            bus = runner.bus_runner
            # Do not rehash the entire audit log on every browser refresh.
            stats["bus"] = {
                "connected": bus._client.is_connected(),
                "proposals": bus.reflex.proposals,
                "decisions": len(bus.verification.decisions),
                "executed": bus.execution.executed, "failed": bus.execution.failed,
            }
        snapshot = {
            "home_revision": self.revision,
            "ticks": runner._tick_count, "devices": devices, "stats": stats,
            "pipeline": runner.bus_runner is not None,
            "broker": {
                "host": runner.config.broker.host, "port": runner.config.broker.port,
                "connected": runner.emitter._client.is_connected(),
            },
            "rules": [rule.model_dump() for rule in runner.config.reflex_rules],
        }
        with self._lock:
            self._snapshot = snapshot

    def house(self) -> dict:
        with self._lock:
            if not self.home:
                raise HTTPException(404, "Aucune maison éditable chargée.")
            return self.home.model_dump()

    def context(self) -> dict:
        """The same inventory serves the editor, 3D view and Jabfy Core."""
        from sim.home.catalog import device_capabilities

        with self._lock:
            if not self.home:
                raise HTTPException(404, "Aucune maison éditable chargée.")
            rooms = {room.id: room for room in self.home.rooms}
            states = {device["id"]: device for device in self._snapshot.get("devices", [])}
            inventory = []
            for device in self.home.devices:
                capabilities = device_capabilities(device.type)
                inventory.append({
                    **device.model_dump(), "room_name": rooms[device.room_id].name,
                    "state": deepcopy(states.get(device.id, {}).get("state", {})),
                    "actions": capabilities["actions"],
                    "sensor_events": capabilities["sensor_events"],
                })
            return {
                "schema_version": 1, "simulation": True, "revision": self.revision,
                "status": self._status,
                "home": {"id": self.home.id, "name": self.home.name,
                         "rooms": [room.model_dump() for room in self.home.rooms]},
                "devices": inventory,
            }

    def _submit(self, action: Callable, timeout: float = 20) -> Any:
        with self._lock:
            if self._status != "running":
                raise HTTPException(409, "La simulation doit être démarrée.")
        future = Future()
        try:
            self._jobs.put_nowait((future, action))
        except Full:
            raise HTTPException(429, "Trop de demandes en cours.") from None
        try:
            return future.result(timeout=timeout)
        except FutureTimeout:
            # An unstarted job is cancelled; an already running job may still finish.
            future.cancel()
            raise HTTPException(504, "Opération en cours : vérifiez son résultat avant de réessayer.") from None

    def command(self, device_id: str, action: str, params: dict, revision=None) -> dict:
        from sim.dashboard.commands import execute_command

        def execute():
            if revision is not None and revision != self.revision:
                raise HTTPException(409, "La maison a changé. Demandez une nouvelle proposition.")
            self._require_connection()
            return execute_command(self.runner, device_id, action, params)

        return self._submit(execute)

    def sensor_event(self, device_id: str, event: str) -> None:
        if event == "motion":
            return self.trigger_motion(device_id, 5000)

        def inject():
            self._require_connection()
            device = next((device for device in self.runner.devices if device.id == device_id), None)
            if device is None:
                raise HTTPException(404, "Appareil introuvable.")
            if not isinstance(device, SmokeSensor) or event not in {"smoke_on", "smoke_off"}:
                raise HTTPException(400, "Événement incompatible avec cet appareil.")
            (device.trigger_alarm if event == "smoke_on" else device.clear_alarm)()
            self.runner.emitter.emit(device)
            self._event(f"simulation.{event}", device_id)
            self._capture()

        self._submit(inject)

    def replace_home(self, home) -> dict:
        from sim.home.conversion import to_sim_config

        def replace():
            if self.runner_factory is None:
                raise HTTPException(409, "La modification de cette simulation est désactivée.")
            config = to_sim_config(home, self.base_config)
            # Reuse same-id/type state machines, including thermostat and sensor clocks.
            old = self.runner
            replacement = self.runner_factory(config)
            previous = {device.id: device for device in old.devices}
            for device in replacement.devices:
                existing = previous.get(device.id)
                if existing is not None and existing.device_type == device.device_type:
                    for key, value in existing.__dict__.items():
                        if key not in {"id", "location", "topic_prefix", "telemetry_interval_ms"}:
                            setattr(device, key, deepcopy(value))
            with self._lock:
                self._status = "starting"
            self._detach()
            old.shutdown()
            if old.bus_runner and replacement.bus_runner:
                replacement.bus_runner.reflex.restore_unchanged_rules(old.bus_runner.reflex)
            try:
                replacement.start()
                if self.store:
                    self.store.save(home)
            except Exception as exc:
                replacement.shutdown()
                try:
                    old.start()
                except Exception as rollback_error:
                    with self._lock:
                        self._status = "error"
                        self._error = str(rollback_error)
                    self._stop.set()
                else:
                    self._attach()
                    with self._lock:
                        self._status = "running"
                raise HTTPException(503, f"La maison précédente est conservée : {exc}") from exc
            self.runner = replacement
            with self._lock:
                self.home = home
                self.revision = self._revision(home)
                self._previous.clear()
            self._attach()
            self._capture()
            with self._lock:
                self._status = "running"
                self._error = None
            self._event("home.saved", value=home.name)
            return home.model_dump()

        return self._submit(replace)

    def _require_connection(self) -> None:
        if (not self.runner.emitter._client.is_connected()
                or (self.runner.bus_runner and not self.runner.bus_runner._client.is_connected())):
            raise HTTPException(409, "La simulation attend sa connexion au broker MQTT.")

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy({
                **self._snapshot, "status": self._status, "error": self._error,
                # Bus publications are synchronous/nested; timestamps restore causal order.
                "events": sorted(self._events, key=lambda event: event["time"], reverse=True),
            })

    def trigger_motion(self, device_id: str, duration_ms: int) -> None:
        device = next((device for device in self.runner.devices if device.id == device_id), None)
        if device is None:
            raise HTTPException(404, "Appareil introuvable.")
        if not isinstance(device, MotionSensor):
            raise HTTPException(400, "Cet appareil n’est pas un détecteur de mouvement.")
        current = self.snapshot()
        if (current["status"] != "running" or not current["broker"]["connected"]
                or (current["pipeline"] and not current["stats"]["bus"]["connected"])):
            raise HTTPException(409, "La simulation attend sa connexion au broker MQTT.")
        try:
            self._inputs.put_nowait((device, duration_ms))
        except Full:
            raise HTTPException(429, "Trop de demandes, réessayez dans un instant.") from None

    def _run(self) -> None:
        try:
            self.runner.start()
            with self._lock:
                self._status = "running"
            interval = self.runner.config.tick_interval_ms
            if interval <= 0:
                raise ValueError("tick_interval_ms must be greater than zero")
            while not self._stop.is_set():
                started = time.monotonic()
                # Only this worker changes devices or swaps the running house.
                for _ in range(32):
                    try:
                        future, job = self._jobs.get_nowait()
                    except Empty:
                        break
                    if future.set_running_or_notify_cancel():
                        try:
                            future.set_result(job())
                        except Exception as exc:
                            future.set_exception(exc)
                interval = self.runner.config.tick_interval_ms
                while True:
                    try:
                        device, duration = self._inputs.get_nowait()
                    except Empty:
                        break
                    # Ignore queued input for an appliance removed by an editor save.
                    device = next((current for current in self.runner.devices
                                   if current.id == device.id and isinstance(current, MotionSensor)), None)
                    if device is None:
                        continue
                    device.trigger_motion(duration_ms=duration)
                    self._event("simulation.motion", device.id, value=True)
                    # Publish the edge before tick() can clear a short detection.
                    self.runner.emitter.emit(device)
                self.runner._tick(interval)
                self._capture()
                self._stop.wait(max(0.0, interval / 1000 - (time.monotonic() - started)))
        except Exception as exc:
            logger.exception("Simulation dashboard could not run")
            with self._lock:
                self._status = "error"
                self._error = str(exc)
        finally:
            try:
                self.runner.shutdown()
            except Exception:
                logger.exception("Simulation cleanup failed")
            with self._lock:
                if self._status != "error":
                    self._status = "stopped"
            while True:
                try:
                    future, _ = self._jobs.get_nowait()
                except Empty:
                    break
                if not future.cancelled():
                    future.set_exception(HTTPException(409, "La simulation est arrêtée."))
