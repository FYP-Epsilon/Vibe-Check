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
                    "error": "Phase 1 Quality Gate failed.",
                    "details": phase_1_result["phase_1_certificate"]
                }
            )

        # Phase 2: LTLf Synthesis
        synthesizer = FLTLSynthesizer(phase_1_result)
        phase_2_result = synthesizer.run_pipeline()

        # Phase 3: Mutation Refinement
        validator = MutationValidator(phase_1_result["semantic_graph"], phase_2_result["ltlf_property_suite"])
        phase_3_result = validator.execute_validation_pipeline()
        
        return {
            "status": "PASS",
            "phase_1": phase_1_result,
            "phase_2": phase_2_result,
            "phase_3": phase_3_result
        }
        
    except VerificationException as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/docs")
@app.get("/")
def read_root():
    return {"status": "online", "message": "✅ Module 01 (Spec Engine) API is running."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
