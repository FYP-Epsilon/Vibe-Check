"""
demo/test_e2e_demo.py
======================
Regression coverage for the first real end-to-end demo (Next Steps.md item
#6): BPMN spec -> Module 01 -> Module 02 (call-order WIR) -> Module 03
(Phase A-D check) -> PASS/FAIL + readable counterexample, against the real
FLOW-BENCH corpus and the real compiled vibecheck_lifter engine.

Skipped entirely if the C++ engine isn't compiled -- same convention as
module_03_equiv/tests/test_cpp_engine.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "module_03_equiv", "src"))

import pytest

try:
    import vibecheck_lifter  # noqa: F401
    HAS_MODULE = True
except ImportError:
    HAS_MODULE = False

pytestmark = pytest.mark.skipif(
    not HAS_MODULE,
    reason="vibecheck_lifter.so not compiled — skipping e2e demo tests.",
)

from e2e_demo import check_variant  # noqa: E402


def test_uid44_is_a_real_violation_with_a_readable_counterexample():
    """uid 44's two real LLM implementations violate two genuine ordering
    properties -- confirmed against the D2 fix's own acceptance pair."""
    report = check_variant(44, "44__llama-3.1-8b.py")
    assert report["overall"] == "FAIL"
    assert report["n_violation"] == 2
    for r in report["results"]:
        if r["verdict"] == "VIOLATION":
            assert r["readable_counterexample"]
            assert "state=" not in r["readable_counterexample"]  # not the raw SPOT dump
            assert "&" not in r["readable_counterexample"]


def test_uid77_is_a_real_compliant_case():
    """uid 77's real implementation satisfies its one determinable ordering
    property (the exact case that flips VIOLATION -> COMPLIANT under D2's
    call-order lifting -- see CP1 Lifting-Scope Decision.md)."""
    report = check_variant(77, "77__llama-3.1-8b.py")
    assert report["overall"] == "PASS"
    assert report["n_violation"] == 0
    assert report["n_compliant"] >= 1


def test_driver_is_the_workflow_function_for_both_specs():
    """Both real FLOW-BENCH variants follow the corpus's own convention of a
    single orchestrator function named "workflow"."""
    assert check_variant(44, "44__llama-3.1-8b.py")["driver"] == "workflow"
    assert check_variant(77, "77__llama-3.1-8b.py")["driver"] == "workflow"
