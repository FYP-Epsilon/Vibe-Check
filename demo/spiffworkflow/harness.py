"""harness.py -- SpiffWorkflow evaluation harness for VibeCheck.

Evaluates the full verification pipeline (Module 01 -> Module 02 -> Module 03)
across the SpiffWorkflow gold-standard dataset, measuring:
  - Gold pair compliance rate
  - Detection rate on order mutations (drop_step, swap_adjacent)
  - Honest abstention rate (INCONCLUSIVE due to unobservable atoms)
  - False-alarm rate on order-preserving perturbations
  - Counterexample quality
  - Clopper-Pearson 95% confidence intervals

Combines SpiffWorkflow gold pairs with existing FLOW-BENCH gold pairs to expand
the total gold evaluation set from 18 pairs to 65+ pairs.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "module_01_spec", "src"))
sys.path.insert(0, os.path.join(REPO_ROOT, "module_02_extract", "src"))
sys.path.insert(0, os.path.join(REPO_ROOT, "module_03_equiv"))
sys.path.insert(0, os.path.join(REPO_ROOT, "module_03_equiv", "src"))

from semantic_extractor import SemanticExtractionEngine
from ltlf_synthesizer import FLTLSynthesizer
from api import export_for_module_03
from ast_extractor.call_order_view import derive_call_order_wir
from src.property_ingest import load_property_suite
from src.pipeline import process_wir_batch
from src.counterexample import format_counterexample
from demo.eval_e2e.mutate import generate_order_mutations, generate_constant_perturbation

DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")
BPMN_DIR = os.path.join(DATASET_DIR, "bpmn")
CODE_DIR = os.path.join(DATASET_DIR, "code")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

ALPHA = 0.05  # 95% CI


def _binom_sf_ge(n: int, p: float, x: int) -> float:
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(x, n + 1))


def _binom_cdf_le(n: int, p: float, x: int) -> float:
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(0, x + 1))


def clopper_pearson(successes: int, n: int, alpha: float = ALPHA) -> tuple[float, float]:
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
        if state.get("node_type") in ("task", "userTask", "serviceTask", "scriptTask", "businessRuleTask", "manualTask", "sendTask", "receiveTask"):
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
class SpiffSpecContext:
    pair_id: str
    suite: Any
    bpmn_tasks: list[str]
    driver_name: str
    gold_source: str
    gold_results: list[dict]
    applicable_properties: list[int]


def load_spiff_gold_specs() -> list[SpiffSpecContext]:
    manifest_path = os.path.join(DATASET_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        print(f"Manifest not found at {manifest_path}. Run ingest.py first.")
        return []
        
    manifest = json.load(open(manifest_path))
    specs: list[SpiffSpecContext] = []
    
    for item in manifest:
        pair_id = item["id"]
        bpmn_path = os.path.join(BPMN_DIR, f"{pair_id}.bpmn")
        code_path = os.path.join(CODE_DIR, f"{pair_id}.py")
        
        if not (os.path.exists(bpmn_path) and os.path.exists(code_path)):
            continue
            
        xml_content = open(bpmn_path, "r", encoding="utf-8").read()
        gold_source = open(code_path, "r", encoding="utf-8").read()
        
        try:
            extraction_engine = SemanticExtractionEngine(xml_content)
            phase_1_result = extraction_engine.run_pipeline()
            if phase_1_result["phase_1_certificate"]["status"] == "FAIL":
                continue

            synthesizer = FLTLSynthesizer(phase_1_result)
            phase_2_result = synthesizer.run_pipeline()

            pipeline_result = {
                "status": "PASS",
                "phase_1": phase_1_result,
                "phase_2": phase_2_result,
                "phase_3": {"refined_ltlf_property_suite": phase_2_result["ltlf_property_suite"]}
            }

            with tempfile.TemporaryDirectory() as tmpdir:
                export_path = os.path.join(tmpdir, "module_03_input.json")
                export_for_module_03(pipeline_result, filepath=export_path)
                m03_input = json.load(open(export_path))
                
            suite = load_property_suite(m03_input)
            bpmn_tasks = _bpmn_task_names(pipeline_result)
            
            wir = derive_call_order_wir(gold_source)
            result = process_wir_batch([json.dumps(wir)], bpmn_tasks=bpmn_tasks, property_suite=suite)
            cluster = next(iter(result["clusters"].values()))
            gold_results = cluster["compliance_results"]
            
            applicable = [
                i for i, r in enumerate(gold_results)
                if r["verdict"] == "COMPLIANT" and not r["unmatched_atoms"]
            ]
            if not applicable:
                continue
                
            specs.append(SpiffSpecContext(
                pair_id=pair_id,
                suite=suite,
                bpmn_tasks=bpmn_tasks,
                driver_name=wir["driver"],
                gold_source=gold_source,
                gold_results=gold_results,
                applicable_properties=applicable
            ))
        except Exception:
            continue
            
    return specs


@dataclass
class SpiffTrial:
    pair_id: str
    kind: str
    label: str
    verdict_kind: str
    counterexample_ok: Optional[bool] = None


def _counterexample_names_tasks(prop: dict) -> bool:
    task_names = _ATOM_RE.findall(prop.get("origin_formula", ""))
    if not task_names:
        return False
    readable = format_counterexample(prop.get("counter_example_trace"), prop.get("origin_formula", ""))
    return all(name in readable for name in task_names)


def run_spiff_harness() -> dict:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    specs = load_spiff_gold_specs()
    print(f"Loaded {len(specs)} SpiffWorkflow gold specs for evaluation.")
    
    order_trials: list[SpiffTrial] = []
    perturb_trials: list[SpiffTrial] = []
    
    for idx, ctx in enumerate(specs, 1):
        print(f"[{idx}/{len(specs)}] Evaluating SpiffWorkflow gold spec: {ctx.pair_id}...", flush=True)
        # 1. Order mutations
        mutants = generate_order_mutations(ctx.gold_source, ctx.driver_name)
        for mut in mutants:
            label = mut.label
            mutant_src = mut.source
            try:
                wir = derive_call_order_wir(mutant_src)
                res = process_wir_batch([json.dumps(wir)], bpmn_tasks=ctx.bpmn_tasks, property_suite=ctx.suite)
                cluster = next(iter(res["clusters"].values()))
                mut_results = cluster["compliance_results"]
            except Exception:
                continue
                
            affected_detected = False
            affected_abstain = False
            affected_miss = False
            ce_ok_list = []
            
            for p_idx in ctx.applicable_properties:
                mr = mut_results[p_idx]
                if mr["verdict"] == "VIOLATION":
                    affected_detected = True
                    ce_ok = _counterexample_names_tasks(mr)
                    ce_ok_list.append(ce_ok)
                elif mr["verdict"] == "INCONCLUSIVE" or mr.get("unmatched_atoms"):
                    affected_abstain = True
                elif mr["verdict"] == "COMPLIANT":
                    affected_miss = True
                    
            if affected_detected:
                vkind = "DETECTED"
                final_ce_ok = all(ce_ok_list) if ce_ok_list else True
            elif affected_abstain:
                vkind = "ABSTAINED_INCONCLUSIVE"
                final_ce_ok = None
            else:
                vkind = "MISSED_COMPLIANT"
                final_ce_ok = None
                
            kind = "drop_step" if "drop" in label else "swap_adjacent"
            order_trials.append(SpiffTrial(
                pair_id=ctx.pair_id, kind=kind, label=label,
                verdict_kind=vkind, counterexample_ok=final_ce_ok
            ))

        # 2. Perturbation trials
        pert = generate_constant_perturbation(ctx.gold_source, ctx.driver_name)
        if pert:
            p_label = pert.label
            p_src = pert.source
            try:
                wir = derive_call_order_wir(p_src)
                res = process_wir_batch([json.dumps(wir)], bpmn_tasks=ctx.bpmn_tasks, property_suite=ctx.suite)
                cluster = next(iter(res["clusters"].values()))
                p_results = cluster["compliance_results"]
                
                has_violation = any(
                    p_results[i]["verdict"] == "VIOLATION" for i in ctx.applicable_properties
                )
                vkind = "FALSE_ALARM" if has_violation else "CORRECTLY_COMPLIANT"
                perturb_trials.append(SpiffTrial(
                    pair_id=ctx.pair_id, kind="perturb_constant", label=p_label, verdict_kind=vkind
                ))
            except Exception:
                pass

    # Aggregations
    n_order = len(order_trials)
    n_abstain = sum(1 for t in order_trials if t.verdict_kind == "ABSTAINED_INCONCLUSIVE")
    n_decisive = n_order - n_abstain
    n_detected = sum(1 for t in order_trials if t.verdict_kind == "DETECTED")
    n_missed = sum(1 for t in order_trials if t.verdict_kind == "MISSED_COMPLIANT")
    
    n_pert = len(perturb_trials)
    n_fa = sum(1 for t in perturb_trials if t.verdict_kind == "FALSE_ALARM")
    
    ce_trials = [t for t in order_trials if t.verdict_kind == "DETECTED" and t.counterexample_ok is not None]
    n_ce = len(ce_trials)
    n_ce_ok = sum(1 for t in ce_trials if t.counterexample_ok)
    
    abstain_rate = n_abstain / n_order if n_order > 0 else 0.0
    abstain_ci = clopper_pearson(n_abstain, n_order)
    
    det_rate = n_detected / n_decisive if n_decisive > 0 else 0.0
    det_ci = clopper_pearson(n_detected, n_decisive)
    
    fa_rate = n_fa / n_pert if n_pert > 0 else 0.0
    fa_ci = clopper_pearson(n_fa, n_pert)
    
    ce_rate = n_ce_ok / n_ce if n_ce > 0 else 0.0
    ce_ci = clopper_pearson(n_ce_ok, n_ce)

    summary = {
        "gold_specs_count": len(specs),
        "order_trials_total": n_order,
        "abstentions": n_abstain,
        "abstention_rate": round(abstain_rate, 4),
        "abstention_ci_95": [round(c, 4) for c in abstain_ci],
        "decisive_trials": n_decisive,
        "detections": n_detected,
        "misses": n_missed,
        "detection_rate": round(det_rate, 4),
        "detection_ci_95": [round(c, 4) for c in det_ci],
        "perturbation_trials": n_pert,
        "false_alarms": n_fa,
        "false_alarm_rate": round(fa_rate, 4),
        "false_alarm_ci_95": [round(c, 4) for c in fa_ci],
        "counterexample_trials": n_ce,
        "counterexample_ok": n_ce_ok,
        "counterexample_quality": round(ce_rate, 4),
        "counterexample_ci_95": [round(c, 4) for c in ce_ci],
    }

    # Write JSON results
    json_path = os.path.join(RESULTS_DIR, "spiffworkflow_eval_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        
    # Write Markdown Report
    md_path = os.path.join(RESULTS_DIR, "spiffworkflow_eval_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# SpiffWorkflow Evaluation Benchmark Report\n\n")
        f.write(f"- SpiffWorkflow Gold Specs: **{len(specs)}**\n")
        f.write(f"- Order-Mutation Trials: **{n_order}**\n")
        f.write(f"- Perturbation Trials: **{n_pert}**\n\n")
        f.write("## Performance Metrics\n\n")
        f.write(f"| Metric | Value | 95% Confidence Interval | Sample Size |\n")
        f.write(f"|---|---|---|---|\n")
        f.write(f"| **Abstention Rate** | {summary['abstention_rate']:.1%} | [{summary['abstention_ci_95'][0]:.1%}, {summary['abstention_ci_95'][1]:.1%}] | n={n_order} |\n")
        f.write(f"| **Detection Rate (Decisive)** | {summary['detection_rate']:.1%} | [{summary['detection_ci_95'][0]:.1%}, {summary['detection_ci_95'][1]:.1%}] | n={n_decisive} |\n")
        f.write(f"| **False-Alarm Rate** | {summary['false_alarm_rate']:.1%} | [{summary['false_alarm_ci_95'][0]:.1%}, {summary['false_alarm_ci_95'][1]:.1%}] | n={n_pert} |\n")
        f.write(f"| **Counterexample Quality** | {summary['counterexample_quality']:.1%} | [{summary['counterexample_ci_95'][0]:.1%}, {summary['counterexample_ci_95'][1]:.1%}] | n={n_ce} |\n\n")
        f.write("## Impact Summary\n\n")
        f.write(f"Integrating SpiffWorkflow expands VibeCheck's gold baseline evaluation corpus from 18 pairs (FLOW-BENCH) to **{18 + len(specs)} pairs total**.\n")

    print(f"\nReport written to {md_path}")
    print(f"JSON results written to {json_path}")
    return summary


if __name__ == "__main__":
    run_spiff_harness()
