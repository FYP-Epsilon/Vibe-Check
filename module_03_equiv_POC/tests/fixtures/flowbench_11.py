from src.lifter import WIRLifter, LifterConfig

# 1. Bypassing the file system by defining the Conditional Update WIR directly
# This models the 'expected_output' where Slack is replaced by Outlook in the 'high' branch
raw_wir = {
  "entry_node": "L0",
  "exit_node": "L5",
  "nodes": [
    {"id": "L0", "type": "entry", "successors": ["L1"], "predecessors": [], "data_vars": []},
    {"id": "L1", "type": "task", "successors": ["L2"], "predecessors": ["L0"], "code": ["incident = ServiceNow_incident__4_0_0__retrievewithwhere_incident()"], "data_vars": ["incident"]},
    {"id": "L2", "type": "decision", "successors": ["L3", "L4"], "predecessors": ["L1"], "code": [], "data_vars": ["incident"]},
    {"id": "L3", "type": "task", "successors": ["L5"], "predecessors": ["L2"], "code": ["issue = Jira_Issue__2_0_0__create_Issue()", "email = Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages()"], "data_vars": ["issue", "email"]},
    {"id": "L4", "type": "task", "successors": ["L5"], "predecessors": ["L2"], "code": ["issue = GitHub_Issue__3_0_0__create_Issue()"], "data_vars": ["issue"]},
    {"id": "L5", "type": "exit", "successors": [], "predecessors": ["L3", "L4"], "data_vars": []}
  ],
  "edges": [
    {"source": "L0", "target": "L1", "guard": None},
    {"source": "L1", "target": "L2", "guard": None},
    {"source": "L2", "target": "L3", "guard": "incident.priority == 'high'"},
    {"source": "L2", "target": "L4", "guard": "incident.priority != 'high'"},
    {"source": "L3", "target": "L5", "guard": None},
    {"source": "L4", "target": "L5", "guard": None}
  ],
  "certificate": {
    "version": "V3",
    "node_coverage": 1.0,
    "edge_coverage": 1.0,
    "guard_success_rate": 1.0,
    "abort": False,
    "message": "Conditional update extracted."
  }
}

# 2. Run the lifter
lifter = WIRLifter(LifterConfig(loop_max=3, confidence_threshold=0.90))
lts_list = lifter.lift(raw_wir)
lts = lts_list[0]

# 3. Print the results for your manual validation
print("STATES:")
for sid, meta in lts.states.items():
    print(f"  {sid}: {meta}")

print("\nTRANSITIONS:")
for src, tgt, lbl in lts.transitions:
    print(f"  {src} ──[{lbl}]──> {tgt}")