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
        'startEvent', 'endEvent', 'task', 'userTask', 'serviceTask', 'scriptTask', 'manualTask',
        'exclusiveGateway', 'parallelGateway', 'inclusiveGateway', 'boundaryEvent',
        'subProcess', 'callActivity', 'eventBasedGateway',
        'intermediateCatchEvent', 'intermediateThrowEvent'
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
        self.start_states: List[str] = []
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
            pass

        return {
            "phase_1_certificate": certificate,
            "semantic_graph": {
                "initial_state": self.initial_state,
                "start_states": self.start_states,
                "states": self.states,
                "edges": self.edges
            }
        }

    def _layer_v3_sanitize(self):
        """
        Layer V3: Strips presentational DI tags and identifies executable nodes.
        """
        for diag in self.root.findall('.//bpmndi:BPMNDiagram', self.NS):
            try:
                self.root.remove(diag)
            except ValueError:
                pass

        # Identify all executable control-flow nodes in the raw XML for coverage metrics
        self.executable_nodes_count = 0
        for node_type in self.EXECUTABLE_NODES:
            nodes = self.root.findall(f'.//bpmn:{node_type}', self.NS)
            self.executable_nodes_count += len(nodes)

    def _layer_v2_construct_and_label(self):
        """
        Layer V2: Traverses sanitized DOM and applies Kripke labeling.
        (Milestones P1.2, P1.3, P1.4)
        """
        # Build parent map to identify parents of nodes (e.g. subProcesses)
        parent_map = {c: p for p in self.root.iter() for c in p}
        
        # Populate unsupported constructs by scanning all elements under root
        known_tags = set(self.EXECUTABLE_NODES + [
            'sequenceFlow', 'process', 'definitions', 'multiInstanceLoopCharacteristics',
            'standardLoopCharacteristics', 'conditionExpression', 'extensionElements',
            'incoming', 'outgoing', 'documentation', 'ioSpecification', 'dataInputAssociation',
            'dataOutputAssociation', 'property', 'dataObjectReference', 'dataObject', 'laneSet', 'lane',
            'collaboration', 'participant', 'messageFlow', 'association', 'textAnnotation'
        ])
        for elem in self.root.iter():
            tag_local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            # If it's a BPMN element not in known_tags, record it
            if elem.tag.startswith(f"{{{self.NS['bpmn']}}}") and tag_local not in known_tags:
                if tag_local not in self.unsupported_constructs:
                    self.unsupported_constructs.append(tag_local)

        processes = self.root.findall('.//bpmn:process', self.NS)
        
        for process in processes:
            # 1. State Instantiation & Kripke Labeling
            for node_type in self.EXECUTABLE_NODES:
                # Use recursive .// to find nested elements (e.g. inside subProcesses)
                for node in process.findall(f'.//bpmn:{node_type}', self.NS):
                    node_id = node.get('id')
                    node_name = node.get('name', node_id)
                    
                    # Apply Kripke-compatible labeling
                    props = []
                    clean_name = node_name.replace(" ", "_").replace("\n", "_")
                    
                    if 'task' in node_type.lower():
                        props = [f"start({clean_name})", f"done({clean_name})"]
                    else:
                        props = [clean_name]

                    state_dict = {
                        "node_id": node_id,
                        "node_type": node_type,
                        "atomic_propositions": props
                    }

                    # Read parent if nested in a subProcess
                    curr = node
                    while curr in parent_map:
                        parent = parent_map[curr]
                        tag_local = parent.tag.split('}')[-1] if '}' in parent.tag else parent.tag
                        if tag_local == 'subProcess':
                            state_dict["parent"] = parent.get('id')
                            break
                        curr = parent

                    # Read loop characteristics
                    has_loop = (node.find('.//bpmn:multiInstanceLoopCharacteristics', self.NS) is not None or
                                node.find('.//bpmn:standardLoopCharacteristics', self.NS) is not None)
                    if has_loop:
                        state_dict["loop"] = True

                    # Extract default flow attribute for exclusive gateway
                    if node_type == 'exclusiveGateway':
                        default_flow = node.get('default')
                        if default_flow:
                            state_dict["default_flow"] = default_flow

                    # Track initial states (startEvent)
                    if node_type == 'startEvent':
                        if node_id not in self.start_states:
                            self.start_states.append(node_id)
                        if not self.initial_state:
                            self.initial_state = node_id

                    self.states.append(state_dict)
                    self.mapped_nodes_count += 1

            # 2. Edge Mapping (Sequence Flow)
            sequence_flows = process.findall('.//bpmn:sequenceFlow', self.NS)
            for flow in sequence_flows:
                source = flow.get('sourceRef')
                target = flow.get('targetRef')
                if source and target:
                    condition = None
                    cond_node = flow.find('bpmn:conditionExpression', self.NS)
                    if cond_node is not None:
                        condition = cond_node.text

                    edge = {
                        "flow_id": flow.get('id'),
                        "source_id": source,
                        "target_id": target
                    }
                    if condition and condition.strip():
                        edge["condition"] = condition.strip()
                    
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
        
        status = "PASS" if node_coverage >= 1.0 else "FAIL"
        
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
