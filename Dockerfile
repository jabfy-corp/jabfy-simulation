FROM python:3.11-slim

WORKDIR /app

# Install jabfy-bus + jabfy-sim together
COPY ../jabfy-bus /jabfy-bus
COPY . /app

RUN pip install --no-cache-dir \
    "/jabfy-bus[all]" \
    "/app[bus]"

CMD ["jabfy-sim", "demo", "--broker", "mosquitto:1883"]
