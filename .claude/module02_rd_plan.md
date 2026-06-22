# Module 02 — R&D Plan: Architecture Perfection & Evaluation Strategy

**Created**: 2026-05-30  
**Purpose**: Context document for any future session working on Module 02 R&D before implementation resumes.  
**Scope**: Research only — no code changes until architecture is finalized.

---

## 1. Project Identity

| Field | Value |
|-------|-------|
| Framework | VibeCheck — Post-Hoc Formal Verification of LLM-Generated Python Code Using BPMN-Derived Temporal Specifications |
| Group | 18 (Epsilon), Faculty of IT, University of Moratuwa |
| Supervisor | Dr. Thilina Thanthriwatta |
| Dataset | IBM FLOW-BENCH — 101 workflow triplets (NL + BPMN XML + Python), **80 dev / 21 eval** |
| This module | Module 02 — Verified IR Extraction (sole developer) |

---

## 2. Current Module 02 Architecture

### Pipeline (3-layer validation → certificate)

```
Input: LLM-generated Python code (+ optional BPMN spec for diagnostics)

Layer V3 — Static AST Extraction (ast_extractor.py, 1346 lines)
  CFGExtractor → DominatorAnalyzer → GuardExtractor → WIRDataLayer → WIR JSON

Layer V2 — Symbolic Validation (z3_sym_engine.py, 1183 lines)
  Z3VariableRegistry → SymbolicEvaluator → WIRSymbolicTracer → BoundedConcolicEngine
  (k=3 bounded loop unrolling, Z3 SMT solver)

Layer V1 — Dynamic Validation (dynamic_tracer.py, 933 lines)
  WIRTraceCollector → WIRReferenceInterpreter → DifferentialComparator
  → RandomizedDifferentialTester (n=50 random runs, sys.settrace)

Composition: MultiModalCertificateComposer
  combined = 1 - (1-v1)(1-v2)(1-v3) ≥ 0.95

Output: Verified WIR JSON + Multi-Modal Certificate (V1+V2+V3)
API: FastAPI POST /verify (main.py)
```

### What's implemented

| File | Lines | Status |
|------|-------|--------|
| `src/ast_extractor.py` | 1,346 | Complete |
| `src/z3_sym_engine.py` | 1,183 | ~90% — 5 NotImplementedError stubs |
| `src/dynamic_tracer.py` | 933 | Complete |
| `src/main.py` | 241 | Complete |
| Tests | ~1,416 | 97 tests, 201 assertions |
| `adapters/` | — | Not started |
| `ai_refinement/` | — | Not started |
| `eval/` | — | Not started |
| `shared_schemas/wir_schema.json` | — | Missing |

---

## 3. Known Architectural Holes

### Bugs
- **P0 — Z3 Double-Reset**: `solver.reset()` called redundantly before AND after each iteration in `z3_sym_engine.py` ~lines 4360–4397. Kills accumulated path constraints.
- **P1 — QCE State Merging Never Invoked**: `state_pool` accumulates states but `merge_states()` is never called. k-bounding alone is active.
- **P1 — Container Type V1 Fallback**: `list`/`dict` params skip V2 entirely (~30% of FLOW-BENCH workflows).

### Structural Weaknesses
- Independence assumption in certificate formula: V1, V2, V3 all reason about the same WIR from the same AST extractor. A systematic extractor bug causes correlated failures — combined score does not reflect true independent confidence.
- Threshold pre-declared at 0.95 before any calibration experiment. Circular reasoning risk.
- "Three-layer path explosion defense" is actually only k-bounding (one layer). QCE refinement is a stub.
- M01 semantic output (`specification` field) only feeds GPT-4o-mini narrative — not used to constrain V2 or improve V1 trace matching.

### Missing Components
- `adapters/SelfConsistencyAdapter` — multi-implementation comparison
- `adapters/Module01Adapter` — M01→M02 semantic alignment
- `ai_refinement/` — GPT-4o-mini counterexample explainer, guard simplifier
- `eval/` — golden dataset, mutation suite, adversarial cases

---

## 4. Thesis Vulnerability Map

| Vulnerability | Risk Level | Examiner Attack |
|---------------|------------|-----------------|
| Independence assumption | HIGH | "If the AST extractor mis-parses a loop, all three layers fail on the same wrong WIR — your combined score is meaningless" |
| 20 eval samples | HIGH | "You cannot claim ≥95% bug detection with statistical confidence on 21 samples" |
| Pre-declared 0.95 threshold | HIGH | "You chose 0.95 then measured against it — that's not validation, it's tautology" |
| QCE gap (one layer, not three) | MEDIUM | "You claim three defenses against path explosion but only k-bounding is implemented" |
| Container type blind spot | MEDIUM | "30% of your benchmark is skipped by V2 — your symbolic coverage is not what you claim" |
| M01 coupling under-exploited | LOW | "Why does Module 02 accept BPMN spec input if it only uses it for narrative?" |

