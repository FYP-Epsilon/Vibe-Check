"""harness.py -- Next Steps.md item #7: full-pipeline (M01->M02->M03)
evaluation harness.

Extends module_02_extract/eval's mutation-based measurement methodology
(detection rate / false-alarm rate / Clopper-Pearson CIs, see calibrate.py)
to the whole conformance-checking pipeline, using the real FLOW-BENCH BPMN
specs and real LLM-generated implementations already in this repo
(flow-bench/data/context, module_02_extract/eval/variants/normalized).

Ground-truth provenance (read before trusting any number below):
FLOW-BENCH has no native correctness labels for its LLM implementations
(.claude/memory/flowbench_groundtruth_finding.md) -- there is no source of
"this real implementation is/isn't spec-conformant" to measure against
directly. This harness builds ground truth the same way module_02_extract's
own eval does: by injecting mutations of known, verifiable effect into a
real implementation already confirmed COMPLIANT end-to-end ("gold"), then
checking whether the pipeline's own verdict flips as the mutation's class
predicts. All rates below are therefore for *injected* defect classes, not
a measurement of real LLM implementations' actual conformance rate -- state
that caveat wherever these numbers are quoted.

Sample size: only 6 of the corpus's 48 (BPMN, real-implementation) pairs
have both >=1 conformance-checkable property AND >=1 real implementation
this harness can independently confirm end-to-end COMPLIANT to use as gold
(the 22-checkable-spec count itself is a further cut of a 48-not-101 count
-- see the module docstring's cross-reference to
flowbench_groundtruth_finding.md on why FLOW-BENCH's public "101" doesn't
survive contact with this project's own checkability gates). n=6 gold
specs is not enough for a tight interval; every rate below is reported
with its Clopper-Pearson 95% CI precisely so that is visible rather than
hidden behind a point estimate.

Usage::

    python -m demo.eval_e2e.harness
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any, Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "module_01_spec", "src"))
sys.path.insert(0, os.path.join(REPO_ROOT, "module_02_extract", "src"))
sys.path.insert(0, os.path.join(REPO_ROOT, "module_03_equiv"))
sys.path.insert(0, os.path.join(REPO_ROOT, "module_03_equiv", "src"))

from api import run_module_01_pipeline, export_for_module_03  # module_01_spec
from ast_extractor.call_order_view import derive_call_order_wir  # module_02_extract
from src.property_ingest import load_property_suite  # module_03_equiv
from src.pipeline import process_wir_batch, HAS_CPP_ENGINE  # module_03_equiv
from src.counterexample import format_counterexample  # module_03_equiv

from .mutate import generate_order_mutations, generate_constant_perturbation, call_sequence

CTX_DIR = os.path.join(REPO_ROOT, "flow-bench", "data", "context")
VAR_DIR = os.path.join(REPO_ROOT, "module_02_extract", "eval", "variants", "normalized")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

ALPHA = 0.05  # 95% confidence intervals

# Ported (not imported) from module_02_extract/eval/calibrate.py: importing
# it directly would drag in module_02_extract/src/main.py's whole import
# chain (z3_sym_engine uses Python 3.10+ `match` syntax), which conflicts
# with the Python-3.9-only compiled vibecheck_lifter this harness also
# needs in the same process. Same rationale as property_ingest.py's own
# ported-not-imported LTLf normalization.

def _binom_sf_ge(n: int, p: float, x: int) -> float:
    import math
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(x, n + 1))


def _binom_cdf_le(n: int, p: float, x: int) -> float:
    import math
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(0, x + 1))


def clopper_pearson(successes: int, n: int, alpha: float = ALPHA) -> tuple[float, float]:
    """Exact two-sided (1-alpha) binomial confidence interval, via bisection
    on the exact binomial CDF. Verbatim port of calibrate.py's own."""
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

_ATOM_RE = re.compile(r"(?:start|done)\(([^)]+)\)")


def _bpmn_task_names(pipeline_result: dict) -> list[str]:
    names: list[str] = []
    for state in pipeline_result["phase_1"]["semantic_graph"]["states"]:
        if state.get("node_type") in ("task", "userTask", "serviceTask"):
            for prop in state.get("atomic_propositions", []):
                m = _ATOM_RE.match(prop)
                if m:
                    names.append(m.group(1))
                    break
    seen: dict[str, None] = {}
    for n in names:
        seen.setdefault(n, None)
    return list(seen)


