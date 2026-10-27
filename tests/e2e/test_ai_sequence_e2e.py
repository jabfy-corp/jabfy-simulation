"""Live stack: the AI tab prompt must blink the salon lamps one at a time.

Run against `docker compose up`: JABFY_E2E_URL=http://127.0.0.1:8080 pytest -m e2e tests/e2e
"""

import json
import os
import threading
import time
from urllib.request import Request, urlopen

import pytest

paho = pytest.importorskip("paho.mqtt.client")

BASE_URL = os.getenv("JABFY_E2E_URL", "")
MQTT_HOST = os.getenv("JABFY_E2E_MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("JABFY_E2E_MQTT_PORT", "1883"))
MODEL = os.getenv("JABFY_E2E_MODEL", "agent")
PROMPT = ("allume et eteind toutes les lampes du salon en quinconce pendant une seconde, "
          "pas plus d'une lampe doit etre allumée en meme temps")
LIGHT_TYPES = {"on_off_light", "dimmer_light", "rgb_bulb"}
TERMINAL = {"completed", "failed", "rejected", "no_action"}

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not BASE_URL, reason="JABFY_E2E_URL is not set"),
]


def call(path, body=None, timeout=15):
    request = Request(BASE_URL.rstrip("/") + path,
                      data=json.dumps(body).encode() if body is not None else None,
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


class CommandTimeline:
    """Every `<device>/set` published on the broker, timestamped on arrival."""

    def __init__(self):
        self.entries = []
        self._lock = threading.Lock()
        self._subscribed = threading.Event()
        self.client = paho.Client(callback_api_version=paho.CallbackAPIVersion.VERSION2)
        self.client.on_connect = lambda c, *_: c.subscribe("zigbee2mqtt/+/set")
        self.client.on_subscribe = lambda *_: self._subscribed.set()
        self.client.on_message = self._on_message

    def __enter__(self):
        self.client.connect(MQTT_HOST, MQTT_PORT)
        self.client.loop_start()
        assert self._subscribed.wait(5), "MQTT subscription failed"
        return self

    def __exit__(self, *exc):
        self.client.loop_stop()
        self.client.disconnect()

    def _on_message(self, client, userdata, message):
        wire = message.topic.split("/")[1]
        state = json.loads(message.payload).get("state")
        with self._lock:
            self.entries.append((time.monotonic(), wire, state))


def salon_lamps(context):
    wires = {}
    for device in context["devices"]:
        if device["room_id"] == "salon" and device["type"] in LIGHT_TYPES:
            wires[device["bus"]["topic"].rsplit("/", 1)[-1]] = device["id"]
    return wires


def lamp_states():
    return {device["id"]: device["state"].get("state") for device in call("/api/state")["devices"]}


@pytest.mark.parametrize("attempt", range(3))
def test_salon_lamps_blink_one_at_a_time(attempt):
    context = call("/api/ai/context")
    lamps = salon_lamps(context)
    assert len(lamps) >= 2, "the salon needs at least two lamps"
    for device_id in lamps.values():
        call(f"/api/devices/{device_id}/commands", {"action": "turn_off", "params": {}}, timeout=30)

    with CommandTimeline() as timeline:
        prompt_id = call("/api/ai/prompt", {"model": MODEL, "prompt": PROMPT})["prompt_id"]
        deadline = time.monotonic() + 240
        while True:
            run = call(f"/api/ai/runs/{prompt_id}")
            if run["status"] in TERMINAL or time.monotonic() > deadline:
                break
            time.sleep(0.25)
        time.sleep(0.5)
        entries = list(timeline.entries)

    assert run["status"] == "completed", run
    assert {entry[1] for entry in entries} <= set(lamps), f"only salon lamps: {entries}"

    lit, switched_on, durations = {}, set(), {}
    for at, wire, state in entries:
        if state == "ON":
            lit[wire] = at
            switched_on.add(wire)
            assert len(lit) <= 1, f"two lamps on together: {sorted(lit)}"
        elif state == "OFF" and wire in lit:
            durations.setdefault(wire, []).append(at - lit.pop(wire))
    assert switched_on == set(lamps), f"every salon lamp must light up: {entries}"
    assert not lit, f"lamps left on: {sorted(lit)}"
    for wire, values in durations.items():
        assert all(0.8 <= value <= 1.5 for value in values), (wire, values)

    time.sleep(0.5)
    states = lamp_states()
    assert all(states[device_id] == "OFF" for device_id in lamps.values()), states
