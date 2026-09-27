"""Local disk cache for API responses, keyed by a hash of request parameters.

Avoids re-hitting the Wikimedia/Wikidata APIs when the agent refines a query
(e.g. adds a language or extends the date range) but most of the request is
unchanged.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

CACHE_DIR = Path(__file__).resolve().parent.parent / "output" / "cache"


def _key(namespace: str, params: dict[str, Any]) -> str:
    payload = json.dumps(params, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{namespace}_{digest}"


def get(namespace: str, params: dict[str, Any]) -> Any | None:
    path = CACHE_DIR / f"{_key(namespace, params)}.json"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def set(namespace: str, params: dict[str, Any], value: Any) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{_key(namespace, params)}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False)
