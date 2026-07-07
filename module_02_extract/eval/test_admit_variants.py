"""test_admit_variants.py -- Session C, C3 admission-plumbing unit tests.
No network calls anywhere in this module (pure code-vs-code execution)."""

from __future__ import annotations

from eval.admit_variants import (
    generate_admission_inputs, admission_check, _generate_inputs_round_robin,
)


BASE_SOURCE = (
    "def workflow(status: str) -> int:\n"
    "    if status == 'high':\n"
    "        return 1\n"
    "    return 0\n"
)


class TestRoundRobinInputGeneration:
    def test_both_pool_literals_covered_within_budget(self):
        pool = ["high", "urgent"]
        inputs_list = generate_admission_inputs(BASE_SOURCE, "workflow", pool, seed=1, n=10)
        seen = {i["status"] for i in inputs_list}
        assert "high" in seen
        assert "urgent" in seen

    def test_deterministic_under_fixed_seed(self):
        pool = ["high"]
        a = generate_admission_inputs(BASE_SOURCE, "workflow", pool, seed=42, n=20)
        b = generate_admission_inputs(BASE_SOURCE, "workflow", pool, seed=42, n=20)
        assert a == b

    def test_queue_drains_before_random_fallback(self):
        import random
        pool = ["alpha", "beta"]
        queue = list(pool)
        rng = random.Random(0)

        # First two draws must come from the queue in order.
        def make_func(status: str) -> int:
            return 0
        first = _generate_inputs_round_robin(make_func, pool, queue, rng)
        second = _generate_inputs_round_robin(make_func, pool, queue, rng)
        assert first["status"] == "alpha"
        assert second["status"] == "beta"
        assert queue == []


class TestAdmissionCheck:
    def test_identical_source_admits(self):
        inputs_list = generate_admission_inputs(BASE_SOURCE, "workflow", ["high"], seed=1, n=20)
        rate, first_div = admission_check(BASE_SOURCE, BASE_SOURCE, "workflow", inputs_list)
        assert rate == 0.0
        assert first_div is None

    def test_behaviorally_different_source_rejected(self):
        variant_source = (
            "def workflow(status: str) -> int:\n"
            "    if status == 'high':\n"
            "        return 2\n"  # different return value on the same branch
            "    return 0\n"
        )
        inputs_list = generate_admission_inputs(BASE_SOURCE, "workflow", ["high"], seed=1, n=20)
        rate, first_div = admission_check(BASE_SOURCE, variant_source, "workflow", inputs_list)
        assert rate > 0.0
        assert first_div is not None
        assert first_div["base_return"] != first_div["variant_return"]

    def test_crashing_variant_recorded_as_exception(self):
        variant_source = (
            "def workflow(status: str) -> int:\n"
            "    return 1 / 0\n"
        )
        inputs_list = generate_admission_inputs(BASE_SOURCE, "workflow", ["high"], seed=1, n=5)
        rate, first_div = admission_check(BASE_SOURCE, variant_source, "workflow", inputs_list)
        assert rate == 1.0
        assert first_div["variant_return"].startswith("__exception__:")
