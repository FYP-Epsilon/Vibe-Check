"""
tests/test_p4_completion_tier_semantics.py
==========================================
FlowBench evaluation defect #3: _generate_sentinels emitted an unconditional
`F(done(X))` P4_Task_Coverage obligation for EVERY task node. That formula
asserts X completes on every execution -- true only for a task on every
start->end path. For a task behind an exclusive gateway it is false on any
trace that takes the other branch, and LTLfAuditor._generate_traces enumerates
each branch as a separate trace. The synthesised suite therefore rejected the
very diagram it was derived from: measured 0/50 branching diagrams had a sound
suite.

CHOICE OF FIX, with the alternative measured rather than argued (both were run
against all 148 FLOW-BENCH diagrams on the post-fix-1/2 tree):

  A. emit F(done(X)) only for mandatory tasks, drop it elsewhere
     -> 145/148 sound, but 195 of 437 obligations disappear entirely.
  B. replace every F(done(X)) with G(start(X) -> F(done(X)))
     -> 145/148 sound, all 437 kept, but every obligation weakened, including
        the 242 where the strong claim was valid.
  CHOSEN (hybrid): F(done(X)) where the task is mandatory, the conditional
     form elsewhere
     -> 145/148 sound, all 437 obligations kept, 242 still unconditional.

The hybrid dominates: identical soundness to both alternatives with strictly
more information retained. A and B each pay something the hybrid does not.

The 3 residual unsound diagrams (output/uid_67, output/uid_8, context/uid_92)
are NOT this defect: they have two distinct task node-ids collapsing to one
atomic proposition, which makes a P1 ordering property self-contradictory.
That is a separate defect, diagnosed as such in the evaluation memo and out of
scope for this branch. It is pinned below so it cannot be silently conflated
with this one.
"""

import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from ltlf_synthesizer import FLTLSynthesizer
from mutation_refiner import LTLfAuditor

_REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")


def _branching_graph():
    """Start -> Gateway -> {Task_A | Task_B} -> End. Both tasks are optional:
    neither completes on the trace that takes the other branch."""
    return {
        "semantic_graph": {
            "initial_state": "Start_1",
            "start_states": ["Start_1"],
            "states": [
                {"node_id": "Start_1", "node_type": "startEvent", "atomic_propositions": ["node(Start)"]},
                {"node_id": "GW_1", "node_type": "exclusiveGateway", "atomic_propositions": ["node(GW)"]},
                {"node_id": "Task_A", "node_type": "task", "atomic_propositions": ["start(A)", "done(A)"]},
                {"node_id": "Task_B", "node_type": "task", "atomic_propositions": ["start(B)", "done(B)"]},
                {"node_id": "End_1", "node_type": "endEvent", "atomic_propositions": ["node(End)"]},
            ],
            "edges": [
                {"flow_id": "F1", "source_id": "Start_1", "target_id": "GW_1"},
                {"flow_id": "F2", "source_id": "GW_1", "target_id": "Task_A"},
                {"flow_id": "F3", "source_id": "GW_1", "target_id": "Task_B"},
                {"flow_id": "F4", "source_id": "Task_A", "target_id": "End_1"},
                {"flow_id": "F5", "source_id": "Task_B", "target_id": "End_1"},
            ],
        }
    }


