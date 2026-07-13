import json
import xml.etree.ElementTree as ET
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent / "src"))
from semantic_extractor import SemanticExtractionEngine
from fidelity_index import SemanticFidelityIndex

NS = {
    'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)

def extract_graph(xml_str):
    engine = SemanticExtractionEngine(xml_str)
    return engine.run_pipeline()["semantic_graph"]

def drop_random_element(tree, tag_name):
    root = tree.getroot()
    # Find all elements matching tag
    elements = root.findall(f'.//{tag_name}', NS)
    if not elements:
        return False
    
    # We need to find the parent to remove the element.
    # ET doesn't have a direct parent pointer, so we search for it.
    elem_to_remove = elements[0]
    parent_map = {c: p for p in root.iter() for c in p}
    parent = parent_map.get(elem_to_remove)
    if parent is not None:
        parent.remove(elem_to_remove)
        return True
    return False

def drop_random_task(tree):
    return drop_random_element(tree, 'bpmn:task')

def drop_random_edge(tree):
    return drop_random_element(tree, 'bpmn:sequenceFlow')

def build_chain_and_test(file_path: Path) -> int:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            xml_str = f.read()
    except Exception:
        return -1
    
    orig_graph = extract_graph(xml_str)
    
    tree = ET.ElementTree(ET.fromstring(xml_str))
    
    sfis = [1.0] # Step 0 is original, SFI = 1.0
    violations = 0
    
    # 5 step chain: drop task, drop edge, drop task, drop edge, drop task
    for step in range(5):
        if step % 2 == 0:
            success = drop_random_task(tree)
        else:
            success = drop_random_edge(tree)
            
        if not success:
            break
            
        mut_xml = ET.tostring(tree.getroot(), encoding='unicode')
        mut_graph = extract_graph(mut_xml)
        
        sfi = SemanticFidelityIndex.calculate(orig_graph, mut_graph)
        
        # Check monotonicity
        if sfi > sfis[-1] + 1e-5: # epsilon tolerance
            violations += 1
            
        sfis.append(sfi)
        
    return violations

def main():
    with open("module_01_spec/eval/split.json", "r") as f:
        split = json.load(f)
    
    eval_uids = split.get("EVAL", [])
    if not eval_uids:
        print("No EVAL uids found.")
        return
        
    chains_tested = 0
    total_violations = 0
    
    for uid in eval_uids[:20]: # 20 nested-perturbation chains
        bpmn_path = Path(f"module_01_spec/eval/corpus/flowbench/uid_{uid}_output.bpmn")
        if not bpmn_path.exists():
            continue
            
        v = build_chain_and_test(bpmn_path)
        if v >= 0:
            chains_tested += 1
            total_violations += v
            
    if chains_tested == 0:
        print("Could not test any chains.")
        return
        
    violation_rate = total_violations / (chains_tested * 5.0) # max 5 steps per chain
    print(f"Tested {chains_tested} chains (up to 5 steps each).")
    print(f"Total monotonicity violations: {total_violations}")
    print(f"Violation rate: {violation_rate:.4f} (Acceptance: <= 0.05)")

if __name__ == "__main__":
    main()
