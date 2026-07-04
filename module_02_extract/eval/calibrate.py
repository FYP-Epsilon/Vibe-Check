"""calibrate.py -- calibration runner for the Module 02 verification pipeline.

Splits the FLOW-BENCH-derived corpus (label "correct") and its mutants
(label "buggy") into CALIB/EVAL sets -- 50/50, stratified by the base
program's semantic tag, fixed seed -- runs every program through the real
verification pipeline, picks a decision threshold tau on CALIB by
maximizing Youden's J on the combined_confidence ROC curve, then reports
detection rate (recall on buggy) and false-alarm rate (1 - specificity on
correct) on the held-out EVAL set with exact Clopper-Pearson binomial
confidence intervals. No scipy/numpy dependency: the binomial CDF is
computed exactly via math.comb and inverted by bisection.

Two modes (--mode):

  self (legacy)   -- run mutants through the ordinary /verify pipeline.
                      V1's oracle is a WIR *re-derived from the mutant
                      itself*, so it cannot distinguish a mutant from its
                      base program (see round3_verified_findings "Round-3b").
                      Preserved as a documented negative finding --
                      NEVER regenerate calibration_report.md automatically
                      from a differential run.
  differential    -- (default) run each mutant's compiled code against the
                      *base* program's WIR as the V1/V2 oracle
                      (run_v1_pipeline(source=mutant, wir=base_func_wir)).
                      This is the actual bug detector; V2 in this mode
                      contributes spec-path coverage, not detection --
                      see run_differential_verification's docstring.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path
from typing import Any, Optional

EVAL_DIR = Path(__file__).resolve().parent
MODULE02_DIR = EVAL_DIR.parent
sys.path.insert(0, str(MODULE02_DIR / "src"))

from main import (  # noqa: E402
    _run_verification, _derive_v1_params, _derive_initial_inputs,
    _select_entry_function, _derive_task_patterns, SAFE_BUILTINS,
)
from ast_extractor import run_v3_pipeline  # noqa: E402
from z3_sym_engine import run_v2_pipeline  # noqa: E402
from dynamic_tracer import run_v1_pipeline, MultiModalCertificateComposer  # noqa: E402
import ast  # noqa: E402

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

def _base_func_wir(base_uid: int, manifest_by_uid: dict[int, dict[str, Any]],
                    cache: dict[int, tuple[str, dict[str, Any]]]) -> Optional[tuple[str, dict[str, Any]]]:
    """(base_source, base WIR for its first function), cached per base_uid
    so N mutants sharing one base don't re-extract its WIR N times."""
    if base_uid in cache:
        return cache[base_uid]
    base_entry = manifest_by_uid.get(base_uid)
    if base_entry is None:
        return None
    base_path = EVAL_DIR / base_entry["source_file"]
    if not base_path.exists():
        return None
    base_source = base_path.read_text(encoding="utf-8")
    base_wir = run_v3_pipeline(base_source)
    functions = base_wir.get("functions", {})
    if not functions:
        return None
    result = (base_source, functions[_select_entry_function(functions)])
    cache[base_uid] = result
    return result


def run_differential_verification(mutant_source: str, base_func_wir: dict[str, Any]) -> dict[str, Any]:
    """
    Verify *mutant_source* against the *base* program's WIR instead of a
    WIR re-derived from the mutant itself.

    V3 still runs on the mutant standalone (extraction fidelity is a
    property of the mutant's own syntax, independent of any oracle) and
    gates the result exactly as in self-mode. V1 is the actual
    differential detector: its "expected" trace now comes from the base
    program's control flow, so a mutation that changes actual behavior
    (dropped step, reordered step, flipped guard direction) diverges from
    an oracle that no longer matches. V2 in this mode explores the base
    program's *symbolic path structure* while concretely executing the
    mutant -- it has no actual/expected comparator of its own, so it
    contributes spec-path coverage statistics, not detection.
    """
    wir = run_v3_pipeline(mutant_source)
    v3_cert = wir.get("certificate", {})

    functions = wir.get("functions", {})
    if not functions:
        return {"combined_confidence": 0.0, "passed": False, "message": "no functions in mutant"}
    function_name = _select_entry_function(functions)

    local_env: dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
    try:
        exec(compile(mutant_source, "<string>", "exec"), local_env)
        func_obj = local_env[function_name]
    except Exception as e:
        return {"combined_confidence": 0.0, "passed": False, "message": f"mutant failed to compile/exec: {e}"}

    mutant_tree = ast.parse(mutant_source)
    v1_params = _derive_v1_params(base_func_wir)
    initial_inputs = _derive_initial_inputs(mutant_tree, func_obj)

    v1_cert = run_v1_pipeline(
        source=mutant_source,
        function_name=function_name,
        wir=base_func_wir,
        task_patterns=_derive_task_patterns(mutant_tree, function_name),
        branch_lines=v1_params["branch_lines"],
        control_variables=v1_params["control_variables"],
        state_variables=v1_params["state_variables"] or None,
        n_runs=10,
        seed=42,
        compiled_ns=local_env,
    )

    v2_result = run_v2_pipeline(
        source=mutant_source,
        function_name=function_name,
        initial_inputs=initial_inputs,
        max_k=3,
        query_budget=20,
        compiled_ns=local_env,
        wir=base_func_wir,
    )
    v2_cert = v2_result["certificate"]

    composer = MultiModalCertificateComposer()
    return composer.compose(v1_cert, v2_cert, v3_cert)


