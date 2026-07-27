"""
tests/test_phase_b.py
=====================
Phase B integration tests for the vibecheck_lifter C++ engine.

Tests exercise the new Phase B API:
  - detect_divergent_states(): Divergence detection via spot::scc_info
  - minimize_stuttering(): Quotient automaton construction
  - compute_bisimulation_full(): Full result with partition + diagnostics
  - check_stuttering_bisimulation(): Rewritten disjoint-union approach
  - tarjan_tau_collapse(): Rewritten with spot::scc_info

WIR fixtures are crafted to produce specific graph topologies:
  - Tau self-loops, tau cycles, backward BFS propagation
  - Stuttering-equivalent and non-equivalent graph pairs
"""

import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

try:
    import vibecheck_lifter
    HAS_MODULE = True
except ImportError:
    HAS_MODULE = False

pytestmark = pytest.mark.skipif(
    not HAS_MODULE,
    reason="vibecheck_lifter.so not compiled — skipping Phase B tests.",
)

# ---------------------------------------------------------------------------
# WIR Fixtures
# ---------------------------------------------------------------------------

# Linear graph: S0 --tau--> T1 --action--> S2
# No divergence possible.
LINEAR_WIR = {
    "entry_node": "S0", "exit_node": "S2",
    "nodes": [
        {"id": "S0", "type": "entry",  "successors": ["T1"], "predecessors": [], "control_vars": [], "data_vars": []},
        {"id": "T1", "type": "task",   "successors": ["S2"], "predecessors": ["S0"], "control_vars": [], "data_vars": [],
         "code": ["approve_loan(data)"]},
        {"id": "S2", "type": "exit",   "successors": [],      "predecessors": ["T1"], "control_vars": [], "data_vars": []},
    ],
    "edges": [
        {"source": "S0", "target": "T1", "guard": None, "exception_type": None},
        {"source": "T1", "target": "S2", "guard": None, "exception_type": None},
    ],
    "control_variables": [], "data_variables": [],
}

# Tau self-loop: S0 --tau--> S1 --tau--> S1 (self-loop) --exit_flag--> S2
# S1 is divergent (tau self-loop). S0 is divergent (can reach S1 via tau).
TAU_SELFLOOP_WIR = {
    "entry_node": "S0", "exit_node": "S2",
    "nodes": [
        {"id": "S0", "type": "entry", "successors": ["S1"],      "predecessors": [],       "control_vars": [], "data_vars": []},
        {"id": "S1", "type": "block", "successors": ["S1", "S2"], "predecessors": ["S0", "S1"], "control_vars": [], "data_vars": []},
        {"id": "S2", "type": "exit",  "successors": [],           "predecessors": ["S1"],   "control_vars": [], "data_vars": []},
    ],
    "edges": [
        {"source": "S0", "target": "S1", "guard": None,        "exception_type": None},
        {"source": "S1", "target": "S1", "guard": None,        "exception_type": None},
        {"source": "S1", "target": "S2", "guard": "exit_flag", "exception_type": None},
    ],
    "control_variables": [], "data_variables": [],
}

# Tau cycle: S0 --tau--> S1 --tau--> S2 --tau--> S1 (cycle) --done--> S3
# S1 and S2 form a divergent tau cycle. S0 is divergent (backward BFS).
TAU_CYCLE_WIR = {
    "entry_node": "S0", "exit_node": "S3",
    "nodes": [
        {"id": "S0", "type": "entry",   "successors": ["S1"],      "predecessors": [],          "control_vars": [], "data_vars": []},
        {"id": "S1", "type": "block",   "successors": ["S2"],      "predecessors": ["S0", "S2"], "control_vars": [], "data_vars": []},
        {"id": "S2", "type": "gateway", "successors": ["S1", "S3"], "predecessors": ["S1"],      "control_vars": [], "data_vars": []},
        {"id": "S3", "type": "exit",    "successors": [],           "predecessors": ["S2"],      "control_vars": [], "data_vars": []},
    ],
    "edges": [
        {"source": "S0", "target": "S1", "guard": None,   "exception_type": None},
        {"source": "S1", "target": "S2", "guard": None,   "exception_type": None},
        {"source": "S2", "target": "S1", "guard": None,   "exception_type": None},
        {"source": "S2", "target": "S3", "guard": "done", "exception_type": None},
    ],
    "control_variables": [], "data_variables": [],
}

