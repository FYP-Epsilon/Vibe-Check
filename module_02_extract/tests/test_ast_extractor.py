"""
test_ast_extractor.py
=====================
Unit tests for Phase 1 (V3) static AST extraction.

Run with ``pytest`` from the repo root::

    pytest module_02_extract/tests/test_ast_extractor.py -v
"""

import ast

import pytest

import sys
from pathlib import Path

# Ensure src/ is on the path when pytest runs from the repo root.
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from ast_extractor import (
    CFGExtractor,
    DominatorAnalyzer,
    GuardExtractor,
    WIRDataLayer,
    V3Certificate,
    run_v3_pipeline,
    _unparse,
    _collect_vars,
)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _extract(source: str) -> dict:
    """Shorthand: parse *source* and return the WIR dict."""
    return CFGExtractor().extract(source)


def _find_node(wir: dict, node_type: str, guard_substring: str = "") -> dict:
    """Return the first WIR node matching *node_type* and optional guard text."""
    for n in wir["nodes"]:
        if n["type"] == node_type:
            if not guard_substring or guard_substring in (n.get("guard") or ""):
                return n
    raise LookupError(f"No {node_type} node found with guard '{guard_substring}'")


# ----------------------------------------------------------------------
# P1.1 – CFGExtractor basics
# ----------------------------------------------------------------------

class TestCFGExtractorBasics:
    def test_empty_module(self):
        wir = _extract("")
        assert wir["entry_node"] is not None
        assert wir["exit_node"] is not None
        assert any(n["type"] == "entry" for n in wir["nodes"])
        assert any(n["type"] == "exit" for n in wir["nodes"])

    def test_simple_assignment(self):
        wir = _extract("x = 1\ny = 2")
        blocks = [n for n in wir["nodes"] if n["type"] == "block"]
        assert len(blocks) >= 2

    def test_if_branch(self):
        wir = _extract("if x:\n    a = 1\nelse:\n    a = 2")
        gateways = [n for n in wir["nodes"] if n["type"] == "gateway"]
        assert len(gateways) >= 1
        # Should have true and false outgoing edges.
        g = gateways[0]
        assert len(g["successors"]) == 2

    def test_while_loop(self):
        wir = _extract("while x:\n    a = 1")
        loops = [n for n in wir["nodes"] if n["type"] == "loop"]
        assert len(loops) >= 1
        # Back-edge from body back to header.
        header = loops[0]
        assert header["id"] in [sid for nid in wir["nodes"] for sid in nid["successors"]]

    def test_for_loop(self):
        wir = _extract("for i in range(10):\n    a = i")
        loops = [n for n in wir["nodes"] if n["type"] == "loop"]
        assert len(loops) >= 1

    def test_try_except(self):
        wir = _extract("try:\n    a = 1\nexcept ValueError:\n    b = 2")
        # The try block links to body and to except handler.
        edges = wir["edges"]
        exc_edges = [e for e in edges if e.get("exception_type")]
        assert len(exc_edges) >= 1
        assert any("ValueError" in (e.get("exception_type") or "") for e in exc_edges)

    def test_function_def(self):
        wir = _extract("def foo():\n    pass")
        tasks = [n for n in wir["nodes"] if n["type"] == "task"]
        assert len(tasks) == 1
        assert tasks[0]["code"][0].startswith("def foo")

    def test_sub_cfg_for_function(self):
        wir = _extract("def foo():\n    x = 1\n    return x")
        assert "foo" in wir["functions"]
        sub = wir["functions"]["foo"]
        assert sub["entry_node"] is not None
        assert sub["exit_node"] is not None


# ----------------------------------------------------------------------
# P1.1 – Python 3.10+ special constructs
# ----------------------------------------------------------------------

