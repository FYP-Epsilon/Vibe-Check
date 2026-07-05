"""gold_wir.py -- independent gold-standard WIR labeler for E2.

Anti-circularity rule (load-bearing -- do not violate): this module must
NEVER import anything from ``src/ast_extractor/``. It derives a gold
control-flow structure straight from the ``ast`` module, independently of
the extractor being evaluated. If this module ever imports the extractor,
the E2 accuracy numbers become circular and meaningless -- enforced by
``eval/test_gold_wir.py``'s import-scan test.

Schema (one gold node per *statement*, no synthetic merge/exit bookkeeping
nodes -- see the E2 report's Methods section for why that choice matters):

    node:  {"gold_id": str, "type": "block"|"gateway"|"loop"|"return", "code": str}
    edge:  {"src_gold_id": str, "dst_gold_id": str, "label": str}

Type assignment: ``if``/``elif`` -> "gateway" (one gold node per test,
``elif`` is just a nested ``if`` in ``orelse``); ``for``/``while`` ->
"loop"; ``return`` -> "return"; everything else -> "block". Edge labels:
"true"/"false" out of a gateway, "enter"/"back" for a loop's body entry
and back-edge, "seq" for ordinary sequential fall-through.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Optional

EVAL_DIR = Path(__file__).resolve().parent
MODULE02_DIR = EVAL_DIR.parent
CORPUS_DIR = EVAL_DIR / "corpus"
GOLD_DIR = EVAL_DIR / "gold"
MANIFEST_PATH = EVAL_DIR / "manifest.json"


class GoldBuilder:
    """Builds a statement-level gold CFG for a single function body."""

    def __init__(self) -> None:
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self._counter = 0

    def _new_id(self) -> str:
        self._counter += 1
        return f"g{self._counter}"

    def _add_node(self, node_type: str, code: str) -> str:
        gold_id = self._new_id()
        self.nodes.append({"gold_id": gold_id, "type": node_type, "code": code})
        return gold_id

    def _add_edge(self, src: str, dst: str, label: str) -> None:
        self.edges.append({"src_gold_id": src, "dst_gold_id": dst, "label": label})

    def build_function(self, func_def: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
        self.build_seq(func_def.body)
        return {"nodes": self.nodes, "edges": self.edges}

    def build_seq(self, stmts: list[ast.stmt]) -> tuple[Optional[str], list[str]]:
        """Build a sequential chain of statements.

        Returns (entry_id or None if empty, dangling exit ids that whatever
        follows this sequence should link from).
        """
        entry_id: Optional[str] = None
        prev_exits: list[str] = []
        for stmt in stmts:
            node_id, exits = self._build_stmt(stmt)
            if entry_id is None:
                entry_id = node_id
            for p in prev_exits:
                self._add_edge(p, node_id, "seq")
            prev_exits = exits
        return entry_id, prev_exits

    def _build_stmt(self, stmt: ast.stmt) -> tuple[str, list[str]]:
        if isinstance(stmt, ast.If):
            return self._build_if(stmt)
        if isinstance(stmt, (ast.For, ast.While)):
            return self._build_loop(stmt)
        if isinstance(stmt, ast.Return):
            gold_id = self._add_node("return", ast.unparse(stmt))
            return gold_id, []  # terminal: nothing falls through a return
        # Generic statement (Assign, Expr, AugAssign, AnnAssign, Pass, ...).
        gold_id = self._add_node("block", ast.unparse(stmt))
        return gold_id, [gold_id]

    def _build_if(self, stmt: ast.If) -> tuple[str, list[str]]:
        gw_id = self._add_node("gateway", ast.unparse(stmt.test))

        then_entry, then_exits = self.build_seq(stmt.body)
        if then_entry is not None:
            self._add_edge(gw_id, then_entry, "true")
        else:
            then_exits = [gw_id]

        if stmt.orelse:
            else_entry, else_exits = self.build_seq(stmt.orelse)
            if else_entry is not None:
                self._add_edge(gw_id, else_entry, "false")
            else:
                else_exits = [gw_id]
        else:
            else_exits = [gw_id]

        return gw_id, then_exits + else_exits

    def _build_loop(self, stmt: ast.For | ast.While) -> tuple[str, list[str]]:
        if isinstance(stmt, ast.For):
            code = f"for {ast.unparse(stmt.target)} in {ast.unparse(stmt.iter)}"
        else:
            code = f"while {ast.unparse(stmt.test)}"
        loop_id = self._add_node("loop", code)

        body_entry, body_exits = self.build_seq(stmt.body)
        if body_entry is not None:
            self._add_edge(loop_id, body_entry, "enter")
            for be in body_exits:
                self._add_edge(be, loop_id, "back")

        # The loop node itself is the dangling exit for fall-through after
        # the iterable is exhausted / the condition goes false.
        return loop_id, [loop_id]


def build_gold(source: str, function_name: str = "workflow") -> dict[str, Any]:
    """Parse *source* and build a gold CFG for *function_name*."""
    tree = ast.parse(source)
    func_def = next(
        (n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == function_name),
        None,
    )
    if func_def is None:
        return {"nodes": [], "edges": []}
    return GoldBuilder().build_function(func_def)


def generate_gold(
    corpus_dir: Path = CORPUS_DIR,
    gold_dir: Path = GOLD_DIR,
    manifest_path: Path = MANIFEST_PATH,
) -> list[int]:
    """Generate gold/uid_*.json for every corpus program. Returns the uids
    for which gold generation succeeded."""
    gold_dir.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    corpus_entries = [e for e in manifest if "base_uid" not in e]

    ok_uids: list[int] = []
    for entry in corpus_entries:
        uid = entry["uid"]
        path = corpus_dir / f"uid_{uid}.py"
        if not path.exists():
            continue
        source = path.read_text(encoding="utf-8")
        try:
            gold = build_gold(source)
        except SyntaxError:
            continue
        (gold_dir / f"uid_{uid}.json").write_text(json.dumps(gold, indent=2), encoding="utf-8")
        ok_uids.append(uid)
    return ok_uids


if __name__ == "__main__":
    ok = generate_gold()
    print(f"Generated gold WIR for {len(ok)} programs -> {GOLD_DIR}")
