import json
import time
import os
import sys

# Ensure the 'src' directory is in the path for the compiled .so
sys.path.append(os.path.dirname(__file__))

try:
    # Attempt to import the compiled C++ Pybind11 module
    import vibecheck_lifter
    print("✅ Successfully imported vibecheck_lifter")
except ImportError as e:
    print(f"❌ Failed to import vibecheck_lifter: {e}")
    # Print diagnostic info
    print(f"Current Directory: {os.getcwd()}")
    print(f"Files in current dir: {os.listdir('.')}")
    if os.path.exists('src'):
        print(f"Files in src/: {os.listdir('src')}")
    sys.exit(1)

def main():
    print("\n--- VibeCheck Equivalence Engine (Module 03) ---")
    print("Initializing Advanced Lifter (Milestone P1.1 Verification)...")
    
    # Instantiate the AdvancedLifter C++ class
    lifter = vibecheck_lifter.AdvancedLifter()
    
    # Mock JSON payload adhering to shared_schemas/wir_schema.json
    # Test case: variables with concrete types vs unresolved types (Any)
    mock_wir = {
        "control_variables": ["loan_approved", "credit_score"],
        "data_variables": ["requested_amount"],
        "types": {
            "loan_approved": "bool",
            "credit_score": "int",
            "requested_amount": "float",
            "risk_profile": "Any"  # Triggers conservative over-approximation (P1.1)
        }
    }
    
    wir_json_str = json.dumps(mock_wir)
    
    print(f"Parsing mock WIR types...")
    # ... existing verification ...
    try:
        lifter.parse_wir_types(wir_json_str)
        var_map = lifter.get_variable_map()
        
        print("\n[BDD Variable Registry]")
        for var, idx in sorted(var_map.items()):
            print(f"  {var} => BDD Index: {idx}")
        
        # Verify the over-approximation logic
        if "risk_profile_ANY" in var_map:
            print("\n✅ Verification Success: 'risk_profile_ANY' correctly mapped as non-deterministic choice.")
        
        # --- Milestone P1.2 Verification: Semantic Action Label Mapping ---
        print("\nInitializing Semantic Matcher (Milestone P1.2)...")
        bpmn_tasks = ["Check Funds", "Approve Loan", "Verify Identity"]
        lifter.set_bpmn_tasks(bpmn_tasks)
        
        test_actions = [
            ("check_funds", "Lexical"),          # Exact lexical (normalized)
            ("VerifyIdent", "Levenshtein"),       # Levenshtein distance 2
            ("validate_bank_balance", "NLP")     # NLP similarity (Sentence-BERT)
        ]
        
        for action, tier in test_actions:
            matched = lifter.semantic_match(action)
            print(f"  Action: '{action}' ({tier} tier) => Matched: '{matched}'")

    except Exception as e:
        print(f"❌ Execution Error: {e}")

    print("\nModule 03: Build verification complete. Standing by for JSON WIR inputs...")
    time.sleep(2)

if __name__ == "__main__":
    main()
