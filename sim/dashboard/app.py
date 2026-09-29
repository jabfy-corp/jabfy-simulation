"""HTTP routes for the house document, live simulation, controls and AI bridge."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Path as PathParam, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from sim.dashboard.core_client import CoreClient
from sim.dashboard.runtime import Dashboard
from sim.home.catalog import catalog
from sim.home.models import Home

STATIC = Path(__file__).with_name("static")


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MotionInput(InputModel):
    duration_ms: int = Field(default=5000, ge=200, le=60000, strict=True)


class CommandInput(InputModel):
    action: str = Field(min_length=1, max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)
    context_revision: str | None = None


class SensorInput(InputModel):
    event: Literal["motion", "smoke_on", "smoke_off"]


class ProposalInput(InputModel):
    model: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=4000)


def same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Origine de la requête non autorisée.")


def create_app(runner: Any, *, home=None, store=None, runner_factory=None,
               core_url: str = "http://127.0.0.1:8000") -> FastAPI:
    dashboard = Dashboard(runner, home=home, store=store, runner_factory=runner_factory)
    core = CoreClient(core_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        dashboard.start()
        try:
            yield
        finally:
            dashboard.close()

    app = FastAPI(title="Jabfy · Maison simulée", lifespan=lifespan)
    app.state.dashboard = dashboard
    app.state.core_client = core

    @app.get("/api/state")
    def state():
        return dashboard.snapshot()

    @app.get("/api/home")
    def get_home():
        return dashboard.house()

    @app.put("/api/home", dependencies=[Depends(same_origin)])
    def save_home(body: Home):
        return dashboard.replace_home(body)

    @app.get("/api/catalog")
    def get_catalog():
        return catalog()

    @app.post("/api/devices/{device_id}/commands", dependencies=[Depends(same_origin)])
    def command(device_id: str, body: CommandInput):
        return dashboard.command(device_id, body.action, body.params, body.context_revision)

    @app.post("/api/devices/{device_id}/events", status_code=202,
              dependencies=[Depends(same_origin)])
    def sensor_event(device_id: str, body: SensorInput):
        dashboard.sensor_event(device_id, body.event)
        return {"accepted": True}

    @app.post("/api/devices/{device_id}/motion", status_code=202,
              dependencies=[Depends(same_origin)])
    def motion(device_id: str, body: MotionInput):
        dashboard.trigger_motion(device_id, body.duration_ms)
        return {"accepted": True, "device_id": device_id, "duration_ms": body.duration_ms}

    @app.get("/api/ai/context")
    def context():
        return dashboard.context()

    @app.get("/api/ai/models")
    def models():
        return core.request("/models")

    @app.post("/api/ai/propose", dependencies=[Depends(same_origin)])
    def propose(body: ProposalInput):
        return core.request("/simulation/propose", body.model_dump())

    @app.post("/api/ai/prompt", status_code=202, dependencies=[Depends(same_origin)])
    def prompt(body: ProposalInput):
        return core.request("/prompt", body.model_dump())

    @app.get("/api/ai/runs/{run_id}")
    def run(run_id: str = PathParam(pattern=r"^[0-9a-f-]{36}$")):
        return core.request(f"/prompts/{run_id}")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
