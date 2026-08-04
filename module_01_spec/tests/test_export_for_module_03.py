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
                "P1_Structural_Control_Flow": ["!start(Reject) W done(Approve)"],
                "P2_Quality_Limits": ["G(iteration_count <= 10 -> F(process_complete))"],
            }
        },
    }


def _pipeline_result_with_all_five_tiers():
    """mutation_refiner.py's _certify() always emits all 5 tiers (P3 and
    synthesized_mutant_killers included, even if empty) -- this is the shape
    real Module 01 runs actually produce, not the 3-tier minimal fixture
    above.

    The synthesized_mutant_killers entry deliberately repeats the P1 formula
    verbatim, in mutation_refiner.py's own "!v W u" shape -- that's what
    mutation_refiner.py actually does (every killer it synthesizes is
    appended to both P1_Structural_Control_Flow and synthesized_mutant_killers
    at synthesis time, see mutation_refiner.py's refinement loop), so the
    fixture exercises that real invariant rather than a formula that never
    collides with anything. P3's formula uses adversarial_generator.py's own
    "G(a -> !F(b))" shape."""
    result = _minimal_pipeline_result()
    result["phase_3"]["refined_ltlf_property_suite"]["P3_Adversarial_Defenses"] = [
        "G(start(Approve) -> F(done(Approve)))"
    ]
    result["phase_3"]["refined_ltlf_property_suite"]["synthesized_mutant_killers"] = [
        "!start(Reject) W done(Approve)"
    ]
    return result


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

        # Regression: tier_semantics previously covered only 3 of the 5 tiers
        # refined_ltlf_property_suite can contain, so a suite with any real
        # P3/synthesized_mutant_killers property made Module 03's
        # load_property_suite hard-error (see test_real_export_is_ingestible_by_module_03).
        # Both tiers now flag as conformance-checkable in tier_semantics. In
        # practice property_ingest still excludes every property either
        # produces today -- P3 because its "G(a -> !F(b))" shape trips
        # property_ingest's SPOT-grammar filter, synthesized_mutant_killers
        # because mutation_refiner.py always duplicates its formulas into
        # P1_Structural_Control_Flow first -- see
        # test_real_export_is_ingestible_by_module_03 for the exact reasons.
        # The flag flip is still correct to keep: it's what makes those
        # exclusions legible (reported with a reason) instead of a blanket,
        # unexplained tier ban.
        assert tiers["P3_Adversarial_Defenses"]["conformance_check"] is True
        assert tiers["synthesized_mutant_killers"]["conformance_check"] is True


def test_real_export_is_ingestible_by_module_03():
    """Regression: feed export_for_module_03's actual output (all 5 tiers
    populated, as mutation_refiner.py's _certify() really produces) straight
    into property_ingest.load_property_suite() -- this used to raise
    ValueError("tier 'P3_Adversarial_Defenses' has properties but no entry
    in tier_semantics") because tier_semantics only ever covered 3 tiers.

    P3_Adversarial_Defenses and synthesized_mutant_killers now have
    conformance_check=True in tier_semantics. synthesized_mutant_killers'
    formula here is a byte-for-byte duplicate of the P1_Structural_Control_Flow
    formula (the real relationship mutation_refiner.py produces), so it must
    be excluded as a cross-tier duplicate -- checking the identical formula
    twice under two tier names would double-count one violation as two, not
    add new detection power.

    P3_Adversarial_Defenses's own formula ends up excluded too, but for an
    unrelated, pre-existing reason worth naming explicitly rather than
    asserting blind: adversarial_generator.py's killer template is
    "G(a -> !F(b))", and property_ingest's _rejects_spot_grammar flags any
    bare "->" as a disallowed comparison operator (its regex matches the
    literal ">" inside "->", not just standalone "<"/">"/"<="/">=" numeric
    comparisons). So turning P3's tier flag on does not yet make it
    checkable in practice -- every formula the current P3 synthesis
    produces uses "->" and is filtered out downstream of the flag, before
    it reaches SPOT. Fixing the grammar-rejection regex to stop matching
    "->" is a separate, pre-existing bug -- out of scope here, but worth
    flagging: enabling P3.conformance_check today adds no real detection
    power until that filter is fixed too."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "module_03_equiv", "src"))
    from property_ingest import load_property_suite

    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "module_03_input.json")
        export_for_module_03(_pipeline_result_with_all_five_tiers(), filepath=filepath)

        with open(filepath) as f:
            payload = json.load(f)

        suite = load_property_suite(payload)  # must not raise
        checkable_tiers = {p.tier for p in suite.conformance_properties()}
        assert "P1_Structural_Control_Flow" in checkable_tiers
        assert "P3_Adversarial_Defenses" not in checkable_tiers
        assert "synthesized_mutant_killers" not in checkable_tiers

        excluded_reasons = {e.tier: e.reason for e in suite.excluded_properties()}
        assert "comparison operator" in excluded_reasons["P3_Adversarial_Defenses"]
        assert "duplicate" in excluded_reasons["synthesized_mutant_killers"]


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
    test_real_export_is_ingestible_by_module_03()
    test_ltlf_property_suite_unchanged_by_the_new_field()
    test_loop_bound_defaults_to_zero_when_undocumented()
    print("All tests passed.")
