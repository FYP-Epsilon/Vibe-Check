"""
test_dynamic_tracer.py
======================
Unit tests for Phase 3 (V1) dynamic tracing & differential execution.

Run with ``pytest`` from the repo root::

    pytest module_02_extract/tests/test_dynamic_tracer.py -v
"""

import sys
import types
from pathlib import Path

# Ensure src/ is on the path.
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import pytest

from dynamic_tracer import (
    WIRTraceCollector,
    WIRReferenceInterpreter,
    DifferentialComparator,
    RandomizedDifferentialTester,
    MultiModalCertificateComposer,
    run_v1_pipeline,
)


# ----------------------------------------------------------------------
# Mocks for sys.settrace frame objects
# ----------------------------------------------------------------------

class MockCode:
    def __init__(self, filename: str, name: str):
        self.co_filename = filename
        self.co_name = name


class MockFrame:
    def __init__(
        self,
        filename: str,
        func_name: str,
        lineno: int,
        locals_dict: dict,
    ):
        self.f_code = MockCode(filename, func_name)
        self.f_lineno = lineno
        self.f_locals = locals_dict


# ----------------------------------------------------------------------
# P3.1 -- WIRTraceCollector (mock-frame unit tests)
# ----------------------------------------------------------------------

class TestWIRTraceCollectorMock:
    def test_ignores_non_target_file(self):
        coll = WIRTraceCollector(
            target_file="/foo.py",
            task_patterns=["task"],
            branch_lines={10},
            control_variables=["x"],
        )
        frame = MockFrame("/bar.py", "task_a", 10, {"x": 1})
        result = coll.trace_callback(frame, "line", None)
        assert result is None
        assert len(coll.trace_log) == 0

    def test_records_task_entry(self):
        coll = WIRTraceCollector(
            target_file="/foo.py",
            task_patterns=["task"],
            branch_lines=set(),
            control_variables=["x"],
        )
        frame = MockFrame("/foo.py", "task_a", 5, {"x": 42})
        result = coll.trace_callback(frame, "call", None)
        assert callable(result)
        assert len(coll.trace_log) == 1
        assert coll.trace_log[0]["event"] == "task_entry"
        assert coll.trace_log[0]["function"] == "task_a"

    def test_records_task_exit(self):
        coll = WIRTraceCollector(
            target_file="/foo.py",
            task_patterns=["task"],
            branch_lines=set(),
            control_variables=["x"],
        )
        coll.trace_callback(MockFrame("/foo.py", "task_a", 5, {"x": 1}), "call", None)
        frame = MockFrame("/foo.py", "task_a", 8, {"x": 99})
        result = coll.trace_callback(frame, "return", "done")
        assert result is None
        assert len(coll.trace_log) == 2
        assert coll.trace_log[1]["event"] == "task_exit"
        assert coll.trace_log[1]["return_value"] == "done"

    def test_records_branch_point(self):
        coll = WIRTraceCollector(
            target_file="/foo.py",
            task_patterns=["task"],
            branch_lines={20},
            control_variables=["x"],
        )
        frame = MockFrame("/foo.py", "foo", 20, {"x": 7})
        result = coll.trace_callback(frame, "line", None)
        assert callable(result)
        assert len(coll.trace_log) == 1
        assert coll.trace_log[0]["event"] == "branch_point"

    def test_observables_serialization(self):
        coll = WIRTraceCollector(
            target_file="/foo.py",
            task_patterns=["task"],
            branch_lines={20},
            control_variables=["x", "y"],
        )
        frame = MockFrame("/foo.py", "foo", 20, {"x": 7, "y": [1, 2, 3]})
        coll.trace_callback(frame, "line", None)
        obs = coll.trace_log[0]["observables"]
        assert "x" in obs
        assert obs["x"]["type"] == "int"
        assert "hash" in obs["x"]
        assert obs["y"]["type"] == "list"

    def test_exception_event_capture(self):
        coll = WIRTraceCollector(
            target_file="/foo.py",
            task_patterns=["task"],
            branch_lines=set(),
            control_variables=[],
        )
        try:
            raise ValueError("boom")
        except Exception:
            exc_type, exc_val, exc_tb = sys.exc_info()
            frame = MockFrame("/foo.py", "foo", 10, {})
            result = coll.trace_callback(frame, "exception", (exc_type, exc_val, exc_tb))
            assert callable(result)
            assert len(coll.exception_records) == 1
            assert coll.exception_records[0]["exception_type"] == "ValueError"

    def test_mutation_audit_outside_task(self):
        coll = WIRTraceCollector(
            target_file="/foo.py",
            task_patterns=["task"],
            branch_lines={10},
            control_variables=[],
            state_variables=["loan_status"],
        )
        # First line event establishes baseline.
        coll.trace_callback(MockFrame("/foo.py", "helper", 10, {"loan_status": "pending"}), "line", None)
        # Second line event changes the state variable while NOT inside a task.
        coll.trace_callback(MockFrame("/foo.py", "helper", 11, {"loan_status": "approved"}), "line", None)
        assert len(coll.mutation_warnings) == 1
        assert coll.mutation_warnings[0]["variable"] == "loan_status"

    def test_mutation_audit_inside_task_is_allowed(self):
        coll = WIRTraceCollector(
            target_file="/foo.py",
            task_patterns=["task"],
            branch_lines={10},
            control_variables=[],
            state_variables=["loan_status"],
        )
        coll.trace_callback(MockFrame("/foo.py", "task_a", 5, {"loan_status": "pending"}), "call", None)
        coll.trace_callback(MockFrame("/foo.py", "task_a", 10, {"loan_status": "approved"}), "line", None)
        assert len(coll.mutation_warnings) == 0

    def test_dict_iteration_hashing(self):
        coll = WIRTraceCollector(
            target_file="/foo.py",
            task_patterns=["task"],
            branch_lines={10},
            control_variables=["k"],
            for_loop_lines={10},
        )
        frame = MockFrame("/foo.py", "foo", 10, {"k": "alpha"})
        coll.trace_callback(frame, "line", None)
        info = coll.trace_log[0].get("iteration_info")
        assert info is not None
        assert info["iteration_index"] == 1
        assert info["key_hash"] is not None


