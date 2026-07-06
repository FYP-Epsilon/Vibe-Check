"""cfg_extractor.py -- V3 hardened AST -> CFG traversal (CFGExtractor).

(Auto-extracted verbatim from the original monolith during modularization.)
"""

from __future__ import annotations

import ast
from typing import Any, Optional
from .models import WIRNode, WIREdge
from .helpers import _unparse, _extract_name, _collect_vars


def _is_bookkeeping_node(node: dict[str, Any], protected_ids: set[Optional[str]]) -> bool:
    """A node is contractible iff it's a plain "block" with no code and no
    guard, and isn't the graph's designated entry/exit (contracting those
    would break anything that checks `current == exit_id` to terminate)."""
    if node["id"] in protected_ids:
        return False
    if node.get("type") != "block":
        return False
    code = node.get("code") or []
    if any(s.strip() for s in code):
        return False
    if node.get("guard"):
        return False
    return True


def contract_bookkeeping_nodes(wir: dict[str, Any]) -> dict[str, Any]:
    """
    Post-construction pass: remove blank merge/exit bookkeeping nodes.

    visit_If, visit_While, visit_For, visit_Try, visit_TryStar, and
    visit_Match each create one or more ``_make_block(node)`` nodes purely
    to join branches or mark a loop/exception exit -- these carry no code
    and no guard, and don't correspond to any AST statement. They're
    load-bearing *during construction* (e.g. visit_Try's finally-clause
    rerouting rewires edges through the merge node), but once construction
    is done they're pure noise in the emitted WIR: extra unmatched nodes
    against any statement-level ground truth (see eval/gold_wir.py / E2),
    and structure Module 03's equivalence clustering has to see through.

    This does NOT touch the visitors -- it rewires the already-built graph:
    every predecessor of a contractible node is linked directly to every
    successor, preserving edge labels (guard / exception_type). If a
    predecessor edge and a successor edge each carry a *different* label,
    that node is left uncontracted (recorded, not silently dropped) rather
    than picking one label and losing information.
    """
    nodes = {n["id"]: dict(n) for n in wir.get("nodes", [])}
    edges = [dict(e) for e in wir.get("edges", [])]
    protected: set[Optional[str]] = {wir.get("entry_node"), wir.get("exit_node")}

    uncontracted: list[str] = []
    progress = True
    while progress:
        progress = False
        candidates = [nid for nid, n in nodes.items() if _is_bookkeeping_node(n, protected)]
        for nid in candidates:
            if nid not in nodes:
                continue  # removed earlier in this same pass

            preds = [e for e in edges if e["target"] == nid]
            succs = [e for e in edges if e["source"] == nid]

            conflict = False
            for pe in preds:
                for se in succs:
                    p_label = (pe.get("guard"), pe.get("exception_type"))
                    s_label = (se.get("guard"), se.get("exception_type"))
                    if p_label != (None, None) and s_label != (None, None) and p_label != s_label:
                        conflict = True
                        break
                if conflict:
                    break
            if conflict:
                if nid not in uncontracted:
                    uncontracted.append(nid)
                continue

            new_edges = []
            for pe in preds:
                for se in succs:
                    guard = pe.get("guard") if pe.get("guard") is not None else se.get("guard")
                    exc = pe.get("exception_type") if pe.get("exception_type") is not None else se.get("exception_type")
                    new_edges.append({"source": pe["source"], "target": se["target"], "guard": guard, "exception_type": exc})

            edges = [e for e in edges if e["target"] != nid and e["source"] != nid] + new_edges

            for pe in preds:
                pred = nodes.get(pe["source"])
                if pred is not None:
                    pred["successors"] = [s for s in pred.get("successors", []) if s != nid]
            for se in succs:
                succ = nodes.get(se["target"])
                if succ is not None:
                    succ["predecessors"] = [p for p in succ.get("predecessors", []) if p != nid]
            for pe in preds:
                pred = nodes.get(pe["source"])
                for se in succs:
                    succ = nodes.get(se["target"])
                    if pred is not None and se["target"] not in pred["successors"]:
                        pred["successors"].append(se["target"])
                    if succ is not None and pe["source"] not in succ["predecessors"]:
                        succ["predecessors"].append(pe["source"])

            del nodes[nid]
            progress = True

    new_wir = dict(wir)
    new_wir["nodes"] = list(nodes.values())
    new_wir["edges"] = edges
    if uncontracted:
        new_wir["_bookkeeping_contraction_skipped"] = uncontracted
    return new_wir


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

                functions[child.name] = contract_bookkeeping_nodes(sub.to_wir())

        wir = contract_bookkeeping_nodes(self.to_wir())
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
        if isinstance(node.target, (ast.Tuple, ast.List)):
            header.data_vars = [
                elt.id for elt in node.target.elts
                if isinstance(elt, ast.Name)
            ]
        else:
            t = _extract_name(node.target)
            header.data_vars = [t] if t else []

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
