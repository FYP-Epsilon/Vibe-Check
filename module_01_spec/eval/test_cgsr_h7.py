import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent / "src"))
from spec_refiner import SpecificationRefiner, OverWeakeningException

def mock_external_eval(suite: dict) -> float:
    # A mock evaluation function:
    # We pretend that P1_Structural_Control_Flow gives us 80% detection,
    # and P2_Quality_Limits gives us 20% detection.
    # If properties are missing, score drops.
    score = 0.0
    p1 = suite.get("P1_Structural_Control_Flow", [])
    if len(p1) == 2:
        score += 0.80
    elif len(p1) == 1:
        score += 0.40
        
    p2 = suite.get("P2_Quality_Limits", [])
    if len(p2) >= 1:
        score += 0.20
        
    return score

def main():
    print("Testing NC-2 CGSR Over-weakening Guard (H7b)...")
    
    # Original suite
    suite = {
        "P1_Structural_Control_Flow": ["Prop_A", "Prop_B"],
        "P2_Quality_Limits": ["Prop_C"]
    }
    
    refiner = SpecificationRefiner(suite, mock_external_eval)
    print(f"Baseline External Score: {refiner.baseline_score:.2f}")
    
    # 1. Safe Repair (doesn't drop external score too much)
    # Suppose we drop a redundant property not tracked by our mock eval, 
    # but let's drop one P1 which drops score by 0.40 -> this SHOULD be rejected.
    try:
        print("Attempting to drop 'Prop_A' (simulating 40% regression)...")
        refiner.repair({"Prop_A"}, max_regression=0.05)
        print("FAIL: Should have rejected the repair!")
    except OverWeakeningException as e:
        print(f"SUCCESS: Guard tripped correctly -> {e}")
        
    # 2. Safe Repair (drops exactly 0%, safe)
    # Suppose we drop a property that has 0% detection contribution
    suite_with_dummy = {
        "P1_Structural_Control_Flow": ["Prop_A", "Prop_B"],
        "P2_Quality_Limits": ["Prop_C"],
        "P3_Dummy": ["Dummy_Bug"]
    }
    
    refiner2 = SpecificationRefiner(suite_with_dummy, mock_external_eval)
    try:
        print("Attempting to drop 'Dummy_Bug' (simulating 0% regression)...")
        new_suite = refiner2.repair({"Dummy_Bug"}, max_regression=0.05)
        print("SUCCESS: Repair accepted.")
        if "Dummy_Bug" not in new_suite.get("P3_Dummy", []):
            print("Property successfully removed.")
    except OverWeakeningException as e:
        print(f"FAIL: Should not have rejected -> {e}")

if __name__ == "__main__":
    main()
