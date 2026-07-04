"""pipeline.py -- V2 pipeline entry point (run_v2_pipeline).

(Auto-extracted verbatim from the original monolith during modularization.)
"""

from __future__ import annotations

from typing import Any, Optional
from .concolic import BoundedConcolicEngine


def run_v2_pipeline(
    source: str,
    function_name: str,
    initial_inputs: dict[str, Any],
    max_k: int = 3,
    query_budget: int = 500,
    compiled_ns: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    End-to-end Phase-2 pipeline.

    1. Runs the :class:`BoundedConcolicEngine` on *function_name*.
    2. Returns the V2 certificate plus the final concrete / symbolic
       states from the last iteration.
    """
    engine = BoundedConcolicEngine(
        source=source,
        function_name=function_name,
        max_k=max_k,
        query_budget=query_budget,
        compiled_ns=compiled_ns,
    )
    cert = engine.run(initial_inputs)
    return {
        "certificate": cert,
        "engine": engine,
    }
