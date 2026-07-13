"""
Comprehensive test suite for the 4-phase Equivalence Checking Engine.
=====================================================================
Tests cover:
    - Phase A: Quality gate, LTS lifting, loop unrolling, nested functions
    - Phase B: Tarjan SCC, divergence detection, partition refinement, bisimilarity
    - Phase C: Clustering, representative selection, singleton anomalies
    - Phase D: Model checking, product BFS, loop-bound trap handling
    - Integration: Full pipeline end-to-end
"""

from __future__ import annotations

import json
import sys
import os
import pytest

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.lifter import LTS, LifterConfig, QualityGateError, WIRLifter
from src.stuttering_engine import StutteringEngine, StutteringResult
from src.clustering import BehavioralClusterer, ClusterResult
from src.model_checker import ModelChecker, PropertyMonitor, VerificationVerdict


# ═══════════════════════════════════════════════════════════════════════════
#  Test Fixtures
# ═══════════════════════════════════════════════════════════════════════════

def make_simple_wir() -> dict:
    """Minimal valid WIR: entry → task → exit."""
    return {
        "entry_node": "S0",
        "exit_node": "S2",
        "nodes": [
            {"id": "S0", "type": "entry", "successors": ["S1"], "predecessors": [], "control_vars": [], "data_vars": []},
            {"id": "S1", "type": "task",  "successors": ["S2"], "predecessors": ["S0"], "control_vars": [], "data_vars": []},
            {"id": "S2", "type": "exit",  "successors": [],     "predecessors": ["S1"], "control_vars": [], "data_vars": []},
        ],
        "edges": [
            {"source": "S0", "target": "S1", "guard": None, "exception_type": None},
            {"source": "S1", "target": "S2", "guard": None, "exception_type": None},
        ],
        "certificate": {
            "version": "V3",
            "node_coverage": 1.0,
            "edge_coverage": 1.0,
            "guard_success_rate": 1.0,
            "abort": False,
            "message": "OK"
        }
    }


def make_branching_wir() -> dict:
    """WIR with a gateway/branch: entry → gateway → {A, B} → exit."""
    return {
        "entry_node": "S0",
        "exit_node": "S3",
        "nodes": [
            {"id": "S0", "type": "entry",   "successors": ["G1"], "predecessors": [], "control_vars": [], "data_vars": []},
            {"id": "G1", "type": "gateway", "successors": ["A1", "B1"], "predecessors": ["S0"], "control_vars": ["flag"], "data_vars": [], "guard": "flag"},
            {"id": "A1", "type": "task",    "successors": ["S3"], "predecessors": ["G1"], "control_vars": [], "data_vars": []},
            {"id": "B1", "type": "task",    "successors": ["S3"], "predecessors": ["G1"], "control_vars": [], "data_vars": []},
            {"id": "S3", "type": "exit",    "successors": [],     "predecessors": ["A1", "B1"], "control_vars": [], "data_vars": []},
        ],
        "edges": [
            {"source": "S0", "target": "G1", "guard": None,       "exception_type": None},
            {"source": "G1", "target": "A1", "guard": "flag",     "exception_type": None},
            {"source": "G1", "target": "B1", "guard": "not flag", "exception_type": None},
            {"source": "A1", "target": "S3", "guard": None,       "exception_type": None},
            {"source": "B1", "target": "S3", "guard": None,       "exception_type": None},
        ],
        "certificate": {
            "version": "V3",
            "node_coverage": 1.0,
            "edge_coverage": 1.0,
            "guard_success_rate": 1.0,
            "abort": False,
            "message": "OK"
        }
    }


def make_loop_wir() -> dict:
    """WIR with a loop node for testing bounded unrolling."""
    return {
        "entry_node": "L0",
        "exit_node": "L3",
        "nodes": [
            {"id": "L0", "type": "entry", "successors": ["L1"], "predecessors": [], "control_vars": [], "data_vars": []},
            {"id": "L1", "type": "loop",  "successors": ["L2"], "predecessors": ["L0", "L2"], "control_vars": [], "data_vars": [], "guard": "iter items", "ast_type": "For"},
            {"id": "L2", "type": "task",  "successors": ["L1", "L3"], "predecessors": ["L1"], "control_vars": [], "data_vars": []},
            {"id": "L3", "type": "exit",  "successors": [],     "predecessors": ["L2"], "control_vars": [], "data_vars": []},
        ],
        "edges": [
            {"source": "L0", "target": "L1", "guard": None,         "exception_type": None},
            {"source": "L1", "target": "L2", "guard": "iter items",  "exception_type": None},
            {"source": "L2", "target": "L1", "guard": None,          "exception_type": None},
            {"source": "L2", "target": "L3", "guard": "done",        "exception_type": None},
        ],
        "certificate": {
            "version": "V3",
            "node_coverage": 1.0,
            "edge_coverage": 1.0,
            "guard_success_rate": 1.0,
            "abort": False,
            "message": "OK"
        }
    }


