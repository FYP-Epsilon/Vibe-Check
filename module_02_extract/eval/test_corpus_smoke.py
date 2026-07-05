"""test_corpus_smoke.py -- smoke test for the FLOW-BENCH generated corpus.

Runs a sample of generated corpus programs (spanning linear, conditional,
loop, user_task, and update-style tags) through the real Module 02
verification pipeline and asserts each one round-trips to a well-formed
certificate -- i.e. never falls through to main.py's outer exception
handler (which would return an empty wir/details dict and an "aborted"
message).
"""

from __future__ import annotations

import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
MODULE02_DIR = EVAL_DIR.parent
sys.path.insert(0, str(MODULE02_DIR / "src"))

from main import _run_verification  # noqa: E402

# Spans: linear (1, 8), conditional (2), loop+conditional (4, 90),
# user_task (31), linear_update_delete (77), linear_update_replace (82),
# conditional_update_delete (88), conditional_update_replace (11).
SAMPLE_UIDS = [1, 2, 4, 8, 11, 31, 77, 82, 88, 90]


def _is_well_formed(cert: dict) -> bool:
    required_keys = {
        "v3_coverage", "v2_confidence", "v1_confidence",
        "combined_confidence", "passed", "message", "wir",
    }
    if not required_keys.issubset(cert.keys()):
        return False
    # The outer catch-all in main.py:verify returns an empty wir/details
    # dict with an "aborted" message -- that's the failure mode we're
    # checking against, not the legitimate "passed: False" verdict.
    if cert["wir"] == {} and "aborted" in cert["message"].lower():
        return False
    return isinstance(cert["passed"], bool)


class TestCorpusSmoke:
    def test_sample_round_trips_without_outer_exception(self):
        corpus_dir = EVAL_DIR / "corpus"
        failures = []
        for uid in SAMPLE_UIDS:
            path = corpus_dir / f"uid_{uid}.py"
            assert path.exists(), f"corpus file missing for uid {uid}; run flowbench_adapter.py"
            source = path.read_text(encoding="utf-8")
            cert = _run_verification(source)
            if not _is_well_formed(cert):
                failures.append((uid, cert.get("message")))
        assert not failures, f"non-well-formed certificates: {failures}"

    def test_full_corpus_generated(self):
        corpus_dir = EVAL_DIR / "corpus"
        manifest_path = EVAL_DIR / "manifest.json"
        assert manifest_path.exists()
        generated = list(corpus_dir.glob("uid_*.py"))
        assert len(generated) == 101