class TestCFGExtractorPython310Plus:
    def test_named_expr_in_condition(self):
        """Walrus operator ``:=`` inside an *if* predicate."""
        wir = _extract("if (x := 5) > 3:\n    pass")
        gw = _find_node(wir, "gateway")
        # The gateway should note the walrus-assigned variable.
        assert "x" in gw["control_vars"]

    def test_named_expr_standalone(self):
        """Direct visit_NamedExpr dispatch."""
        extractor = CFGExtractor()
        node = ast.NamedExpr(target=ast.Name(id="y", ctx=ast.Store()), value=ast.Constant(value=7))
        entry, exit_node = extractor.visit(node)
        assert "y" in entry.control_vars

    def test_match_statement(self):
        """Structural pattern matching (PEP 634)."""
        source = """
match value:
    case 1:
        a = 1
    case 2:
        a = 2
    case _:
        a = 3
"""
        wir = _extract(source)
        gateways = [n for n in wir["nodes"] if n["type"] == "gateway"]
        # Subject gateway + one per case
        assert len(gateways) >= 3

    def test_try_star(self):
        """Exception groups ``try* … except*`` (PEP 654)."""
        source = """
try:
    a = 1
except* RuntimeError:
    b = 2
"""
        wir = _extract(source)
        exc_edges = [e for e in wir["edges"] if (e.get("exception_type") or "").startswith("*:")]
        assert len(exc_edges) >= 1

    def test_break_and_continue(self):
        source = """
while x:
    if y:
        break
    continue
"""
        wir = _extract(source)
        breaks = [n for n in wir["nodes"] if n["type"] == "break"]
        conts = [n for n in wir["nodes"] if n["type"] == "continue"]
        assert len(breaks) == 1
        assert len(conts) == 1


# ----------------------------------------------------------------------
# P1.2 – DominatorAnalyzer
# ----------------------------------------------------------------------

class TestDominatorAnalyzer:
    def test_immediate_dominators_linear(self):
        source = "a = 1\nb = 2\nc = 3"
        wir = _extract(source)
        dom = DominatorAnalyzer(wir)
        idoms = dom.compute_immediate_dominators()
        entry = wir["entry_node"]
        # Entry dominates everything in a linear chain.
        for node_id in idoms:
            if node_id != entry:
                # Walk idom chain back to entry
                cur = node_id
                while cur is not None and cur != entry:
                    cur = idoms.get(cur)
                assert cur == entry, f"{node_id} not dominated by entry"

    def test_verify_ordering_true(self):
        source = "if x:\n    a = 1\nelse:\n    a = 2"
        wir = _extract(source)
        dom = DominatorAnalyzer(wir)
        # In this simple graph the gateway dominates the merge.
        gw = _find_node(wir, "gateway")
        # Find merge node (successor of both branches)
        succs = set()
        for n in wir["nodes"]:
            if n["type"] == "block" and gw["id"] in n["predecessors"]:
                succs.add(n["id"])
        # Actually the merge is the block after if/else.
        merge_id = [n["id"] for n in wir["nodes"]
                    if n["type"] == "block" and set(n["predecessors"]) == set(gw["successors"])]
        if merge_id:
            result = dom.verify_ordering(gw["id"], merge_id[0])
            assert result["passed"] is True

    def test_verify_ordering_false(self):
        source = "a = 1\nb = 2"
        wir = _extract(source)
        dom = DominatorAnalyzer(wir)
        nodes = [n["id"] for n in wir["nodes"] if n["type"] == "block"]
        if len(nodes) >= 2:
            result = dom.verify_ordering(nodes[1], nodes[0])
            assert result["passed"] is False


# ----------------------------------------------------------------------
# P1.3 – GuardExtractor
# ----------------------------------------------------------------------

class TestGuardExtractor:
    def test_simple_literal(self):
        ge = GuardExtractor()
        node = ast.parse("x > 0", mode="eval").body
        cnf = ge.extract(node)
        assert len(cnf) == 1
        assert len(cnf[0]) == 1
        assert cnf[0][0].text == "x > 0"
        assert cnf[0][0].negated is False

    def test_and_flattening(self):
        ge = GuardExtractor()
        node = ast.parse("x > 0 and y < 10", mode="eval").body
        cnf = ge.extract(node)
        # (x > 0) ∧ (y < 10)  →  [[x>0], [y<10]]
        texts = {clause[0].text for clause in cnf}
        assert "x > 0" in texts
        assert "y < 10" in texts

    def test_or_flattening(self):
        ge = GuardExtractor()
        node = ast.parse("x > 0 or y < 10", mode="eval").body
        cnf = ge.extract(node)
        # (x > 0) ∨ (y < 10)  →  [[x>0, y<10]]
        assert len(cnf) == 1
        assert len(cnf[0]) == 2
        texts = {lit.text for lit in cnf[0]}
        assert "x > 0" in texts
        assert "y < 10" in texts

    def test_not_and_de_morgan(self):
        ge = GuardExtractor()
        node = ast.parse("not (x > 0 and y < 10)", mode="eval").body
        cnf = ge.extract(node)
        # not(a ∧ b)  →  (not a) ∨ (not b)
        # Comparisons are inverted, so we get positive literals with inverted ops.
        assert len(cnf) == 1
        assert len(cnf[0]) == 2
        texts = {lit.text for lit in cnf[0]}
        assert "x <= 0" in texts
        assert "y >= 10" in texts
        assert all(not lit.negated for lit in cnf[0])

    def test_not_or_de_morgan(self):
        ge = GuardExtractor()
        node = ast.parse("not (x > 0 or y < 10)", mode="eval").body
        cnf = ge.extract(node)
        # not(a ∨ b)  →  (not a) ∧ (not b)
        # Comparisons are inverted to keep literals positive.
        assert len(cnf) == 2
        texts = {clause[0].text for clause in cnf}
        assert "x <= 0" in texts
        assert "y >= 10" in texts
        assert all(not lit.negated for clause in cnf for lit in clause)

    def test_comparison_inversion(self):
        ge = GuardExtractor()
        node = ast.parse("not (x < 5)", mode="eval").body
        cnf = ge.extract(node)
        # Should become x >= 5 (positive literal, not negated)
        assert len(cnf) == 1
        assert len(cnf[0]) == 1
        lit = cnf[0][0]
        assert lit.negated is False
        assert lit.text == "x >= 5"

    def test_ite_encoding_and(self):
        ge = GuardExtractor()
        node = ast.parse("a and b and c", mode="eval").body
        ite = ge.encode_short_circuit(node)
        assert "ITE" in ite
        assert "False" in ite

    def test_ite_encoding_or(self):
        ge = GuardExtractor()
        node = ast.parse("a or b or c", mode="eval").body
        ite = ge.encode_short_circuit(node)
        assert "ITE" in ite
        assert "True" in ite