@dataclass
class SpecContext:
    """Everything needed to run process_wir_batch against this spec's
    property suite more than once (gold, then each mutant)."""
    uid: int
    suite: Any
    bpmn_tasks: list[str]
    driver_name: str
    gold_source: str
    gold_results: list[dict]           # process_wir_batch's compliance_results for gold
    applicable_properties: list[int]   # indices where gold is COMPLIANT with atoms fully matched


def discover_gold_specs() -> list[SpecContext]:
    """Every (BPMN spec, real LLM variant) pair with >=1 conformance-
    checkable property and >=1 real variant this harness independently
    confirms COMPLIANT end-to-end -- the only pairs usable as a mutation
    base. Not hardcoded: re-derived each run so this stays correct as the
    corpus changes."""
    uids = sorted(
        int(f.split("_")[1]) for f in os.listdir(CTX_DIR) if f.endswith("_context.bpmn")
    )
    variant_files = sorted(os.listdir(VAR_DIR))

    specs: list[SpecContext] = []
    for uid in uids:
        variants = [f for f in variant_files if re.match(rf"^{uid}__", f)]
        if not variants:
            continue

        bpmn_xml = open(os.path.join(CTX_DIR, f"uid_{uid}_context.bpmn")).read()
        try:
            pipeline_result = run_module_01_pipeline(bpmn_xml)
            with tempfile.TemporaryDirectory() as tmpdir:
                export_path = os.path.join(tmpdir, "module_03_input.json")
                export_for_module_03(pipeline_result, filepath=export_path)
                m03_input = json.load(open(export_path))
        except (ImportError, ModuleNotFoundError):
            # Not a per-spec skip: the environment itself is broken (e.g. the
            # Python-3.9-only compiled vibecheck_lifter unimportable under the
            # active interpreter). Letting this masquerade as "M01-ineligible
            # spec" is exactly what silently produced a 0-gold-spec report
            # instead of a crash -- so it must propagate.
            raise
        except Exception:
            continue  # M01-ineligible spec (not every BPMN file in this corpus survives M01's own pipeline)

        suite = load_property_suite(m03_input)
        checkable = suite.conformance_properties()
        if not checkable:
            continue

        bpmn_tasks = _bpmn_task_names(pipeline_result)

        for vf in variants:
            source = open(os.path.join(VAR_DIR, vf)).read()
            try:
                wir = derive_call_order_wir(source)
                result = process_wir_batch([json.dumps(wir)], bpmn_tasks=bpmn_tasks, property_suite=suite)
            except (ImportError, ModuleNotFoundError):
                raise  # environment-broken, not a per-variant skip -- see comment above
            except Exception:
                continue
            cluster = next(iter(result["clusters"].values()))
            gold_results = cluster["compliance_results"]
            verdicts = {r["verdict"] for r in gold_results}
            if "VIOLATION" in verdicts or "COMPLIANT" not in verdicts:
                continue  # not a clean end-to-end PASS -- not usable as gold

            applicable = [
                i for i, r in enumerate(gold_results)
                if r["verdict"] == "COMPLIANT" and not r["unmatched_atoms"]
            ]
            if not applicable:
                continue  # gold satisfies nothing with fully-matched atoms -- no property a mutation could break

            specs.append(SpecContext(
                uid=uid, suite=suite, bpmn_tasks=bpmn_tasks,
                driver_name=wir["driver"], gold_source=source,
                gold_results=gold_results, applicable_properties=applicable,
            ))
            break  # one gold variant per spec is enough

    return specs


@dataclass
class Trial:
    uid: int
    kind: str
    label: str
    # Order mutations (drop_step/swap_adjacent): one of "DETECTED",
    # "MISSED_COMPLIANT" (a genuine miss -- the mutation broke a property
    # gold satisfied, but the pipeline still says COMPLIANT), or
    # "ABSTAINED_INCONCLUSIVE" (the affected task's own atom became
    # unmatched, so the pipeline honestly declines to guess rather than
    # emitting a wrong verdict -- excluded from the detection-rate
    # denominator, reported separately; see harness.py's module docstring).
    # perturb_constant: "FALSE_ALARM" or "CORRECTLY_COMPLIANT".
    verdict_kind: str
    counterexample_ok: Optional[bool] = None  # only set when verdict_kind == "DETECTED"


