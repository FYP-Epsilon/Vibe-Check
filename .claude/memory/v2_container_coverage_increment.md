---
name: v2-container-coverage-increment
description: RESOLVED — e4ba019 ported onto the modularized package (T4, commit ff0b1d4) including the coverage-credit formula follow-on
metadata:
  type: project
---

**RESOLVED 2026-07-04** on branch `fix/mod2/verdict-and-eval-corpus`, commit `ff0b1d4` (T4 in [[session-2026-07-04-t1-t7-implementation]]). `e4ba019` (below) never got merged into `develop` and its target file no longer existed post-modularization, so it was ported by hand onto `src/z3_sym_engine/{concolic,evaluator,tracer}.py`. The "OPEN FOLLOW-ON" this memory used to track is done: `_emit_certificate` now has a coverage-credit term (`0.5*branch_diversity_score + 0.3*min(covered_edges/4, 1.0)`, applied only when `solver_rate == 0 and covered_edges >= 2`). Verified: the list-loop-with-if/else test case now gets confidence 0.8 (was 0.0) with the same 4-edge/1.0-diversity coverage e4ba019 originally measured. Regression tests added in `tests/test_z3_sym_engine.py`.

Original increment notes below, kept for the historical measurement numbers.

Scoped first increment for the V2 container gap (vulnerability #5), on branch `fix/mod2/phase1-symbolic-hardening`, commit `e4ba019`. All 105 tests pass.

**Done:**
- `BoundedConcolicEngine._seed_containers` (called in `run()` after the input deepcopy): replaces empty `list`/`dict` inputs with small non-empty samples — lists get 2 type-hinted scalars; dicts get the string keys the function actually subscripts (discovered by walking the source AST for `param["key"]`), else generic `k0/k1`. This gets concolic execution INTO container loops/branches instead of bailing to V1.
- `SymbolicEvaluator.visit_Call`: `len(x)` of a container concrete on the current path returns `z3.IntVal(len(x))` (concrete_state threaded through `_eval_symbolic`), so length guards like `len(items) > 3` carry real meaning.

**Measured (before→after, `_seed_containers` disabled vs enabled):** list loop+branch `covered_edges` 1→4, `branch_diversity_score` 0→1.0; dict-key branch 0→1 edge. **Coverage goal achieved.**

**OPEN FOLLOW-ON (next decision):** V2 `confidence` still reads **0.0** for pure-container functions despite full branch coverage, because the confidence formula in `_emit_certificate` keys off solver `iterations`/`feasible_paths`/`solver_success_rate` — and a pure-container function has **no scalar inputs to re-solve**, so `_concolic_iteration` returns None on the first call (`iteration` stays 0). The covered_edges/diversity are computed but **not used** in the confidence number.

**Why:** the seeding fixed coverage but not the headline confidence metric the certificate composes. **How to apply (next session):** decide how the certificate should credit a fully-covered-but-unsolved path — e.g. fold `branch_diversity_score`/coverage into the V2 confidence, OR count an initial fully-traced path as a successful iteration. This touches `_emit_certificate`'s confidence for ALL functions (the core thesis artifact), so it is a deliberate, test-guarded change — add a regression test asserting container functions get non-zero V2 confidence. Deferred full symbolic-length/element solving remains out of scope. See [[module02-rd-deliverable]], [[z3-double-reset-misdiagnosis]], [[module01-ownership-boundary]].
