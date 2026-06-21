# Session Handover — 2026-05-30

---

## ⏩ UPDATE — Implementation Session (2026-05-30, later) — RESUME HERE

> This section reflects the **current** state. Some items in the original R&D handover below are now **superseded** (flagged inline). Branch: **`fix/mod2/phase1-symbolic-hardening`** (3 commits, pushed; PR not yet opened — `gh` not installed). **All 105 tests pass** (was 97 + 8 new parity tests).

### What was done this session (Module 02 only — see [[module01-ownership-boundary]])
1. **Ran the R&D multi-agent session** → `.claude/module02_rd_deliverable.md` (revised architecture, dataset+power analysis, calibration protocol, vuln mitigations, phase plan). Key grounded findings: public FLOW-BENCH has **no executable Python / correctness labels** (E1 needs a mutation corpus — see [[flowbench-groundtruth-finding]]); 21 eval samples are statistically fatal for a "≥95%" claim.
2. **`1df3287` — Z3 hardening.** The audited **"P0 double-reset" bug does NOT exist** (misdiagnosis — see [[z3-double-reset-misdiagnosis]]); real fix was O(n²)→O(n) incremental `push()/pop()` in `_solve_for_inputs` + removing dead resets. Also migrated the `_execute_concrete` step-counter guard `sys.settrace`→`sys.monitoring`.
3. **`869499c` — V1 `WIRTraceCollector` `sys.monitoring` runtime path** (settrace kept as fallback + unit-test path), with `test_dynamic_tracer_parity.py` (8 cases, byte-identical). **Behaviour-preserving only — NOT a perf/portability win** (CPython-only either way; reads `f_locals` every line).
4. **`e4ba019` — V2 container coverage** ([[v2-container-coverage-increment]]): seed non-empty containers + concrete `len()`. Branch coverage list 1→4 edges (diversity 0→1.0), dict 0→1.

### Immediate next steps (priority order)
1. **Open the PR** for `fix/mod2/phase1-symbolic-hardening` (install `gh`, or use the GitHub URL). Full PR body was prepared in-session.
2. **V2 container confidence follow-on** ([[v2-container-coverage-increment]]): coverage is achieved but V2 *confidence* still reads 0 for pure-container functions — the formula in `_emit_certificate` ignores `branch_diversity_score`/coverage. Decide how the certificate credits a fully-covered-but-unsolved path; add a regression test. (Touches the certificate for all functions — deliberate, test-guarded.)
3. **`Module01Adapter` is BLOCKED** — Module 01 belongs to another developer; do not build against it until the user says M01 is ready ([[module01-ownership-boundary]]).
4. Other unblocked Module-02-internal items from the deliverable: typed `/verify` partial-failure contract (Critic-Q10), adaptive V1 run count (Q9), ValidationConfig, QCE state-merging decision (Q3).
5. GitNexus index is **stale** — run `npx gitnexus analyze` to refresh the graph.

### Corrections to the R&D handover below
- ❌ "Fix P0 Z3 double-reset bug (~lines 4360–4397)" — **bug does not exist**; file is ~1183 lines; already addressed as an O(n²) refactor.
- ⚠️ FLOW-BENCH "101 triplets w/ Python + 80/20 split" — that's a **group-derived** framing; the public dataset has no executable code or correctness labels.
- ⚠️ V1 "sys.settrace, n=50" — V1 now has a `sys.monitoring` runtime path; run count is still fixed (adaptive is a pending item).
- ⚠️ "97 tests" → now **105**.

---

## What We Did This Session <!-- (original R&D / Miro session — partially superseded; see UPDATE above) -->

1. Read all docs (`/docs/architecture`, `/docs/module_summery`, `/docs/module02/`) for a full research overview
2. Ran a full implementation audit of Module 02 codebase
3. Created two Miro architecture diagrams — then discovered and corrected a major error in Diagram 1
4. Discussed the M01 → M02 cross-track data flow and its untapped potential

---

## Project Identity

| Field | Value |
|-------|-------|
| **Framework** | VibeCheck — Post-Hoc Formal Verification of LLM-Generated Python Code Using BPMN-Derived Temporal Specifications |
| **Group** | Group 18 (Epsilon), Faculty of IT, University of Moratuwa |
| **Supervisor** | Dr. Thilina Thanthriwatta |
| **Dataset** | IBM FLOW-BENCH — 101 workflow triplets (NL + BPMN XML + Python), 80/20 dev/eval split |
| **User's module** | Module 02 — Verified IR Extraction (sole developer) |
| **Teammates** | Module 01: Welmilla CN (214248K) · Module 03: Hettiarachchi HTV (214077J) |

---

## Architecture (Dual-Track, 5-Stage Pipeline)

```
Track A (Spec):   BPMN 2.0 XML ──► Module 01 ──► M_spec + LTLf Props ──────────┐
                                    (Stage S1)                                    ▼
                                                                            Module 03 ──► Verdict
                                                                            (Stage S5)    ▲
Track B (Code):   LLM Python Code ──► Module 02 ──► WIR + M_code ───────────────┘
                                       (Stages S3-S4)
```

