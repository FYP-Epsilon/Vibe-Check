"""
main.py
=======
FastAPI entry point for Module 02 (Extract Engine).

Exposes a single POST endpoint ``/verify`` that accepts Python source code,
runs the complete V3 → V2 → V1 pipeline, and returns a multi-modal
certificate as JSON.
"""

import ast
import concurrent.futures
import inspect
import os
import time
from typing import Any, Optional, get_type_hints

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="VibeCheck Extract Engine", version="2.0.0")

# B3: wall-clock timeout for the whole /verify call. Read once at import
# time (module attribute, not re-read from the environment per request);
# tests monkeypatch this attribute directly rather than the env var, since
# Python looks up a bare global name in the enclosing module's namespace
# at CALL time, so a monkeypatched value is picked up by verify() even
# though it's a free variable there.
VERIFY_TIMEOUT_S = float(os.getenv("VERIFY_TIMEOUT_S", "30"))

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


def _derive_branch_arms(func_wir: dict) -> dict[int, tuple[Optional[int], Optional[int]]]:
    """
    For each gateway/loop node, resolve the first source line reached via its
    true (successors[0]) and false (successors[1]) outgoing edge.

    This is the "observation layer" for F2's branch-decision inference: it
    tells the collector WHERE the true/false arms of a branch land in the
    source, derived purely from the code-under-test's own WIR structure (no
    oracle/spec knowledge), matching the same observation-vs-oracle split
    established for branch_lines in eval/calibrate.py's C2 fix. A node with no
    code of its own (an entry/exit or an unremoved bookkeeping remnant) is
    walked through to its own successors until a real line is found.
    """
    nodes = {n["id"]: n for n in func_wir.get("nodes", [])}

    def _first_line(node_id: Optional[str], visited: set[str]) -> Optional[int]:
        if node_id is None or node_id in visited or node_id not in nodes:
            return None
        visited.add(node_id)
        node = nodes[node_id]
        if node.get("line"):
            return node["line"]
        for succ in node.get("successors", []):
            line = _first_line(succ, visited)
            if line is not None:
                return line
        return None

    arms: dict[int, tuple[Optional[int], Optional[int]]] = {}
    for node in nodes.values():
        if node["type"] in ("gateway", "loop") and node.get("line"):
            succs = node.get("successors", [])
            true_line = _first_line(succs[0], set()) if len(succs) >= 1 else None
            false_line = _first_line(succs[1], set()) if len(succs) >= 2 else None
            arms[node["line"]] = (true_line, false_line)
    return arms


