"""
api.py
======
FastAPI entry point for Module 01 (Spec Engine).
Exposes an endpoint to transform BPMN XML into a Semantic Graph.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json
from semantic_extractor import SemanticExtractionEngine

app = FastAPI(title="VibeCheck Spec Engine", version="1.0.0")

class BPMNPayload(BaseModel):
    xml_string: str

@app.post("/extract")
def extract_semantic_graph(payload: BPMNPayload) -> dict:
    """
    Accepts a BPMN 2.0 XML string and returns the Phase 1 Semantic Graph and Certificate.
    """
    try:
        engine = SemanticExtractionEngine(payload.xml_string)
        result = engine.run_pipeline()
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
