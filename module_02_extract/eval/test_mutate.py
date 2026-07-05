"""test_mutate.py -- unit tests for eval/mutate.py's mutation operators.

Exercises a subset of the 10 operators on a small fixed base program and
verifies each mutant (a) is a different source string, (b) still parses,
and (c) actually differs semantically from the base on at least one input.
"""

from __future__ import annotations

from eval.mutate import apply_operator
from eval.e3_correlation import semantic_diff_rate

BASE_SOURCE = '''\
def stub_check(value=None):
    return {"value": value}


def workflow(x: int):
    data = stub_check(value=x)
    if data["value"] > 10:
        result = "big"
    else:
        result = "small"
    return result
'''


def _run_workflow(source: str, x: int):
    ns: dict = {}
    exec(compile(source, "<mutant>", "exec"), ns)
    return ns["workflow"](x)


class TestMutationOperators:
    def test_negate_guard_differs_semantically(self):
        result = apply_operator(BASE_SOURCE, "negate-guard")
        assert result is not None
        mutated_source, site = result
        assert mutated_source != BASE_SOURCE
        compile(mutated_source, "<mutant>", "exec")  # still parses
        assert _run_workflow(BASE_SOURCE, 20) == "big"
        assert _run_workflow(mutated_source, 20) == "small"

    def test_boundary_shift_differs_semantically(self):
        result = apply_operator(BASE_SOURCE, "boundary-shift")
        assert result is not None
        mutated_source, site = result
        assert mutated_source != BASE_SOURCE
        compile(mutated_source, "<mutant>", "exec")
        assert _run_workflow(BASE_SOURCE, 10) == "small"
        assert _run_workflow(mutated_source, 10) == "big"

    def test_swap_branches_differs_semantically(self):
        result = apply_operator(BASE_SOURCE, "swap-branches")
        assert result is not None
        mutated_source, site = result
        assert mutated_source != BASE_SOURCE
        compile(mutated_source, "<mutant>", "exec")
        assert _run_workflow(BASE_SOURCE, 20) == "big"
        assert _run_workflow(mutated_source, 20) == "small"

    def test_constant_perturb_differs_semantically(self):
        result = apply_operator(BASE_SOURCE, "constant-perturb")
        assert result is not None
        mutated_source, site = result
        assert mutated_source != BASE_SOURCE
        compile(mutated_source, "<mutant>", "exec")
        # 10 > 10 is False on both; the perturbed constant makes 10 > 1010 also
        # False, so pick a value where the perturbation actually flips the guard.
        assert _run_workflow(BASE_SOURCE, 20) == "big"
        assert _run_workflow(mutated_source, 20) == "small"

    def test_off_by_one_loop_inapplicable_without_range_or_slice(self):
        result = apply_operator(BASE_SOURCE, "off-by-one-loop")
        assert result is None

    def test_early_return_cuts_real_logic(self):
        """C3 regression test: the fixed op_early_return must actually
        change behavior (unlike the original, which inserted immediately
        before the trailing return -- a no-op on every generated
        workflow). Uses E3's own recorder (semantic_diff_rate) as the
        independent behavioral check, not a hand-rolled comparison."""
        result = apply_operator(BASE_SOURCE, "early-return")
        assert result is not None
        mutated_source, site = result
        assert mutated_source != BASE_SOURCE
        compile(mutated_source, "<mutant>", "exec")  # still parses

        inputs = [{"x": i} for i in range(-5, 25)]
        rate = semantic_diff_rate(BASE_SOURCE, mutated_source, "workflow", inputs)
        assert rate > 0.0

    def test_early_return_inapplicable_on_short_body(self):
        short_source = "def workflow(x: int):\n    y = x\n    return y\n"
        result = apply_operator(short_source, "early-return")
        assert result is None

    def test_early_return_deterministic_under_fixed_seed(self):
        result1 = apply_operator(BASE_SOURCE, "early-return")
        result2 = apply_operator(BASE_SOURCE, "early-return")
        assert result1 == result2