def make_wir_with_functions() -> dict:
    """WIR with nested functions block."""
    base = make_simple_wir()
    base["functions"] = {
        "process_orders": {
            "entry_node": "F1",
            "exit_node": "F3",
            "nodes": [
                {"id": "F1", "type": "entry", "successors": ["F2"], "predecessors": [], "control_vars": [], "data_vars": []},
                {"id": "F2", "type": "task",  "successors": ["F3"], "predecessors": ["F1"], "control_vars": [], "data_vars": []},
                {"id": "F3", "type": "exit",  "successors": [],     "predecessors": ["F2"], "control_vars": [], "data_vars": []},
            ],
            "edges": [
                {"source": "F1", "target": "F2", "guard": None, "exception_type": None},
                {"source": "F2", "target": "F3", "guard": None, "exception_type": None},
            ]
        }
    }
    return base


def make_low_confidence_wir() -> dict:
    """WIR with guard_success_rate below minimum confidence floor."""
    wir = make_simple_wir()
    wir["certificate"]["guard_success_rate"] = 0.3
    return wir


def make_mid_confidence_wir() -> dict:
    """WIR with guard_success_rate between floor and threshold (WARNING tier)."""
    wir = make_simple_wir()
    wir["certificate"]["guard_success_rate"] = 0.8333333333333334
    return wir


def make_abort_wir() -> dict:
    """WIR with abort=True in certificate."""
    wir = make_simple_wir()
    wir["certificate"]["abort"] = True
    return wir


# ═══════════════════════════════════════════════════════════════════════════
#  Phase A Tests: Lifter
# ═══════════════════════════════════════════════════════════════════════════

class TestQualityGate:
    """Tests for the binary quality gate."""

    def test_pass_high_confidence(self):
        lifter = WIRLifter()
        wir = make_simple_wir()
        # Should not raise
        result = lifter.lift(wir)
        assert len(result) >= 1

    def test_reject_low_confidence(self):
        lifter = WIRLifter(LifterConfig(confidence_threshold=0.95))
        wir = make_low_confidence_wir()  # 0.3 < minimum_confidence 0.50
        with pytest.raises(QualityGateError, match="Low confidence"):
            lifter.lift(wir)

    def test_reject_abort_flag(self):
        lifter = WIRLifter()
        wir = make_abort_wir()
        with pytest.raises(QualityGateError, match="abort"):
            lifter.lift(wir)

    def test_warn_but_continue_when_non_fatal(self):
        lifter = WIRLifter(LifterConfig(
            confidence_threshold=0.95,
            abort_on_low_confidence=False,
        ))
        wir = make_low_confidence_wir()
        result = lifter.lift(wir)
        assert len(result) >= 1

    def test_warning_tier_mid_confidence(self):
        """guard_success_rate=0.833 is between floor (0.50) and threshold (0.95).
        Should proceed with a WARNING, not abort."""
        lifter = WIRLifter(LifterConfig(
            confidence_threshold=0.95,
            minimum_confidence=0.50,
        ))
        wir = make_mid_confidence_wir()
        result = lifter.lift(wir)
        assert len(result) >= 1
        assert lifter._quality_gate_result == "WARNING"


class TestLTSLifting:
    """Tests for basic LTS construction."""

    def test_simple_linear(self):
        lifter = WIRLifter()
        result = lifter.lift(make_simple_wir())
        lts = result[0]
        assert lts.num_states() == 3
        assert lts.num_transitions() == 2
        assert lts.initial_state == "S0"
        assert "S2" in lts.exit_states

    def test_branching(self):
        lifter = WIRLifter()
        result = lifter.lift(make_branching_wir())
        lts = result[0]
        assert lts.num_states() == 5
        assert lts.num_transitions() == 5
        assert "flag" in lts.atomic_propositions

    def test_tau_labels(self):
        """Null guards should produce 'tau' labels."""
        lifter = WIRLifter()
        result = lifter.lift(make_simple_wir())
        lts = result[0]
        labels = {lbl for _, _, lbl in lts.transitions}
        assert "tau" in labels

    def test_successors(self):
        lifter = WIRLifter()
        result = lifter.lift(make_simple_wir())
        lts = result[0]
        succs = lts.successors("S0")
        assert len(succs) == 1
        assert succs[0][0] == "S1"

    def test_cyclomatic_complexity(self):
        lifter = WIRLifter()
        result = lifter.lift(make_branching_wir())
        lts = result[0]
        cc = lts.cyclomatic_complexity()
        # E=5, N=5, P=1 → 5-5+2 = 2
        assert cc == 2


class TestNestedFunctions:
    """Tests for the functions block traversal."""

    def test_functions_produce_separate_lts(self):
        lifter = WIRLifter()
        result = lifter.lift(make_wir_with_functions())
        assert len(result) == 2  # top-level + process_orders
        names = {l.name for l in result}
        assert "__top_level__" in names
        assert "process_orders" in names

    def test_function_lts_structure(self):
        lifter = WIRLifter()
        result = lifter.lift(make_wir_with_functions())
        fn_lts = [l for l in result if l.name == "process_orders"][0]
        assert fn_lts.num_states() == 3
        assert fn_lts.initial_state == "F1"


