---
name: module03-e2e-plan-findings
description: Module 03 verified state 2026-07-11 — clustering scores 0.459/0.630 on its own contract ground truth (task calls never become labels + refinement finer than stuttering equivalence); gate refuses 38/101 clean bases; pytest uncollectable; full plan in .claude/module03_e2e_plan.md
metadata:
  type: project
---

Verified 2026-07-11 (Fable 5 session executing [[fable-module03-e2e-plan-prompt]]; deliverable: `.claude/module03_e2e_plan.md`, sibling of [[module01-e2e-plan-findings]]). All claims verified against `develop` @ `febd547` AND empirically by running the pipeline on the real multi-impl corpus.

**Split-brain confirmed + sharpened** ([[module03-split-brain-finding]] grounds this): Python path (tested, orchestrated by pipeline.py) vs C++/SPOT path (Docker CMD, M04's import target, Linux/cp312 `.so`). Neither has spec ingestion — Phase D = 2 canned checks (loop-bound trap + reachability of literal "error/abort/panic" labels). Docs describe a THIRD codebase: `m_code_lifter.py`/`verify_determinism.py`/`test_equivalence.py`/`main_role_c.py` don't exist in the repo. `pipeline.py` clusters ONE WIR's own fragments (incl. stub defs) — no batch-of-implementations entrypoint exists anywhere.

**Headline empirical run** (M02 V3 → Python lifter → clustering, 13 uids with admitted variants, contract §4 ground truth): **pairwise precision 0.459 / recall 0.630**. Both failure directions at once: (a) task calls NEVER become transition labels (`lifter.py:284-319` labels from guards only; uid_1 base workflow = 3 states, all tau) → rejected_behavioral variants merge with bases (20 FP pairs); (b) guard strings compared as opaque text (`folder['name'] == None` ≠ `not (folder_name is not None)`) + partition refinement finer than stuttering bisimulation (tau-prefix/mid-tau micro-tests → False where the definition says True, `stuttering_engine.py:324-415`) → bases split from their own ADMITTED variants (10 FN pairs). Divergence-sensitivity itself works (micro-test correct).

**Other verified defects**: quality gate reads M02's `guard_success_rate` (= CNF-decomposition fraction, `certificate.py:19`) as confidence@0.95 → **refuses 38/101 clean bases** incl. uid 4. Constant `unknown_unresolved_guard` fallback label merges unrelated programs (`lifter.py:359`). `tests/test_cpp_engine.py:1` = bare path line = SyntaxError → `pytest tests/` cannot collect (37 tests pass only as `pytest tests/test_pipeline.py`); NO CI exists. C++ `compute_deterministic_hash` is `std::hash`, not SHA-256 as claimed, and has zero callers. Parallel-gateway abstraction: DESIGN-ONLY both paths (and 0 parallel constructs in the whole shared corpus).

**Corpus counts** (manifest.json verified): 294 records, 184 screened-pass, **20 admitted (13 uids)**, 164 rejected_behavioral (95 uids) — too small for headline rates; report pilot figures + bootstrap CI only.

**How to apply**: coding session = T1–T8 in the plan's Synthesis §7 (T1 test/CI fix → T2 commit 0.459/0.630 baseline eval → T3 gate+labels → T4 task-call observability → T5 stuttering rewrite → T6 canonicalization+batch entrypoint → T7 Phase-D corpus + M01 contract doc → T8 matcher port). Canonical-path recommendation: **Python canonical, C++ port-and-freeze** (needs owner ratification — M03 is the teammate's module). The M01→M03 property-suite contract doc is shared with M01 plan's T5-prep — co-author once, both plans reference it. `comparison_mode="task_only"` for any M02-comparator reuse (contract §7).
