"""
tests/test_phase_c.py
=====================
Phase C integration tests for the VibeCheck clustering engine.

Tests exercise:
  - C++ cluster_implementations() via Pybind11
  - Python process_wir_batch() orchestrator
  - Shared bdd_dict invariant enforcement
  - Representative selection (min states, then min edges)
  - Isomorphic / non-isomorphic clustering correctness
  - Empty and single-element edge cases
"""

import json
import sys
import os
import pytest

# Add the src directory to sys.path for the compiled .so module
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

try:
    import vibecheck_lifter
    HAS_MODULE = True
except ImportError:
    HAS_MODULE = False

pytestmark = pytest.mark.skipif(
    not HAS_MODULE,
    reason="vibecheck_lifter.so not compiled — skipping Phase C tests.",
)


# ---------------------------------------------------------------------------
# WIR Fixtures
# ---------------------------------------------------------------------------

# Linear: S0 --tau--> T1 --action--> S2   (3 states, 2 edges)
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

# Structurally identical to LINEAR_WIR but different node IDs
# → should be isomorphic after minimization
LINEAR_WIR_VARIANT = {
    "entry_node": "A0", "exit_node": "A2",
    "nodes": [
        {"id": "A0", "type": "entry",  "successors": ["A1"], "predecessors": [], "control_vars": [], "data_vars": []},
        {"id": "A1", "type": "task",   "successors": ["A2"], "predecessors": ["A0"], "control_vars": [], "data_vars": [],
         "code": ["approve_loan(data)"]},
        {"id": "A2", "type": "exit",   "successors": [],      "predecessors": ["A1"], "control_vars": [], "data_vars": []},
    ],
    "edges": [
        {"source": "A0", "target": "A1", "guard": None, "exception_type": None},
        {"source": "A1", "target": "A2", "guard": None, "exception_type": None},
    ],
    "control_variables": [], "data_variables": [],
}

