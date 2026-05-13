"""
main.py
=======
FastAPI entry point for Module 02 (Extract Engine).

Exposes a single POST endpoint ``/verify`` that accepts Python source code,
runs the complete V3 → V2 → V1 pipeline, and returns a multi-modal
certificate as JSON.
"""

import ast
import inspect
import os
import time
from typing import Any, get_type_hints

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="VibeCheck Extract Engine", version="2.0.0")

try:
    from .ast_extractor import CFGExtractor, run_v3_pipeline
    from .z3_sym_engine import BoundedConcolicEngine, run_v2_pipeline
    from .dynamic_tracer import (
        run_v1_pipeline,
        MultiModalCertificateComposer,
    )
except ImportError:
    from ast_extractor import CFGExtractor, run_v3_pipeline
    from z3_sym_engine import BoundedConcolicEngine, run_v2_pipeline
    from dynamic_tracer import (
        run_v1_pipeline,
        MultiModalCertificateComposer,
    )


class CodePayload(BaseModel):
    source_code: str


def _derive_v1_params(func_wir: dict) -> dict:
    """
    Derive V1 pipeline parameters directly from a function sub-CFG.

    Returns a dictionary with:
      * branch_lines      – line numbers of every gateway node
      * control_variables – union of control_vars from all gateways
      * state_variables   – union of data_vars from block nodes (excluding
                            control variables)
    """
    branch_lines: set[int] = set()
    control_variables: set[str] = set()
    state_variables: set[str] = set()

    for node in func_wir.get("nodes", []):
        if node["type"] == "gateway":
            if node.get("line"):
                branch_lines.add(node["line"])
            control_variables.update(node.get("control_vars", []))
        elif node["type"] == "block":
            state_variables.update(node.get("data_vars", []))

    # Remove any control variables that leaked into state
    state_variables -= control_variables

    return {
        "branch_lines": branch_lines,
        "control_variables": sorted(control_variables),
        "state_variables": sorted(state_variables),
    }


def _run_verification(source: str) -> dict:
    """
    Execute the full V3 → V2 → V1 pipeline on *source* and return the
    aggregated certificate dictionary.
    """
    # ------------------------------------------------------------------
    # Syntax pre-check
    # ------------------------------------------------------------------
    try:
        ast.parse(source)
    except SyntaxError:
        raise ValueError("Source code is not valid Python syntax.")

    # ------------------------------------------------------------------
    # Phase 1  --  Hardened Static AST Extraction (V3)
    # ------------------------------------------------------------------
    wir = run_v3_pipeline(source)
    v3_cert = wir.get("certificate", {})

    # ------------------------------------------------------------------
    # Dynamically select the first function for V2 / V1
    # ------------------------------------------------------------------
    functions = wir.get("functions", {})
    if not functions:
        raise ValueError("No functions found in source — cannot verify.")

    function_name = next(iter(functions))
    func_wir = functions[function_name]
    v1_params = _derive_v1_params(func_wir)

    # ------------------------------------------------------------------
    # Compile source once and share the namespace with V2 and V1
    # ------------------------------------------------------------------
    local_env: dict[str, Any] = {"__builtins__": __builtins__}
    exec(compile(source, "<string>", "exec"), local_env)
    func_obj = local_env[function_name]

    # ------------------------------------------------------------------
    # Derive initial inputs dynamically from function signature
    # ------------------------------------------------------------------
    try:
        type_hints = get_type_hints(func_obj)
    except Exception:
        type_hints = {}

    sig = inspect.signature(func_obj)
    initial_inputs: dict[str, Any] = {}
    for param_name, param in sig.parameters.items():
        ann = type_hints.get(param_name)
        origin = getattr(ann, "__origin__", None)
        if ann is int:
            initial_inputs[param_name] = 0
        elif ann is float:
            initial_inputs[param_name] = 0.0
        elif ann is bool:
            initial_inputs[param_name] = False
        elif ann is str:
            initial_inputs[param_name] = ""
        elif ann is list or origin is list:
            initial_inputs[param_name] = []  # Prevent element-type crashes on untyped collections.
        elif ann is dict or origin is dict:
            initial_inputs[param_name] = {}
        else:
            initial_inputs[param_name] = 0

    # ------------------------------------------------------------------
    # Phase 2  --  Symbolic Refinement with Z3 (V2)
    # ------------------------------------------------------------------
    # Production evaluation targets: V2_QUERY_BUDGET=500, V1_RUNS=100 per execution plan.
    query_budget = int(os.getenv("V2_QUERY_BUDGET", "20"))
    n_runs = int(os.getenv("V1_RUNS", "10"))
    v2_result = run_v2_pipeline(
        source=source,
        function_name=function_name,
        initial_inputs=initial_inputs,
        max_k=3,
        query_budget=query_budget,
        compiled_ns=local_env,
    )
    v2_cert = v2_result["certificate"]

    # ------------------------------------------------------------------
    # Phase 3  --  Dynamic Tracing & Differential Execution (V1)
    # ------------------------------------------------------------------
    v1_cert = run_v1_pipeline(
        source=source,
        function_name=function_name,
        wir=func_wir,
        task_patterns=[function_name],
        branch_lines=v1_params["branch_lines"],
        control_variables=v1_params["control_variables"],
        state_variables=v1_params["state_variables"] or None,
        n_runs=n_runs,
        seed=42,
        compiled_ns=local_env,
    )

    # ------------------------------------------------------------------
    # P3.5  --  Multi-Modal Certificate Composer
    # ------------------------------------------------------------------
    composer = MultiModalCertificateComposer()
    final = composer.compose(v1_cert, v2_cert, v3_cert)

    # Normalise to the wire format expected by the UI
    return {
        "v3_coverage": v3_cert.get("node_coverage", 0.0),
        "v2_confidence": final.get("v2_confidence", 0.0),
        "v1_confidence": final.get("v1_confidence", 0.0),
        "combined_confidence": final.get("combined_confidence", 0.0),
        "passed": final.get("passed", False),
        "message": final.get("message", ""),
        "v3_details": v3_cert,
        "v2_details": v2_cert,
        "v1_details": v1_cert,
        "wir": wir,
    }


@app.post("/verify")
def verify(payload: CodePayload) -> dict:
    """
    Accept Python workflow source code, run the full extraction / verification
    pipeline, and return the certificate JSON.
    """
    try:
        result = _run_verification(payload.source_code)
    except (ValueError, SyntaxError, TypeError, KeyError, RuntimeError, Exception) as e:
        return {
            "passed": False,
            "message": f"Verification aborted: {str(e)}",
            "v3_coverage": 0.0,
            "v2_confidence": 0.0,
            "v1_confidence": 0.0,
            "combined_confidence": 0.0,
            "v3_details": {},
            "v2_details": {},
            "v1_details": {},
            "wir": {},
        }
    return result


# Keep the CLI entry-point available for local / container debugging
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
