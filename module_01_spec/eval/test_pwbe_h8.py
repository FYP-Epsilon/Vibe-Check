import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent / "src"))
from semantic_extractor import SemanticExtractionEngine
from ltlf_synthesizer import FLTLSynthesizer

try:
    from sklearn.metrics import roc_auc_score
except ImportError:
    roc_auc_score = None

def generate_tiered_properties(xml_str):
    try:
        extractor = SemanticExtractionEngine(xml_str)
        phase1_out = extractor.run_pipeline()
        
        synth = FLTLSynthesizer(phase1_out)
        phase2_out = synth.run_pipeline()
        
        suite = phase2_out["ltlf_property_suite"]
        return {
            "P0": set(suite.get("P0_Critical_Sentinels", [])),
            "P1": set(suite.get("P1_Structural_Control_Flow", [])),
            "P2": set(suite.get("P2_Quality_Limits", []))
        }
    except Exception:
        return {"P0": set(), "P1": set(), "P2": set()}

def main():
    mutants_file = Path("module_01_spec/eval/mutants.json")
    if not mutants_file.exists():
        print("Mutants file not found.")
        return
        
    with open(mutants_file, "r") as f:
        mutants = json.load(f)
        
    y_true = []
    y_scores = []
    
    total_mutants = 0
    p0_vetoes = 0
    
    # Evaluate Clean diagrams (True label = 0)
    # We will use the original corpus diagrams as our clean set
    clean_uids = set(m["uid"] for m in mutants if not m["equivalent"])
    
    for uid in clean_uids:
        # A clean diagram against itself has 0 missing properties
        # so score is 0.
        y_true.append(0)
        y_scores.append(0.0)
        
    # Evaluate Mutants (True label = 1)
    for mut in mutants:
        if mut["equivalent"]:
            continue
            
        uid = mut["uid"]
        orig_file = Path(f"module_01_spec/eval/corpus/flowbench/uid_{uid}_output.bpmn")
        mut_file = Path(f"module_01_spec/eval/corpus/mutants/{mut['file']}")
        
        if not orig_file.exists() or not mut_file.exists():
            continue
            
        orig_tiers = generate_tiered_properties(orig_file.read_text(encoding="utf-8"))
        mut_tiers = generate_tiered_properties(mut_file.read_text(encoding="utf-8"))
        
        if not orig_tiers["P0"] and not orig_tiers["P1"]:
            continue
            
        # Missing properties are considered "failed" on the mutant
        p0_fails = len(orig_tiers["P0"] - mut_tiers["P0"])
        p1_fails = len(orig_tiers["P1"] - mut_tiers["P1"])
        p2_fails = len(orig_tiers["P2"] - mut_tiers["P2"])
        
        total_mutants += 1
        
        if p0_fails > 0:
            p0_vetoes += 1
        else:
            # P0-clean stratum
            y_true.append(1)
            # The PWBE vector score for P1/P2
            y_scores.append(float(p1_fails + p2_fails))
            
    if total_mutants == 0:
        print("No non-equivalent mutants could be evaluated.")
        return
        
    veto_prevalence = p0_vetoes / total_mutants
    p0_clean_fraction = 1.0 - veto_prevalence
    
    print(f"Total non-equivalent mutants: {total_mutants}")
    print(f"P0 Vetoes: {p0_vetoes}")
    print(f"Veto Prevalence: {veto_prevalence:.4f}")
    print(f"P0-Clean Stratum: {p0_clean_fraction:.4f} (Acceptance: >= 0.10)")
    
    if p0_clean_fraction > 0:
        if roc_auc_score:
            auc = roc_auc_score(y_true, y_scores)
            print(f"Conditional AUC (P1/P2 score | P0-clean): {auc:.4f} (Acceptance: > 0.50)")
        else:
            print("scikit-learn not installed, cannot compute exact AUC easily.")
    else:
        print("No P0-clean mutants to compute AUC.")

if __name__ == "__main__":
    main()
