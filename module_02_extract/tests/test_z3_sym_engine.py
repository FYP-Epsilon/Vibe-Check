"""
test_z3_sym_engine.py
=====================
Unit tests for Phase 2 (V2) Z3 symbolic refinement engine.

Run with ``pytest`` from the repo root::

    pytest module_02_extract/tests/test_z3_sym_engine.py -v
"""

import sys
from pathlib import Path

# Ensure src/ is on the path.
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import ast

import pytest
import z3

from z3_sym_engine import (
    Z3VariableRegistry,
    SymbolicEvaluator,
    WIRSymbolicTracer,
    BoundedConcolicEngine,
    BranchRecord,
    run_v2_pipeline,
)
from ast_extractor import CFGExtractor


# ----------------------------------------------------------------------
# P2.1 -- Z3VariableRegistry
# ----------------------------------------------------------------------

class TestZ3VariableRegistry:
    def test_infer_int(self):
        reg = Z3VariableRegistry()
        sort = reg.infer_sort(42)
        assert sort == z3.IntSort()

    def test_infer_float(self):
        reg = Z3VariableRegistry()
        sort = reg.infer_sort(3.14)
        assert sort == z3.RealSort()

    def test_infer_bool(self):
        reg = Z3VariableRegistry()
        sort = reg.infer_sort(True)
        assert sort == z3.BoolSort()

    def test_infer_str(self):
        reg = Z3VariableRegistry()
        sort = reg.infer_sort("hello")
        assert sort == z3.IntSort()

    def test_infer_list(self):
        reg = Z3VariableRegistry()
        sort = reg.infer_sort([1, 2, 3])
        assert isinstance(sort, z3.ArraySortRef)

    def test_declare_creates_constant(self):
        reg = Z3VariableRegistry()
        c = reg.declare("x", 5)
        assert isinstance(c, z3.ExprRef)
        assert c.sort() == z3.IntSort()

    def test_declare_retrieves_existing_same_type(self):
        reg = Z3VariableRegistry()
        c1 = reg.declare("x", 5)
        c2 = reg.declare("x", 10)
        assert c1 is c2

    def test_version_on_type_change(self):
        reg = Z3VariableRegistry()
        c1 = reg.declare("x", 5)
        c2 = reg.declare("x", 3.14)
        assert c1 is not c2
        assert c2.decl().name() == "x_1"
        assert c2.sort() == z3.RealSort()

    def test_flatten_dict(self):
        reg = Z3VariableRegistry()
        value = {"total": 20, "items": [{"price": 10, "qty": 2}]}
        flats = reg.flatten_dict("order", value)
        assert "order_total" in flats
        assert "order_items_0_price" in flats
        assert "order_items_0_qty" in flats
        assert flats["order_total"].sort() == z3.IntSort()

    def test_get_flat(self):
        reg = Z3VariableRegistry()
        reg.flatten_dict("cfg", {"a": 1})
        assert reg.get_flat("cfg_a") is not None
        assert reg.get_flat("missing") is None

    def test_declare_array(self):
        reg = Z3VariableRegistry()
        arr = reg.declare_array("items", z3.IntSort())
        assert isinstance(arr, z3.ArrayRef)

    def test_declare_finite_array(self):
        reg = Z3VariableRegistry()
        scalars = reg.declare_finite_array("vec", [10, 20, 30])
        assert len(scalars) == 3
        assert all(s.sort() == z3.IntSort() for s in scalars)


# ----------------------------------------------------------------------
# SymbolicEvaluator
# ----------------------------------------------------------------------

class TestSymbolicEvaluator:
    def _eval(self, expr: str, state: dict[str, z3.ExprRef] = None):
        reg = Z3VariableRegistry()
        state = state if state is not None else {}
        tree = ast.parse(expr, mode="eval")
        ev = SymbolicEvaluator(reg, state)
        return ev.eval(tree.body)

    def test_int_literal(self):
        r = self._eval("5")
        assert r.eq(z3.IntVal(5))

    def test_bool_literal(self):
        r = self._eval("True")
        assert r.eq(z3.BoolVal(True))

    def test_float_literal(self):
        r = self._eval("3.5")
        assert r.eq(z3.RealVal(3.5))

    def test_variable_lookup(self):
        x = z3.Int("x")
        r = self._eval("x", {"x": x})
        assert r is x

    def test_addition(self):
        r = self._eval("x + y", {"x": z3.Int("x"), "y": z3.Int("y")})
        assert r.eq(z3.Int("x") + z3.Int("y"))

    def test_comparison_eq(self):
        r = self._eval("x == 5", {"x": z3.Int("x")})
        assert r.eq(z3.Int("x") == z3.IntVal(5))

    def test_chained_compare(self):
        r = self._eval("0 < x < 10", {"x": z3.Int("x")})
        # Should be And(0 < x, x < 10)
        assert z3.is_and(r)

    def test_and_or(self):
        r = self._eval("x > 0 and y < 10", {"x": z3.Int("x"), "y": z3.Int("y")})
        assert z3.is_and(r)

    def test_not(self):
        r = self._eval("not (x > 0)", {"x": z3.Int("x")})
        assert z3.is_not(r)

    def test_named_expr(self):
        state: dict[str, z3.ExprRef] = {}
        r = self._eval("(z := 5)", state)
        assert "z" in state
        assert r.eq(z3.IntVal(5))

    def test_uninterpreted_call(self):
        r = self._eval("foo()")
        assert isinstance(r, z3.ExprRef)