# Backward BFS test: S0 --tau--> S1 --tau--> S2 --tau(self)--> S2 --complete--> S3
# S2 is directly divergent (self-loop). S1 and S0 are divergent via backward BFS.
BACKWARD_BFS_WIR = {
    "entry_node": "S0", "exit_node": "S3",
    "nodes": [
        {"id": "S0", "type": "entry", "successors": ["S1"],      "predecessors": [],       "control_vars": [], "data_vars": []},
        {"id": "S1", "type": "block", "successors": ["S2"],      "predecessors": ["S0"],   "control_vars": [], "data_vars": []},
        {"id": "S2", "type": "block", "successors": ["S2", "S3"], "predecessors": ["S1", "S2"], "control_vars": [], "data_vars": []},
        {"id": "S3", "type": "exit",  "successors": [],           "predecessors": ["S2"],   "control_vars": [], "data_vars": []},
    ],
    "edges": [
        {"source": "S0", "target": "S1", "guard": None,       "exception_type": None},
        {"source": "S1", "target": "S2", "guard": None,       "exception_type": None},
        {"source": "S2", "target": "S2", "guard": None,       "exception_type": None},
        {"source": "S2", "target": "S3", "guard": "complete", "exception_type": None},
    ],
    "control_variables": [], "data_variables": [],
}

# Stuttering pair A: S0 --action_x--> S1
# (Edge from entry with guard "action_x" → observable)
STUTTER_A_WIR = {
    "entry_node": "S0", "exit_node": "S1",
    "nodes": [
        {"id": "S0", "type": "entry", "successors": ["S1"], "predecessors": [], "control_vars": [], "data_vars": []},
        {"id": "S1", "type": "exit",  "successors": [],      "predecessors": ["S0"], "control_vars": [], "data_vars": []},
    ],
    "edges": [
        {"source": "S0", "target": "S1", "guard": "action_x", "exception_type": None},
    ],
    "control_variables": [], "data_variables": [],
}

# Stuttering pair B: T0 --tau--> T1 --action_x--> T2
# Should be stuttering bisimilar to pair A.
STUTTER_B_WIR = {
    "entry_node": "T0", "exit_node": "T2",
    "nodes": [
        {"id": "T0", "type": "entry", "successors": ["T1"], "predecessors": [],     "control_vars": [], "data_vars": []},
        {"id": "T1", "type": "block", "successors": ["T2"], "predecessors": ["T0"], "control_vars": [], "data_vars": []},
        {"id": "T2", "type": "exit",  "successors": [],      "predecessors": ["T1"], "control_vars": [], "data_vars": []},
    ],
    "edges": [
        {"source": "T0", "target": "T1", "guard": None,       "exception_type": None},
        {"source": "T1", "target": "T2", "guard": "action_x", "exception_type": None},
    ],
    "control_variables": [], "data_variables": [],
}

# Non-equivalent pair: U0 --action_y--> U1  (different observable action)
NONEQUIV_WIR = {
    "entry_node": "U0", "exit_node": "U1",
    "nodes": [
        {"id": "U0", "type": "entry", "successors": ["U1"], "predecessors": [], "control_vars": [], "data_vars": []},
        {"id": "U1", "type": "exit",  "successors": [],      "predecessors": ["U0"], "control_vars": [], "data_vars": []},
    ],
    "edges": [
        {"source": "U0", "target": "U1", "guard": "action_y", "exception_type": None},
    ],
    "control_variables": [], "data_variables": [],
}

