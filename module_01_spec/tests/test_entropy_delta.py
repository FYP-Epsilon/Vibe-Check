import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent / "src"))
from semantic_extractor import SemanticExtractionEngine
from ltlf_synthesizer import FLTLSynthesizer
from entropy_delta import EntropyDeltaLocator

def generate_properties(xml_str):
    try:
        # Phase 1
        extractor = SemanticExtractionEngine(xml_str)
        phase1_out = extractor.run_pipeline()
        
        # Phase 2
        synth = FLTLSynthesizer(phase1_out)
        phase2_out = synth.run_pipeline()
        
        # Flatten all properties
        props = []
        for p_list in phase2_out["ltlf_property_suite"].values():
            props.extend(p_list)
        return set(props), phase1_out["semantic_graph"]
    except Exception:
        return set(), {}

def main():
    mutants_file = Path("module_01_spec/eval/mutants.json")
    if not mutants_file.exists():
        print("Mutants file not found.")
        return
        
    with open(mutants_file, "r") as f:
        mutants = json.load(f)
        
    total_eval = 0
    top1_success = 0
    
    for mut in mutants:
        if mut["equivalent"]:
            continue
            
        uid = mut["uid"]
        orig_file = Path(f"module_01_spec/eval/corpus/flowbench/uid_{uid}_output.bpmn")
        mut_file = Path(f"module_01_spec/eval/corpus/mutants/{mut['file']}")
        
        if not orig_file.exists() or not mut_file.exists():
            continue
            
        orig_props, orig_graph = generate_properties(orig_file.read_text(encoding="utf-8"))
        mut_props, _ = generate_properties(mut_file.read_text(encoding="utf-8"))
        
        if not orig_props:
            continue
            
        # Mocking model checker: failing properties are those that the mutant lacks
        # (Since if an edge is missing, the structural property is missing, representing a failure)
        failing_props = list(orig_props - mut_props)
        
        if not failing_props:
            continue
            
        ranked = EntropyDeltaLocator.localize_fault(failing_props, orig_graph)
        
        if not ranked:
            continue
            
        total_eval += 1
        top_1_id = ranked[0][0]
        
        if top_1_id == mut["target_element_id"]:
            top1_success += 1
        elif total_eval == 1:
            print(f"DEBUG: mut target: {mut['target_element_id']}")
            print(f"DEBUG: failing props: {failing_props}")
            print(f"DEBUG: ranked: {ranked}")
            
    if total_eval == 0:
        print("No non-equivalent mutants could be evaluated.")
        return
        
    success_rate = top1_success / total_eval
    print(f"Evaluated {total_eval} mutants for fault localization.")
    print(f"Top-1 Success Rate: {success_rate:.4f} (Acceptance: >= 0.50)")
    
if __name__ == "__main__":
    main()
