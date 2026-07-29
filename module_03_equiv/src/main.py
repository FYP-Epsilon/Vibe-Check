"""
main.py -- Module 03 Equivalence Engine HTTP service.

Mirrors module_01_spec's FastAPI pattern (`uvicorn src.main:app`). Replaces
the old print-and-exit demo script, whose in-process `import vibecheck_lifter`
only ever worked when run directly inside this container -- M04's UI runs in
a *different* container with no compiled `.so`, so that import always failed
there (vibecheck-vault/Next Steps.md item #2).

Two endpoints, deliberately not conflated:

- ``/lift``: the actual fix for item #2 -- WIR type-lifting + tiered semantic
  action matching (the P1.1/P1.2 milestone demo), now reachable over HTTP
  instead of requiring the caller to have the compiled module itself.
- ``/check``: the real Phase A-D conformance check (property_ingest +
  process_wir_batch). This is the start of item #6 (first e2e demo), not
  part of #2's fix -- flagged explicitly because of a real constraint: this
  container only has module_03_equiv's own source (see property_ingest.py's
  own docstring on dual-track independence), so it cannot itself turn a
  definition-order WIR into a call-order one (module_02_extract's
  ``derive_call_order_wir``, the D2 fix, lives in the *other* container).
  The caller is responsible for posting an already call-order-lifted WIR;
  posting a definition-order one silently reproduces the pre-D2 bug.
"""

import json
import sys
import os
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

sys.path.append(os.path.dirname(__file__))

try:
    import vibecheck_lifter
    HAS_CPP_ENGINE = True
except ImportError:
    vibecheck_lifter = None  # type: ignore[assignment]
    HAS_CPP_ENGINE = False

from .pipeline import process_wir_batch
from .property_ingest import load_property_suite

app = FastAPI(title="VibeCheck Equivalence Engine", version="1.0.0")


def _require_cpp_engine() -> None:
    if not HAS_CPP_ENGINE:
        raise HTTPException(
            status_code=503,
            detail="vibecheck_lifter C++ module not available in this container.",
        )


class LiftPayload(BaseModel):
    wir: dict[str, Any]
    bpmn_tasks: list[str] = []
    action: Optional[str] = None


@app.post("/lift")
def lift(payload: LiftPayload):
    """WIR type-lifting (P1.1) + tiered semantic action matching (P1.2)."""
    _require_cpp_engine()

    lifter = vibecheck_lifter.AdvancedLifter()
    try:
        lifter.parse_wir_types(json.dumps(payload.wir))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"WIR type parsing failed: {exc}")

    result: dict[str, Any] = {"variable_map": lifter.get_variable_map()}

    if payload.bpmn_tasks:
        lifter.set_bpmn_tasks(payload.bpmn_tasks)
        if payload.action:
            result["matched_action"] = lifter.semantic_match(payload.action)

    return result


class CheckPayload(BaseModel):
    wir: dict[str, Any]
    bpmn_tasks: list[str] = []
    ltlf_property_suite: dict[str, list[str]]
    tier_semantics: dict[str, dict]


@app.post("/check")
def check(payload: CheckPayload):
    """
    Full Phase A-D conformance check for a single WIR.

    ``wir`` must already be call-order-lifted (see this module's docstring)
    -- this endpoint does not and cannot do that lifting itself.
    """
    _require_cpp_engine()

    try:
        suite = load_property_suite({
            "ltlf_property_suite": payload.ltlf_property_suite,
            "tier_semantics": payload.tier_semantics,
        })
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        result = process_wir_batch(
            [json.dumps(payload.wir)],
            bpmn_tasks=payload.bpmn_tasks,
            property_suite=suite,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Phase A-D processing failed: {exc}")

    cluster = next(iter(result["clusters"].values()))
    return {
        "compliance_results": cluster["compliance_results"],
        "excluded_properties": [
            {"tier": e.tier, "origin_formula": e.origin_formula, "reason": e.reason}
            for e in suite.excluded_properties()
        ],
    }


@app.get("/health")
def health():
    return {"status": "ok", "cpp_engine": HAS_CPP_ENGINE}
