---
name: module01-e2e-plan-findings
description: Module 01 verified state 2026-07-11 — FLOW-BENCH BPMN corpus IS public (IBM/flow-bench, Apache-2.0); only 3/100 real diagrams pass M01 end-to-end; suite kills its own correct graph; full E2E plan in .claude/module01_e2e_plan.md
metadata:
  type: project
---

Verified 2026-07-11 (Fable 5 session executing [[fable-module01-e2e-plan-prompt]]; deliverable: `.claude/module01_e2e_plan.md`). All claims re-verified against `develop` @ `febd547` and empirically by running M01's pipeline (seed 42).

**FLOW-BENCH bpmn-refs: AVAILABLE.** `github.com/IBM/flow-bench` (Apache-2.0) has `data/output/uid_N_output.bpmn` — the exact `$ref` targets of `module_02_extract/inputs/conditional_ootb.yaml`. 100 files (uid 90 missing), 100/100 parse, same BPMN namespace M01 expects. Also `data/context/` (48 more diagrams). This supersedes the "unobtainable?" question in the prompt; [[flowbench-groundtruth-finding]] (no executable-Python labels) still holds for M02's E1 but doesn't apply to M01.

**Empirical corpus run (headline)**: only **3/100** diagrams pass M01 end-to-end. Phase 1 FAIL 37/100 (V3 counts nodes recursively `.//` but V2 maps only direct process children → subProcess files collapse coverage; mean 0.776, min 0.214). Phase 2 crashes 6/100 (`VerificationException` — any XOR-join or all-unconditioned XOR split; the whole corpus has ZERO `conditionExpression`: predicates live in gateway `name` = "Decision: x == 'y'"). Phase 3 FAIL 54/57 (kill ratios 0.65–0.95).

**Soundness (worse than M02's V3=1.0)**: sequence template `G(start(B) -> F(done(A)))` is temporally backwards → the **unmutated original graph is killed by its own suite** (base false-alarm ≈ 100%). P0 sentinels `G(!done U start)` are never evaluated (`_evaluate` fallthrough → True, mutation_refiner.py:171). `_synthesize_killer`'s fallback `G(refined_constraint_N)` is special-cased to always fail (mutation_refiner.py:149-151) — an auto-kill token rigging the kill ratio. Phase 3 RNG unseeded → nondeterministic verdicts; killed_ratio divides by fixed 20.0. `api.py` is a SyntaxError (IndentationError line 45) — dead file; FastAPI app is `main.py` (roles swapped vs older notes). `module_01_spec/tests/` now exists but is empty.

**Novelties**: items 1–5 partially in code with load-bearing defects; NC-1..4, super-node, Phase 4, TCB = zero code (grep confirmed). Corpus has ZERO parallelGateway → super-node abstraction recommended for descoping (also conflicts with NC-4 localization).

**M03 blast radius**: M03 consumes NOTHING from M01 today — `model_checker.check_all_properties` takes `(name, monitor_LTS)` built inside M03; no module_01/ltlf refs in its pipeline/main. Fallback = property-string contract doc + M03's own lifter; Phase 4 becomes M01-internal QA.

**How to apply**: next coding session = T1–T7 order in the plan's Synthesis §7 (T1 mechanical fixes → T2 corpus fetch + pre-fix baseline → T3 soundness core → T4 extraction/gateway fixes → T5 adapter+gold labels → T6 mutation corpus/calibration → T7 SPOT normalizer). Stats floor: no "≥90%" detection claim under 150 EVAL mutants; pre-register 90% (not 95%), target 280 mutants. M01 is the teammate's code ([[module01-ownership-boundary]]) — confirm who executes.
