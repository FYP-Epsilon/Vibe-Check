import ast
import yaml
import json
from pathlib import Path
from typing import Set, Tuple, List, Dict
import sys

# Add src to path so we can import SemanticExtractionEngine
sys.path.append(str(Path(__file__).parent.parent / "src"))
from semantic_extractor import SemanticExtractionEngine

class SequenceParser(ast.NodeVisitor):
    def __init__(self):
        self.tasks = set()
        self.edges = set()
        self.xor_branches = set()
        self.current_predecessors = {"Start"}

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            task_name = node.func.id
            self.tasks.add(task_name)
            for p in self.current_predecessors:
                self.edges.add((p, task_name))
            self.current_predecessors = {task_name}
        elif isinstance(node.func, ast.Attribute):
            task_name = node.func.attr
            self.tasks.add(task_name)
            for p in self.current_predecessors:
                self.edges.add((p, task_name))
            self.current_predecessors = {task_name}
        self.generic_visit(node)

    def visit_If(self, node):
        entry_preds = set(self.current_predecessors)
        
        # condition text
        cond = ast.unparse(node.test)
        
        self.current_predecessors = set(entry_preds)
        for stmt in node.body:
            self.visit(stmt)
        then_preds = set(self.current_predecessors)
        
        for p in (then_preds - entry_preds):
            self.xor_branches.add((cond, p))

        self.current_predecessors = set(entry_preds)
        for stmt in node.orelse:
            self.visit(stmt)
        else_preds = set(self.current_predecessors)

        for p in (else_preds - entry_preds):
            self.xor_branches.add((f"!({cond})", p))

        self.current_predecessors = then_preds | else_preds

    def visit_For(self, node):
        entry_preds = set(self.current_predecessors)
        for stmt in node.body:
            self.visit(stmt)
        # Back edges for loops
        for p in self.current_predecessors:
            for ep in entry_preds:
                self.edges.add((p, ep))
        self.current_predecessors = self.current_predecessors | entry_preds

    def visit_While(self, node):
        self.visit_For(node)

def parse_sequence(sequence_lines: List[str]) -> SequenceParser:
    code = "\n".join(sequence_lines)
    tree = ast.parse(code)
    parser = SequenceParser()
    parser.visit(tree)
    return parser

def extract_from_bpmn(bpmn_path: Path):
    with open(bpmn_path, "r", encoding="utf-8") as f:
        xml_string = f.read()
    
    engine = SemanticExtractionEngine(xml_string)
    result = engine.run_pipeline()
    graph = result["semantic_graph"]
    
    tasks = set()
    node_name_map = {}
    start_nodes = set()
    for state in graph["states"]:
        if state["node_type"] == "startEvent":
            start_nodes.add(state["node_id"])
        
        # M1 cleans names: clean_name = node_name.replace(" ", "_").replace("\n", "_")
        # And it uses atomic_propositions for tasks: "start(X)", "done(X)"
        props = state.get("atomic_propositions", [])
        name = props[0]
        if name.startswith("start(") and name.endswith(")"):
            name = name[6:-1]
            tasks.add(name)
        node_name_map[state["node_id"]] = name

    edges = set()
    for edge in graph["edges"]:
        u_id = edge["source_id"]
        v_id = edge["target_id"]
        u_name = node_name_map.get(u_id, u_id)
        v_name = node_name_map.get(v_id, v_id)
        
        if u_id in start_nodes:
            u_name = "Start"
            
        # In BPMN, a gateway is a node, so edge is A -> Gateway -> B
        # Let's simplify by just looking at task ordering. 
        # But for exact matching we might need path reachability ignoring gateways.
        # This is a basic edge extraction
        edges.add((u_name, v_name))
        
    return tasks, edges

def calculate_f1(gold: set, pred: set):
    tp = len(gold & pred)
    fp = len(pred - gold)
    fn = len(gold - pred)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1

def main():
    yaml_path = Path("module_01_spec/eval/corpus/flowbench/conditional_ootb.yaml")
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    total_metrics = {"tasks": {"tp": 0, "fp": 0, "fn": 0}}
    
    for test in data.get("tests", []):
        uid = test["_metadata"]["uid"]
        sequence = test["expected_output"]["sequence"]
        
        parser = parse_sequence(sequence)
        gold_tasks = parser.tasks
        
        bpmn_path = Path(f"module_01_spec/eval/corpus/flowbench/uid_{uid}_output.bpmn")
        if not bpmn_path.exists():
            continue
            
        pred_tasks, _ = extract_from_bpmn(bpmn_path)
        
        tp = len(gold_tasks & pred_tasks)
        fp = len(pred_tasks - gold_tasks)
        fn = len(gold_tasks - pred_tasks)
        
        total_metrics["tasks"]["tp"] += tp
        total_metrics["tasks"]["fp"] += fp
        total_metrics["tasks"]["fn"] += fn
        
    tp = total_metrics["tasks"]["tp"]
    fp = total_metrics["tasks"]["fp"]
    fn = total_metrics["tasks"]["fn"]
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    report = f"""# Module 01 - E2 Structural Evaluation
    
## Overall Task Recognition
- **Precision**: {precision:.4f}
- **Recall**: {recall:.4f}
- **Micro-F1**: {f1:.4f}

*(Note: Edge and XOR metrics logic requires reachability analysis over BPMN graphs due to intermediate gateways. For now, task presence micro-F1 is reported.)*
"""
    report_path = Path("module_01_spec/eval/reports/m1_e2_structural.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report)
    print(f"Generated {report_path}")
    print(report)

if __name__ == "__main__":
    main()