class TestLoopUnrolling:
    """Tests for bounded loop state duplication."""

    def test_loop_creates_iterations(self):
        lifter = WIRLifter(LifterConfig(loop_max=3))
        result = lifter.lift(make_loop_wir())
        lts = result[0]
        # Should have iteration states
        iter_states = [s for s in lts.states if "_iter_" in s]
        assert len(iter_states) == 3  # iter_0, iter_1, iter_2

    def test_loop_creates_trap_state(self):
        lifter = WIRLifter(LifterConfig(loop_max=2))
        result = lifter.lift(make_loop_wir())
        lts = result[0]
        trap_states = [
            s for s in lts.states
            if s.endswith("_loop_exceeds_bound_error")
        ]
        assert len(trap_states) == 1
        trap_meta = lts.states[trap_states[0]]
        assert trap_meta["type"] == "error"

    def test_original_loop_node_removed(self):
        lifter = WIRLifter(LifterConfig(loop_max=2))
        result = lifter.lift(make_loop_wir())
        lts = result[0]
        assert "L1" not in lts.states


# ═══════════════════════════════════════════════════════════════════════════
#  Phase B Tests: Stuttering Engine
# ═══════════════════════════════════════════════════════════════════════════

class TestTarjanSCC:
    """Tests for Tarjan's SCC on tau-subgraph."""

    def test_no_cycles(self):
        """A linear tau chain has only singleton SCCs."""
        lts = LTS("linear")
        lts.states = {"A": {}, "B": {}, "C": {}}
        lts.transitions = [("A", "B", "tau"), ("B", "C", "tau")]
        lts.initial_state = "A"

        engine = StutteringEngine()
        result = engine.compute(lts)
        assert result.divergent_states == set()
        assert len(result.divergent_sccs) == 0

    def test_self_loop_divergent(self):
        """A self-loop on tau should be flagged as divergent."""
        lts = LTS("selfloop")
        lts.states = {"X": {}}
        lts.transitions = [("X", "X", "tau")]
        lts.initial_state = "X"

        engine = StutteringEngine()
        result = engine.compute(lts)
        assert "X" in result.divergent_states

    def test_cycle_divergent(self):
        """A tau cycle A → B → A should flag both as divergent."""
        lts = LTS("cycle")
        lts.states = {"A": {}, "B": {}}
        lts.transitions = [("A", "B", "tau"), ("B", "A", "tau")]
        lts.initial_state = "A"

        engine = StutteringEngine()
        result = engine.compute(lts)
        assert result.divergent_states == {"A", "B"}


class TestDivergencePropagation:
    """Tests for backward divergence propagation."""

    def test_propagation_through_tau(self):
        """State C reaches divergent cycle A↔B via tau → C is divergent."""
        lts = LTS("prop")
        lts.states = {"A": {}, "B": {}, "C": {}}
        lts.transitions = [
            ("A", "B", "tau"),
            ("B", "A", "tau"),
            ("C", "A", "tau"),
        ]
        lts.initial_state = "C"

        engine = StutteringEngine()
        result = engine.compute(lts)
        assert "C" in result.divergent_states


class TestPartitionRefinement:
    """Tests for the naive O(n²) partition refinement."""

    def test_identical_states_same_block(self):
        """Two states with identical outgoing behaviour share a block."""
        lts = LTS("identical")
        lts.states = {"A": {}, "B": {}, "C": {}}
        lts.transitions = [
            ("A", "C", "act"),
            ("B", "C", "act"),
        ]
        lts.initial_state = "A"

        engine = StutteringEngine()
        result = engine.compute(lts)
        assert result.state_to_block["A"] == result.state_to_block["B"]

    def test_different_labels_different_blocks(self):
        """States with different observable labels land in different blocks."""
        lts = LTS("diff")
        lts.states = {"A": {}, "B": {}, "C": {}, "D": {}}
        lts.transitions = [
            ("A", "C", "x"),
            ("B", "D", "y"),
        ]
        lts.initial_state = "A"

        engine = StutteringEngine()
        result = engine.compute(lts)
        assert result.state_to_block["A"] != result.state_to_block["B"]


class TestBisimilarity:
    """Tests for the are_bisimilar() method."""

    def test_self_bisimilar(self):
        """An LTS is bisimilar to itself."""
        lts = LTS("self")
        lts.states = {"S0": {}, "S1": {}}
        lts.transitions = [("S0", "S1", "act")]
        lts.initial_state = "S0"

        engine = StutteringEngine()
        assert engine.are_bisimilar(lts, lts) is True

    def test_structurally_equivalent(self):
        """Two structurally identical LTS (different names) are bisimilar."""
        lts1 = LTS("alpha")
        lts1.states = {"A": {}, "B": {}}
        lts1.transitions = [("A", "B", "go")]
        lts1.initial_state = "A"

        lts2 = LTS("beta")
        lts2.states = {"X": {}, "Y": {}}
        lts2.transitions = [("X", "Y", "go")]
        lts2.initial_state = "X"

        engine = StutteringEngine()
        assert engine.are_bisimilar(lts1, lts2) is True

    def test_different_behaviour_not_bisimilar(self):
        """LTS with different observable behaviour are not bisimilar."""
        lts1 = LTS("one")
        lts1.states = {"A": {}, "B": {}}
        lts1.transitions = [("A", "B", "x")]
        lts1.initial_state = "A"

        lts2 = LTS("two")
        lts2.states = {"C": {}, "D": {}}
        lts2.transitions = [("C", "D", "y")]
        lts2.initial_state = "C"

        engine = StutteringEngine()
        assert engine.are_bisimilar(lts1, lts2) is False


