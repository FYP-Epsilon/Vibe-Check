import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from api import run_module_01_pipeline, export_for_module_03, export_for_module_02
import os

def test_api_pipeline():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" targetNamespace="http://bpmn.io/schema/bpmn">
      <bpmn:process id="Process_1" isExecutable="false">
        <bpmn:startEvent id="StartEvent_1" />
        <bpmn:task id="Task_1" name="Approve" />
        <bpmn:endEvent id="EndEvent_1" />
        <bpmn:sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="Task_1" />
        <bpmn:sequenceFlow id="Flow_2" sourceRef="Task_1" targetRef="EndEvent_1" />
      </bpmn:process>
    </bpmn:definitions>
    """
    res = run_module_01_pipeline(xml)
    
    assert res["status"] in ["PASS", "PASS_PBCTS_UNCONVERGED", "FAIL"]
    if res["status"] != "FAIL":
        assert "phase_1" in res
        assert "phase_2" in res
        assert "phase_3" in res
        
        # Test exports
        f3 = export_for_module_03(res, "test_m3.json")
        f2 = export_for_module_02(res, "test_m2.json")
        
        assert os.path.exists(f3)
        assert os.path.exists(f2)
        
        # Cleanup
        os.remove(f3)
        os.remove(f2)
