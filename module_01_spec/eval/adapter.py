import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

# Standard BPMN 2.0 Namespaces
NS = {
    'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
    'bpmndi': 'http://www.omg.org/spec/BPMN/20100524/DI',
    'dc': 'http://www.omg.org/spec/DD/20100524/DC',
    'di': 'http://www.omg.org/spec/DD/20100524/DI'
}

def adapt_bpmn(file_path: Path):
    try:
        tree = ET.parse(file_path)
    except ET.ParseError as e:
        print(f"Error parsing {file_path}: {e}")
        return False

    root = tree.getroot()
    modified = False

    # Find all exclusive gateways
    for gateway in root.findall('.//bpmn:exclusiveGateway', NS):
        name = gateway.get('name', '')
        match = re.match(r'Decision:\s*(.+)', name, re.IGNORECASE)
        if match:
            predicate = match.group(1).strip()
            gateway_id = gateway.get('id')
            
            # Find outgoing sequence flows
            # BPMN typically has <outgoing> elements, or we can just find sequenceFlows with sourceRef
            sequence_flows = root.findall(f".//bpmn:sequenceFlow[@sourceRef='{gateway_id}']", NS)
            
            if sequence_flows:
                # Attach to the first outgoing flow
                first_flow = sequence_flows[0]
                
                # Check if it already has a conditionExpression
                existing_cond = first_flow.find('bpmn:conditionExpression', NS)
                if existing_cond is None:
                    # Create conditionExpression
                    cond_expr = ET.Element(f"{{{NS['bpmn']}}}conditionExpression")
                    cond_expr.text = predicate
                    first_flow.append(cond_expr)
                    modified = True

    if modified:
        # Register namespaces to keep the output clean
        for prefix, uri in NS.items():
            ET.register_namespace(prefix, uri)
        tree.write(file_path, encoding='utf-8', xml_declaration=True)
        return True
    return False

def main():
    corpus_dir = Path("module_01_spec/eval/corpus/flowbench")
    if not corpus_dir.exists():
        print(f"Corpus directory {corpus_dir} not found.")
        return

    bpmn_files = list(corpus_dir.glob("uid_*_output.bpmn"))
    adapted_count = 0

    for f in bpmn_files:
        if adapt_bpmn(f):
            adapted_count += 1

    print(f"Adapted {adapted_count} out of {len(bpmn_files)} BPMN files.")

if __name__ == "__main__":
    main()