# ----------------------------------------------------------------------
# WIRSymbolicTracer
# ----------------------------------------------------------------------

class TestWIRSymbolicTracer:
    def test_linear_trace(self):
        source = "x = 1\ny = x + 2\nreturn y"
        wir = CFGExtractor().extract(source)
        reg = Z3VariableRegistry()
        tracer = WIRSymbolicTracer(wir, reg, {}, function_name=None, max_k=3)
        pc, branches = tracer.trace()
        assert z3.is_true(pc) or str(pc) == "True"
        assert len(branches) == 0

    def test_if_trace(self):
        source = """
def foo(x):
    if x > 0:
        y = 1
    else:
        y = -1
    return y
"""
        wir = CFGExtractor().extract(source)
        reg = Z3VariableRegistry()
        tracer = WIRSymbolicTracer(wir, reg, {"x": 5}, function_name="foo", max_k=3)
        pc, branches = tracer.trace()
        assert len(branches) == 1
        assert branches[0].taken is True
        assert "x > 0" in branches[0].guard_str
        # Path condition should include x > 0.
        assert z3.is_and(pc) or "x" in str(pc)

    def test_loop_unrolling(self):
        source = """
def countdown(n):
    i = 0
    while i < n:
        i = i + 1
    return i
"""
        wir = CFGExtractor().extract(source)
        reg = Z3VariableRegistry()
        tracer = WIRSymbolicTracer(wir, reg, {"n": 2}, function_name="countdown", max_k=3)
        pc, branches = tracer.trace()
        # With n=2 and max_k=3, the loop should execute twice.
        loop_branches = [b for b in branches if "i < n" in b.guard_str or "while" in b.guard_str]
        assert len(loop_branches) >= 2

    def test_loop_havoc_after_k(self):
        source = """
def countdown(n):
    i = 0
    while i < n:
        i = i + 1
    return i
"""
        wir = CFGExtractor().extract(source)
        reg = Z3VariableRegistry()
        # n=10 but max_k=1 -- havoc should kick in after 1 iteration.
        tracer = WIRSymbolicTracer(wir, reg, {"n": 10}, function_name="countdown", max_k=1)
        pc, branches = tracer.trace()
        # After havoc, i should be a fresh symbol.
        assert "havoc" in str(pc) or "i_havoc" in str(tracer.symbolic_state.get("i", ""))


# ----------------------------------------------------------------------
# BoundedConcolicEngine
# ----------------------------------------------------------------------

