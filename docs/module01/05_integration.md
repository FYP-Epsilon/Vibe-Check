# Module 01 Integration & Decoupled Handoff

## Objective
To ensure perfect, mathematically sound decoupling between Module 01 (Specification Extraction) and Modules 02/03 (Code Verification).

## API Orchestration (`api.py`)
Module 01 is designed as a standalone orchestrator. When `run_module_01_pipeline()` is executed, it runs the entire 4-phase validation architecture, returning a JSON certificate of the results.
The pipeline outputs distinct JSON payloads for the downstream modules.

## Module 02 Output (`module_02_input.json`)
Module 02 (IR Extraction) is responsible for dynamically tracing the LLM's Python code execution. It uses `sys.settrace`. 
To ensure it operates with lightning speed and zero overhead on standard Python libraries, Module 01 feeds it:
* `semantic_graph`: The full Kripke state structure.
* `task_patterns`: A string array of exactly which function names to listen for (e.g., `["Check_Inventory", "Ship_Order"]`). 

**Crucial Note:** Module 02 does *not* receive LTLf rules, as that would cause Z3 path explosion overhead. It only extracts traces.

## Module 03 Output (`module_03_input.json`)
Module 03 (The Verification Engine) is the mathematical judge. It compares the extracted traces against the rules.
Module 01 feeds it:
* `semantic_graph`: The state structure.
* `loop_bound_documented`: The maximum limit of loops allowed (derived from P2_Quality_Limits).
* `ltlf_property_suite`: The absolute core payload. This contains `P0`, `P1`, `P2`, and the newly synthesized `P3_Adversarial_Defenses`. Module 03 uses these exact strings alongside C++ SPOT to perform Stuttering Bisimulation proof checking on the LLM's code execution traces.
