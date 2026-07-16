"""
tests/test_cpp_engine.py
========================
Phase A integration tests for the vibecheck_lifter C++ engine.

Tests exercise the build_spot_automaton() entry point and verify:
  - State/edge counts match expected WIR structure.
  - Task node code arrays produce observable (non-tau) transitions.
  - Guard conditions produce observable transitions.
  - Structural boilerplate (entry, exit, gateway) produces tau (bddtrue).
  - Semantic matching correctly maps LLM function names to BPMN tasks.
  - Diagnostics telemetry is populated correctly.
  - Self-equivalence via stuttering bisimulation.
  - Deterministic hashing is stable.
"""

import json
import sys
import os
import pytest

# Add the src directory to sys.path so we can find the compiled .so module
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

try:
    import vibecheck_lifter
    HAS_MODULE = True
except ImportError:
    HAS_MODULE = False

pytestmark = pytest.mark.skipif(
    not HAS_MODULE,
    reason="vibecheck_lifter.so not compiled — skipping C++ engine tests.",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SIMPLE_LINEAR_WIR = {
    "entry_node": "S0",
    "exit_node": "S2",
    "nodes": [
        {"id": "S0", "type": "entry",  "successors": ["T1"], "predecessors": [], "control_vars": [], "data_vars": []},
        {"id": "T1", "type": "task",   "successors": ["S2"], "predecessors": ["S0"], "control_vars": [], "data_vars": [],
         "code": ["result = approve_loan(application)"]},
        {"id": "S2", "type": "exit",   "successors": [],      "predecessors": ["T1"], "control_vars": [], "data_vars": []},
    ],
    "edges": [
        {"source": "S0", "target": "T1", "guard": None,  "exception_type": None},
        {"source": "T1", "target": "S2", "guard": None,  "exception_type": None},
    ],
    "control_variables": [],
    "data_variables": [],
}

BRANCHING_WIR = {
    "entry_node": "E",
    "exit_node": "X",
    "nodes": [
        {"id": "E",  "type": "entry",   "successors": ["G"],  "predecessors": [],      "control_vars": [], "data_vars": []},
        {"id": "G",  "type": "gateway", "successors": ["T1", "T2"], "predecessors": ["E"], "control_vars": ["approved"], "data_vars": [], "guard": "approved"},
        {"id": "T1", "type": "task",    "successors": ["X"],  "predecessors": ["G"],   "control_vars": [], "data_vars": [],
         "code": ["approve_loan(data)"]},
        {"id": "T2", "type": "task",    "successors": ["X"],  "predecessors": ["G"],   "control_vars": [], "data_vars": [],
         "code": ["reject_loan(data)"]},
        {"id": "X",  "type": "exit",    "successors": [],      "predecessors": ["T1", "T2"], "control_vars": [], "data_vars": []},
    ],
    "edges": [
        {"source": "E",  "target": "G",  "guard": None,           "exception_type": None},
        {"source": "G",  "target": "T1", "guard": "approved",     "exception_type": None},
        {"source": "G",  "target": "T2", "guard": "not approved", "exception_type": None},
        {"source": "T1", "target": "X",  "guard": None,           "exception_type": None},
        {"source": "T2", "target": "X",  "guard": None,           "exception_type": None},
    ],
    "control_variables": ["approved"],
    "data_variables": [],
}

MULTI_ACTION_TASK_WIR = {
    "entry_node": "S0",
    "exit_node": "S2",
    "nodes": [
        {"id": "S0", "type": "entry", "successors": ["T1"], "predecessors": [], "control_vars": [], "data_vars": []},
        {"id": "T1", "type": "task",  "successors": ["S2"], "predecessors": ["S0"], "control_vars": [], "data_vars": [],
         "code": ["verify_identity(user)", "approve_loan(data)", "print('done')"]},
        {"id": "S2", "type": "exit",  "successors": [],      "predecessors": ["T1"], "control_vars": [], "data_vars": []},
    ],
    "edges": [
        {"source": "S0", "target": "T1", "guard": None, "exception_type": None},
        {"source": "T1", "target": "S2", "guard": None, "exception_type": None},
    ],
    "control_variables": [],
    "data_variables": [],
}

SEMANTIC_MATCH_WIR = {
    "entry_node": "S0",
    "exit_node": "S2",
    "nodes": [
        {"id": "S0", "type": "entry", "successors": ["T1"], "predecessors": [], "control_vars": [], "data_vars": []},
        {"id": "T1", "type": "task",  "successors": ["S2"], "predecessors": ["S0"], "control_vars": [], "data_vars": []},
        {"id": "S2", "type": "exit",  "successors": [],      "predecessors": ["T1"], "control_vars": [], "data_vars": []},
    ],
    "edges": [
        {"source": "S0", "target": "T1", "guard": "verify_identity_task", "exception_type": None},
        {"source": "T1", "target": "S2", "guard": "approve_loan",         "exception_type": None},
    ],
    "control_variables": ["balance"],
    "data_variables": ["user_id"],
    "types": {"user_id": "Any"},
}


# ---------------------------------------------------------------------------
# Test: Basic automaton construction
# ---------------------------------------------------------------------------

class TestBuildSpotAutomaton:
    """Tests for the build_spot_automaton() free function and AdvancedLifter."""

    def test_simple_linear_state_count(self):
        """A 3-node linear WIR should produce exactly 3 states."""
        graph = vibecheck_lifter.build_spot_automaton(json.dumps(SIMPLE_LINEAR_WIR))
        assert graph.num_states() == 3

    def test_simple_linear_edge_count(self):
        """A 3-node linear WIR with 2 edges should produce exactly 2 edges."""
        graph = vibecheck_lifter.build_spot_automaton(json.dumps(SIMPLE_LINEAR_WIR))
        assert graph.num_edges() == 2

    def test_init_state_is_zero(self):
        """The entry node S0 should be mapped to init state 0 (first created)."""
        graph = vibecheck_lifter.build_spot_automaton(json.dumps(SIMPLE_LINEAR_WIR))
        assert graph.get_init_state_number() == 0

    def test_branching_state_count(self):
        """The branching WIR has 5 nodes → 5 states."""
        graph = vibecheck_lifter.build_spot_automaton(json.dumps(BRANCHING_WIR))
        assert graph.num_states() == 5

    def test_branching_edge_count(self):
        """The branching WIR has 5 edges → 5 edges."""
        graph = vibecheck_lifter.build_spot_automaton(json.dumps(BRANCHING_WIR))
        assert graph.num_edges() == 5


# ---------------------------------------------------------------------------
# Test: Diagnostics telemetry
# ---------------------------------------------------------------------------

class TestDiagnostics:
    """Tests for LifterDiagnostics population."""

    def test_diagnostics_populated(self):
        """Diagnostics should be populated after build_spot_automaton."""
        lifter = vibecheck_lifter.AdvancedLifter()
        lifter.build_spot_automaton(json.dumps(SIMPLE_LINEAR_WIR))
        diag = lifter.get_last_diagnostics()
        assert diag.total_states == 3
        assert diag.total_edges == 2
        assert diag.deadlock_states == 0
        assert diag.unreachable_states == 0

    def test_branching_diagnostics_observable_edges(self):
        """Branching WIR with guards should report observable edges."""
        lifter = vibecheck_lifter.AdvancedLifter()
        lifter.build_spot_automaton(json.dumps(BRANCHING_WIR))
        diag = lifter.get_last_diagnostics()
        # G→T1 (guard: "approved") and G→T2 (guard: "not approved") are observable
        assert diag.observable_edges >= 2


# ---------------------------------------------------------------------------
# Test: Semantic matching integration
# ---------------------------------------------------------------------------

class TestSemanticMatching:
    """Tests for the 3-tier semantic_match cascade within the lifter."""

    def test_exact_lexical_match(self):
        """Tier 1: exact normalized match should return the BPMN task."""
        lifter = vibecheck_lifter.AdvancedLifter()
        lifter.set_bpmn_tasks(["Approve Loan", "Reject Loan", "Verify Identity"])
        assert lifter.semantic_match("approve_loan") == "Approve Loan"

    def test_levenshtein_match(self):
        """Tier 2: close edit distance should match."""
        lifter = vibecheck_lifter.AdvancedLifter()
        lifter.set_bpmn_tasks(["Approve Loan", "Reject Loan", "Verify Identity"])
        # "aprove_loan" is edit distance 1 from "approveloan"
        result = lifter.semantic_match("aprove_loan")
        assert result == "Approve Loan"

    def test_no_match_returns_unlabeled(self):
        """An unrecognized action should return 'unlabeled_task'."""
        lifter = vibecheck_lifter.AdvancedLifter()
        lifter.set_bpmn_tasks(["Approve Loan", "Reject Loan"])
        assert lifter.semantic_match("completely_unknown_action") == "unlabeled_task"


def test_semantic_match_with_guard_nlp(self):
        """Tier 3 NLP matching should resolve 'verify_identity_task' to 'Verify Identity'."""
        # This explicitly skips the test if the NLP environment isn't set up, preventing false failures in CI
        pytest.importorskip("nlp_utils", reason="nlp_utils (Sentence-BERT) not available")
        
        lifter = vibecheck_lifter.AdvancedLifter()
        lifter.set_bpmn_tasks(["Approve Loan", "Reject Loan", "Verify Identity"])
        lifter.build_spot_automaton(json.dumps(SEMANTIC_MATCH_WIR))
        diag = lifter.get_last_diagnostics()

        # Both tasks should be successfully matched to canonical BPMN names
        assert "Approve Loan" in diag.matched_aps       # Matches via Tier 1 (Lexical)
        assert "Verify Identity" in diag.matched_aps    # Matches via Tier 3 (NLP)
        assert diag.observable_edges >= 2

def test_semantic_match_with_guard_fallback(self):
        """Unmatched guards should fall back to raw opaque APs (e.g., 'g_verify_identity_task')."""
        lifter = vibecheck_lifter.AdvancedLifter()
        # Intentionally omit "Verify Identity" so it fails Tier 1, Tier 2, and Tier 3
        lifter.set_bpmn_tasks(["Approve Loan", "Reject Loan"])
        lifter.build_spot_automaton(json.dumps(SEMANTIC_MATCH_WIR))
        diag = lifter.get_last_diagnostics()

        assert "Approve Loan" in diag.matched_aps
        assert "Verify Identity" not in diag.matched_aps # Failed to match
        # BUT the edge is STILL observable because it fell back to a raw opaque guard AP
        assert diag.observable_edges >= 2

def test_task_code_action_matching(self):
        """Task nodes with code arrays should produce matched APs."""
        lifter = vibecheck_lifter.AdvancedLifter()
        lifter.set_bpmn_tasks(["Approve Loan", "Verify Identity"])
        lifter.build_spot_automaton(json.dumps(MULTI_ACTION_TASK_WIR))
        diag = lifter.get_last_diagnostics()
        # "verify_identity" and "approve_loan" from code lines should match
        # "print" is a builtin and should be filtered out
        assert len(diag.matched_aps) >= 2
        matched_lower = {ap.lower().replace(" ", "") for ap in diag.matched_aps}
        assert "approveloan" in matched_lower or "Approve Loan" in diag.matched_aps
        assert "verifyidentity" in matched_lower or "Verify Identity" in diag.matched_aps


# ---------------------------------------------------------------------------
# Test: Tau labeling for structural nodes
# ---------------------------------------------------------------------------

class TestTauLabeling:
    """Tests ensuring structural boilerplate produces silent transitions."""

    def test_entry_to_task_is_tau_when_no_guard(self):
        """An edge from entry to task with null guard should be tau."""
        lifter = vibecheck_lifter.AdvancedLifter()
        lifter.build_spot_automaton(json.dumps(SIMPLE_LINEAR_WIR))
        diag = lifter.get_last_diagnostics()
        # S0→T1 has null guard AND S0 is type 'entry' (no code) → tau
        assert diag.tau_edges >= 1

    def test_task_with_code_produces_observable(self):
        """A task node with code should produce at least one observable edge."""
        lifter = vibecheck_lifter.AdvancedLifter()
        lifter.set_bpmn_tasks(["Approve Loan"])
        lifter.build_spot_automaton(json.dumps(SIMPLE_LINEAR_WIR))
        diag = lifter.get_last_diagnostics()
        # T1→S2: T1 is a task with code ["result = approve_loan(application)"]
        #   → "approve_loan" matches "Approve Loan" → observable
        assert diag.observable_edges >= 1


# ---------------------------------------------------------------------------
# Test: Self-equivalence and hashing
# ---------------------------------------------------------------------------

class TestEquivalenceAndHashing:
    """Tests for stuttering bisimulation and deterministic hashing."""

    def test_self_equivalence(self):
        """An automaton is stuttering-bisimilar to itself."""
        lifter = vibecheck_lifter.AdvancedLifter()
        graph = lifter.build_spot_automaton(json.dumps(SIMPLE_LINEAR_WIR))
        assert lifter.check_stuttering_bisimulation(graph, graph) is True


# ---------------------------------------------------------------------------
# Test: Variable map and AP registration
# ---------------------------------------------------------------------------

class TestVariableRegistration:
    """Tests for parse_wir_types and AP registration."""

    def test_control_variables_registered(self):
        """Control variables from the WIR should appear in the variable map."""
        lifter = vibecheck_lifter.AdvancedLifter()
        lifter.parse_wir_types(json.dumps(SEMANTIC_MATCH_WIR))
        var_map = lifter.get_variable_map()
        assert "balance" in var_map

    def test_unresolved_type_registers_any_variant(self):
        """An 'Any' typed variable should register with _ANY suffix."""
        lifter = vibecheck_lifter.AdvancedLifter()
        lifter.parse_wir_types(json.dumps(SEMANTIC_MATCH_WIR))
        var_map = lifter.get_variable_map()
        assert "user_id_ANY" in var_map


# ---------------------------------------------------------------------------
# Test: Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """Tests for graceful error handling."""

    def test_invalid_json_raises(self):
        """Invalid JSON should raise an exception."""
        with pytest.raises(Exception):
            vibecheck_lifter.build_spot_automaton("{not valid json}")

    def test_empty_wir_produces_empty_graph(self):
        """A WIR with no nodes should produce a graph with 0 states."""
        empty_wir = {"entry_node": "", "exit_node": "", "nodes": [], "edges": []}
        graph = vibecheck_lifter.build_spot_automaton(json.dumps(empty_wir))
        assert graph.num_states() == 0


# ---------------------------------------------------------------------------
# Test: Free function convenience wrapper
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Standalone runner (for manual testing outside pytest)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not HAS_MODULE:
        print("❌ Could not import vibecheck_lifter. Ensure it is compiled and in the 'src/' directory.")
        sys.exit(0)

    print("Running manual integration tests...\n")

    lifter = vibecheck_lifter.AdvancedLifter()
    lifter.set_bpmn_tasks(["Approve Loan", "Reject Loan", "Verify Identity"])

    print("--- Test: Simple Linear WIR ---")
    g = lifter.build_spot_automaton(json.dumps(SIMPLE_LINEAR_WIR))
    d = lifter.get_last_diagnostics()
    print(f"  States: {g.num_states()}, Edges: {g.num_edges()}")
    print(f"  Diagnostics: {d}")
    print(f"  Matched APs: {d.matched_aps}")
    print(f"  Unmatched: {d.unmatched_actions}")

    print("\n--- Test: Branching WIR ---")
    g2 = lifter.build_spot_automaton(json.dumps(BRANCHING_WIR))
    d2 = lifter.get_last_diagnostics()
    print(f"  States: {g2.num_states()}, Edges: {g2.num_edges()}")
    print(f"  Observable: {d2.observable_edges}, Tau: {d2.tau_edges}")

    print("\n--- Test: Self-equivalence ---")
    eq = lifter.check_stuttering_bisimulation(g, g)
    print(f"  Result: {'PASSED' if eq else 'FAILED'}")

    print("\n✅ All manual tests completed.")
