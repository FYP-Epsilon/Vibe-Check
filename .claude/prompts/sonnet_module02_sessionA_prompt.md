# SESSION MANDATE — Module 02, Session A: differential-mode composition discount + constant-perturb sharpening

You are running the first of three planned post-merge sessions on VibeCheck (`C:\Research\FYP\Vibe-Check`). PR #28 is merged; `develop` carries the full F1/F2 state. This session fixes the two instrument-facing backlog items so the upcoming multi-implementation corpus (Session C) is measured by a sound instrument. Both fixes are small; the work is mostly in re-running the instruments and reporting honestly.

**Branch**: `fix/mod2/differential-compose-and-perturb` off `develop`. Baseline: **188 tests passing**.

## Verified context (re-read cited lines before editing)

**A1 — V2 masks V1 in differential mode.** `eval/calibrate.py::run_differential_verification` composes the final score with the standard composer: `combined = 1-(1-v1)(1-v2)`. In differential mode V1 has a real oracle (the base WIR) but **V2 does not** — it symbolically explores the mutant's own code, so its confidence is not "no bug found" evidence. Measured consequence (see the comment in `eval/test_calibrate.py::test_value_only_guard_mutation_now_detected` and `.claude/memory/round3_verified_findings_2026_07_04.md` Round-3h): on a stub-free scalar workflow a negate-guard mutant scores **v1=0.0 (perfect detection) but combined=0.5** because self-referential v2=0.5 floors the OR-composition — unflagged at τ=0.10. The corpus currently dodges this only because container inputs make V2 bail (v2≈0 → combined=v1). The multi-impl variants of Session C will include stub-free/scalar styles, so this must be fixed first.

**A2 — constant-perturb undetected for a sampling reason.** Per-operator table (`eval/results/calibration_report_differential.md`): constant-perturb 0/9 despite F2 moving its confidence 0.8 → 0.32. The report's own diagnosis: the branch decision diverges only on the fraction of the n_runs=10 inputs that happen to draw the mutated literal from the string pool — the pool is built from the **mutant's** source (D1, `src/dynamic_tracer/randomized.py`), sampled uniformly with ""/junk, so many runs exercise neither literal and both sides agree vacuously.

## Ground rules

