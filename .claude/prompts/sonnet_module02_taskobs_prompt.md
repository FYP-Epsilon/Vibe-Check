# SESSION MANDATE — Module 02: task-observability alignment (follow-up to D1–D5, PR #25)

You are continuing on branch **`fix/mod2/verdict-and-eval-corpus`** in `C:\Research\FYP\Vibe-Check` (PR #25 is already open against `develop` — push further commits to the same branch; do not open a new PR). Baseline: **137 tests passing**. Module 02 only (`module_02_extract/`); other modules are teammates' — read-only.

## Why this session exists (verified against source 2026-07-04 — re-read cited lines before editing, they may have drifted)

The differential-mode calibration (`eval/results/calibration_report_differential.md`) measured J=0.0506, detection 0.43 vs false-alarm 0.39 — a coin flip. Verified root cause chain, in priority order:

1. **The V1 reference interpreter cannot execute task-API calls.** `WIRReferenceInterpreter._exec_stmt` (`src/dynamic_tracer/interpreter.py:180-184`) runs `exec(stmt, {"__builtins__": {}}, state)` and silently swallows the resulting `NameError` — so any `x = Some_Stub_Call()` never populates `state`, every downstream guard falls to permissive-False (`interpreter.py:175-177`), and every for-loop over that variable iterates nothing (`interpreter.py:88-91`). Confirmed: a *correct* base program (uid_4) scores combined 0.0 against its own WIR. There is no working baseline.
2. **Even with (1) fixed, stub calls are invisible in traces.** Stub-call assignments are WIR *block* nodes. The reference interpreter only emits `task_entry`/`task_exit` for WIR `task` nodes (`interpreter.py:61-67`), and the actual-side collector only records task events for functions matching `task_patterns`, which is just `[function_name]` (`src/main.py`, `_run_verification`, `task_patterns=[function_name]`). So a drop-step mutant that deletes a leaf stub call produces **zero trace difference** on either side. Detection currently rides only on indirect state→branch-count effects and exceptions — hence the noise.
3. (Known, deprioritized) collector `branch_point` events carry `observables` but no decision field (`src/dynamic_tracer/collector.py:186-192`, `316-322`), so D3's decision-aware comparison is a no-op on real runs. **Do not fix this session** — after task-event alignment, negate-guard mutants should be caught by *which stubs execute* per branch; we reassess afterwards with data.

The fix is **task-observability alignment**: make stub calls first-class observable events on BOTH sides of the differential comparison.

## Ground rules

1. `CLAUDE.md` GitNexus workflow applies: `npx gitnexus analyze` first (index predates recent commits), `gitnexus_impact` before modifying any symbol, `gitnexus_detect_changes()` before each commit.
2. Full suite green after every task (`cd module_02_extract && python -m pytest -q`, currently 137), **including** `tests/test_dynamic_tracer_parity.py`.
3. One commit per task, conventional style. Do not change existing `/verify` wire-format keys.
4. Report measured numbers as-is. If detection stays weak, document why in the report — do not tune the corpus or threshold logic to manufacture a result.

---

## TASKS (in order)

### E1 — Give the reference interpreter a real execution environment

**Files**: `src/dynamic_tracer/interpreter.py` (constructor lines 22-28, `_exec_stmt` lines 179-184), `src/dynamic_tracer/randomized.py` (`_run_expected`, lines 121-134).

- Add an optional `exec_env: Optional[dict]` parameter to `WIRReferenceInterpreter.__init__`. In `_exec_stmt`, exec with `globals` built from that env (stub functions + the module's `SAFE_BUILTINS` from `src/dynamic_tracer/safe_exec.py:11-17`) and `locals=state`, instead of the current empty-builtins dict. Mutants and bases share identical stub defs by construction (`eval/mutate.py` mutates only the `workflow` function — see its module docstring), so passing the tester's own compiled namespace is sound for both self- and differential-mode.
- In `RandomizedDifferentialTester._run_expected` (`randomized.py:121-124`), construct the interpreter with `exec_env=self._compiled_ns`.
- Stop swallowing everything in `_exec_stmt`: keep the try/except (WIR statements can legitimately fail on some paths), but count failures (e.g. `self.exec_errors += 1`) and surface the count in the trace log or certificate so a fully-broken reference can never again masquerade as a clean one. Same treatment for the guard fallback at `interpreter.py:175-177` if cheap.

**Tests** (`tests/test_dynamic_tracer.py`, near the `WIRReferenceInterpreter` cases at ~lines 258-340): a two-stub workflow WIR where a guard reads a stub-returned value — with `exec_env` provided, assert state populates and the guard-dependent branch is taken; without it, assert the old behavior (documents the difference).

### E2 — Task-event alignment on stub calls (both sides)

**Files**: `src/main.py` (`_run_verification`, the `task_patterns=[function_name]` call site), `src/dynamic_tracer/interpreter.py` (`_step` block/task handling, lines 57-149), `src/dynamic_tracer/randomized.py` (`_run_expected` synthetic wrap, lines 125-134), `eval/calibrate.py` (differential runner, ~lines 181-230), `src/dynamic_tracer/comparator.py` (stutter elimination, lines 39-44 + `_extract_task_names`).

1. **Derive task patterns from the source**: in `_run_verification` (and mirrored in `eval/calibrate.py`'s differential runner), set `task_patterns = [entry_function] + [every other function name defined at module level in the source]` (walk the AST; you already have the parse tree in `_run_verification`). For the FLOW-BENCH corpus these are exactly the stub names; for single-function fixtures (loan_approval) this degenerates to today's behavior. Note the collector matches patterns by substring (`randomized.py:128` uses `pat in name`) — stub names are long and unique, but verify no pattern is a substring of another before relying on it; use exact matching if you touch the matcher.
2. **Actual side**: confirm the collector already emits `task_entry`/`task_exit` when a traced function matching `task_patterns` is entered/exited (read `src/dynamic_tracer/collector.py`, settrace callback ~141-215 and monitoring callbacks ~215-300). If it keys off call/return events of matching functions, expanding `task_patterns` is sufficient — no collector change.
3. **Reference side**: in `WIRReferenceInterpreter._step`, when executing a block/task statement whose RHS calls a name in a known task-pattern set (pass the set into the constructor), emit `{"event": "task_entry", "task": <called name>}` before and `task_exit` after executing the statement — mirroring what the collector records when the actual code calls the stub. Detect the called name with a small `ast.parse(stmt)` check (statements are single assignments; cache parses if it matters). Order inside loops must match the actual side: one entry/exit pair per execution of the statement.
4. Keep the existing synthetic workflow-level wrap (`randomized.py:125-134`) consistent — the workflow function itself is still a task pattern.
5. **Comparator interplay**: `_eliminate_stutter` filters actual events against expected task names (`comparator.py:39-44`); with stubs now in both traces this should align naturally, but re-check the LCS fixtures (`tests/test_dynamic_tracer.py:341-410`) — update fixtures only where they baked in the old single-pattern assumption.

**Acceptance test (the point of the whole session)**, in `tests/test_dynamic_tracer.py` or `tests/test_integration.py`: a base program with three stub calls vs (a) itself → similarity 1.0 / passes; (b) a drop-step mutant (middle stub call deleted) verified **against the base WIR** → missing `task_entry` lowers similarity below the base's own score; (c) a negate-guard mutant whose two branches call different stubs, against base WIR with an input that takes the mutated branch → divergent task sequence detected.

### E3 — Re-run both calibrations with valid function selection

**Files**: `eval/calibrate.py`, `eval/results/`.

1. Archive first: move `eval/results/calibration_report.md` (self-mode — **invalid**: it measured a stub function via the `next(iter(functions))` bug) and `eval/results/calibration_report_differential.md` (pre-alignment baseline) into `eval/results/archive/` with a short `README.md` stating why each is superseded. Do not delete them.
2. Re-run **self-mode** (now measuring `workflow` for the first time): expect logic-mutation detection ≈ 0 by architecture (self-referential oracle) — this is the *valid* measurement of the negative result that `tests/test_integration.py:85-104` documents; say so in the report.
3. Re-run **differential mode** with E1+E2 in place. Regenerate both reports with the same structure (Youden's J on CALIB, frozen τ, EVAL detection/false-alarm with Clopper–Pearson CIs, per-operator table). Re-freeze `eval/threshold.json` from differential CALIB.
4. In the differential report, add a short "vs pre-alignment baseline" table (J, detection, FA before/after) and a per-operator interpretation — specifically whether negate-guard/boundary-shift/constant-perturb still need branch-decision comparison (the deprioritized cause 3) or are now covered via stub-sequence divergence.

### E4 — Wrap-up

- Update the `tests/test_integration.py:85-104` docstring NOTE if the new numbers change its claims.
- Append the results to `.claude/memory/session_2026_07_04_t1_t7_implementation.md` (per-operator table, τ, CIs, before/after comparison).
- `gitnexus_detect_changes()`, push, then update **PR #25's body** (`gh pr edit`) — replace the results section with the new differential table and one paragraph on the task-observability fix; keep the self-referential-oracle finding paragraph.

---

## WHAT NOT TO DO

- Do not add a branch-decision field to the collector this session (cause 3) — measure E2's effect first; if the per-operator table shows value-only mutations still at ~0, write that as the next session's scoped task instead.
- Do not modify `eval/mutate.py`'s invariant that stubs are never mutated — E1's soundness depends on it.
- Do not delete archived reports or rewrite git history; the invalid self-mode report is part of the documented finding trail.
- Do not touch `visit_Attribute`, wall-clock timeouts, typed `/verify` statuses, adaptive n_runs, or `merge_states` — still out of scope.
- Do not let the reference interpreter start *tracing into* stub bodies — it emits synthetic task events around the statement; the stubs' internals are not part of the observable abstraction.

## DEFINITION OF DONE

- Suite green (137 + new tests), parity tests included.
- E2 acceptance test passes: drop-step and branch-divergence mutants are detected against base WIR; base-vs-itself stays clean.
- `eval/results/` has archived old reports + fresh self-mode and differential reports; `threshold.json` re-frozen from differential CALIB.
- PR #25 body updated with honest before/after numbers; session memory updated.
