> [!info] Imported from repo docs
> Source: `docs/module02/00_overview.md` @ main `7089711` (2026-07-28). `docs/` was removed from the repo (develop @ `05fae60`, 2026-07-28) after this import — **this vault copy is now the surviving snapshot** (git history retains the originals).

# Module 02: VibeCheck IR Validator — Architecture Overview

> **Status**: Core validator (V1/V2/V3) implemented in `src/`, plus core hardening, multi-implementation corpus generation, and a full evaluation harness (`eval/`) — see §4 for per-phase detail. AI-assisted refinement (originally-planned Phase 2) is not implemented. This document is a living reference, kept in sync with the current source — see `docs/module02/12_wir_and_certificate_contract.md` for the authoritative WIR/certificate schema consumed by Module 03.
> **Owner**: Module 02 Lead Developer
> **Last Updated**: 2026-07-09 (docs refresh reconciling this document with seven engineering sessions' worth of implementation changes)

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
| V2 | Symbolic Validation | Z3 concolic execution with k-bounded loop unrolling, branch-negation path exploration, container-input seeding | *"The paths through the WIR are logically feasible in the code"* | Independent of V1, V3 |
| V1 | Dynamic Validation | PEP 669 `sys.monitoring`-first differential testing (falls back to `sys.settrace` on Python < 3.12 or when no monitoring tool id is free), WIR reference interpreter, LCS trace comparison, randomized testing | *"The code and WIR behave identically on concrete inputs"* | Independent of V2, V3 |

(An earlier V2 design also included QCE — Query Count Estimation — symbolic state merging. It was never wired into the concolic exploration loop above, only exercised by its own unit tests, and was deleted as dead code rather than kept as an unused capability; see `eval/results/session_b_report.md`'s B4 section.)

> [!warning] The "multi-modal" certificate is empirically two-modal on the current corpus
> V2's `confidence` measures 0.0 for essentially every FLOW-BENCH-derived base program in this corpus — container-shaped inputs make V2 bail to a V1 fallback — so `combined_confidence` in practice is driven almost entirely by V1, not a genuine three-way (or even two-way) combination. This is a real, checked fact from the calibration data, not a formal ablation result (none has been run as a controlled experiment). V3 still gates independently, so it isn't "two-modal" in the sense of only one layer mattering at all — but V1+V2's product is functionally V1 alone here. See `Module_02_Verified_IR_Extraction.md` §10.7 for the full finding and its source, and Next Steps.md item #12 for the standing instruction to keep this stated openly rather than let the architecture table above imply an even three-way split.

### Certificate Composition Formula

```
combined_confidence = 1 - (1 - v1_confidence) * (1 - v2_confidence)
```

V3 does **not** appear in this product. An earlier version of this formula included a `(1 - v3)` term, but V3 measures *extraction fidelity* (does the WIR structurally match the code?), not *behavioral correctness* — and V3 saturates to a near-1.0 score for almost any structurally extractable program, which made the three-term product's combined score vacuous (a WIR could reach the certification threshold on V3's contribution alone, regardless of what V1/V2 found). V3 now acts as a **gate** instead: if extraction fidelity is below threshold (`v3_cert["abort"] = True`), verification fails immediately regardless of V1/V2, since a low-fidelity WIR means every downstream check ran against an unfaithful model of the code in the first place. A WIR is **certified valid** if `combined_confidence >= 0.95` and V3 did not abort.

---

## 3. Component Map

Legend: ✅ implemented · ⏳ planned, not present. The three validation layers were modularized from single-file monoliths into packages partway through implementation — each is now a directory, not a `.py` file.

```
module_02_extract/
├── src/
│   ├── ast_extractor/         # ✅ V3: cfg_extractor.py (CFGExtractor), dominators.py,
│   │                          #    guards.py, data_layer.py, certificate.py, models.py,
│   │                          #    schema.py, pipeline.py (run_v3_pipeline)
│   ├── z3_sym_engine/          # ✅ V2: registry.py (Z3VariableRegistry), evaluator.py,
│   │                          #    tracer.py (WIRSymbolicTracer), concolic.py
│   │                          #    (BoundedConcolicEngine), pipeline.py (run_v2_pipeline)
│   ├── dynamic_tracer/         # ✅ V1: collector.py (WIRTraceCollector), interpreter.py
│   │                          #    (WIRReferenceInterpreter), comparator.py
│   │                          #    (DifferentialComparator), randomized.py
│   │                          #    (RandomizedDifferentialTester), composer.py
│   │                          #    (MultiModalCertificateComposer), pipeline.py (run_v1_pipeline)
│   └── main.py                 # ✅ FastAPI /verify endpoint + orchestration; CodePayload(BaseModel)
│                              #    still defined inline (see "Planned" below); typed per-layer
│                              #    `layers` status key; wall-clock timeout wrapper
├── tests/                     # ✅ test_ast_extractor.py, test_z3_sym_engine.py,
│                              #    test_dynamic_tracer.py, test_dynamic_tracer_parity.py,
│                              #    test_integration.py (246 tests total, incl. eval/)
├── inputs/                    # ✅ sample workflows (e.g. loan_approval.py)
├── eval/                      # ✅ full evaluation harness — NOT the 4-layer plan originally
│   │                          #    sketched below; see docs/module02/09_experiments.md's
│   │                          #    historical-document banner for what changed and why.
│   │                          #    manifest.json + flowbench_adapter.py (corpus), mutate.py
│   │                          #    (10 mutation operators), calibrate*.py (threshold
│   │                          #    selection), nim_client.py + gen_variants.py +
│   │                          #    admit_variants.py (multi-implementation corpus),
│   │                          #    e2_structural.py / e3_correlation.py (structural /
│   │                          #    behavioral accuracy experiments), c5_experiments.py /
│   │                          #    d3_control.py (cross-implementation comparison-mode
│   │                          #    experiments), results/ (all current reports)
│
│   # --- Still planned, not present in src/ ---
├── models.py                  # ⏳ Pydantic schemas (CodePayload still lives inline in main.py)
├── adapters/                  # ⏳ originally-planned pluggable multi-implementation-generation
│                              #    layer (base.py / llm_adapter.py / m01_adapter.py). Multi-
│                              #    implementation generation was ultimately built directly in
│                              #    eval/ (nim_client.py, flowbench_adapter.py) as an evaluation
│                              #    harness, not as this production adapter layer or a
│                              #    /verify-batch endpoint — no Module 01 integration exists yet.
└── ai_refinement/             # ⏳ LLM-based diagnostic refinement (originally-planned Phase 2)
                               #    — not implemented; no code under this name exists.
```

---

## 4. Implementation Roadmap (6 Phases)

| Phase | Document | Scope | Status |
|-------|----------|-------|--------|
| **Phase 1** | `05_core_hardening.md` | Fix solver bugs, increase test coverage, validate thresholds | **Done** — hardening happened, but as a series of engineering sessions rather than this doc's original plan; see its historical-document banner. 246 tests passing today. |
| **Phase 2** | `06_ai_refinement.md` | Integrate OpenAI GPT-4o-mini for counterexample explanation, certificate narrative, guard simplification | **Not implemented.** No code under `ai_refinement/` or equivalent exists. This is the one phase whose original "Pending" status is still accurate. |
| **Phase 3** | `07_multi_impl.md` | Self-consistency sampling adapter, multi-implementation orchestrator, `/verify-batch` endpoint | **Done, differently.** Multi-implementation generation and comparison exist (`eval/nim_client.py`, `eval/flowbench_adapter.py`, `comparison_mode` in the comparator), but as an evaluation harness against 3 real LLM APIs, not this doc's planned adapter layer or `/verify-batch` endpoint. See its historical-document banner. |
| **Phase 4** | `08_eval_data.md` | 4-layer evaluation data generation (golden, augmented, mutation, adversarial) | **Done, differently.** A mutation-based evaluation corpus exists (`eval/mutate.py`, 10 operators, 427 applicable mutants) plus the multi-implementation natural-bug corpus from Phase 3 above — not this doc's originally-planned 4-layer structure. See its historical-document banner. |
| **Phase 5** | `09_experiments.md` | Seeded bug detection, metric calibration, threshold tuning | **Done.** See `eval/results/calibration_report_differential.md` and `eval/results/session_b_report.md` for current, verified numbers — not this doc's original plan. See its historical-document banner. |
| **Phase 6** | `10_integration.md` | Module 03 API contract, thesis documentation, supervisor checkpoint | **Partially done.** The Module 03 API contract now exists at `docs/module02/12_wir_and_certificate_contract.md` (current, generated from source). See `10_integration.md`'s historical-document banner for the rest of this phase's original scope. |

---

## 5. External Interfaces

### Input: `POST /verify` — `CodePayload`

The implemented endpoint takes a single field (`main.py: CodePayload`). A `specification` field (to carry Module 01's output directly into a single combined-verification call) is planned but not currently part of the accepted schema.

```json
{
  "source_code": "def handle_incident() -> str:\n    incident = ServiceNow_incident__4_0_0__retrievewithwhere_incident()\n    if incident.impact == 'high':\n        ..."
}
```

### Output: actual `/verify` response (flat wire format)

The current `_run_verification` returns a flat object (not the nested `wir`+`certificate` shape that was originally envisioned). Every phase (V3, compile, V2, V1) runs in its own try/except and contributes a per-layer `status` (`"OK"` / `"ERROR"` / `"SKIPPED"`) plus a `reason` to the `layers` key — a fatal earlier-phase failure marks later phases `SKIPPED` with the upstream reason rather than leaving them silently absent. On error the top-level keys are the same shape with `passed: false`, a `message`, and every `layers` entry `"ERROR"`. The whole call is wrapped in a wall-clock timeout (`VERIFY_TIMEOUT_S` env var, default 30s) — see `docs/module02/12_wir_and_certificate_contract.md` for its documented boundary (it reliably bounds a hung Python loop; it cannot, in CPython, preempt a single long-running C-level statement holding the interpreter lock).

Below is a **real response**, generated locally against this repo's own `module_02_extract/inputs/loan_approval.py` sample (`v3_details`/`v2_details`/`v1_details`/`wir` omitted here for brevity — they're large nested objects, present in the real response):

```json
{
  "v3_coverage": 1.0,
  "v3_abort": false,
  "v2_confidence": 1.0,
  "v1_confidence": 1.0,
  "combined_confidence": 1.0,
  "passed": true,
  "message": "WIR validated -- passed to Module 03.",
  "layers": {
    "v3": { "status": "OK", "reason": "V3 structural extraction passed quality gate." },
    "v2": { "status": "OK", "reason": "V2 symbolic refinement complete." },
    "v1": { "status": "OK", "reason": "V1 dynamic tracing passed." }
  }
}
```

The combined-confidence formula for a less-than-perfect run, worked through for illustration (not a live run): `v1_confidence=0.92`, `v2_confidence=0.85` gives `combined_confidence = 1 - (1 - 0.92)(1 - 0.85) = 0.988` — the three-term formula's old example value of `0.9997` is not reachable under the current two-term formula for these inputs.

### Planned, not implemented: batch output (originally-planned Phase 3)

No `/verify-batch` endpoint exists. This shape was the original plan for the adapter-layer multi-implementation orchestrator described in §4's Phase 3 row; that work happened instead in `eval/` as an evaluation harness (see `eval/results/multi_impl_report.md`), not as this production endpoint. Kept here as a still-open design sketch, not current behavior.

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
| **Three independent modes, but only two vote** | Independent failure surfaces prevent correlated failures. V3 (structural fidelity) acts as a gate rather than a voting term — see §2's formula section for why the original three-term product was replaced. |
| **Combined = 1 - (1-v1)(1-v2)** | Standard parallel-system reliability formula for the two behavioral-correctness layers. Each independently contributes evidence; V3 gates instead of voting. |
| **0.95 certification threshold (self-mode)** | Empirical target, calibrated during the eval sessions described in §4's Phase 5 row. Differential mode (verifying a program against a *different* program's WIR — mutants, or independent implementations) uses a separately-calibrated operating point on `combined_confidence`, currently `tau = 0.10` (below which a run is flagged), selected via Youden's J on a held-out split — see `eval/results/calibration_report_differential.md`. |
| **OpenAI GPT-4o-mini for refinement** *(not realized)* | This was the plan for the never-implemented AI-refinement phase (§4, Phase 2). Recorded here as design history, not current behavior — no code exists under this decision. |
| **Self-consistency in adapter layer** *(not realized as planned)* | Multi-implementation generation was originally planned as a pluggable adapter layer in `src/`. It was ultimately built inside `eval/` instead (`nim_client.py`, `flowbench_adapter.py`), as an evaluation harness against real LLM APIs rather than a production adapter — see §4's Phase 3 row. |
| **4-layer evaluation data** *(not realized as planned)* | The originally-planned golden/augmented/mutation/adversarial 4-layer structure was not built. What exists instead is a mutation-based corpus (`eval/mutate.py`, 10 operators) plus a real multi-implementation natural-bug corpus (3 LLM model families) — see §4's Phase 4 row. |

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
