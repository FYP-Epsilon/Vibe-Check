import json
import copy
from typing import Dict, Any
try:
    from .semantic_extractor import SemanticExtractionEngine
    from .ltlf_synthesizer import FLTLSynthesizer, VerificationException
    from .mutation_refiner import MutationValidator
except ImportError:
    from semantic_extractor import SemanticExtractionEngine
    from ltlf_synthesizer import FLTLSynthesizer, VerificationException
    from mutation_refiner import MutationValidator

def run_module_01_pipeline(bpmn_xml: str, seed: int = 42) -> Dict[str, Any]:
    """
    Runs the complete pipeline for Module 01 of the VibeCheck Framework."""
    try:
        # Phase 1: Semantic Extraction
        extraction_engine = SemanticExtractionEngine(bpmn_xml)
        phase_1_result = extraction_engine.run_pipeline()
        
        if phase_1_result["phase_1_certificate"]["status"] == "FAIL":
            return {
                "status": "FAIL",
                "phase": 1,
                "error": "Phase 1 Quality Gate failed.",
                "details": phase_1_result["phase_1_certificate"]
            }

        # Phase 2: LTLf Synthesis
        synthesizer = FLTLSynthesizer(phase_1_result)
        phase_2_result = synthesizer.run_pipeline()

        # Phase 3: Mutation Refinement
        validator = MutationValidator(phase_1_result["semantic_graph"], phase_2_result["ltlf_property_suite"])
        phase_3_result = validator.execute_validation_pipeline(seed=seed)
        
        if phase_3_result["phase_3_certificate"]["status"] == "FAIL":
            return {
                "status": "FAIL",
                "phase": 3,
                "error": "Phase 3 Quality Gate failed.",
                "details": phase_3_result["phase_3_certificate"]
            }

        # Phase 4: PBCTS with Self-Correcting Specification Loop (SCSL)
        # If PBCTS detects semantic gaps (over-specification), it synthesizes
        # corrective LTLf formulas, adds them to the property suite, and re-verifies.
        # This guarantees Module 01 either PROVES alignment or FAILS with diagnostics.
        try:
            from .bidirectional_alignment import run_pbcts_pipeline
        except ImportError:
            from bidirectional_alignment import run_pbcts_pipeline

        max_scsl_rounds = 3
        current_suite = copy.deepcopy(phase_3_result["refined_ltlf_property_suite"])
        phase_pbcts_result = None
        scsl_round = 0

        for scsl_round in range(max_scsl_rounds):
            try:
                phase_pbcts_result = run_pbcts_pipeline(
                    property_suite=current_suite,
                    semantic_graph=phase_1_result["semantic_graph"]
                )
            except Exception as e:
                phase_pbcts_result = {
                    "phase_4_certificate": {
                        "status": "FAIL_WITH_ERRORS",
                        "message": str(e)
                    }
                }
                break

            cert = phase_pbcts_result.get("phase_4_certificate", {})
            converged = cert.get("convergence", {}).get("converged", False)
            corrections = cert.get("scsl_corrections", [])

            if converged:
                break  # Alignment mathematically proven

            if not corrections or scsl_round == max_scsl_rounds - 1:
                break  # No auto-corrections possible or final round

            # SCSL: Apply corrections and retry
            current_suite = copy.deepcopy(current_suite)
            current_suite.setdefault("P4_SCSL_Corrections", []).extend(corrections)

        # Determine overall status
        overall_status = "PASS"
        if phase_pbcts_result:
            p4_converged = phase_pbcts_result.get("phase_4_certificate", {}).get("convergence", {}).get("converged", False)
            if not p4_converged:
                overall_status = "FAIL_ALIGNMENT_UNPROVEN"

        return {
            "status": overall_status,
            "phase_1": phase_1_result,
            "phase_2": phase_2_result,
            "phase_3": phase_3_result,
            "phase_4": phase_pbcts_result,
            "phase_5": None,
            "scsl_rounds_executed": scsl_round + 1
        }
        
    except VerificationException as e:
        return {
            "status": "FAIL",
            "phase": 2,
            "error": str(e)
        }
    except Exception as e:
        return {
            "status": "FAIL",
            "error": f"Unexpected error: {str(e)}"
        }

