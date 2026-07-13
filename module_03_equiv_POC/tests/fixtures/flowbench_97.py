from src.lifter import WIRLifter, LifterConfig

# 1. Defining the WIR for the Loop-Body Replacement (Retrieve -> Create)
raw_wir = {
  "entry_node": "L0",
  "exit_node": "L4",
  "nodes": [
    {"id": "L0", "type": "entry", "successors": ["L1"], "predecessors": [], "data_vars": []},
    {"id": "L1", "type": "task", "successors": ["L2"], "predecessors": ["L0"], "code": ["repositories = GitHub_Repository__3_0_0__retrievewithwhere_Repository()"], "data_vars": ["repositories"]},
    {"id": "L2", "type": "loop", "successors": ["L3", "L4"], "predecessors": ["L1", "L3"], "guard": "iter repositories", "ast_type": "For"},
    {"id": "L3", "type": "task", "successors": ["L2"], "predecessors": ["L2"], "code": ["updated_issue = GitHub_Issue__3_0_0__create_Issue()"], "data_vars": ["updated_issue"]},
    {"id": "L4", "type": "exit", "successors": [], "predecessors": ["L2"], "data_vars": []}
  ],
  "edges": [
    {"source": "L0", "target": "L1", "guard": None},
    {"source": "L1", "target": "L2", "guard": None},
    {"source": "L2", "target": "L3", "guard": "iter repositories"},
    {"source": "L3", "target": "L2", "guard": None},
    {"source": "L2", "target": "L4", "guard": "not iter repositories"}
  ],
  "certificate": {
    "version": "V3",
    "node_coverage": 1.0,
    "edge_coverage": 1.0,
    "guard_success_rate": 1.0,
    "abort": False,
    "message": "Loop-body replacement verified."
  }
}

# 2. Run the lifter
lifter = WIRLifter(LifterConfig(loop_max=2, confidence_threshold=0.90))
lts_list = lifter.lift(raw_wir)
lts = lts_list[0]

# 3. Print results for manual validation
print("STATES:")
for sid, meta in lts.states.items():
    print(f"  {sid}: {meta}")

print("\nTRANSITIONS:")
for src, tgt, lbl in lts.transitions:
    print(f"  {src} ──[{lbl}]──> {tgt}")