def run_mutant(ctx: SpecContext, mutant_source: str) -> list[dict]:
    wir = derive_call_order_wir(mutant_source)
    result = process_wir_batch([json.dumps(wir)], bpmn_tasks=ctx.bpmn_tasks, property_suite=ctx.suite)
    cluster = next(iter(result["clusters"].values()))
    return cluster["compliance_results"]


def _counterexample_names_tasks(prop: dict) -> bool:
    """Does the rendered counterexample name every BPMN task this specific
    property's own formula references? Narrow, mechanical definition --
    not a subjective quality rubric (see harness.py's module docstring and
    the PR body for why this scope was chosen over a fuller rubric)."""
    task_names = _ATOM_RE.findall(prop["origin_formula"])
    if not task_names:
        return False
    readable = format_counterexample(prop["counter_example_trace"], prop["origin_formula"])
    return all(name in readable for name in task_names)


def evaluate_spec(ctx: SpecContext) -> tuple[list[Trial], list[str]]:
    """Returns (trials, skipped_log) -- skipped_log records mutation
    candidates discarded because they failed their own verification step
    (not a genuine violation / not actually order-preserving), so nothing
    is silently dropped from the eventual report."""
    trials: list[Trial] = []
    skipped: list[str] = []

    for mutation in generate_order_mutations(ctx.gold_source, ctx.driver_name):
        mutant_results = run_mutant(ctx, mutation.source)

        hit_idx = next(
            (i for i in ctx.applicable_properties
             if mutant_results[i]["verdict"] == "VIOLATION" and not mutant_results[i]["unmatched_atoms"]),
            None,
        )
        if hit_idx is not None:
            verdict_kind = "DETECTED"
            counterexample_ok = _counterexample_names_tasks(mutant_results[hit_idx])
        elif any(mutant_results[i]["unmatched_atoms"] for i in ctx.applicable_properties):
            # At least one applicable property lost an atom it could
            # previously observe -- the honest verdict is "can't tell",
            # not a wrong COMPLIANT. Checked, not assumed: found via the
            # first real run that this is common for drop_step and did
            # not always coincide with a genuine miss (see harness.py's
            # module docstring / the PR body for the corpus evidence).
            verdict_kind = "ABSTAINED_INCONCLUSIVE"
            counterexample_ok = None
        else:
            verdict_kind = "MISSED_COMPLIANT"
            counterexample_ok = None

        trials.append(Trial(
            uid=ctx.uid, kind=mutation.kind, label=mutation.label,
            verdict_kind=verdict_kind, counterexample_ok=counterexample_ok,
        ))

    perturbation = generate_constant_perturbation(ctx.gold_source, ctx.driver_name)
    if perturbation is None:
        skipped.append(f"uid {ctx.uid}: no eligible literal for perturb_constant")
    else:
        gold_seq = call_sequence(ctx.gold_source, ctx.driver_name)
        mutant_seq = call_sequence(perturbation.source, ctx.driver_name)
        if mutant_seq != gold_seq:
            skipped.append(
                f"uid {ctx.uid}: perturb_constant candidate changed call order "
                f"({gold_seq} -> {mutant_seq}) -- discarded, not order-preserving"
            )
        else:
            mutant_results = run_mutant(ctx, perturbation.source)
            false_alarmed = any(
                mutant_results[i]["verdict"] == "VIOLATION"
                for i in ctx.applicable_properties
            )
            trials.append(Trial(
                uid=ctx.uid, kind=perturbation.kind, label=perturbation.label,
                verdict_kind="FALSE_ALARM" if false_alarmed else "CORRECTLY_COMPLIANT",
            ))

    return trials, skipped


def _rate(k: int, n: int) -> tuple[Optional[float], Optional[tuple[float, float]]]:
    if n == 0:
        return None, None
    return k / n, clopper_pearson(k, n, ALPHA)


