import json
from typing import Dict, Any
from semantic_extractor import SemanticExtractionEngine
from ltlf_synthesizer import FLTLSynthesizer, VerificationException

def run_module_01_pipeline(bpmn_xml: str) -> Dict[str, Any]:
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
        
        return {
            "status": "PASS",
            "phase_1": phase_1_result,
            "phase_2": phase_2_result
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
    # Test with a simple BPMN XML
    test_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" targetNamespace="http://bpmn.io/schema/bpmn">
      <bpmn:process id="Process_1" isExecutable="false">
        <bpmn:startEvent id="Start_1" name="Start" />
        <bpmn:exclusiveGateway id="Gateway_1" name="Check" />
        <bpmn:task id="Task_A" name="A" />
        <bpmn:task id="Task_B" name="B" />
        <bpmn:sequenceFlow id="F1" sourceRef="Start_1" targetRef="Gateway_1" />
        <bpmn:sequenceFlow id="F2" sourceRef="Gateway_1" targetRef="Task_A">
            <bpmn:conditionExpression>x > 10</bpmn:conditionExpression>
        </bpmn:sequenceFlow>
        <bpmn:sequenceFlow id="F3" sourceRef="Gateway_1" targetRef="Task_B" />
      </bpmn:process>
    </bpmn:definitions>
    """
    result = run_module_01_pipeline(test_xml)
    print(json.dumps(result, indent=2))
