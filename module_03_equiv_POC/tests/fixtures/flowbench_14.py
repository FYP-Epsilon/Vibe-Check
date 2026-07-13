from src.lifter import WIRLifter, LifterConfig

# 1. Defining the WIR for the Nested Conditional Insertion
raw_wir = {
  "entry_node": "L0",
  "exit_node": "L6",
  "nodes": [
    {"id": "L0", "type": "entry", "successors": ["L1"], "predecessors": [], "data_vars": []},
    {"id": "L1", "type": "task", "successors": ["L2"], "predecessors": ["L0"], "code": ["campaigns = Marketo_campaigns__3_0_0__retrievewithwhere_campaigns()"], "data_vars": ["campaigns"]},
    {"id": "L2", "type": "loop", "successors": ["L3", "L6"], "predecessors": ["L1", "L5"], "guard": "iter campaigns", "ast_type": "For"},
    {"id": "L3", "type": "decision", "successors": ["L4", "L5"], "predecessors": ["L2"], "code": [], "data_vars": ["campaign"]},
    {"id": "L4", "type": "task", "successors": ["L5"], "predecessors": ["L3"], "code": ["applicants = Microsoft_Dynamics_365_for_Finance_and_Operations_Applicant__2_0_0__retrievewithwhere_Applicant()", "board = monday_com_Board__2_0_0__create_Board()"], "data_vars": ["applicants", "board"]},
    {"id": "L5", "type": "task", "successors": ["L2"], "predecessors": ["L3", "L4"], "code": [], "data_vars": []},
    {"id": "L6", "type": "exit", "successors": [], "predecessors": ["L2"], "data_vars": []}
  ],
  "edges": [
    {"source": "L0", "target": "L1", "guard": None},
    {"source": "L1", "target": "L2", "guard": None},
    {"source": "L2", "target": "L3", "guard": "iter campaigns"},
    {"source": "L3", "target": "L4", "guard": "campaign.type == 'Finance'"},
    {"source": "L3", "target": "L5", "guard": "campaign.type != 'Finance'"},
    {"source": "L4", "target": "L5", "guard": None},
    {"source": "L5", "target": "L2", "guard": None},
    {"source": "L2", "target": "L6", "guard": "not iter campaigns"}
  ],
  "certificate": {
    "version": "V3",
    "node_coverage": 1.0,
    "edge_coverage": 1.0,
    "guard_success_rate": 1.0,
    "abort": False,
    "message": "Conditional task insertion in loop extracted."
  }
}

# 2. Run the lifter with loop_max=2
lifter = WIRLifter(LifterConfig(loop_max=2, confidence_threshold=0.90))
lts_list = lifter.lift(raw_wir)
lts = lts_list[0]

# 3. Print the results for manual validation
print("STATES:")
for sid, meta in lts.states.items():
    print(f"  {sid}: {meta}")

print("\nTRANSITIONS:")
for src, tgt, lbl in lts.transitions:
    print(f"  {src} ──[{lbl}]──> {tgt}")