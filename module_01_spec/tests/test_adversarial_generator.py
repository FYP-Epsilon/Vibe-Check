import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from adversarial_generator import AdversarialGenerator

def test_adversarial_generator_traces():
    generator = AdversarialGenerator()
    graph = {
        "states": [
            {"node_id": "Start_1", "node_type": "startEvent", "atomic_propositions": ["start"]},
            {"node_id": "Task_1", "node_type": "task", "atomic_propositions": ["start(T1)", "done(T1)"]},
            {"node_id": "End_1", "node_type": "endEvent", "atomic_propositions": ["end"]}
        ]
    }
    
    # Not enough tasks to generate traces in this basic logic
    traces = generator.generate_deceptive_traces(graph)
    assert len(traces) == 0
    
    # Add a second task to trigger generation
    graph["states"].append({"node_id": "Task_2", "node_type": "task", "atomic_propositions": ["start(T2)", "done(T2)"]})
    traces = generator.generate_deceptive_traces(graph)
    assert len(traces) > 0
    
    # Check that synthesis creates LTLf killers without the X operator
    killers = generator.synthesize_killer_properties(traces)
    assert len(killers) > 0
    for k in killers:
        assert "G(" in k
        assert "X(" not in k
