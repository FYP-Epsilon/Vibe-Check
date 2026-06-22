# Phase 3 Master Integration Plan: The Role C Equivalence Checking Engine

## Objective
To implement a dynamic, mathematically rigorous, and memory-safe Equivalence Checking Engine (Module 03) that eliminates the "Verification Gap." The engine will dynamically ingest WIR payloads, strictly manage C++/Python memory boundaries using the SPOT library, and execute an optimized divergence-sensitive stuttering bisimulation to evaluate whether AI-generated code ($M_{code}$) is observationally equivalent to a golden specification ($M_{spec}$).

## 1. Dynamic Input Mapping & Lifecycle Integration

To move away from the legacy static file paths and isolated script execution, the pipeline will adopt a robust ingestion and lifecycle model:

### 1.1 Shared Memory Context (`bdd_dict` Lifecycle)
- **Constraint:** Synchronous product intersection requires that boolean variables (e.g., transition guards like `loan_approved == true`) map to the exact same integer ID in both automata.
- **Solution:** A single `spot::bdd_dict_ptr` must be instantiated at the start of a verification batch. 
- **Pybind11 Integration:** The Python layer will control the high-level orchestration, but the C++ layer will firmly own the memory. We will utilize `py::smart_holder` and `return_value_policy::reference_internal` to guarantee that Python's garbage collector does not prematurely destroy the shared dictionary while `twa_graph` instances remain active.

### 1.2 Dynamic Ingestion & Resolution
- **Endpoint Structure:** The C++ `AdvancedLifter` will expose an `ingest_wir(json_payload)` method.
- **Spec Resolution:** Upon receiving the JSON payload, the engine extracts the `spec_id` from the payload header. It dynamically queries the local artifact store (or database) to retrieve the corresponding $M_{spec}$ WIR baseline. Both the spec and the generated code are then lifted into the shared memory context.

## 2. State Space Optimization & Scale Resilience

The legacy implementation (`repo_snapshot.txt`) relied on exhaustive, explicit matrices (e.g., `_compute_silent_closure` computing full reachability via BFS for every state), resulting in unacceptable $O(V^2)$ memory bloat. We will modernize this logic:

### 2.1 Tarjan SCC Pre-Collapse on the $\tau$-Graph
- Before refinement, the engine extracts the $\tau$-subgraph (transitions labeled as internal, noise, or `_`).
- We execute Tarjan's Strongly Connected Components algorithm explicitly on this subgraph.
- Any cycle composed entirely of $\tau$-edges is mathematically collapsed into a single macroscopic state. This prevents infinite stuttering loops from paralyzing the downstream bisimulation.

### 2.2 Shift to Groote & Vaandrager Partition Refinement
- **Algorithmic Shift:** We discard the explicit closure arrays. The engine will implement the Groote & Vaandrager algorithm ($O(m \log n)$ complexity).
- **Splitter Queues:** The engine initializes blocks based on observable labels. It maintains an active queue of "splitter blocks." A block is refined by calculating backwards $\tau$-reachability from the splitter. This dynamic, demand-driven splitting fundamentally mitigates the state-space explosion typically caused by dense sequential LLM logic.

## 3. Complete Boundary & Edge-Case Identification Matrix

The stochastic nature of Generative AI necessitates aggressive defensive programming. The engine will actively trap and flag the following anomalies during lifting and refinement:

1. **Unreachable Code:** 
   - *Detection:* Execute a topological BFS from the initial state ($S_0$) immediately after node parsing. 
   - *Action:* All states in the set $S \setminus \text{Reach}(S_0)$ are pruned before BDD allocation, preventing ghost-state explosion.

2. **Deadlocks (Premature Termination):**
   - *Detection:* Any state $s$ where $|Out(s)| = 0$ but $s \notin Terminal\_States$ (as defined by the BPMN end events).
   - *Action:* Tagged as `Premature_Termination_Error`. The pipeline rejects the automaton.

3. **Silent Divergence ($\tau$-Livelock):**
   - *Detection:* During Tarjan collapse, if a collapsed $\tau$-SCC possesses zero outgoing observable transitions (transitions with non-$\tau$ labels).
   - *Action:* The macro-state is isolated and flagged as a `Livelock_Violation`. The AI hallucinated an infinite loop with no business value.

4. **SMT Guard Conflicts (Dead Branches):**
   - *Detection:* During BDD edge creation, if the conjunction of a branch condition evaluates to `buddy.bdd_false()`.
   - *Action:* The transition is mathematically impossible. It is stripped from the LTS, and a diagnostic warning is logged regarding unreachable LLM logic.

## 4. E2E Production-Ready Verification Roadmap

This sequence ensures stable, incremental integration into the joint repository.

### Commit 1: Memory Foundation & The Shared BDD Lifter
- Refactor the core of `m_code_lifter.py` and `spot_lifter.py` into the C++ `AdvancedLifter` class.
- Implement the strict Pybind11 memory boundaries (`spot::bdd_dict_ptr` management).
- Build the dynamic JSON parser capable of instantiating `spot::twa_graph` instances utilizing the shared dictionary.

### Commit 2: Defensive Lifting & Topological Pruning
- Implement the unreachable code pruning (BFS from $S_0$).
- Implement deadlock detection and SMT guard conflict evaluation during edge construction.
- Integrate the semantic NLP label matching to differentiate observable actions from $\tau$-transitions.

### Commit 3: The Divergence-Sensitive Stuttering Engine
- Port the legacy `verify_determinism.py` logic natively to C++.
- Implement the Tarjan SCC $\tau$-collapse logic on the `twa_graph`.
- Implement the Groote & Vaandrager partition refinement loop utilizing dynamic splitter queues rather than exhaustive matrices.

### Commit 4: Clustering Pipeline & Output Layer
- Implement the deterministic graph serialization and SHA-256 hashing for the stabilized equivalence classes.
- Wrap the execution into the master clustering loop (`clustering_engine.py` equivalent).
- Expose the final verification boolean, the selected Representative Automaton (`LTS_rep`), and the cluster mappings back to Python for Module 04 UI consumption.