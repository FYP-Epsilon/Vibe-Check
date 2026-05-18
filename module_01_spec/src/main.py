import time
import json
from api import run_module_01_pipeline

def main():
    print("✅ Module 01 (Spec Engine): BPMN Parsing & LTLf Synthesis environment initialized.")
    
    # Example BPMN XML input with XOR gateway and implicit guard
    bpmn_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" targetNamespace="http://bpmn.io/schema/bpmn">
      <bpmn:process id="Loan_Process" isExecutable="true">
        <bpmn:startEvent id="Start_1" name="Begin" />
        <bpmn:exclusiveGateway id="Gateway_1" name="Credit Check" />
        <bpmn:task id="Activity_Approve" name="Approve Loan" />
        <bpmn:task id="Activity_Reject" name="Reject Loan" />
        <bpmn:endEvent id="End_1" name="Finish" />
        
        <bpmn:sequenceFlow id="F1" sourceRef="Start_1" targetRef="Gateway_1" />
        <bpmn:sequenceFlow id="F2" sourceRef="Gateway_1" targetRef="Activity_Approve">
            <bpmn:conditionExpression>credit_score > 700</bpmn:conditionExpression>
        </bpmn:sequenceFlow>
        <bpmn:sequenceFlow id="F3" sourceRef="Gateway_1" targetRef="Activity_Reject" /> <!-- Implicit Else -->
        
        <bpmn:sequenceFlow id="F4" sourceRef="Activity_Approve" targetRef="End_1" />
        <bpmn:sequenceFlow id="F5" sourceRef="Activity_Reject" targetRef="End_1" />
      </bpmn:process>
    </bpmn:definitions>
    """
    
    print("\n[V3 -> V2 -> V1 Pipeline] Starting Full Module 01 Execution...")
    try:
        result = run_module_01_pipeline(bpmn_xml)
        
        if result["status"] == "PASS":
            print("\n[Phase 1: Semantic Extraction Certificate]")
            print(json.dumps(result["phase_1"]["phase_1_certificate"], indent=2))
            
            print("\n[Phase 2: LTLf Synthesis Certificate]")
            print(json.dumps(result["phase_2"]["phase_2_certificate"], indent=2))
            
            print("\n[Inferred Implicit Guards]")
            print(json.dumps(result["phase_2"]["inferred_implicit_guards"], indent=2))
            
            print("\n[Generated LTLf Properties (Sample)]")
            for cat, props in result["phase_2"]["ltlf_property_suite"].items():
                print(f"- {cat}: {len(props)} properties")
                if props:
                    print(f"  Example: {props[0]}")
        else:
            print(f"❌ Pipeline Failed at Phase {result.get('phase', 'Unknown')}: {result.get('error')}")
        
    except Exception as e:
        print(f"❌ Execution Failed: {e}")

    time.sleep(1)
    print("\nModule 01: Standing by for real-time BPMN XML inputs...")

if __name__ == "__main__":
    main()
