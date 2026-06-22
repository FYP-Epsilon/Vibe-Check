---
name: z3-double-reset-misdiagnosis
description: The "P0 Z3 double-reset" bug was a misdiagnosis; real fix was an O(n^2)→O(n) solver refactor
metadata:
  type: project
---

The R&D plan (`module02_rd_plan.md` §3) listed a **P0 "Z3 double-reset"** bug — *"solver.reset() called before AND after each iteration at z3_sym_engine.py ~L4360–4397, kills accumulated path constraints."* **This was a misdiagnosis** (confirmed 2026-05-30 by reading the code + git blame).

Reality: `BoundedConcolicEngine._solve_for_inputs` (real location `module_02_extract/src/z3_sym_engine.py:947`; the file is only ~1183 lines so L4360 never existed) created a **fresh local `z3.Solver()` per call**. The two `solver.reset()` calls (added later in commit `ee8a3be`, a "solver hygiene" pass) were **no-ops** — resetting a fresh solver, then resetting one about to be GC'd. Path-constraint accumulation is held in `self.explored_path_conditions` (re-added as `z3.Not(pc)` each solve), which `reset()` cannot affect.

**Why:** matters because this was the #1 "cheapest fix" item; acting on it blindly would have "fixed" nothing. The real defect was a **performance smell** — re-adding all explored blocking clauses to a fresh solver every iteration is O(n²) over a run.

**How to apply:** Done on branch `fix/mod2/phase1-symbolic-hardening` (3 commits):
1. `1df3287` — removed the dead resets + misleading comment; refactored `_solve_for_inputs` to a persistent solver with incremental `push()/pop()` (transient query) + monotonic blocking clauses (`self._blocked_count`); migrated `_execute_concrete` step-counter guard `sys.settrace`→`sys.monitoring` with settrace fallback.
2. `869499c` — full V1 `WIRTraceCollector` `sys.monitoring` runtime path (settrace kept as fallback + `trace_callback` unit-test path). Event mapping reconciled (`PY_START`/`PY_RETURN`/`PY_UNWIND`/`RAISE`/`LINE`, locals via `sys._getframe(1)`); gated by `test_dynamic_tracer_parity.py` (8 cases, byte-identical vs settrace).

**Important:** the V1 migration is **behaviour-preserving only — NOT a perf or portability win** (V1 reads `f_locals` every line so PEP 669's low-overhead model doesn't apply; `sys.monitoring` is also CPython-only). So Critic-Q5's concerns are unaddressed — keep CPython-only as a documented thesis limitation. **Next highest-ROI item: `Module01Adapter`** (WIR-independent oracle, vulnerability #1) — not started. All 105 tests pass. Lesson: verify audit claims against primary source before "fixing." See [[module02-rd-deliverable]].
