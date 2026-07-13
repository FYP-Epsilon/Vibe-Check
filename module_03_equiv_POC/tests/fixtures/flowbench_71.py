from src.lifter import WIRLifter, LifterConfig

# 1. Defining the WIR for the Mid-Sequence Linear Insertion
raw_wir = {
  "entry_node": "L0",
  "exit_node": "L5",
  "nodes": [
    {"id": "L0", "type": "entry", "successors": ["L1"], "predecessors": [], "data_vars": []},
    {"id": "L1", "type": "task", "successors": ["L2"], "predecessors": ["L0"], "code": ["topic = Amazon_SNS_Topic__3_0_0__create_Topic()"], "data_vars": ["topic"]},
    {"id": "L2", "type": "task", "successors": ["L3"], "predecessors": ["L1"], "code": ["attachment = Asana_Attachments__2_0_0__create_Attachments()"], "data_vars": ["attachment"]},
    {"id": "L3", "type": "task", "successors": ["L4"], "predecessors": ["L2"], "code": ["message = Amazon_SQS_Messages__3_0_0__PUTMESSAGE_Messages()"], "data_vars": ["message"]},
    {"id": "L4", "type": "task", "successors": ["L5"], "predecessors": ["L3"], "code": ["update_topic = Amazon_SNS_Topic__3_0_0__updatewithwhere_Topic()"], "data_vars": ["update_topic"]},
    {"id": "L5", "type": "exit", "successors": [], "predecessors": ["L4"], "data_vars": []}
  ],
  "edges": [
    {"source": "L0", "target": "L1", "guard": None},
    {"source": "L1", "target": "L2", "guard": None},
    {"source": "L2", "target": "L3", "guard": None},
    {"source": "L3", "target": "L4", "guard": None},
    {"source": "L4", "target": "L5", "guard": None}
  ],
  "certificate": {
    "version": "V3",
    "node_coverage": 1.0,
    "edge_coverage": 1.0,
    "guard_success_rate": 1.0,
    "abort": False,
    "message": "Linear mid-sequence insertion extracted."
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