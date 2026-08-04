"""
tests/test_pbcts_convergence.py
=================================
Next Steps.md item #8: PBCTS convergence (bidirectional_alignment.py's
run_idcd -- Iterative Deepening with Convergence Detection, IDCD) and SCSL
(Self-Correcting Specification Loop, _compute_corrections) had zero tests.
A converging and a non-converging fixture, plus SCSL correction synthesis
on a genuine semantic gap.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from bidirectional_alignment import PBCTSAlignmentPipeline

_GRAPH = {
    "initial_state": "Start_1",
    "start_states": ["Start_1"],
    "states": [
        {"node_id": "Start_1", "node_type": "startEvent", "atomic_propositions": ["node(Start)"]},
        {"node_id": "Task_A", "node_type": "task", "atomic_propositions": ["start(Approve)", "done(Approve)"]},
        {"node_id": "End_1", "node_type": "endEvent", "atomic_propositions": ["node(End)"]},
    ],
    "edges": [
        {"source_id": "Start_1", "target_id": "Task_A"},
        {"source_id": "Task_A", "target_id": "End_1"},
    ],
}


class TestIDCDConvergence:
    """run_idcd's own convergence detection: `abs(eas_k - eas_prev) <
    epsilon and k > 1`."""

    def test_small_graph_converges_within_k_max(self):
        """A small, loop-free graph's model traces saturate almost
        immediately (bounded DFS caps at min(k, num_nodes)), so EAS
        stabilizes by k=2 well within the default k_max=20."""
        suite = {"P1_Structural_Control_Flow": ["start(Approve) & X(done(Approve))"]}
        pipeline = PBCTSAlignmentPipeline(suite, _GRAPH)
        frc = pipeline.run_idcd(k_max=20, epsilon=0.001)

        assert frc["convergence"]["converged"] is True
        assert frc["convergence"]["k_converged"] <= 20
        assert frc["reliability"]["confidence"] == 0.999  # 1.0 - epsilon
        assert "fully enumerated" in frc["reliability"]["completeness_statement"]

    def test_k_max_of_one_cannot_converge_by_construction(self):
        """Checked, not assumed: the convergence check itself requires
        `k > 1` (there is no eas_prev to compare against at k=1), so
        k_max=1 deterministically produces converged=False regardless of
        the graph/suite -- the cleanest way to pin the non-convergence
        path without needing a suite that happens to oscillate forever."""
        suite = {"P1_Structural_Control_Flow": ["start(Approve) & X(done(Approve))"]}
        pipeline = PBCTSAlignmentPipeline(suite, _GRAPH)
        frc = pipeline.run_idcd(k_max=1, epsilon=0.001)

        assert frc["convergence"]["converged"] is False
        assert frc["convergence"]["k_converged"] == 1
        assert len(frc["convergence"]["eas_history"]) == 1
        # Non-converged confidence falls back to SCov, not (1 - epsilon).
        assert frc["reliability"]["confidence"] == frc["specification_coverage"]["SCov"]
        assert "capped" in frc["reliability"]["completeness_statement"]


class TestSCSLCorrections:
    """_compute_corrections: synthesizes corrective LTLf formulas from
    over-specification gaps (LTLf permits a trace the BPMN graph can't
    produce)."""

    def test_multi_step_gap_produces_a_correction(self):
        """The suite's own formula allows start(Approve) immediately
        followed by node(End), which never happens in the graph.
        SCSL should forbid this invalid transition."""
        suite = {"P1_Structural_Control_Flow": ["start(Approve) & X(node(End))"]}
        pipeline = PBCTSAlignmentPipeline(suite, _GRAPH)
        frc = pipeline.run_idcd(k_max=20, epsilon=0.001)
    
        assert "!F(start(Approve) & X(node(End)))" in frc["scsl_corrections"]
        gap_types = {g["type"] for g in frc["differential_analysis"]["semantic_gaps"]}
        assert "over_specification" in gap_types

    def test_single_step_only_gaps_produce_no_correction(self):
        """_compute_corrections only looks at *consecutive* pairs of
        non-empty steps within a trace -- a formula whose only spec-only
        traces are a single step long has no adjacent pair to correct
        from, so scsl_corrections must be empty rather than erroring."""
        suite = {"P1_Structural_Control_Flow": ["F(start(Approve))"]}
        pipeline = PBCTSAlignmentPipeline(suite, _GRAPH)
        frc = pipeline.run_idcd(k_max=20, epsilon=0.001)

        assert frc["scsl_corrections"] == []
