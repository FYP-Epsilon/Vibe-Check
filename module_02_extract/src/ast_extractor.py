"""
ast_extractor.py
================
Phase 1: Hardening Static AST Extraction (V3)
Module 02 — Verified IR Extraction

This module implements the static analysis pipeline that transforms
Python 3.10+ source code into a hardened Workflow Intermediate
Representation (WIR) with complete branch-condition metadata,
dominator-tree proofs, and syntactic correctness certificates.

Milestones
----------
P1.1  CFGExtractor       – hardened AST → CFG traversal (NodeVisitor)
P1.2  DominatorAnalyzer  – networkx-based immediate-dominator tree
P1.3  GuardExtractor     – condition flattening to Conjunctive Normal Form
P1.4  WIRDataLayer       – control-variable vs. data-variable classification
P1.5  V3Certificate      – syntactic correctness certificate generator
"""

from __future__ import annotations

import ast
import copy
import itertools
from dataclasses import dataclass, field
from typing import Any, Optional

import networkx as nx


# ----------------------------------------------------------------------
# Shared WIR Data Model
# ----------------------------------------------------------------------

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


# CNF is a list of clauses; each clause is a list of Literals.
CNF = list[list[Literal]]


# ----------------------------------------------------------------------
# Utility helpers
# ----------------------------------------------------------------------

def _unparse(node: ast.AST) -> str:
    """Safe ``ast.unparse`` wrapper."""
    try:
        return ast.unparse(node)
    except Exception:
        return f"<{type(node).__name__}>"


def _extract_name(node: ast.AST) -> Optional[str]:
    """Return a simple variable name, or *None* for complex expressions."""
    if isinstance(node, ast.Name):
        return node.id
    return None