Both tracks are fed by **FLOW-BENCH**. LLM code generation is external (GPT-4, Claude, etc.) — not part of any module.

---

## Module Summaries

### Module 01 — Specification Analysis (Track A, Stage S1)
- **Input**: BPMN 2.0 XML + optional NL description
- **Output**: Semantic Graph (JSON) → LTLf Property Suite (P0/P1/P2 hierarchy) → M_spec Automaton (SPOT TGBA/DFA)
- **4-Phase pipeline**: Semantic Extraction → LTLf Synthesis → Mutation Validation (20 mutants, C_struct ≥ 0.95, delta = 1.0) → Automata Lifting (SPOT + BuDDy BDD)
- **Status**: Phases 1–3 complete; Phase 4 SPOT integration in progress
- **Key feature**: Self-strengthening recursive refinement loop — synthesises new properties to kill surviving BPMN mutants

### Module 02 — Verified IR Extraction (Track B, Stages S3-S4) — YOUR MODULE
- **Input**: LLM-generated Python code (+ optional BPMN spec for diagnostics)
- **Output**: Verified WIR JSON + Multi-Modal Certificate (V1+V2+V3)
- **Certificate formula**: `combined = 1 - (1-v1)(1-v2)(1-v3) ≥ 0.95`
- **3-layer validation**:
  - V3 — Static AST extraction (`ast_extractor.py`): CFG, dominator analysis, CNF guard flattening, variable classification
  - V2 — Symbolic validation (`z3_sym_engine.py`): Z3 concolic execution, k-bounded loop unrolling (k=3)
  - V1 — Dynamic validation (`dynamic_tracer.py`): sys.settrace, LCS trace alignment, n=50 random runs
- **API**: FastAPI `POST /verify` endpoint (`main.py`)

### Module 03 — Equivalence Engine (Convergence, Stage S5)
- **Input**: M_spec (from M01) + WIR/M_code + EQI Certificate (from M02) + N Python implementations
- **Output**: Equivalence clusters + Conformance verdict (PASS/FAIL) + Diagnostic counter-examples
- **4-Phase pipeline**: Lifter (WIR → SPOT twa_graph) → Divergence-Sensitive Stuttering Bisimulation (Groote-Vaandrager O(m log n)) → Clustering (SHA-256, O(scripts)→O(clusters)) → Model Checking (synchronous product + Couvreur emptiness check)
- **EQI tier**: GREEN ≥0.90 (standard), YELLOW 0.70–0.90 (conservative abstraction), RED <0.70 (refuse lifting)
- **Status**: Python prototype done; C++ SPOT components in development

---

## Module 02 Implementation Audit

### File Inventory

| File | Lines | Status |
|------|-------|--------|
| `src/ast_extractor.py` | 1,346 | ✅ COMPLETE |
| `src/z3_sym_engine.py` | 1,183 | ⚠️ ~90% — 5 stubs |
| `src/dynamic_tracer.py` | 933 | ✅ COMPLETE |
| `src/main.py` | 241 | ✅ COMPLETE |
| `test_ast_extractor.py` | — | 30 tests |
| `test_z3_sym_engine.py` | — | 39 tests |
| `test_dynamic_tracer.py` | — | 26 tests |
| `test_integration.py` | — | 2 tests |
| **Total** | **~3,703** prod + **~1,416** test | **97 tests, 201 assertions** |

### Phase Completion

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 1 (Core hardening) | Z3 bug fixes, adaptive test runs, ValidationConfig | ⏳ Pending |
| Phase 2 (AI refinement) | GPT-4o-mini counterexample explainer, narrative, guard simplifier | ⏳ Pending |
| Phase 3 (Multi-impl adapters) | SelfConsistencyAdapter, Module01Adapter, `/verify-batch` | ⏳ Pending |
| Phase 4 (Eval data) | 50 golden + 100 augmented + 500 mutants + 10 adversarial | ⏳ Pending |
| Phase 5 (Experiments) | E1 bug detection ≥95%, E2 structural accuracy ≥98%, E3 Pearson r ≥0.85 | ⏳ Pending |
| Phase 6 (Integration) | Module 03 API contract, thesis chapter, supervisor sign-off | ⏳ Pending |

### Missing Directories/Files
- `adapters/` — NOT STARTED
- `ai_refinement/` — NOT STARTED
- `eval/` — NOT STARTED
- `shared_schemas/wir_schema.json` — MISSING (graceful fallback exists in code)

### Known Bugs (from `docs/module02/05_core_hardening.md`)

**P0 — Z3 Solver Double-Reset Bug** (`z3_sym_engine.py` ~lines 4360–4397)
```python
# BUG: solver.reset() called redundantly before AND after each iteration
solver.reset()                    # ← BUG #1: kills accumulated constraints
solver.add(path_condition)
# ... solve ...
solver.reset()                    # ← BUG #2: redundant reset before next iter
```
Fix: use fresh `Solver()` per iteration OR `push()`/`pop()` pattern.

**P1 — QCE State Merging Never Invoked**
- `state_pool` accumulates states but `merge_states()` is never called
- k-bounding alone active; documented as known limitation

