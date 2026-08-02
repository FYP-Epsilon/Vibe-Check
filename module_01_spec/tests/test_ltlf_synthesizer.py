import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from ltlf_synthesizer import FLTLSynthesizer

@pytest.fixture
def sample_graph():
    return {
        "semantic_graph": {
            "initial_state": "Start_1",
            "states": [
                {"node_id": "Start_1", "node_type": "startEvent", "atomic_propositions": ["node(start)"]},
                {"node_id": "Task_1", "node_type": "task", "atomic_propositions": ["start(T1)", "done(T1)"]},
                {"node_id": "Gateway_1", "node_type": "exclusiveGateway", "atomic_propositions": ["node(xor)"]},
                {"node_id": "Task_2", "node_type": "task", "atomic_propositions": ["start(T2)", "done(T2)"]},
                {"node_id": "End_1", "node_type": "endEvent", "atomic_propositions": ["node(end)"]}
            ],
            "edges": [
                {"source_id": "Start_1", "target_id": "Task_1"},
                {"source_id": "Task_1", "target_id": "Gateway_1"},
                {"source_id": "Gateway_1", "target_id": "Task_2"},
                {"source_id": "Task_2", "target_id": "End_1"}
            ]
        }
    }

def test_ltlf_synthesizer(sample_graph):
    synthesizer = FLTLSynthesizer(sample_graph)
    result = synthesizer.run_pipeline()
    
    assert result["phase_2_certificate"]["status"] == "PASS"
    suite = result["ltlf_property_suite"]
    assert "P1_Structural_Control_Flow" in suite
    assert "P0_Critical_Sentinels" in suite
    
    # Check that structural flow properties for tasks are generated properly
    has_flow = any("!start(T2)W(done(T1))" in p.replace(" ", "") for p in suite["P1_Structural_Control_Flow"])
    assert has_flow, f"Expected a bridged control flow property for Task_1 -> Task_2, got: {suite['P1_Structural_Control_Flow']}"
