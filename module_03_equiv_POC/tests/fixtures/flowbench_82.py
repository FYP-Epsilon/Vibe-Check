from src.lifter import WIRLifter, LifterConfig

# 1. Defining the WIR for the Linear Replacement (Gmail -> Outlook)
raw_wir = {
  "entry_node": "L0",
  "exit_node": "L6",
  "nodes": [
    {"id": "L0", "type": "entry", "successors": ["L1"], "predecessors": [], "data_vars": []},
    {"id": "L1", "type": "task", "successors": ["L2"], "predecessors": ["L0"], "code": ["board = Trello_Board__2_0_0__create_Board()"], "data_vars": ["board"]},
    {"id": "L2", "type": "task", "successors": ["L3"], "predecessors": ["L1"], "code": ["board = Trello_Board__2_0_0__updatewithwhere_Board()"], "data_vars": ["board"]},
    {"id": "L3", "type": "task", "successors": ["L4"], "predecessors": ["L2"], "code": ["email = Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages()"], "data_vars": ["email"]},
    {"id": "L4", "type": "task", "successors": ["L5"], "predecessors": ["L3"], "code": ["card = Trello_Card__2_0_0__create_Card()"], "data_vars": ["card"]},
    {"id": "L5", "type": "task", "successors": ["L6"], "predecessors": ["L4"], "code": ["card = Trello_Member__2_0_0__create_Member()"], "data_vars": ["card"]},
    {"id": "L6", "type": "exit", "successors": [], "predecessors": ["L5"], "data_vars": []}
  ],
  "edges": [
    {"source": "L0", "target": "L1", "guard": None},
    {"source": "L1", "target": "L2", "guard": None},
    {"source": "L2", "target": "L3", "guard": None},
    {"source": "L3", "target": "L4", "guard": None},
    {"source": "L4", "target": "L5", "guard": None},
    {"source": "L5", "target": "L6", "guard": None}
  ],
  "certificate": {
    "version": "V3",
    "node_coverage": 1.0,
    "edge_coverage": 1.0,
    "guard_success_rate": 1.0,
    "abort": False,
    "message": "Linear replacement verified."
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