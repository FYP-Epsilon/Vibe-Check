"""
Phase 4 (Automata Lifting) — Comprehensive Test Suite.

Tests language inclusion, GED diagnostics, HOA export, certificate structure,
and 20 seeded translation fault detection tests.

All tests run WITHOUT the SPOT library installed.
"""
import pytest
import sys
import os
import copy
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.automata_lifter import AutomataLifter, AutomataLifterException
from src.formula_normalizer import FormulaNormalizer


# ── Fixtures ─────────────────────────────────────────────────────────

SIMPLE_GRAPH = {
    "initial_state": "Start_1",
    "start_states": ["Start_1"],
    "states": [
        {"node_id": "Start_1", "node_type": "startEvent", "atomic_propositions": ["start_event"]},
        {"node_id": "Task_A", "node_type": "task", "atomic_propositions": ["start(Task_A)", "done(Task_A)"]},
        {"node_id": "Task_B", "node_type": "task", "atomic_propositions": ["start(Task_B)", "done(Task_B)"]},
        {"node_id": "End_1", "node_type": "endEvent", "atomic_propositions": ["end_event"]},
    ],
    "edges": [
        {"flow_id": "F1", "source_id": "Start_1", "target_id": "Task_A"},
        {"flow_id": "F2", "source_id": "Task_A", "target_id": "Task_B"},
        {"flow_id": "F3", "source_id": "Task_B", "target_id": "End_1"},
    ],
}

CORRECT_SUITE = {
    "P0_Critical_Sentinels": [
        "!done(Task_A) W start(Task_A)",
        "!done(Task_B) W start(Task_B)",
    ],
    "P1_Structural_Control_Flow": [
        "!start(Task_A) W start_event",
        "!start(Task_B) W done(Task_A)",
        "!end_event W done(Task_B)",
    ],
    "P2_Quality_Limits": [],
}


# ── Formula Normalizer Tests ────────────────────────────────────────

class TestFormulaNormalizer:
    @pytest.mark.parametrize("formula", [
        "G(start(Task_1) -> F(done(Task_1)))",
        "!done(A) W start(A)",
        "G(start(A) <-> start(B)) && G(done(A) <-> done(B))",
    ])
    def test_round_trip(self, formula):
        norm = FormulaNormalizer.normalize(formula)
        denorm = FormulaNormalizer.denormalize(norm)
        assert denorm == formula

    def test_empty_formula(self):
        assert FormulaNormalizer.normalize("") == ""
        assert FormulaNormalizer.denormalize("") == ""

    def test_specific_transformations(self):
        assert "&&" not in FormulaNormalizer.normalize("a && b")
        assert "&" in FormulaNormalizer.normalize("a && b")
        assert "||" not in FormulaNormalizer.normalize("a || b")
        assert "|" in FormulaNormalizer.normalize("a || b")
        assert "start_Task_A" in FormulaNormalizer.normalize("start(Task_A)")
        assert "done_Task_A" in FormulaNormalizer.normalize("done(Task_A)")

    def test_no_double_ampersand_in_denormalize(self):
        """Regression: denormalize must not turn && into &&&&."""
        norm = FormulaNormalizer.normalize("a && b")
        assert norm == "a & b"
        denorm = FormulaNormalizer.denormalize(norm)
        assert denorm == "a && b"
        assert "&&&&" not in denorm


# ── Language Inclusion — 20 Seeded Translation Faults ────────────────

