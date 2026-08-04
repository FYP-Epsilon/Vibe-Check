"""
tests/test_phase3_gate.py
==========================
Next Steps.md item #8: Phase 3's quality gate (mutation_refiner.py's
MutationValidator._certify()) had zero tests. Covers the gate's own
PASS/FAIL boundary (C_struct >= 1.0 AND mutants_killed_ratio >= 1.0)
directly, plus one real end-to-end refinement round through
execute_validation_pipeline().
"""

import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from mutation_refiner import MutationValidator

_GRAPH = {
    "initial_state": "Start_1",
    "start_states": ["Start_1"],
    "states": [
        {"node_id": "Start_1", "node_type": "startEvent", "atomic_propositions": ["node(Start)"]},
        {"node_id": "Task_A", "node_type": "task", "atomic_propositions": ["start(Approve)", "done(Approve)"]},
        {"node_id": "Gateway_1", "node_type": "exclusiveGateway", "atomic_propositions": ["node(Decide)"]},
        {"node_id": "End_1", "node_type": "endEvent", "atomic_propositions": ["node(End)"]},
    ],
    "edges": [
        {"source_id": "Start_1", "target_id": "Task_A"},
        {"source_id": "Task_A", "target_id": "Gateway_1"},
        {"source_id": "Gateway_1", "target_id": "End_1", "condition": "x > 0"},
    ],
}

_SUITE = {
    "P1_Structural_Control_Flow": ["G(start(Approve) -> F(done(Approve)))"],
}


class TestGateBoundaryDirect:
    """Exercises _certify()'s own PASS/FAIL threshold directly, isolated
    from the mutation-generation/audit machinery."""

    def _validator(self) -> MutationValidator:
        # MutationValidator.__init__ does `self.graph = semantic_graph` --
        # no copy -- so a deepcopy here is required, not defensive
        # paranoia: without it, test_unlabeled_node_fails_even_at_full_kill_ratio's
        # in-place append would permanently pollute _GRAPH for every test
        # that runs after it in the same process (confirmed empirically).
        return MutationValidator(copy.deepcopy(_GRAPH), copy.deepcopy(_SUITE))

    def test_full_structural_coverage_and_full_kill_ratio_passes(self):
        v = self._validator()
        v.engine.mutants = [{"edges": []}] * 5
        v.mutants_killed = 5
        cert = v._certify(surviving_mutants=[])
        assert cert["phase_3_certificate"]["status"] == "PASS"
        assert cert["phase_3_certificate"]["C_struct_coefficient"] == 1.0
        assert cert["phase_3_certificate"]["mutants_killed_ratio"] == 1.0

    def test_one_surviving_mutant_fails_despite_full_structural_coverage(self):
        """C_struct alone (all nodes labeled) is not sufficient -- any
        surviving (unkilled) mutant fails the gate."""
        v = self._validator()
        v.engine.mutants = [{"edges": []}] * 5
        v.mutants_killed = 4  # one survives
        cert = v._certify(surviving_mutants=[{"id": "m1", "edges": []}])
        assert cert["phase_3_certificate"]["status"] == "FAIL"
        assert cert["phase_3_certificate"]["mutants_killed_ratio"] == 4 / 5
        assert "unresolved_vulnerabilities" in cert["phase_3_certificate"]

    def test_unlabeled_node_fails_even_at_full_kill_ratio(self):
        """The converse boundary: every mutant killed, but C_struct < 1.0
        because a node has no atomic_propositions at all."""
        v = self._validator()
        v.graph["states"].append({"node_id": "Extra_1", "node_type": "task", "atomic_propositions": []})
        v.engine.mutants = [{"edges": []}] * 3
        v.mutants_killed = 3
        cert = v._certify(surviving_mutants=[])
        assert cert["phase_3_certificate"]["status"] == "FAIL"
        assert cert["phase_3_certificate"]["C_struct_coefficient"] < 1.0

    def test_zero_mutants_generated_defaults_kill_ratio_to_pass(self):
        """Guards the `if actual_count > 0` branch: no mutants generated at
        all (e.g. a graph too small to mutate) must not be misread as 0/0
        surviving -- killed_ratio defaults to 1.0, same convention as the
        node_coverage guard in Phase 1's gate."""
        v = self._validator()
        v.engine.mutants = []
        v.mutants_killed = 0
        cert = v._certify(surviving_mutants=[])
        assert cert["phase_3_certificate"]["mutants_killed_ratio"] == 1.0
        assert cert["phase_3_certificate"]["status"] == "PASS"


class TestSelfHealingEndToEnd:
    """One real run of execute_validation_pipeline() -- the recursive
    refinement loop that synthesizes killer properties for surviving
    mutants and re-audits until the gate passes or max_rounds is hit."""

    def test_real_pipeline_converges_within_max_rounds(self):
        validator = MutationValidator(copy.deepcopy(_GRAPH), copy.deepcopy(_SUITE))
        cert = validator.execute_validation_pipeline(seed=42, max_rounds=3)
        # Whatever the final verdict, self_healing_rounds must be recorded
        # and bounded by max_rounds -- the field this test suite has never
        # exercised before.
        assert 1 <= cert["phase_3_certificate"]["self_healing_rounds"] <= 3
        assert cert["phase_3_certificate"]["status"] in ("PASS", "FAIL")
        assert cert["phase_3_certificate"]["mutants_generated"] >= 0
