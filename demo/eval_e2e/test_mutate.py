"""Regression tests for mutate.py's mutation generators. Pure AST logic --
no C++ engine or corpus access needed, unlike test_harness.py."""

import ast

from .mutate import (
    call_sequence,
    generate_constant_perturbation,
    generate_order_mutations,
)

SOURCE = '''
def step_a():
    return 1


def step_b():
    return 2


def step_c():
    return 3


def workflow():
    x = step_a()
    y = step_b()
    z = step_c(count=5, label="hi")
    return x, y, z
'''


class TestGenerateOrderMutations:
    def test_drop_step_removes_exactly_one_statement(self):
        mutations = generate_order_mutations(SOURCE, "workflow")
        drops = [m for m in mutations if m.kind == "drop_step"]
        assert len(drops) == 3
        for m in drops:
            tree = ast.parse(m.source)
            driver = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "workflow")
            assert len(driver.body) == 3  # 4 - 1 dropped
            assert len(m.affected_calls) == 1

    def test_swap_adjacent_reorders_two_statements(self):
        mutations = generate_order_mutations(SOURCE, "workflow")
        swaps = [m for m in mutations if m.kind == "swap_adjacent"]
        assert len(swaps) == 2  # (a,b) and (b,c) adjacent pairs
        for m in swaps:
            seq = call_sequence(m.source, "workflow")
            assert seq != ("step_a", "step_b", "step_c")
            assert sorted(seq) == ["step_a", "step_b", "step_c"]

    def test_no_mutations_below_two_targets(self):
        source = "def step_a():\n    return 1\n\n\ndef workflow():\n    x = step_a()\n    return x\n"
        assert generate_order_mutations(source, "workflow") == []

    def test_missing_driver_returns_empty(self):
        assert generate_order_mutations(SOURCE, "not_the_driver") == []


class TestCallSequence:
    def test_matches_source_order(self):
        assert call_sequence(SOURCE, "workflow") == ("step_a", "step_b", "step_c")

    def test_empty_for_missing_driver(self):
        assert call_sequence(SOURCE, "nope") == ()


class TestGenerateConstantPerturbation:
    def test_skips_driver_keyword_arguments(self):
        """count=5 and label="hi" select which stub call executes here --
        must not be the literal perturbed, since that isn't guaranteed
        order-preserving."""
        mutation = generate_constant_perturbation(SOURCE, "workflow")
        assert mutation is not None
        assert "count=5" in mutation.source
        assert 'label=\'hi\'' in mutation.source or 'label="hi"' in mutation.source
        # the driver's own call-order must be untouched by this mutation
        assert call_sequence(mutation.source, "workflow") == call_sequence(SOURCE, "workflow")
        # something was actually perturbed (one of the three stub return literals)
        assert mutation.source != SOURCE

    def test_none_when_no_eligible_constant(self):
        source = "def workflow():\n    step_a()\n    step_b()\n"
        assert generate_constant_perturbation(source, "workflow") is None
