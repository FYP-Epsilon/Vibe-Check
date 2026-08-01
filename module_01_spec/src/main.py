import os
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

try:
    from .semantic_extractor import SemanticExtractionEngine
    from .ltlf_synthesizer import FLTLSynthesizer
    from .mutation_refiner import MutationValidator, VerificationException
except ImportError:
    from semantic_extractor import SemanticExtractionEngine
    from ltlf_synthesizer import FLTLSynthesizer
    from mutation_refiner import MutationValidator, VerificationException

app = FastAPI(title="VibeCheck Spec Engine", version="2.0.0")

class BPMNPayload(BaseModel):
    bpmn_xml: str
    seed: int = 42

@app.post("/verify")
def verify_spec(payload: BPMNPayload):
    bpmn_xml = payload.bpmn_xml
    if not bpmn_xml.strip():
        raise HTTPException(status_code=400, detail="BPMN XML content is required.")
        
    try:
        # Phase 1: Semantic Extraction
        extraction_engine = SemanticExtractionEngine(bpmn_xml)
        phase_1_result = extraction_engine.run_pipeline()
        
        if phase_1_result["phase_1_certificate"]["status"] == "FAIL":
            raise HTTPException(
                status_code=422,
                detail={
                    "phase": 1,
                    "error_code": "PHASE_1_GATE_FAIL",
                    "certificate": phase_1_result["phase_1_certificate"]
                }
            )

        # Phase 2: LTLf Synthesis
        synthesizer = FLTLSynthesizer(phase_1_result)
        phase_2_result = synthesizer.run_pipeline()

        # Phase 3: Mutation Refinement
        validator = MutationValidator(phase_1_result["semantic_graph"], phase_2_result["ltlf_property_suite"])
        phase_3_result = validator.execute_validation_pipeline(seed=payload.seed)
        
        if phase_3_result["phase_3_certificate"]["status"] == "FAIL":
            raise HTTPException(
                status_code=422,
                detail={
                    "phase": 3,
                    "error_code": "PHASE_3_GATE_FAIL",
                    "certificate": phase_3_result["phase_3_certificate"]
                }
            )
        
        # Phase 5B: Progression-Based Constructive Trace Synthesis (PBCTS)
        # Replaces Phase 4 and Phase 5A natively in the FastAPI route
        phase_pbcts_result = None
        try:
            try:
                from .bidirectional_alignment import run_pbcts_pipeline
            except ImportError:
                from bidirectional_alignment import run_pbcts_pipeline
            
            phase_pbcts_result = run_pbcts_pipeline(
                property_suite=phase_3_result["refined_ltlf_property_suite"],
                semantic_graph=phase_1_result["semantic_graph"]
            )
        except Exception as e:
            phase_pbcts_result = {
                "phase_4_certificate": {
                    "status": "FAIL_WITH_ERRORS",
                    "error_code": "PHASE_4_PBCTS_ERROR",
                    "message": str(e)
                }
            }

        # Determine overall status
        overall_status = "PASS"
        if phase_pbcts_result:
            p4_status = phase_pbcts_result.get("phase_4_certificate", {}).get("convergence", {}).get("converged", False)
            if not p4_status:
                overall_status = "PASS_PBCTS_UNCONVERGED"


        return {
            "status": overall_status,
            "phase_1": phase_1_result,
            "phase_2": phase_2_result,
            "phase_3": phase_3_result,
            "phase_4": phase_pbcts_result,
            "phase_5": None,
        }
        
    except VerificationException as e:
        raise HTTPException(
            status_code=422,
            detail={
                "phase": 2,
                "error_code": "PHASE_2_VERIFICATION_FAIL",
                "message": str(e)
            }
        )
    except HTTPException:
        # Re-raise FastAPIs HTTPExceptions
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "SYNTAX_ERROR",
                "message": str(e)
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "UNEXPECTED_ERROR",
                "message": f"Unexpected error: {str(e)}"
            }
        )

@app.get("/")
def read_root():
    return {"status": "online", "message": "✅ Module 01 (Spec Engine) API is running."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
