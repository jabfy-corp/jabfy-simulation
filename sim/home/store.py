"""Atomic local persistence of a validated house, with no runtime state."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

from sim.home.models import Home


class HouseStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self, default: Home) -> Home:
        try:
            data = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self.save(default)
            return Home.model_validate(default.model_dump())
        try:
            return Home.model_validate_json(data)
        except ValueError as exc:
            raise ValueError(f"Maison invalide dans '{self.path}' : {exc}") from exc

    def save(self, home: Home) -> None:
        # Revalidate nested lists too: a caller may have mutated a model in memory.
        valid = Home.model_validate(home.model_dump())
        payload = valid.model_dump_json(indent=2) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix=f".{self.path.name}.", suffix=".tmp", delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
