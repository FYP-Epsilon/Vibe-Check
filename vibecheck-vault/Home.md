# VibeCheck — Research Vault

> Post-hoc **verified translation validation**: formally checks whether LLM-generated Python workflow code conforms to its originating **BPMN 2.0** specification, producing a quantified, evidence-backed certificate rather than a proof.
> FYP Group Epsilon, Faculty of IT, University of Moratuwa. Snapshot: **2026-07-30** (`main-demo` @ `5c65046` — **declared the FINAL implementation**; future changes are bug fixes, not architecture).

## Start here

- [[Project Overview]] — one-document tour of the whole system: problem, architecture, module-by-module implementation, contracts, evaluation numbers, limitations
- [[Next Steps]] — the research roadmap that got us here (P0–P3); most items now ✅ done — kept as the audit trail of *how* the final state was reached

## Final evaluation results (plain-English, current as of 2026-08-03)

- [[Final Evaluation Results/Full Project Evaluation Results|Full Project Evaluation Results]] — what the whole system does, end-to-end numbers, how we evaluate it, system-wide novelty
- [[Final Evaluation Results/Module 01 Evaluation Results|Module 01 Evaluation Results]] · [[Final Evaluation Results/Module 02 Evaluation Results|Module 02 Evaluation Results]] · [[Final Evaluation Results/Module 03 Evaluation Results|Module 03 Evaluation Results]]

## Novelty documents (research positioning)

- [[Module 01 - Specification Analysis/Module 01 Novelty|Module 01 Novelty]] — PBCTS, mutation self-validation of generated specs, BPMN→LTLf with coverage gates vs prior art
- [[Module 02 - Verified IR Extraction/Module 02 Novelty|Module 02 Novelty]] — WIR + 3-layer calibrated certificate, differential tracing vs translation validation / LLM-codegen verification literature
- [[Module 03 - Equivalence Engine/Module 03 Novelty|Module 03 Novelty]] — divergence-sensitive equivalence for LLM code, behavioral clustering, alive-extension LTLf→LTL bridging vs prior art

## Canvases

- [[Project Architecture.canvas|Project Architecture]] — full dual-track pipeline, all four modules (updated to the wired end-to-end state)
- [[Project Status.canvas|Project Status]] — whole-project status snapshot, strengths, remaining gaps
- [[Module 01 - Specification Analysis/Module 01 Architecture.canvas|Module 01 Architecture]] · [[Module 01 - Specification Analysis/Module 01 Status.canvas|Module 01 Status]]
- [[Module 02 - Verified IR Extraction/Module 02 Architecture.canvas|Module 02 Architecture]] · [[Module 02 - Verified IR Extraction/Module 02 Status.canvas|Module 02 Status]]
- [[Module 03 - Equivalence Engine/Module 03 Architecture.canvas|Module 03 Architecture]] · [[Module 03 - Equivalence Engine/Module 03 Status.canvas|Module 03 Status]]
- [[Module 04 - Verification Portal/Module 04 Architecture.canvas|Module 04 Architecture]] · [[Module 04 - Verification Portal/Module 04 Status.canvas|Module 04 Status]]

## Module notes