# Branching graph for quotient test
BRANCH_WIR = {
    "entry_node": "E", "exit_node": "X",
    "nodes": [
        {"id": "E",  "type": "entry",   "successors": ["G"],       "predecessors": [],            "control_vars": [], "data_vars": []},
        {"id": "G",  "type": "gateway", "successors": ["T1", "T2"], "predecessors": ["E"],        "control_vars": [], "data_vars": []},
        {"id": "T1", "type": "task",    "successors": ["X"],       "predecessors": ["G"],         "control_vars": [], "data_vars": [],
         "code": ["approve(data)"]},
        {"id": "T2", "type": "task",    "successors": ["X"],       "predecessors": ["G"],         "control_vars": [], "data_vars": [],
         "code": ["reject(data)"]},
        {"id": "X",  "type": "exit",    "successors": [],           "predecessors": ["T1", "T2"], "control_vars": [], "data_vars": []},
    ],
    "edges": [
        {"source": "E",  "target": "G",  "guard": None,     "exception_type": None},
        {"source": "G",  "target": "T1", "guard": "yes",    "exception_type": None},
        {"source": "G",  "target": "T2", "guard": "no",     "exception_type": None},
        {"source": "T1", "target": "X",  "guard": None,     "exception_type": None},
        {"source": "T2", "target": "X",  "guard": None,     "exception_type": None},
    ],
    "control_variables": [], "data_variables": [],
}


# ---------------------------------------------------------------------------
# Test: Divergence Detection
# ---------------------------------------------------------------------------

class TestDivergenceDetection:
    """Tests for detect_divergent_states()."""

    def test_linear_no_divergence(self):
        """A linear graph with no tau cycles has zero divergent states."""
        lifter = vibecheck_lifter.AdvancedLifter()
        lifter.set_bpmn_tasks(["Approve Loan"])
        graph = lifter.build_spot_automaton(json.dumps(LINEAR_WIR))
        div = lifter.detect_divergent_states(graph)
        assert len(div) == 3
        assert not any(div), f"Expected no divergent states, got {div}"

    def test_tau_selfloop_detected(self):
        """A state with a tau self-loop is divergent."""
        lifter = vibecheck_lifter.AdvancedLifter()
        graph = lifter.build_spot_automaton(json.dumps(TAU_SELFLOOP_WIR))
        div = lifter.detect_divergent_states(graph)
        assert len(div) == 3
        # S1 (state index 1) has a tau self-loop → divergent
        assert div[1] is True, "S1 should be divergent (tau self-loop)"

    def test_tau_cycle_detected(self):
        """States in a multi-state tau cycle are divergent."""
        lifter = vibecheck_lifter.AdvancedLifter()
        graph = lifter.build_spot_automaton(json.dumps(TAU_CYCLE_WIR))
        div = lifter.detect_divergent_states(graph)
        # S1 (index 1) and S2 (index 2) form a tau cycle
        assert div[1] is True, "S1 should be divergent (tau cycle member)"
        assert div[2] is True, "S2 should be divergent (tau cycle member)"

    def test_backward_bfs_propagation(self):
        """States that can reach divergent states via tau are also divergent."""
        lifter = vibecheck_lifter.AdvancedLifter()
        graph = lifter.build_spot_automaton(json.dumps(BACKWARD_BFS_WIR))
        div = lifter.detect_divergent_states(graph)
        # S2 (index 2) has self-loop → directly divergent
        # S1 (index 1) can reach S2 via tau → divergent via backward BFS
        # S0 (index 0) can reach S1 via tau → divergent via backward BFS
        assert div[2] is True, "S2 should be directly divergent"
        assert div[1] is True, "S1 should be divergent via backward BFS"
        assert div[0] is True, "S0 should be divergent via backward BFS"

    def test_exit_state_not_divergent(self):
        """Exit states without tau transitions are never divergent."""
        lifter = vibecheck_lifter.AdvancedLifter()
        graph = lifter.build_spot_automaton(json.dumps(BACKWARD_BFS_WIR))
        div = lifter.detect_divergent_states(graph)
        # S3 (index 3) is exit, no tau out or self-loop
        assert div[3] is False, "Exit state S3 should not be divergent"

    def test_empty_graph_no_divergence(self):
        """An empty graph returns an empty divergence vector."""
        lifter = vibecheck_lifter.AdvancedLifter()
        empty_wir = {"entry_node": "", "exit_node": "", "nodes": [], "edges": []}
        graph = lifter.build_spot_automaton(json.dumps(empty_wir))
        div = lifter.detect_divergent_states(graph)
        assert len(div) == 0