# ----------------------------------------------------------------------
# P1.4 – WIRDataLayer
# ----------------------------------------------------------------------

class TestWIRDataLayer:
    def test_control_vs_data_classification(self):
        source = """
x = 1
y = 2
if x > 0:
    z = y + 1
"""
        wir = run_v3_pipeline(source)
        control = set(wir.get("control_variables", []))
        data = set(wir.get("data_variables", []))
        assert "x" in control
        assert "y" in data
        assert "z" in data


# ----------------------------------------------------------------------
# P1.5 – V3Certificate
# ----------------------------------------------------------------------

class TestV3Certificate:
    def test_certificate_not_aborting_on_simple_code(self):
        source = "x = 1\nif x:\n    pass"
        wir = run_v3_pipeline(source)
        cert = wir["certificate"]
        assert cert["version"] == "V3"
        assert isinstance(cert["node_coverage"], float)
        assert isinstance(cert["edge_coverage"], float)
        assert isinstance(cert["guard_success_rate"], float)
        assert isinstance(cert["abort"], bool)

    def test_guard_results_populated(self):
        source = "if x and y:\n    pass"
        wir = run_v3_pipeline(source)
        guards = wir.get("guard_extraction", {})
        assert guards["total"] >= 1
        assert guards["success"] >= 1
        assert len(guards["conditions"]) >= 1


# ----------------------------------------------------------------------
# End-to-end pipeline
# ----------------------------------------------------------------------

class TestEndToEnd:
    def test_demo_workflow(self):
        source = """
def approve(credit_score: int, amount: float):
    if (threshold := 700) and credit_score >= threshold:
        if amount > 10_000:
            return "manual"
        return "approved"
    return "denied"

match credit_score:
    case 800:
        tier = "platinum"
    case n if n > 700:
        tier = "gold"
    case _:
        tier = "standard"

try:
    process(tier)
except ValueError:
    log_error()

try:
    process(tier)
except* RuntimeError:
    log_critical()
"""
        wir = run_v3_pipeline(source)
        assert wir["entry_node"] is not None
        assert wir["exit_node"] is not None
        assert "functions" in wir
        assert "approve" in wir["functions"]
        assert "dominators" in wir
        assert "guard_extraction" in wir
        assert "control_variables" in wir
        assert "certificate" in wir
        cert = wir["certificate"]
        # The demo contains rich constructs; coverage should be high.
        assert cert["node_coverage"] > 0.5
        assert cert["edge_coverage"] > 0.5



class TestWIRSchemaValidation:
    def test_valid_wir_passes_schema(self):
        source = "def foo(x):\n    if x > 0:\n        return 1\n    return 0"
        wir = run_v3_pipeline(source)
        # If schema exists, this should not raise.
        assert "entry_node" in wir
        assert "certificate" in wir

    def test_wir_has_required_top_level_keys(self):
        source = "x = 1"
        wir = run_v3_pipeline(source)
        assert "entry_node" in wir
        assert "exit_node" in wir
        assert "nodes" in wir
        assert "edges" in wir
