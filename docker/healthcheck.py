"""Check the simulation and both MQTT clients, not just the HTTP server."""

import json
from urllib.request import urlopen


def main() -> None:
    with urlopen("http://127.0.0.1:8080/api/state", timeout=3) as response:
        state = json.load(response)
    healthy = (
        state.get("status") == "running"
        and state.get("broker", {}).get("connected")
        and state.get("stats", {}).get("bus", {}).get("connected")
    )
    raise SystemExit(0 if healthy else 1)


if __name__ == "__main__":
    main()