# ---------------------------------------------------------------------------
# Test: Minimize Stuttering (Quotient Construction)
# ---------------------------------------------------------------------------

class TestMinimizeStuttering:
    """Tests for minimize_stuttering() quotient automaton."""

    def test_linear_quotient_no_reduction(self):
        """A minimal linear graph cannot be reduced further."""
        lifter = vibecheck_lifter.AdvancedLifter()
        lifter.set_bpmn_tasks(["Approve Loan"])
        graph = lifter.build_spot_automaton(json.dumps(LINEAR_WIR))
        quotient = lifter.minimize_stuttering(graph)
        # Linear: S0 --tau--> T1 --observable--> S2
        # S0 and T1 might be merged (stuttering tau) if no
        # observable difference. They CAN differ because T1 has an
        # observable outgoing edge and S0 does not.
        assert quotient.num_states() <= graph.num_states()
        assert quotient.num_states() >= 1

    def test_selfloop_quotient_preserves_structure(self):
        """Quotient preserves observable behavior despite divergence."""
        lifter = vibecheck_lifter.AdvancedLifter()
        graph = lifter.build_spot_automaton(json.dumps(TAU_SELFLOOP_WIR))
        quotient = lifter.minimize_stuttering(graph)
        # The quotient should be smaller or equal
        assert quotient.num_states() <= graph.num_states()
        # Must still have at least one edge for the observable transition
        assert quotient.num_edges() >= 1

    def test_tau_cycle_collapses(self):
        """A tau cycle should be collapsed by stuttering minimization."""
        lifter = vibecheck_lifter.AdvancedLifter()
        graph = lifter.build_spot_automaton(json.dumps(TAU_CYCLE_WIR))
        quotient = lifter.minimize_stuttering(graph)
        # S1 and S2 form a divergent tau cycle, should collapse
        assert quotient.num_states() < graph.num_states()

    def test_branching_quotient(self):
        """Branching graph with distinct branches should not over-collapse."""
        lifter = vibecheck_lifter.AdvancedLifter()
        lifter.set_bpmn_tasks(["Approve", "Reject"])
        graph = lifter.build_spot_automaton(json.dumps(BRANCH_WIR))
        quotient = lifter.minimize_stuttering(graph)
        # Must preserve at least the two distinct branches
        assert quotient.num_states() >= 2
        assert quotient.num_edges() >= 2


# ---------------------------------------------------------------------------
# Test: compute_bisimulation_full (Diagnostics)
# ---------------------------------------------------------------------------