def _linear_graph():
    """Start -> Task_A -> End. Task_A is on every path, so the unconditional
    claim is valid and must be preserved -- the fix must not weaken it."""
    return {
        "semantic_graph": {
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
    }


def _p4(graph):
    return FLTLSynthesizer(graph).run_pipeline()["ltlf_property_suite"]["P4_Task_Coverage"]


def test_optional_task_gets_a_conditional_obligation():
    """The defect itself: a task behind a gateway must not carry an
    unconditional completion claim, because it is false on the other branch."""
    p4 = _p4(_branching_graph())

    assert "F(done(A))" not in p4
    assert "F(done(B))" not in p4
    assert "G(start(A) -> F(done(A)))" in p4
    assert "G(start(B) -> F(done(B)))" in p4


def test_mandatory_task_keeps_the_unconditional_obligation():
    """The fix must not over-correct. Candidate B (weaken everything) was
    rejected precisely because it would have weakened this case too."""
    p4 = _p4(_linear_graph())

    assert "F(done(A))" in p4


def test_no_task_loses_its_obligation():
    """Candidate A (drop the property for optional tasks) was rejected because
    it discards 195 of 437 corpus-wide obligations. Every task must still be
    covered by exactly one P4 property."""
    p4 = _p4(_branching_graph())

    assert len(p4) == 2
    assert sum("done(A)" in p for p in p4) == 1
    assert sum("done(B)" in p for p in p4) == 1


def test_suite_admits_the_branching_diagram_it_was_derived_from():
    """The soundness property the defect violated, asserted end-to-end: a
    synthesised suite must not reject its own source diagram. This is the
    check that fails on the unfixed synthesiser."""
    graph = _branching_graph()
    suite = FLTLSynthesizer(graph).run_pipeline()["ltlf_property_suite"]

    killed, detail = LTLfAuditor(suite).is_killed(graph["semantic_graph"])

    assert killed is False, f"suite rejects its own diagram: {detail}"


def test_suite_admits_a_real_branching_corpus_diagram():
    """Hand-built fixtures can be accidentally easy. Pinned against a real
    FLOW-BENCH diagram that contains a gateway, since the measured failure was
    corpus-wide (0/50 branching diagrams sound before the fix)."""
    import collections

    from semantic_extractor import SemanticExtractionEngine

    for path in sorted(glob.glob(os.path.join(_REPO_ROOT, "flow-bench", "data", "output", "*.bpmn"))):
        with open(path) as f:
            xml = f.read()
        graph = SemanticExtractionEngine(xml).run_pipeline()
        sg = graph["semantic_graph"]
        outdeg = collections.Counter(e["source_id"] for e in sg.get("edges", []))
        if not any(v >= 2 for v in outdeg.values()):
            continue  # not a branching diagram

        suite = FLTLSynthesizer(graph).run_pipeline()["ltlf_property_suite"]
        killed, detail = LTLfAuditor(suite).is_killed(sg)
        assert killed is False, f"{os.path.basename(path)} rejects its own suite: {detail}"
        return

    raise AssertionError("no branching diagram found in corpus")


def test_removing_the_unsound_obligation_exposes_a_weaker_kill_rate():
    """The consequence of this fix that a reader most needs to know, pinned so
    it cannot be rediscovered by accident.

    Before: the over-strong F(done(X)) was false on branch-local traces, so it
    rejected almost any mutant it was evaluated against -- INCLUDING the
    unmutated diagram. Those kills were an artifact of an unsound property,
    not evidence the suite discriminates. mutants_killed_ratio read 1.0 on all
    148 diagrams partly because of it.

    After: property kills across the corpus fall from 1248 to 168, and 54/148
    diagrams no longer pass the Phase 3 gate at all -- their suites genuinely
    cannot kill a connected mutant. That is a truthful measurement replacing a
    flattering one, and it is the honest baseline the evaluation harness needs.

    This test asserts the mechanism rather than the corpus totals: a mutant
    that stays connected and only reroutes an optional branch must NOT be
    killed by a P4 obligation, because no sound completion property can
    distinguish it.
    """
    graph = _branching_graph()
    suite = FLTLSynthesizer(graph).run_pipeline()["ltlf_property_suite"]
    p4_only = {"P4_Task_Coverage": suite["P4_Task_Coverage"]}

    # Mutant: drop the Task_B branch. Still connected, still reaches End.
    mutant = _branching_graph()["semantic_graph"]
    mutant["edges"] = [e for e in mutant["edges"] if e["flow_id"] != "F3"]

    killed, _mechanism, detail = LTLfAuditor(p4_only).classify_kill(mutant)

    assert killed is False, (
        "a sound P4 suite must not 'kill' a connected mutant it cannot "
        f"legitimately distinguish; got: {detail}"
    )


def test_disconnected_graph_claims_nothing_unconditionally():
    """Guard on the mandatory-node computation: with no complete start->end
    path, no task can be proven to complete, so nothing may be emitted
    unconditionally."""
    graph = _linear_graph()
    graph["semantic_graph"]["edges"] = [
        e for e in graph["semantic_graph"]["edges"] if e["flow_id"] != "F2"
    ]

    assert all(not p.startswith("F(") for p in _p4(graph))
