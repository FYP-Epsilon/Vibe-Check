**Module 03 — Equivalence Engine**

Module 03 is the convergence point of VibeCheck. It mathematically compares the formal specification (`M_spec`, produced by Module 01) against the code's intermediate representation (WIR, produced by Module 02). It delivers a deterministic PASS, or a FAIL accompanied by a counterexample trace showing exactly where the generated code's behavior diverges from the BPMN 2.0 specification.

**The Four Phases**

- **Phase A — Lifter:** Lifts the WIR into a formal Labeled Transition System (LTS). It handles loops natively via graph cycles. Action names are resolved using a 3-tier cascade (exact → edit-distance → Sentence-BERT) running live in C++ via embedded Pybind11. An `unlabeled_task` fallback guarantees unmatched actions cannot silently slip through the analysis.
    
- **Phase B — Divergence-Sensitive Stuttering Bisimulation:** Compresses the LTS into a minimal quotient automaton while strictly preserving divergence. It refuses to merge a silently-infinite loop (e.g., a hallucinated `while True: pass`) with a normal wait state, ensuring that code that never makes progress is not certified. This establishes true process equivalence over functional, trace, and process boundaries (implemented via Groote–Vaandrager `partition_refinement` + `spot::scc_info` τ-cycle collapse).
    
- **Phase C — Behavioral Clustering:** Groups bisimulation-reduced automata so that verifying $N$ LLM implementations costs roughly `#distinct behaviors` rather than $N$ full model-checking runs. Powered by the C++ `cluster_implementations` function, it evaluates structural isomorphism via `spot::isomorphism_checker::are_isomorphic` under a strict shared `bdd_dict` memory constraint.
    
- **Phase D — Model Checking:** Executes the synchronous product of the behavior automaton and a negated violation automaton. Textbook SPOT integration: `parse_infix_psl` → ¬φ → Büchi via `spot::translator` on the code automaton's native `bdd_dict` → `spot::product` → `is_empty()`. If a violation is found, `accepting_run()` extracts the exact prefix and cycle to generate the counterexample trace.
    

**Implementation Core: C++ / SPOT Engine**

The verification engine is built entirely in C++ for maximum performance and memory safety, interfacing with the Python orchestrator via Pybind11.

- **C++ Engine (`lifter.cpp` 1,262 LOC, `lifter.hpp` 294 LOC):** Deep integration with the SPOT library throughout (`scc_info`, `simulation`, `postproc`, `are_isomorphic`, `translator`, `product`, `emptiness`).
    
- **Pybind11 Module (`vibecheck_lifter`):** Exposes the `AdvancedLifter` class managing Phases A and B, alongside free functions for Phase C (`cluster_implementations`) and Phase D (`check_compliance`).
    
- **Orchestrator (`pipeline.py`):** The `process_wir_batch()` function seamlessly pipelines the full A→D chain in a single process, model-checking each cluster representative and returning `{is_compliant, verdict, counter_example_trace}`.
    
- **NLP Bridge (`nlp_utils.py`):** A lightweight `all-MiniLM-L6-v2` transformer model provides real-time NLP embeddings for the C++ Tier 3 semantic matcher.
    

**Why Divergence-Sensitivity Matters**

Standard stuttering bisimulation collapses unobservable (τ) loops. Therefore, a generated workflow that deadlocks in a silent infinite loop (a classic LLM hallucination) would be mathematically judged as equivalent to a workflow that is safely waiting for input. Divergence-sensitivity keeps those τ-cycles visible to the auditor, preventing the certification of livelocked code.

**EQI Gate**

Verification behavior degrades according to Module 02's extraction confidence (EQI): full verification, conservative verification, or refuse-and-flag for manual review. Low-confidence extractions are halted before formal checking begins to ensure system integrity.

**Tests & Stability**

The pipeline is secured by 113 test functions, including a dedicated C++ test suite (`test_cpp_engine.py`) that validates tautologies, looping-WIR failures, counterexample extraction, quotient compliance, and strict memory segmentation guards across the Pybind11 boundary.

**Status & Open Integrations**

✅ **Core Engine Complete:** The C++/SPOT engine is fully complete through Phase D — executing true LTL model checking with counterexample extraction.

⛔ **Module 01 Ingestion Bridge:** The Phase D `check_compliance` engine accepts SPOT infix LTL (infinite-trace semantics). Module 01 currently produces LTLf strings (finite-trace semantics). A formal LTLf→LTL transformation bridge is pending to finalize the end-to-end integration between the spec and the code auditor.

## Links

- [[Home]]
- [[Module 03 Architecture.canvas|Module 03 Architecture]]
- [[Module 03 Status.canvas|Module 03 Status]]
- [[Module 03 Repo Docs Index]]