class TestBisimulationFull:
    """Tests for compute_bisimulation_full() result structure."""

    def test_result_fields_populated(self):
        """BisimulationResult should have all fields populated."""
        lifter = vibecheck_lifter.AdvancedLifter()
        graph = lifter.build_spot_automaton(json.dumps(TAU_SELFLOOP_WIR))
        result = lifter.compute_bisimulation_full(graph)
        assert result.original_states == 3
        assert result.quotient_states <= 3
        assert result.quotient_states == result.num_partition_blocks
        assert len(result.partition) == 3
        assert len(result.divergent) == 3

    def test_divergent_count_matches(self):
        """num_divergent should match the count of True in divergent vector."""
        lifter = vibecheck_lifter.AdvancedLifter()
        graph = lifter.build_spot_automaton(json.dumps(TAU_CYCLE_WIR))
        result = lifter.compute_bisimulation_full(graph)
        assert result.num_divergent == sum(result.divergent)

    def test_partition_blocks_contiguous(self):
        """Partition blocks should be contiguously numbered 0..k-1."""
        lifter = vibecheck_lifter.AdvancedLifter()
        graph = lifter.build_spot_automaton(json.dumps(BRANCH_WIR))
        result = lifter.compute_bisimulation_full(graph)
        blocks = set(result.partition)
        assert blocks == set(range(result.num_partition_blocks))

    def test_quotient_matches_minimize(self):
        """compute_bisimulation_full quotient should match minimize_stuttering."""
        lifter = vibecheck_lifter.AdvancedLifter()
        graph = lifter.build_spot_automaton(json.dumps(LINEAR_WIR))
        result = lifter.compute_bisimulation_full(graph)
        quotient_direct = lifter.minimize_stuttering(graph)
        assert result.quotient.num_states() == quotient_direct.num_states()
        assert result.quotient.num_edges() == quotient_direct.num_edges()

    def test_nondivergent_result(self):
        """A graph with no divergence should report 0 divergent states."""
        lifter = vibecheck_lifter.AdvancedLifter()
        lifter.set_bpmn_tasks(["Approve Loan"])
        graph = lifter.build_spot_automaton(json.dumps(LINEAR_WIR))
        result = lifter.compute_bisimulation_full(graph)
        assert result.num_divergent == 0
        assert not any(result.divergent)

    def test_repr_string(self):
        """BisimulationResult should have a useful repr."""
        lifter = vibecheck_lifter.AdvancedLifter()
        graph = lifter.build_spot_automaton(json.dumps(TAU_SELFLOOP_WIR))
        result = lifter.compute_bisimulation_full(graph)
        r = repr(result)
        assert "BisimulationResult" in r
        assert "original=" in r
        assert "quotient=" in r


# ---------------------------------------------------------------------------
# Test: Stuttering Bisimulation Check (Rewritten)
# ---------------------------------------------------------------------------

class TestStutteringBisimulation:
    """Tests for check_stuttering_bisimulation() with the new Phase B backend."""

    def test_self_equivalence(self):
        """An automaton is always stuttering bisimilar to itself."""
        lifter = vibecheck_lifter.AdvancedLifter()
        graph = lifter.build_spot_automaton(json.dumps(LINEAR_WIR))
        assert lifter.check_stuttering_bisimulation(graph, graph) is True

    def test_stuttering_equivalent_pair(self):
        """A --action_x--> B should be bisimilar to C --tau--> D --action_x--> E."""
        lifter = vibecheck_lifter.AdvancedLifter()
        g1 = lifter.build_spot_automaton(json.dumps(STUTTER_A_WIR))
        g2 = lifter.build_spot_automaton(json.dumps(STUTTER_B_WIR))
        assert lifter.check_stuttering_bisimulation(g1, g2) is True

    def test_nonequivalent_different_actions(self):
        """Graphs with different observable actions are NOT bisimilar."""
        lifter = vibecheck_lifter.AdvancedLifter()
        g1 = lifter.build_spot_automaton(json.dumps(STUTTER_A_WIR))
        g2 = lifter.build_spot_automaton(json.dumps(NONEQUIV_WIR))
        assert lifter.check_stuttering_bisimulation(g1, g2) is False

    def test_divergent_vs_nondivergent(self):
        """A divergent graph is NOT bisimilar to a non-divergent one
        (divergence-sensitive: initial partition separates them)."""
        lifter = vibecheck_lifter.AdvancedLifter()
        g_div = lifter.build_spot_automaton(json.dumps(TAU_SELFLOOP_WIR))
        g_lin = lifter.build_spot_automaton(json.dumps(LINEAR_WIR))
        assert lifter.check_stuttering_bisimulation(g_div, g_lin) is False

    def test_self_equivalence_divergent(self):
        """A divergent automaton is bisimilar to itself."""
        lifter = vibecheck_lifter.AdvancedLifter()
        graph = lifter.build_spot_automaton(json.dumps(TAU_CYCLE_WIR))
        assert lifter.check_stuttering_bisimulation(graph, graph) is True

    def test_branching_self_equivalence(self):
        """Branching graph is bisimilar to itself."""
        lifter = vibecheck_lifter.AdvancedLifter()
        lifter.set_bpmn_tasks(["Approve", "Reject"])
        graph = lifter.build_spot_automaton(json.dumps(BRANCH_WIR))
        assert lifter.check_stuttering_bisimulation(graph, graph) is True


