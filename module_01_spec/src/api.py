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
