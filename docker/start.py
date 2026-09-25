"""Start the container UI once MQTT is listening, including after a Docker restart."""

import os
import socket
import time


def main() -> None:
    broker = os.environ.get("MQTT_BROKER", "mosquitto:1883")
    host, port = broker.rsplit(":", 1)
    deadline = time.monotonic() + 60
    while True:
        try:
            with socket.create_connection((host, int(port)), timeout=2):
                break
        except OSError:
            if time.monotonic() >= deadline:
                raise SystemExit(f"MQTT is unavailable at {broker}; container will retry.")
            time.sleep(1)

    # Replace this process so SIGTERM reaches the simulator for graceful shutdown.
    os.execvp("jabfy-sim", [
        "jabfy-sim", "ui", "--host", "0.0.0.0", "--port", "8080",
        "--broker", broker, "--home-file", "/app/data/home.json",
        "--core-url", os.environ.get("JABFY_CORE_URL", "http://core:8000"),
    ])


if __name__ == "__main__":
    main()
