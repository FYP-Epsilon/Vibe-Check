from src.lifter import WIRLifter, LifterConfig

# 1. Defining the WIR for the Nested Conditional Deletion
raw_wir = {
  "entry_node": "L0",
  "exit_node": "L5",
  "nodes": [
    {"id": "L0", "type": "entry", "successors": ["L1"], "predecessors": [], "data_vars": []},
    {"id": "L1", "type": "task", "successors": ["L2"], "predecessors": ["L0"], "code": ["devices = Microsoft_Entra_ID_Devices__4_0_0__retrievewithwhere_Devices()"], "data_vars": ["devices"]},
    {"id": "L2", "type": "loop", "successors": ["L3", "L5"], "predecessors": ["L1", "L4"], "guard": "iter devices", "ast_type": "For"},
    {"id": "L3", "type": "decision", "successors": ["L4"], "predecessors": ["L2"], "code": [], "data_vars": ["device"]},
    {"id": "L4", "type": "task", "successors": ["L2"], "predecessors": ["L3"], "code": ["email = Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages()"], "data_vars": ["email"]},
    {"id": "L5", "type": "exit", "successors": [], "predecessors": ["L2"], "data_vars": []}
  ],
  "edges": [
    {"source": "L0", "target": "L1", "guard": None},
    {"source": "L1", "target": "L2", "guard": None},
    {"source": "L2", "target": "L3", "guard": "iter devices"},
    {"source": "L3", "target": "L4", "guard": "not device.isCompliant"},
    {"source": "L4", "target": "L2", "guard": None},
    {"source": "L2", "target": "L5", "guard": "not iter devices"}
  ],
  "certificate": {
    "version": "V3",
    "node_coverage": 1.0,
    "edge_coverage": 1.0,
    "guard_success_rate": 1.0,
    "abort": False,
    "message": "Conditional deletion in loop extracted."
  }
}

# 2. Run the lifter with loop_max=2
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