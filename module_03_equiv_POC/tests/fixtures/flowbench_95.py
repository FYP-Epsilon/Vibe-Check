from src.lifter import WIRLifter, LifterConfig

# 1. Defining the WIR for the Nested Conditional Replacement (Create -> Update)
raw_wir = {
  "entry_node": "L0",
  "exit_node": "L6",
  "nodes": [
    {"id": "L0", "type": "entry", "successors": ["L1"], "predecessors": [], "data_vars": []},
    {"id": "L1", "type": "task", "successors": ["L2"], "predecessors": ["L0"], "code": ["contacts = Salesforce_Contact__5_0_0__retrievewithwhere_Contact()"], "data_vars": ["contacts"]},
    {"id": "L2", "type": "loop", "successors": ["L3", "L6"], "predecessors": ["L1", "L5"], "guard": "iter contacts", "ast_type": "For"},
    {"id": "L3", "type": "decision", "successors": ["L4", "L5"], "predecessors": ["L2"], "code": [], "data_vars": ["contact"]},
    {"id": "L4", "type": "task", "successors": ["L5"], "predecessors": ["L3"], "code": ["updated_contact = Salesforce_Contact__5_0_0__updatewithwhere_Contact()"], "data_vars": ["updated_contact"]},
    {"id": "L5", "type": "task", "successors": ["L2"], "predecessors": ["L3", "L4"], "code": ["task = user_task(\"check compliance\")"], "data_vars": ["task"]},
    {"id": "L6", "type": "exit", "successors": [], "predecessors": ["L2"], "data_vars": []}
  ],
  "edges": [
    {"source": "L0", "target": "L1", "guard": None},
    {"source": "L1", "target": "L2", "guard": None},
    {"source": "L2", "target": "L3", "guard": "iter contacts"},
    {"source": "L3", "target": "L4", "guard": "contact.CleanStatus == 'new'"},
    {"source": "L3", "target": "L5", "guard": "contact.CleanStatus != 'new'"},
    {"source": "L4", "target": "L5", "guard": None},
    {"source": "L5", "target": "L2", "guard": None},
    {"source": "L2", "target": "L6", "guard": "not iter contacts"}
  ],
  "certificate": {
    "version": "V3",
    "node_coverage": 1.0,
    "edge_coverage": 1.0,
    "guard_success_rate": 1.0,
    "abort": False,
    "message": "Conditional replacement in loop extracted."
  }
}

# 2. Run the lifter
lifter = WIRLifter(LifterConfig(loop_max=2, confidence_threshold=0.90))
lts_list = lifter.lift(raw_wir)
lts = lts_list[0]

# 3. Print results for validation
print("STATES:")
for sid, meta in lts.states.items():
    print(f"  {sid}: {meta}")

print("\nTRANSITIONS:")
for src, tgt, lbl in lts.transitions:
    print(f"  {src} ──[{lbl}]──> {tgt}")