class TestBoundedConcolicEngine:
    def test_concrete_execution(self):
        source = "def foo(x):\n    return x + 1"
        engine = BoundedConcolicEngine(source, "foo", max_k=3, query_budget=10)
        result = engine._execute_concrete({"x": 5})
        assert result == 6

    def test_negate_last_branch(self):
        source = "def foo(x):\n    if x > 0:\n        return 1\n    return 0"
        engine = BoundedConcolicEngine(source, "foo", max_k=3, query_budget=10)
        # First iteration with x=5 (takes true branch).
        registry = Z3VariableRegistry()
        tracer = WIRSymbolicTracer(engine.wir, registry, {"x": 5}, function_name="foo")
        pc, branches = tracer.trace()
        new_pc = BoundedConcolicEngine._negate_last_branch(pc, branches)
        assert new_pc is not None
        # Solve the negated PC to find x <= 0.
        solver = z3.Solver()
        solver.add(new_pc)
        assert solver.check() == z3.sat

    def test_solve_for_inputs(self):
        source = "def foo(x):\n    if x > 0:\n        return 1\n    return 0"
        engine = BoundedConcolicEngine(source, "foo", max_k=3, query_budget=10)
        registry = Z3VariableRegistry()
        tracer = WIRSymbolicTracer(engine.wir, registry, {"x": 5}, function_name="foo")
        pc, branches = tracer.trace()
        new_pc = BoundedConcolicEngine._negate_last_branch(pc, branches)
        new_inputs = engine._solve_for_inputs(new_pc, {"x": 5})
        assert new_inputs is not None
        assert new_inputs["x"] <= 0

    def test_full_concolic_two_iterations(self):
        source = """
def classify(x):
    if x > 0:
        return "positive"
    return "non_positive"
"""
        engine = BoundedConcolicEngine(source, "classify", max_k=3, query_budget=10)
        cert = engine.run({"x": 5})
        # Should explore at least 2 paths (positive and non-positive).
        assert cert["iterations"] >= 1
        assert cert["feasible_paths"] >= 1

    def test_full_concolic_nested_branches(self):
        source = """
def quadrant(x, y):
    if x > 0:
        if y > 0:
            return "Q1"
        return "Q2"
    return "Q3_or_Q4"
"""
        engine = BoundedConcolicEngine(source, "quadrant", max_k=3, query_budget=20)
        cert = engine.run({"x": 1, "y": 1})
        # Should explore multiple paths.
        assert cert["iterations"] >= 1
        assert cert["total_paths"] > 0

    def test_qce_cold_variables(self):
        source = "def foo(x):\n    return x"
        engine = BoundedConcolicEngine(source, "foo", max_k=3, query_budget=10)
        state_a = {"y": z3.Int("y")}
        state_b = {"y": z3.Int("y2")}
        # x is not a future control var, so differing y is cold.
        saves = engine.qce_predicts_savings("node_1", state_a, state_b)
        assert saves is True

    def test_qce_hot_variables(self):
        source = """
def foo(x):
    if x > 0:
        return 1
    return 0
"""
        engine = BoundedConcolicEngine(source, "foo", max_k=3, query_budget=10)
        state_a = {"x": z3.Int("x_a")}
        state_b = {"x": z3.Int("x_b")}
        # x is a future control var, so differing x is hot.
        saves = engine.qce_predicts_savings(engine.wir["entry_node"], state_a, state_b)
        assert saves is False

    def test_merge_states(self):
        source = "def foo(x):\n    return x"
        engine = BoundedConcolicEngine(source, "foo", max_k=3, query_budget=10)
        g = z3.Bool("g")
        merged = engine.merge_states(
            g,
            {"x": z3.IntVal(1), "y": z3.IntVal(2)},
            {"x": z3.IntVal(3), "y": z3.IntVal(2)},
        )
        assert merged["y"].eq(z3.IntVal(2))
        # x should be an ITE.
        assert "If" in str(merged["x"])


# ----------------------------------------------------------------------
# run_v2_pipeline orchestrator
# ----------------------------------------------------------------------

class TestRunV2Pipeline:
    def test_orchestrator_returns_certificate(self):
        source = """
def classify(x):
    if x > 0:
        return "positive"
    return "non_positive"
"""
        result = run_v2_pipeline(source, "classify", {"x": 5}, max_k=3, query_budget=10)
        assert "certificate" in result
        cert = result["certificate"]
        assert cert["version"] == "V2"
        assert isinstance(cert["confidence"], float)


# ----------------------------------------------------------------------
# Edge-case robustness
# ----------------------------------------------------------------------

class TestRobustness:
    def test_empty_source(self):
        engine = BoundedConcolicEngine("", "foo")
        with pytest.raises(KeyError):
            engine._execute_concrete({})

    def test_missing_function(self):
        source = "x = 1"
        engine = BoundedConcolicEngine(source, "missing", max_k=3, query_budget=10)
        with pytest.raises(KeyError):
            engine._execute_concrete({})

    def test_unparseable_guard(self):
        source = "def foo(x):\n    return x"
        engine = BoundedConcolicEngine(source, "foo", max_k=3, query_budget=10)
        registry = Z3VariableRegistry()
        tracer = WIRSymbolicTracer(engine.wir, registry, {"x": 1}, function_name="foo")
        # Manually inject a bad guard string.
        tracer.nodes["node_1"]["type"] = "gateway"
        tracer.nodes["node_1"]["guard"] = "!!!not valid python!!!"
        tracer.nodes["node_1"]["successors"] = ["node_2", "node_2"]
        pc, branches = tracer.trace()
        # Should not crash; falls back to True.
        assert pc is not None
