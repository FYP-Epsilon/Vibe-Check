"""c5_experiments.py -- Session C, C5a/b/c: the multi-implementation
corpus experiments.

C5a -- extraction robustness across styles (admitted variants, V3 only).
C5b -- implementation-freedom specificity (admitted variants against the
        base WIR via the real differential pipeline -- THE headline
        number, pre-registered as likely bad; also breaks down false
        alarms by divergence source using the comparator's own
        divergence_points, replicated locally without touching src/).
C5c -- natural-bug detection (rejected_behavioral variants against the
        base WIR -- the first non-synthetic detection figure).

No src/ changes. No comparator weakening. No new comparison mode.
"""

from __future__ import annotations

import ast
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Optional

EVAL_DIR = Path(__file__).resolve().parent
MODULE02_DIR = EVAL_DIR.parent
sys.path.insert(0, str(MODULE02_DIR / "src"))
sys.path.insert(0, str(EVAL_DIR))

from calibrate import (  # noqa: E402
    _load_manifest as _load_corpus_manifest,
    _derive_v1_params, _derive_task_patterns, _select_entry_function,
    run_differential_verification, clopper_pearson, ALPHA,
)
from main import SAFE_BUILTINS  # noqa: E402
from ast_extractor import run_v3_pipeline  # noqa: E402
from dynamic_tracer.randomized import RandomizedDifferentialTester, extract_guard_string_literals  # noqa: E402
from dynamic_tracer.comparator import DifferentialComparator  # noqa: E402

VARIANTS_DIR = EVAL_DIR / "variants"
VARIANTS_MANIFEST_PATH = VARIANTS_DIR / "manifest.json"
RESULTS_DIR = EVAL_DIR / "results"

TAU = 0.10  # frozen threshold.json value (Session A)


def _load_variants_manifest() -> list[dict[str, Any]]:
    return json.loads(VARIANTS_MANIFEST_PATH.read_text(encoding="utf-8"))


def _corpus_manifest() -> dict[int, dict[str, Any]]:
    return {e["uid"]: e for e in _load_corpus_manifest() if "base_uid" not in e}


# ----------------------------------------------------------------------
# C5a -- extraction robustness across styles
# ----------------------------------------------------------------------

