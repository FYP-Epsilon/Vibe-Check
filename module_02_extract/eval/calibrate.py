"""calibrate.py -- calibration runner for the Module 02 verification pipeline.

Splits the FLOW-BENCH-derived corpus (label "correct") and its mutants
(label "buggy") into CALIB/EVAL sets -- 50/50, stratified by the base
program's semantic tag, fixed seed -- runs every program through the real
V3->V2->V1 pipeline, picks a decision threshold tau on CALIB by maximizing
Youden's J on the combined_confidence ROC curve, then reports detection
rate (recall on buggy) and false-alarm rate (1 - specificity on correct)
on the held-out EVAL set with exact Clopper-Pearson binomial confidence
intervals. No scipy/numpy dependency: the binomial CDF is computed
exactly via math.comb and inverted by bisection.
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path
from typing import Any, Optional

EVAL_DIR = Path(__file__).resolve().parent
MODULE02_DIR = EVAL_DIR.parent
sys.path.insert(0, str(MODULE02_DIR / "src"))

from main import _run_verification  # noqa: E402

MANIFEST_PATH = EVAL_DIR / "manifest.json"
THRESHOLD_PATH = EVAL_DIR / "threshold.json"
RESULTS_DIR = EVAL_DIR / "results"

SEED = 1234
ALPHA = 0.05  # 95% confidence intervals


# ----------------------------------------------------------------------
# Exact binomial CDF + Clopper-Pearson interval (no scipy dependency)
# ----------------------------------------------------------------------

def _binom_sf_ge(n: int, p: float, x: int) -> float:
    """P(X >= x) for X ~ Binomial(n, p)."""
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(x, n + 1))


def _binom_cdf_le(n: int, p: float, x: int) -> float:
    """P(X <= x) for X ~ Binomial(n, p)."""
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(0, x + 1))


def clopper_pearson(successes: int, n: int, alpha: float = ALPHA) -> tuple[float, float]:
    """Exact two-sided (1-alpha) binomial confidence interval for a
    proportion successes/n, via bisection on the exact binomial CDF."""
    if n == 0:
        return (0.0, 1.0)

    if successes == 0:
        lo = 0.0
    else:
        lo_lo, lo_hi = 0.0, 1.0
        target = alpha / 2
        for _ in range(100):
            mid = (lo_lo + lo_hi) / 2
            if _binom_sf_ge(n, mid, successes) > target:
                lo_hi = mid
            else:
                lo_lo = mid
        lo = (lo_lo + lo_hi) / 2

    if successes == n:
        hi = 1.0
    else:
        hi_lo, hi_hi = 0.0, 1.0
        target = alpha / 2
        for _ in range(100):
            mid = (hi_lo + hi_hi) / 2
            if _binom_cdf_le(n, mid, successes) > target:
                hi_lo = mid
            else:
                hi_hi = mid
        hi = (hi_lo + hi_hi) / 2

    return (lo, hi)


# ----------------------------------------------------------------------
# Manifest / split handling
# ----------------------------------------------------------------------

def _load_manifest() -> list[dict[str, Any]]:
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _base_tag(tags: list[str]) -> str:
    """The semantic (non-numeric) tag used for stratification."""
    for t in tags:
        if not t.isdigit():
            return t
    return "unknown"


def _uid_for(entry: dict[str, Any]) -> int:
    return entry.get("base_uid", entry.get("uid"))


def _label_for(entry: dict[str, Any]) -> str:
    return "buggy" if "base_uid" in entry else "correct"


def stratified_split(manifest: list[dict[str, Any]], seed: int = SEED) -> tuple[set[int], set[int]]:
    """50/50 split of base (corpus) uids into CALIB/EVAL, stratified by
    semantic tag. Mutants inherit their base_uid's split assignment."""
    corpus_entries = [e for e in manifest if "base_uid" not in e]
    by_tag: dict[str, list[int]] = {}
    for e in corpus_entries:
        by_tag.setdefault(_base_tag(e.get("tags", [])), []).append(e["uid"])

    rng = random.Random(seed)
    calib: set[int] = set()
    eval_set: set[int] = set()
    for tag, uids in by_tag.items():
        uids = sorted(set(uids))
        rng.shuffle(uids)
        half = len(uids) // 2
        calib.update(uids[:half])
        eval_set.update(uids[half:])
    return calib, eval_set


# ----------------------------------------------------------------------
# Pipeline execution
# ----------------------------------------------------------------------