def export_for_module_03(pipeline_result: Dict[str, Any], filepath: str = "module_03_input.json"):
    """
    Extracts the specific artifacts required by Module 03 and saves them to a JSON file.
    """
    if pipeline_result.get("status") in ["FAIL", "FAIL_WITH_ERRORS"]:
        raise ValueError("Cannot export to Module 03: Pipeline failed.")

    import re
    # PBCTS ignores loop bounds. We extract it directly from P2_Quality_Limits.
    loop_bound = 0
    p2_suite = pipeline_result["phase_3"]["refined_ltlf_property_suite"].get("P2_Quality_Limits", [])
    for prop in p2_suite:
        # e.g., looks like a comment or specifically encoded in a property string.
        # The semantic extractor puts loop limits in comments sometimes, but 
        # normally we can safely default to 3 if we can't parse it.
        match = re.search(r'loop_bound\s*=\s*(\d+)', prop, re.IGNORECASE)
        if match:
            loop_bound = int(match.group(1))
            break
            
    m3_payload = {
        "semantic_graph": pipeline_result["phase_1"]["semantic_graph"],
        "ltlf_property_suite": pipeline_result["phase_3"]["refined_ltlf_property_suite"],
        "loop_bound_documented": loop_bound,
        # Found by the Module 01 <-> Module 03 bridge investigation: P0 sentinels
        # of the shape '!done(T) W start(T)' are unfalsifiable under any lifting
        # faithful to task semantics -- the invariant that makes a lifting faithful
        # IS the property. A violation there means the Module 03 lifter has a bug,
        # not that the generated code is wrong. Encoded here so any future
        # Module 03 ingestion code inherits the correct handling by construction
        # rather than by tribal knowledge.
        "tier_semantics": {
            "P0_Critical_Sentinels": {
                "role": "lifting_self_test",
                "conformance_check": False,
                "note": (
                    "Unfalsifiable under any faithful lifting. Do not report as a "
                    "passed/failed conformance verdict against generated code; use "
                    "only to self-test the Module 03 lifter."
                ),
            },
            "P1_Structural_Control_Flow": {
                "role": "conformance_check",
                "conformance_check": True,
                "note": "Cross-task ordering/exclusivity properties, genuinely falsifiable against code.",
            },
            "P2_Quality_Limits": {
                "role": "conformance_check",
                "conformance_check": True,
                "note": "Quality/iteration-bound properties, genuinely falsifiable against code.",
            },
        },
    }

    with open(filepath, "w") as f:
        json.dump(m3_payload, f, indent=2)
    return filepath

def export_for_module_02(pipeline_result: Dict[str, Any], filepath: str = "module_02_input.json"):
    """
    Extracts the Semantic Map required by Module 02 for AST tracking and dynamic tracing.
    """
    if pipeline_result.get("status") in ["FAIL", "FAIL_WITH_ERRORS"]:
        raise ValueError("Cannot export to Module 02: Pipeline failed.")

    m2_payload = {
        "semantic_graph": pipeline_result["phase_1"]["semantic_graph"],
        "task_patterns": []
    }
    
    # Auto-generate task patterns for Module 02's Observable Trace Capture
    for node in m2_payload["semantic_graph"]["states"]:
        if node["node_type"] == "task":
            # Extract raw task names as patterns (e.g., "Check_Inventory")
            for prop in node["atomic_propositions"]:
                if prop.startswith("start("):
                    m2_payload["task_patterns"].append(prop[6:-1])
                    
    with open(filepath, "w") as f:
        json.dump(m2_payload, f, indent=2)
    return filepath

if __name__ == "__main__":
    # Test with a simple BPMN XML in here
    simple_bpmn_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" 
                      xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" 
                      targetNamespace="http://bpmn.io/schema/bpmn">
      <bpmn:process id="Process_1" isExecutable="false">
        <bpmn:startEvent id="StartEvent_1" name="Start" />
        <bpmn:task id="Task_1" name="Approve" />
        <bpmn:endEvent id="EndEvent_1" name="End" />
        <bpmn:sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="Task_1" />
        <bpmn:sequenceFlow id="Flow_2" sourceRef="Task_1" targetRef="EndEvent_1" />
      </bpmn:process>
      <bpmndi:BPMNDiagram id="BPMNDiagram_1">
        <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_1" />
      </bpmndi:BPMNDiagram>
    </bpmn:definitions>
    """
    
    result = run_module_01_pipeline(simple_bpmn_xml)
    print("Pipeline Result Status:", result["status"])
    export_path = export_for_module_03(result)
    print(f"Exported perfectly structured payload for Module 03 to {export_path}")
    export_path_2 = export_for_module_02(result)
    print(f"Exported Semantic Map payload for Module 02 to {export_path_2}")