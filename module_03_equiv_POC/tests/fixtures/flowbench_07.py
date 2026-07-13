from src.lifter import WIRLifter, LifterConfig

# 1. Bypassing the file system by defining the WIR directly
raw_wir = {
  "entry_node": "L0",
  "exit_node": "L5",
  "nodes": [
    {"id": "L0", "type": "entry", "successors": ["L1"], "predecessors": [], "data_vars": []},
    {"id": "L1", "type": "task", "successors": ["L2"], "predecessors": ["L0"], "code": ["channels = Slack_channel__3_0_0__retrievewithwhere_channel()"], "data_vars": ["channels"]},
    {"id": "L2", "type": "loop", "successors": ["L3", "L5"], "predecessors": ["L1", "L4"], "guard": "iter channels", "ast_type": "For", "control_vars": ["channels"]},
    {"id": "L3", "type": "task", "successors": ["L4"], "predecessors": ["L2"], "code": ["users = Slack_user__4_0_0__retrievewithwhere_user()"], "data_vars": ["users"]},
    {"id": "L4", "type": "task", "successors": ["L2"], "predecessors": ["L3"], "code": ["task = user_task(\"validate credentials\")"], "data_vars": ["task"]},
    {"id": "L5", "type": "exit", "successors": [], "predecessors": ["L2"], "data_vars": []}
  ],
  "edges": [
    {"source": "L0", "target": "L1", "guard": None},
    {"source": "L1", "target": "L2", "guard": None},
    {"source": "L2", "target": "L3", "guard": "iter channels"},
    {"source": "L3", "target": "L4", "guard": None},
    {"source": "L4", "target": "L2", "guard": None},
    {"source": "L2", "target": "L5", "guard": "not iter channels"}
  ],
  "certificate": {
    "version": "V3",
    "node_coverage": 1.0,
    "edge_coverage": 1.0,
    "guard_success_rate": 1.0,
    "abort": False,
    "message": "Loop with nested user_task extracted."
  }
}

# 2. Run the lifter with loop_max=2 to keep the output readable
lifter = WIRLifter(LifterConfig(loop_max=2, confidence_threshold=0.95))
lts_list = lifter.lift(raw_wir)
lts = lts_list[0]

# 3. Print the results for your manual validation
print("STATES:")
for sid, meta in lts.states.items():
    print(f"  {sid}: {meta}")

print("\nTRANSITIONS:")
for src, tgt, lbl in lts.transitions:
    print(f"  {src} ──[{lbl}]──> {tgt}")