def run_harness() -> dict:
    if not HAS_CPP_ENGINE:
        raise RuntimeError(
            "vibecheck_lifter C++ module not available under this interpreter "
            f"({sys.executable}). It is a Python-3.9-only compiled extension "
            "(module_03_equiv/src/vibecheck_lifter.cpython-39-darwin.so) -- "
            "run this harness with a Python 3.9 interpreter that has it on "
            "the path, or rebuild it for the interpreter you're using (see "
            "module_03_equiv/CMakeLists.txt)."
        )
    specs = discover_gold_specs()
    if not specs:
        raise RuntimeError(
            "discover_gold_specs() found 0 usable specs -- refusing to write a "
            "report that would look like a valid (if bleak) measurement. This "
            "almost always means the environment is broken (e.g. running under "
            "the wrong Python interpreter for the compiled vibecheck_lifter "
            "extension), not that the corpus genuinely has no gold specs."
        )
    all_trials: list[Trial] = []
    all_skipped: list[str] = []
    for ctx in specs:
        trials, skipped = evaluate_spec(ctx)
        all_trials.extend(trials)
        all_skipped.extend(skipped)

    order_trials = [t for t in all_trials if t.kind in ("drop_step", "swap_adjacent")]
    perturb_trials = [t for t in all_trials if t.kind == "perturb_constant"]
    abstained_trials = [t for t in order_trials if t.verdict_kind == "ABSTAINED_INCONCLUSIVE"]
    # Detection rate is scoped to trials where the pipeline actually committed
    # to a verdict (DETECTED or MISSED_COMPLIANT) -- abstentions are excluded
    # from this denominator and reported as their own rate instead, since an
    # honest "can't tell" is not the same failure mode as a wrong COMPLIANT
    # (see evaluate_spec's classification and the module docstring).
    decisive_trials = [t for t in order_trials if t.verdict_kind != "ABSTAINED_INCONCLUSIVE"]
    detected_trials = [t for t in order_trials if t.verdict_kind == "DETECTED"]

    detection_rate, detection_ci = _rate(len(detected_trials), len(decisive_trials))
    abstention_rate, abstention_ci = _rate(len(abstained_trials), len(order_trials))
    false_alarm_rate, false_alarm_ci = _rate(
        sum(1 for t in perturb_trials if t.verdict_kind == "FALSE_ALARM"), len(perturb_trials)
    )
    counterexample_rate, counterexample_ci = _rate(
        sum(1 for t in detected_trials if t.counterexample_ok), len(detected_trials)
    )

    by_kind: dict[str, dict[str, int]] = {}
    for t in order_trials:
        d = by_kind.setdefault(t.kind, {"n": 0, "detected": 0, "missed": 0, "abstained": 0})
        d["n"] += 1
        d["detected"] += int(t.verdict_kind == "DETECTED")
        d["missed"] += int(t.verdict_kind == "MISSED_COMPLIANT")
        d["abstained"] += int(t.verdict_kind == "ABSTAINED_INCONCLUSIVE")

    return {
        "n_gold_specs": len(specs),
        "gold_uids": [c.uid for c in specs],
        "skipped": all_skipped,
        "detection_rate": detection_rate, "detection_ci": detection_ci, "n_decisive_trials": len(decisive_trials),
        "abstention_rate": abstention_rate, "abstention_ci": abstention_ci, "n_order_trials": len(order_trials),
        "by_mutation_kind": by_kind,
        "false_alarm_rate": false_alarm_rate, "false_alarm_ci": false_alarm_ci, "n_perturb_trials": len(perturb_trials),
        "counterexample_quality_rate": counterexample_rate, "counterexample_quality_ci": counterexample_ci,
        "n_detected": len(detected_trials),
        "trials": [
            {"uid": t.uid, "kind": t.kind, "label": t.label, "verdict_kind": t.verdict_kind,
             "counterexample_ok": t.counterexample_ok}
            for t in all_trials
        ],
    }


def _fmt_ci(ci: Optional[tuple[float, float]]) -> str:
    if ci is None:
        return "n/a"
    return f"[{ci[0]:.2f}, {ci[1]:.2f}]"


