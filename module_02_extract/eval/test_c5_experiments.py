"""test_c5_experiments.py -- Session C, C5c divergence-classification unit
tests. No network calls, no differential-verification runs (those are
covered by the full corpus run recorded in eval/results/multi_impl_report.md,
not re-run in tests)."""

from __future__ import annotations

from eval.c5_experiments import _is_exception_class


class TestIsExceptionClass:
    def test_variant_side_exception_is_exception_class(self):
        rec = {"admission": {"first_divergent_input": {
            "base_return": "None", "variant_return": "__exception__:KeyError",
        }}}
        assert _is_exception_class(rec) is True

    def test_base_side_exception_is_exception_class(self):
        rec = {"admission": {"first_divergent_input": {
            "base_return": "__exception__:KeyError", "variant_return": "None",
        }}}
        assert _is_exception_class(rec) is True

    def test_no_exception_is_logic_class(self):
        rec = {"admission": {"first_divergent_input": {
            "base_return": "0", "variant_return": "1",
        }}}
        assert _is_exception_class(rec) is False

    def test_no_divergence_record_is_logic_class(self):
        rec = {"admission": {"first_divergent_input": None}}
        assert _is_exception_class(rec) is False
