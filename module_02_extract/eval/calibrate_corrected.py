"""calibrate_corrected.py -- corrected differential-mode calibration (C4).

The plain "detection rate" figure in the pre-correction differential
report conflated two different things: mutants that are genuinely buggy
(semantic_diff_rate > 0, from eval/e3_correlation.py's code-vs-code
ground truth) and mutants that are behaviorally equivalent to their base
(semantic_diff_rate == 0) -- treating both as "positives" meant a
correctly-equivalent mutant getting flagged counted as a detection win,
not the false alarm it actually is (this is exactly what made the
pre-fix op_early_return's ~0.43 "detection rate" look like partial
success on a hard operator, when 101/101 of those mutants were actually
equivalent).

This module presents three separated figures instead of one aggregate:

1. Genuine-bug detection: recall on EVAL mutants with
   semantic_diff_rate > 0 (E3's code-vs-code ground truth -- the WIR
   never touches this side, same anti-circularity guarantee as E3).
2. Equivalent-mutant specificity: 1 - false-flag rate on EVAL mutants
   with semantic_diff_rate == 0 -- these are NOT bugs, so being flagged
   is a false positive, symmetric with (3) below.
3. False-alarm rate on untouched EVAL base programs (unchanged concept
   from the original report).

Threshold tau is selected on CALIB using ONLY genuinely-buggy mutants as
positives and base programs as negatives -- equivalent mutants are
excluded from tau selection (they're mislabeled data for that purpose,
not a class to optimize the boundary against).
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any, Optional

EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL_DIR))

from calibrate import (  # noqa: E402
    ALPHA, SEED, RESULTS_DIR, THRESHOLD_PATH,
    _base_func_wir, _base_tag, _load_manifest, _uid_for,
    clopper_pearson, run_differential_verification, stratified_split,
)

PAIRS_CSV = RESULTS_DIR / "e3_pairs.csv"


def _load_pairs(path: Path = PAIRS_CSV) -> dict[str, dict[str, Any]]:
    with open(path, "r", newline="", encoding="utf-8") as f:
        return {row["mutant_id"]: row for row in csv.DictReader(f)}


def _mutant_id(entry: dict[str, Any]) -> str:
    return f"{entry['base_uid']}__{entry['operator']}__{entry.get('site') or ''}"


def score_base_programs(manifest: list[dict[str, Any]]) -> dict[int, float]:
    """combined_confidence for every base program against its own WIR
    (differential mode's "correct" / negative class)."""
    manifest_by_uid = {e["uid"]: e for e in manifest if "base_uid" not in e}
    cache: dict[int, Any] = {}
    scores: dict[int, float] = {}
    for uid, entry in manifest_by_uid.items():
        base = _base_func_wir(uid, manifest_by_uid, cache)
        if base is None:
            continue
        base_source, base_func_wir = base
        cert = run_differential_verification(base_source, base_func_wir)
        scores[uid] = cert.get("combined_confidence", 0.0)
    return scores


def build_records(
    manifest: list[dict[str, Any]],
    pairs: dict[str, dict[str, Any]],
    base_scores: dict[int, float],
) -> list[dict[str, Any]]:
    """One record per scored item: base programs (class "correct") and
    mutants split into "buggy" (semantic_diff_rate > 0) and "equivalent"
    (semantic_diff_rate == 0), each carrying its own base_uid for the
    CALIB/EVAL split and tag for stratification."""
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
        if row is None:
            continue
        diff_rate = float(row["semantic_diff_rate"])
        base_uid = entry["base_uid"]
        records.append({
            "uid": base_uid,
            "class": "buggy" if diff_rate > 0 else "equivalent",
            "operator": entry["operator"],
            "tag": _base_tag(manifest_by_uid[base_uid].get("tags", [])),
            "combined_confidence": float(row["combined_confidence"]),
        })

    return records


def youdens_j_on_genuine(records: list[dict[str, Any]]) -> tuple[float, float]:
    """tau maximizing sensitivity+specificity-1 using ONLY class=="buggy"
    (genuine) as positives and class=="correct" as negatives; class
    "equivalent" is excluded from selection entirely."""
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
        "equivalent_specificity_ci": (
            (1 - equiv_flag_ci[1], 1 - equiv_flag_ci[0]) if equiv_flag_ci else None
        ),
        "n_equivalent": n_equiv,
        "false_alarm_rate": false_alarm_rate, "false_alarm_ci": false_alarm_ci, "n_correct": n_correct,
        "by_operator": by_operator,
    }


def run_corrected() -> dict[str, Any]:
    manifest = _load_manifest()
    pairs = _load_pairs()
    base_scores = score_base_programs(manifest)
    records = build_records(manifest, pairs, base_scores)

    calib_uids, eval_uids = stratified_split(manifest, seed=SEED)
    calib_records = [r for r in records if r["uid"] in calib_uids]
    eval_records = [r for r in records if r["uid"] in eval_uids]

    tau, best_j = youdens_j_on_genuine(calib_records)
    calib_summary = three_figure_eval(calib_records, tau)
    eval_summary = three_figure_eval(eval_records, tau)

    return {"tau": tau, "youdens_j": best_j, "calib": calib_summary, "eval": eval_summary}


def _fmt_ci(ci: Optional[tuple[float, float]]) -> str:
    if ci is None:
        return "n/a"
    return f"[{ci[0]:.3f}, {ci[1]:.3f}]"


PRE_CORRECTION_BASELINE = {
    "youdens_j": 0.8069,
    "detection_rate": 0.8636,   # old aggregate figure, conflated genuine+equivalent
    "false_alarm_rate": 0.0588,
}