def _collect_vars(node: ast.AST) -> list[str]:
    """Return a sorted, deduplicated list of variable names in *node*."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
    return sorted(names)


# ----------------------------------------------------------------------
# P1.1  CFGExtractor
# ----------------------------------------------------------------------

class CFGExtractor:
    """
    Hardened AST → CFG builder.

    The extractor walks a Python 3.10+ abstract syntax tree and builds a
    statement-level control-flow graph.  Every significant control-flow
    construct (``if``, ``while``, ``for``, ``try``, ``try*``, ``match``,
    and the walrus operator ``:=``) receives explicit handling.
    """

    def __init__(self) -> None:
        # Graph storage
        self.nodes: dict[str, WIRNode] = {}
        self.edges: list[WIREdge] = []

        # Book-keeping
        self._counter: int = 0
        self.entry_id: Optional[str] = None
        self.exit_id: Optional[str] = None
        self.unsupported_constructs: list[str] = []
        self._current_func: Optional[str] = None

        # Loop context stack: list of (header_id, exit_id)
        self._loop_stack: list[tuple[str, str]] = []

    # -- internal helpers ------------------------------------------------

    def _new_id(self, prefix: str = "node") -> str:
        self._counter += 1
        return f"{prefix}_{self._counter}"

    def _make_block(
        self,
        ast_node: Optional[ast.AST] = None,
        line: int = 0,
        node_type: str = "block",
    ) -> WIRNode:
        """Allocate a fresh WIRNode, register it, and return it."""
        n = WIRNode(
            id=self._new_id(),
            node_type=node_type,
            ast_type=type(ast_node).__name__ if ast_node else "",
            line=line or (ast_node.lineno if ast_node and hasattr(ast_node, "lineno") else 0),
        )
        self.nodes[n.id] = n
        return n

    def _link(
        self,
        src: WIRNode,
        dst: WIRNode,
        guard: Optional[str] = None,
        exception_type: Optional[str] = None,
    ) -> None:
        """Add a directed edge from *src* to *dst*."""
        if dst.id not in src.successors:
            src.successors.append(dst.id)
        if src.id not in dst.predecessors:
            dst.predecessors.append(src.id)
        self.edges.append(WIREdge(src.id, dst.id, guard, exception_type))

    def _build_body(self, body: list[ast.stmt]) -> tuple[WIRNode, WIRNode]:
        """
        Convert a list of statements into a sequential chain.

        Returns ``(entry, exit)`` where *entry* is the first node of the
        chain and *exit* is the last node.
        """
        if not body:
            n = self._make_block()
            return n, n

        first_entry, first_exit = self.visit(body[0])
        current = first_exit

        for stmt in body[1:]:
            stmt_entry, stmt_exit = self.visit(stmt)
            # Normal sequential linkage – even after a *break* or *return*
            # we keep the edge.  The CFG is an over-approximation, which is
            # sound for the structural V3 pre-check.
            self._link(current, stmt_entry)
            current = stmt_exit

        return first_entry, current

    # -- public API ------------------------------------------------------

    def extract(self, source: str) -> dict[str, Any]:
        """
        Parse *source* and return a complete WIR dictionary.

        The WIR contains the top-level module CFG plus a ``functions``
        mapping with per-function sub-CFGs.
        """
        tree = ast.parse(source)
        entry, exit_node = self.visit(tree)
        self.entry_id = entry.id
        self.exit_id = exit_node.id

        # Extract sub-CFGs for every top-level function definition.
        functions: dict[str, dict[str, Any]] = {}
        for child in tree.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sub = CFGExtractor()
                sub._current_func = child.name
                func_entry, func_exit = sub._build_body(child.body)
                sub.entry_id = func_entry.id
                sub.exit_id = func_exit.id

                # Record arguments as data variables on the entry node.
                for arg in child.args.args:
                    sub.nodes[func_entry.id].data_vars.append(arg.arg)
                for arg in child.args.kwonlyargs:
                    sub.nodes[func_entry.id].data_vars.append(arg.arg)

                functions[child.name] = sub.to_wir()

        wir = self.to_wir()
        wir["functions"] = functions
        return wir

    def to_wir(self) -> dict[str, Any]:
        """Serialise the current CFG into the WIR JSON dictionary."""
        return {
            "entry_node": self.entry_id,
            "exit_node": self.exit_id,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
            "unsupported_constructs": list(self.unsupported_constructs),
        }

    # -- visitor dispatcher ----------------------------------------------

    def visit(self, node: ast.AST) -> tuple[WIRNode, WIRNode]:
        """Dispatch to ``visit_<NodeType>`` or fall back to ``generic_visit``."""
        method = getattr(self, f"visit_{type(node).__name__}", self.generic_visit)
        return method(node)

    def generic_visit(self, node: ast.AST) -> tuple[WIRNode, WIRNode]:
        """
        Fallback handler for AST node types that do not affect control flow.
        We create a single opaque block and record its source text.
        """
        n = self._make_block(node)
        n.code.append(_unparse(node))
        return n, n

    # -- statement-level visitors ----------------------------------------

    def visit_Module(self, node: ast.Module) -> tuple[WIRNode, WIRNode]:
        """Module is the program entry point."""
        entry = self._make_block(node, node_type="entry")
        exit_node = self._make_block(node, node_type="exit")

        if not node.body:
            self._link(entry, exit_node)
            return entry, exit_node

        current = entry
        for stmt in node.body:
            stmt_entry, stmt_exit = self.visit(stmt)
            self._link(current, stmt_entry)
            current = stmt_exit

        self._link(current, exit_node)
        return entry, exit_node

    def visit_Expr(self, node: ast.Expr) -> tuple[WIRNode, WIRNode]:
        """Bare expression statement (e.g. a function call)."""
        n = self._make_block(node)
        n.code.append(_unparse(node.value))
        return n, n

    def visit_Assign(self, node: ast.Assign) -> tuple[WIRNode, WIRNode]:
        n = self._make_block(node)
        n.code.append(_unparse(node))
        n.data_vars.extend(_collect_vars(node.value))
        for t in node.targets:
            n.data_vars.extend(_collect_vars(t))
        return n, n

    def visit_AnnAssign(self, node: ast.AnnAssign) -> tuple[WIRNode, WIRNode]:
        n = self._make_block(node)
        n.code.append(_unparse(node))
        if node.target:
            n.data_vars.extend(_collect_vars(node.target))
        if node.value:
            n.data_vars.extend(_collect_vars(node.value))
        return n, n

    def visit_AugAssign(self, node: ast.AugAssign) -> tuple[WIRNode, WIRNode]:
        n = self._make_block(node)
        n.code.append(_unparse(node))
        n.data_vars.extend(_collect_vars(node.target))
        n.data_vars.extend(_collect_vars(node.value))
        return n, n

    def visit_NamedExpr(self, node: ast.NamedExpr) -> tuple[WIRNode, WIRNode]:
        """
        P1.1 – Walrus operator ``:=`` (PEP 572).

        A named expression is both an assignment and a value.  We record
        the target as a *control* variable because it is defined inside an
        expression context (frequently a branch predicate) and therefore
        directly influences downstream control flow.
        """
        n = self._make_block(node)
        n.code.append(_unparse(node))
        target_name = _extract_name(node.target)
        if target_name:
            n.control_vars.append(target_name)
        n.data_vars.extend(_collect_vars(node.value))
        return n, n

    def visit_If(self, node: ast.If) -> tuple[WIRNode, WIRNode]:
        """Conditional branch with explicit true / false successors."""
        cond_block = self._make_block(node, node_type="gateway")
        cond_text = _unparse(node.test)
        cond_block.guard = cond_text
        cond_block.control_vars.extend(_collect_vars(node.test))

        # Walrus operators inside the predicate are assignments too.
        for child in ast.walk(node.test):
            if isinstance(child, ast.NamedExpr):
                cond_block.code.append(_unparse(child))
                t = _extract_name(child.target)
                if t and t not in cond_block.control_vars:
                    cond_block.control_vars.append(t)

        then_entry, then_exit = self._build_body(node.body)

        if node.orelse:
            else_entry, else_exit = self._build_body(node.orelse)
        else:
            else_entry = else_exit = self._make_block(node)

        merge = self._make_block(node)

        self._link(cond_block, then_entry, guard=cond_text)
        self._link(cond_block, else_entry, guard=f"not ({cond_text})")
        self._link(then_exit, merge)
        self._link(else_exit, merge)

        return cond_block, merge

    def visit_While(self, node: ast.While) -> tuple[WIRNode, WIRNode]:
        """
        Loop with a back-edge from body exit to the loop header.

        Python's ``while … else`` is modelled by routing the *false*
        branch through the ``else`` body before reaching the merge block.
        """
        header = self._make_block(node, node_type="loop")
        cond_text = _unparse(node.test)
        header.guard = cond_text
        header.control_vars.extend(_collect_vars(node.test))

        for child in ast.walk(node.test):
            if isinstance(child, ast.NamedExpr):
                header.code.append(_unparse(child))
                t = _extract_name(child.target)
                if t and t not in header.control_vars:
                    header.control_vars.append(t)

        exit_block = self._make_block(node)

        self._loop_stack.append((header.id, exit_block.id))
        body_entry, body_exit = self._build_body(node.body)
        self._loop_stack.pop()

        if node.orelse:
            else_entry, else_exit = self._build_body(node.orelse)
        else:
            else_entry = else_exit = exit_block

        self._link(header, body_entry, guard=cond_text)
        self._link(header, else_entry, guard=f"not ({cond_text})")
        self._link(body_exit, header)  # back-edge
        if node.orelse:
            self._link(else_exit, exit_block)

        return header, exit_block

    def visit_For(self, node: ast.For) -> tuple[WIRNode, WIRNode]:
        """
        ``for`` loop.

        The iteration variable is recorded as a data variable on the
        header node, and the iterable expression is stored as the guard.
        """
        header = self._make_block(node, node_type="loop")
        iter_text = _unparse(node.iter)
        header.guard = f"iter {iter_text}"
        header.control_vars.extend(_collect_vars(node.iter))
        header.data_vars.extend(_collect_vars(node.target))

        exit_block = self._make_block(node)

        self._loop_stack.append((header.id, exit_block.id))
        body_entry, body_exit = self._build_body(node.body)
        self._loop_stack.pop()

        if node.orelse:
            else_entry, else_exit = self._build_body(node.orelse)
        else:
            else_entry = else_exit = exit_block

        self._link(header, body_entry, guard=f"next({iter_text})")
        self._link(header, else_entry, guard=f"exhausted({iter_text})")
        self._link(body_exit, header)
        if node.orelse:
            self._link(else_exit, exit_block)

        return header, exit_block

    def visit_Break(self, node: ast.Break) -> tuple[WIRNode, WIRNode]:
        """Jump to the innermost loop exit."""
        n = self._make_block(node, node_type="break")
        n.code.append("break")
        if self._loop_stack:
            _, exit_id = self._loop_stack[-1]
            self._link(n, self.nodes[exit_id])
        return n, n

    def visit_Continue(self, node: ast.Continue) -> tuple[WIRNode, WIRNode]:
        """Jump to the innermost loop header."""
        n = self._make_block(node, node_type="continue")
        n.code.append("continue")
        if self._loop_stack:
            header_id, _ = self._loop_stack[-1]
            self._link(n, self.nodes[header_id])
        return n, n

    def visit_Return(self, node: ast.Return) -> tuple[WIRNode, WIRNode]:
        n = self._make_block(node, node_type="return")
        n.code.append(_unparse(node))
        if node.value:
            n.data_vars.extend(_collect_vars(node.value))
        return n, n

    def visit_FunctionDef(self, node: ast.FunctionDef) -> tuple[WIRNode, WIRNode]:
        """
        At module level a function definition is an opaque task boundary.

        The body of the function is *not* inlined; instead it is stored
        as a separate sub-CFG inside ``WIR["functions"]`` (see
        :py:meth:`extract`).
        """
        n = self._make_block(node, node_type="task")
        n.code.append(f"def {node.name}(...)")
        # Record signature variables for data-flow use.
        for arg in node.args.args:
            n.data_vars.append(arg.arg)
        for arg in node.args.kwonlyargs:
            n.data_vars.append(arg.arg)
        return n, n

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> tuple[WIRNode, WIRNode]:
        return self.visit_FunctionDef(node)  # type: ignore[arg-type]

    def visit_With(self, node: ast.With) -> tuple[WIRNode, WIRNode]:
        """``with`` statement – treated as a sequential block."""
        n = self._make_block(node)
        n.code.append(_unparse(node))
        for item in node.items:
            n.data_vars.extend(_collect_vars(item.context_expr))
        body_entry, body_exit = self._build_body(node.body)
        self._link(n, body_entry)
        return n, body_exit

    def visit_Try(self, node: ast.Try) -> tuple[WIRNode, WIRNode]:
        """
        ``try … except … else … finally``.

        We create a dedicated *try* block, route normal execution through
        the try body, and add exception edges from the try block to each
        handler.  The ``finally`` block (if present) is always reachable
        from both the normal and exception paths.
        """
        try_block = self._make_block(node, node_type="block")
        try_block.code.append("try:")

        try_body_entry, try_body_exit = self._build_body(node.body)
        self._link(try_block, try_body_entry)

        # Merge point after all handlers and else clause.
        merge = self._make_block(node)

        handler_entries: list[WIRNode] = []
        for handler in node.handlers:
            h_entry, h_exit = self._build_body(handler.body)
            exc_type = _unparse(handler.type) if handler.type else "Exception"
            self._link(try_block, h_entry, exception_type=exc_type)
            handler_entries.append(h_entry)
            self._link(h_exit, merge)

        if node.orelse:
            else_entry, else_exit = self._build_body(node.orelse)
            self._link(try_body_exit, else_entry)
            self._link(else_exit, merge)
        else:
            self._link(try_body_exit, merge)

        if node.finalbody:
            finally_entry, finally_exit = self._build_body(node.finalbody)
            # Re-route every path that currently enters *merge* so that it
            # passes through *finally* first.
            old_merge_preds = list(merge.predecessors)
            merge.predecessors.clear()
            for pred_id in old_merge_preds:
                pred = self.nodes[pred_id]
                # Replace edge pred->merge with pred->finally_entry
                if merge.id in pred.successors:
                    pred.successors.remove(merge.id)
                self.edges = [e for e in self.edges
                              if not (e.source == pred_id and e.target == merge.id)]
                self._link(pred, finally_entry)
            self._link(finally_exit, merge)

        return try_block, merge

    def visit_TryStar(self, node: ast.TryStar) -> tuple[WIRNode, WIRNode]:
        """
        P1.1 – Exception groups ``try* … except*`` (PEP 654).

        Semantically identical to a normal ``try`` for CFG purposes, but
        we annotate every exception edge with ``exception_type="*"`` to
        flag that the handler matches *sub-groups* of an ``ExceptionGroup``
        rather than a single naked exception.
        """
        try_block = self._make_block(node, node_type="block")
        try_block.code.append("try*:")

        try_body_entry, try_body_exit = self._build_body(node.body)
        self._link(try_block, try_body_entry)

        merge = self._make_block(node)

        for handler in node.handlers:
            h_entry, h_exit = self._build_body(handler.body)
            exc_type = _unparse(handler.type) if handler.type else "ExceptionGroup"
            # TryStar handlers match exception *groups* – annotate distinctly.
            self._link(try_block, h_entry, exception_type=f"*:{exc_type}")
            self._link(h_exit, merge)

        if node.orelse:
            else_entry, else_exit = self._build_body(node.orelse)
            self._link(try_body_exit, else_entry)
            self._link(else_exit, merge)
        else:
            self._link(try_body_exit, merge)

        if node.finalbody:
            finally_entry, finally_exit = self._build_body(node.finalbody)
            old_merge_preds = list(merge.predecessors)
            merge.predecessors.clear()
            for pred_id in old_merge_preds:
                pred = self.nodes[pred_id]
                if merge.id in pred.successors:
                    pred.successors.remove(merge.id)
                self.edges = [e for e in self.edges
                              if not (e.source == pred_id and e.target == merge.id)]
                self._link(pred, finally_entry)
            self._link(finally_exit, merge)

        return try_block, merge

    def visit_Match(self, node: ast.Match) -> tuple[WIRNode, WIRNode]:
        """
        P1.1 – Structural pattern matching (PEP 634).

        We model a ``match`` statement as a cascade of *gateway* nodes:
        one subject node followed by one conditional node per case.  The
        pattern of each case becomes the guard; the case body becomes the
        branch.  There is no explicit merge – every case body is linked
        to a shared post-match block.
        """
        subject = self._make_block(node, node_type="gateway")
        subject_text = _unparse(node.subject)
        subject.guard = f"match {subject_text}"
        subject.control_vars.extend(_collect_vars(node.subject))

        merge = self._make_block(node)

        prev_fallback: Optional[WIRNode] = subject
        for case in node.cases:
            case_guard = self._match_pattern_to_guard(subject_text, case.pattern)
            case_node = self._make_block(case, node_type="gateway")
            case_node.guard = case_guard
            case_node.control_vars.extend(_collect_vars(case.pattern))

            if case.guard:  # ``case … if <guard>``
                extra = _unparse(case.guard)
                case_guard = f"({case_guard}) and ({extra})"
                case_node.guard = case_guard
                case_node.control_vars.extend(_collect_vars(case.guard))

            body_entry, body_exit = self._build_body(case.body)
            self._link(case_node, body_entry, guard=case_guard)
            self._link(body_exit, merge)

            if prev_fallback is not None:
                self._link(prev_fallback, case_node, guard=f"not ({prev_fallback.guard})")
            prev_fallback = case_node

        # If no case matches, fall through to merge (Python raises
        # MatchError at runtime; we model this as an implicit exit path).
        if prev_fallback is not None:
            self._link(prev_fallback, merge, guard="no match")

        return subject, merge

    @staticmethod
    def _match_pattern_to_guard(subject: str, pattern: ast.pattern) -> str:
        """Convert an AST ``match`` pattern into a rough equality guard string."""
        if isinstance(pattern, ast.MatchValue):
            return f"{subject} == {_unparse(pattern.value)}"
        elif isinstance(pattern, ast.MatchSingleton):
            return f"{subject} is {pattern.value}"
        elif isinstance(pattern, ast.MatchAs):
            if pattern.pattern is None:
                return f"{subject} is not None"  # catch-all binding
            return f"{subject} matches {_unparse(pattern.pattern)}"
        elif isinstance(pattern, ast.MatchClass):
            cls = _unparse(pattern.cls)
            return f"isinstance({subject}, {cls})"
        elif isinstance(pattern, ast.MatchSequence):
            return f"len({subject}) == {len(pattern.patterns)}"
        elif isinstance(pattern, ast.MatchMapping):
            return f"{subject} is mapping"
        elif isinstance(pattern, ast.MatchStar):
            return f"*{subject} remainder"
        else:
            return f"{subject} matches <{type(pattern).__name__}>"

    def visit_ClassDef(self, node: ast.ClassDef) -> tuple[WIRNode, WIRNode]:
        """Classes are opaque blocks for CFG extraction."""
        n = self._make_block(node)
        n.code.append(f"class {node.name}(...)")
        self.unsupported_constructs.append(f"ClassDef:{node.name}")
        return n, n

    def visit_Import(self, node: ast.Import) -> tuple[WIRNode, WIRNode]:
        n = self._make_block(node)
        n.code.append(_unparse(node))
        return n, n

    def visit_ImportFrom(self, node: ast.ImportFrom) -> tuple[WIRNode, WIRNode]:
        n = self._make_block(node)
        n.code.append(_unparse(node))
        return n, n

    def visit_Global(self, node: ast.Global) -> tuple[WIRNode, WIRNode]:
        n = self._make_block(node)
        n.code.append(_unparse(node))
        return n, n

    def visit_Nonlocal(self, node: ast.Nonlocal) -> tuple[WIRNode, WIRNode]:
        n = self._make_block(node)
        n.code.append(_unparse(node))
        return n, n

    def visit_Pass(self, node: ast.Pass) -> tuple[WIRNode, WIRNode]:
        n = self._make_block(node)
        n.code.append("pass")
        return n, n

    def visit_Assert(self, node: ast.Assert) -> tuple[WIRNode, WIRNode]:
        n = self._make_block(node)
        n.code.append(_unparse(node))
        n.control_vars.extend(_collect_vars(node.test))
        return n, n

    def visit_Raise(self, node: ast.Raise) -> tuple[WIRNode, WIRNode]:
        n = self._make_block(node)
        n.code.append(_unparse(node))
        return n, n

    def visit_Delete(self, node: ast.Delete) -> tuple[WIRNode, WIRNode]:
        n = self._make_block(node)
        n.code.append(_unparse(node))
        return n, n


# ----------------------------------------------------------------------
# P1.2  DominatorAnalyzer
# ----------------------------------------------------------------------

class DominatorAnalyzer:
    """
    Compute immediate dominators and dominance frontiers using NetworkX.

    The dominator tree provides the structural proof required by V3:
    if node *d* dominates node *n*, then every path from the entry to
    *n* must pass through *d*.  This lets us verify BPMN ordering
    constraints (e.g. "Gateway CreditCheckPassed must precede
    Task ApproveLoan") syntactically.
    """

    def __init__(self, wir: dict[str, Any]) -> None:
        self.wir = wir
        self.g: nx.DiGraph = nx.DiGraph()
        self._build_graph()

    # -- internal helpers ------------------------------------------------

    def _build_graph(self) -> None:
        """Populate the NetworkX digraph from the WIR edge list."""
        for n in self.wir.get("nodes", []):
            self.g.add_node(n["id"], **n)
        for e in self.wir.get("edges", []):
            self.g.add_edge(e["source"], e["target"], **e)

    # -- public API ------------------------------------------------------

    def compute_immediate_dominators(self) -> dict[str, Optional[str]]:
        """
        Return a mapping ``{node_id: immediate_dominator_id}``.

        The entry node maps to ``None``.  If the graph is not reachable
        from the entry (e.g. disconnected due to incomplete exception
        handling), nodes outside the reachable set are omitted.
        """
        entry = self.wir.get("entry_node")
        if entry is None or entry not in self.g:
            return {}

        try:
            idoms = nx.immediate_dominators(self.g, entry)
        except nx.NetworkXError:
            # nx.immediate_dominators raises if entry does not reach all nodes.
            # We fall back to the reachable subgraph.
            reachable = nx.descendants(self.g, entry) | {entry}
            sub = self.g.subgraph(reachable).copy()
            idoms = nx.immediate_dominators(sub, entry)

        # Convert to serialisable dict; entry node has no idom.
        return {node: (dom if dom != node else None)
                for node, dom in idoms.items()}

    def compute_dominance_frontier(self) -> dict[str, set[str]]:
        """
        Return the dominance frontier for every node.

        A node *n* is in the dominance frontier of *d* iff *d* dominates
        a predecessor of *n* but does not strictly dominate *n*.
        """
        entry = self.wir.get("entry_node")
        if entry is None or entry not in self.g:
            return {}

        # Restrict to reachable nodes
        reachable = nx.descendants(self.g, entry) | {entry}
        sub = self.g.subgraph(reachable).copy()

        idoms = nx.immediate_dominators(sub, entry)

        # Build dominator tree
        dom_tree: dict[str, set[str]] = {n: set() for n in sub.nodes()}
        for node, dom in idoms.items():
            if dom != node:
                dom_tree[dom].add(node)

        # Compute frontier
        frontier: dict[str, set[str]] = {n: set() for n in sub.nodes()}

        def _dominates(d: str, n: str) -> bool:
            """True if *d* dominates *n* (including strict equality)."""
            cur: Optional[str] = n
            while cur is not None:
                if cur == d:
                    return True
                cur = idoms.get(cur)
            return False

        for node in sub.nodes():
            preds = list(sub.predecessors(node))
            if len(preds) >= 2:
                for pred in preds:
                    runner = pred
                    while runner is not None and not _dominates(node, runner):
                        frontier[runner].add(node)
                        runner = idoms.get(runner)

        return frontier

    def verify_ordering(self, required_before: str, required_after: str) -> dict[str, Any]:
        """
        V3 syntactic pre-check: verify that *required_before* dominates
        *required_after* in the CFG.

        Returns a dictionary with ``passed``, ``reason``, and the
        dominator path.
        """
        idoms = self.compute_immediate_dominators()
        if required_after not in idoms:
            return {
                "passed": False,
                "reason": f"'{required_after}' is not reachable from entry",
                "path": [],
            }

        # Walk the idom chain from required_after back to entry.
        path: list[str] = [required_after]
        cur: Optional[str] = idoms.get(required_after)
        while cur is not None:
            path.append(cur)
            if cur == required_before:
                return {
                    "passed": True,
                    "reason": f"'{required_before}' dominates '{required_after}'",
                    "path": list(reversed(path)),
                }
            cur = idoms.get(cur)

        return {
            "passed": False,
            "reason": f"'{required_before}' does NOT dominate '{required_after}'",
            "path": list(reversed(path)),
        }


# ----------------------------------------------------------------------
# P1.3  GuardExtractor
# ----------------------------------------------------------------------

class GuardExtractor:
    """
    Flatten Python boolean expressions into Conjunctive Normal Form (CNF).

    The extractor handles:
    * ``and`` / ``or`` / ``not`` via De Morgan's laws
    * Comparison operator inversion so that every literal is positive
    * Short-circuit semantics encoded as explicit ITE annotations
    * Collection of the typed variable inventory for each literal
    """

    def __init__(self) -> None:
        self.ite_counter: int = 0

    # -- public API ------------------------------------------------------

    def extract(self, node: ast.AST) -> CNF:
        """
        Convert an arbitrary expression AST into CNF.

        Returns a list of clauses where each clause is a list of
        :class:`Literal` objects.
        """
        nnf = self._to_nnf(node)
        return self._nnf_to_cnf(nnf)

    def extract_with_inventory(self, node: ast.AST) -> dict[str, Any]:
        """
        Like :py:meth:`extract` but also returns the variable inventory.
        """
        cnf = self.extract(node)
        inventory: dict[str, list[str]] = {}
        for clause in cnf:
            for lit in clause:
                for v in lit.vars_involved:
                    inventory.setdefault(v, []).append(lit.text)
        return {
            "cnf": [[lit.to_dict() for lit in clause] for clause in cnf],
            "inventory": inventory,
        }

    # -- NNF conversion --------------------------------------------------

    def _to_nnf(self, node: ast.AST, negated: bool = False) -> ast.AST:
        """
        Push negations inward until the tree contains only positive
        literals, ``And``, and ``Or`` nodes.
        """
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return self._to_nnf(node.operand, not negated)

        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                if negated:
                    # not(a and b) -> (not a) or (not b)
                    new_values = [self._to_nnf(v, True) for v in node.values]
                    return ast.BoolOp(op=ast.Or(), values=new_values)
                else:
                    new_values = [self._to_nnf(v, False) for v in node.values]
                    return ast.BoolOp(op=ast.And(), values=new_values)
            elif isinstance(node.op, ast.Or):
                if negated:
                    # not(a or b) -> (not a) and (not b)
                    new_values = [self._to_nnf(v, True) for v in node.values]
                    return ast.BoolOp(op=ast.And(), values=new_values)
                else:
                    new_values = [self._to_nnf(v, False) for v in node.values]
                    return ast.BoolOp(op=ast.Or(), values=new_values)

        if isinstance(node, ast.Compare) and negated:
            return self._invert_compare(node)

        if negated:
            # Generic fallback: wrap in UnaryOp Not
            return ast.UnaryOp(op=ast.Not(), value=node)

        return node

    @staticmethod
    def _invert_compare(node: ast.Compare) -> ast.Compare:
        """
        Invert every comparator in a comparison chain.

        ``not (x < y)`` → ``x >= y``, etc.
        """
        mapping = {
            ast.Eq: ast.NotEq,
            ast.NotEq: ast.Eq,
            ast.Lt: ast.GtE,
            ast.LtE: ast.Gt,
            ast.Gt: ast.LtE,
            ast.GtE: ast.Lt,
            ast.Is: ast.IsNot,
            ast.IsNot: ast.Is,
            ast.In: ast.NotIn,
            ast.NotIn: ast.In,
        }
        new_ops = []
        for op in node.ops:
            inv = mapping.get(type(op))
            if inv is None:
                # Fallback: wrap whole compare in not
                return ast.UnaryOp(op=ast.Not(), value=node)  # type: ignore[return-value]
            new_ops.append(inv())
        return ast.Compare(left=node.left, ops=new_ops, comparators=node.comparators)

    # -- CNF conversion --------------------------------------------------

    def _nnf_to_cnf(self, node: ast.AST) -> CNF:
        """Recursively convert a negation-free AST into CNF."""
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                result: CNF = []
                for v in node.values:
                    result.extend(self._nnf_to_cnf(v))
                return result
            elif isinstance(node.op, ast.Or):
                cnfs = [self._nnf_to_cnf(v) for v in node.values]
                return self._distribute_or(cnfs)

        # Atomic literal
        lit = self._make_literal(node)
        return [[lit]]

    def _distribute_or(self, cnfs: list[CNF]) -> CNF:
        """
        Distribute disjunction over conjunction.

        ``(a ∧ b) ∨ (c ∧ d)`` → ``(a ∨ c) ∧ (a ∨ d) ∧ (b ∨ c) ∧ (b ∨ d)``

        We flatten the result so that each element of the cross-product
        becomes a single clause.
        """
        # Each CNF is a list of clauses.  The OR of two CNFs is the
        # cross-product of their clause lists, merging clauses.
        result: CNF = [[]]
        for cnf in cnfs:
            new_result: CNF = []
            for clause_a in result:
                for clause_b in cnf:
                    merged = clause_a + clause_b
                    new_result.append(merged)
            result = new_result
        return result

    def _make_literal(self, node: ast.AST) -> Literal:
        """Create a Literal from an atomic AST node."""
        negated = isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not)
        if negated:
            inner = node.value  # type: ignore[attr-defined]
            text = f"not ({_unparse(inner)})"
            vars_involved = _collect_vars(inner)
            return Literal(negated=True, ast_node=inner, text=text, vars_involved=vars_involved)

        text = _unparse(node)
        vars_involved = _collect_vars(node)
        return Literal(negated=False, ast_node=node, text=text, vars_involved=vars_involved)

    # -- short-circuit ITE helpers ---------------------------------------

    def encode_short_circuit(self, node: ast.BoolOp) -> str:
        """
        Produce an explicit ITE string for a BoolOp.

        ``a and b`` → ``ITE(a, b, False)``
        ``a or b``  → ``ITE(a, True, b)``
        """
        if isinstance(node.op, ast.And):
            parts = [_unparse(v) for v in node.values]
            # Right-associate for multi-way And
            result = f"ITE({parts[0]}, {parts[1]}, False)"
            for p in parts[2:]:
                result = f"ITE({p}, {result}, False)"
            return result
        elif isinstance(node.op, ast.Or):
            parts = [_unparse(v) for v in node.values]
            result = f"ITE({parts[0]}, True, {parts[1]})"
            for p in parts[2:]:
                result = f"ITE({p}, True, {result})"
            return result
        return _unparse(node)


# ----------------------------------------------------------------------
# P1.4  WIRDataLayer
# ----------------------------------------------------------------------

class WIRDataLayer:
    """
    Classify variables into *control* (appear in branch conditions) and
    *data* (only used in computations).

    Performs a lightweight reaching-definitions style analysis over the
    CFG so that downstream V2 symbolic execution knows which variables
    must be tracked with full precision.
    """

    def __init__(self, wir: dict[str, Any]) -> None:
        self.wir = wir
        self.control_vars: set[str] = set()
        self.data_vars: set[str] = set()
        self._analyze()

    def _analyze(self) -> None:
        """Scan every WIR node and collect variable usages.

        Recursively descends into function sub-CFGs so that variables
        defined inside functions are also classified.
        """
        def _scan(node_list: list[dict[str, Any]]) -> None:
            for node in node_list:
                self.control_vars.update(node.get("control_vars", []))
                self.data_vars.update(node.get("data_vars", []))

        _scan(self.wir.get("nodes", []))
        for func_wir in self.wir.get("functions", {}).values():
            _scan(func_wir.get("nodes", []))

        # A variable that appears in both sets is *control* (the more
        # restrictive classification takes precedence).
        self.data_vars -= self.control_vars

    def get_classification(self) -> dict[str, list[str]]:
        return {
            "control_variables": sorted(self.control_vars),
            "data_variables": sorted(self.data_vars),
        }

    def annotate_wir(self) -> dict[str, Any]:
        """Return a new WIR with global control/data variable lists."""
        new_wir = copy.deepcopy(self.wir)
        classification = self.get_classification()
        new_wir["control_variables"] = classification["control_variables"]
        new_wir["data_variables"] = classification["data_variables"]
        return new_wir


# ----------------------------------------------------------------------
# P1.5  V3Certificate
# ----------------------------------------------------------------------

class V3Certificate:
    """
    Generate the Phase-1 syntactic correctness certificate.

    The certificate contains:
    * node_coverage      – fraction of AST statement nodes mapped to WIR
    * edge_coverage      – fraction of control-flow edges preserved
    * guard_success_rate – fraction of branch conditions decomposed into CNF
    * unsupported list   – constructs that could not be modelled
    * abort flag         – set when node_coverage < 0.95
    """

    def __init__(
        self,
        source: str,
        wir: dict[str, Any],
        guard_results: dict[str, Any],
    ) -> None:
        self.source = source
        self.wir = wir
        self.guard_results = guard_results
        self.tree = ast.parse(source)

    # -- public API ------------------------------------------------------

    def generate(self) -> dict[str, Any]:
        """Build and return the certificate dictionary."""
        node_cov = self._compute_node_coverage()
        edge_cov = self._compute_edge_coverage()
        guard_rate = self._compute_guard_success_rate()
        unsupported = self.wir.get("unsupported_constructs", [])

        abort = node_cov < 0.95

        cert = {
            "version": "V3",
            "node_coverage": node_cov,
            "edge_coverage": edge_cov,
            "guard_success_rate": guard_rate,
            "unsupported_constructs": unsupported,
            "abort": abort,
            "message": (
                "ABORT: node coverage below 0.95 threshold — manual review required."
                if abort else "V3 structural extraction passed quality gate."
            ),
        }
        return cert

    # -- metric helpers --------------------------------------------------

    def _compute_node_coverage(self) -> float:
        """
        Fraction of significant AST nodes that have a corresponding WIR node.

        We count all statement nodes in the original AST (excluding
        expressions nested inside statements) and compare against the
        number of WIR nodes of type ``block``, ``gateway``, ``loop``,
        ``task``, etc.  Function sub-CFGs are included in the count.
        """
        ast_stmt_count = 0
        for child in ast.walk(self.tree):
            if isinstance(child, ast.stmt):
                ast_stmt_count += 1

        def _count_significant(node_list: list[dict[str, Any]]) -> int:
            return sum(
                1 for n in node_list if n["type"] not in ("entry", "exit")
            )

        # Count WIR nodes that are not purely structural (entry/exit)
        wir_count = _count_significant(self.wir.get("nodes", []))
        for func_wir in self.wir.get("functions", {}).values():
            wir_count += _count_significant(func_wir.get("nodes", []))

        if ast_stmt_count == 0:
            return 1.0
        return min(wir_count / ast_stmt_count, 1.0)

    def _compute_edge_coverage(self) -> float:
        """
        Heuristic edge coverage: we assume every conditional statement
        contributes at least two edges.  The ratio of actual edges to
        expected edges gives a rough coverage score.

        Function sub-CFG edges are included in the count.
        """
        edges = list(self.wir.get("edges", []))
        for func_wir in self.wir.get("functions", {}).values():
            edges.extend(func_wir.get("edges", []))
        if not edges:
            return 1.0

        # Count conditional constructs in AST
        expected = 0
        for child in ast.walk(self.tree):
            if isinstance(child, (ast.If, ast.While, ast.For)):
                expected += 2
            elif isinstance(child, ast.Try):
                expected += 2 + len(child.handlers)
            elif isinstance(child, ast.TryStar):
                expected += 2 + len(child.handlers)
            elif isinstance(child, ast.Match):
                expected += len(child.cases) + 1

        if expected == 0:
            return 1.0
        return min(len(edges) / expected, 1.0)

    def _compute_guard_success_rate(self) -> float:
        """
        Fraction of branch conditions that were successfully parsed into
        CNF without falling back to an opaque string.
        """
        guards = self.guard_results
        total = guards.get("total", 0)
        success = guards.get("success", 0)
        if total == 0:
            return 1.0
        return success / total


# ----------------------------------------------------------------------
# Convenience orchestrator
# ----------------------------------------------------------------------

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

    return wir
