"""pipeline.py -- V3 end-to-end pipeline entry point (run_v3_pipeline).

(Auto-extracted verbatim from the original monolith during modularization.)
"""

from __future__ import annotations

import ast
from typing import Any, Optional
import jsonschema
from .cfg_extractor import CFGExtractor
from .dominators import DominatorAnalyzer
from .guards import GuardExtractor
from .data_layer import WIRDataLayer
from .certificate import V3Certificate
from .schema import _WIR_SCHEMA


def run_v3_pipeline(source: str) -> dict[str, Any]:
    """
    End-to-end Phase-1 pipeline.

    1. Extract CFG from *source*.
    2. Compute dominator tree.
    3. Extract and flatten all branch guards to CNF.
    4. Classify control vs. data variables.
    5. Emit the V3 certificate.
    """
    # --- P1.1 ----------------------------------------------------------
    extractor = CFGExtractor()
    wir = extractor.extract(source)

    # --- P1.2 ----------------------------------------------------------
    dom = DominatorAnalyzer(wir)
    idoms = dom.compute_immediate_dominators()
    wir["dominators"] = idoms
    wir["dominance_frontier"] = {k: list(v) for k, v in dom.compute_dominance_frontier().items()}

    # --- P1.3 ----------------------------------------------------------
    guard_ex = GuardExtractor()
    guard_results: dict[str, Any] = {"total": 0, "success": 0, "conditions": []}

    def _process_guards(node_list: list[dict[str, Any]]) -> None:
        for n in node_list:
            g = n.get("guard")
            if g:
                guard_results["total"] += 1
                try:
                    tree = ast.parse(g, mode="eval")
                    cnf = guard_ex.extract(tree.body)
                    guard_results["success"] += 1
                    guard_results["conditions"].append({
                        "node_id": n["id"],
                        "guard": g,
                        "cnf": [[lit.to_dict() for lit in clause] for clause in cnf],
                    })
                except Exception:
                    guard_results["conditions"].append({
                        "node_id": n["id"],
                        "guard": g,
                        "cnf": None,
                        "error": "Failed to parse guard into CNF",
                    })

    _process_guards(wir.get("nodes", []))
    for func_wir in wir.get("functions", {}).values():
        _process_guards(func_wir.get("nodes", []))

    wir["guard_extraction"] = guard_results

    # --- P1.4 ----------------------------------------------------------
    data_layer = WIRDataLayer(wir)
    wir = data_layer.annotate_wir()

    # --- P1.5 ----------------------------------------------------------
    cert = V3Certificate(source, wir, guard_results).generate()
    wir["certificate"] = cert

    # --- Schema validation -----------------------------------------------
    if _WIR_SCHEMA is not None:
        try:
            jsonschema.validate(instance=wir, schema=_WIR_SCHEMA)
        except jsonschema.ValidationError as e:
            raise ValueError(f"WIR schema validation failed: {e.message} at {list(e.path)}")

        for func_name, func_wir in wir.get("functions", {}).items():
            try:
                jsonschema.validate(instance=func_wir, schema=_WIR_SCHEMA)
            except jsonschema.ValidationError as e:
                raise ValueError(
                    f"WIR schema validation failed for function '{func_name}': {e.message} at {list(e.path)}"
                )

    return wir