# ═══════════════════════════════════════════════════════════════════════════
#  Phase C Tests: Clustering
# ═══════════════════════════════════════════════════════════════════════════

class TestClustering:
    """Tests for the behavioural clusterer."""

    def _make_lts(self, name: str, label: str) -> LTS:
        lts = LTS(name)
        lts.states = {"s0": {}, "s1": {}}
        lts.transitions = [("s0", "s1", label)]
        lts.initial_state = "s0"
        lts.atomic_propositions = {label}
        return lts

    def test_identical_models_cluster_together(self):
        lts_a = self._make_lts("a", "go")
        lts_b = self._make_lts("b", "go")

        engine = StutteringEngine()
        clusterer = BehavioralClusterer(engine)
        result = clusterer.cluster([lts_a, lts_b])

        assert result.num_clusters == 1
        assert len(result.singleton_anomalies) == 0

    def test_different_models_separate_clusters(self):
        lts_a = self._make_lts("a", "x")
        lts_b = self._make_lts("b", "y")

        engine = StutteringEngine()
        clusterer = BehavioralClusterer(engine)
        result = clusterer.cluster([lts_a, lts_b])

        assert result.num_clusters == 2
        assert len(result.singleton_anomalies) == 2

    def test_representative_by_complexity(self):
        """Representative should be the model with lowest cyclomatic complexity."""
        lts_a = LTS("simple")
        lts_a.states = {"s0": {}, "s1": {}}
        lts_a.transitions = [("s0", "s1", "go")]
        lts_a.initial_state = "s0"

        lts_b = LTS("complex")
        lts_b.states = {"s0": {}, "s1": {}, "s2": {}}
        lts_b.transitions = [("s0", "s1", "go"), ("s1", "s2", "go"), ("s0", "s2", "go")]
        lts_b.initial_state = "s0"

        # They differ → separate clusters, but verify representative logic works
        engine = StutteringEngine()
        clusterer = BehavioralClusterer(engine)
        result = clusterer.cluster([lts_a, lts_b])

        # Each is its own cluster — check that representative equals itself
        for cid, rep in result.representatives.items():
            assert rep in [m for m in result.clusters[cid]]


# ═══════════════════════════════════════════════════════════════════════════
#  Phase D Tests: Model Checker
# ═══════════════════════════════════════════════════════════════════════════

class TestPropertyMonitor:
    """Tests for monitor construction."""

    def test_reachability_monitor_structure(self):
        mon = PropertyMonitor.from_reachability("danger")
        assert "mon_ok" in mon.states
        assert "mon_violating" in mon.states
        assert mon.initial_state == "mon_ok"
        assert mon.states["mon_violating"]["violating"] is True

    def test_loop_bound_monitor_structure(self):
        mon = PropertyMonitor.from_loop_bound_check()
        assert "mon_ok" in mon.states
        assert mon.initial_state == "mon_ok"


class TestModelChecker:
    """Tests for the finite-trace BFS model checker."""

    def test_safe_system_passes(self):
        """A system with no forbidden labels should PASS."""
        sys_lts = LTS("safe")
        sys_lts.states = {"s0": {}, "s1": {}}
        sys_lts.transitions = [("s0", "s1", "ok")]
        sys_lts.initial_state = "s0"

        mon = PropertyMonitor.from_reachability("danger")
        checker = ModelChecker()
        verdict = checker.check(sys_lts, mon)

        assert verdict.result == "PASS"
        assert verdict.states_explored > 0

    def test_forbidden_label_detected(self):
        """A system that reaches a forbidden label should FAIL."""
        sys_lts = LTS("unsafe")
        sys_lts.states = {"s0": {}, "s1": {}, "s2": {}}
        sys_lts.transitions = [
            ("s0", "s1", "ok"),
            ("s1", "s2", "danger"),
        ]
        sys_lts.initial_state = "s0"

        mon = PropertyMonitor.from_reachability("danger")
        checker = ModelChecker()
        verdict = checker.check(sys_lts, mon)

        assert verdict.result == "FAIL"
        assert len(verdict.violating_states) > 0
        assert len(verdict.counterexample_trace) > 0

    def test_loop_bound_trap_detected(self):
        """A system with a trap state should trigger loop-bound violation."""
        sys_lts = LTS("trapped")
        sys_lts.states = {
            "s0": {"type": "entry"},
            "s1": {"type": "task"},
            "trap": {"type": "error", "error_kind": "loop_exceeds_bound_error"},
        }
        sys_lts.transitions = [
            ("s0", "s1", "tau"),
            ("s1", "trap", "tau"),
        ]
        sys_lts.initial_state = "s0"

        mon = PropertyMonitor.from_loop_bound_check()
        checker = ModelChecker()
        verdict = checker.check(sys_lts, mon)

        assert verdict.result == "FAIL"
        assert len(verdict.loop_bound_violations) > 0

    def test_counterexample_trace_reconstructed(self):
        """Counterexample trace should be a valid path from initial to violation."""
        sys_lts = LTS("trace_test")
        sys_lts.states = {"A": {}, "B": {}, "C": {}}
        sys_lts.transitions = [
            ("A", "B", "tau"),
            ("B", "C", "danger"),
        ]
        sys_lts.initial_state = "A"

        mon = PropertyMonitor.from_reachability("danger")
        checker = ModelChecker()
        verdict = checker.check(sys_lts, mon)

        assert verdict.result == "FAIL"
        trace = verdict.counterexample_trace
        assert trace[0].startswith("A||")
        assert len(trace) >= 2

    def test_check_all_properties(self):
        """check_all_properties should return results for each property."""
        sys_lts = LTS("multi")
        sys_lts.states = {"s0": {}, "s1": {}}
        sys_lts.transitions = [("s0", "s1", "ok")]
        sys_lts.initial_state = "s0"

        props = [
            ("no_danger", PropertyMonitor.from_reachability("danger")),
            ("no_error", PropertyMonitor.from_reachability("error")),
        ]

        checker = ModelChecker()
        results = checker.check_all_properties(sys_lts, props)
        assert len(results) == 2
        assert all(v.result == "PASS" for _, v in results)


