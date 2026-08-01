import pytest
from src.bidirectional_alignment import run_pbcts_pipeline

def test_bidirectional_alignment():
    property_suite = {"P1_Structural_Control_Flow": ["F(start)"]}
    semantic_graph = {
        "initial_state": "Start_1",
        "start_states": ["Start_1"],
        "states": [{"node_id": "Start_1", "node_type": "startEvent", "atomic_propositions": ["start"]}],
        "edges": []
    }
    
    # We expect this to run and return a certificate
    try:
        res = run_pbcts_pipeline(property_suite, semantic_graph)
        assert "phase_4_certificate" in res
        cert = res["phase_4_certificate"]
        assert "alignment_scores" in cert
    except Exception as e:
        # In a deep test suite we would mock out the LTLf evaluator if it's too complex, 
        # but for a basic integration test it should run for this trivial graph.
        pytest.fail(f"PBCTS pipeline raised an exception: {e}")
