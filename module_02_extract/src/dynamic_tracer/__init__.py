"""V1 dynamic differential-testing package.

(Auto-extracted verbatim from the original monolith during modularization.)
"""


from __future__ import annotations

import sys
try:
    from ..ast_extractor import CFGExtractor, _collect_vars
except ImportError:
    from ast_extractor import CFGExtractor, _collect_vars
from .safe_exec import SAFE_BUILTINS, _safe_eval, _safe_exec
from .collector import WIRTraceCollector
from .interpreter import WIRReferenceInterpreter
from .comparator import DifferentialComparator
from .randomized import RandomizedDifferentialTester
from .composer import MultiModalCertificateComposer
from .pipeline import run_v1_pipeline

__all__ = [
    "SAFE_BUILTINS",
    "_safe_eval",
    "_safe_exec",
    "WIRTraceCollector",
    "WIRReferenceInterpreter",
    "DifferentialComparator",
    "RandomizedDifferentialTester",
    "MultiModalCertificateComposer",
    "run_v1_pipeline",
]