def run_pipeline_on_manifest(manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run every runnable manifest entry through _run_verification."""
    records: list[dict[str, Any]] = []
    for entry in manifest:
        if entry.get("applicable") is False:
            continue
        source_file = entry.get("source_file")
        if not source_file:
            continue
        path = EVAL_DIR / source_file
        if not path.exists():
            continue
        source = path.read_text(encoding="utf-8")
        cert = _run_verification(source)
        records.append({
            "uid": _uid_for(entry),
            "label": _label_for(entry),
            "operator": entry.get("operator"),
            "combined_confidence": cert.get("combined_confidence", 0.0),
        })
    return records


# ----------------------------------------------------------------------
# Threshold selection
# ----------------------------------------------------------------------

def youdens_j_threshold(records: list[dict[str, Any]]) -> tuple[float, float]:
    """tau that maximizes sensitivity+specificity-1 for the rule
    'predict buggy iff combined_confidence < tau'. Returns (tau, best_j)."""
    positives = [r for r in records if r["label"] == "buggy"]
    negatives = [r for r in records if r["label"] == "correct"]
    scores = sorted({r["combined_confidence"] for r in records})
    candidates = [0.0] + scores + [1.0]

    best_tau, best_j = 0.95, -1.0
    for tau in candidates:
        tp = sum(1 for r in positives if r["combined_confidence"] < tau)
        tn = sum(1 for r in negatives if r["combined_confidence"] >= tau)
        sensitivity = tp / len(positives) if positives else 0.0
        specificity = tn / len(negatives) if negatives else 0.0
        j = sensitivity + specificity - 1.0
        if j > best_j:
            best_j, best_tau = j, tau
    return best_tau, best_j


def evaluate_at_threshold(records: list[dict[str, Any]], tau: float) -> dict[str, Any]:
    positives = [r for r in records if r["label"] == "buggy"]
    negatives = [r for r in records if r["label"] == "correct"]

    tp = sum(1 for r in positives if r["combined_confidence"] < tau)
    fp = sum(1 for r in negatives if r["combined_confidence"] < tau)

    detection_rate = tp / len(positives) if positives else None
    false_alarm_rate = fp / len(negatives) if negatives else None
    detection_ci = clopper_pearson(tp, len(positives)) if positives else None
    false_alarm_ci = clopper_pearson(fp, len(negatives)) if negatives else None

    by_operator: dict[str, dict[str, Any]] = {}
    for op in sorted({r["operator"] for r in positives if r["operator"]}):
        op_records = [r for r in positives if r["operator"] == op]
        op_tp = sum(1 for r in op_records if r["combined_confidence"] < tau)
        by_operator[op] = {
            "n": len(op_records),
            "detected": op_tp,
            "detection_rate": op_tp / len(op_records) if op_records else None,
        }

    return {
        "tau": tau,
        "n_positives": len(positives),
        "n_negatives": len(negatives),
        "detection_rate": detection_rate,
        "detection_ci_95": detection_ci,
        "false_alarm_rate": false_alarm_rate,
        "false_alarm_ci_95": false_alarm_ci,
        "by_operator": by_operator,
    }


# ----------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------

def _fmt_ci(ci: Optional[tuple[float, float]]) -> str:
    if ci is None:
        return "n/a"
    return f"[{ci[0]:.3f}, {ci[1]:.3f}]"


def render_report(calib_summary: dict[str, Any], eval_summary: dict[str, Any], seed: int) -> str:
    lines = [
        "# Module 02 Calibration Report",
        "",
        f"Seed: `{seed}`. CALIB/EVAL split: 50/50 stratified by base-program tag.",
        "",
        "## Threshold selection (CALIB)",
        "",
        f"- Youden's J-optimal tau: **{calib_summary['tau']:.4f}**",
        f"- Youden's J at tau: {calib_summary['best_j']:.4f}",
        f"- CALIB positives (buggy): {calib_summary['n_positives']}",
        f"- CALIB negatives (correct): {calib_summary['n_negatives']}",
        "",
        "## Held-out evaluation (EVAL)",
        "",
        f"- Detection rate (recall on buggy): "
        f"{eval_summary['detection_rate']:.4f} "
        f"(95% CI {_fmt_ci(eval_summary['detection_ci_95'])}, n={eval_summary['n_positives']})",
        f"- False-alarm rate (buggy-predicted among correct): "
        f"{eval_summary['false_alarm_rate']:.4f} "
        f"(95% CI {_fmt_ci(eval_summary['false_alarm_ci_95'])}, n={eval_summary['n_negatives']})",
        "",
        "## Detection rate by mutation operator (EVAL)",
        "",
        "| operator | n | detected | detection rate |",
        "|---|---|---|---|",
    ]
    for op, stats in sorted(eval_summary["by_operator"].items()):
        rate = f"{stats['detection_rate']:.3f}" if stats["detection_rate"] is not None else "n/a"
        lines.append(f"| {op} | {stats['n']} | {stats['detected']} | {rate} |")
    lines.append("")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main() -> None:
    manifest = _load_manifest()
    calib_uids, eval_uids = stratified_split(manifest, seed=SEED)

    calib_manifest = [e for e in manifest if _uid_for(e) in calib_uids]
    eval_manifest = [e for e in manifest if _uid_for(e) in eval_uids]

    calib_records = run_pipeline_on_manifest(calib_manifest)
    eval_records = run_pipeline_on_manifest(eval_manifest)

    tau, best_j = youdens_j_threshold(calib_records)
    calib_summary = evaluate_at_threshold(calib_records, tau)
    calib_summary["best_j"] = best_j
    eval_summary = evaluate_at_threshold(eval_records, tau)

    THRESHOLD_PATH.write_text(
        json.dumps({
            "tau": tau,
            "youdens_j": best_j,
            "seed": SEED,
            "n_calib_positives": calib_summary["n_positives"],
            "n_calib_negatives": calib_summary["n_negatives"],
        }, indent=2),
        encoding="utf-8",
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report = render_report(calib_summary, eval_summary, SEED)
    (RESULTS_DIR / "calibration_report.md").write_text(report, encoding="utf-8")

    print(report)


if __name__ == "__main__":
    main()