def write_report(summary: dict) -> str:
    lines = [
        "# E2E Evaluation Harness -- First Real Run",
        "",
        "Next Steps.md item #7. See `demo/eval_e2e/harness.py`'s module docstring",
        "for the full ground-truth-provenance and sample-size caveats before",
        "quoting any number below.",
        "",
        f"- Gold specs (checkable + >=1 confirmed-COMPLIANT real variant): "
        f"**{summary['n_gold_specs']}** (uids {summary['gold_uids']})",
        f"- Order-mutation trials (drop_step + swap_adjacent): {summary['n_order_trials']}",
        f"- Perturbation trials (order-preserving, verified): {summary['n_perturb_trials']}",
        "",
        "## Finding: task-drop defects are frequently unobservable, not just undetected",
        "",
        "Checked empirically (not assumed): a mutation that drops a task's own call "
        "entirely often makes that task's own atom vanish from what the code-side "
        "matcher can observe. When that happens, the pipeline correctly reports "
        "`INCONCLUSIVE` (it cannot claim an ordering result over a task it can no "
        "longer see happening) rather than a wrong `COMPLIANT`. This is honest "
        "behavior, not a detection failure -- so it is reported as its own rate, "
        "**excluded from the detection-rate denominator below**, rather than being "
        "silently averaged into a single misleading number. It does NOT happen for "
        "every drop -- when the dropped task isn't the one an applicable property "
        "actually references, the property stays (correctly or incorrectly) "
        "resolvable, so drop_step splits across all three outcomes; see the JSON "
        "results for the per-mutant breakdown.",
        "",
        f"**Abstention rate: {summary['abstention_rate']:.3f}** (95% CI "
        f"{_fmt_ci(summary['abstention_ci'])}, n={summary['n_order_trials']}) -- "
        f"fraction of order-mutation trials where the pipeline honestly abstained "
        f"(`INCONCLUSIVE`, atom unmatched) rather than committing to a verdict."
        if summary['abstention_rate'] is not None else "n/a (no order trials)",
        "",
        "## Detection rate",
        "",
        (f"**{summary['detection_rate']:.3f}** (95% CI {_fmt_ci(summary['detection_ci'])}, "
         f"n={summary['n_decisive_trials']}) -- of the order-mutation trials where the "
         f"pipeline committed to a verdict (excludes the abstentions above), the "
         f"fraction correctly flagged VIOLATION on the same property gold satisfied "
         f"with fully-matched atoms.")
        if summary['detection_rate'] is not None else "n/a (no decisive order trials)",
        "",
        "By mutation kind (n / detected / missed-as-compliant / abstained-inconclusive):",
        "",
    ]
    for kind, d in summary["by_mutation_kind"].items():
        lines.append(f"- `{kind}`: {d['n']} / {d['detected']} / {d['missed']} / {d['abstained']}")

    lines += [
        "",
        "## False-alarm rate",
        "",
        (f"**{summary['false_alarm_rate']:.3f}** (95% CI {_fmt_ci(summary['false_alarm_ci'])}, "
         f"n={summary['n_perturb_trials']}) -- fraction of verified order-preserving "
         f"literal perturbations the pipeline incorrectly flagged VIOLATION on. Note: "
         f"unmutated gold variants are deliberately excluded from this denominator -- "
         f"they were selected *because* they already verified COMPLIANT, so including "
         f"them would be circular; only the perturbation mutants (novel relative to "
         f"selection) are counted.")
        if summary['false_alarm_rate'] is not None else "n/a (no perturbation trials)",
        "",
        "## Counterexample quality",
        "",
        (f"**{summary['counterexample_quality_rate']:.3f}** (95% CI {_fmt_ci(summary['counterexample_quality_ci'])}, "
         f"n={summary['n_detected']}) -- of the mutations the pipeline correctly "
         f"detected, the fraction whose rendered counterexample named every BPMN "
         f"task the violated property's own formula references (a narrow, "
         f"mechanical yes/no -- not a subjective rubric; see the PR body for why "
         f"this scope was chosen).")
        if summary['counterexample_quality_rate'] is not None else "n/a (nothing detected)",
        "",
        "## Discarded candidates",
        "",
    ]
    if summary["skipped"]:
        lines += [f"- {s}" for s in summary["skipped"]]
    else:
        lines.append("(none)")

    return "\n".join(lines) + "\n"


def main() -> None:
    summary = run_harness()
    report = write_report(summary)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "e2e_eval_report.md"), "w") as f:
        f.write(report)
    with open(os.path.join(RESULTS_DIR, "e2e_eval_results.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(report)


if __name__ == "__main__":
    main()
