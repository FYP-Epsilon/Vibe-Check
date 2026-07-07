"""d3_control.py -- Session D, D3: the task_only-vs-strict control experiment.

Runs the full differential mutation calibration (same manifest, same seed,
same tau-selection procedure as calibrate_corrected.py's three-figure
result) TWICE -- once in strict mode (the regression proof: must reproduce
Session A's frozen numbers exactly, since comparison_mode="strict" is a
behavioral no-op vs pre-D1 code) and once in task_only mode (the control:
pre-registered expectation is that negate-guard/constant-perturb collapse
back toward their pre-F2/pre-A2 levels, since those operators' detection
rides on branch-decision divergence that task_only discards by design).

Standalone and read-only:
- Does NOT write threshold.json (no operating-threshold change this
  session -- both runs here are clearly-labeled control/regression-proof
  experiments, not a new frozen operating point).
- Does NOT modify calibrate_corrected.py's frozen report or overwrite
  eval/results/calibration_report_differential.md.
- Reuses eval/results/e3_pairs.csv ONLY for its semantic_diff_rate ground
  truth (genuine vs equivalent classification, code-vs-code, independent
  of comparison_mode) -- never its combined_confidence column, which is
  strict-mode-frozen from an earlier session; combined_confidence for
  every base and mutant is recomputed fresh here, once per mode, so the
  strict/task_only comparison is a true apples-to-apples rerun.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL_DIR))

from calibrate import (  # noqa: E402
    ALPHA, SEED, _base_func_wir, _base_tag, _load_manifest,
    clopper_pearson, run_differential_verification, stratified_split,
)
from calibrate_corrected import _load_pairs, _mutant_id  # noqa: E402

RESULTS_DIR = EVAL_DIR / "results"


def score_base_programs(manifest: list[dict[str, Any]], comparison_mode: str) -> dict[int, float]:
    manifest_by_uid = {e["uid"]: e for e in manifest if "base_uid" not in e}
    cache: dict[int, Any] = {}
    scores: dict[int, float] = {}
    for uid, entry in manifest_by_uid.items():
        base = _base_func_wir(uid, manifest_by_uid, cache)
        if base is None:
            continue
        base_source, base_func_wir = base
        cert = run_differential_verification(
            base_source, base_func_wir, base_source=base_source, comparison_mode=comparison_mode,
        )
        scores[uid] = cert.get("combined_confidence", 0.0)
    return scores


def score_mutants(manifest: list[dict[str, Any]], pairs: dict[str, dict[str, Any]], comparison_mode: str) -> dict[str, float]:
    manifest_by_uid = {e["uid"]: e for e in manifest if "base_uid" not in e}
    cache: dict[int, Any] = {}
    scores: dict[str, float] = {}
    mutant_entries = [e for e in manifest if e.get("applicable") and "base_uid" in e]
    for entry in mutant_entries:
        mid = _mutant_id(entry)
        if mid not in pairs:
            continue
        base_uid = entry["base_uid"]
        base = _base_func_wir(base_uid, manifest_by_uid, cache)
        if base is None:
            continue
        base_source, base_func_wir = base
        mutant_path = EVAL_DIR / entry["source_file"]
        mutant_source = mutant_path.read_text(encoding="utf-8")
        cert = run_differential_verification(
            mutant_source, base_func_wir, base_source=base_source, comparison_mode=comparison_mode,
        )
        scores[mid] = cert.get("combined_confidence", 0.0)
    return scores


def build_records(
    manifest: list[dict[str, Any]],
    pairs: dict[str, dict[str, Any]],
    base_scores: dict[int, float],
    mutant_scores: dict[str, float],
) -> list[dict[str, Any]]:
    manifest_by_uid = {e["uid"]: e for e in manifest if "base_uid" not in e}
    records: list[dict[str, Any]] = []

    for uid, score in base_scores.items():
        entry = manifest_by_uid[uid]
        records.append({
            "uid": uid, "class": "correct", "operator": None,
            "tag": _base_tag(entry.get("tags", [])),
            "combined_confidence": score,
        })

    mutant_entries = [e for e in manifest if e.get("applicable") and "base_uid" in e]
    for entry in mutant_entries:
        mid = _mutant_id(entry)
        row = pairs.get(mid)
        if row is None or mid not in mutant_scores:
            continue
        diff_rate = float(row["semantic_diff_rate"])
        base_uid = entry["base_uid"]
        records.append({
            "uid": base_uid,
            "class": "buggy" if diff_rate > 0 else "equivalent",
            "operator": entry["operator"],
            "tag": _base_tag(manifest_by_uid[base_uid].get("tags", [])),
            "combined_confidence": mutant_scores[mid],
        })

    return records


def youdens_j_on_genuine(records: list[dict[str, Any]]) -> tuple[float, float]:
    positives = [r for r in records if r["class"] == "buggy"]
    negatives = [r for r in records if r["class"] == "correct"]
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


def three_figure_eval(records: list[dict[str, Any]], tau: float) -> dict[str, Any]:
    genuine = [r for r in records if r["class"] == "buggy"]
    equivalent = [r for r in records if r["class"] == "equivalent"]
    correct = [r for r in records if r["class"] == "correct"]

    detected = sum(1 for r in genuine if r["combined_confidence"] < tau)
    equiv_flagged = sum(1 for r in equivalent if r["combined_confidence"] < tau)
    base_flagged = sum(1 for r in correct if r["combined_confidence"] < tau)

    def _rate_ci(k: int, n: int) -> tuple[Optional[float], Optional[tuple[float, float]], int]:
        if n == 0:
            return None, None, 0
        return k / n, clopper_pearson(k, n, ALPHA), n

    detection_rate, detection_ci, n_genuine = _rate_ci(detected, len(genuine))
    equiv_flag_rate, equiv_flag_ci, n_equiv = _rate_ci(equiv_flagged, len(equivalent))
    false_alarm_rate, false_alarm_ci, n_correct = _rate_ci(base_flagged, len(correct))

    by_operator: dict[str, dict[str, Any]] = {}
    for op in sorted({r["operator"] for r in genuine if r["operator"]}):
        op_records = [r for r in genuine if r["operator"] == op]
        op_detected = sum(1 for r in op_records if r["combined_confidence"] < tau)
        by_operator[op] = {"n": len(op_records), "detected": op_detected,
                            "rate": op_detected / len(op_records) if op_records else None}

    return {
        "tau": tau,
        "detection_rate": detection_rate, "detection_ci": detection_ci, "n_genuine": n_genuine,
        "equivalent_specificity": (1 - equiv_flag_rate) if equiv_flag_rate is not None else None,
        "n_equivalent": n_equiv,
        "false_alarm_rate": false_alarm_rate, "false_alarm_ci": false_alarm_ci, "n_correct": n_correct,
        "by_operator": by_operator,
    }


def run_mode(manifest: list[dict[str, Any]], pairs: dict[str, dict[str, Any]], comparison_mode: str) -> dict[str, Any]:
    base_scores = score_base_programs(manifest, comparison_mode)
    mutant_scores = score_mutants(manifest, pairs, comparison_mode)
    records = build_records(manifest, pairs, base_scores, mutant_scores)

    calib_uids, eval_uids = stratified_split(manifest, seed=SEED)
    calib_records = [r for r in records if r["uid"] in calib_uids]
    eval_records = [r for r in records if r["uid"] in eval_uids]

    tau, best_j = youdens_j_on_genuine(calib_records)
    eval_summary = three_figure_eval(eval_records, tau)
    return {"mode": comparison_mode, "tau": tau, "youdens_j": best_j, "eval": eval_summary}


def run_d3() -> dict[str, Any]:
    manifest = _load_manifest()
    pairs = _load_pairs()
    strict = run_mode(manifest, pairs, "strict")
    task_only = run_mode(manifest, pairs, "task_only")
    return {"strict": strict, "task_only": task_only}


if __name__ == "__main__":
    result = run_d3()
    for mode, r in result.items():
        e = r["eval"]
        print(f"{mode}: tau={r['tau']:.4f} J={r['youdens_j']:.4f} "
              f"detection={e['detection_rate']:.4f} FA={e['false_alarm_rate']:.4f}")