# ----------------------------------------------------------------------
# P3.1 -- WIRTraceCollector (integration with real sys.settrace)
# ----------------------------------------------------------------------

class TestWIRTraceCollectorIntegration:
    def test_full_trace_of_simple_function(self):
        source = """
def task_process(x):
    if x > 0:
        return x * 2
    return x
"""
        ns = {}
        exec(compile(source, "<string>", "exec"), ns)
        func = ns["task_process"]

        coll = WIRTraceCollector(
            target_file="<string>",
            task_patterns=["task"],
            branch_lines={3},
            control_variables=["x"],
        )
        coll.start_tracing()
        try:
            func(5)
        finally:
            coll.stop_tracing()

        events = [e["event"] for e in coll.trace_log]
        assert "task_entry" in events
        assert "task_exit" in events
        assert "branch_point" in events

    def test_exception_capture_integration(self):
        source = """
def task_fail(x):
    raise ValueError("oops")
"""
        ns = {}
        exec(compile(source, "<string>", "exec"), ns)
        func = ns["task_fail"]

        coll = WIRTraceCollector(
            target_file="<string>",
            task_patterns=["task"],
            branch_lines=set(),
            control_variables=[],
        )
        coll.start_tracing()
        try:
            try:
                func(1)
            except ValueError:
                pass
        finally:
            coll.stop_tracing()

        exc_events = [e for e in coll.trace_log if e["event"] == "exception"]
        assert len(exc_events) >= 1
        assert exc_events[0]["exception_type"] == "ValueError"


# ----------------------------------------------------------------------
# P3.2 -- WIRReferenceInterpreter
# ----------------------------------------------------------------------

