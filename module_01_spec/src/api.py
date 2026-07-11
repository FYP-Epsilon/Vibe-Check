import json
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

        return {
            "status": "PASS",
            "phase_1": phase_1_result,
            "phase_2": phase_2_result,
            "phase_3": phase_3_result
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
    print(json.dumps(result, indent=2))