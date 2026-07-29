"""V2 Z3 concolic symbolic-execution package.

(Auto-extracted verbatim from the original monolith during modularization.)
"""


from __future__ import annotations

import sys
try:
    from ..ast_extractor import CFGExtractor, _unparse
except ImportError:
    from ast_extractor import CFGExtractor, _unparse
from .safe_exec import SAFE_BUILTINS, _safe_eval, _safe_exec
from .registry import Z3VariableRegistry
from .evaluator import SymbolicEvaluator
from .tracer import BranchRecord, WIRSymbolicTracer
from .concolic import BoundedConcolicEngine
from .pipeline import run_v2_pipeline

__all__ = [
    "SAFE_BUILTINS",
    "_safe_eval",
    "_safe_exec",
    "Z3VariableRegistry",
    "SymbolicEvaluator",
    "BranchRecord",
    "WIRSymbolicTracer",
    "BoundedConcolicEngine",
    "run_v2_pipeline",
]