- [[Module 01 - Specification Analysis/Module 01 Knowledge|Module 01 — Specification Analysis]] 🟢 (final 4-phase PBCTS pipeline; startup fixed, **56/56 tests pass** post PR #89 (98 total incl. eval/), slim Dockerfile, status codes unified)
- [[Module 02 - Verified IR Extraction/Module 02 Knowledge|Module 02 — Verified IR Extraction]] 🟢 (most mature, measured; call-order WIR exposed from `/verify`, container fixed, **256 tests**)
- [[Module 03 - Equivalence Engine/Module 03 Knowledge|Module 03 — Equivalence Engine]] 🟢 (C++/SPOT engine covers all phases A–D; **M01 ingestion wired** (`property_ingest.py`), alive-extension LTLf→LTL bridge, real FastAPI service, **142/145 test functions pass** (2 known-gap failures, unimplemented hash feature))
- [[Module 04 - Verification Portal/Module 04 Knowledge|Module 04 — Verification Portal]] 🟢 (all three engine pages now HTTP incl. the fixed equiv page; **live E2E `/check` demo added** — see [[Final Evaluation Results/Full Project Evaluation Results|Full Project Evaluation Results]]; still zero automated tests of its own)

## Repo docs (vault copy)

The repo's entire `docs/` tree, imported @ `7089711`. **`docs/` has since been removed from the repo** (develop @ `05fae60`) — these vault copies are now the surviving snapshot (git history retains the originals).

- [[Project Repo Docs Index]] — architecture plans, thesis Ch. 5 draft + figures, WIR schema docs
- [[Module 01 Repo Docs Index]] · [[Module 02 Repo Docs Index]] · [[Module 03 Repo Docs Index]]

## Key concepts

- **WIR (Workflow Intermediate Representation)** — JSON CFG, the schema-validated contract between Module 02 (producer) and Module 03 (consumer): `shared_schemas/wir_schema.json`. `/verify` now returns **two views**: `wir` (definition-order) and `call_order_wir` (D2 lifting — driver-function CFG with sibling calls as task boundaries, the view Module 03's lifter actually needs).
- **Dual-track independence** — spec track and code track never see each other's input; they meet only in Module 03 as independent mathematical objects, avoiding circular verification. Preserved even in the bridge: `property_ingest.py` *ports* the LTLf normalization it needs rather than importing Module 01's source.
- **V1/V2/V3 certificate** — V3 structural hard gate, V2 Z3 symbolic, V1 dynamic differential tracing; `combined = 1 − (1−v1)(1−v2)` in self-mode, `combined = v1` in differential mode; acceptance ≥ 0.95.
- **Divergence-sensitive stuttering bisimulation** — refuses to merge a silently-infinite loop (e.g. hallucinated `while True: pass`) with a normal wait state. Implemented in both Python (`stuttering_engine.py`) and C++ (`spot::scc_info` + Groote–Vaandrager).
- **PBCTS (Progression-Based Constructive Trace Synthesis)** — Module 01's Phase 4: LTLf formulas are *progressed* step-by-step in pure Python to construct satisfying traces `T_spec`, then bidirectionally aligned with model traces (`EAS_BDA`, `IDCD` convergence gate, `SCSL` self-correction loop ≤ 3 rounds) → Formal Reliability Certificate v2.0.
- **LTLf→LTL bridge — WIRED (was the headline gap).** Module 03's `property_ingest.py` (PR #72) loads `module_03_input.json`, tier-gates (only `node()`-free P1 properties are conformance-checkable today — 17.6% of the tier, corpus-measured; P0/P2/P3 excluded with reasons, never silently dropped), collapses `start(T)`/`done(T)` to one flat **quoted** atom per task ("Option B"), and `check_compliance` applies the **alive-extension** finite-trace bridge (`spot::from_ltlf`, De Giacomo & Vardi) with mutual-exclusion edge closure for non-looping automata (PR #70).
- **`flow-bench/`** — vendored upstream copy of IBM FLOW-BENCH (arXiv 2505.11646) at repo root; Module 02's eval harness uses its own derived copy under `module_02_extract/inputs/`.

## Headline numbers

**Module 02 eval** (`module_02_extract/eval/results/`):

| Metric | Value |
|---|---|
| Genuine-bug detection | 0.9952 (n=210) |
| False-alarm rate | 0.0588 (n=51) |
| WIR structural F1 | 1.0000 |
| Natural-bug detection | 1.0 strict / 0.9329 task_only |
| Calibration corpus | 427 mutants, 10 operators |
| Natural-bug corpus | 3 LLM families, 20 admitted / 164 rejected |

**End-to-end M01→M02→M03 eval** (`demo/eval_e2e/results/`, updated 2026-08-03 after P4_Task_Coverage ingestion expanded the gold set; small n, CIs by design — see [[Final Evaluation Results/Full Project Evaluation Results|Full Project Evaluation Results]] for the full plain-English writeup):

| Metric | Value |
|---|---|
| Gold specs | 18 (up from 6 pre-P4_Task_Coverage) |
| Abstention (honest INCONCLUSIVE) | 0.383 [0.26, 0.52] (n=60) |
| Detection (decisive trials) | 0.162 [0.06, 0.32] (n=37) |
| False-alarm rate | 0.000 [0.00, 0.34] (n=9) |
| Counterexample quality | 0.833 [0.36, 1.00] (n=6) |
| M03 oracle-agreement run (earlier, definition-order lifting — see [[Final Evaluation Results/Module 03 Evaluation Results|Module 03 Evaluation Results]] for the caveat) | 29 specs, 58 checks — 100% agreement with M01's `evaluate_ltlf` oracle on all 35 decisive verdicts |

## Current state

The headline end-to-end claim is **wired and demonstrated**: BPMN spec → Module 01 (LTLf property suite) → Module 02 (call-order WIR) → Module 03 (Phase A–D conformance check) → PASS/FAIL + readable counterexample, run against real LLM-generated FLOW-BENCH implementations (`demo/e2e_demo.py`), with a measured evaluation harness on top (`demo/eval_e2e/`). As of 2026-08-03, this is also demonstrated **live against the actual deployed HTTP services** (`module_04_ui/src/e2e_orchestrator.py`, the "🔄 E2E Pipeline" UI page), not just the in-process harness — see [[Final Evaluation Results/Full Project Evaluation Results|Full Project Evaluation Results]]. CI runs per-module tests plus a real docker-compose startup check.

**Remaining honest gaps** (tracked, not hidden): only the `node()`-free slice of P1 properties is conformance-checkable (17.6% of the tier); loop-bound safety checking has no home in the canonical path (`P2_Quality_Limits` excluded, legacy `run_pipeline` is its only implementation); non-terminating-trace semantics vs termination-requiring properties is an explicitly deferred design decision; E2E detection 0.162 at small n (task-drop mutants are often unobservable → honest abstention, currently 0.383); M04 still has zero automated tests of its own (though the `/check` endpoint now has a live UI demo); V2 contributes ≈ nothing on the current corpus (certificate is V1-driven — stated in the prominent docs).
