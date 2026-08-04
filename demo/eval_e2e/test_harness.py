"""Regression coverage for the E2E evaluation harness (Next Steps.md item
#7). Skipped entirely if the C++ engine isn't compiled -- same convention
as demo/test_e2e_demo.py and module_03_equiv/tests/test_cpp_engine.py.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "module_03_equiv", "src"))

import pytest

try:
    import vibecheck_lifter  # noqa: F401
    HAS_MODULE = True
except ImportError:
    HAS_MODULE = False

pytestmark = pytest.mark.skipif(
    not HAS_MODULE,
    reason="vibecheck_lifter.so not compiled — skipping E2E eval harness tests.",
)

from .harness import clopper_pearson, discover_gold_specs, evaluate_spec  # noqa: E402


def test_clopper_pearson_matches_known_values():
    """Sanity check against textbook Clopper-Pearson values (also cross-
    checked against module_02_extract/eval/calibrate.py's own port, not
    reimported here -- see harness.py's module docstring for why)."""
    lo, hi = clopper_pearson(0, 10)
    assert lo == 0.0
    assert 0.0 < hi < 0.5
    lo, hi = clopper_pearson(10, 10)
    assert hi == 1.0
    assert 0.5 < lo < 1.0


def test_discover_gold_specs_finds_uid_77():
    """uid 77 is the corpus's own known-COMPLIANT pair (see
    demo/e2e_demo.py, CP1 Lifting-Scope Decision.md) -- must always surface
    as a gold spec."""
    specs = discover_gold_specs()
    uids = [c.uid for c in specs]
    assert 77 in uids


def test_uid_77_mutation_outcomes_are_pinned():
    """Regression-pins the exact finding this harness's first real run
    surfaced for uid 77 (see demo/eval_e2e/results/e2e_eval_report.md):
    dropping either of its 2 driver calls makes that task's own atom
    unobservable (ABSTAINED_INCONCLUSIVE, not a miss), while swapping their
    order is a genuine, correctly-detected violation."""
    specs = discover_gold_specs()
    ctx = next(c for c in specs if c.uid == 77)
    trials, _ = evaluate_spec(ctx)

    drops = [t for t in trials if t.kind == "drop_step"]
    swaps = [t for t in trials if t.kind == "swap_adjacent"]
    assert len(drops) == 2
    assert all(t.verdict_kind == "ABSTAINED_INCONCLUSIVE" for t in drops)
    assert len(swaps) == 1
    assert swaps[0].verdict_kind == "DETECTED"
    assert swaps[0].counterexample_ok is True
