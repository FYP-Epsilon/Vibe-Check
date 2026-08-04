"""
tests/test_counterexample.py
=============================
Pure-Python tests for counterexample.py -- no SPOT/C++ toolchain required.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from counterexample import format_counterexample


REAL_UID44_TRACE = (
    "Counter-example trace (prefix):\n"
    "  [0] state=1 label=Invoice & !PriceLevel & !SalesOrder & !Slack & alive & !invoices & !not_invoices\n"
    "  [1] state=2 label=!Invoice & !PriceLevel & !SalesOrder & !Slack & alive & invoices & !not_invoices\n"
    "  [2] state=3 label=!Invoice & !PriceLevel & !SalesOrder & Slack & alive & !invoices & !not_invoices\n"
    "  [3] state=4 label=!Invoice & PriceLevel & !SalesOrder & !Slack & alive & !invoices & !not_invoices\n"
    "  [4] state=5 label=!Invoice & !PriceLevel & SalesOrder & !Slack & alive & !invoices & !not_invoices\n"
    "Counter-example trace (cycle):\n"
    "  [0] state=6 label=!alive\n"
)


def test_empty_trace_returns_empty_string():
    assert format_counterexample("", "!start(X) W done(Y)") == ""


def test_filters_to_only_the_formulas_own_atoms():
    formula = "!start(PriceLevel) W done(SalesOrder)"
    result = format_counterexample(REAL_UID44_TRACE, formula)
    assert result == "PriceLevel → SalesOrder"


def test_different_formula_same_trace_different_atoms():
    formula = "!start(Invoice) W done(PriceLevel)"
    result = format_counterexample(REAL_UID44_TRACE, formula)
    assert result == "Invoice → PriceLevel"


def test_no_relevant_atoms_in_trace_gives_explicit_message():
    formula = "!start(NeverInTrace) W done(AlsoNeverInTrace)"
    result = format_counterexample(REAL_UID44_TRACE, formula)
    assert "never touches" in result


def test_formula_with_no_atoms_returns_raw_trace_verbatim():
    # A malformed/unusual formula this parser can't extract atoms from --
    # degrade to showing the raw trace rather than silently losing it.
    result = format_counterexample(REAL_UID44_TRACE, "G(1)")
    assert result == REAL_UID44_TRACE
