import pytest
from src.mutation_refiner import MutationValidator

def test_mutation_validator():
    graph = {
        "initial_state": "Start_1",
        "states": [
            {"node_id": "Start_1", "node_type": "startEvent", "atomic_propositions": ["start"]},
            {"node_id": "Task_1", "node_type": "task", "atomic_propositions": ["start(T1)", "done(T1)"]},
            {"node_id": "End_1", "node_type": "endEvent", "atomic_propositions": ["end"]}
        ],
        "edges": [
            {"source_id": "Start_1", "target_id": "Task_1"},
            {"source_id": "Task_1", "target_id": "End_1"}
        ]
    }
    suite = {
        "P1_Structural_Control_Flow": ["!start(T1) W start"]
    }
    validator = MutationValidator(graph, suite)
    
    # Run with a short max_rounds to ensure it finishes quickly
    result = validator.execute_validation_pipeline(seed=42, max_rounds=1)
    
    assert "phase_3_certificate" in result
    cert = result["phase_3_certificate"]
    assert "status" in cert
    assert "mutants_generated" in cert
