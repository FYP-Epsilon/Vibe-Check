from src.lifter import WIRLifter, LifterConfig

# 1. Defining the WIR for the Linear Update
raw_wir = {
  "entry_node": "L0",
  "exit_node": "L4",
  "nodes": [
    {"id": "L0", "type": "entry", "successors": ["L1"], "predecessors": [], "data_vars": []},
    {"id": "L1", "type": "task", "successors": ["L2"], "predecessors": ["L0"], "code": ["asset = Zendesk_Service_asset__3_0_0__create_asset()"], "data_vars": ["asset"]},
    {"id": "L2", "type": "task", "successors": ["L3"], "predecessors": ["L1"], "code": ["person = Zendesk_Service_person__3_0_0__create_person()"], "data_vars": ["person"]},
    {"id": "L3", "type": "task", "successors": ["L4"], "predecessors": ["L2"], "code": ["ticket = Zendesk_Service_Ticket__2_0_0__create_Ticket()"], "data_vars": ["ticket"]},
    {"id": "L4", "type": "exit", "successors": [], "predecessors": ["L3"], "data_vars": []}
  ],
  "edges": [
    {"source": "L0", "target": "L1", "guard": None},
    {"source": "L1", "target": "L2", "guard": None},
    {"source": "L2", "target": "L3", "guard": None},
    {"source": "L3", "target": "L4", "guard": None}
  ],
  "certificate": {
    "version": "V3",
    "node_coverage": 1.0,
    "edge_coverage": 1.0,
    "guard_success_rate": 1.0,
    "abort": False,
    "message": "Linear update extracted."
  }
}

# 2. Run the lifter
lifter = WIRLifter(LifterConfig(loop_max=1, confidence_threshold=0.90))
lts_list = lifter.lift(raw_wir)
lts = lts_list[0]

# 3. Print results for validation
print("STATES:")
for sid, meta in lts.states.items():
    print(f"  {sid}: {meta}")

print("\nTRANSITIONS:")
for src, tgt, lbl in lts.transitions:
    print(f"  {src} ──[{lbl}]──> {tgt}")