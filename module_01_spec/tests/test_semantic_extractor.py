import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from semantic_extractor import SemanticExtractionEngine

def test_semantic_extractor_valid_xml():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" targetNamespace="http://bpmn.io/schema/bpmn">
      <bpmn:process id="Process_1" isExecutable="false">
        <bpmn:startEvent id="StartEvent_1" />
        <bpmn:task id="Task_1" name="Task A" />
        <bpmn:endEvent id="EndEvent_1" />
        <bpmn:sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="Task_1" />
        <bpmn:sequenceFlow id="Flow_2" sourceRef="Task_1" targetRef="EndEvent_1" />
      </bpmn:process>
    </bpmn:definitions>
    """
    engine = SemanticExtractionEngine(xml)
    result = engine.run_pipeline()
    
    assert result["phase_1_certificate"]["status"] == "PASS"
    graph = result["semantic_graph"]
    assert len(graph["states"]) == 3
    assert len(graph["edges"]) == 2
    assert graph["initial_state"] == "StartEvent_1"

def test_semantic_extractor_invalid_xml():
    with pytest.raises(ValueError):
        SemanticExtractionEngine("<invalid_xml_without_closing_tag")
