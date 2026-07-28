# Module 01 — Specification Analysis (Knowledge Note)

> **Purpose:** The *spec track* of VibeCheck. Converts a **BPMN 2.0 XML** process model into a formal specification — tiered LTLf properties plus a **PBCTS-generated trace certificate** — that Module 03 (equivalence engine) is meant to verify LLM-generated Python workflow code against.

Repo: `module_01_spec/` | Service: FastAPI (`main.py`, "VibeCheck Spec Engine v2.0.0"), docker service `spec-engine` | ~1,950 LOC across 11 src files

> ⚠ **Architecture pivot (2026-07-28):** the SPOT/HOA Phase 4 (`automata_lifter.py`) and process-mining Phase 5 (`process_mining_alignment.py`) were **deleted** after one day and replaced by a pure-Python **PBCTS** Phase 4. SPOT no longer appears in any executable code — but the Dockerfile still builds SPOT 2.11.6 from source (dead weight).

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

- **To Module 03:** `export_for_module_03()` → `module_03_input.json` = `{semantic_graph, ltlf_property_suite, loop_bound_documented}` — LTLf **strings** (loop bound now regex-parsed from `P2_Quality_Limits`). Nothing in Module 03 consumes it yet.
- **To Module 02:** `export_for_module_02()` → `module_02_input.json` = `{semantic_graph, task_patterns}`; Module 02's `randomized.py` already consumes `task_patterns` — the one **actually wired** cross-module handoff.

## Status & Issues (2026-07-28, main @ `7089711`)

- ✅ 4-phase pipeline implemented end-to-end (`api.py::run_module_01_pipeline`, 194 LOC); PBCTS replaces SPOT with stdlib-only code.
- ⛔ **STARTUP BUG:** `main.py:11,16` still does `from .automata_lifter import AutomataLifter` — the module was deleted, so the FastAPI app (and the Docker `uvicorn src.main:app` CMD) raises `ModuleNotFoundError` on startup. The `/verify` route never uses the import.
- ⛔ **STILL ZERO tests** — third cycle running; gates and convergence logic entirely unexercised.
- ⚠ Status-code inconsistency: unconverged PBCTS is `FAIL_ALIGNMENT_UNPROVEN` in `api.py` but `PASS_PBCTS_UNCONVERGED` in `main.py`.
- ⚠ Dockerfile still builds SPOT 2.11.6 from source — heavy dead build step, nothing imports it. `requirements.txt` clean (fastapi, uvicorn, networkx).
- ⚠ `formula_normalizer.py` docstrings still promise "SPOT-compatible grammar"; nothing consumes it for SPOT anymore.
- ⚠ Docs: the `docs/` tree was **removed from the repo** (develop @ `05fae60`) and survives only as vault copies ([[Module 01 Repo Docs Index]]). The 00–05 set reflects the pivot; the module_summery page copy remains **doubly stale** — it describes the old *planned* SPOT integration (`SpotLTLfCompiler`, BuDDy) that came and went.
- Reputation note: two architectural pivots in as many days (SPOT→HOA, then HOA→PBCTS), each deleting the previous day's work including tests. The velocity is real; so is the churn.

## Links

- [[Home]]
- [[Module 01 Architecture.canvas]]
- [[Module 01 Status.canvas]]
- [[Module 01 Repo Docs Index]]
