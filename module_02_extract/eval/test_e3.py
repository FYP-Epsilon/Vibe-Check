"""test_e3.py -- unit tests for e3_correlation.py (X3).

Statistics functions checked against hand-computed values; the recorder
checked for correctness on a small hand-built base/mutant pair.
"""

from __future__ import annotations

import pytest

from eval.e3_correlation import (
    fisher_z_ci,
    pearson_r,
    semantic_diff_rate,
    spearman_rho,
)


class TestPearsonR:
    def test_known_value(self):
        # mean x=3, mean y=3; dx=[-2,-1,0,1,2]; dy=[-1,-2,1,0,2]
        # cov = 2+2+0+0+4=8; vx=10; vy=10 -> r = 8/10 = 0.8
        xs = [1, 2, 3, 4, 5]
        ys = [2, 1, 4, 3, 5]
        assert pearson_r(xs, ys) == pytest.approx(0.8, abs=1e-9)

    def test_perfect_positive_correlation(self):
        assert pearson_r([1, 2, 3, 4], [1, 2, 3, 4]) == pytest.approx(1.0)

    def test_perfect_negative_correlation(self):
        assert pearson_r([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)

    def test_zero_variance_returns_zero(self):
        assert pearson_r([1, 1, 1], [1, 2, 3]) == 0.0


class TestSpearmanRho:
    def test_known_value_no_ties(self):
        # y is a permutation of 1..5 so rank(y) == y here, coinciding with
        # the Pearson case above but computed through the rank-conversion
        # code path.
        xs = [1, 2, 3, 4, 5]
        ys = [2, 1, 4, 3, 5]
        assert spearman_rho(xs, ys) == pytest.approx(0.8, abs=1e-9)

    def test_perfect_correlation_with_ties(self):
        xs = [1, 2, 2, 3]
        ys = [1, 2, 2, 3]
        assert spearman_rho(xs, ys) == pytest.approx(1.0)


class TestFisherZCI:
    def test_known_value(self):
        # r=0.8, n=5: z=atanh(0.8), se=1/sqrt(2), z_crit=1.96
        lo, hi = fisher_z_ci(0.8, 5)
        assert lo == pytest.approx(-0.27966351711309484, abs=1e-6)
        assert hi == pytest.approx(0.9861968915080719, abs=1e-6)

    def test_ci_contains_point_estimate(self):
        lo, hi = fisher_z_ci(0.5, 30)
        assert lo <= 0.5 <= hi

    def test_perfect_correlation_degenerate(self):
        assert fisher_z_ci(1.0, 10) == (1.0, 1.0)

    def test_too_few_samples_degenerate(self):
        lo, hi = fisher_z_ci(0.5, 3)
        assert (lo, hi) == (0.5, 0.5)


class TestSemanticDiffRate:
    BASE = (
        "def stub_a():\n    return {'v': 1}\n\n\n"
        "def stub_b():\n    return {'v': 2}\n\n\n"
        "def workflow(x: int) -> int:\n"
        "    a = stub_a()\n"
        "    b = stub_b()\n"
        "    return 0\n"
    )

    def test_base_vs_itself_is_zero(self):
        inputs = [{"x": i} for i in range(5)]
        rate = semantic_diff_rate(self.BASE, self.BASE, "workflow", inputs)
        assert rate == 0.0

    def test_drop_step_mutant_is_nonzero(self):
        mutant = self.BASE.replace("    b = stub_b()\n", "")
        assert mutant != self.BASE
        inputs = [{"x": i} for i in range(5)]
        rate = semantic_diff_rate(self.BASE, mutant, "workflow", inputs)
        # Dropping an unconditional stub call changes the call sequence on
        # every input regardless of x -- diff_rate should be 1.0 here.
        assert rate > 0.0
        assert rate == pytest.approx(1.0)
