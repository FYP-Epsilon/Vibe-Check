# Phase 5: Reverse Process Mining Alignment

## Objective
To provide a heuristic, A-Priori verification of the execution model using standard Process Mining techniques.

## A-Priori Execution (Virtual Tracing)
Standard process mining happens *after* a software is written and deployed (analyzing database logs). `process_mining_alignment.py` executes **Reverse Process Mining**. Before any code is written, it uses the generated LTLf properties to "virtually execute" the workflow, outputting thousands of hypothetical event logs (Execution Traces).

## EAS Calculation
Using `pm4py`, the module takes these virtual logs and measures their fitness and precision against the original BPMN diagram. This produces an **Extraction Alignment Score (EAS)**, proving definitively that the LTLf rules the system just generated perfectly encapsulate the business logic diagram the user provided.