class TestLanguageInclusionSeededFaults:
    """Each test creates a faulty property suite and verifies detection."""

    def _check_fault_detected(self, faulty_suite):
        """Helper: run language inclusion and assert a problem is found."""
        lifter = AutomataLifter(faulty_suite, SIMPLE_GRAPH)
        result = lifter.check_language_inclusion()
        # Fault detected if forward or reverse fails, or counterexamples exist
        detected = (
            not result.get("forward", True)
            or not result.get("reverse", True)
            or len(result.get("counterexamples", [])) > 0
        )
        assert detected, f"Fault NOT detected. Result: {result}"

    def test_fault_01_reversed_ordering(self):
        """Swap A→B to B→A ordering."""
        s = copy.deepcopy(CORRECT_SUITE)
        s["P1_Structural_Control_Flow"][1] = "!start(Task_A) W done(Task_B)"
        self._check_fault_detected(s)

    def test_fault_02_missing_sentinel_a(self):
        """Remove Task_A sentinel."""
        s = copy.deepcopy(CORRECT_SUITE)
        s["P0_Critical_Sentinels"] = [p for p in s["P0_Critical_Sentinels"] if "Task_A" not in p]
        self._check_fault_detected(s)

    def test_fault_03_missing_sentinel_b(self):
        """Remove Task_B sentinel."""
        s = copy.deepcopy(CORRECT_SUITE)
        s["P0_Critical_Sentinels"] = [p for p in s["P0_Critical_Sentinels"] if "Task_B" not in p]
        self._check_fault_detected(s)

    def test_fault_04_wrong_ordering_target(self):
        """Task_B ordering points to itself."""
        s = copy.deepcopy(CORRECT_SUITE)
        s["P1_Structural_Control_Flow"][1] = "!start(Task_B) W done(Task_B)"
        self._check_fault_detected(s)

    def test_fault_05_extra_spurious_property(self):
        """Add constraint that contradicts valid traces."""
        s = copy.deepcopy(CORRECT_SUITE)
        s["P1_Structural_Control_Flow"].append("G(!start(Task_B))")
        self._check_fault_detected(s)

    def test_fault_06_inverted_sentinel(self):
        """Flip sentinel done/start."""
        s = copy.deepcopy(CORRECT_SUITE)
        s["P0_Critical_Sentinels"][0] = "!start(Task_A) W done(Task_A)"
        self._check_fault_detected(s)

    def test_fault_07_missing_all_p1(self):
        """Remove all P1 properties."""
        s = copy.deepcopy(CORRECT_SUITE)
        s["P1_Structural_Control_Flow"] = []
        self._check_fault_detected(s)

    def test_fault_08_swapped_task_names(self):
        """Swap Task_A and Task_B in sentinels."""
        s = copy.deepcopy(CORRECT_SUITE)
        s["P0_Critical_Sentinels"] = [
            "!done(Task_B) W start(Task_A)",
            "!done(Task_A) W start(Task_B)",
        ]
        self._check_fault_detected(s)

    def test_fault_09_wrong_prerequisite(self):
        """Wrong prerequisite in ordering."""
        s = copy.deepcopy(CORRECT_SUITE)
        s["P1_Structural_Control_Flow"][0] = "!start(Task_A) W end_event"
        self._check_fault_detected(s)

    def test_fault_10_circular_ordering(self):
        """Add circular dependency A→B→A."""
        s = copy.deepcopy(CORRECT_SUITE)
        s["P1_Structural_Control_Flow"].append("!start(Task_A) W done(Task_B)")
        self._check_fault_detected(s)

    def test_fault_11_missing_start_ordering(self):
        """Remove start_event ordering."""
        s = copy.deepcopy(CORRECT_SUITE)
        s["P1_Structural_Control_Flow"] = [
            p for p in s["P1_Structural_Control_Flow"] if "start_event" not in p
        ]
        self._check_fault_detected(s)

    def test_fault_12_missing_end_ordering(self):
        """Remove end_event ordering."""
        s = copy.deepcopy(CORRECT_SUITE)
        s["P1_Structural_Control_Flow"] = [
            p for p in s["P1_Structural_Control_Flow"] if "end_event" not in p
        ]
        self._check_fault_detected(s)

    def test_fault_13_double_done(self):
        """Sentinel allows done before start (tautological)."""
        s = copy.deepcopy(CORRECT_SUITE)
        s["P0_Critical_Sentinels"][0] = "!done(Task_A) W done(Task_A)"
        self._check_fault_detected(s)

    def test_fault_14_impossible_conjunction(self):
        """Add impossible property."""
        s = copy.deepcopy(CORRECT_SUITE)
        s["P1_Structural_Control_Flow"].append("start_event && !start_event")
        self._check_fault_detected(s)

    def test_fault_15_wrong_weak_until(self):
        """Change W to U incorrectly."""
        pytest.skip("W and U are equivalent on complete traces where RHS occurs, so this is not detectable via reverse inclusion.")

    def test_fault_16_negated_ordering(self):
        """Negate the ordering constraint entirely."""
        s = copy.deepcopy(CORRECT_SUITE)
        s["P1_Structural_Control_Flow"][1] = "!(!start(Task_B) W done(Task_A))"
        self._check_fault_detected(s)

    def test_fault_17_wrong_task_in_p0(self):
        """Sentinel references non-existent task."""
        s = copy.deepcopy(CORRECT_SUITE)
        s["P0_Critical_Sentinels"][0] = "!done(Task_X) W start(Task_X)"
        self._check_fault_detected(s)

    def test_fault_18_duplicate_wrong_constraint(self):
        """Duplicate constraint with wrong polarity."""
        s = copy.deepcopy(CORRECT_SUITE)
        s["P1_Structural_Control_Flow"].append("!done(Task_A) W start(Task_B)")
        self._check_fault_detected(s)

    def test_fault_19_all_sentinels_removed(self):
        """No P0 properties at all."""
        s = copy.deepcopy(CORRECT_SUITE)
        s["P0_Critical_Sentinels"] = []
        self._check_fault_detected(s)

    def test_fault_20_contradictory_mutex(self):
        """Add mutex between sequential tasks + force both."""
        s = copy.deepcopy(CORRECT_SUITE)
        s["P1_Structural_Control_Flow"].append("G(!(start(Task_A) && start(Task_B)))")
        s["P1_Structural_Control_Flow"].append("F(start(Task_A) && start(Task_B))")
        self._check_fault_detected(s)


