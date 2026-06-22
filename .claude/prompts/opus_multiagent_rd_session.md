# Opus 4.8 Multi-Agent R&D Session Prompt
# Copy-paste this entire prompt into a new Claude Opus 4.8 session.
# Do NOT summarize or abbreviate — the full context is required.

---

## SESSION MANDATE

You are running a **research and design session only**. No code will be written. No files will be edited. The goal is to produce a finalized architecture and evaluation strategy for Module 02 of a formal verification research system, ready for implementation in the next session.

You will operate as **five concurrent sub-agents**, each with a distinct mandate. After all five complete their analysis, you will switch to a **Synthesis Agent** role to reconcile their outputs into one structured deliverable.

Read the full project brief below before beginning any analysis.

---

## PROJECT BRIEF

**System name**: VibeCheck  
**Full title**: Post-Hoc Formal Verification of LLM-Generated Python Code Using BPMN-Derived Temporal Specifications  
**University**: Faculty of IT, University of Moratuwa — Final Year Project, Group 18 (Epsilon)  
**Supervisor**: Dr. Thilina Thanthriwatta  
**Your module**: Module 02 — Verified IR Extraction (sole developer)  
**Codebase**: ~3,703 lines of production Python, 97 tests

### Pipeline Architecture (Dual-Track, 5-Stage)

```
Track A (Spec):   BPMN 2.0 XML ──► Module 01 ──► M_spec + LTLf Props ──────────┐
                                    (Stage S1)                                    ▼
                                                                            Module 03 ──► Verdict
                                                                            (Stage S5)    ▲
Track B (Code):   LLM Python Code ──► Module 02 ──► WIR + M_code ───────────────┘
                                       (Stages S3-S4)
```

Both tracks are fed by **FLOW-BENCH** (IBM, 101 workflow triplets: NL description + BPMN 2.0 XML + Python implementation, 80 dev / 21 eval split). LLM code generation is external (GPT-4, Claude, etc.) — not part of any module.

### Module 02 Current Design

**Input**: LLM-generated Python code (+ optional BPMN spec for diagnostics)  
**Output**: Verified WIR (Workflow Intermediate Representation) JSON + Multi-Modal Certificate (V1+V2+V3)

**Layer V3 — Static AST Extraction** (`ast_extractor.py`, 1346 lines)
- CFGExtractor → DominatorAnalyzer → GuardExtractor → WIRDataLayer → WIR JSON
- Builds the WIR from Python AST: control flow graph, dominator tree, CNF-flattened guards, variable classification

**Layer V2 — Symbolic Validation** (`z3_sym_engine.py`, 1183 lines, ~90% complete)
- Z3VariableRegistry → SymbolicEvaluator → WIRSymbolicTracer → BoundedConcolicEngine
- Z3 SMT solver, k=3 bounded loop unrolling, quasi-concolic execution (QCE)
- **Known bug**: `solver.reset()` called before AND after each iteration — kills accumulated path constraints
- **Known gap**: container types (`list`, `dict`) force fallback to V1 only (~30% of FLOW-BENCH)
- **Known gap**: QCE state merging (`merge_states()`) is implemented but never called

**Layer V1 — Dynamic Validation** (`dynamic_tracer.py`, 933 lines)
- WIRTraceCollector → WIRReferenceInterpreter → DifferentialComparator → RandomizedDifferentialTester
- `sys.settrace` instrumentation, n=50 random runs, LCS-based trace alignment

**Certificate Composition** (`MultiModalCertificateComposer`)
- Formula: `combined = 1 - (1-v1)(1-v2)(1-v3)`
- Threshold: combined ≥ 0.95 → PASS; < 0.95 → FAIL/ABORT
- Module 03 uses this certificate to decide whether to lift WIR to SPOT automaton

**API**: FastAPI `POST /verify` endpoint

### What Does Not Exist Yet
- `adapters/SelfConsistencyAdapter` — multi-implementation comparison
- `adapters/Module01Adapter` — feeding M01 semantic graph into M02
- `ai_refinement/` — GPT-4o-mini counterexample explainer and guard simplifier
- `eval/` — golden dataset generation, mutation suite, adversarial cases
- `shared_schemas/wir_schema.json` — schema for WIR JSON

### Module 03 Contract (what M02 must satisfy)
- Module 03 reads the EQI (Equivalence Quality Index) certificate from Module 02
- GREEN ≥0.90 → standard SPOT automaton lifting
- YELLOW 0.70–0.90 → conservative abstraction
- RED <0.70 → Module 03 refuses to lift (returns FAIL immediately)
- Module 03 uses Groote-Vaandrager bisimulation (O(m log n)) + Couvreur emptiness check

### Known Thesis Vulnerabilities

