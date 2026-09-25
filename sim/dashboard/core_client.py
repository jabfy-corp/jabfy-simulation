"""Small HTTP bridge to Jabfy Core. The destination is server configuration."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException


class CoreClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def request(self, path: str, body: dict | None = None) -> dict:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=90 if body is not None else 5) as response:
                return json.loads(response.read(2_000_000))
        except HTTPError as exc:
            try:
                detail = json.loads(exc.read()).get("detail", str(exc))
            except (ValueError, UnicodeDecodeError):
                detail = str(exc)
            raise HTTPException(502, f"Jabfy Core : {detail}") from exc
        except (URLError, OSError, ValueError) as exc:
            raise HTTPException(503, "Jabfy Core est indisponible. Démarrez-le pour utiliser l’IA.") from exc
