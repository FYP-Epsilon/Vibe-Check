# Module 02: VibeCheck IR Validator — Architecture Overview

> **Status**: Implementation complete (V1/V2/V3). Phases 1–6 in progress.  
> **Owner**: Module 02 Lead Developer  
> **Last Updated**: 2026-05-17

---

## 1. Purpose

Module 02 is the **bridge between untrusted LLM-generated Python workflow code and formally verifiable control-flow representations**. It takes raw Python IR (Intermediate Representation) as input and produces a **verified Workflow Intermediate Representation (WIR)** — a JSON-structured control-flow graph accompanied by a multi-modal correctness certificate.

Without Module 02, Module 03 has no trustworthy input against which to perform bisimulation checking against the BPMN specification. This module is the technical centerpiece of **Research Question 2** (RQ2): *How can we gain confidence that extracted IR faithfully represents the original code's behavior when both the code and the extraction process are potentially unreliable?*

---

## 2. Three-Layer Validation Architecture

Module 02 operates through **three complementary validation modes**, each providing different confidence evidence with independent failure modes. The final output is a **multi-modal certificate** combining all three confidence scores.

| Mode | Name | Technique | What It Proves | Independence |
|------|------|-----------|----------------|--------------|
| V3 | Structural Validation | AST → CFG extraction, dominator analysis, guard CNF flattening, control/data variable classification | *"The WIR structurally matches the code"* | Independent of V1, V2 |
| V2 | Symbolic Validation | Z3 concolic execution with k-bounded loop unrolling, QCE state merging, path exploration | *"The paths through the WIR are logically feasible in the code"* | Independent of V1, V3 |
| V1 | Dynamic Validation | `sys.settrace` differential testing, WIR reference interpreter, LCS trace comparison, randomized testing | *"The code and WIR behave identically on concrete inputs"* | Independent of V2, V3 |

### Certificate Composition Formula

```
combined = 1 - (1 - v1) * (1 - v2) * (1 - v3)
```

A WIR is **certified valid** if `combined >= 0.95`. Each mode contributes independently — the combined score only reaches the threshold if at least two modes provide significant evidence.

---

## 3. Component Map

```
module02/
├── ast_extractor.py          # V3: CFGExtractor, DominatorAnalyzer, GuardExtractor, WIRDataLayer
├── z3_sym_engine.py          # V2: Z3VariableRegistry, WIRSymbolicTracer, BoundedConcolicEngine
├── dynamic_tracer.py         # V1: WIRTraceCollector, WIRReferenceInterpreter, DifferentialComparator
├── main.py                   # FastAPI: /verify endpoint, orchestration
├── models.py                 # Pydantic: ValidationRequest, ValidationResponse, Certificate schemas
├── adapters/                 # NEW (Phase 3): Multi-implementation generation
│   ├── base.py              # GenerationAdapter abstract interface
│   ├── llm_adapter.py       # SelfConsistencyAdapter: temperature-sampled LLM generation
│   └── m01_adapter.py       # Module01Adapter: delegates to external Module 01
├── ai_refinement/           # NEW (Phase 2): LLM-based diagnostic refinement
│   ├── client.py            # OpenAI GPT-4o-mini client wrapper
│   ├── counterexample.py    # V1 failure explanation generator
│   ├── narrative.py         # Certificate → human-readable report
│   └── guard_simplify.py    # Guard expression simplification
└── eval/                    # NEW (Phases 4–5): Evaluation framework
    ├── generate_golden.py   # Layer 1: Golden workflow generator
    ├── augment_flowbench.py # Layer 2: FLOW-BENCH derivative augmenter
    ├── mutation_engine.py   # Layer 3: Mutation testing engine
    ├── adversarial.py       # Layer 4: Hand-crafted edge cases
    └── run_experiments.py   # Evaluation orchestrator + metric calculator
```

---

## 4. Implementation Roadmap (6 Phases)

