import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from scripts import cache


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Every test gets its own empty cache dir so tests never depend on
    (or pollute) the real API response cache used by the CLI."""
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / "cache")
