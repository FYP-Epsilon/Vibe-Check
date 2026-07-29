"""
tests/test_export_for_module_03.py
===================================
Regression test for the tier_semantics metadata added to export_for_module_03().

Found by the Module 01 <-> Module 03 bridge investigation: P0 sentinels of the
shape '!done(T) W start(T)' are unfalsifiable under any lifting faithful to task
semantics, so they must never be reported as a conformance verdict against
generated code -- only as a self-test of the Module 03 lifter itself.
export_for_module_03() now encodes that distinction as machine-readable metadata
in module_03_input.json, so a future Module 03 ingestion layer inherits the
correct handling by construction rather than by convention.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from api import export_for_module_03


def _minimal_pipeline_result():
    """A minimal-but-valid pipeline_result shape, bypassing phases 1-4 entirely
    since this test targets only export_for_module_03's own payload assembly."""
    return {
        "status": "PASS",
        "phase_1": {"semantic_graph": {"nodes": [], "edges": []}},
        "phase_3": {
            "refined_ltlf_property_suite": {
                "P0_Critical_Sentinels": ["!done(Approve) W start(Approve)"],
                "P1_Structural_Control_Flow": ["G(start(Approve) -> !start(Reject))"],
                "P2_Quality_Limits": ["G(iteration_count <= 10 -> F(process_complete))"],
            }
        },
    }


def test_export_raises_on_failed_pipeline():
    """export_for_module_03 must refuse to export a failed pipeline's results."""
    try:
        export_for_module_03({"status": "FAIL"})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_tier_semantics_present_and_correct():
    """tier_semantics must mark P0 as a non-conformance lifting self-test, and
    P1/P2 as genuine conformance checks."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "module_03_input.json")
        export_for_module_03(_minimal_pipeline_result(), filepath=filepath)

        with open(filepath) as f:
            payload = json.load(f)

        assert "tier_semantics" in payload
        tiers = payload["tier_semantics"]

        assert tiers["P0_Critical_Sentinels"]["role"] == "lifting_self_test"
        assert tiers["P0_Critical_Sentinels"]["conformance_check"] is False

        assert tiers["P1_Structural_Control_Flow"]["role"] == "conformance_check"
        assert tiers["P1_Structural_Control_Flow"]["conformance_check"] is True

        assert tiers["P2_Quality_Limits"]["role"] == "conformance_check"
        assert tiers["P2_Quality_Limits"]["conformance_check"] is True


def test_ltlf_property_suite_unchanged_by_the_new_field():
    """Adding tier_semantics must not alter the existing property suite payload
    -- this is additive metadata, not a restructuring of the properties list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "module_03_input.json")
        pr = _minimal_pipeline_result()
        export_for_module_03(pr, filepath=filepath)

        with open(filepath) as f:
            payload = json.load(f)

        assert payload["ltlf_property_suite"] == pr["phase_3"]["refined_ltlf_property_suite"]


def test_loop_bound_defaults_to_zero_when_undocumented():
    """Existing behaviour (loop_bound_documented defaults to 0 absent an
    explicit 'loop_bound = N' comment) must be unaffected by this change."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "module_03_input.json")
        export_for_module_03(_minimal_pipeline_result(), filepath=filepath)

        with open(filepath) as f:
            payload = json.load(f)

        assert payload["loop_bound_documented"] == 0


if __name__ == "__main__":
    test_export_raises_on_failed_pipeline()
    test_tier_semantics_present_and_correct()
    test_ltlf_property_suite_unchanged_by_the_new_field()
    test_loop_bound_defaults_to_zero_when_undocumented()
    print("All tests passed.")
