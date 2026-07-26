import os
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

try:
    from .semantic_extractor import SemanticExtractionEngine
    from .ltlf_synthesizer import FLTLSynthesizer
    from .mutation_refiner import MutationValidator, VerificationException
    from .automata_lifter import AutomataLifter, AutomataLifterException
except ImportError:
    from semantic_extractor import SemanticExtractionEngine
    from ltlf_synthesizer import FLTLSynthesizer
    from mutation_refiner import MutationValidator, VerificationException
    from automata_lifter import AutomataLifter, AutomataLifterException

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
        
        # Phase 4: Automata Lifting (non-blocking — SPOT may not be installed)
        phase_4_result = None
        try:
            lifter = AutomataLifter(
                property_suite=phase_3_result,
                semantic_graph=phase_1_result["semantic_graph"],
            )
            phase_4_result = lifter.run_pipeline()
        except AutomataLifterException as e:
            phase_4_result = {
                "phase_4_certificate": {
                    "status": "FAIL",
                    "error_code": "PHASE_4_LIFTER_FAIL",
                    "message": str(e),
                }
            }
        except Exception as e:
            phase_4_result = {
                "phase_4_certificate": {
                    "status": "FAIL_WITH_ERRORS",
                    "error_code": "PHASE_4_UNEXPECTED_ERROR",
                    "message": str(e),
                }
            }

        # Phase 5: Reverse Process Mining Alignment
        phase_5_result = None
        try:
            try:
                from .process_mining_alignment import ProcessMiningAlignment
                from .mutation_refiner import LTLfAuditor
            except ImportError:
                from process_mining_alignment import ProcessMiningAlignment
                from mutation_refiner import LTLfAuditor
                
            auditor = LTLfAuditor(phase_3_result["refined_ltlf_property_suite"])
            ltlf_traces = auditor._generate_traces(phase_1_result["semantic_graph"], depth=10)
            
            aligner = ProcessMiningAlignment(bpmn_xml, ltlf_traces, semantic_graph=phase_1_result["semantic_graph"])
            phase_5_result = aligner.run_pipeline()
        except Exception as e:
            phase_5_result = {
                "phase_5_certificate": {
                    "status": "FAIL_WITH_ERRORS",
                    "error_code": "PHASE_5_ALIGNMENT_FAIL",
                    "message": str(e)
                }
            }

        # Determine overall status
        overall_status = "PASS"
        if phase_4_result:
            p4_status = phase_4_result.get("phase_4_certificate", {}).get("status", "")
            if p4_status == "FAIL":
                overall_status = "PASS_PHASE4_FAIL"
            elif p4_status == "PASS_NO_SPOT":
                overall_status = "PASS_NO_SPOT"
                
        if phase_5_result:
            p5_status = phase_5_result.get("phase_5_certificate", {}).get("status", "")
            if p5_status == "FAIL":
                overall_status = "PASS_PHASE5_FAIL"
            elif p5_status == "PASS_NO_PM4PY":
                if overall_status == "PASS":
                    overall_status = "PASS_NO_PM4PY"

        return {
            "status": overall_status,
            "phase_1": phase_1_result,
            "phase_2": phase_2_result,
            "phase_3": phase_3_result,
            "phase_4": phase_4_result,
            "phase_5": phase_5_result,
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