class TestWIRReferenceInterpreter:
    def _make_wir(self, nodes: list[dict], entry: str, exit_node: str) -> dict:
        return {"nodes": nodes, "entry_node": entry, "exit_node": exit_node}

    def test_linear_execution(self):
        wir = self._make_wir(
            [
                {"id": "e", "type": "entry", "successors": ["b"]},
                {"id": "b", "type": "block", "code": ["x = 1"], "successors": ["x"]},
                {"id": "x", "type": "exit", "successors": []},
            ],
            "e",
            "x",
        )
        interp = WIRReferenceInterpreter(wir)
        trace = interp.execute({})
        assert len(trace) == 0  # no tasks or gateways

    def test_gateway_branching(self):
        wir = self._make_wir(
            [
                {"id": "e", "type": "entry", "successors": ["g"]},
                {
                    "id": "g",
                    "type": "gateway",
                    "guard": "x > 0",
                    "code": ["gateway"],
                    "successors": ["t", "f"],
                },
                {"id": "t", "type": "block", "code": ["y = 1"], "successors": ["x"]},
                {"id": "f", "type": "block", "code": ["y = -1"], "successors": ["x"]},
                {"id": "x", "type": "exit", "successors": []},
            ],
            "e",
            "x",
        )
        interp = WIRReferenceInterpreter(wir)
        trace = interp.execute({"x": 5})
        assert any(e["event"] == "branch_point" and e["taken_branch"] is True for e in trace)

        interp2 = WIRReferenceInterpreter(wir)
        trace2 = interp2.execute({"x": -5})
        assert any(e["event"] == "branch_point" and e["taken_branch"] is False for e in trace2)

    def test_task_trace(self):
        wir = self._make_wir(
            [
                {"id": "e", "type": "entry", "successors": ["t"]},
                {"id": "t", "type": "task", "code": ["do_work"], "successors": ["x"]},
                {"id": "x", "type": "exit", "successors": []},
            ],
            "e",
            "x",
        )
        interp = WIRReferenceInterpreter(wir)
        trace = interp.execute({})
        assert trace[0]["event"] == "task_entry"
        assert trace[1]["event"] == "task_exit"

    def test_loop_bounded(self):
        wir = self._make_wir(
            [
                {"id": "e", "type": "entry", "successors": ["l"]},
                {
                    "id": "l",
                    "type": "loop",
                    "guard": "i < 3",
                    "successors": ["b", "x"],
                },
                {"id": "b", "type": "block", "code": ["i = i + 1"], "successors": ["l"]},
                {"id": "x", "type": "exit", "successors": []},
            ],
            "e",
            "x",
        )
        interp = WIRReferenceInterpreter(wir)
        trace = interp.execute({"i": 0})
        branch_events = [e for e in trace if e["event"] == "branch_point"]
        # Should evaluate loop condition at least 3 times (enter 3x, exit 1x)
        assert len(branch_events) >= 2


# ----------------------------------------------------------------------
# P3.3 -- DifferentialComparator
# ----------------------------------------------------------------------

class TestDifferentialComparator:
    def test_identical_traces(self):
        actual = [
            {"event": "task_entry", "function": "foo"},
            {"event": "task_exit", "function": "foo"},
        ]
        expected = [
            {"event": "task_entry", "task": "foo"},
            {"event": "task_exit", "task": "foo"},
        ]
        comp = DifferentialComparator(actual, expected)
        result = comp.compare()
        assert result["similarity_score"] == 1.0
        assert result["passed"] is True

    def test_stutter_elimination(self):
        """Gotcha 1: helper functions (silent steps) are ignored."""
        actual = [
            {"event": "task_entry", "function": "helper"},  # silent step
            {"event": "task_entry", "function": "foo"},
            {"event": "task_exit", "function": "foo"},
        ]
        expected = [
            {"event": "task_entry", "task": "foo"},
            {"event": "task_exit", "task": "foo"},
        ]
        comp = DifferentialComparator(actual, expected)
        result = comp.compare()
        assert result["similarity_score"] == 1.0
        assert result["passed"] is True

    def test_divergent_traces(self):
        actual = [
            {"event": "task_entry", "function": "foo"},
            {"event": "task_exit", "function": "foo"},
        ]
        expected = [
            {"event": "task_entry", "task": "bar"},
            {"event": "task_exit", "task": "bar"},
        ]
        comp = DifferentialComparator(actual, expected)
        result = comp.compare()
        assert result["similarity_score"] == 0.0
        assert result["passed"] is False
        assert len(result["divergence_points"]) > 0

    def test_partial_match(self):
        actual = [
            {"event": "task_entry", "function": "foo"},
            {"event": "branch_point", "function": "foo", "taken_branch": True},
            {"event": "task_exit", "function": "foo"},
        ]
        expected = [
            {"event": "task_entry", "task": "foo"},
            {"event": "task_exit", "task": "foo"},
        ]
        comp = DifferentialComparator(actual, expected)
        result = comp.compare()
        # 2 out of 3 match after normalisation
        assert result["similarity_score"] == pytest.approx(2 / 3, 0.01)

    def test_lcs_correctness(self):
        a = [("A",), ("B",), ("C",)]
        b = [("A",), ("C",), ("D",)]
        assert DifferentialComparator._lcs(a, b) == 2


# ----------------------------------------------------------------------
# P3.4 -- RandomizedDifferentialTester
# ----------------------------------------------------------------------

