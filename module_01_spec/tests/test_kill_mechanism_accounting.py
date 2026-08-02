"""
tests/test_kill_mechanism_accounting.py
=======================================
FlowBench evaluation defect #2: LTLfAuditor.is_killed() returned True whenever
a mutant had no complete trace ("if not traces: return True"), without
consulting a single property. Two very different events were therefore scored
identically:

  (a) a property rejected the mutant   -- evidence the suite is strong;
  (b) the mutation disconnected the graph -- detected by the trace generator,
      which an EMPTY property suite would detect just as reliably.

Because BPMNMutationEngine only produces sequence_flow_deletion mutants
(measured: 2960/2960 across FLOW-BENCH), (b) dominated, and Phase 3's
mutants_killed_ratio read exactly 1.0 on all 148 diagrams. The gate was
passing on no property evidence whatsoever, and nothing in the output made
that visible.

DECISION RECORDED: mutants_killed_ratio and the PASS gate are deliberately
left unchanged. Requiring property kills to pass would fail 81/148 diagrams
(measured post-fix), which is a scoring-policy change, not a defect fix, and
execute_validation_pipeline is HIGH risk by impact analysis (15 impacted, 3
direct callers reaching demo/ and eval_e2e/). Instead the mechanism is made
visible and the vacuous case is flagged explicitly, so a caller can no longer
read 1.0 and conclude the suite was tested.

These tests use real mutants of a real graph rather than hand-built dicts:
the whole point of the defect is what the two mechanisms do on actual
BPMN-derived structures.
"""

import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from mutation_refiner import LTLfAuditor


def _linear_graph():
    """Start -> A -> End, with node propositions in the form semantic_extractor
    emits, so the auditor is exercised on realistic proposition shapes."""
    return {
        "initial_state": "Start_1",
        "start_states": ["Start_1"],
        "states": [
            {"node_id": "Start_1", "node_type": "startEvent", "atomic_propositions": ["node(Start)"]},
            {"node_id": "Task_A", "node_type": "task", "atomic_propositions": ["start(A)", "done(A)"]},
            {"node_id": "End_1", "node_type": "endEvent", "atomic_propositions": ["node(End)"]},
        ],
        "edges": [
            {"flow_id": "F1", "source_id": "Start_1", "target_id": "Task_A"},
            {"flow_id": "F2", "source_id": "Task_A", "target_id": "End_1"},
        ],
    }


def test_disconnection_kill_is_labelled_as_such():
    """A mutant whose graph has been severed must report the disconnection
    mechanism, not be silently indistinguishable from a property kill. This
    is the exact case that inflated mutants_killed_ratio to 1.0."""
    mutant = _linear_graph()
    mutant["edges"] = [e for e in mutant["edges"] if e["flow_id"] != "F2"]

    # A NON-EMPTY suite, to prove the mechanism is reported by cause rather
    # than by the suite happening to be empty.
    auditor = LTLfAuditor({"P0_Critical_Sentinels": ["!done(A) W start(A)"]})
    killed, mechanism, _detail = auditor.classify_kill(mutant)

    assert killed is True
    assert mechanism == LTLfAuditor.KILL_BY_DISCONNECTION


def test_disconnection_is_detected_even_by_an_empty_suite():
    """The reason a disconnection kill is not evidence of suite strength,
    asserted directly: with zero properties the mutant is still 'killed'."""
    mutant = _linear_graph()
    mutant["edges"] = [e for e in mutant["edges"] if e["flow_id"] != "F2"]

    killed, mechanism, _ = LTLfAuditor({}).classify_kill(mutant)

    assert killed is True
    assert mechanism == LTLfAuditor.KILL_BY_DISCONNECTION


def test_property_kill_is_labelled_as_such():
    """The mechanism that actually measures suite strength must be
    distinguishable. A connected graph failing a property must report
    KILL_BY_PROPERTY."""
    connected = _linear_graph()
    # A property the connected graph genuinely violates: End is reached.
    auditor = LTLfAuditor({"P1_Structural_Control_Flow": ["G(!node(End))"]})
    killed, mechanism, detail = auditor.classify_kill(connected)

    assert killed is True
    assert mechanism == LTLfAuditor.KILL_BY_PROPERTY
    assert "Property" in detail


def test_surviving_mutant_reports_no_mechanism():
    """A connected mutant that satisfies every property must not be counted
    under either mechanism."""
    killed, mechanism, _ = LTLfAuditor({}).classify_kill(_linear_graph())

    assert killed is False
    assert mechanism is LTLfAuditor.NOT_KILLED


def test_certificate_flags_a_vacuous_kill_ratio():
    """The headline defect, pinned end-to-end: a Phase 3 certificate reporting
    mutants_killed_ratio 1.0 with zero property kills must say so, so a
    downstream reader cannot mistake it for a validated suite. Measured
    corpus-wide, 81/148 FLOW-BENCH diagrams are in exactly this state."""
    import glob

    from api import run_module_01_pipeline

    repo_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
    corpus = os.path.join(repo_root, "flow-bench", "data", "output")
    assert glob.glob(os.path.join(corpus, "*.bpmn")), "FLOW-BENCH corpus missing"

    # Named exemplars rather than a slice of the corpus: uid_1 and uid_22 are
    # measured all-disconnection diagrams (20/20 kills by disconnection, 0 by
    # property), so this test fails loudly if the flag stops firing rather than
    # depending on how many diagrams happen to be scanned. The corpus-wide
    # figure (81/148 vacuous) is recorded in the PR, not re-measured per run.
    paths = [os.path.join(corpus, name) for name in ("uid_1_output.bpmn", "uid_22_output.bpmn")]
    vacuous_seen = False
    for path in paths:
        with open(path) as f:
            cert = run_module_01_pipeline(f.read())["phase_3"]["phase_3_certificate"]

        # The decomposition must always add up to the headline count.
        assert (
            cert["mutants_killed_by_property"] + cert["mutants_killed_by_disconnection"]
            == round(cert["mutants_killed_ratio"] * cert["mutants_generated"])
        )
        # And the vacuity flag must be exactly the condition it claims to be.
        assert cert["kill_evidence_vacuous"] == (
            cert["mutants_killed_ratio"] >= 1.0 and cert["mutants_killed_by_property"] == 0
        )
        vacuous_seen = vacuous_seen or cert["kill_evidence_vacuous"]

    assert vacuous_seen, (
        "expected at least one diagram passing Phase 3 on zero property kills; "
        "if this now fails, the suite genuinely improved and the flag needs re-baselining"
    )


def test_is_killed_contract_is_unchanged_for_existing_callers():
    """is_killed() is on a HIGH-risk path (execute_validation_pipeline: 15
    impacted symbols, 3 direct callers reaching demo/ and eval_e2e/), so its
    two-tuple shape must survive this change untouched."""
    mutant = _linear_graph()
    mutant["edges"] = [e for e in mutant["edges"] if e["flow_id"] != "F2"]

    result = LTLfAuditor({}).is_killed(mutant)

    assert isinstance(result, tuple) and len(result) == 2
    killed, detail = result
    assert killed is True
    assert "disconnected" in detail
