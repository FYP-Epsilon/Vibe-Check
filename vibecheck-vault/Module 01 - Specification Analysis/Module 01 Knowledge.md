# Module 01 — Specification Analysis (Knowledge Note)

> **Purpose:** The *spec track* of VibeCheck. Converts a **BPMN 2.0 XML** process model into a formal specification — tiered LTLf properties plus a **PBCTS-generated trace certificate** — that Module 03 (equivalence engine) is meant to verify LLM-generated Python workflow code against.

Repo: `module_01_spec/` | Service: FastAPI (`main.py`, "VibeCheck Spec Engine v2.0.0"), docker service `spec-engine` | ~2,260 LOC across 11 src files + 6 test files (~700 LOC, 28 tests)

> ⚠ **Architecture pivot (2026-07-28):** the SPOT/HOA Phase 4 (`automata_lifter.py`) and process-mining Phase 5 (`process_mining_alignment.py`) were **deleted** after one day and replaced by a pure-Python **PBCTS** Phase 4. SPOT no longer appears in any executable code — and as of 2026-07-29 (PR #82) the Dockerfile no longer builds SPOT from source either; the dead weight is gone.

## The 4 Phases

| Phase | Component | What it does |
|---|---|---|
| 1. Semantic Extraction | `semantic_extractor.py` | BPMN XML → semantic graph, V3→V2→V1 layers, Kripke labeling (`start(X)`/`done(X)`/`node(X)`). **Now dynamic**: every XML element with an `id` (minus a ~26-tag exclusion list) counts toward coverage; new **`_recovery_pass()`** re-scans from the XML root for unmapped elements and re-certifies once. Gate: **node coverage ≥ 1.0**. |
| 2. LTLf Synthesis | `ltlf_synthesizer.py` | Tiered properties: **P0 safety / P1 liveness / P2 fairness**. Implicit-else resolution, template instantiation, P0/P2 sentinels. Gate: **guard-resolution coverage ≥ 1.0**, else `VerificationException`. |
| 3. Mutation Self-Validation | `mutation_refiner.py` + `adversarial_generator.py` | 5 mutation operators; traces now from **bounded iterative DFS** (loops allowed, cap 100). **Multi-round self-healing** (`max_rounds=3`): re-audit with killer-enriched suite, adversarial red-teaming in round 0 (killers injected into `P3_Adversarial_Defenses`). FAIL certificate lists `unresolved_vulnerabilities` with `human_action_required`. Gates: **C_struct ≥ 1.0 AND kill ratio δ ≥ 1.0**. |
| 4. PBCTS + Alignment | `ltlf_progression.py` (192) + `trace_synthesizer.py` (153) + `bidirectional_alignment.py` (172) | **Progression-Based Constructive Trace Synthesis.** Pure-Python LTLf progression (`progress`, `simplify`, `extract_obligations`) replaces SPOT automata: `PBCTSEngine` conjoins the suite and enumerates satisfying traces `T_spec` (obligation pruning + memoized branching, `bound_k`, max 200 traces), scoring **SCov** = 0.4·node + 0.4·branch + 0.2·depth. `PBCTSAlignmentPipeline` aligns `T_spec` vs model traces bidirectionally → precision/recall/**EAS_BDA** (F1 harmonic mean); gate = **IDCD convergence**: \|ΔEAS\| < 0.001 for some k ≤ 20. **SCSL** (Self-Correcting Specification Loop) converts over-specification gaps into `!(F(a & X(b)))` corrections (`P4_SCSL_Corrections`, ≤ 10), re-running PBCTS up to 3 rounds. Output: **Formal Reliability Certificate v2.0** (`method: "PBCTS_BDA_IDCD"`) with differential analysis (spec-only/model-only traces, semantic-gap examples). |

## Quality Gates (current)

- Phase 1: node coverage ≥ 1.0 (dynamic node set, one recovery retry)
- Phase 2: guard-resolution coverage ≥ 1.0
- Phase 3: C_struct ≥ 1.0 AND kill ratio δ ≥ 1.0 (≤ 3 self-healing rounds)
- Phase 4: **IDCD convergence** (\|ΔEAS\| < 0.001, k ≤ 20); confidence = 1−ε if converged else SCov. (Doc *targets* of EAS ≥ 0.90 / SCov ≥ 0.85 are not enforced in code.)

## Novelty Scoreboard — churned again

- **PBCTS / EAS_BDA / IDCD / SCSL** — IMPLEMENTED (the new Phase 4 stack; doc `04_pbcts_trace_synthesis.md` still labeled "Status: Planned" though shipped).
- **Adversarial red-teaming** — IMPLEMENTED, simulated heuristics (round 0 of Phase 3).
- **SPOT/HOA automata lifting, GED, process-mining EAS** — implemented, then **DELETED** one day later in the pivot.
- **SFI / ΔH / PWBE** — implemented, then removed earlier in the same cycle. Nothing remains.
- **CGSR-like self-healing** — IMPLEMENTED in spirit: Phase 3 multi-round killer refinement + Phase 4 SCSL loop.

## Module handoffs

- **To Module 03:** `export_for_module_03()` → `module_03_input.json` = `{semantic_graph, ltlf_property_suite, loop_bound_documented}` — LTLf **strings** (loop bound now regex-parsed from `P2_Quality_Limits`). **Now consumed** by Module 03's `property_ingest.py` (PR #72) — tier-gated, de-duplicated, normalized to SPOT-ready quoted atoms. A real bug was found and fixed at this seam while building the e2e demo: `export_for_module_03()`'s `tier_semantics` only covered 3 of the 5 tiers the suite can contain, hard-erroring `load_property_suite` on real specs; fixed in `api.py` + regression test (`test_real_export_is_ingestible_by_module_03`).
- **To Module 02:** `export_for_module_02()` → `module_02_input.json` = `{semantic_graph, task_patterns}`; Module 02's `randomized.py` already consumes `task_patterns` — the one **actually wired** cross-module handoff.

## Status & Issues (2026-07-29, main-demo @ `5c65046` — FINAL)

- ✅ 4-phase pipeline implemented end-to-end (`api.py::run_module_01_pipeline`, 260 LOC); PBCTS replaces SPOT with stdlib-only code.
- ✅ **Startup bug FIXED** (`bc35c02`, 2026-07-29): the dead `automata_lifter` import is out of `main.py`; the FastAPI app and the Docker `uvicorn src.main:app` CMD start cleanly. CI (PR #80) now runs a real docker-compose startup check so it stays fixed.
- ✅ **Tests exist and pass** (PR #79): 6 test files, 28 tests — phase-1/phase-3 gates, PBCTS convergence, SCSL, status-code consistency, M03 export, main API. **Verified: 28/28 pass in ~0.3s** (2026-07-29).
- ✅ **Status-code inconsistency FIXED** (PR #81): `api.py` and `main.py` both report unconverged PBCTS as `PASS_PBCTS_UNCONVERGED`; a dedicated test (`test_status_code_consistency.py`) pins the agreement.
- ✅ **SPOT dropped from the Dockerfile** (PR #82): 19-line slim Dockerfile (python:3.10-slim + pip + uvicorn), with a candid comment explaining the removal. `requirements.txt` is fastapi / uvicorn / networkx.
- ✅ **`formula_normalizer.py` docstrings FIXED**: rewritten to say plainly the class is UNUSED dead code, never imported by `api.py`/`main.py`, and that M03's `property_ingest.py` ports its own (different) normalization — "do not resurrect this class as-is."
- ✅ **M03 handoff WIRED** (PR #72 + #70): Module 03's `property_ingest.py` ingests `module_03_input.json` (tier-gated: only `node()`-free P1 properties are conformance-checkable today — 17.6% of the tier; P0/P2/P3 excluded with explicit reasons), and the LTLf(finite)→LTL(infinite) semantic gap is bridged on M03's side via the alive-extension (`spot::from_ltlf`, De Giacomo & Vardi) for non-looping automata. Demonstrated end-to-end in `demo/e2e_demo.py` and measured in `demo/eval_e2e/`. Remaining scope limits live in [[../Module 03 - Equivalence Engine/Module 03 Knowledge|Module 03 Knowledge]].
- ✅ **FlowBench evaluation design session (2026-08-02) found 3 real defects in mainline; all 3 fixed in [PR #89](https://github.com/FYP-Epsilon/Vibe-Check/pull/89) `fix/mod1/flowbench-defects`, merged into `demo/evaluation-finale` (not yet `main-demo`)** — see [[FlowBench Evaluation Investigation/M01 FlowBench Evaluation Methodology|the original diagnosis memo]] and [[FlowBench Evaluation Investigation/Phase 2 - Defect Fixes (PR #89)/PR_fix_mod1_flowbench_defects|the fix PR description]], both independently re-verified before AND after merge (reproduction logs alongside each; 56/56 tests re-confirmed on the merged tree). Before → after, corpus-wide (148 FlowBench diagrams):
  - **Suite soundness** (does the suite admit its own source diagram?): 79/148 → **145/148**; branching diagrams 0/50 → **49/50**.
  - **Phase 4** (`ltlf_synthesizer.py:225`'s hardcoded P2 property had a `/* loop_bound=10 */` comment M01's own `evaluate_ltlf` couldn't tokenize): `FAIL_WITH_ERRORS` 148/148 → **4/148**; real v2.0 PBCTS certificates 0/148 → **90/148** (54/148 now correctly abort at the Phase 3 gate instead of masking the failure downstream). Fixing this uncovered a **4th defect** the original memo missed: `evaluate_ltlf`'s tokenizer had no rule for `node(...)` atoms at all, separately unparseable — fixed in the same commit (`a3acf0b`).
  - **Kill-mechanism accounting** (`LTLfAuditor.is_killed` scored a disconnected mutant as "killed" without consulting any property): the conflation is now split into `mutants_killed_by_property` / `mutants_killed_by_disconnection` / `property_kill_ratio` / `kill_evidence_vacuous`, added append-only (`is_killed`'s 2-tuple contract kept unchanged — GitNexus rated its caller `execute_validation_pipeline` HIGH risk, 15 impacted symbols). **The gate threshold was deliberately left unchanged**: property kills remain 0 on sound-suite diagrams even after the fix — this makes the vacuity visible, it does not make the suite stronger.
  - **`P4_Task_Coverage` unsoundness on branching diagrams**: fixed with a hybrid not in the original memo — `F(done(X))` kept unconditional only for tasks on every start→end path (computed the same way `_generate_traces` enumerates paths, to avoid reintroducing a synth/audit mismatch), conditional `G(start(X) -> F(done(X)))` elsewhere. Beat both memo-proposed candidates: same soundness (145/148) with zero of the 437 completion obligations dropped. Side effect, disclosed rather than hidden: removing the over-strong obligation drops corpus-wide property kills from 1248 to 168, and 54/148 diagrams no longer pass the Phase 3 gate on property evidence — this is the vacuity in the point above becoming visible, not a regression.
  - **A 5th defect found and left unfixed** (out of scope for this PR): the remaining 4 `FAIL_WITH_ERRORS` diagrams fail because `semantic_extractor` emits an empty proposition name (`node()`) for some elements — an extractor defect, not a tokenizer gap.
  - Tests: 35 → **56 passing**, all new fixes covered by corpus-driven regression tests, not just hand-written fixtures.
- ⚠ Doc *targets* (EAS ≥ 0.90 / SCov ≥ 0.85) remain unenforced in code; IDCD convergence is the only Phase 4 gate. Adversarial red-teaming is still simulated heuristics, not a real LLM.
- ⚠ Docs: the `docs/` tree was **removed from the repo** (develop @ `05fae60`) and survives only as vault copies ([[Module 01 Repo Docs Index]]); the module_summery page copy remains **doubly stale** — it describes the old *planned* SPOT integration that came and went.
- Reputation note: the churn era is over — 2026-07-29 was a cleanup day (tests, status codes, Dockerfile, CI, startup fix) with no further pivots. The final state is the first one that is both coherent and tested.

## Links

- [[Home]]
- [[Module 01 Novelty]] — research positioning vs prior art
- [[Module 01 Architecture.canvas]]
- [[Module 01 Status.canvas]]
- [[Module 01 Repo Docs Index]]
- [[FlowBench Evaluation Investigation/M01 FlowBench Evaluation Methodology|M01 FlowBench Evaluation Methodology]] — design memo + pilot findings (2026-08-02)