# ═══════════════════════════════════════════════════════════════════════════
#  Integration Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestIntegration:
    """End-to-end integration tests through all four phases."""

    def test_full_pipeline_simple(self):
        """Simple WIR through all 4 phases."""
        # Phase A
        lifter = WIRLifter()
        lts_list = lifter.lift(make_simple_wir())
        assert len(lts_list) >= 1

        # Phase B
        engine = StutteringEngine()
        for lts in lts_list:
            result = engine.compute(lts)
            assert result.num_blocks > 0

        # Phase C
        clusterer = BehavioralClusterer(engine)
        cluster_result = clusterer.cluster(lts_list)
        assert cluster_result.num_clusters >= 1

        # Phase D
        checker = ModelChecker()
        lts_by_name = {l.name: l for l in lts_list}
        for cid, rep_name in cluster_result.representatives.items():
            rep = lts_by_name[rep_name]
            mon = PropertyMonitor.from_loop_bound_check()
            verdict = checker.check(rep, mon)
            assert verdict.result in ("PASS", "FAIL")

    def test_full_pipeline_with_functions(self):
        """WIR with functions block → produces multiple LTS models."""
        lifter = WIRLifter()
        lts_list = lifter.lift(make_wir_with_functions())
        assert len(lts_list) == 2

        engine = StutteringEngine()
        clusterer = BehavioralClusterer(engine)
        result = clusterer.cluster(lts_list)
        assert result.num_clusters >= 1

    def test_full_pipeline_with_loop(self):
        """WIR with loop → unrolling + trap state + model check."""
        lifter = WIRLifter(LifterConfig(loop_max=2))
        lts_list = lifter.lift(make_loop_wir())
        lts = lts_list[0]

        # Verify trap state exists
        traps = [s for s in lts.states if "_loop_exceeds_bound_error" in s]
        assert len(traps) >= 1

        # Model check for loop bound
        checker = ModelChecker()
        mon = PropertyMonitor.from_loop_bound_check()
        verdict = checker.check(lts, mon)
        # The trap is reachable → should FAIL
        assert verdict.result == "FAIL"
        assert len(verdict.loop_bound_violations) > 0

    def test_quality_gate_blocks_pipeline(self):
        """Low confidence WIR (below minimum floor) should abort before any LTS is produced."""
        lifter = WIRLifter(LifterConfig(confidence_threshold=0.99))
        wir = make_simple_wir()
        wir["certificate"]["guard_success_rate"] = 0.30  # Below minimum_confidence floor (0.50)

        with pytest.raises(QualityGateError):
            lifter.lift(wir)

    def test_full_pipeline_module02_wir_payload(self):
        """
        Full E2E test with the exact WIR payload from Module 02.
        This payload has guard_success_rate=0.833 (WARNING tier)
        and a nested function 'process_batch_orders' with 29 nodes.
        """
        wir = {
            "entry_node": "node_1",
            "exit_node": "node_2",
            "nodes": [
                {"id": "node_1", "type": "entry", "ast_type": "Module", "line": 0, "code": [],
                 "successors": ["node_3"], "predecessors": [],
                 "guard": None, "exception_type": None, "control_vars": [], "data_vars": []},
                {"id": "node_2", "type": "exit", "ast_type": "Module", "line": 0, "code": [],
                 "successors": [], "predecessors": ["node_3"],
                 "guard": None, "exception_type": None, "control_vars": [], "data_vars": []},
                {"id": "node_3", "type": "task", "ast_type": "FunctionDef", "line": 1,
                 "code": ["def process_batch_orders(...)"],
                 "successors": ["node_2"], "predecessors": ["node_1"],
                 "guard": None, "exception_type": None, "control_vars": [],
                 "data_vars": ["inventory_level", "order_quantities", "is_premium_vendor"]},
            ],
            "edges": [
                {"source": "node_1", "target": "node_3", "guard": None, "exception_type": None},
                {"source": "node_3", "target": "node_2", "guard": None, "exception_type": None},
            ],
            "functions": {
                "process_batch_orders": {
                    "entry_node": "node_1",
                    "exit_node": "node_29",
                    "nodes": [
                        {"id": "node_1", "type": "block", "ast_type": "Assign", "line": 2,
                         "code": ["status = 'PROCESSING'"], "successors": ["node_2"], "predecessors": [],
                         "guard": None, "exception_type": None, "control_vars": [],
                         "data_vars": ["status", "inventory_level", "order_quantities", "is_premium_vendor"]},
                        {"id": "node_2", "type": "block", "ast_type": "Assign", "line": 3,
                         "code": ["fulfilled_orders = 0"], "successors": ["node_3"], "predecessors": ["node_1"],
                         "guard": None, "exception_type": None, "control_vars": [], "data_vars": ["fulfilled_orders"]},
                        {"id": "node_3", "type": "block", "ast_type": "Assign", "line": 4,
                         "code": ["revenue = 0.0"], "successors": ["node_4"], "predecessors": ["node_2"],
                         "guard": None, "exception_type": None, "control_vars": [], "data_vars": ["revenue"]},
                        {"id": "node_4", "type": "gateway", "ast_type": "If", "line": 6,
                         "code": [], "successors": ["node_5", "node_6"], "predecessors": ["node_3"],
                         "guard": "inventory_level < 0", "exception_type": None,
                         "control_vars": ["inventory_level"], "data_vars": []},
                        {"id": "node_5", "type": "return", "ast_type": "Return", "line": 7,
                         "code": ["return {'status': 'INVALID_STATE', 'revenue': 0.0}"],
                         "successors": ["node_7"], "predecessors": ["node_4"],
                         "guard": None, "exception_type": None, "control_vars": [], "data_vars": []},
                        {"id": "node_6", "type": "block", "ast_type": "If", "line": 6,
                         "code": [], "successors": ["node_7"], "predecessors": ["node_4"],
                         "guard": None, "exception_type": None, "control_vars": [], "data_vars": []},
                        {"id": "node_7", "type": "block", "ast_type": "If", "line": 6,
                         "code": [], "successors": ["node_8"], "predecessors": ["node_5", "node_6"],
                         "guard": None, "exception_type": None, "control_vars": [], "data_vars": []},
                        {"id": "node_8", "type": "loop", "ast_type": "For", "line": 9,
                         "code": [], "successors": ["node_10", "node_9"],
                         "predecessors": ["node_11", "node_23", "node_7"],
                         "guard": "iter order_quantities", "exception_type": None,
                         "control_vars": ["order_quantities"], "data_vars": ["qty"]},
                        {"id": "node_9", "type": "block", "ast_type": "For", "line": 9,
                         "code": [], "successors": ["node_24"], "predecessors": ["node_22", "node_8"],
                         "guard": None, "exception_type": None, "control_vars": [], "data_vars": []},
                        {"id": "node_10", "type": "gateway", "ast_type": "If", "line": 10,
                         "code": [], "successors": ["node_11", "node_12"], "predecessors": ["node_8"],
                         "guard": "qty <= 0", "exception_type": None,
                         "control_vars": ["qty"], "data_vars": []},
                        {"id": "node_11", "type": "continue", "ast_type": "Continue", "line": 11,
                         "code": ["continue"], "successors": ["node_8", "node_13"],
                         "predecessors": ["node_10"],
                         "guard": None, "exception_type": None, "control_vars": [], "data_vars": []},
                        {"id": "node_12", "type": "block", "ast_type": "If", "line": 10,
                         "code": [], "successors": ["node_13"], "predecessors": ["node_10"],
                         "guard": None, "exception_type": None, "control_vars": [], "data_vars": []},
                        {"id": "node_13", "type": "block", "ast_type": "If", "line": 10,
                         "code": [], "successors": ["node_14"], "predecessors": ["node_11", "node_12"],
                         "guard": None, "exception_type": None, "control_vars": [], "data_vars": []},
                        {"id": "node_14", "type": "gateway", "ast_type": "If", "line": 13,
                         "code": [], "successors": ["node_15", "node_22"], "predecessors": ["node_13"],
                         "guard": "inventory_level >= qty", "exception_type": None,
                         "control_vars": ["inventory_level", "qty"], "data_vars": []},
                        {"id": "node_15", "type": "block", "ast_type": "AugAssign", "line": 14,
                         "code": ["inventory_level -= qty"], "successors": ["node_16"],
                         "predecessors": ["node_14"],
                         "guard": None, "exception_type": None, "control_vars": [],
                         "data_vars": ["inventory_level", "qty"]},
                        {"id": "node_16", "type": "block", "ast_type": "AugAssign", "line": 15,
                         "code": ["fulfilled_orders += 1"], "successors": ["node_17"],
                         "predecessors": ["node_15"],
                         "guard": None, "exception_type": None, "control_vars": [],
                         "data_vars": ["fulfilled_orders"]},
                        {"id": "node_17", "type": "gateway", "ast_type": "If", "line": 17,
                         "code": [], "successors": ["node_18", "node_19"], "predecessors": ["node_16"],
                         "guard": "is_premium_vendor", "exception_type": None,
                         "control_vars": ["is_premium_vendor"], "data_vars": []},
                        {"id": "node_18", "type": "block", "ast_type": "Assign", "line": 18,
                         "code": ["price = 80.0 * qty"], "successors": ["node_20"],
                         "predecessors": ["node_17"],
                         "guard": None, "exception_type": None, "control_vars": [],
                         "data_vars": ["qty", "price"]},
                        {"id": "node_19", "type": "block", "ast_type": "Assign", "line": 20,
                         "code": ["price = 100.0 * qty"], "successors": ["node_20"],
                         "predecessors": ["node_17"],
                         "guard": None, "exception_type": None, "control_vars": [],
                         "data_vars": ["qty", "price"]},
                        {"id": "node_20", "type": "block", "ast_type": "If", "line": 17,
                         "code": [], "successors": ["node_21"], "predecessors": ["node_18", "node_19"],
                         "guard": None, "exception_type": None, "control_vars": [], "data_vars": []},
                        {"id": "node_21", "type": "block", "ast_type": "AugAssign", "line": 22,
                         "code": ["revenue += price"], "successors": ["node_23"],
                         "predecessors": ["node_20"],
                         "guard": None, "exception_type": None, "control_vars": [],
                         "data_vars": ["revenue", "price"]},
                        {"id": "node_22", "type": "break", "ast_type": "Break", "line": 24,
                         "code": ["break"], "successors": ["node_9", "node_23"],
                         "predecessors": ["node_14"],
                         "guard": None, "exception_type": None, "control_vars": [], "data_vars": []},
                        {"id": "node_23", "type": "block", "ast_type": "If", "line": 13,
                         "code": [], "successors": ["node_8"], "predecessors": ["node_21", "node_22"],
                         "guard": None, "exception_type": None, "control_vars": [], "data_vars": []},
                        {"id": "node_24", "type": "gateway", "ast_type": "If", "line": 26,
                         "code": [], "successors": ["node_25", "node_26"], "predecessors": ["node_9"],
                         "guard": "inventory_level == 0", "exception_type": None,
                         "control_vars": ["inventory_level"], "data_vars": []},
                        {"id": "node_25", "type": "block", "ast_type": "Assign", "line": 27,
                         "code": ["status = 'RESTOCK_REQUIRED'"], "successors": ["node_27"],
                         "predecessors": ["node_24"],
                         "guard": None, "exception_type": None, "control_vars": [], "data_vars": ["status"]},
                        {"id": "node_26", "type": "block", "ast_type": "Assign", "line": 29,
                         "code": ["status = 'SUCCESS'"], "successors": ["node_27"],
                         "predecessors": ["node_24"],
                         "guard": None, "exception_type": None, "control_vars": [], "data_vars": ["status"]},
                        {"id": "node_27", "type": "block", "ast_type": "If", "line": 26,
                         "code": [], "successors": ["node_28"], "predecessors": ["node_25", "node_26"],
                         "guard": None, "exception_type": None, "control_vars": [], "data_vars": []},
                        {"id": "node_28", "type": "block", "ast_type": "Assign", "line": 31,
                         "code": ["audit_trail = f'Fulfilled {fulfilled_orders} orders. Remaining stock: {inventory_level}'"],
                         "successors": ["node_29"], "predecessors": ["node_27"],
                         "guard": None, "exception_type": None, "control_vars": [],
                         "data_vars": ["fulfilled_orders", "inventory_level", "audit_trail"]},
                        {"id": "node_29", "type": "return", "ast_type": "Return", "line": 33,
                         "code": ["return {'status': status, 'revenue': revenue}"],
                         "successors": [], "predecessors": ["node_28"],
                         "guard": None, "exception_type": None, "control_vars": [],
                         "data_vars": ["revenue", "status"]},
                    ],
                    "edges": [
                        {"source": "node_1", "target": "node_2", "guard": None, "exception_type": None},
                        {"source": "node_2", "target": "node_3", "guard": None, "exception_type": None},
                        {"source": "node_4", "target": "node_5", "guard": "inventory_level < 0", "exception_type": None},
                        {"source": "node_4", "target": "node_6", "guard": "not (inventory_level < 0)", "exception_type": None},
                        {"source": "node_5", "target": "node_7", "guard": None, "exception_type": None},
                        {"source": "node_6", "target": "node_7", "guard": None, "exception_type": None},
                        {"source": "node_3", "target": "node_4", "guard": None, "exception_type": None},
                        {"source": "node_11", "target": "node_8", "guard": None, "exception_type": None},
                        {"source": "node_10", "target": "node_11", "guard": "qty <= 0", "exception_type": None},
                        {"source": "node_10", "target": "node_12", "guard": "not (qty <= 0)", "exception_type": None},
                        {"source": "node_11", "target": "node_13", "guard": None, "exception_type": None},
                        {"source": "node_12", "target": "node_13", "guard": None, "exception_type": None},
                        {"source": "node_15", "target": "node_16", "guard": None, "exception_type": None},
                        {"source": "node_17", "target": "node_18", "guard": "is_premium_vendor", "exception_type": None},
                        {"source": "node_17", "target": "node_19", "guard": "not (is_premium_vendor)", "exception_type": None},
                        {"source": "node_18", "target": "node_20", "guard": None, "exception_type": None},
                        {"source": "node_19", "target": "node_20", "guard": None, "exception_type": None},
                        {"source": "node_16", "target": "node_17", "guard": None, "exception_type": None},
                        {"source": "node_20", "target": "node_21", "guard": None, "exception_type": None},
                        {"source": "node_22", "target": "node_9", "guard": None, "exception_type": None},
                        {"source": "node_14", "target": "node_15", "guard": "inventory_level >= qty", "exception_type": None},
                        {"source": "node_14", "target": "node_22", "guard": "not (inventory_level >= qty)", "exception_type": None},
                        {"source": "node_21", "target": "node_23", "guard": None, "exception_type": None},
                        {"source": "node_22", "target": "node_23", "guard": None, "exception_type": None},
                        {"source": "node_13", "target": "node_14", "guard": None, "exception_type": None},
                        {"source": "node_8", "target": "node_10", "guard": "next(order_quantities)", "exception_type": None},
                        {"source": "node_8", "target": "node_9", "guard": "exhausted(order_quantities)", "exception_type": None},
                        {"source": "node_23", "target": "node_8", "guard": None, "exception_type": None},
                        {"source": "node_7", "target": "node_8", "guard": None, "exception_type": None},
                        {"source": "node_24", "target": "node_25", "guard": "inventory_level == 0", "exception_type": None},
                        {"source": "node_24", "target": "node_26", "guard": "not (inventory_level == 0)", "exception_type": None},
                        {"source": "node_25", "target": "node_27", "guard": None, "exception_type": None},
                        {"source": "node_26", "target": "node_27", "guard": None, "exception_type": None},
                        {"source": "node_9", "target": "node_24", "guard": None, "exception_type": None},
                        {"source": "node_27", "target": "node_28", "guard": None, "exception_type": None},
                        {"source": "node_28", "target": "node_29", "guard": None, "exception_type": None},
                    ],
                    "unsupported_constructs": []
                }
            },
            "guard_extraction": {
                "total": 6, "success": 5,
                "conditions": [
                    {"node_id": "node_4", "guard": "inventory_level < 0"},
                    {"node_id": "node_8", "guard": "iter order_quantities", "error": "Failed to parse guard into CNF"},
                    {"node_id": "node_10", "guard": "qty <= 0"},
                    {"node_id": "node_14", "guard": "inventory_level >= qty"},
                    {"node_id": "node_17", "guard": "is_premium_vendor"},
                    {"node_id": "node_24", "guard": "inventory_level == 0"},
                ]
            },
            "control_variables": ["inventory_level", "is_premium_vendor", "order_quantities", "qty"],
            "data_variables": ["audit_trail", "fulfilled_orders", "price", "revenue", "status"],
            "certificate": {
                "version": "V3",
                "node_coverage": 1.0,
                "edge_coverage": 1.0,
                "guard_success_rate": 0.8333333333333334,
                "unsupported_constructs": [],
                "abort": False,
                "message": "V3 structural extraction passed quality gate."
            }
        }

        # Phase A: Lifter (should pass with WARNING due to 0.833 < 0.95)
        lifter = WIRLifter(LifterConfig(
            confidence_threshold=0.95,
            minimum_confidence=0.50,
            loop_max=3,
        ))
        lts_list = lifter.lift(wir)
        assert lifter._quality_gate_result == "WARNING"
        assert len(lts_list) == 2  # top-level + process_batch_orders

        top_lts = [l for l in lts_list if l.name == "__top_level__"][0]
        fn_lts = [l for l in lts_list if l.name == "process_batch_orders"][0]

        # Top-level should be simple: 3 nodes, 2 edges
        assert top_lts.num_states() == 3
        assert top_lts.num_transitions() == 2

        # Function LTS should have loop unrolling applied
        # node_8 is a loop node → should be replaced by iterations + trap
        assert "node_8" not in fn_lts.states
        iter_states = [s for s in fn_lts.states if "node_8_iter_" in s]
        assert len(iter_states) == 3  # loop_max=3
        trap_states = [s for s in fn_lts.states if s.endswith("_loop_exceeds_bound_error")]
        assert len(trap_states) == 1

        # Phase B: Stuttering Engine
        engine = StutteringEngine()
        for lts in lts_list:
            result = engine.compute(lts)
            assert result.num_blocks > 0

        # Phase C: Clustering
        clusterer = BehavioralClusterer(engine)
        cluster_result = clusterer.cluster(lts_list)
        assert cluster_result.num_clusters >= 1

        # Phase D: Model Checker
        checker = ModelChecker()
        lts_by_name = {l.name: l for l in lts_list}
        for cid, rep_name in cluster_result.representatives.items():
            rep = lts_by_name[rep_name]
            mon = PropertyMonitor.from_loop_bound_check()
            verdict = checker.check(rep, mon)
            assert verdict.result in ("PASS", "FAIL")
            assert verdict.states_explored > 0


# ═══════════════════════════════════════════════════════════════════════════
#  Runner
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