# ---------------------------------------------------------------------------
# Test: Tau-SCC Collapse (Rewritten with spot::scc_info)
# ---------------------------------------------------------------------------

class TestTauSccCollapse:
    """Tests for tarjan_tau_collapse() with the new spot::scc_info backend."""

    def test_linear_no_collapse(self):
        """A linear graph with no tau cycles should not collapse."""
        lifter = vibecheck_lifter.AdvancedLifter()
        lifter.set_bpmn_tasks(["Approve Loan"])
        graph = lifter.build_spot_automaton(json.dumps(LINEAR_WIR))
        collapsed = lifter.tarjan_tau_collapse(graph)
        # No tau-SCC to collapse → same state count
        assert collapsed.num_states() == graph.num_states()

    def test_selfloop_collapses(self):
        """A tau self-loop doesn't reduce state count (single-state SCC)."""
        lifter = vibecheck_lifter.AdvancedLifter()
        graph = lifter.build_spot_automaton(json.dumps(TAU_SELFLOOP_WIR))
        collapsed = lifter.tarjan_tau_collapse(graph)
        # S1 self-loop is a single-state SCC (with self-loop) — but
        # tarjan_tau_collapse merges SCC members, which for a single
        # state is a no-op. The self-loop edge within the SCC is dropped.
        assert collapsed.num_states() == graph.num_states()

    def test_tau_cycle_collapses(self):
        """A 2-state tau cycle should collapse to a single state."""
        lifter = vibecheck_lifter.AdvancedLifter()
        graph = lifter.build_spot_automaton(json.dumps(TAU_CYCLE_WIR))
        collapsed = lifter.tarjan_tau_collapse(graph)
        # S1 and S2 form a 2-state SCC → collapsed to 1 state
        assert collapsed.num_states() < graph.num_states()
        assert collapsed.num_states() == graph.num_states() - 1  # 4 → 3

    def test_init_state_preserved(self):
        """The init state mapping should be correct after collapse."""
        lifter = vibecheck_lifter.AdvancedLifter()
        graph = lifter.build_spot_automaton(json.dumps(TAU_CYCLE_WIR))
        collapsed = lifter.tarjan_tau_collapse(graph)
        # Init state should be valid
        assert collapsed.get_init_state_number() < collapsed.num_states()


# ---------------------------------------------------------------------------
# Test: Deterministic Hashing (backward compat after rewrite)
# ---------------------------------------------------------------------------

class TestHashingPostRewrite:
    """Ensure deterministic hashing still works after Phase B rewrite."""

    def test_hash_stability_after_rewrite(self):
        """Hash should be deterministic after the Phase B rewrite."""
        lifter = vibecheck_lifter.AdvancedLifter()
        graph = lifter.build_spot_automaton(json.dumps(LINEAR_WIR))
        h1 = lifter.compute_deterministic_hash(graph)
        h2 = lifter.compute_deterministic_hash(graph)
        assert h1 == h2

    def test_quotient_hash_differs_from_original(self):
        """The quotient of a reducible graph should hash differently."""
        lifter = vibecheck_lifter.AdvancedLifter()
        graph = lifter.build_spot_automaton(json.dumps(TAU_CYCLE_WIR))
        quotient = lifter.minimize_stuttering(graph)
        h_orig = lifter.compute_deterministic_hash(graph)
        h_quot = lifter.compute_deterministic_hash(quotient)
        # The quotient has fewer states → almost certainly different hash
        if quotient.num_states() < graph.num_states():
            assert h_orig != h_quot
