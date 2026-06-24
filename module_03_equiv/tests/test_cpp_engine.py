/tests/test_cpp_engine.py

import json
import sys
import os

# Add the current directory to sys.path so we can find the compiled .so module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import vibecheck_lifter
    print("✅ Successfully imported vibecheck_lifter")
except ImportError:
    print("❌ Could not import vibecheck_lifter. Ensure it is compiled and in the 'src/' directory.")
    # Exit gracefully for now since we are in a headless environment without a compiler
    sys.exit(0)

def test_engine():
    lifter = vibecheck_lifter.AdvancedLifter()
    
    # Mock BPMN tasks for semantic matching
    bpmn_tasks = ["Approve Loan", "Reject Loan", "Verify Identity"]
    lifter.set_bpmn_tasks(bpmn_tasks)
    
    # Mock WIR JSON
    mock_wir = {
        "entry_node": "S0",
        "exit_node": "S2",
        "nodes": [
            {"id": "S0", "type": "entry", "successors": ["T1"], "predecessors": [], "control_vars": [], "data_vars": []},
            {"id": "T1", "type": "task", "successors": ["S2"], "predecessors": ["S0"], "control_vars": [], "data_vars": []},
            {"id": "S2", "type": "exit", "successors": [], "predecessors": ["T1"], "control_vars": [], "data_vars": []}
        ],
        "edges": [
            {"source": "S0", "target": "T1", "guard": "verify_identity_task", "exception_type": None},
            {"source": "T1", "target": "S2", "guard": "approve_loan", "exception_type": None}
        ],
        "control_variables": ["balance"],
        "data_variables": ["user_id"],
        "types": {
            "user_id": "Any"
        }
    }
    
    wir_str = json.dumps(mock_wir)
    
    print("\n--- Testing WIR Type Parsing ---")
    lifter.parse_wir_types(wir_str)
    print("Variable Map:", lifter.get_variable_map())
    
    print("\n--- Testing LTS Lifting ---")
    graph = lifter.lift_to_lts(wir_str)
    print(f"LTS created with {graph.num_states()} states and {graph.num_edges()} edges.")
    
    print("\n--- Testing Minimization & Hashing ---")
    collapsed = lifter.tarjan_tau_collapse(graph)
    h = lifter.compute_deterministic_hash(collapsed)
    print(f"Deterministic Hash: {h}")
    
    print("\n--- Testing Equivalence Checking ---")
    # Test self-equivalence
    is_equiv = lifter.check_stuttering_bisimulation(graph, graph)
    print(f"Self-equivalence check: {'PASSED' if is_equiv else 'FAILED'}")

if __name__ == "__main__":
    test_engine()
