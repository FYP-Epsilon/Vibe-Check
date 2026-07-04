"""safe_exec.py -- sandboxed eval/exec helpers + SAFE_BUILTINS.

(Auto-extracted verbatim from the original monolith during modularization.)
"""

from __future__ import annotations

from typing import Any, Optional


SAFE_BUILTINS = {
    "len": len, "range": range, "enumerate": enumerate, "zip": zip,
    "map": map, "filter": filter, "abs": abs, "min": min, "max": max,
    "sum": sum, "round": round, "str": str, "int": int, "float": float,
    "bool": bool, "list": list, "dict": dict, "tuple": tuple, "set": set,
    "type": type, "isinstance": isinstance, "hasattr": hasattr, "getattr": getattr,
}


def _safe_eval(expr: str, env: dict[str, Any]) -> Any:
    """Evaluate *expr* in a restricted environment."""
    return eval(expr, {"__builtins__": {}}, env)


def _safe_exec(stmts: list[str], env: dict[str, Any]) -> None:
    """Execute a list of statement strings inside *env*."""
    if not stmts:
        return
    code = "\n".join(stmts)
    exec(code, {"__builtins__": {}}, env)
