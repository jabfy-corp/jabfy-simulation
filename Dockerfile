FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# The build context is the parent workspace, set by jabfy-deploy/compose.local.yml.
COPY jabfy-bus/pyproject.toml jabfy-bus/README.md /jabfy-bus/
COPY jabfy-bus/jabfy_bus /jabfy-bus/jabfy_bus
COPY jabfy-guard/pyproject.toml jabfy-guard/README.md /jabfy-guard/
COPY jabfy-guard/src /jabfy-guard/src
COPY jabfy-simulation/pyproject.toml jabfy-simulation/README.md /app/
COPY jabfy-simulation/sim /app/sim
COPY jabfy-simulation/scenarios /app/scenarios
COPY jabfy-simulation/docker /app/docker

RUN pip install --no-cache-dir \
    "/jabfy-guard" \
    "/jabfy-bus[all]" \
    "/app[full]"

EXPOSE 8080

CMD ["python", "/app/docker/start.py"]
