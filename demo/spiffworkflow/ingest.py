"""ingest.py -- Fast, scalable ingestion of SpiffWorkflow tutorial and sample
process models. Uses Module 01 Phase 1 & Phase 2 LTLf synthesis to rapidly
build property suites, generates execution-order Python workflow implementations,
and validates clean COMPLIANT end-to-end verdicts (Modules 02 & 03).
"""

import os
import sys
import json
import re
import tempfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple, Any, Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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

SPIFF_CLI_DIR = "/tmp/spiff-example-cli/bpmn/tutorial"
SPIFF_MODELS_DIR = "/tmp/sample-process-models"
DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")
BPMN_OUT_DIR = os.path.join(DATASET_DIR, "bpmn")
CODE_OUT_DIR = os.path.join(DATASET_DIR, "code")

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


def sanitize_func_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", name).lower()
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned or cleaned[0].isdigit():
        cleaned = "task_" + cleaned
    return cleaned


def generate_python_workflow(task_names: list[str]) -> str:
    lines = ["# SpiffWorkflow Generated Implementation", "import time", ""]
    func_names = []
    for t in task_names:
        fname = sanitize_func_name(t)
        func_names.append(fname)
        lines.append(f"def {fname}():")
        lines.append(f'    """Task: {t}"""')
        lines.append(f'    print("Executing {t}")')
        lines.append(f'    return True')
        lines.append("")

    lines.append("def run_workflow():")
    lines.append('    """Driver function executing tasks in BPMN sequence."""')
    for fname in func_names:
        lines.append(f"    {fname}()")
    lines.append("    return True")
    lines.append("")
    lines.append('if __name__ == "__main__":')
    lines.append("    run_workflow()")
    lines.append("")
    return "\n".join(lines)


def collect_spiff_bpmn_files() -> List[Tuple[str, str]]:
    pairs = []
    
    # 1. spiff-example-cli tutorial files
    if os.path.exists(SPIFF_CLI_DIR):
        for f in sorted(os.listdir(SPIFF_CLI_DIR)):
            if f.endswith(".bpmn"):
                name = "spiff_cli_" + f.replace(".bpmn", "")
                pairs.append((name, os.path.join(SPIFF_CLI_DIR, f)))

    # 2. sample-process-models files
    if os.path.exists(SPIFF_MODELS_DIR):
        count = 0
        for root, dirs, files in os.walk(SPIFF_MODELS_DIR):
            for f in sorted(files):
                if f.endswith(".bpmn"):
                    rel = os.path.relpath(os.path.join(root, f), SPIFF_MODELS_DIR)
                    name = "spiff_model_" + re.sub(r"[^a-zA-Z0-9_]", "_", rel.replace(".bpmn", "")).lower()
                    pairs.append((name, os.path.join(root, f)))
                    count += 1
                    if count >= 150:
                        break
            if count >= 150:
                break
                
    return pairs


def ingest_all() -> int:
    os.makedirs(BPMN_OUT_DIR, exist_ok=True)
    os.makedirs(CODE_OUT_DIR, exist_ok=True)
    
    candidates = collect_spiff_bpmn_files()
    print(f"Found {len(candidates)} candidate SpiffWorkflow BPMN files.", flush=True)
    
    successful_pairs = 0
    ingested_summary = []
    
    for idx, (file_id, path) in enumerate(candidates, 1):
        try:
            xml_content = open(path, "r", encoding="utf-8", errors="ignore").read()
            
            # Fast Phase 1 + Phase 2 LTLf synthesis
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
            checkable = suite.conformance_properties()
            if not checkable:
                continue
                
            bpmn_tasks = _bpmn_task_names(pipeline_result)
            if len(bpmn_tasks) < 2:
                continue
                
            py_code = generate_python_workflow(bpmn_tasks)
            wir = derive_call_order_wir(py_code)
            
            # verify compliance via Module 03
            result = process_wir_batch([json.dumps(wir)], bpmn_tasks=bpmn_tasks, property_suite=suite)
            cluster = next(iter(result["clusters"].values()))
            gold_results = cluster["compliance_results"]
            
            verdicts = {r["verdict"] for r in gold_results}
            if "VIOLATION" in verdicts or "COMPLIANT" not in verdicts:
                continue
                
            applicable = [
                r for r in gold_results if r["verdict"] == "COMPLIANT" and not r["unmatched_atoms"]
            ]
            if not applicable:
                continue
                
            # save pair
            bpmn_dest = os.path.join(BPMN_OUT_DIR, f"{file_id}.bpmn")
            code_dest = os.path.join(CODE_OUT_DIR, f"{file_id}.py")
            with open(bpmn_dest, "w", encoding="utf-8") as f:
                f.write(xml_content)
            with open(code_dest, "w", encoding="utf-8") as f:
                f.write(py_code)
                
            successful_pairs += 1
            ingested_summary.append({
                "id": file_id,
                "bpmn_file": bpmn_dest,
                "code_file": code_dest,
                "tasks_count": len(bpmn_tasks),
                "checkable_properties": len(checkable),
                "applicable_properties": len(applicable)
            })
            print(f"[{successful_pairs}] INGESTED {file_id}: {len(bpmn_tasks)} tasks, {len(checkable)} props", flush=True)
            
        except Exception:
            continue
            
    manifest_path = os.path.join(DATASET_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(ingested_summary, f, indent=2)
        
    print(f"\nSuccessfully ingested {successful_pairs} SpiffWorkflow gold pairs!", flush=True)
    print(f"Manifest written to: {manifest_path}", flush=True)
    return successful_pairs


if __name__ == "__main__":
    ingest_all()
