"""test_gold_wir.py -- tests for the independent gold-WIR labeler (X1).

Includes the load-bearing anti-circularity check: gold_wir.py must never
import anything from src/ast_extractor/, or the E2 accuracy numbers
become circular (the extractor graded against a copy of itself).
"""

from __future__ import annotations

import ast
from pathlib import Path

from eval.gold_wir import build_gold

GOLD_WIR_SOURCE = Path(__file__).resolve().parent / "gold_wir.py"


class TestAntiCircularity:
    def test_gold_wir_never_imports_ast_extractor(self):
        tree = ast.parse(GOLD_WIR_SOURCE.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "ast_extractor" not in alias.name
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or "ast_extractor" not in node.module


class TestBuildGold:
    SOURCE = (
        "def stub_a():\n    return {}\n\n\n"
        "def stub_b():\n    return {}\n\n\n"
        "def stub_c():\n    return {}\n\n\n"
        "def workflow(items: list, status: str) -> int:\n"
        "    a = stub_a()\n"
        "    if status == \"high\":\n"
        "        b = stub_b()\n"
        "    for x in items:\n"
        "        c = stub_c()\n"
        "    return 0\n"
    )

    def test_node_types_and_count(self):
        gold = build_gold(self.SOURCE)
        types = [n["type"] for n in gold["nodes"]]
        # a=stub_a() (block), if-gateway, b=stub_b() (block),
        # for-loop, c=stub_c() (block), return.
        assert types == ["block", "gateway", "block", "loop", "block", "return"]

    def test_node_code_matches_unparsed_statements(self):
        gold = build_gold(self.SOURCE)
        codes = {n["gold_id"]: n["code"] for n in gold["nodes"]}
        assert codes["g1"] == "a = stub_a()"
        assert codes["g2"] == "status == 'high'"
        assert codes["g3"] == "b = stub_b()"
        assert codes["g4"] == "for x in items"
        assert codes["g5"] == "c = stub_c()"
        assert codes["g6"] == "return 0"

    def test_edges_exact(self):
        gold = build_gold(self.SOURCE)
        edges = {(e["src_gold_id"], e["dst_gold_id"], e["label"]) for e in gold["edges"]}
        assert edges == {
            ("g1", "g2", "seq"),      # a = stub_a() -> if
            ("g2", "g3", "true"),     # if -> b = stub_b()
            ("g3", "g4", "seq"),      # b = stub_b() -> for (true branch falls through)
            # No else clause: the gateway itself is the "false" dangling exit,
            # forwarded by build_seq's generic sequential-fallthrough logic --
            # so this is labeled "seq", not "false" (there's no explicit
            # false-branch statement to point an edge at).
            ("g2", "g4", "seq"),
            ("g4", "g5", "enter"),    # for -> c = stub_c()
            ("g5", "g4", "back"),     # c = stub_c() -> for (back-edge)
            ("g4", "g6", "seq"),      # for -> return (loop node is its own fall-through exit)
        }

    def test_return_has_no_outgoing_edges(self):
        gold = build_gold(self.SOURCE)
        return_id = next(n["gold_id"] for n in gold["nodes"] if n["type"] == "return")
        assert all(e["src_gold_id"] != return_id for e in gold["edges"])

    def test_missing_function_returns_empty(self):
        gold = build_gold(self.SOURCE, function_name="does_not_exist")
        assert gold == {"nodes": [], "edges": []}