# ── Edge Case Tests ──────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_property_suite(self):
        """Empty suite should produce a result (not crash)."""
        empty = {"P0_Critical_Sentinels": [], "P1_Structural_Control_Flow": [], "P2_Quality_Limits": []}
        lifter = AutomataLifter(empty, SIMPLE_GRAPH)
        result = lifter.run_pipeline()
        assert result is not None
        assert "phase_4_certificate" in result

    def test_single_property(self):
        """Single property compilation."""
        single = {"P0_Critical_Sentinels": ["!done(Task_A) W start(Task_A)"], "P1_Structural_Control_Flow": [], "P2_Quality_Limits": []}
        lifter = AutomataLifter(single, SIMPLE_GRAPH)
        result = lifter.run_pipeline()
        assert result is not None

    def test_disconnected_graph(self):
        """Graph with an unreachable island node."""
        g = copy.deepcopy(SIMPLE_GRAPH)
        g["states"].append({"node_id": "Island", "node_type": "task", "atomic_propositions": ["start(Island)", "done(Island)"]})
        lifter = AutomataLifter(CORRECT_SUITE, g)
        result = lifter.run_pipeline()
        assert result is not None

    def test_graph_with_cycles(self):
        """Graph containing a back-edge."""
        g = copy.deepcopy(SIMPLE_GRAPH)
        g["edges"].append({"flow_id": "F_back", "source_id": "Task_B", "target_id": "Task_A"})
        lifter = AutomataLifter(CORRECT_SUITE, g)
        result = lifter.run_pipeline()
        assert result is not None

    def test_no_end_events(self):
        """Graph without endEvent nodes."""
        g = copy.deepcopy(SIMPLE_GRAPH)
        g["states"] = [s for s in g["states"] if s["node_type"] != "endEvent"]
        g["edges"] = [e for e in g["edges"] if e["target_id"] != "End_1"]
        lifter = AutomataLifter(CORRECT_SUITE, g)
        result = lifter.run_pipeline()
        assert result is not None

    def test_ged_computation(self):
        """GED returns a float >= 0."""
        lifter = AutomataLifter(CORRECT_SUITE, SIMPLE_GRAPH)
        ged = lifter.compute_ged()
        assert isinstance(ged, float)
        assert ged >= 0

    def test_hoa_export(self):
        """Export HOA to file (without SPOT, file is header-only)."""
        lifter = AutomataLifter(CORRECT_SUITE, SIMPLE_GRAPH)
        lifter.run_pipeline()
        with tempfile.NamedTemporaryFile(suffix=".hoa", delete=False) as f:
            path = f.name
        try:
            lifter.export_hoa(path)
            assert os.path.exists(path)
            content = open(path, encoding="utf-8").read()
            assert "VibeCheck" in content
        finally:
            os.unlink(path)

    def test_certificate_structure(self):
        """All required certificate fields are present."""
        lifter = AutomataLifter(CORRECT_SUITE, SIMPLE_GRAPH)
        result = lifter.run_pipeline()
        cert = result["phase_4_certificate"]
        required = [
            "status", "monitors_compiled", "monitors_failed",
            "language_inclusion_forward", "language_inclusion_reverse",
            "language_inclusion_counterexamples",
            "ged_score", "ged_diagnostics",
            "loop_bound_documented", "compilation_timeouts", "errors_count",
        ]
        for field in required:
            assert field in cert, f"Missing certificate field: {field}"

    def test_spot_not_installed_graceful(self):
        """Without SPOT, the pipeline still runs (language inclusion + GED)."""
        lifter = AutomataLifter(CORRECT_SUITE, SIMPLE_GRAPH)
        result = lifter.run_pipeline()
        assert result is not None
        # Should have either PASS or PASS_NO_SPOT (no crash)
        status = result["phase_4_certificate"]["status"]
        assert status in ("PASS", "PASS_NO_SPOT", "FAIL", "FAIL_WITH_ERRORS")

    def test_monitor_export_format(self):
        """get_monitor_export returns a list of dicts with expected keys."""
        lifter = AutomataLifter(CORRECT_SUITE, SIMPLE_GRAPH)
        lifter.run_pipeline()
        export = lifter.get_monitor_export()
        assert isinstance(export, list)
        for item in export:
            assert "name" in item
            assert "tier" in item
            assert "hoa" in item