class TestRandomizedDifferentialTester:
    def test_generates_certificate(self):
        source = """
def classify(x, y):
    if x > 0:
        if y > 0:
            return "Q1"
        return "Q2"
    return "Q3_or_Q4"
"""
        from ast_extractor import CFGExtractor
        wir = CFGExtractor().extract(source)
        func_wir = wir["functions"]["classify"]

        tester = RandomizedDifferentialTester(
            source=source,
            function_name="classify",
            wir=func_wir,
            task_patterns=["classify"],
            branch_lines={3, 4},
            control_variables=["x", "y"],
            n_runs=10,
            seed=42,
        )
        cert = tester.run()
        assert cert["version"] == "V1"
        assert 0 <= cert["confidence"] <= 1.0
        assert cert["total_runs"] == 10

    def test_input_coverage_score(self):
        source = "def foo(x):\n    return x"
        from ast_extractor import CFGExtractor
        wir = CFGExtractor().extract(source)
        func_wir = wir["functions"]["foo"]

        tester = RandomizedDifferentialTester(
            source=source,
            function_name="foo",
            wir=func_wir,
            task_patterns=["foo"],
            branch_lines=set(),
            control_variables=["x"],
            n_runs=5,
            seed=123,
        )
        cert = tester.run()
        assert cert["input_coverage_score"] <= 1.0
        assert cert["input_coverage_score"] > 0.0


# ----------------------------------------------------------------------
# P3.5 -- MultiModalCertificateComposer
# ----------------------------------------------------------------------

class TestMultiModalCertificateComposer:
    def test_all_high_confidence_passes(self):
        v1 = {"confidence": 0.99}
        v2 = {"confidence": 0.98}
        v3 = {"confidence": 0.97}
        result = MultiModalCertificateComposer.compose(v1, v2, v3)
        assert result["passed"] is True
        assert result["combined_confidence"] > 0.95

    def test_low_confidence_fails(self):
        v1 = {"confidence": 0.5}
        v2 = {"confidence": 0.5}
        v3 = {"confidence": 0.5}
        result = MultiModalCertificateComposer.compose(v1, v2, v3)
        assert result["passed"] is False
        assert result["combined_confidence"] < 0.95

    def test_combined_formula(self):
        v1 = {"confidence": 0.9}
        v2 = {"confidence": 0.0}
        v3 = {"confidence": 0.0}
        result = MultiModalCertificateComposer.compose(v1, v2, v3)
        assert result["combined_confidence"] == pytest.approx(0.9, 0.001)

    def test_v3_confidence_excluded_from_combined_formula(self):
        """V3 is extraction fidelity, not a correctness signal -- it must not
        enter the OR-composition. combined_confidence depends only on v1/v2."""
        v1 = {"confidence": 0.8}
        v2 = {"confidence": 0.5}
        low_v3 = {"confidence": 0.1, "abort": False}
        high_v3 = {"confidence": 0.99, "abort": False}
        result_low = MultiModalCertificateComposer.compose(v1, v2, low_v3)
        result_high = MultiModalCertificateComposer.compose(v1, v2, high_v3)
        expected = 1.0 - (1.0 - 0.8) * (1.0 - 0.5)
        assert result_low["combined_confidence"] == pytest.approx(expected, 0.001)
        assert result_high["combined_confidence"] == pytest.approx(expected, 0.001)

    def test_v3_abort_gates_regardless_of_v1_v2(self):
        """A low-fidelity WIR (V3 abort) means V1/V2 ran against an unfaithful
        model -- the result must fail even when v1/v2 are both saturated."""
        v1 = {"confidence": 1.0}
        v2 = {"confidence": 1.0}
        v3 = {"confidence": 0.5, "abort": True}
        result = MultiModalCertificateComposer.compose(v1, v2, v3)
        assert result["combined_confidence"] == pytest.approx(1.0, 0.001)
        assert result["passed"] is False
        assert result["v3_abort"] is True


# ----------------------------------------------------------------------
# Orchestrator
# ----------------------------------------------------------------------

class TestRunV1Pipeline:
    def test_end_to_end(self):
        source = "def foo(x):\n    if x > 0:\n        return 1\n    return 0"
        from ast_extractor import CFGExtractor
        wir = CFGExtractor().extract(source)
        func_wir = wir["functions"]["foo"]

        cert = run_v1_pipeline(
            source=source,
            function_name="foo",
            wir=func_wir,
            task_patterns=["foo"],
            branch_lines={2},
            control_variables=["x"],
            n_runs=5,
            seed=7,
        )
        assert cert["version"] == "V1"
        assert isinstance(cert["confidence"], float)
