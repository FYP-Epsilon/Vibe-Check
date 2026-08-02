"""
tests/test_loop_bound_decoupling.py
===================================
FlowBench evaluation defect #1: the P2 bounded-loop property carried its
numeric bound in-band, as a C-style comment prefixed to the formula
("/* loop_bound=10 */ G(start -> F(done))"). ltlf_eval's TOKEN_SPEC has no
comment syntax, so the module's own evaluator raised on its own synthesised
property and Phase 4 returned FAIL_WITH_ERRORS on 148/148 FLOW-BENCH diagrams.

The trap this file exists to guard: simply deleting the comment makes the
formula parse but silently zeroes export_for_module_03's loop-bound
extraction, which regexed that same comment back out of the formula text.
Nothing in the suite caught that, because the only existing loop-bound test
asserts the *default-absent* case (test_export_for_module_03.py's
test_loop_bound_defaults_to_zero_when_undocumented) and would keep passing
against a permanently-zero extractor.

So both halves are pinned here: the formula must be parseable AND the bound
must still arrive at Module 03 -- neither alone is the fix.
"""

import glob
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from api import export_for_module_03, run_module_01_pipeline
from ltlf_eval import evaluate_ltlf
from ltlf_synthesizer import DEFAULT_LOOP_BOUND, FLTLSynthesizer

_REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")


def _first_corpus_diagram():
    """A real FLOW-BENCH diagram, not a hand-written fixture: the defect was
    measured corpus-wide, so the regression is pinned against the same kind
    of input that exhibited it."""
    matches = sorted(glob.glob(os.path.join(_REPO_ROOT, "flow-bench", "data", "output", "*.bpmn")))
    assert matches, "FLOW-BENCH corpus missing; this test needs a real diagram"
    with open(matches[0]) as f:
        return f.read()


def test_p2_property_is_a_parseable_ltlf_formula():
    """The synthesised P2 property must be accepted by this module's own
    evaluator. A specification engine that emits properties its own checker
    cannot tokenize has no way to self-validate, which is exactly the state
    Phase 4 was in."""
    result = run_module_01_pipeline(_first_corpus_diagram())
    p2 = result["phase_2"]["ltlf_property_suite"]["P2_Quality_Limits"]

    assert p2, "P2_Quality_Limits should not be empty"
    for prop in p2:
        assert not prop.lstrip().startswith("/*"), (
            "loop bound must not be re-encoded in-band in the formula string"
        )
        # Must not raise: a trace of one empty state is enough to exercise
        # tokenize + parse, which is where the defect lived.
        evaluate_ltlf(prop, [set()])


def test_loop_bound_survives_as_structured_metadata():
    """The bound must reach Module 03 without being regexed back out of a
    formula. This is the half of the fix that a naive comment-deletion would
    have broken silently."""
    result = run_module_01_pipeline(_first_corpus_diagram())

    assert result["phase_2"]["spec_metadata"]["loop_bound_documented"] == DEFAULT_LOOP_BOUND

    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "module_03_input.json")
        export_for_module_03(result, filepath=filepath)
        with open(filepath) as f:
            payload = json.load(f)

    assert payload["loop_bound_documented"] == DEFAULT_LOOP_BOUND, (
        "export_for_module_03 must read the structured bound, not parse formula text"
    )


def test_phase_4_no_longer_fails_on_its_own_property_suite():
    """Phase 4 returned FAIL_WITH_ERRORS on every diagram in the corpus
    because it could not parse the properties Phase 2 handed it. Pinning the
    end-to-end consequence, not just the formula shape, so a regression in
    either the tokenizer or the synthesizer is caught here."""
    result = run_module_01_pipeline(_first_corpus_diagram())
    certificate = result["phase_4"]["phase_4_certificate"]

    assert certificate.get("status") != "FAIL_WITH_ERRORS", certificate.get("message")
    assert "certificate_version" in certificate, (
        "Phase 4 should emit a real PBCTS certificate, not an error stub"
    )


def test_synthesizer_publishes_metadata_without_running_full_pipeline():
    """spec_metadata must be part of the synthesizer's own contract, so a
    consumer reading Phase 2 output directly (as api.py now does) is not
    depending on an incidental side effect of the full pipeline."""
    graph = {
        "semantic_graph": {
            "initial_state": "Start_1",
            "start_states": ["Start_1"],
            "states": [
                {"node_id": "Start_1", "node_type": "startEvent", "atomic_propositions": ["node(start_event)"]},
                {"node_id": "End_1", "node_type": "endEvent", "atomic_propositions": ["node(end_event)"]},
            ],
            "edges": [{"flow_id": "F1", "source_id": "Start_1", "target_id": "End_1"}],
        }
    }
    output = FLTLSynthesizer(graph).run_pipeline()

    assert "spec_metadata" in output
    assert output["spec_metadata"]["loop_bound_documented"] == DEFAULT_LOOP_BOUND