| Vulnerability | Examiner attack |
|---------------|-----------------|
| Independence assumption | "V1, V2, V3 all reason about the same WIR from the same AST extractor. A systematic extractor bug causes correlated failures across all three — your combined score is not what you claim." |
| 21 eval samples | "You cannot claim ≥95% bug detection with statistical confidence on 21 samples." |
| Pre-declared 0.95 threshold | "You chose 0.95, then measured against it — that is tautology, not validation." |
| QCE gap | "You claim three defenses against path explosion but only k-bounding is implemented." |
| Container type blind spot | "30% of your benchmark skips V2 — your symbolic coverage is overstated." |

### Planned Experiments (not yet run)
- **E1**: Bug detection rate ≥ 95% on evaluation set
- **E2**: Structural accuracy of WIR extraction ≥ 98%
- **E3**: Pearson r ≥ 0.85 between certificate score and actual correctness

---

## AGENT ROLES

You will now execute the following five agents **in sequence**, labelling each output clearly. Think deeply for each role before writing its output.

---

### AGENT 1 — Literature Scout

**Mandate**: Find and evaluate academic literature that informs (or challenges) the current design.

Search for papers in these areas. For each area, report: what the literature says, whether it supports or challenges the current M02 design, and any concrete design change it implies.

**Areas to cover**:

1. **Formal verification of LLM-generated code** — What approaches exist? How do they handle Python? Are multi-layer approaches (static + symbolic + dynamic) standard?
2. **Python symbolic execution** — Z3 vs CVC5 vs Bitwuzla vs abstract interpretation (PyAbsInt, IKOS, Lyra). For workflow code specifically: which handles container types better?
3. **IR extraction from Python** — How do other systems build an IR from Python AST? What do they capture that the current V3 layer misses?
4. **Multi-layer verification certificate combination** — Is the independence assumption (`combined = 1 - (1-v1)(1-v2)(1-v3)`) used in the literature? What alternatives exist: Dempster-Shafer evidence theory, copula-based combination, fuzzy logic, Bayesian combination? Which is most defensible for correlated failures?
5. **Correlated failure in verification layers** — Literature on what happens when multiple verification layers share a common upstream artifact (like a single AST extractor feeding all three layers).
6. **Bounded symbolic execution** — Is k=3 a standard choice for loop unrolling in workflow-scale Python? What does the literature say about choosing k?

**Output format**: One paragraph per area. End with a list of top 3 design changes implied by the literature.

---

### AGENT 2 — Dataset Scout

**Mandate**: Find datasets that can supplement or replace FLOW-BENCH for evaluating Module 02.

**Critical constraint**: FLOW-BENCH has only 21 evaluation samples. This is almost certainly insufficient for claiming ≥95% bug detection with statistical confidence. The primary goal of this agent is to find more data.

**Search for**:

1. **BPMN + Python pairs** — Any dataset with both a workflow specification (BPMN, PDDL, Petri net) AND a corresponding Python implementation AND ground truth correctness labels.
2. **Workflow code benchmarks** — IBM FLOW-BENCH variants, ProBench, BPI Challenge datasets, academic process mining benchmarks.
3. **Python correctness benchmarks** — HumanEval (164 functions), MBPP (374 problems), SWE-Bench (2294 GitHub issues). Can any of these be adapted? What would be needed?
4. **LLM code generation benchmarks** — Any benchmark where LLMs generated Python code and correctness was verified — especially if the code has workflow-like structure (sequential steps, branching, loops with explicit semantics).
5. **Synthetic augmentation options** — If no suitable dataset exists, what augmentation strategies are defensible? GPT-4 generation of BPMN+code pairs? Mutation of existing FLOW-BENCH? How would you justify synthetic data in a thesis?

**Output format**: Table of datasets found (name, N samples, has BPMN?, has code?, has labels?, source). Then: recommended dataset strategy with statistical justification — what N is needed, what the recommended combination is.

---

### AGENT 3 — Evaluation Methodologist

**Mandate**: Design the empirical calibration protocol for the 0.95 threshold and the statistical framework for E1/E2/E3.

The current design pre-declares 0.95 as the pass threshold, then plans to measure against it. A thesis examiner will correctly identify this as circular. Your job is to fix it.

**Deliver**:

1. **Threshold calibration protocol** — Step-by-step experiment to set the threshold empirically BEFORE claiming it. What is measured, on what data, using what method. Key constraint: the calibration data must be separate from the evaluation data.

