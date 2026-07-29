"""call_order_view.py -- call-order-linearized WIR, as an alternative to
``CFGExtractor.extract()``'s definition-order top-level graph.

``extract()`` walks the module body in file order, so a top-level
``def foo(): ...`` becomes a ``task`` node at the point it is *defined*, not
where it is *called*. The function that actually drives execution (calls the
sibling task functions, in real order, inside real branches) is extracted
separately into ``functions[name]`` with its calls flattened to opaque
``block`` nodes -- invisible to anything that only reads the top-level graph.
That mismatch is a structural cause of wrong Phase D verdicts (see
vibecheck-vault/Module 03 - Equivalence Engine/Bridge Investigation/CP1
Lifting-Scope Decision.md): both false ``VIOLATION`` (definition order
disagreeing with real call order) and the automaton never containing gateway
guards and task atoms together.

This module lifts the driver's own control-flow graph instead, reusing
``CFGExtractor``'s existing (tested) statement-visitor machinery, and marks
each call-site to a sibling top-level function as the task boundary. The
result is a WIR shaped exactly like ``extract()``'s top-level output --
suitable as a drop-in replacement for the graph fed to the C++ lifter --
but ordered and branched the way the driver actually executes.
"""

from __future__ import annotations

import ast
from typing import Any, Optional

from .cfg_extractor import CFGExtractor, contract_bookkeeping_nodes


def _count_sibling_calls(body: list[ast.stmt], sibling_names: set[str], exclude: str) -> int:
    count = 0
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in sibling_names and node.func.id != exclude:
                    count += 1
    return count


def _find_driver(
    tree: ast.Module, defs: dict[str, ast.stmt], sibling_names: set[str]
) -> tuple[str, list[ast.stmt]]:
    """Return ``(driver_name, driver_body)``: the top-level function whose
    body calls the most sibling top-level functions, or -- if no function
    calls any sibling at all -- the module's own trailing top-level
    statements (calls made directly at module scope)."""
    best_name: Optional[str] = None
    best_body: Optional[list[ast.stmt]] = None
    best_count = 0
    for name, node in defs.items():
        count = _count_sibling_calls(node.body, sibling_names, exclude=name)
        if count > best_count:
            best_name, best_body, best_count = name, node.body, count

    if best_name is not None:
        assert best_body is not None
        return best_name, best_body

    toplevel = [
        s for s in tree.body
        if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Import, ast.ImportFrom))
    ]
    return "<module>", toplevel


def _node_calls_sibling(code_lines: list[str], sibling_names: set[str], exclude: str) -> bool:
    """Does this node's (unparsed) statement text call a sibling top-level
    function? Re-parses the statement rather than regexing it, so this
    can't be fooled by a name that merely looks like a call."""
    for line in code_lines:
        try:
            stmt_tree = ast.parse(line)
        except SyntaxError:
            continue
        for node in ast.walk(stmt_tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in sibling_names and node.func.id != exclude:
                    return True
    return False


def derive_call_order_wir(source: str) -> dict[str, Any]:
    """
    Build a call-order-linearized WIR for *source*.

    Does not call or modify ``CFGExtractor.extract()`` -- this is a separate
    entry point, so ``extract()``'s definition-order output (and everything
    that already depends on its exact shape) is untouched.
    """
    tree = ast.parse(source)
    defs = {
        c.name: c for c in tree.body
        if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    sibling_names = set(defs.keys())

    driver_name, driver_body = _find_driver(tree, defs, sibling_names)

    sub = CFGExtractor()
    sub._current_func = driver_name
    entry, last = sub._build_body(driver_body)
    # _build_body (unlike visit_Module) returns the last statement's own
    # node as the chain's tail, with no outgoing edge. A task label only
    # ever attaches to an edge *leaving* its node (see lifter.cpp's
    # resolve_task_label call site), so without a trailing sentinel the
    # last call in the driver would never register an AP at all. Mirror
    # visit_Module's own entry/exit sentinel pattern to fix that.
    exit_sentinel = sub._make_block(node_type="exit")
    sub._link(last, exit_sentinel)
    sub.entry_id = entry.id
    sub.exit_id = exit_sentinel.id
    wir = contract_bookkeeping_nodes(sub.to_wir())

    for node in wir["nodes"]:
        if node["type"] != "block":
            continue
        if _node_calls_sibling(node["code"], sibling_names, exclude=driver_name):
            node["type"] = "task"

    wir["driver"] = driver_name
    return wir