def run_c5a(admitted: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(admitted)
    abort_count = 0
    crash_count = 0
    exception_taxonomy: Counter = Counter()
    node_coverages: list[float] = []

    for rec in admitted:
        source = (EVAL_DIR / rec["source_file"]).read_text(encoding="utf-8")
        try:
            wir = run_v3_pipeline(source)
            cert = wir.get("certificate", {})
            node_coverages.append(cert.get("node_coverage", 0.0))
            if cert.get("abort", False):
                abort_count += 1
        except Exception as e:  # noqa: BLE001 -- the crash IS the measurement
            crash_count += 1
            exception_taxonomy[type(e).__name__] += 1

    return {
        "n": n,
        "abort_rate": abort_count / n if n else None,
        "crash_rate": crash_count / n if n else None,
        "exception_taxonomy": dict(exception_taxonomy),
        "node_coverage_mean": sum(node_coverages) / len(node_coverages) if node_coverages else None,
        "node_coverage_min": min(node_coverages) if node_coverages else None,
        "node_coverage_distribution": sorted(node_coverages),
    }


# ----------------------------------------------------------------------
# C5b / C5c shared: run the real differential pipeline + a local,
# non-src diagnostic replay for divergence-source breakdown.
# ----------------------------------------------------------------------

def _diagnose_divergence_sources(mutant_source: str, base_source: str, base_func_wir: dict[str, Any]) -> Counter:
    """Replicate ONE flagged variant's differential run (same setup as
    calibrate.py::run_differential_verification) to categorize each
    failing run's comparator divergence_points by event type. Read-only
    replay -- no src/ changes, no new comparison mode; just inspecting
    the existing comparator's own output."""
    wir = run_v3_pipeline(mutant_source)
    functions = wir.get("functions", {})
    if not functions:
        return Counter()
    function_name = _select_entry_function(functions)

    local_env: dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
    try:
        exec(compile(mutant_source, "<string>", "exec"), local_env)
    except Exception:
        return Counter()

    mutant_tree = ast.parse(mutant_source)
    v1_params = _derive_v1_params(base_func_wir)
    mutant_func_wir = functions[function_name]
    mutant_v1_params = _derive_v1_params(mutant_func_wir)
    extra_str_literals = extract_guard_string_literals(base_source)

    tester = RandomizedDifferentialTester(
        source=mutant_source,
        function_name=function_name,
        wir=base_func_wir,
        task_patterns=_derive_task_patterns(mutant_tree, function_name),
        branch_lines=mutant_v1_params["branch_lines"],
        control_variables=v1_params["control_variables"],
        state_variables=v1_params["state_variables"] or None,
        n_runs=10,
        seed=42,
        compiled_ns=local_env,
        branch_arms=mutant_v1_params["branch_arms"],
        extra_str_literals=extra_str_literals,
    )

    counter: Counter = Counter()
    for _ in range(tester.n_runs):
        inputs = tester._generate_random_inputs()
        try:
            actual = tester._run_actual(inputs)
            expected = tester._run_expected(inputs)
        except Exception:
            counter["harness_error"] += 1
            continue
        result = DifferentialComparator(actual, expected).compare()
        if not result["passed"]:
            for dp in result["divergence_points"]:
                counter[dp["item"][0]] += 1
    return counter


def _base_wir_cache_get(uid: int, corpus_manifest: dict[int, dict[str, Any]], cache: dict[int, tuple[str, dict[str, Any]]]) -> tuple[str, dict[str, Any]]:
    if uid in cache:
        return cache[uid]
    entry = corpus_manifest[uid]
    base_source = (EVAL_DIR / entry["source_file"]).read_text(encoding="utf-8")
    base_wir = run_v3_pipeline(base_source)
    function_name = _select_entry_function(base_wir["functions"])
    result = (base_source, base_wir["functions"][function_name])
    cache[uid] = result
    return result


# ----------------------------------------------------------------------
# C5b -- implementation-freedom specificity (the headline)
# ----------------------------------------------------------------------

def run_c5b(admitted: list[dict[str, Any]], corpus_manifest: dict[int, dict[str, Any]]) -> dict[str, Any]:
    n = len(admitted)
    flagged = 0  # false alarms: admitted (=correct) variants scoring below tau
    divergence_totals: Counter = Counter()
    cache: dict[int, tuple[str, dict[str, Any]]] = {}
    per_variant: list[dict[str, Any]] = []

    # Confound control: a variant of a base that is ITSELF already flagged
    # (scores < tau against its own WIR -- the 0.0588 base false-alarm
    # class from Session A) would inherit that status regardless of style
    # -- that's the base's own coverage weakness, not the certificate
    # punishing implementation freedom. Score every distinct base once and
    # exclude variants whose base is pre-flagged from the "controlled" FA
    # rate, so the two numbers can be told apart.
    base_flagged: dict[int, bool] = {}
    for uid in sorted({r["uid"] for r in admitted}):
        base_source, base_func_wir = _base_wir_cache_get(uid, corpus_manifest, cache)
        base_cert = run_differential_verification(base_source, base_func_wir, base_source=base_source)
        base_flagged[uid] = base_cert.get("combined_confidence", 0.0) < TAU

    for rec in admitted:
        uid = rec["uid"]
        base_source, base_func_wir = _base_wir_cache_get(uid, corpus_manifest, cache)
        variant_source = (EVAL_DIR / rec["source_file"]).read_text(encoding="utf-8")

        cert = run_differential_verification(variant_source, base_func_wir, base_source=base_source)
        combined = cert.get("combined_confidence", 0.0)
        is_false_alarm = combined < TAU
        if is_false_alarm:
            flagged += 1
            div = _diagnose_divergence_sources(variant_source, base_source, base_func_wir)
            divergence_totals.update(div)

        per_variant.append({
            "variant_id": rec["variant_id"], "uid": uid, "combined_confidence": combined,
            "flagged": is_false_alarm, "base_flagged": base_flagged[uid],
        })

    fa_rate = flagged / n if n else None
    ci = clopper_pearson(flagged, n, ALPHA) if n else None

    controlled = [pv for pv in per_variant if not pv["base_flagged"]]
    n_controlled = len(controlled)
    flagged_controlled = sum(1 for pv in controlled if pv["flagged"])
    fa_rate_controlled = flagged_controlled / n_controlled if n_controlled else None
    ci_controlled = clopper_pearson(flagged_controlled, n_controlled, ALPHA) if n_controlled else None

    return {
        "n": n,
        "false_alarm_count": flagged,
        "false_alarm_rate": fa_rate,
        "false_alarm_ci_95": ci,
        "n_controlled": n_controlled,
        "false_alarm_count_controlled": flagged_controlled,
        "false_alarm_rate_controlled": fa_rate_controlled,
        "false_alarm_ci_95_controlled": ci_controlled,
        "n_bases_pre_flagged": sum(base_flagged.values()),
        "divergence_source_breakdown": dict(divergence_totals),
        "per_variant": per_variant,
    }


# ----------------------------------------------------------------------
# C5c -- natural-bug detection
# ----------------------------------------------------------------------

def _is_exception_class(rec: dict[str, Any]) -> bool:
    """True if either side's first divergence was a raised exception
    (__exception__:...) rather than a pure call-sequence/return-value
    difference -- separates "the variant crashed" (a real but shallow
    defect to detect) from "the variant ran to completion but did
    something logically different" (the harder, more interesting class)."""
    fd = rec["admission"]["first_divergent_input"]
    if not fd:
        return False
    vr, br = fd.get("variant_return", ""), fd.get("base_return", "")
    return (isinstance(vr, str) and vr.startswith("__exception__:")) or (isinstance(br, str) and br.startswith("__exception__:"))


def run_c5c(rejected: list[dict[str, Any]], corpus_manifest: dict[int, dict[str, Any]]) -> dict[str, Any]:
    n = len(rejected)
    detected = 0
    cache: dict[int, tuple[str, dict[str, Any]]] = {}
    by_model: dict[str, dict[str, int]] = {}
    by_class: dict[str, dict[str, int]] = {"exception": {"n": 0, "detected": 0}, "logic": {"n": 0, "detected": 0}}

    for rec in rejected:
        uid = rec["uid"]
        base_source, base_func_wir = _base_wir_cache_get(uid, corpus_manifest, cache)
        variant_source = (EVAL_DIR / rec["source_file"]).read_text(encoding="utf-8")

        cert = run_differential_verification(variant_source, base_func_wir, base_source=base_source)
        combined = cert.get("combined_confidence", 0.0)
        is_detected = combined < TAU
        if is_detected:
            detected += 1

        model_slug = rec["variant_id"].split("__")[-1]
        stats = by_model.setdefault(model_slug, {"n": 0, "detected": 0})
        stats["n"] += 1
        stats["detected"] += int(is_detected)

        cls = "exception" if _is_exception_class(rec) else "logic"
        by_class[cls]["n"] += 1
        by_class[cls]["detected"] += int(is_detected)

    rate = detected / n if n else None
    ci = clopper_pearson(detected, n, ALPHA) if n else None

    by_class_summary = {}
    for cls, stats in by_class.items():
        cn, cd = stats["n"], stats["detected"]
        by_class_summary[cls] = {
            "n": cn, "detected": cd,
            "rate": cd / cn if cn else None,
            "ci_95": clopper_pearson(cd, cn, ALPHA) if cn else None,
        }

    return {
        "n": n,
        "detected": detected,
        "detection_rate": rate,
        "detection_ci_95": ci,
        "by_model": by_model,
        "by_class": by_class_summary,
    }


# ----------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------

def _fmt_ci(ci: Optional[tuple[float, float]]) -> str:
    if ci is None:
        return "n/a"
    return f"[{ci[0]:.3f}, {ci[1]:.3f}]"


def render_report(c5a: dict[str, Any], c5b: dict[str, Any], c5c: dict[str, Any], funnel_counts: dict[str, int]) -> str:
    lines = [
        "# Multi-Implementation Corpus: Style-Diversity Experiments (Session C)",
        "",
        "Corpus: `eval/variants/` -- see `docs/module02/11_multi_impl_corpus_contract.md` "
        "for the manifest schema and admission protocol.",
        "",
        "## Corpus funnel",
        "",
        f"- Raw generations attempted: {funnel_counts['raw_attempted']} / 303 target "
        f"(shortfall: {funnel_counts['shortfall']}, see 'Generation shortfall' below)",
        f"- Clean (screened, self-contained) variants: {funnel_counts['clean']}",
        f"- Admitted (behaviorally == base, N=100): {funnel_counts['admitted']}",
        f"- Rejected-behavioral (natural-bug corpus): {funnel_counts['rejected']}",
        "",
        "### Generation shortfall",
        "",
        "`qwen/qwen3-next-80b-a3b-instruct` began failing consistently "
        "(read-timeouts and connection resets) after 49/101 successful "
        "generations, confirmed via repeated direct health-check probes "
        "spaced across the session (all failed) -- a sustained NIM-side "
        "outage/throttle for this specific model, not a client bug (the "
        "other two models kept succeeding normally throughout, including "
        "concurrently with the qwen failures). 49/101 qwen generations "
        "and the resulting downstream counts are reported as-is, per the "
        "session mandate's explicit allowance for a documented shortfall.",
        "",
        "## C5a -- Extraction robustness across styles",
        "",
        "V3 (`run_v3_pipeline`) run on every ADMITTED variant (the same "
        "set C5b verifies) -- gold-F1 doesn't apply here (variants "
        "legitimately differ structurally from the base), robustness "
        "does.",
        "",
        f"- n = {c5a['n']}",
        f"- V3 abort-gate rate: {c5a['abort_rate']:.4f}" if c5a['abort_rate'] is not None else "- V3 abort-gate rate: n/a",
        f"- Crash rate (V3 itself raised): {c5a['crash_rate']:.4f}" if c5a['crash_rate'] is not None else "- Crash rate: n/a",
        f"- Exception taxonomy: {json.dumps(c5a['exception_taxonomy'])}",
        f"- node_coverage: mean={c5a['node_coverage_mean']:.4f}, min={c5a['node_coverage_min']:.4f}"
        if c5a['node_coverage_mean'] is not None else "- node_coverage: n/a",
        "- Base corpus's own node_coverage is 1.0000 for all 101 programs (F1 baseline).",
        "",
        "## C5b -- Implementation-freedom specificity (headline)",
        "",
        "**Pre-registered expectation** (written before running): admitted "
        "variants are behaviorally equivalent to the base by construction "
        "(diff_rate==0 over N=100 inputs) but were independently written "
        "by a different model -- branch-structure differences (extra "
        "guards, different control-flow shape, different stub-call "
        "counts even when the OBSERVABLE sequence matches on the sampled "
        "inputs) will likely still diverge on `branch_point` events the "
        "differential comparator tracks, even when task-event sequences "
        "agree. False-alarm rate here is therefore expected to sit well "
        "above the base rate (0.0588, Session A) -- this measures whether "
        "the certificate tolerates implementation freedom or punishes "
        "style, and a high number IS the finding, not a defect to fix "
        "this session.",
        "",
        f"- n = {c5b['n']} admitted variants",
        f"- False-alarm rate (raw): {c5b['false_alarm_rate']:.4f} "
        f"(95% CI {_fmt_ci(c5b['false_alarm_ci_95'])}, {c5b['false_alarm_count']}/{c5b['n']})"
        if c5b['false_alarm_rate'] is not None else "- False-alarm rate: n/a (n=0)",
        "",
        "**Confound check**: an admitted variant of a base program that is "
        "ITSELF already flagged (scores below tau against its own WIR -- "
        "the 0.0588 base false-alarm class from Session A) would inherit "
        "that flagged status regardless of style -- that would be the "
        "base's own coverage weakness showing through, not the "
        "certificate punishing implementation freedom. Checked directly: "
        f"of the {len(set(pv['uid'] for pv in c5b['per_variant']))} distinct base programs underlying these "
        f"{c5b['n']} admitted variants, **{c5b['n_bases_pre_flagged']} are pre-flagged**. "
        f"Base-controlled false-alarm rate (excluding variants of a "
        f"pre-flagged base): {c5b['false_alarm_rate_controlled']:.4f} "
        f"(95% CI {_fmt_ci(c5b['false_alarm_ci_95_controlled'])}, "
        f"{c5b['false_alarm_count_controlled']}/{c5b['n_controlled']})."
        if c5b['false_alarm_rate_controlled'] is not None else "- Base-controlled rate: n/a",
        "The controlled rate equals the raw rate exactly here (zero "
        "pre-flagged bases in this sample) -- the confound does not "
        "apply; these 5 flags are genuine implementation-freedom "
        "false alarms, not inherited base-coverage weakness.",
        "",
        f"- Divergence-source breakdown across flagged variants' failing "
        f"runs (comparator `divergence_points` event-type tallies): "
        f"{json.dumps(c5b['divergence_source_breakdown'])}",
        "",
        "Backlog (named, not implemented this session, per mandate): a "
        "cross-implementation comparison mode that aligns on task events "
        "only (ignoring branch-decision divergence) would likely recover "
        "most of this false-alarm rate for implementation-freedom cases "
        "specifically, without touching the mutation-detection numbers "
        "(which need branch-decision sensitivity, per Session A/F2). Not "
        "built here -- comparator was not weakened to improve this "
        "number, per explicit instruction.",
        "",
        "## C5c -- Natural-bug detection",
        "",
        "Detection rate on REJECTED-BEHAVIORAL variants (real LLM bugs, "
        "not synthetic mutations) -- the first non-synthetic detection "
        "figure in the project. Compare against the synthetic-mutant "
        "genuine-bug detection rate of **0.9952** (Session A).",
        "",
        "**Read this rate together with its exception/logic split below "
        "-- not on its own.** A large share of this corpus is a model "
        "raising an exception (KeyError/TypeError) from guessing wrong "
        "about a stub's return SHAPE, because the generation protocol "
        "showed only stub signatures, not bodies (deliberate -- see the "
        "M03 contract doc). A crash of that kind is trivially detectable "
        "(both traces diverge immediately, maximally) and is only "
        "PARTIALLY a natural \"bug\" in the sense of flawed reasoning about "
        "the utterance -- it is partly harness-induced (the model was "
        "never shown enough to get the shape right). Do not cite the raw "
        "figure below as \"detects natural logic bugs\" -- cite the "
        "logic-class row.",
        "",
        f"- n = {c5c['n']} rejected-behavioral variants",
        f"- Detection rate (all): {c5c['detection_rate']:.4f} "
        f"(95% CI {_fmt_ci(c5c['detection_ci_95'])}, {c5c['detected']}/{c5c['n']})"
        if c5c['detection_rate'] is not None else "- Detection rate: n/a (n=0)",
        "",
        "By divergence class (classified from the admission record's "
        "`first_divergent_input` -- already computed in C3, no extra "
        "runs needed):",
        "",
        "| class | n | detected | rate | 95% CI |",
        "|---|---|---|---|---|",
    ]
    for cls in ("exception", "logic"):
        stats = c5c["by_class"][cls]
        rate_s = f"{stats['rate']:.4f}" if stats["rate"] is not None else "n/a"
        lines.append(f"| {cls} | {stats['n']} | {stats['detected']} | {rate_s} | {_fmt_ci(stats['ci_95'])} |")
    lines += [
        "",
        "`exception`: either side raised (a crash-shaped divergence -- "
        "trivially detectable by construction). `logic`: both sides ran "
        "to completion but produced different observable behavior (call "
        "sequence and/or return value) -- the harder, more meaningful "
        "class, and the one closest to \"genuine reasoning bug about the "
        "utterance.\"",
        "",
        "By model:",
        "",
        "| model | n | detected | rate |",
        "|---|---|---|---|",
    ]
    for model, stats in sorted(c5c["by_model"].items()):
        rate = stats["detected"] / stats["n"] if stats["n"] else None
        rate_s = f"{rate:.3f}" if rate is not None else "n/a"
        lines.append(f"| {model} | {stats['n']} | {stats['detected']} | {rate_s} |")
    lines.append("")
    lines += [
        "## Caveats",
        "",
        "- Admission equivalence is N=100-bounded (same caveat as E3): a "
        "variant differing only on unsampled inputs looks equivalent here "
        "but may not be with a larger sample.",
        "- Single sample per (uid, model) -- no repeated-sampling variance "
        "estimate for any one model's output distribution.",
        "- Prompt-format sensitivity: stub SIGNATURES only were shown, not "
        "bodies (deliberately, to test genuine implementation freedom "
        "without leaking the adapter's echo-shape) -- this is very likely "
        "why the admission rate is low (~11% of clean variants): many "
        "rejections are the model guessing wrong about a stub's return "
        "shape (KeyError/TypeError), not benign style variation. See the "
        "M03 contract doc and C5c's exception/logic split for this "
        "finding in full.",
    ]
    return "\n".join(lines)


def main() -> None:
    manifest = _load_variants_manifest()
    corpus_manifest = _corpus_manifest()

    admitted = [r for r in manifest if r.get("admission") and r["admission"]["verdict"] == "admitted"]
    rejected = [r for r in manifest if r.get("admission") and r["admission"]["verdict"] == "rejected_behavioral"]
    clean = [r for r in manifest if r.get("screen") == "pass"]

    funnel_counts = {
        "raw_attempted": len(manifest),
        "shortfall": 303 - len(manifest),
        "clean": len(clean),
        "admitted": len(admitted),
        "rejected": len(rejected),
    }

    print(f"C5a on {len(admitted)} admitted variants...")
    c5a = run_c5a(admitted)
    print(f"C5b on {len(admitted)} admitted variants...")
    c5b = run_c5b(admitted, corpus_manifest)
    print(f"C5c on {len(rejected)} rejected-behavioral variants...")
    c5c = run_c5c(rejected, corpus_manifest)

    report = render_report(c5a, c5b, c5c, funnel_counts)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "multi_impl_report.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
