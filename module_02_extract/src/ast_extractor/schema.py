"""schema.py -- WIR JSON-schema loading (graceful fallback).

(Auto-extracted verbatim from the original monolith during modularization.)
"""

from __future__ import annotations

import json
from pathlib import Path


_CANDIDATE_SCHEMA_PATHS = [
    Path(__file__).resolve().parent.parent.parent.parent / "shared_schemas" / "wir_schema.json",
    Path(__file__).resolve().parent.parent.parent / "shared_schemas" / "wir_schema.json",
    Path("/app/shared_schemas/wir_schema.json"),
]


_WIR_SCHEMA = None


for p in _CANDIDATE_SCHEMA_PATHS:
    if p.exists():
        _WIR_SCHEMA = json.loads(p.read_text())
        break
