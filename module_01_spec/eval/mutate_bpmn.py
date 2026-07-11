import os
import json
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {
    'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
    'bpmndi': 'http://www.omg.org/spec/BPMN/20100524/DI',
    'dc': 'http://www.omg.org/spec/DD/20100524/DC',
    'di': 'http://www.omg.org/spec/DD/20100524/DI'
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)

def generate_split(bpmn_files):
    split = {"CALIB": [], "EVAL": []}
    for f in bpmn_files:
        uid = int(f.stem.split('_')[1])
        h = int(hashlib.sha1(str(uid).encode()).hexdigest(), 16)
        if h % 10 < 3:
            split["CALIB"].append(uid)
        else:
            split["EVAL"].append(uid)
    return split

def mutate_gateway_type_swap(tree, uid, mutants_list, out_dir):
    root = tree.getroot()
    gateways = root.findall('.//bpmn:exclusiveGateway', NS)
    for g in gateways:
        g.tag = f"{{{NS['bpmn']}}}parallelGateway"
        target_id = g.get("id")
        out_name = f"uid_{uid}_mut_gts_{target_id}.bpmn"
        tree.write(out_dir / out_name, encoding='utf-8', xml_declaration=True)
        mutants_list.append({
            "uid": uid,
            "operator": "gateway_type_swap",
            "target_element_id": target_id,
            "file": out_name,
            "equivalent": False
        })
        # revert
        g.tag = f"{{{NS['bpmn']}}}exclusiveGateway"

def mutate_equivalent_whitespace(tree, uid, mutants_list, out_dir):
    root = tree.getroot()
    tasks = root.findall('.//bpmn:task', NS)
    for t in tasks:
        name = t.get("name", "")
        if name:
            t.set("name", name + " ")
            target_id = t.get("id")
            out_name = f"uid_{uid}_mut_eqw_{target_id}.bpmn"
            tree.write(out_dir / out_name, encoding='utf-8', xml_declaration=True)
            mutants_list.append({
                "uid": uid,
                "operator": "equivalent_whitespace",
                "target_element_id": target_id,
                "file": out_name,
                "equivalent": True
            })
            # revert
            t.set("name", name)

def main():
    corpus_dir = Path("module_01_spec/eval/corpus/flowbench")
    out_dir = Path("module_01_spec/eval/corpus/mutants")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    bpmn_files = list(corpus_dir.glob("uid_*_output.bpmn"))
    
    # 1. Generate Split
    split = generate_split(bpmn_files)
    with open("module_01_spec/eval/split.json", "w") as f:
        json.dump(split, f, indent=2)
    print("Generated eval/split.json")
    
    # 2. Write Operating Point
    op_point = """# Operating Point Rule
A mutant is *detected* iff the frozen post-Phase-3 property suite synthesized from the **unmutated** diagram, evaluated by the checker on the **mutant's** graph, reports >=1 violated P0 or P1 property.
"""
    Path("module_01_spec/eval/OPERATING_POINT.md").write_text(op_point)
    print("Generated eval/OPERATING_POINT.md")

    # 3. Mutate
    mutants_list = []
    for f in bpmn_files:
        uid = int(f.stem.split('_')[1])
        try:
            tree = ET.parse(f)
            mutate_gateway_type_swap(tree, uid, mutants_list, out_dir)
            mutate_equivalent_whitespace(tree, uid, mutants_list, out_dir)
        except Exception as e:
            print(f"Error mutating {f}: {e}")

    with open("module_01_spec/eval/mutants.json", "w") as f:
        json.dump(mutants_list, f, indent=2)
    print(f"Generated {len(mutants_list)} external XML mutants in {out_dir}")

if __name__ == "__main__":
    main()