2. **Statistical power analysis for E1** (≥95% bug detection):
   - Given a true positive rate of 95%, what N samples are needed to reject the null hypothesis (rate ≤ 80%) at α=0.05, power=0.80?
   - What statistical test is appropriate (exact binomial test, McNemar's test)?
   - What does this mean for FLOW-BENCH's 21-sample eval split?

3. **Statistical framework for E2** (≥98% structural accuracy):
   - What metric operationalizes "structural accuracy"? (F1 on WIR nodes/edges? Edit distance? Something else?)
   - What N is needed at the same power level?

4. **Statistical framework for E3** (Pearson r ≥ 0.85 between certificate score and actual correctness):
   - Is Pearson r the right measure? (It requires continuous ground truth — where does that come from?)
   - What N is needed to detect r=0.85 vs r=0 at α=0.05, power=0.80?

5. **Avoiding circular threshold validation** — Write the exact thesis wording you would recommend for presenting the threshold: how to frame it so it is not circular, what caveats to include.

**Output format**: Numbered protocol for each item. Be specific — include formulas, sample sizes, test names.

---

### AGENT 4 — Architecture Critic

**Mandate**: Generate the 10 hardest thesis-committee questions about Module 02's design. For each: state whether the current design answers it, and if not, propose a concrete fix (architectural change, scoped claim, or documented limitation).

The questions must be adversarial — the kind a formal methods examiner would ask. Do not soften them.

**You must include questions that directly attack**:
- The independence assumption in the certificate formula
- The 30% V2 coverage gap (container types)
- The QCE "three defenses" claim vs. reality (only k-bounding)
- The pre-declared 0.95 threshold
- The use of `sys.settrace` for V1 (reliability, overhead, CPython-only)
- The WIR as the shared upstream artifact for all three layers
- The choice of Z3 over abstract interpretation for workflow-scale Python
- The M01 → M02 coupling (why accept BPMN spec if only used for narrative?)
- The n=50 run count for V1 (is it enough? how was it chosen?)
- The FastAPI endpoint design (what happens if V3 fails? what's the partial output contract?)

**Output format**: Numbered list 1–10. For each: Q (the question), CURRENT (what the design answers today), FIX (what to change, with specificity).

---

### AGENT 5 — Synthesis Agent

**Mandate**: Integrate the outputs of Agents 1–4 into a single, structured, actionable deliverable. Do not propose novel ideas. Reconcile conflicts between agents. If agents disagree, state the disagreement and recommend one resolution with justification.

Produce exactly the following 5 sections:

---

#### DELIVERABLE 1 — Revised Module 02 Architecture

For each component, state: **KEEP** / **REMOVE** / **ADD** / **CHANGE**, with a one-sentence justification.

Minimum coverage:
- V3 (AST extraction layer)
- V2 (Z3 symbolic layer) — include decision on container type handling
- V1 (dynamic tracing layer) — include decision on `sys.settrace` vs alternatives
- Certificate composition formula — include decision on independence assumption
- M01 → M02 semantic alignment — include decision on whether to implement
- QCE / state merging — include decision on whether to implement or document as limitation

End with: the revised certificate formula (or confirmation that `1-(1-v1)(1-v2)(1-v3)` is defensible with appropriate caveats).

---

#### DELIVERABLE 2 — Dataset Recommendation

- Recommended eval dataset(s) with total N
- Statistical power assessment: is the recommended N sufficient for E1/E2/E3 claims?
- Augmentation strategy if N is insufficient (with thesis defensibility assessment)
- Train/dev/eval split recommendation

---

#### DELIVERABLE 3 — Empirical Calibration Protocol

Step-by-step protocol (from Agent 3, validated against Agent 4's questions) for setting the 0.95 threshold empirically. Include the exact thesis wording recommendation.

---

#### DELIVERABLE 4 — Top 5 Thesis Vulnerability Mitigations

For each of the top 5 vulnerabilities (ranked by examiner attack severity):
- The vulnerability (one sentence)
- The mitigation (architectural change, scoped claim, or documented limitation)
- Whether it requires code changes or thesis wording only
- Risk if not addressed

---

#### DELIVERABLE 5 — Revised Phase Plan

Phases 1–6 of the original implementation plan, with scope adjustments:
- Phase 1: Core hardening (Z3 bugs, adaptive runs, ValidationConfig)
- Phase 2: AI refinement (GPT-4o-mini)
- Phase 3: Multi-impl adapters (SelfConsistencyAdapter, Module01Adapter, /verify-batch)
- Phase 4: Eval data (golden + augmented + mutants + adversarial)
- Phase 5: Experiments (E1/E2/E3)
- Phase 6: Integration (M03 API contract, thesis chapter)

For each phase: SCOPE CHANGE (expanded/reduced/unchanged), PRIORITY CHANGE (moved up/down), DROPPED items (with reason), ADDED items (with reason).

---

## EXECUTION INSTRUCTIONS

1. Run Agents 1–4 in parallel (present all four outputs before Synthesis).
2. Label each agent output with a clear header: `## AGENT 1 — Literature Scout`, etc.
3. After all four agents complete, run Agent 5 (Synthesis). Label: `## AGENT 5 — SYNTHESIS`.
4. The synthesis output must be usable directly as an implementation brief — specific enough to make code-change decisions without further research.
5. If the `/architecture` plugin is available, use it to generate a revised architecture diagram in the synthesis output. If not, produce a text-based component diagram.
6. After the full output, add a `## NEXT SESSION` section: a 5-bullet list of the first actions to take in the implementation session, in priority order.

---

## WHAT NOT TO DO

- Do not write any code.
- Do not edit any files.
- Do not fix any bugs (note them, but leave fixing to the implementation session).
- Do not make vague recommendations — every recommendation must be specific enough to act on.
- Do not skip the Synthesis Agent — the raw agent outputs are not the deliverable.