| Phase | Document | Scope | Status |
|-------|----------|-------|--------|
| **Phase 1** | `05_core_hardening.md` | Fix solver bugs, increase test coverage, validate thresholds | Pending |
| **Phase 2** | `06_ai_refinement.md` | Integrate OpenAI GPT-4o-mini for counterexample explanation, certificate narrative, guard simplification | Pending |
| **Phase 3** | `07_multi_impl.md` | Self-consistency sampling adapter, multi-implementation orchestrator, `/verify-batch` endpoint | Pending |
| **Phase 4** | `08_eval_data.md` | 4-layer evaluation data generation (golden, augmented, mutation, adversarial) | Pending |
| **Phase 5** | `09_experiments.md` | Seeded bug detection, metric calibration, threshold tuning | Pending |
| **Phase 6** | `10_integration.md` | Module 03 API contract, thesis documentation, supervisor checkpoint | Pending |

---

## 5. External Interfaces

### Input: From Module 01 (or Generation Adapter)

```json
{
  "workflow_code": "def handle_incident() -> str:\n    incident = ServiceNow_incident__4_0_0__retrievewithwhere_incident()\n    if incident.impact == 'high':\n        ...",
  "specification": "BPMN XML or natural language spec (optional, for diagnostics)"
}
```

### Output: To Module 03

```json
{
  "wir": {
    "entry": "node_0",
    "nodes": [...],
    "edges": [...],
    "control_variables": [...],
    "data_variables": [...]
  },
  "certificate": {
    "v1": { "score": 0.92, "tests_run": 50, "mismatches": 0 },
    "v2": { "score": 0.85, "paths_explored": 12, "solver_time": 2.3 },
    "v3": { "score": 0.98, "nodes": 8, "edges": 10, "guards_cnf": 4 },
    "combined": 0.9997,
    "passed": true
  }
}
```

### New: Batch Output (Phase 3)

```json
{
  "implementations": [
    { "variant_id": 0, "wir": {...}, "certificate": {...} },
    { "variant_id": 1, "wir": {...}, "certificate": {...} },
    ...
  ],
  "cluster_summary": {
    "equivalence_clusters": [[0,1,3], [2]],
    "consensus_size": 3,
    "selected_variant": 0
  }
}
```

---

## 6. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Three independent modes** | Independent failure surfaces prevent correlated failures. If V3 has a bug in dominator analysis, V1 and V2 still provide confidence. |
| **Combined = 1 - product of failures** | Standard parallel-system reliability formula. Each mode independently contributes evidence. |
| **0.95 certification threshold** | Empirical target from concolic testing literature. Calibrated during Phase 5 experiments. |
| **OpenAI GPT-4o-mini for refinement** | $5 budget covers entire project. Used only for diagnostics (not verification logic). Prevents circular reasoning in research. |
| **Self-consistency in adapter layer** | Multi-implementation generation lives in pluggable adapter, not core validator. Keeps validation engine model-agnostic. |
| **4-layer evaluation data** | Matches FLOW-BENCH methodology (golden + augmented + mutation + adversarial). Provides ground truth for all metrics. |

---

## 7. References

1. VibeCheck Research Design — "Verified Translation Validation for LLM-Generated Workflow Code" (Interim Report)
2. Module 02 Execution Plan — `module_02_execution_plan.md`
3. IBM Flow-Bench Dataset — https://github.com/IBM/flow-bench [^19^]
4. Isahagian et al. (2025). *Towards Conversational Generation of Enterprise Workflows*. arXiv:2505.11646 [^8^]
5. De Moura & Bjorner (2008). *Z3: An Efficient SMT Solver*. TACAS.
6. Godefroid et al. (2005). *DART: Directed Automated Random Testing*. PLDI.
7. Cadar et al. (2006). *EXE: Automatically Generating Inputs of Death*. CCS.
8. Ammann & Offutt (2008). *Introduction to Software Testing*. Cambridge University Press.
9. Papadakis et al. (2015). *Trivial Compiler Equivalence: A Large Scale Empirical Study of a Simple, Fast and Effective Equivalent Mutant Detection Technique*. ICSE.
10. Wang et al. (2023). *Self-Consistency Improves Chain of Thought Reasoning in Language Models*. ICLR.

---

*For detailed implementation of each phase, see the numbered phase documents (`05_*` through `10_*`).*
