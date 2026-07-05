"""V3 static AST extraction package (structural validation).

(Auto-extracted verbatim from the original monolith during modularization.)
"""


from __future__ import annotations

from .schema import _CANDIDATE_SCHEMA_PATHS, _WIR_SCHEMA
from .models import WIRNode, WIREdge, Literal, CNF
from .helpers import _unparse, _extract_name, _collect_vars
from .cfg_extractor import CFGExtractor
from .dominators import DominatorAnalyzer
from .guards import GuardExtractor
from .data_layer import WIRDataLayer
from .certificate import V3Certificate
from .pipeline import run_v3_pipeline

__all__ = [
    "_CANDIDATE_SCHEMA_PATHS",
    "_WIR_SCHEMA",
    "WIRNode",
    "WIREdge",
    "Literal",
    "CNF",
    "_unparse",
    "_extract_name",
    "_collect_vars",
    "CFGExtractor",
    "DominatorAnalyzer",
    "GuardExtractor",
    "WIRDataLayer",
    "V3Certificate",
    "run_v3_pipeline",
]
