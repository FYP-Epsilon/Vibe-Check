from src.lifter import WIRLifter, LifterConfig

# 1. Defining the WIR for the Conditional Replacement (Create -> Retrieve)
raw_wir = {
  "entry_node": "L0",
  "exit_node": "L7",
  "nodes": [
    {"id": "L0", "type": "entry", "successors": ["L1"], "predecessors": [], "data_vars": []},
    {"id": "L1", "type": "task", "successors": ["L2"], "predecessors": ["L0"], "code": ["leads = Salesforce_Lead__5_0_0__retrievewithwhere_Lead()"], "data_vars": ["leads"]},
    {"id": "L2", "type": "loop", "successors": ["L3", "L7"], "predecessors": ["L1", "L6"], "guard": "iter leads", "ast_type": "For"},
    {"id": "L3", "type": "decision", "successors": ["L4", "L5"], "predecessors": ["L2"], "code": [], "data_vars": ["lead"]},
    {"id": "L4", "type": "task", "successors": ["L6"], "predecessors": ["L3"], "code": ["campaigns = Salesforce_Campaign__8_0_0__retrievewithwhere_Campaign()"], "data_vars": ["campaigns"]},
    {"id": "L5", "type": "task", "successors": ["L6"], "predecessors": ["L3"], "code": ["update_lead = Salesforce_Lead__5_0_0__updatewithwhere_Lead()"], "data_vars": ["update_lead"]},
    {"id": "L6", "type": "task", "successors": ["L2"], "predecessors": ["L4", "L5"], "code": [], "data_vars": []},
    {"id": "L7", "type": "exit", "successors": [], "predecessors": ["L2"], "data_vars": []}
  ],
  "edges": [
    {"source": "L0", "target": "L1", "guard": None},
    {"source": "L1", "target": "L2", "guard": None},
    {"source": "L2", "target": "L3", "guard": "iter leads"},
    {"source": "L3", "target": "L4", "guard": "lead.rating == 'high'"},
    {"source": "L3", "target": "L5", "guard": "lead.rating != 'high'"},
    {"source": "L4", "target": "L6", "guard": None},
    {"source": "L5", "target": "L6", "guard": None},
    {"source": "L6", "target": "L2", "guard": None},
    {"source": "L2", "target": "L7", "guard": "not iter leads"}
  ],
  "certificate": {
    "version": "V3",
    "node_coverage": 1.0,
    "edge_coverage": 1.0,
    "guard_success_rate": 1.0,
    "abort": False,
    "message": "Conditional loop-branch replacement verified."
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