"""HTTP mock server — mimics real device REST APIs for testing jabfy-bus.

Two sub-applications are mounted:

  SmartTV (Samsung SmartThings-style):
    GET  /api/v2/                         — device info
    GET  /api/v2/state                    — full state
    POST /api/v2/power                    — {"state":"on"|"off"}
    POST /api/v2/volume                   — {"volume":30}
    POST /api/v2/source                   — {"source":"HDMI1"}

  NAS (Synology DSM-style):
    GET  /webapi/entry.cgi?api=SYNO.Info  — system info
    GET  /webapi/entry.cgi?api=SYNO.Storage.Volume — volume list
    GET  /webapi/entry.cgi?api=SYNO.FileStation.List — file list (stub)

The server runs in a background daemon thread.  Requires fastapi and
uvicorn — available transitively via jabfy-bus extras.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

try:
    import uvicorn
    from fastapi import FastAPI, HTTPException, Query, Request
    from fastapi.responses import JSONResponse
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False


class HTTPMockServer:
    """Runs SmartTV + NAS mock REST APIs in a background thread.

    Args:
        tv_device: A SmartTV instance (or None to skip SmartTV routes).
        nas_data:  Static NAS info dict (or None to use defaults).
        host:      Bind host (default ``"0.0.0.0"``).
        tv_port:   Port for SmartTV API (default 8001).
        nas_port:  Port for NAS API (default 5000).

    Usage::

        server = HTTPMockServer(tv_device=my_tv, host="localhost")
        server.start()
        # ... run simulation ...
        server.stop()
    """

    def __init__(
        self,
        tv_device: Any | None = None,
        nas_data: dict | None = None,
        host: str = "0.0.0.0",
        tv_port: int = 8001,
        nas_port: int = 5000,
    ) -> None:
        if not _FASTAPI_AVAILABLE:
            raise RuntimeError(
                "fastapi and uvicorn are required for HTTPMockServer. "
                "Install: pip install fastapi uvicorn"
            )
        self.host = host
        self.tv_port = tv_port
        self.nas_port = nas_port
        self._tv = tv_device
        self._nas_data = nas_data or _default_nas_data()
        self._tv_server: uvicorn.Server | None = None
        self._nas_server: uvicorn.Server | None = None
        self._threads: list[threading.Thread] = []

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start both API servers in background daemon threads."""
        if self._tv is not None:
            tv_app = _build_tv_app(self._tv)
            tv_cfg = uvicorn.Config(
                tv_app, host=self.host, port=self.tv_port,
                log_level="warning", access_log=False,
            )
            self._tv_server = uvicorn.Server(tv_cfg)
            t = threading.Thread(
                target=self._tv_server.run,
                daemon=True, name="mock-tv-api",
            )
            t.start()
            self._threads.append(t)
            logger.info("SmartTV mock API started on %s:%d", self.host, self.tv_port)

        nas_app = _build_nas_app(self._nas_data)
        nas_cfg = uvicorn.Config(
            nas_app, host=self.host, port=self.nas_port,
            log_level="warning", access_log=False,
        )
        self._nas_server = uvicorn.Server(nas_cfg)
        t = threading.Thread(
            target=self._nas_server.run,
            daemon=True, name="mock-nas-api",
        )
        t.start()
        self._threads.append(t)
        logger.info("NAS (Synology DSM) mock API started on %s:%d", self.host, self.nas_port)

    def stop(self) -> None:
        """Signal both servers to shut down."""
        if self._tv_server:
            self._tv_server.should_exit = True
        if self._nas_server:
            self._nas_server.should_exit = True
        for t in self._threads:
            t.join(timeout=2.0)
        logger.info("HTTP mock servers stopped")


# ──────────────────────────────────────────────────────────────────────────────
# SmartTV FastAPI app
# ──────────────────────────────────────────────────────────────────────────────