# Branching: E --tau--> G --approved--> T1 --tau--> X
#                         --!approved-> T2 --tau--> X
# (5 states, 5 edges) → structurally different from LINEAR
BRANCHING_WIR = {
    "entry_node": "E", "exit_node": "X",
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
    "control_variables": ["approved"], "data_variables": [],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_and_minimize(lifter, wir_dict):
    """Build a SPOT automaton from a WIR dict, then minimize it."""
    graph = lifter.build_spot_automaton(json.dumps(wir_dict))
    return lifter.minimize_stuttering(graph)


# ---------------------------------------------------------------------------
# Test: cluster_implementations() core behaviour
# ---------------------------------------------------------------------------

class TestClusterImplementations:
    """Tests for the C++ cluster_implementations() function."""

    def test_empty_input(self):
        """An empty vector should produce zero clusters."""
        clusters = vibecheck_lifter.cluster_implementations([])
        assert len(clusters) == 0

    def test_single_automaton(self):
        """A single graph should form exactly one cluster of size 1."""
        lifter = vibecheck_lifter.AdvancedLifter()
        q = _build_and_minimize(lifter, LINEAR_WIR)

        clusters = vibecheck_lifter.cluster_implementations([q])
        assert len(clusters) == 1

        entry = list(clusters.values())[0]
        assert entry.indices == [0]
        assert entry.representative is not None

    def test_isomorphic_pair_same_cluster(self):
        """Two isomorphic quotient automata should be in the same cluster."""
        lifter = vibecheck_lifter.AdvancedLifter()
        q1 = _build_and_minimize(lifter, LINEAR_WIR)
        q2 = _build_and_minimize(lifter, LINEAR_WIR_VARIANT)

        clusters = vibecheck_lifter.cluster_implementations([q1, q2])
        assert len(clusters) == 1

        entry = list(clusters.values())[0]
        assert sorted(entry.indices) == [0, 1]

    def test_non_isomorphic_separate_clusters(self):
        """A linear and a branching WIR should produce different clusters."""
        lifter = vibecheck_lifter.AdvancedLifter()
        q_linear = _build_and_minimize(lifter, LINEAR_WIR)
        q_branch = _build_and_minimize(lifter, BRANCHING_WIR)

        clusters = vibecheck_lifter.cluster_implementations([q_linear, q_branch])
        assert len(clusters) == 2

        # Each cluster has exactly one member
        for entry in clusters.values():
            assert len(entry.indices) == 1

    def test_mixed_batch(self):
        """A batch with 2 isomorphic + 1 different → 2 clusters."""
        lifter = vibecheck_lifter.AdvancedLifter()
        q1 = _build_and_minimize(lifter, LINEAR_WIR)
        q2 = _build_and_minimize(lifter, LINEAR_WIR_VARIANT)
        q3 = _build_and_minimize(lifter, BRANCHING_WIR)

        clusters = vibecheck_lifter.cluster_implementations([q1, q2, q3])
        assert len(clusters) == 2

        # Find which cluster has 2 members
        sizes = sorted(len(e.indices) for e in clusters.values())
        assert sizes == [1, 2]

    def test_representative_selection_fewest_states(self):
        """Representative should be the automaton with fewest states."""
        lifter = vibecheck_lifter.AdvancedLifter()
        q1 = _build_and_minimize(lifter, LINEAR_WIR)
        q2 = _build_and_minimize(lifter, LINEAR_WIR_VARIANT)

        clusters = vibecheck_lifter.cluster_implementations([q1, q2])
        entry = list(clusters.values())[0]

        rep = entry.representative
        # The representative should have <= states of any member
        assert rep.num_states() <= q1.num_states()
        assert rep.num_states() <= q2.num_states()

    def test_all_identical(self):
        """Three copies of the same WIR → single cluster with 3 members."""
        lifter = vibecheck_lifter.AdvancedLifter()
        qs = [_build_and_minimize(lifter, LINEAR_WIR) for _ in range(3)]

        clusters = vibecheck_lifter.cluster_implementations(qs)
        assert len(clusters) == 1
        assert sorted(list(clusters.values())[0].indices) == [0, 1, 2]

    def test_all_different(self):
        """Linear, variant, and branching all through separate lifter calls.
        Note: LINEAR and VARIANT are isomorphic, so we get 2 clusters.
        """
        lifter = vibecheck_lifter.AdvancedLifter()
        q1 = _build_and_minimize(lifter, LINEAR_WIR)
        q2 = _build_and_minimize(lifter, BRANCHING_WIR)

        clusters = vibecheck_lifter.cluster_implementations([q1, q2])
        assert len(clusters) == 2


# ---------------------------------------------------------------------------
# Test: ClusterEntry Pybind11 binding
# ---------------------------------------------------------------------------

class TestClusterEntryBinding:
    """Tests for the ClusterEntry wrapper."""

    def test_repr(self):
        """ClusterEntry should have a readable repr."""
        lifter = vibecheck_lifter.AdvancedLifter()
        q = _build_and_minimize(lifter, LINEAR_WIR)

        clusters = vibecheck_lifter.cluster_implementations([q])
        entry = list(clusters.values())[0]
        r = repr(entry)
        assert "ClusterEntry" in r
        assert "indices=" in r
        assert "rep_states=" in r

    def test_indices_is_list(self):
        """ClusterEntry.indices should be a Python list of ints."""
        lifter = vibecheck_lifter.AdvancedLifter()
        q = _build_and_minimize(lifter, LINEAR_WIR)

        clusters = vibecheck_lifter.cluster_implementations([q])
        entry = list(clusters.values())[0]
        assert isinstance(entry.indices, list)
        assert all(isinstance(i, int) for i in entry.indices)

    def test_representative_is_twa_graph(self):
        """ClusterEntry.representative should be a TwaGraph instance."""
        lifter = vibecheck_lifter.AdvancedLifter()
        q = _build_and_minimize(lifter, LINEAR_WIR)

        clusters = vibecheck_lifter.cluster_implementations([q])
        entry = list(clusters.values())[0]
        assert hasattr(entry.representative, "num_states")
        assert hasattr(entry.representative, "num_edges")


# ---------------------------------------------------------------------------
# Test: process_wir_batch() Python orchestrator
# ---------------------------------------------------------------------------

class TestProcessWirBatch:
    """Tests for the Python batch orchestrator."""

    def test_single_variant(self):
        """process_wir_batch with a single WIR should return 1 cluster."""
        from src.pipeline import process_wir_batch

        result = process_wir_batch([json.dumps(LINEAR_WIR)])

        assert "quotients" in result
        assert "diagnostics" in result
        assert "clusters" in result
        assert len(result["quotients"]) == 1
        assert len(result["diagnostics"]) == 1
        assert len(result["clusters"]) == 1

    def test_isomorphic_variants_single_cluster(self):
        """Two isomorphic WIRs should produce a single cluster."""
        from src.pipeline import process_wir_batch

        result = process_wir_batch([
            json.dumps(LINEAR_WIR),
            json.dumps(LINEAR_WIR_VARIANT),
        ])

        assert len(result["clusters"]) == 1
        cluster = list(result["clusters"].values())[0]
        assert sorted(cluster["indices"]) == [0, 1]

    def test_mixed_variants(self):
        """Two isomorphic + one different → 2 clusters."""
        from src.pipeline import process_wir_batch

        result = process_wir_batch([
            json.dumps(LINEAR_WIR),
            json.dumps(LINEAR_WIR_VARIANT),
            json.dumps(BRANCHING_WIR),
        ])

        assert len(result["clusters"]) == 2
        assert len(result["quotients"]) == 3
        assert len(result["diagnostics"]) == 3

    def test_diagnostics_populated(self):
        """Each variant should produce a populated LifterDiagnostics."""
        from src.pipeline import process_wir_batch

        result = process_wir_batch([json.dumps(LINEAR_WIR)])
        diag = result["diagnostics"][0]
        assert diag.total_states > 0
        assert diag.total_edges > 0

    def test_bpmn_tasks_passed_to_lifter(self):
        """bpmn_tasks should be forwarded to the underlying AdvancedLifter."""
        from src.pipeline import process_wir_batch

        result = process_wir_batch(
            [json.dumps(LINEAR_WIR)],
            bpmn_tasks=["Approve Loan"],
        )

        # The lifter should have matched the code action
        diag = result["diagnostics"][0]
        # At minimum, the graph should be built successfully
        assert diag.total_states > 0

    def test_cluster_representative_is_twa_graph(self):
        """Each cluster's representative should be a valid TwaGraph."""
        from src.pipeline import process_wir_batch

        result = process_wir_batch([
            json.dumps(LINEAR_WIR),
            json.dumps(LINEAR_WIR_VARIANT),
        ])

        for cluster in result["clusters"].values():
            rep = cluster["representative"]
            assert hasattr(rep, "num_states")
            assert rep.num_states() > 0

    def test_default_ltl_property_path_still_populates_compliance(self):
        """The pre-ingestion single-string path is unaffected by property_suite."""
        from src.pipeline import process_wir_batch

        result = process_wir_batch([json.dumps(LINEAR_WIR)])
        cluster = list(result["clusters"].values())[0]
        assert "compliance" in cluster
        assert "compliance_results" not in cluster
        assert cluster["compliance"]["verdict"] in ("COMPLIANT", "VIOLATION", "INCONCLUSIVE")

    def test_property_suite_populates_compliance_results_per_property(self):
        """A real PropertySuite checks every conformance property per cluster,
        under compliance_results (a list), not the legacy compliance dict."""
        from src.pipeline import process_wir_batch
        from src.property_ingest import load_property_suite

        payload = {
            "ltlf_property_suite": {
                "P1_Structural_Control_Flow": [
                    '!start(approve_loan) W done(approve_loan)',
                    '!start(reject_loan) W done(approve_loan)',
                ],
                "P0_Critical_Sentinels": [], "P2_Quality_Limits": [],
                "P3_Adversarial_Defenses": [], "synthesized_mutant_killers": [],
            },
            "tier_semantics": {
                "P0_Critical_Sentinels": {"conformance_check": False},
                "P1_Structural_Control_Flow": {"conformance_check": True},
                "P2_Quality_Limits": {"conformance_check": True},
                "P3_Adversarial_Defenses": {"conformance_check": False},
                "synthesized_mutant_killers": {"conformance_check": False},
            },
        }
        suite = load_property_suite(payload)
        assert len(suite.conformance_properties()) == 2

        result = process_wir_batch(
            [json.dumps(LINEAR_WIR)],
            bpmn_tasks=["approve_loan", "reject_loan"],
            property_suite=suite,
        )
        cluster = list(result["clusters"].values())[0]
        assert "compliance_results" in cluster
        assert "compliance" not in cluster
        results = cluster["compliance_results"]
        assert len(results) == 2
        for r in results:
            assert r["verdict"] in ("COMPLIANT", "VIOLATION", "INCONCLUSIVE", "ERROR")
            assert r["tier"] == "P1_Structural_Control_Flow"
            assert r["ltl_property"].startswith('!"')  # Option-B quoted atom, not start(...)


# ---------------------------------------------------------------------------
# Test: Shared bdd_dict invariant
# ---------------------------------------------------------------------------

class TestBddDictInvariant:
    """Verify that the single-lifter constraint is enforced."""

    def test_single_lifter_shared_dict(self):
        """All quotients from one lifter instance share the same bdd_dict.
        This is implicitly tested by cluster_implementations succeeding
        (it would crash or give wrong results with mismatched dicts).
        """
        lifter = vibecheck_lifter.AdvancedLifter()
        q1 = _build_and_minimize(lifter, LINEAR_WIR)
        q2 = _build_and_minimize(lifter, BRANCHING_WIR)

        # If dicts didn't match, are_isomorphic would fail or give wrong results
        # The fact that clustering completes without error confirms the invariant
        clusters = vibecheck_lifter.cluster_implementations([q1, q2])
        assert len(clusters) >= 1

    def test_self_isomorphism(self):
        """A graph should be isomorphic to itself (sanity check)."""
        lifter = vibecheck_lifter.AdvancedLifter()
        q = _build_and_minimize(lifter, LINEAR_WIR)

        clusters = vibecheck_lifter.cluster_implementations([q, q])
        assert len(clusters) == 1
        assert sorted(list(clusters.values())[0].indices) == [0, 1]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
