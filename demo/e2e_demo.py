"""
demo/e2e_demo.py -- VibeCheck's first real end-to-end demo (Next Steps.md item #6).

BPMN spec -> Module 01 (LTLf property suite) -> Module 02 (call-order WIR) ->
Module 03 (Phase A-D conformance check) -> PASS/FAIL + readable counterexample,
run against a real LLM-generated FLOW-BENCH implementation.

This script deliberately crosses the M01/M02/M03 module boundary in one
process for convenience -- production does not: each module deploys as its
own container (see docker-compose.yml) with no access to the others' source,
and Module 03's property_ingest.py ports the LTLf normalization it needs
rather than importing Module 01's, precisely to preserve that independence.
This script is a demo harness sitting *outside* all three modules, not a
change to how any of them talk to each other in production.

Usage::

    python demo/e2e_demo.py

Requires the compiled ``vibecheck_lifter`` C++ extension (module_03_equiv) --
see module_03_equiv/CMakeLists.txt / Dockerfile for the build, or the
locally-built recipe in
"vibecheck-vault/Module 03 - Equivalence Engine/Bridge Investigation/CP1 Lifting-Scope Decision.md".
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "module_01_spec", "src"))
sys.path.insert(0, os.path.join(REPO_ROOT, "module_02_extract", "src"))
sys.path.insert(0, os.path.join(REPO_ROOT, "module_03_equiv"))
sys.path.insert(0, os.path.join(REPO_ROOT, "module_03_equiv", "src"))

from api import run_module_01_pipeline, export_for_module_03  # module_01_spec
from ast_extractor.call_order_view import derive_call_order_wir  # module_02_extract
from src.property_ingest import load_property_suite  # module_03_equiv
from src.pipeline import process_wir_batch  # module_03_equiv
from src.counterexample import format_counterexample  # module_03_equiv

CTX_DIR = os.path.join(REPO_ROOT, "flow-bench", "data", "context")
VAR_DIR = os.path.join(REPO_ROOT, "module_02_extract", "eval", "variants", "normalized")

_ATOM_RE = re.compile(r"(?:start|done)\(([^)]+)\)")
_VERDICT_ICON = {"COMPLIANT": "PASS", "VIOLATION": "FAIL", "INCONCLUSIVE": "?"}


def _bpmn_task_names(pipeline_result: dict) -> list[str]:
    """The task names Module 01's own semantic graph assigned -- the
    vocabulary process_wir_batch's semantic matching resolves code-side
    action text against."""
    names: list[str] = []
    for state in pipeline_result["phase_1"]["semantic_graph"]["states"]:
        if state.get("node_type") in ("task", "userTask", "serviceTask"):
            for prop in state.get("atomic_propositions", []):
                m = re.match(r"(?:start|done)\(([^)]+)\)", prop)
                if m:
                    names.append(m.group(1))
                    break
    seen: dict[str, None] = {}
    for n in names:
        seen.setdefault(n, None)
    return list(seen)


def check_variant(uid: int, variant_filename: str) -> dict:
    """
    Run one (BPMN spec, Python variant) pair through the full M01->M02->M03
    chain. Pure: no printing, so this is what both the CLI report below and
    test_e2e_demo.py's regression tests call directly.

    Returns a dict: {checkable, excluded, driver, results, n_compliant,
    n_violation, n_inconclusive, overall} where "results" is the list of
    per-property dicts process_wir_batch produces, each with an added
    "readable_counterexample" key (only non-empty for VIOLATION).
    """
    # ---- Module 01: BPMN -> LTLf property suite (the real export path) ----
    bpmn_xml = open(os.path.join(CTX_DIR, f"uid_{uid}_context.bpmn")).read()
    pipeline_result = run_module_01_pipeline(bpmn_xml)

    with tempfile.TemporaryDirectory() as tmpdir:
        export_path = os.path.join(tmpdir, "module_03_input.json")
        export_for_module_03(pipeline_result, filepath=export_path)
        m03_input = json.load(open(export_path))

    suite = load_property_suite(m03_input)
    checkable = suite.conformance_properties()
    if not checkable:
        return {
            "checkable": 0, "excluded": len(suite.excluded_properties()),
            "driver": None, "results": [],
            "n_compliant": 0, "n_violation": 0, "n_inconclusive": 0,
            "overall": "SKIPPED",
        }

    # ---- Module 02: Python source -> call-order-lifted WIR (the D2 fix) ----
    source = open(os.path.join(VAR_DIR, variant_filename)).read()
    call_order_wir = derive_call_order_wir(source)

    # ---- Module 03: Phase A-D conformance check ----
    bpmn_tasks = _bpmn_task_names(pipeline_result)
    result = process_wir_batch(
        [json.dumps(call_order_wir)],
        bpmn_tasks=bpmn_tasks,
        property_suite=suite,
    )
    cluster = next(iter(result["clusters"].values()))

    n_violation = n_compliant = n_inconclusive = 0
    results = []
    for r in cluster["compliance_results"]:
        verdict = r["verdict"]
        n_violation += verdict == "VIOLATION"
        n_compliant += verdict == "COMPLIANT"
        n_inconclusive += verdict == "INCONCLUSIVE"
        r = dict(r)
        r["readable_counterexample"] = (
            format_counterexample(r["counter_example_trace"], r["origin_formula"])
            if verdict == "VIOLATION" else ""
        )
        results.append(r)

    if n_violation:
        overall = "FAIL"
    elif n_compliant:
        overall = "PASS"
    else:
        overall = "INCONCLUSIVE"

    return {
        "checkable": len(checkable), "excluded": len(suite.excluded_properties()),
        "driver": call_order_wir.get("driver"), "results": results,
        "n_compliant": n_compliant, "n_violation": n_violation,
        "n_inconclusive": n_inconclusive, "overall": overall,
    }


def run_one(uid: int, variant_filename: str, label: str) -> None:
    print(f"\n{'=' * 70}\n{label}  (uid {uid}, {variant_filename})\n{'=' * 70}")

    report = check_variant(uid, variant_filename)
    print(f"Module 01: {report['checkable']} conformance-checkable propert"
          f"{'y' if report['checkable'] == 1 else 'ies'} "
          f"({report['excluded']} excluded -- see property_ingest.py's tier policy)")
    if report["overall"] == "SKIPPED":
        print("Nothing checkable for this spec -- skipping.")
        return

    print(f"Module 02: driver={report['driver']!r}")

    for r in report["results"]:
        verdict = r["verdict"]
        print(f"\n  [{_VERDICT_ICON.get(verdict, '?')}] {verdict}  ({r['tier']})")
        print(f"      property: {r['origin_formula']}")
        if verdict == "VIOLATION":
            print(f"      counterexample: {r['readable_counterexample']}")
        elif verdict == "INCONCLUSIVE":
            print(f"      reason: atom(s) not observed in the code's call sequence: {r['unmatched_atoms']}")

    print(f"\n  --- {report['n_compliant']} COMPLIANT, {report['n_violation']} VIOLATION, "
          f"{report['n_inconclusive']} INCONCLUSIVE ---")
    if report["overall"] == "FAIL":
        print(f"  OVERALL: FAIL -- {report['n_violation']} conformance "
              f"propert{'y' if report['n_violation'] == 1 else 'ies'} violated.")
    elif report["overall"] == "PASS":
        print("  OVERALL: PASS -- every checkable property that could be determined was satisfied.")
    else:
        print("  OVERALL: INCONCLUSIVE -- no property could be determined against this implementation.")


def main() -> None:
    # Two specs, stated plainly (see CP1 Lifting-Scope Decision.md): the real
    # 29-spec corpus has no single spec with both a genuinely COMPLIANT and a
    # genuinely VIOLATION-ing real LLM implementation, so this demo shows one
    # of each rather than hand-mutating a variant to force a pairing.
    run_one(44, "44__llama-3.1-8b.py", "FAIL case -- real ordering violations")
    run_one(77, "77__llama-3.1-8b.py", "PASS case -- real conformant implementation")


if __name__ == "__main__":
    main()
