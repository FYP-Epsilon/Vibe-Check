"""
tests/test_property_ingest.py
==============================
Pure-Python tests for property_ingest.py -- no SPOT/C++ toolchain required.
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import pytest

from property_ingest import load_property_suite, Property, ExcludedProperty


TIER_SEMANTICS = {
    "P0_Critical_Sentinels": {"conformance_check": False},
    "P1_Structural_Control_Flow": {"conformance_check": True},
    "P2_Quality_Limits": {"conformance_check": True},
    "P3_Adversarial_Defenses": {"conformance_check": False},
    "P4_Task_Coverage": {"conformance_check": True},
    "synthesized_mutant_killers": {"conformance_check": False},
}


def make_payload(**suite_overrides):
    suite = {
        "P0_Critical_Sentinels": ["!done(Approve) W start(Approve)"],
        "P1_Structural_Control_Flow": [
            "!start(B) W done(A)",
            "!start(Decision) W node(Start)",
        ],
        "P2_Quality_Limits": ["G(iteration_count <= 10 -> F(process_complete))"],
        "P3_Adversarial_Defenses": ["!start(A) & X(done(A))"],
        "P4_Task_Coverage": [],
        "synthesized_mutant_killers": [],
    }
    suite.update(suite_overrides)
    return {
        "ltlf_property_suite": suite,
        "tier_semantics": TIER_SEMANTICS,
    }


class TestTierGating:
    def test_p0_excluded_as_lifting_self_test(self):
        result = load_property_suite(make_payload())
        checkable_tiers = {p.tier for p in result.conformance_properties()}
        assert "P0_Critical_Sentinels" not in checkable_tiers
        excluded_p0 = [e for e in result.excluded_properties() if e.tier == "P0_Critical_Sentinels"]
        assert len(excluded_p0) == 1
        assert "conformance_check is False" in excluded_p0[0].reason

    def test_p1_node_free_is_checkable(self):
        result = load_property_suite(make_payload())
        checkable = result.conformance_properties()
        assert len(checkable) == 1
        assert checkable[0].tier == "P1_Structural_Control_Flow"
        assert checkable[0].origin_formula == "!start(B) W done(A)"

    def test_p1_node_bearing_excluded(self):
        result = load_property_suite(make_payload())
        excluded_p1 = [e for e in result.excluded_properties() if e.tier == "P1_Structural_Control_Flow"]
        assert len(excluded_p1) == 1
        assert "node(" in excluded_p1[0].reason

    def test_p2_excluded_for_unparseable_comparison(self):
        result = load_property_suite(make_payload())
        excluded_p2 = [e for e in result.excluded_properties() if e.tier == "P2_Quality_Limits"]
        assert len(excluded_p2) == 1
        assert "comparison operator" in excluded_p2[0].reason
        assert not any(p.tier == "P2_Quality_Limits" for p in result.conformance_properties())

    def test_p3_excluded_not_conformance_check(self):
        result = load_property_suite(make_payload())
        excluded_p3 = [e for e in result.excluded_properties() if e.tier == "P3_Adversarial_Defenses"]
        assert len(excluded_p3) == 1
        assert not any(p.tier == "P3_Adversarial_Defenses" for p in result.conformance_properties())

    def test_empty_tier_produces_nothing(self):
        result = load_property_suite(make_payload())
        assert not any(p.tier == "synthesized_mutant_killers" for p in result.conformance_properties())
        assert not any(e.tier == "synthesized_mutant_killers" for e in result.excluded_properties())


class TestP4TaskCoverage:
    """P4_Task_Coverage carries two shapes from ltlf_synthesizer.py's
    _generate_sentinels: an unconditional F(done(X)) for tasks on every
    start->end path, and a conditional G(start(X) -> F(done(X))) for
    tasks that are not. Only the first is checkable -- the second collapses
    to an unfalsifiable tautology under Option B's start/done atom merge
    (verified with evaluate_ltlf: G("X" -> F("X")) is true on every trace),
    the same failure mode ap_gap_memo.md documented for P0's excluded
    sentinels. Ingestion must keep these two shapes distinguishable rather
    than either checking both (silently vacuous) or excluding both (losing
    the genuine omission check the unconditional shape provides).
    """

    def test_unconditional_form_is_checkable(self):
        result = load_property_suite(make_payload(
            P4_Task_Coverage=["F(done(Approve))"],
        ))
        checkable = [p for p in result.conformance_properties() if p.tier == "P4_Task_Coverage"]
        assert len(checkable) == 1
        assert checkable[0].formula == 'F("Approve")'

    def test_conditional_form_excluded_as_vacuous(self):
        result = load_property_suite(make_payload(
            P4_Task_Coverage=["G(start(Reject) -> F(done(Reject)))"],
        ))
        assert not any(p.tier == "P4_Task_Coverage" for p in result.conformance_properties())
        excluded_p4 = [e for e in result.excluded_properties() if e.tier == "P4_Task_Coverage"]
        assert len(excluded_p4) == 1
        assert "tautology" in excluded_p4[0].reason

    def test_both_forms_together_only_unconditional_checked(self):
        result = load_property_suite(make_payload(
            P4_Task_Coverage=[
                "F(done(Approve))",
                "G(start(Reject) -> F(done(Reject)))",
            ],
        ))
        checkable = [p for p in result.conformance_properties() if p.tier == "P4_Task_Coverage"]
        excluded_p4 = [e for e in result.excluded_properties() if e.tier == "P4_Task_Coverage"]
        assert len(checkable) == 1 and checkable[0].origin_formula == "F(done(Approve))"
        assert len(excluded_p4) == 1 and excluded_p4[0].origin_formula == "G(start(Reject) -> F(done(Reject)))"


class TestNormalization:
    def test_lifecycle_atoms_collapsed_and_quoted(self):
        result = load_property_suite(make_payload())
        prop = result.conformance_properties()[0]
        assert prop.formula == '!"B" W "A"'

    def test_reserved_letter_atom_is_quoted_not_bare(self):
        payload = make_payload(P1_Structural_Control_Flow=[
            "!start(GitHub_thing) W done(Foo)",
        ])
        result = load_property_suite(payload)
        prop = result.conformance_properties()[0]
        # Must be quoted -- an unquoted "GitHub_thing" would be misparsed by
        # SPOT's infix parser as the G operator applied to "itHub_thing".
        assert '"GitHub_thing"' in prop.formula
        assert prop.formula == '!"GitHub_thing" W "Foo"'

    def test_double_ampersand_and_pipe_normalized(self):
        payload = make_payload(P1_Structural_Control_Flow=[
            "start(A) && !start(B) || done(C)",
        ])
        result = load_property_suite(payload)
        prop = result.conformance_properties()[0]
        assert "&&" not in prop.formula
        assert "||" not in prop.formula
        assert prop.formula == '"A" & !"B" | "C"'

    def test_origin_formula_preserved_verbatim(self):
        result = load_property_suite(make_payload())
        prop = result.conformance_properties()[0]
        assert prop.origin_formula == "!start(B) W done(A)"


class TestDeduplication:
    def test_exact_intra_tier_duplicates_collapse_to_one(self):
        payload = make_payload(P1_Structural_Control_Flow=[
            "!start(B) W done(A)",
            "!start(B) W done(A)",
            "!start(B) W done(A)",
        ])
        result = load_property_suite(payload)
        assert len(result.conformance_properties()) == 1

    def test_duplicates_across_tiers_are_not_collapsed(self):
        payload = make_payload(
            P1_Structural_Control_Flow=["!start(B) W done(A)"],
            P3_Adversarial_Defenses=["!start(B) W done(A)"],
        )
        result = load_property_suite(payload)
        # P1 copy is checkable, P3 copy is excluded -- both counted, not merged
        assert len(result.conformance_properties()) == 1
        assert any(e.origin_formula == "!start(B) W done(A)" for e in result.excluded_properties())


class TestValidation:
    def test_missing_ltlf_property_suite_raises(self):
        with pytest.raises(ValueError, match="ltlf_property_suite"):
            load_property_suite({"tier_semantics": TIER_SEMANTICS})

    def test_missing_tier_semantics_raises(self):
        with pytest.raises(ValueError, match="tier_semantics"):
            load_property_suite({"ltlf_property_suite": {}})

    def test_unrecognized_tier_raises(self):
        payload = {
            "ltlf_property_suite": {"P99_Made_Up": ["G(1)"]},
            "tier_semantics": TIER_SEMANTICS,
        }
        with pytest.raises(ValueError, match="P99_Made_Up"):
            load_property_suite(payload)

    def test_tier_present_but_missing_from_tier_semantics_raises(self):
        payload = {
            "ltlf_property_suite": {"P2_Quality_Limits": ["G(1)"]},
            "tier_semantics": {},
        }
        with pytest.raises(ValueError, match="P2_Quality_Limits"):
            load_property_suite(payload)


class TestLoadFromPath:
    def test_load_from_file_path(self, tmp_path):
        payload = make_payload()
        path = tmp_path / "module_03_input.json"
        path.write_text(json.dumps(payload))
        result = load_property_suite(str(path))
        assert len(result.conformance_properties()) == 1
