# Phase 3: PWBE Mutation & Adversarial Red-Teaming

## Objective
To actively prove that the generated LTLf properties are structurally sound and bulletproof against Generative AI deception.

## PWBE (Property-Weighted Bisimulation Equivalence)
Before handing off rules to downstream modules, `mutation_refiner.py` acts as a chaotic actor. It intentionally breaks the semantic graph:
* Substitutes `exclusiveGateway` for `parallelGateway`.
* Deletes random sequence flows.
* Inverts logic conditions.

It then executes symbolic traces against the LTLf property suite to ensure the rules "catch" the mutations. If a mutant survives (i.e., the rules failed to catch the error), it synthesizes a graph-topology constraint to kill it.

## The Core Novelty: Adversarial Formal Specification
Traditional formal methods are passive. VibeCheck is proactive. 
Using `adversarial_generator.py`, the engine utilizes an LLM (Red-Team Agent) to intentionally hallucinate **Deceptive Traces**—execution paths that attempt to bypass business rules while appearing structurally sound (e.g., starting an order, skipping payment, and instantly shipping).

The engine parses these hallucinations and automatically compiles them into **Killer Properties** (e.g., `!(F(done(Ship) & !O(done(Payment))))`). These are saved under a new suite called `P3_Adversarial_Defenses`. This guarantees the framework is mathematically armored against future LLM trickery.