def run_pipeline_on_manifest(
    manifest: list[dict[str, Any]],
    mode: str = "differential",
    manifest_by_uid: Optional[dict[int, dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    """Run every runnable manifest entry through the chosen mode's pipeline."""
    records: list[dict[str, Any]] = []
    wir_cache: dict[int, tuple[str, dict[str, Any]]] = {}
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

        if mode == "self":
            cert = _run_verification(source)
        else:
            base_uid = _uid_for(entry)
            base = _base_func_wir(base_uid, manifest_by_uid or {}, wir_cache)
            if base is None:
                continue
            _, base_func_wir = base
            cert = run_differential_verification(source, base_func_wir)

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


def render_report(calib_summary: dict[str, Any], eval_summary: dict[str, Any], seed: int, mode: str = "differential") -> str:
    title = "Differential-Mode" if mode == "differential" else "Self-Mode"
    lines = [
        f"# Module 02 Calibration Report ({title})",
        "",
        f"Mode: `{mode}`. Seed: `{seed}`. CALIB/EVAL split: 50/50 stratified by base-program tag.",
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

    if mode == "differential":
        lines.extend([
            "## Known limitations (why detection is weak, not tuned away)",
            "",
            "Detection rate (0.43) and false-alarm rate (0.39) are close to each",
            "other -- this is a near-coin-flip signal, not a working detector.",
            "Two independent, verified causes, neither fixed in this session:",
            "",
            "1. **The reference interpreter cannot execute task-API calls.**",
            "   `WIRReferenceInterpreter._exec_stmt` runs "
            "`exec(stmt, {\"__builtins__\": {}}, state)` -- no access to the",
            "   compiled stub defs, so any assignment that calls a user-defined",
            "   function (e.g. `incident = ServiceNow_..._incident()`) silently",
            "   fails and never populates `state`. Every guard reading that",
            "   variable then falls to its permissive-False default, and any",
            "   for-loop over its result gets an empty iterable. This holds for",
            "   BOTH self-mode and differential-mode WIRs -- switching the",
            "   oracle to the base program's WIR (this session's fix) does not",
            "   help, because the base program's own reference execution is",
            "   equally broken. Confirmed directly: base program uid_4 scores",
            "   combined_confidence 0.0 under differential mode -- the",
            "   *correct* program fails its own differential check, so there is",
            "   no working baseline to separate mutants from.",
            "2. **Value-only mutations (negate-guard, boundary-shift,",
            "   constant-perturb) produce identical trace *shape*.** D3 made",
            "   branch-decision comparison possible when both sides carry",
            "   `taken_branch`, but the real actual-side collector never does",
            "   (collector.py has no decision field on branch_point events),",
            "   so this stays a no-op for real runs by design (see D3's commit).",
            "   Verified directly on a hand-crafted base/mutant pair with zero",
            "   function calls involved: identical combined_confidence on both.",
            "",
            "Per-operator numbers above should be read as noise from cause (1),",
            "not as evidence those operators are individually easier/harder to",
            "detect. Fixing cause (1) (giving the interpreter a real compiled",
            "namespace) is the next session's highest-priority item -- see",
            "session memory for the full layered diagnosis.",
        ])

    return "\n".join(lines)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=["self", "differential"], default="differential",
        help="self: mutant verified against its own re-derived WIR (documented "
             "negative finding, calibration_report.md). differential (default): "
             "mutant verified against its base program's WIR "
             "(calibration_report_differential.md).",
    )
    args = parser.parse_args()

    manifest = _load_manifest()
    manifest_by_uid = {e["uid"]: e for e in manifest if "base_uid" not in e}
    calib_uids, eval_uids = stratified_split(manifest, seed=SEED)

    calib_manifest = [e for e in manifest if _uid_for(e) in calib_uids]
    eval_manifest = [e for e in manifest if _uid_for(e) in eval_uids]

    calib_records = run_pipeline_on_manifest(calib_manifest, mode=args.mode, manifest_by_uid=manifest_by_uid)
    eval_records = run_pipeline_on_manifest(eval_manifest, mode=args.mode, manifest_by_uid=manifest_by_uid)

    tau, best_j = youdens_j_threshold(calib_records)
    calib_summary = evaluate_at_threshold(calib_records, tau)
    calib_summary["best_j"] = best_j
    eval_summary = evaluate_at_threshold(eval_records, tau)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report = render_report(calib_summary, eval_summary, SEED, mode=args.mode)

    if args.mode == "differential":
        # threshold.json is frozen from differential-mode CALIB only -- the
        # self-mode J=0 result is not a usable operating point.
        THRESHOLD_PATH.write_text(
            json.dumps({
                "mode": args.mode,
                "tau": tau,
                "youdens_j": best_j,
                "seed": SEED,
                "n_calib_positives": calib_summary["n_positives"],
                "n_calib_negatives": calib_summary["n_negatives"],
            }, indent=2),
            encoding="utf-8",
        )
        (RESULTS_DIR / "calibration_report_differential.md").write_text(report, encoding="utf-8")
    else:
        # Never overwrite the self-mode negative-finding report from a
        # differential run; only a self-mode run regenerates it.
        (RESULTS_DIR / "calibration_report.md").write_text(report, encoding="utf-8")

    print(report)


if __name__ == "__main__":
    main()
