import xml.etree.ElementTree as ET
import json
from typing import List, Dict, Any, Optional

class SemanticExtractionEngine:
    """
    Phase 01 Semantic Extraction Engine for Module 01 of the VibeCheck Framework.
    Implements the V3 -> V2 -> V1 pipeline for BPMN 2.0 to Semantic Graph conversion.
    """
    
    # Standard BPMN 2.0 Namespaces
    NS = {
        'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
        'bpmndi': 'http://www.omg.org/spec/BPMN/20100524/DI',
        'dc': 'http://www.omg.org/spec/DD/20100524/DC',
        'di': 'http://www.omg.org/spec/DD/20100524/DI'
    }

    EXECUTABLE_NODES = [
        'startEvent', 'endEvent', 'task', 'userTask', 'serviceTask', 
        'exclusiveGateway', 'parallelGateway', 'boundaryEvent'
    ]

    def __init__(self, xml_string: str):
        self.xml_string = xml_string
        try:
            self.root = ET.fromstring(xml_string)
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML provided: {e}")
            
        self.states: List[Dict[str, Any]] = []
        self.edges: List[Dict[str, Any]] = []
        self.initial_state: str = ""
        self.unsupported_constructs: List[str] = []
        
        self.executable_nodes_count: int = 0
        self.mapped_nodes_count: int = 0
        self.total_sequence_flows: int = 0
        self.mapped_edges_count: int = 0

    def run_pipeline(self) -> Dict[str, Any]:
        """Executes the V3 -> V2 -> V1 extraction pipeline."""
        # Layer V3: Syntactic Sanitization
        self._layer_v3_sanitize()
        
        # Layer V2: Semantic Graph Construction & Labeling
        self._layer_v2_construct_and_label()
        
        # Layer V1: Quality Gate Certification
        certificate = self._layer_v1_certify()
        
        if certificate["status"] == "FAIL":
            # For this,returning the failed certificate.
            pass

        return {
            "phase_1_certificate": certificate,
            "semantic_graph": {
                "initial_state": self.initial_state,
                "states": self.states,
                "edges": self.edges
            }
        }

    def _layer_v3_sanitize(self):
        """
        Layer V3: Strips presentational DI tags and identifies executable nodes.
        """
        for diag in self.root.findall('.//bpmndi:BPMNDiagram', self.NS):
            # If the diagram is a direct child of definitions
            try:
                self.root.remove(diag)
            except ValueError:
                pass

        # Identify all executable control-flow nodes in the raw XML for coverage metrics
        self.executable_nodes_count = 0
        for node_type in self.EXECUTABLE_NODES:
            # Search globally in the XML to find all instances
            nodes = self.root.findall(f'.//bpmn:{node_type}', self.NS)
            self.executable_nodes_count += len(nodes)

    def _layer_v2_construct_and_label(self):
        """
        Layer V2: Traverses sanitized DOM and applies Kripke labeling.
        (Milestones P1.2, P1.3, P1.4)
        """
        processes = self.root.findall('.//bpmn:process', self.NS)
        
        for process in processes:
            # 1. State Instantiation & Kripke Labeling
            for node_type in self.EXECUTABLE_NODES:
                for node in process.findall(f'bpmn:{node_type}', self.NS):
                    node_id = node.get('id')
                    node_name = node.get('name', node_id)
                    
                    # Apply Kripke-compatible labeling
                    # register distinct atomic propositions for tasks: start(Task_Name) and done(Task_Name)
                    props = []
                    clean_name = node_name.replace(" ", "_").replace("\n", "_")
                    
                    if 'task' in node_type.lower():
                        props = [f"start({clean_name})", f"done({clean_name})"]
                    else:
                        # For other nodes, use a single atomic proposition
                        props = [clean_name]

                    # Track initial state (startEvent)
                    if node_type == 'startEvent' and not self.initial_state:
                        self.initial_state = node_id

                    self.states.append({
                        "node_id": node_id,
                        "node_type": node_type,
                        "atomic_propositions": props
                    })
                    self.mapped_nodes_count += 1

            # 2. Edge Mapping (Sequence Flow)
            sequence_flows = process.findall('bpmn:sequenceFlow', self.NS)
            for flow in sequence_flows:
                source = flow.get('sourceRef')
                target = flow.get('targetRef')
                if source and target:
                    # Extract condition expression if present
                    condition = None
                    cond_node = flow.find('bpmn:conditionExpression', self.NS)
                    if cond_node is not None:
                        condition = cond_node.text

                    edge = {
                        "source_id": source,
                        "target_id": target
                    }
                    if condition:
                        edge["condition"] = condition
                    
                    self.edges.append(edge)
                    self.mapped_edges_count += 1

    def _layer_v1_certify(self) -> Dict[str, Any]:
        """
        Layer V1: Computes coverage metrics and enforces Quality Gate.
        (Milestone P1.5)
        """
        node_coverage = 0.0
        if self.executable_nodes_count > 0:
            node_coverage = self.mapped_nodes_count / self.executable_nodes_count
        
        status = "PASS" if node_coverage >= 0.95 else "FAIL"
        
        return {
            "status": status,
            "node_coverage_Y_Struct": round(node_coverage, 4),
            "sanitized_nodes_count": self.mapped_nodes_count,
            "unsupported_constructs": self.unsupported_constructs
        }

def main():
    """Main execution block for standalone testing."""
    import sys
    import select
    
    input_data = ""
    # Check if there is data waiting on stdin
    if not sys.stdin.isatty():
        input_data = sys.stdin.read().strip()
    
    if not input_data:
        input_data = """<?xml version="1.0" encoding="UTF-8"?>
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

    try:
        engine = SemanticExtractionEngine(input_data)
        result = engine.run_pipeline()
        print(json.dumps(result, indent=2))
    except Exception as e:
        error_result = {
            "phase_1_certificate": {
                "status": "FAIL",
                "error": str(e)
            }
        }
        print(json.dumps(error_result, indent=2))

if __name__ == "__main__":
    main()