- `CLAUDE.md` GitNexus workflow: `npx gitnexus analyze` first, `gitnexus_impact` before modifying any symbol, `gitnexus_detect_changes()` per commit.
- Suite green after every task, incl. `tests/test_dynamic_tracer_parity.py`. `/verify` wire-format keys unchanged.
- **Report measured numbers as-is — this session has a real chance of moving a number in the "wrong" direction (see A1 acceptance), and if it does, that is a finding to explain, not to tune away.**
- Archive superseded reports to `eval/results/archive/` with README lines (4th generation — keep the trail's style).

---

## A1 — Differential-mode composition: V1 is the verdict, V2 is telemetry

**File**: `eval/calibrate.py::run_differential_verification` (self-mode `/verify` and `src/dynamic_tracer/composer.py` are NOT touched — the standard composer remains correct for self-mode where all layers share the self-referential frame).

- In differential mode set `combined_confidence = v1_confidence`. Keep `v2_confidence` in the returned cert (telemetry, labeled as such in a comment: V2 has no oracle in differential mode; its confidence must not count as absence-of-bug evidence).
- Keep the V3 abort gate exactly as is (extraction fidelity still gates everything).
- Update `eval/test_calibrate.py`: the flipped F2 regression test's "deliberately NOT asserting combined < tau" comment block is now resolved — strengthen it to assert `combined_confidence < 0.10` for the negate-guard mutant and update the comment to say A1 resolved the masking (keep the history in the docstring). Check every other test in that file for combined-value assumptions.

**Acceptance & the honest-risk clause**: re-run the full differential calibration (τ re-selected on CALIB as always; re-freeze `threshold.json`). Two things WILL move:
1. Buggy-mutant scores drop (good — no more V2 padding).
2. **Correct-base scores also drop** — a base's combined was `1-(1-v1)(1-v2)`; now it is bare v1. If V1's confidence on correct programs is weak anywhere (recall the round-3 findings: `coverage_score` degrades for degenerate input spaces), the false-alarm rate may RISE above 0.0588. If it does: identify each newly-flagged base, diagnose *why* its V1 confidence is low (one line each in the report), and present the FA change as the cost of removing a statistically indefensible padding term — do not reintroduce V2 to buy the number back. If FA rises above ~0.15, stop and report before proceeding to A2 — that would mean V1's confidence model needs work that is out of this session's scope.

## A2 — Exercise the mutated literal deterministically

**Files**: `src/dynamic_tracer/randomized.py` (D1 pool logic, `__init__`/`_generate_random_inputs`), `eval/calibrate.py` (pass-through).

1. Add an optional `extra_str_literals: Optional[list[str]]` parameter to `RandomizedDifferentialTester` (threaded through `run_v1_pipeline`, `src/dynamic_tracer/pipeline.py`), unioned into the D1 string pool. In `run_differential_verification`, pass the **base** source's guard-compared literals (extract with the same `ast.Compare` walk D1 uses). Rationale to document in a comment: test *inputs* may come from anywhere, including the spec side — inputs are not the oracle; only the expected trace is (no anti-circularity issue; this is ordinary spec-based test-input selection).
2. Change pool sampling from uniform-random to **round-robin-first**: each distinct pool literal is drawn at least once across the run budget before random sampling resumes (deterministic under the existing seed). This guarantees the mutated and original literals are each exercised at least once whenever `n_runs >= len(pool)`.
3. Self-mode `/verify` path: default behavior unchanged (no extra literals passed); the round-robin change applies everywhere — check the D1 tests (`tests/test_dynamic_tracer.py::test_string_pool_varies_str_param_across_runs` and neighbors) and update only if they baked in uniform sampling.

**Tests**: new unit test — a workflow with guard `== "high"` scored as a mutant with pool `{"high_MUTATED"}` + extra literals `{"high"}`, n_runs=10: assert both literals appear in the generated inputs. Plus a `run_differential_verification`-level test: a hand-made constant-perturb mutant (base `== 'high'` → mutant `== 'high_X'`) must now score `combined < 0.10` against the base WIR.

**Acceptance**: in the re-run per-operator table, constant-perturb must move off 0/9. Report the actual number; if any of the 9 stay undetected, diagnose which and why (e.g. numeric literals — the pool is strings; if that's the cause, say so and leave numeric perturbation sharpening as a named backlog item rather than expanding scope).

## Re-run & report (after both fixes)

- One combined re-run: differential calibration + E3 certificate-side rescore (invalidate the score cache — the compose rule changed for every mutant). Self-mode is untouched by A1/A2 defaults; re-run it only if the round-robin change shifts its numbers (check one program first).
- New differential report: three-figure structure, per-operator table, **before/after vs the pre-A1A2 archived report**, a section explaining the composition change (V1-as-verdict rationale), and the honest FA paragraph if it moved. Update the E3 report if r shifts.
- `.claude/memory/session_2026_07_04_t1_t7_implementation.md`: append Session A numbers.
- PR to `develop`: `fix(mod2): differential verdict = V1 only + deterministic literal coverage` — body with before/after tables and, if FA moved, the per-base diagnosis. Standard footer.

## WHAT NOT TO DO

- Do not touch `src/dynamic_tracer/composer.py` or the `/verify` self-mode composition — A1 is differential-harness-only.
- Do not reintroduce any V2 term into the differential verdict to repair a worsened FA — that is the explicitly rejected move.
- Do not regenerate mutants or touch E2 artifacts/gold.
- Out of scope: Session B items (per-layer statuses, wall-clock timeout, merge_states, adaptive n_runs), Session C (multi-impl, NIM), `visit_Attribute`, numeric-literal perturbation sharpening (name it in the report if hit).

## DEFINITION OF DONE

- Suite green (188 + new tests), parity included.
- Strengthened F2 regression test asserts `combined < 0.10` (masking resolved).
- constant-perturb off 0/9 with per-mutant diagnosis for any stragglers.
- New calibration + E3 reports with before/after tables; FA honestly handled (diagnosed if risen; hard stop >0.15); `threshold.json` re-frozen; archives updated.
- PR open; memory appended.