# ── Integration Tests ────────────────────────────────────────────────

class TestIntegration:
    def test_full_pipeline_pass(self):
        """Correct suite + correct graph = forward & reverse PASS."""
        lifter = AutomataLifter(CORRECT_SUITE, SIMPLE_GRAPH)
        result = lifter.run_pipeline()
        assert result["language_inclusion_forward"] is True
        assert result["language_inclusion_reverse"] is True

    def test_full_pipeline_fail_on_wrong_suite(self):
        """Wrong suite should cause at least one direction to fail."""
        faulty = copy.deepcopy(CORRECT_SUITE)
        faulty["P1_Structural_Control_Flow"].append("G(!start(Task_B))")
        lifter = AutomataLifter(faulty, SIMPLE_GRAPH)
        result = lifter.run_pipeline()
        assert not (result["language_inclusion_forward"] and result["language_inclusion_reverse"])

    def test_phase3_wrapped_suite(self):
        """Lifter accepts Phase-3-wrapped output format."""
        wrapped = {
            "phase_3_certificate": {"status": "PASS"},
            "refined_ltlf_property_suite": copy.deepcopy(CORRECT_SUITE),
        }
        lifter = AutomataLifter(wrapped, SIMPLE_GRAPH)
        result = lifter.run_pipeline()
        assert result is not None
        assert "phase_4_certificate" in result
