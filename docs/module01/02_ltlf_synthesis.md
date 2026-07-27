# Phase 2: LTLf Synthesis

## Objective
To mathematically instantiate Linear Temporal Logic on Finite Traces (LTLf) formulas from the Semantic Graph.

## Implicit Logic Inference (Zero Dead-Zone Protocol)
LLMs often hallucinate business logic when a BPMN diagram has implicit "Else" flows (e.g., an XOR gateway with a defined "If" path, but no explicitly drawn default path). `ltlf_synthesizer.py` identifies these gateways and automatically computes the mathematically inverted conjunction (e.g., `!(condition_A) && !(condition_B)`) to forcefully map the implicit default branch. If a gateway is hopelessly ambiguous, it throws a `VerificationException`.

## LTLf Property Suites
The engine synthesizes temporal logic strings into distinct suites:
1. **P0_Critical_Sentinels:** Defines existential laws. (e.g., `!done(Task) W start(Task)` — A task cannot be done until it starts).
2. **P1_Structural_Control_Flow:** Enforces strict execution ordering based on sequence flows and gateways (e.g., `!start(Ship_Order) W Inventory_Available?`).
3. **P2_Quality_Limits:** Injects bounded mathematical loop invariants to prevent infinite execution states (e.g., `G(iteration_count <= 10 -> F(process_complete))`).
