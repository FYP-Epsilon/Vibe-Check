# SESSION MANDATE — Module 02: wrap up the F1/F2 branch (verification + PR only)

You are finishing the mechanical-fixes arc on VibeCheck (`C:\Research\FYP\Vibe-Check`). All implementation is **done, committed, and pushed** — a prior session collision was resolved and reconciled. This session is verification + PR + bookkeeping. **Write no product code.** If verification fails, STOP and report — do not fix.

**Branch**: `fix/mod2/bookkeeping-and-branch-decision` (pushed). Commits, newest first:
- `191eb2c` chore: GitNexus count sync + memory annotation
- `67c4279` **F2**: collector branch decisions (PEP 669 BRANCH + settrace next-line fallback, `branch_arms` from code-under-test's WIR) — includes regenerated calibration/E3 reports, archives, re-frozen `threshold.json`, and the flipped value-only regression test
- `2753693` **F1**: `contract_bookkeeping_nodes` post-pass in `src/ast_extractor/cfg_extractor.py` — includes regenerated E2 report + archive
- `7c6e21e` docs: E2 human-validation VERDICT.md

## Tasks

1. **Re-index**: `npx gitnexus analyze` (index is stale at `2753693`). If the AGENTS.md/CLAUDE.md symbol counts change, commit the sync as `chore(mod2): sync GitNexus index counts` — nothing else.
2. **Verify** (read-only): `cd module_02_extract && python -m pytest -q` → expect **188 passed**, including `tests/test_dynamic_tracer_parity.py`. Confirm `eval/results/calibration_report_differential.md` shows: genuine-bug detection 0.9571 [0.920, 0.980], J=0.9017, false-alarm 0.0588 unchanged, negate-guard 14/14, per-operator constant-perturb 0/9 with its explanation paragraph. Confirm `eval/results/e2_structural_report.md` shows node and edge P/R/F1 = 1.0000 with the pre-contraction before/after table.
3. **Open the PR** to `develop`: `fix(mod2): contract WIR bookkeeping nodes + collector branch decisions`. Body must contain:
   - **F1 paragraph + table**: E2 node P/R/F1 0.8255/1.0000/0.9044 → 1.0/1.0/1.0; edge F1 0.6827 → 1.0; zero new V3 abort-gate failures across the 101-program corpus; calibration byte-identical under F1 alone. Note for the **M03 owner**: emitted WIRs no longer contain blank merge/exit structural nodes — relevant to their equivalence-clustering input.
   - **F2 paragraph + table**: genuine-bug detection 0.9286 → 0.9571 [0.920, 0.980], J 0.8532 → 0.9017, false-alarm unchanged 0.0588; negate-guard 8/14 → 14/14 via the now-live decision-aware comparison; constant-perturb still 0/9 (confidence moves 0.8 → 0.32, doesn't cross τ — input-generator sharpening is backlog, cited from the report).
   - **Known-open-items paragraph** (verbatim substance, don't soften): (a) *V2 masking in differential mode* — on stub-free scalar workflows self-referential V2 (no oracle) floors `combined` at its own confidence even when V1 detects with certainty; corpus programs avoid this only because container inputs make V2 bail; composition discounting for differential mode is backlog (see the comment in `eval/test_calibrate.py::test_value_only_guard_mutation_now_detected`). (b) constant-perturb input sharpening. (c) A note that the session was reconciled from a two-session collision: implementation by one session, verification/test-reconciliation by another — the commit messages record this.
   - Standard generated-with-Claude-Code footer.
4. **Memory**: append the F1/F2 final numbers and the V2-masking caveat to `.claude/memory/session_2026_07_04_t1_t7_implementation.md` if not already present (check first — part was staged before the collision).

## What NOT to do

- No product-code or test changes. A red test = stop and report.
- Do not re-run or regenerate any eval reports — they are committed artifacts of the verified runs.
- Do not touch the backlog items (V2 composition discount, constant-perturb sharpening, `visit_Attribute`, per-layer statuses, timeouts, `merge_states`, adaptive n_runs, multi-implementation corpus).

## Definition of done

188 tests green; index fresh; PR open with both tables, the M03 note, and the known-open-items paragraph; memory appended.
