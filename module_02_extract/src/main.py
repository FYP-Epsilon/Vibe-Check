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


SAFE_BUILTINS = {
    "len": len, "range": range, "enumerate": enumerate, "zip": zip,
    "map": map, "filter": filter, "abs": abs, "min": min, "max": max,
    "sum": sum, "round": round, "str": str, "int": int, "float": float,
    "bool": bool, "list": list, "dict": dict, "tuple": tuple, "set": set,
    "type": type, "isinstance": isinstance, "hasattr": hasattr, "getattr": getattr,
}


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
        if node["type"] in ("gateway", "loop"):
            if node.get("line"):
                branch_lines.add(node["line"])
        control_variables.update(node.get("control_vars", []))
        if node["type"] == "block":
            state_variables.update(node.get("data_vars", []))

    # Remove any control variables that leaked into state
    state_variables -= control_variables

    return {
        "branch_lines": branch_lines,
        "control_variables": sorted(control_variables),
        "state_variables": sorted(state_variables),
    }


def _select_entry_function(functions: dict[str, Any]) -> str:
    """
    Pick the function to verify.

    ``next(iter(functions))`` silently picked whichever function the
    source *defines first* -- correct for the single-function test
    fixtures this pipeline was originally built against, but wrong for
    any multi-function source (e.g. eval/flowbench_adapter.py's generated
    corpus, which emits task-API stub defs *before* the ``workflow`` def
    they support): it verified a trivial stub, never the orchestration
    logic. Prefer a function literally named "workflow"; fall back to
    the first one so single-function sources are unaffected.
    """
    if "workflow" in functions:
        return "workflow"
    return next(iter(functions))


def _derive_task_patterns(tree: ast.Module, entry_function: str) -> list[str]:
    """
    Task patterns for V1: the entry function plus every other function
    defined at module level in the source.

    Previously task_patterns was just [entry_function], so stub-call
    assignments (e.g. ``incident = get_incident()``) were invisible to
    both the actual-side collector (it only tracks functions matching a
    task pattern) and the reference interpreter (E2) -- a drop-step
    mutant that deleted a leaf stub call produced zero trace difference.
    Single-function fixtures (loan_approval.py) are unaffected: this
    degenerates to [entry_function] when there's nothing else defined.
    """
    others = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name != entry_function
    ]
    return [entry_function] + others


def _derive_initial_inputs(tree: ast.Module, func_obj: Any) -> dict[str, Any]:
    """
    Derive a starting concrete input dict from *func_obj*'s type hints.

    Shared by the /verify pipeline and eval/calibrate.py's differential
    mode so both seed str params with the same guard-literal heuristic
    rather than duplicating this logic.
    """
    try:
        type_hints = get_type_hints(func_obj)
    except Exception:
        type_hints = {}

    # First guard-compared string literal in the source, if any -- gives V2's
    # initial concrete input a value that can actually reach a string-guarded
    # branch instead of always starting from "" (mirrors randomized.py's pool).
    first_str_literal = next(
        (
            side.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Compare)
            for side in (node.left, *node.comparators)
            if isinstance(side, ast.Constant) and isinstance(side.value, str)
        ),
        "",
    )

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
            initial_inputs[param_name] = first_str_literal
        elif ann is list or origin is list:
            initial_inputs[param_name] = []  # Prevent element-type crashes on untyped collections.
        elif ann is dict or origin is dict:
            initial_inputs[param_name] = {}
        else:
            initial_inputs[param_name] = 0
    return initial_inputs


def _run_verification(source: str) -> dict:
    """
    Execute the full V3 → V2 → V1 pipeline on *source* and return the
    aggregated certificate dictionary.
    """
    # ------------------------------------------------------------------
    # Normalize literal escapes and enforce size / complexity limits
    # ------------------------------------------------------------------
    source = source.replace('\\n', '\n').replace('\\t', '\t')

    if len(source) > 50000:
        raise ValueError("Source code exceeds maximum length of 50,000 characters.")

    try:
        tree = ast.parse(source)
    except SyntaxError:
        raise ValueError("Source code is not valid Python syntax.")

    ast_node_count = len(list(ast.walk(tree)))
    if ast_node_count > 5000:
        raise ValueError("AST complexity exceeds maximum of 5,000 nodes.")

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

    function_name = _select_entry_function(functions)
    func_wir = functions[function_name]
    v1_params = _derive_v1_params(func_wir)

    # ------------------------------------------------------------------
    # Compile source once and share the namespace with V2 and V1
    # ------------------------------------------------------------------
    local_env: dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
    exec(compile(source, "<string>", "exec"), local_env)
    func_obj = local_env[function_name]

    # ------------------------------------------------------------------
    # Derive initial inputs dynamically from function signature
    # ------------------------------------------------------------------
    initial_inputs = _derive_initial_inputs(tree, func_obj)

    # ------------------------------------------------------------------
    # Phase 2  --  Symbolic Refinement with Z3 (V2)
    # ------------------------------------------------------------------
    # Production evaluation targets: V2_QUERY_BUDGET=500, V1_RUNS=100 per execution plan.
    query_budget = int(os.getenv("V2_QUERY_BUDGET", "20"))
    n_runs = int(os.getenv("V1_RUNS", "10"))

    dynamic_query_budget = min(query_budget, max(10, 500 - ast_node_count // 10))
    dynamic_n_runs = min(n_runs, max(5, 100 - ast_node_count // 50))

    v2_result = run_v2_pipeline(
        source=source,
        function_name=function_name,
        initial_inputs=initial_inputs,
        max_k=3,
        query_budget=dynamic_query_budget,
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
        task_patterns=_derive_task_patterns(tree, function_name),
        branch_lines=v1_params["branch_lines"],
        control_variables=v1_params["control_variables"],
        state_variables=v1_params["state_variables"] or None,
        n_runs=dynamic_n_runs,
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
        "v3_abort": final.get("v3_abort", False),
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
