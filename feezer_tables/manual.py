"""Grids maintained by hand in sources/*.json (operators whose website
cannot be read automatically, e.g. Airtel which blocks robots)."""

from __future__ import annotations

import json
from pathlib import Path

from .model import Grid

SOURCES = Path(__file__).resolve().parent.parent / "sources"


def collect(_fetcher=None, directory: Path = SOURCES) -> list[Grid]:
    grids: list[Grid] = []
    for path in sorted(directory.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        for entry in document["providers"]:
            grid = Grid.from_json(entry)
            grid.source_type = "manual"
            grids.append(grid)
    return grids