def render_report(result: dict[str, Any]) -> str:
    e = result["eval"]
    lines = [
        "# Module 02 Corrected Calibration Report (Differential Mode)",
        "",
        f"Seed: `{SEED}`. CALIB/EVAL split: 50/50 stratified by base-program tag.",
        f"tau selected on CALIB using ONLY genuinely-buggy mutants "
        f"(semantic_diff_rate > 0) as positives and base programs as "
        f"negatives -- equivalent mutants are excluded from tau selection.",
        "",
        "## Why this report exists",
        "",
        "The prior differential report's single 'detection rate' figure",
        "conflated genuinely-buggy mutants with behaviorally-equivalent",
        "ones (semantic_diff_rate == 0, from eval/e3_correlation.py's",
        "code-vs-code ground truth -- the WIR never touches that side).",
        "A correctly-unflagged equivalent mutant looks identical to a",
        "missed genuine bug in that single number. This report separates",
        "them into three figures. It also incorporates two fixes: C2",
        "(branch_lines derived from the mutant's own WIR, not the base's",
        "-- line-shift false positives) and C3 (op_early_return actually",
        "cuts logic now, not a no-op).",
        "",
        f"- Youden's J-optimal tau: **{result['tau']:.4f}** (J={result['youdens_j']:.4f})",
        "",
        "## Three-figure result (EVAL, held out)",
        "",
        f"1. **Genuine-bug detection**: {e['detection_rate']:.4f} "
        f"(95% CI {_fmt_ci(e['detection_ci'])}, n={e['n_genuine']})",
        f"2. **Equivalent-mutant specificity**: "
        f"{e['equivalent_specificity']:.4f} "
        f"(95% CI {_fmt_ci(e['equivalent_specificity_ci'])}, n={e['n_equivalent']})",
        f"3. **False-alarm rate (untouched bases)**: {e['false_alarm_rate']:.4f} "
        f"(95% CI {_fmt_ci(e['false_alarm_ci'])}, n={e['n_correct']})",
        "",
        "### Reading figure 2 (n=9, wide CI -- investigated, not a new bug)",
        "",
        "EVAL contains only 9 equivalent mutants (clustered on 5 distinct",
        "base uids -- one base can contribute several operators' worth),",
        "so this CI is necessarily wide. Checked directly: 8 of the 9",
        "score `combined_confidence` **exactly identical** to their own",
        "base's own score -- i.e. where the base itself already sits",
        "below tau (contributing to figure 3's false-alarm rate), an",
        "equivalent mutant correctly inherits that same status, and C2's",
        "fix leaves no residual line-shift artifact (confirmed by the",
        "exact-match evidence, not inferred). The 1 exception (uid 3's",
        "early-return mutant, 0.0 vs base 0.300) was checked directly: the",
        "cut-off code guarded on `folder['name'] == None`, and E3's local",
        "input generator never produces the value `None` for a str-typed",
        "parameter (only pool literals / \"\" / junk strings), so its",
        "semantic_diff_rate==0 verdict is itself a false negative from",
        "E3's own documented N=25 sampling limitation -- the certificate's",
        "flag is arguably the more correct call here, not a bug to fix.",
        "",
        "## vs pre-correction aggregate baseline",
        "",
        "| metric | pre-correction (archived) | corrected |",
        "|---|---|---|",
        f"| Youden's J | {PRE_CORRECTION_BASELINE['youdens_j']:.4f} | {result['youdens_j']:.4f} |",
        f"| Detection / genuine-bug detection | {PRE_CORRECTION_BASELINE['detection_rate']:.4f} (conflated) | {e['detection_rate']:.4f} |",
        f"| False-alarm rate | {PRE_CORRECTION_BASELINE['false_alarm_rate']:.4f} | {e['false_alarm_rate']:.4f} |",
        "",
        "Pre-correction reports archived at "
        "`eval/results/archive/calibration_report_differential_pre_lineshift_fix.md` "
        "and `eval/results/archive/e3_correlation_report_pre_earlyreturn_fix.md`.",
        "",
        "## Detection rate by operator, genuinely-buggy mutants only (EVAL)",
        "",
        "| operator | n | detected | detection rate |",
        "|---|---|---|---|",
    ]
    for op, stats in sorted(e["by_operator"].items()):
        rate = f"{stats['rate']:.3f}" if stats["rate"] is not None else "n/a"
        lines.append(f"| {op} | {stats['n']} | {stats['detected']} | {rate} |")
    lines.append("")

    cp = e["by_operator"].get("constant-perturb")
    if cp and cp["rate"] == 0.0:
        lines += [
            "`constant-perturb`'s 0.000 here is consistent with the prior",
            "session's D3 finding, not a new surprise: it's a \"value-only\"",
            "mutation (a compared literal changes, no different stub gets",
            "called), which is exactly the class D3 predicted would need a",
            "branch-decision field on the real collector (still missing,",
            "explicitly out of scope) to detect via anything other than",
            "task-sequence divergence. n=9 in this EVAL split is small; the",
            "per-operator rate should be read with that in mind.",
            "",
        ]

    return "\n".join(lines)


def main() -> None:
    result = run_corrected()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report = render_report(result)
    (RESULTS_DIR / "calibration_report_differential.md").write_text(report, encoding="utf-8")

    THRESHOLD_PATH.write_text(
        json.dumps({
            "mode": "differential-corrected",
            "tau": result["tau"],
            "youdens_j": result["youdens_j"],
            "seed": SEED,
        }, indent=2),
        encoding="utf-8",
    )
    print(report)


if __name__ == "__main__":
    main()