**P1 — Container Type Forces V1 Fallback**
- `list`/`dict` params skip V2 entirely (~30% of FLOW-BENCH workflows)
- Minimal fix: treat loop iterators as uninterpreted scalars (IntSort for loop bound)

### 5 NotImplementedError Stubs in z3_sym_engine.py
1. Type conversion edge case in `Z3VariableRegistry`
2. Pattern handler #1 in `SymbolicEvaluator`
3. Pattern handler #2 in `SymbolicEvaluator`
4. Debug utility in `WIRSymbolicTracer`
5. Advanced QCE refinement in `BoundedConcolicEngine`

### Thesis Risks Identified
1. **Independence assumption** — combined formula assumes V1/V2/V3 fail independently, but all reason about the same WIR from the same AST extractor. A systematic extractor bug could cause correlated failures. Must be argued in thesis.
2. **Pre-validated threshold** — 0.95 set before Phase 5 calibration. Circular reasoning risk if threshold not empirically validated.
3. **QCE gap** — "three-layer path explosion defense" is actually only two layers (k-bounding only). Must be stated clearly as a limitation.

---

## Miro Board Status

**Board URL**: https://miro.com/app/board/uXjVHMQbchY=/

| Diagram | Position | Status |
|---------|----------|--------|
| "VibeCheck — High-Level Research Architecture" | x=-3500, y=0 | ❌ **WRONG — DELETE IT** (`moveToWidget=3458764673762225787`) |
| "Module 02 — Detailed Architecture: Multi-Modal IR Validator" | x=3500, y=0 | ✅ Correct |
| "VibeCheck — High-Level Research Architecture (CORRECTED)" | x=-3500, y=4000 | ✅ Correct |

### What the INCORRECT Diagram 1 got wrong
- Module 01 labelled as "LLM Workflow Generator" → it is the **Specification Analysis** module (BPMN → M_spec)
- Python code shown flowing out of Module 01 → wrong, LLM code is **external**
- Module 03 labelled as "BPMN Bisimulation Checker" → it is the full **Equivalence Engine** (4 phases)
- Showed single linear pipeline → it is a **dual-track architecture**

### What the CORRECTED Diagram 1 shows (LR direction, dual-track)
- Track A (top): BPMN XML → Module 01 → quality gate → M_spec + LTLf
- Track B (bottom): LLM Python code → Module 02 → certificate gate → WIR + M_code
- Both → Module 03 → Verdict
- FLOW-BENCH feeds both tracks
- Manual Review as shared error sink

### What the Module 02 Detailed Diagram shows (TB direction)
- Input → FastAPI endpoint
- V3 cluster (yellow): CFGExtractor → DominatorAnalyzer → GuardExtractor → WIRDataLayer → WIR JSON → gate
- V2 cluster (purple): Z3VariableRegistry → SymbolicEvaluator → WIRSymbolicTracer → BoundedConcolicEngine → confidence gate → LOW path triggers V1 Fallback → merges into WIRTraceCollector
- V1 cluster (orange): WIRTraceCollector → WIRReferenceInterpreter → DifferentialComparator → RandomizedDifferentialTester
- Composition cluster (green): MultiModalCertificateComposer → formula → threshold gate → output or abort
- Abort/Flag node (red) floats outside all clusters, receives arrows from V3 gate AND final gate

---

## Cross-Module Data Flow Finding (M01 → M02)

**Question asked**: Is there a semantic map flowing from Module 01 to Module 02 to refine the WIR?

**Answer**: A connection exists but is underutilised.
- Module 01 docs say output goes to Module 02 "as a reference for WIR semantic alignment"
- Module 02 input table says `specification` field is "for diagnostic enrichment only"
- **Current use**: only feeds the Phase 2 GPT-4o-mini AI refinement layer for better explanations

**What could be done (genuine research contribution)**:

| M01 Output | How to use in M02 | Impact |
|------------|-------------------|--------|
| Semantic Graph (task names: `start(Task)`, `done(Task)`) | Feed into `WIRTraceCollector.task_patterns` instead of heuristic string matching | HIGH — directly improves V1 trace quality |
| LTLf P0 Sentinel Properties (`G(!Approve U Validate)`) | Add as hard constraints in V2 Z3 engine | HIGH — catches structural violations before runtime |
| XOR Guard Conditions (implicit else resolved) | Validate against V3 `GuardExtractor` output | MEDIUM — cross-validates guard extraction |

This creates a genuine cross-track feedback mechanism. Worth framing as a novel architectural contribution in thesis Chapter 4.

---

## Suggested Next Session Priorities

1. **Delete** the incorrect Diagram 1 from Miro (`moveToWidget=3458764673762225787`)
2. **Fix P0 Z3 double-reset bug** (`z3_sym_engine.py` ~lines 4360–4397)
3. **Resolve 5 NotImplementedError stubs** in `z3_sym_engine.py`
4. **Create** `shared_schemas/wir_schema.json`
5. **Start Phase 4** eval data generation — `eval/generate_golden.py` first
6. **Prototype** M01→M02 semantic alignment (task_patterns from semantic graph)
