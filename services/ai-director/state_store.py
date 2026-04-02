from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class JsonStateStore:
    """Lightweight JSON file persistence for AI Director job state."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, dict[str, Any]]:
        if not self._path.exists():
            return {}
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                raw = json.load(fh)
            if not isinstance(raw, dict):
                logger.warning("State file %s is not a dict; ignoring", self._path)
                return {}
            return {
                str(k): v for k, v in raw.items() if isinstance(v, dict)
            }
        except Exception:
            logger.exception("Failed to load state from %s", self._path)
            return {}

    def save(self, jobs: dict[str, dict[str, Any]]) -> None:
        tmp_path = self._path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(jobs, fh, indent=2, sort_keys=True)
        tmp_path.replace(self._path)