def _derive_v1_params(func_wir: dict) -> dict:
    """
    Derive V1 pipeline parameters directly from a function sub-CFG.

    Returns a dictionary with:
      * branch_lines      – line numbers of every gateway node
      * control_variables – union of control_vars from all gateways
      * state_variables   – union of data_vars from block nodes (excluding
                            control variables)
      * branch_arms       – per branch_line, (true_line, false_line) — see
                            _derive_branch_arms
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
        "branch_arms": _derive_branch_arms(func_wir),
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

    B2: each phase (V3 -- including the pre-extraction source validation,
    since a syntax error is a V3-layer failure; compile; V2; V1) is
    wrapped in its own try/except and reported in the ``layers`` key
    (``{"v3": {"status": "OK"|"ERROR"|"SKIPPED", "reason": str|None}, ...}``)
    so a failure no longer collapses into one indistinguishable all-zero
    response -- existing top-level keys are unchanged, this only adds
    visibility into WHICH phase failed and why. A phase whose *inputs*
    come from an earlier failed phase (compile's local_env/func_obj,
    V1/V2's function_name/func_wir) is SKIPPED with the upstream reason
    rather than attempted; V2 and V1 are independent of each other once
    compiled, so one failing does not skip the other.
    """
    layers: dict[str, dict[str, Optional[str]]] = {
        "v3": {"status": "SKIPPED", "reason": None},
        "v2": {"status": "SKIPPED", "reason": None},
        "v1": {"status": "SKIPPED", "reason": None},
    }
    wir: dict[str, Any] = {}
    v3_cert: dict[str, Any] = {}
    v2_cert: dict[str, Any] = {}
    v1_cert: dict[str, Any] = {}

    def _result(passed: bool, message: str) -> dict:
        return {
            "v3_coverage": v3_cert.get("node_coverage", 0.0),
            "v3_abort": v3_cert.get("abort", False),
            "v2_confidence": v2_cert.get("confidence", 0.0),
            "v1_confidence": v1_cert.get("confidence", 0.0),
            "combined_confidence": 0.0,
            "passed": passed,
            "message": message,
            "v3_details": v3_cert,
            "v2_details": v2_cert,
            "v1_details": v1_cert,
            "wir": wir,
            "layers": layers,
        }

    # ------------------------------------------------------------------
    # Phase 1  --  Hardened Static AST Extraction (V3), including the
    # pre-extraction source validation (a syntax error IS a V3 failure).
    # ------------------------------------------------------------------
    try:
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

        wir = run_v3_pipeline(source)
        v3_cert = wir.get("certificate", {})
        functions = wir.get("functions", {})
        if not functions:
            raise ValueError("No functions found in source — cannot verify.")
        function_name = _select_entry_function(functions)
        func_wir = functions[function_name]
        v1_params = _derive_v1_params(func_wir)
        layers["v3"] = {"status": "OK", "reason": v3_cert.get("message")}
    except Exception as e:
        reason = str(e)
        layers["v3"] = {"status": "ERROR", "reason": reason}
        layers["v2"] = {"status": "SKIPPED", "reason": f"upstream v3 failure: {reason}"}
        layers["v1"] = {"status": "SKIPPED", "reason": f"upstream v3 failure: {reason}"}
        return _result(False, f"Verification aborted: {reason}")

    # ------------------------------------------------------------------
    # Compile source once and share the namespace with V2 and V1 -- a
    # prerequisite for both, not its own layer key (folded into "v2"
    # since it's the first phase that needs it; v1 is SKIPPED alongside).
    # ------------------------------------------------------------------
    try:
        local_env: dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
        exec(compile(source, "<string>", "exec"), local_env)
        func_obj = local_env[function_name]
        initial_inputs = _derive_initial_inputs(tree, func_obj)
    except Exception as e:
        reason = f"compile failed: {e}"
        layers["v2"] = {"status": "ERROR", "reason": reason}
        layers["v1"] = {"status": "SKIPPED", "reason": f"upstream {reason}"}
        return _result(False, f"Verification aborted: {reason}")

    # ------------------------------------------------------------------
    # Phase 2  --  Symbolic Refinement with Z3 (V2)
    # ------------------------------------------------------------------
    # Production evaluation targets: V2_QUERY_BUDGET=500, V1_RUNS=100 per execution plan.
    query_budget = int(os.getenv("V2_QUERY_BUDGET", "20"))
    n_runs = int(os.getenv("V1_RUNS", "10"))

    dynamic_query_budget = min(query_budget, max(10, 500 - ast_node_count // 10))
    dynamic_n_runs = min(n_runs, max(5, 100 - ast_node_count // 50))

    try:
        v2_result = run_v2_pipeline(
            source=source,
            function_name=function_name,
            initial_inputs=initial_inputs,
            max_k=3,
            query_budget=dynamic_query_budget,
            compiled_ns=local_env,
        )
        v2_cert = v2_result["certificate"]
        layers["v2"] = {"status": "OK", "reason": v2_cert.get("message")}
    except Exception as e:
        v2_cert = {}
        layers["v2"] = {"status": "ERROR", "reason": str(e)}

    # ------------------------------------------------------------------
    # Phase 3  --  Dynamic Tracing & Differential Execution (V1)
    # ------------------------------------------------------------------
    try:
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
            branch_arms=v1_params["branch_arms"],
        )
        layers["v1"] = {"status": "OK", "reason": v1_cert.get("message")}
    except Exception as e:
        v1_cert = {}
        layers["v1"] = {"status": "ERROR", "reason": str(e)}

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
        "layers": layers,
    }


def _timeout_result(timeout_s: float) -> dict:
    reason = "wall-clock timeout"
    return {
        "passed": False,
        "message": f"Verification aborted: wall-clock timeout after {timeout_s}s.",
        "v3_coverage": 0.0,
        "v2_confidence": 0.0,
        "v1_confidence": 0.0,
        "combined_confidence": 0.0,
        "v3_details": {},
        "v2_details": {},
        "v1_details": {},
        "wir": {},
        "layers": {
            "v3": {"status": "ERROR", "reason": reason},
            "v2": {"status": "ERROR", "reason": reason},
            "v1": {"status": "ERROR", "reason": reason},
        },
    }


def _run_verification_with_timeout(source: str, timeout_s: float) -> dict:
    """
    B3: bound how long a single /verify call can run. Step counters
    (WIR interpreter max_steps, V2's query_budget/iteration caps) only
    catch loops that step through WIR nodes -- they do nothing for a
    single Python-level statement that itself takes forever at the C
    level (e.g. ``pow(10, 10**8)``) once inside the real function call in
    V1's _run_actual / V2's _execute_concrete.

    KNOWN LIMITATIONS (Windows has no SIGALRM or any signal-based
    interruption primitive, and Python has no safe way to forcibly kill a
    running thread), stated honestly rather than papered over -- neither
    is production-grade cancellation, both are accepted for a research
    prototype:

    1. The worker thread cannot actually be terminated from here. On
       timeout, this function returns (``wait=False``) rather than
       blocking on the hung thread, but that thread keeps running in the
       background, orphaned, until it either finishes or the process
       exits.
    2. This mechanism only bounds a GIL-RELEASING hang (a Python
       bytecode loop, which yields the GIL at periodic safepoints, or a
       blocking I/O call) -- verified directly: a `while True: pass` hang
       is interrupted close to `timeout_s`. It does NOT bound a
       GIL-MONOPOLIZING hang: a single uninterrupted C-level statement
       with no safepoint (verified directly with a big-integer ``**`` of
       this size, which holds the GIL for its whole ~5s runtime) blocks
       `future.result()`'s own timeout check for as long as that
       statement runs. Once the GIL is released, `future.result()`
       returns the call's REAL result NORMALLY -- not a TimeoutError, not
       a typed timeout response -- because the call did, eventually,
       complete; `timeout_s` was never actually enforced against it. If
       such a statement runs forever (rather than merely a long time),
       this wrapper hangs forever too, silently reproducing the exact
       failure mode it exists to prevent. This is precisely the
       motivating example this docstring opened with (``pow(10,
       10**8)``); a thread-based timeout cannot close this gap in
       CPython, since only process-based isolation (e.g.
       ``multiprocessing`` + ``Process.terminate()``) can preempt a
       GIL-holding call from outside. That is out of scope for this
       session and is named as the honest leftover, not silently
       papered over.
    """
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_run_verification, source)
    try:
        result = future.result(timeout=timeout_s)
        executor.shutdown(wait=False)
        return result
    except concurrent.futures.TimeoutError:
        executor.shutdown(wait=False)
        return _timeout_result(timeout_s)


@app.post("/verify")
def verify(payload: CodePayload) -> dict:
    """
    Accept Python workflow source code, run the full extraction / verification
    pipeline, and return the certificate JSON.
    """
    try:
        result = _run_verification_with_timeout(payload.source_code, VERIFY_TIMEOUT_S)
    except (ValueError, SyntaxError, TypeError, KeyError, RuntimeError, Exception) as e:
        # Last resort: something outside _run_verification's own per-phase
        # try/except blocks raised (should not normally happen, since V3
        # -- including source validation -- is the first and outermost of
        # those). Every layer reports ERROR since none can be attributed
        # a specific phase from here.
        reason = str(e)
        return {
            "passed": False,
            "message": f"Verification aborted: {reason}",
            "v3_coverage": 0.0,
            "v2_confidence": 0.0,
            "v1_confidence": 0.0,
            "combined_confidence": 0.0,
            "v3_details": {},
            "v2_details": {},
            "v1_details": {},
            "wir": {},
            "layers": {
                "v3": {"status": "ERROR", "reason": reason},
                "v2": {"status": "ERROR", "reason": reason},
                "v1": {"status": "ERROR", "reason": reason},
            },
        }
    return result


# Keep the CLI entry-point available for local / container debugging
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
