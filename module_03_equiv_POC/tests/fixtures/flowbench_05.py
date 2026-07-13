
from src.lifter import WIRLifter, LifterConfig

# 1. Bypassing the file system by defining the loop WIR directly
raw_wir = {
  "entry_node": "L0",
  "exit_node": "L5",
  "nodes": [
    {"id": "L0", "type": "entry", "successors": ["L1"], "predecessors": [], "data_vars": []},
    {"id": "L1", "type": "task", "successors": ["L2"], "predecessors": ["L0"], "code": ["folder = Box_Folder__3_0_0__create_Folder()"], "data_vars": ["folder"]},
    {"id": "L2", "type": "task", "successors": ["L3"], "predecessors": ["L1"], "code": ["accounts = Salesforce_Account__5_0_0__retrievewithwhere_Account()"], "data_vars": ["accounts"]},
    {"id": "L3", "type": "loop", "successors": ["L4", "L5"], "predecessors": ["L2", "L4"], "guard": "iter accounts", "ast_type": "For", "control_vars": ["accounts"]},
    {"id": "L4", "type": "task", "successors": ["L3"], "predecessors": ["L3"], "code": ["file = Box_File__3_0_0__create_File()"], "data_vars": ["file"]},
    {"id": "L5", "type": "exit", "successors": [], "predecessors": ["L3"], "data_vars": []}
  ],
  "edges": [
    {"source": "L0", "target": "L1", "guard": None},
    {"source": "L1", "target": "L2", "guard": None},
    {"source": "L2", "target": "L3", "guard": None},
    {"source": "L3", "target": "L4", "guard": "iter accounts"},
    {"source": "L4", "target": "L3", "guard": None},
    {"source": "L3", "target": "L5", "guard": "not iter accounts"}
  ],
  "certificate": {
    "version": "V3",
    "node_coverage": 1.0,
    "edge_coverage": 1.0,
    "guard_success_rate": 1.0,
    "abort": False,
    "message": "Loop sequence extracted."
  }
}

# 2. Run the lifter with loop_max=3
lifter = WIRLifter(LifterConfig(loop_max=3, confidence_threshold=0.95))
lts_list = lifter.lift(raw_wir)
lts = lts_list[0]

# 3. Print the results for your manual validation
print("STATES:")
for sid, meta in lts.states.items():
    print(f"  {sid}: {meta}")

print("\nTRANSITIONS:")
for src, tgt, lbl in lts.transitions:
    print(f"  {src} ──[{lbl}]──> {tgt}")