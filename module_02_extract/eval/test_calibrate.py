"""test_calibrate.py -- sanity tests for eval/calibrate.py's statistics.

clopper_pearson is a from-scratch (no scipy) implementation of the exact
binomial confidence interval; these tests check it against known reference
values and basic invariants rather than re-deriving the math.
"""

from __future__ import annotations

import pytest

from eval.calibrate import clopper_pearson, stratified_split, _base_tag, run_differential_verification
from ast_extractor import run_v3_pipeline


class TestClopperPearson:
    def test_known_reference_value(self):
        # x=5, n=10, alpha=0.05 -- standard textbook example, CI ~[0.187, 0.813].
        lo, hi = clopper_pearson(5, 10)
        assert lo == pytest.approx(0.187, abs=0.01)
        assert hi == pytest.approx(0.813, abs=0.01)

    def test_zero_successes(self):
        lo, hi = clopper_pearson(0, 20)
        assert lo == 0.0
        assert hi < 0.3

    def test_all_successes(self):
        lo, hi = clopper_pearson(20, 20)
        assert hi == 1.0
        assert lo > 0.7

    def test_bounds_contain_point_estimate(self):
        lo, hi = clopper_pearson(7, 50)
        assert lo <= 7 / 50 <= hi

    def test_zero_trials(self):
        assert clopper_pearson(0, 0) == (0.0, 1.0)


class TestStratifiedSplit:
    def _manifest(self):
        return [
            {"uid": i, "tags": [str(i), tag]}
            for i, tag in enumerate(["linear"] * 6 + ["conditional"] * 4, start=1)
        ]

    def test_deterministic_for_fixed_seed(self):
        manifest = self._manifest()
        calib1, eval1 = stratified_split(manifest, seed=42)
        calib2, eval2 = stratified_split(manifest, seed=42)
        assert calib1 == calib2
        assert eval1 == eval2

    def test_partitions_every_uid_exactly_once(self):
        manifest = self._manifest()
        calib, eval_set = stratified_split(manifest, seed=1)
        all_uids = {e["uid"] for e in manifest}
        assert calib.isdisjoint(eval_set)
        assert calib | eval_set == all_uids

    def test_base_tag_skips_numeric_tags(self):
        assert _base_tag(["4", "conditional"]) == "conditional"
        assert _base_tag(["9"]) == "unknown"


class TestRunDifferentialVerification:
    def test_returns_well_formed_certificate(self):
        """Mechanical smoke test: differential mode must return the same
        wire-shaped cert as self-mode, not crash."""
        source = "def workflow(x: int) -> int:\n    if x > 0:\n        return 1\n    return 0\n"
        base_wir = run_v3_pipeline(source)["functions"]["workflow"]
        cert = run_differential_verification(source, base_wir)
        assert "combined_confidence" in cert
        assert isinstance(cert["passed"], bool)

    def test_value_only_guard_mutation_not_detected(self):
        """Documents a known, verified limitation (D4 session finding): a
        guard negated to its logical opposite produces IDENTICAL trace
        *shape* (same task/branch-point counts) on both sides, and D3's
        decision-aware comparison can only activate when the real
        actual-side collector also carries a taken_branch field, which it
        does not (see comparator.py). So even against the correct base
        program's WIR as oracle, differential mode cannot currently tell
        this mutant apart from the base. This is a REGRESSION test for a
        documented gap, not a desired behavior -- if collector.py is ever
        enhanced to emit decisions, this test should start failing and
        should be revisited, not "fixed" by weakening it."""
        base_source = "def workflow(status: str) -> int:\n    if status == 'high':\n        return 1\n    return 0\n"
        mutant_source = "def workflow(status: str) -> int:\n    if not (status == 'high'):\n        return 1\n    return 0\n"
        base_wir = run_v3_pipeline(base_source)["functions"]["workflow"]

        base_cert = run_differential_verification(base_source, base_wir)
        mutant_cert = run_differential_verification(mutant_source, base_wir)
        assert base_cert["combined_confidence"] == pytest.approx(mutant_cert["combined_confidence"])

    def test_line_shifted_equivalent_mutant_scores_like_its_base(self):
        """C2 regression test: a semantically equivalent mutant that merely
        shifts every subsequent line (an inserted no-op statement) must
        score within epsilon of the base's own differential score.

        branch_lines are raw source line numbers; deriving them from the
        BASE WIR (as the code did before this fix) points the collector at
        the wrong line in a shifted mutant, producing spurious divergence
        unrelated to any real behavior change -- confirmed empirically
        (C1) on 3 real early-return mutants, 2 of which were false-flagged
        under the old behavior and recovered exactly under the fix."""
        base_source = (
            "def stub_a():\n    return {'v': 1}\n\n\n"
            "def stub_b():\n    return {'v': 2}\n\n\n"
            "def workflow(status: str) -> int:\n"
            "    a = stub_a()\n"
            "    if status == \"high\":\n"
            "        b = stub_b()\n"
            "    return 0\n"
        )
        shifted_source = base_source.replace(
            "    a = stub_a()\n    if status",
            "    a = stub_a()\n    x_pad = 0\n    if status",
        )
        assert shifted_source != base_source

        base_wir = run_v3_pipeline(base_source)["functions"]["workflow"]
        base_cert = run_differential_verification(base_source, base_wir)
        shifted_cert = run_differential_verification(shifted_source, base_wir)
        assert shifted_cert["combined_confidence"] == pytest.approx(
            base_cert["combined_confidence"], abs=0.01
        )
