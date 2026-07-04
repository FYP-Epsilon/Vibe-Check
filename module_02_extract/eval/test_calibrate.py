"""test_calibrate.py -- sanity tests for eval/calibrate.py's statistics.

clopper_pearson is a from-scratch (no scipy) implementation of the exact
binomial confidence interval; these tests check it against known reference
values and basic invariants rather than re-deriving the math.
"""

from __future__ import annotations

import pytest

from eval.calibrate import clopper_pearson, stratified_split, _base_tag


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
