"""models.py -- shared WIR data model (WIRNode, WIREdge, Literal, CNF).

(Auto-extracted verbatim from the original monolith during modularization.)
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class WIRNode:
    """A single node in the Workflow Intermediate Representation graph."""

    id: str
    node_type: str  # entry, exit, block, gateway, loop, except, finally, match, task
    ast_type: str = ""
    line: int = 0
    code: list[str] = field(default_factory=list)
    successors: list[str] = field(default_factory=list)
    predecessors: list[str] = field(default_factory=list)
    guard: Optional[str] = None          # predicate for conditional edges
    exception_type: Optional[str] = None # e.g. "ValueError" or "*" for TryStar
    control_vars: list[str] = field(default_factory=list)
    data_vars: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.node_type,
            "ast_type": self.ast_type,
            "line": self.line,
            "code": self.code,
            "successors": self.successors,
            "predecessors": self.predecessors,
            "guard": self.guard,
            "exception_type": self.exception_type,
            "control_vars": self.control_vars,
            "data_vars": self.data_vars,
        }


@dataclass
class WIREdge:
    """Directed edge between two WIR nodes, optionally guarded."""

    source: str
    target: str
    guard: Optional[str] = None
    exception_type: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "guard": self.guard,
            "exception_type": self.exception_type,
        }


@dataclass
class Literal:
    """
    An atomic predicate literal inside a CNF clause.

    Attributes
    ----------
    negated:
        True if the literal is negated (e.g. ``not x``).
    ast_node:
        The original AST subtree that this literal represents.
    text:
        Human-readable / Z3-friendly string representation.
    vars_involved:
        Python variable names that appear inside the literal.
    """

    negated: bool
    ast_node: ast.AST
    text: str
    vars_involved: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "negated": self.negated,
            "text": self.text,
            "vars": self.vars_involved,
        }


CNF = list[list[Literal]]