---

## 5. Open Research Questions (Prioritized)

### P0 — Must answer before any code changes
1. Is the 3-layer (AST + Z3 + Dynamic) architecture the right design? Are there better-validated approaches in the literature?
2. Can the independence assumption be defended, or does the formula need to change (e.g., Dempster-Shafer, copula-based combination)?
3. What is the minimum statistically valid eval dataset size for E1 ≥95% bug detection? Is FLOW-BENCH's 21 eval samples enough?
4. How should the 0.95 threshold be set empirically rather than pre-declared?

### P1 — Architecture decisions
5. Is Z3 the right solver for Python workflow code? What about CVC5, Bitwuzla, or abstract interpretation (PyAbsInt, IKOS)?
6. Should V2 treat container iteration as uninterpreted scalars (IntSort loop bound) or is there a better abstraction?
7. What does M01 semantic alignment actually change in V1 trace matching — can the improvement be measured and published?
8. Is `sys.settrace` reliable enough for n=50 runs, or should V1 use a different dynamic analysis approach?

### P2 — Evaluation methodology
9. Are there datasets beyond FLOW-BENCH with BPMN+code pairs for evaluation?
10. What mutation operators are most realistic for LLM-generated workflow bugs?
11. How should adversarial test cases be generated and what properties should they test?

---

## 6. Agent Roles for R&D Session

Five agents, one synthesis pass. Agents run concurrently; synthesis runs after all reports are in.

| Agent | Mandate |
|-------|---------|
| **Literature Scout** | Find papers supporting AND challenging the 3-layer approach. Focus: formal verification of LLM code, Python symbolic execution, IR extraction for workflows, correlated failure in multi-layer verification, Dempster-Shafer/copula combination methods. |
| **Dataset Scout** | Find datasets beyond FLOW-BENCH. Primary goal: more BPMN+code pairs for statistical power. Also look at: BPI Challenge, HumanEval, MBPP, SWE-Bench, ProBench, any IBM/academic workflow benchmarks. Report sample sizes and whether ground truth labels exist. |
| **Evaluation Methodologist** | Design the experiment to set the 0.95 threshold empirically. Define: what N is needed for each E1/E2/E3 claim, what statistical test (e.g., exact binomial, McNemar), how to avoid circular threshold validation. |
| **Architecture Critic** | Generate the 10 hardest thesis-committee questions about Module 02. For each: does the current design answer it? If not, propose a concrete fix. Must challenge the independence assumption, QCE gap, container type gap, and threshold pre-declaration. |
| **Synthesis Agent** | Runs last. Integrates all agent outputs into a single structured deliverable (see Section 8). Does not propose novel ideas — reconciles and resolves conflicts between agents. |

---

## 7. Datasets to Investigate

| Dataset | What it has | Known gap |
|---------|-------------|-----------|
| FLOW-BENCH (IBM) | 101 BPMN+NL+Python triplets, 80/20 split | Only 21 eval samples — low statistical power |
| BPI Challenge (annual) | Real-world BPMN event logs | No paired Python code |
| HumanEval | 164 Python functions with test cases | No BPMN/workflow structure |
| MBPP | 374 Python programming problems | No BPMN/workflow structure |
| SWE-Bench | Real GitHub issues + patches | Complex, not workflow-specific |
| ProBench | Process mining benchmarks | Check for code pairs |

Primary ask: find datasets with **workflow structure + Python implementation + ground truth correctness labels**.

---

## 8. Expected Deliverables from R&D Session

The synthesis agent must produce exactly these 5 sections:

1. **Revised Module 02 Architecture** — Component list with: kept (unchanged), removed (with reason), added (with justification), changed contracts. Include revised certificate formula if the independence assumption cannot be defended.
2. **Dataset Recommendation** — Recommended eval dataset(s), total N, statistical power assessment for E1/E2/E3 claims, augmentation strategy if N is insufficient.
3. **Empirical Calibration Protocol** — Step-by-step experiment to set the threshold empirically, including: what to measure, what statistical test, what sample size, how to report without circular reasoning.
4. **Top 5 Thesis Vulnerability Mitigations** — For each vulnerability in Section 4: the mitigation (architectural change, scoped claim, or documented limitation), and whether it requires code changes or thesis wording only.
5. **Revised Phase Plan** — Phases 1–6 with scope adjustments based on findings. Flag any phase that should be dropped, merged, or added.

---

## 9. Success Criteria for R&D Session

The session is successful if the synthesis output answers all P0 questions (Section 5) and produces all 5 deliverable sections with enough specificity to make code-change decisions without further research.

The session has failed if: deliverables are vague, independence assumption is unresolved, or the threshold calibration protocol is missing.
