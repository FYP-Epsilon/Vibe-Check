"""pipeline.py -- V1 pipeline entry point (run_v1_pipeline).

(Auto-extracted verbatim from the original monolith during modularization.)
"""

from __future__ import annotations

from typing import Any, Callable, Optional, get_type_hints
from .randomized import RandomizedDifferentialTester


def run_v1_pipeline(
    source: str,
    function_name: str,
    wir: dict[str, Any],
    task_patterns: list[str],
    branch_lines: set[int],
    control_variables: list[str],
    state_variables: Optional[list[str]] = None,
    n_runs: int = 20,
    seed: Optional[int] = None,
    compiled_ns: Optional[dict[str, Any]] = None,
    branch_arms: Optional[dict[int, tuple[Optional[int], Optional[int]]]] = None,
) -> dict[str, Any]:
    """
    End-to-end Phase-3 pipeline.

    1. Runs randomized differential testing (actual code vs. WIR reference).
    2. Returns the V1 certificate.
    """
    tester = RandomizedDifferentialTester(
        source=source,
        function_name=function_name,
        wir=wir,
        task_patterns=task_patterns,
        branch_lines=branch_lines,
        control_variables=control_variables,
        state_variables=state_variables,
        n_runs=n_runs,
        seed=seed,
        compiled_ns=compiled_ns,
        branch_arms=branch_arms,
    )
    return tester.run()
