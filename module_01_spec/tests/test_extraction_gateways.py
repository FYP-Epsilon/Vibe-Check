import unittest
from module_01_spec.src.semantic_extractor import SemanticExtractionEngine
from module_01_spec.src.ltlf_synthesizer import FLTLSynthesizer

class TestExtractionGateways(unittest.TestCase):
    def test_subprocess_and_unsupported_constructs(self):
        # A process with a subprocess, loop characteristics, and an unsupported construct (e.g. dataObject)
        bpmn_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" 
                          targetNamespace="http://bpmn.io/schema/bpmn">
          <bpmn:process id="Process_1" isExecutable="false">
            <bpmn:startEvent id="StartEvent_1" name="Start" />
            <bpmn:subProcess id="SubProcess_1" name="SubProcess">
              <bpmn:multiInstanceLoopCharacteristics />
              <bpmn:task id="SubTask_1" name="NestedApprove" />
            </bpmn:subProcess>
            <bpmn:endEvent id="EndEvent_1" name="End" />
            <bpmn:sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="SubProcess_1" />
            <bpmn:sequenceFlow id="Flow_2" sourceRef="SubProcess_1" targetRef="EndEvent_1" />
            <bpmn:complexGateway id="Complex_1" />
          </bpmn:process>
        </bpmn:definitions>
        """
        
        extractor = SemanticExtractionEngine(bpmn_xml)
        res = extractor.run_pipeline()
        self.assertEqual(res["phase_1_certificate"]["status"], "PASS")
        
        # Verify subprocess task is recursively mapped and has parent field
        states = res["semantic_graph"]["states"]
        subtask_state = next(s for s in states if s["node_id"] == "SubTask_1")
        self.assertEqual(subtask_state["parent"], "SubProcess_1")
        
        # Verify subprocess itself has loop: True
        subprocess_state = next(s for s in states if s["node_id"] == "SubProcess_1")
        self.assertTrue(subprocess_state.get("loop"))
        
        # Verify complexGateway is in unsupported_constructs
        self.assertIn("complexGateway", res["phase_1_certificate"]["unsupported_constructs"])

    def test_xor_join_and_default_flow(self):
        # An XOR split with a default flow, and an XOR join
        bpmn_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" 
                          targetNamespace="http://bpmn.io/schema/bpmn">
          <bpmn:process id="Process_1" isExecutable="false">
            <bpmn:startEvent id="StartEvent_1" name="Start" />
            <bpmn:exclusiveGateway id="XOR_Split" name="Split" default="Flow_Else" />
            <bpmn:task id="Task_A" name="Approve" />
            <bpmn:task id="Task_B" name="Reject" />
            <bpmn:exclusiveGateway id="XOR_Join" name="Join" />
            <bpmn:endEvent id="EndEvent_1" name="End" />
            
            <bpmn:sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="XOR_Split" />
            <bpmn:sequenceFlow id="Flow_A" sourceRef="XOR_Split" targetRef="Task_A">
              <bpmn:conditionExpression>score > 50</bpmn:conditionExpression>
            </bpmn:sequenceFlow>
            <bpmn:sequenceFlow id="Flow_Else" sourceRef="XOR_Split" targetRef="Task_B" />
            
            <bpmn:sequenceFlow id="Flow_End_A" sourceRef="Task_A" targetRef="XOR_Join" />
            <bpmn:sequenceFlow id="Flow_End_B" sourceRef="Task_B" targetRef="XOR_Join" />
            <bpmn:sequenceFlow id="Flow_End" sourceRef="XOR_Join" targetRef="EndEvent_1" />
          </bpmn:process>
        </bpmn:definitions>
        """
        
        extractor = SemanticExtractionEngine(bpmn_xml)
        res_p1 = extractor.run_pipeline()
        self.assertEqual(res_p1["phase_1_certificate"]["status"], "PASS")
        
        # Test ltlf synthesis (Phase 2)
        synthesizer = FLTLSynthesizer(res_p1)
        res_p2 = synthesizer.run_pipeline()
        
        # Verify it passed Phase 2 (Join did not cause split-guard exception)
        self.assertEqual(res_p2["phase_2_certificate"]["status"], "PASS")
        
        # Verify default flow Flow_Else got negated conjunction guard
        inferred = res_p2["inferred_implicit_guards"]
        self.assertEqual(len(inferred), 1)
        self.assertEqual(inferred[0]["gateway_id"], "XOR_Split")
        self.assertEqual(inferred[0]["target_node_id"], "Task_B")
        self.assertEqual(inferred[0]["inferred_condition"], "!(score > 50)")

if __name__ == "__main__":
    unittest.main()