def _build_tv_app(tv) -> "FastAPI":
    """Build FastAPI app that wraps a SmartTV device."""
    app = FastAPI(title="jabfy-sim SmartTV Mock", version="1.0")

    @app.get("/api/v2/")
    def device_info():
        return {
            "id": tv.id,
            "name": f"JABFY Simulated TV ({tv.location})",
            "type": "Samsung SmartTV",
            "firmwareVersion": "2.0.0",
            "modelName": "JABFY-SIM-TV-55",
            "protocol": "rest",
        }

    @app.get("/api/v2/state")
    def state():
        return tv.get_state()

    @app.post("/api/v2/power")
    async def power(request: Request):
        body = await request.json()
        cmd_state = body.get("state", "")
        if cmd_state == "on":
            result = tv.apply_command("turn_on")
        elif cmd_state == "off":
            result = tv.apply_command("turn_off")
        else:
            raise HTTPException(status_code=400, detail="state must be 'on' or 'off'")
        return {"ok": result.success, "message": result.reason, "state": tv.get_state()}

    @app.post("/api/v2/volume")
    async def volume(request: Request):
        body = await request.json()
        if "volume" not in body:
            raise HTTPException(status_code=400, detail="volume field required")
        result = tv.apply_command("set_volume", {"volume": body["volume"]})
        if not result.success:
            raise HTTPException(status_code=422, detail=result.reason)
        return {"ok": True, "volume": tv.get_state()["volume"]}

    @app.post("/api/v2/source")
    async def source(request: Request):
        body = await request.json()
        if "source" not in body:
            raise HTTPException(status_code=400, detail="source field required")
        result = tv.apply_command("set_source", {"source": body["source"]})
        if not result.success:
            raise HTTPException(status_code=422, detail=result.reason)
        return {"ok": True, "inputSource": tv.get_state()["inputSource"]}

    @app.post("/api/v2/mute")
    async def mute(request: Request):
        body = await request.json()
        muted = body.get("mute", True)
        result = tv.apply_command("mute" if muted else "unmute")
        return {"ok": result.success, "mute": tv.get_state()["mute"]}

    return app


# ──────────────────────────────────────────────────────────────────────────────
# NAS (Synology DSM-style) FastAPI app
# ──────────────────────────────────────────────────────────────────────────────

def _default_nas_data() -> dict:
    return {
        "hostname": "jabfy-sim-nas",
        "model": "DS923+",
        "firmware": "7.2.1",
        "volumes": [
            {"id": 1, "path": "/volume1", "total_gb": 8000, "used_gb": 2134, "status": "normal"},
            {"id": 2, "path": "/volume2", "total_gb": 4000, "used_gb": 512, "status": "normal"},
        ],
        "files": [
            {"name": "jabfy-recordings", "isdir": True, "size": 0},
            {"name": "backup-2026-09-01.tar", "isdir": False, "size": 4_294_967_296},
        ],
    }


def _build_nas_app(nas_data: dict) -> "FastAPI":
    """Build a Synology DSM-style FastAPI app (read-only stub)."""
    app = FastAPI(title="jabfy-sim NAS Mock (Synology DSM)", version="1.0")

    @app.get("/webapi/entry.cgi")
    def entry(
        api: str = Query(..., description="API name"),
        method: str = Query("get"),
        version: int = Query(1),
    ):
        match api:
            case "SYNO.API.Info":
                return {
                    "success": True,
                    "data": {
                        "SYNO.Info": {"path": "entry.cgi", "minVersion": 1, "maxVersion": 7},
                        "SYNO.Storage.Volume": {"path": "entry.cgi", "minVersion": 1, "maxVersion": 1},
                        "SYNO.FileStation.List": {"path": "entry.cgi", "minVersion": 1, "maxVersion": 2},
                    },
                }

            case "SYNO.Info":
                return {
                    "success": True,
                    "data": {
                        "hostname": nas_data["hostname"],
                        "model": nas_data["model"],
                        "firmware_ver": nas_data["firmware"],
                        "uptime": 86400,
                    },
                }

            case "SYNO.Storage.Volume":
                return {
                    "success": True,
                    "data": {
                        "volumes": [
                            {
                                "id": f"volume_{v['id']}",
                                "vol_path": v["path"],
                                "total_size": str(v["total_gb"] * 1024 ** 3),
                                "used_size": str(v["used_gb"] * 1024 ** 3),
                                "status": v["status"],
                            }
                            for v in nas_data["volumes"]
                        ]
                    },
                }

            case "SYNO.FileStation.List":
                return {
                    "success": True,
                    "data": {
                        "total": len(nas_data["files"]),
                        "offset": 0,
                        "files": [
                            {
                                "name": f["name"],
                                "isdir": f["isdir"],
                                "path": f"/volume1/{f['name']}",
                                "additional": {
                                    "size": str(f["size"]),
                                    "time": {"mtime": 1756944000, "crtime": 1756900000},
                                },
                            }
                            for f in nas_data["files"]
                        ],
                    },
                }

            case _:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": {"code": 100, "errors": f"Unknown API: {api}"}},
                )

    return app
