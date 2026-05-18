import time
import json
from semantic_extractor import SemanticExtractionEngine

def main():
    print("✅ Module 01 (Spec Engine): BPMN Parsing environment initialized successfully.")
    
    # Example BPMN XML input
    bpmn_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" 
                      xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" 
                      targetNamespace="http://bpmn.io/schema/bpmn">
      <bpmn:process id="Process_1" isExecutable="true">
        <bpmn:startEvent id="Start_1" name="Begin" />
        <bpmn:task id="Activity_1" name="Process Data" />
        <bpmn:endEvent id="End_1" name="Finish" />
        <bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Activity_1" />
        <bpmn:sequenceFlow id="Flow_2" sourceRef="Activity_1" targetRef="End_1" />
      </bpmn:process>
    </bpmn:definitions>
    """
    
    print("\n[V3 -> V2 -> V1 Pipeline] Starting Extraction...")
    try:
        engine = SemanticExtractionEngine(bpmn_xml)
        result = engine.run_pipeline()
        
        print("\n[Phase 1 Certificate]")
        print(json.dumps(result["phase_1_certificate"], indent=2))
        
        print("\n[Semantic Graph Summary]")
        print(f"Initial State: {result['semantic_graph']['initial_state']}")
        print(f"States Count: {len(result['semantic_graph']['states'])}")
        print(f"Edges Count: {len(result['semantic_graph']['edges'])}")
        
    except Exception as e:
        print(f"❌ Extraction Failed: {e}")

    time.sleep(1)
    print("\nModule 01: Standing by for real-time BPMN XML inputs...")

if __name__ == "__main__":
    main()
