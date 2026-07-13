# Open python intepreter/Open the Python shell:
# By typing python3 and hit Enter.

# Make sure the path - cd module_03_equiv_POC

# Commnd should be - (base) root@TheodaMSI:/home/theoda/Vibe-Check/module_03_equiv_POC# python3

from src.lifter import WIRLifter, LifterConfig

# 1. Bypassing the file system by defining the linear WIR directly
raw_wir = {
  "entry_node": "L0",
  "exit_node": "L3",
  "nodes": [
    {"id": "L0", "type": "entry", "successors": ["L1"], "predecessors": [], "data_vars": []},
    {"id": "L1", "type": "task", "successors": ["L2"], "predecessors": ["L0"], "code": ["issue = Jira_Issue__2_0_0__create_Issue()"], "data_vars": ["issue"]},
    {"id": "L2", "type": "task", "successors": ["L3"], "predecessors": ["L1"], "code": ["repository = GitHub_Repository__3_0_0__create_Repository()"], "data_vars": ["repository"]},
    {"id": "L3", "type": "exit", "successors": [], "predecessors": ["L2"], "data_vars": []}
  ],
  "edges": [
    {"source": "L0", "target": "L1", "guard": None},
    {"source": "L1", "target": "L2", "guard": None},
    {"source": "L2", "target": "L3", "guard": None}
  ],
  "certificate": {
    "version": "V3",
    "node_coverage": 1.0,
    "edge_coverage": 1.0,
    "guard_success_rate": 0.95,
    "abort": False,
    "message": "Linear sequence extracted."
  }
}

# 2. Run the lifter
# Using a confidence threshold of 0.90 just to be safe with the 0.95 payload
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