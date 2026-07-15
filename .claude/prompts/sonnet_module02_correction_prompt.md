# SESSION MANDATE — Module 02: eval corrections (early-return operator + line-shift sensitivity + corrected headline numbers)

You are running a correction session on VibeCheck (`C:\Research\FYP\Vibe-Check`). The E2/E3 session (PR #26) found that one mutation operator is a no-op and my verification pass derived an implication that must now be tested and fixed. This session makes the thesis numbers final. Work in `module_02_extract/eval/` — **`src/` is frozen** (same rule as last session; genuine bug = separate labeled commit + report note).

**Branch**: continue on PR #26's branch (`feat/mod2/e2-e3-experiments` or whatever `gh pr view 26 --json headRefName` says); push there and update #26's body. Baseline: **171 tests passing**.

## Verified context (re-read cited lines before editing)

1. **`op_early_return` is a no-op** (`eval/mutate.py:148-155`): it inserts `ast.Return(None)` at `len(body) - 1`, but every adapter-generated workflow already ends with `return None`, so the insert lands immediately before an identical statement and cuts nothing. Result: 101/101 early-return mutants are semantically equivalent to their base (E3 report, `eval/results/e3_correlation_report.md:40-57`).
2. **Reconciliation math** (from the verification pass): in the E1 differential calibration (`eval/results/calibration_report_differential.md`), early-return contributed 51 EVAL "positives" of which 22 were "detected". Since those mutants are not actually buggy: detection on genuinely-buggy mutants ≈ (190−22)/(220−51) = 168/169 ≈ **0.994**, while ~43% of the semantically-equivalent (but textually shifted) mutants were flagged — i.e. specificity on equivalent-but-edited code is ~57%, far below the 94% measured on untouched bases.
3. **Line-shift hypothesis (UNVERIFIED — testing it is task C1)**: differential mode derives V1 params, including `branch_lines`, from the **base** WIR (`eval/calibrate.py`, `run_differential_verification` ~line 181, via `_derive_v1_params` imported from `src/main.py:51-80`). `branch_lines` are raw line numbers; an inserted statement shifts every subsequent mutant line by +1, so the collector (which matches `line_no in self.branch_lines`, `src/dynamic_tracer/collector.py:182, 314`) records branch events at wrong/missing positions → spurious trace divergence → false flag. Control/state variables are name-based and line-insensitive; only `branch_lines` should carry this failure mode. **This is an inference. Confirm or refute it empirically before changing anything.**

## Ground rules

- `CLAUDE.md` GitNexus workflow (`npx gitnexus analyze` first; `gitnexus_impact`; `gitnexus_detect_changes()` per commit). Suite green after every task.
- Stdlib only. Report measured numbers as-is; the goal is *correct* numbers, not better-looking ones.
- Archive superseded reports into `eval/results/archive/` with a README line each — never overwrite or delete (this is the third generation of reports; keep the trail consistent with the existing archive).

---

## TASKS

### C1 — Test the line-shift hypothesis (before any fix)

Pick 3 early-return mutants that the calibration flagged (score < τ=0.10) — the cached per-mutant scores from the calibration/E3 runs identify them. For each, run the differential scoring twice, changing exactly one thing:

- **A (status quo)**: `branch_lines` from the base WIR (as today).
- **B**: `branch_lines` re-derived from the *mutant's own* extracted WIR (`run_v3_pipeline(mutant_source)` → same `_derive_v1_params`, take only `branch_lines`; everything else — oracle WIR, control/state variables — unchanged from base).

If B's scores recover to ≈ the base program's own score, the hypothesis is CONFIRMED. If not, diagnose the actual divergence source before proceeding: dump both traces (actual vs expected) for one flagged equivalent mutant and identify which events differ — do not skip this; C2's design depends on the real cause. Write the outcome (confirmed / refuted + actual cause) into the session report either way.

### C2 — Fix the differential harness's textual-shift sensitivity

**File**: `eval/calibrate.py` (`run_differential_verification`). Assuming C1 confirms: derive `branch_lines` from the mutant's own WIR while keeping the **base** WIR as the V1 oracle and base-derived control/state variables (name-based, shift-insensitive). Add a comment explaining why the observation layer (where to watch) may come from the code under test while the oracle (what to expect) must not — watching positions are not spec knowledge, so anti-circularity is preserved. If C1 refuted the hypothesis, fix whatever the actual cause was, same file if possible; `src/` only if unavoidable (separate commit + justification).

**Test**: `eval/test_calibrate.py` (or new file): a base program and a hand-made *semantically equivalent* mutant (e.g. an inserted `x_pad = 0` line that shifts everything down) must score within a small epsilon of the base's own differential score.

### C3 — Fix `op_early_return` and regenerate its mutants

**File**: `eval/mutate.py:148-155`.

- New behavior: insert `return None` at a position that actually cuts logic — a random index in `[1, len(body)-2]` (seeded, deterministic per uid, consistent with how other operators pick sites), never immediately before the trailing return; return `None` (inapplicable) when the body has < 3 statements. Site string should name the statement it now precedes.
- Regenerate **only** the early-return mutants (delete the old `eval/mutants/*__early-return__*.py`, regenerate, update `eval/manifest.json` in place; other operators' mutants untouched — their E3 scores stay valid).
- **Tests** (`eval/test_mutate.py`): the mutant differs behaviorally from base on at least one input for a 3+-statement workflow (reuse E3's recorder machinery from `eval/e3_correlation.py` — call it, don't copy it); inapplicability on a 2-statement body; determinism under fixed seed.
- Sanity gate: after regeneration, compute `semantic_diff_rate` (E3 machinery) for the new early-return mutants and report the equivalent count — expect near 0 now; if many are still equivalent, investigate before running C4 (e.g. bodies where everything after the insert point is dead anyway).

### C4 — Re-run everything downstream and produce the corrected final numbers

1. Archive the current differential calibration report, self-mode report, and E3 report (E2 is unaffected — it uses only base programs — leave it alone).
2. Re-run differential calibration (with C2's fix and C3's mutants) and self-mode calibration; re-run E3 (only early-return rows need rescoring for ground truth, but the certificate side changed for *all* mutants if C2 touched scoring — rescore everything; the cache makes this cheap for unchanged paths only if the cache key includes the scoring-code version, otherwise invalidate it).
3. **The corrected report must present three separated figures, not one aggregate**:
   - Detection rate on **non-equivalent** mutants (label from E3's `semantic_diff_rate > 0` — code-vs-code, still anti-circular), with Clopper–Pearson CI.
   - **Specificity on equivalent mutants** (fraction of `semantic_diff_rate == 0` mutants NOT flagged) as its own figure with CI — this is the honest replacement for burying them in the positive class, and post-C2 it should approach the untouched-base specificity; report the comparison.
   - False-alarm rate on untouched bases (as before).
   Plus the standard per-operator table, before/after-correction comparison against the archived reports, and updated E3 correlation (full + diff_rate>0 subset).
4. Freeze the final `eval/threshold.json` from the corrected differential CALIB.

### C5 — Wrap-up

- Update `eval/results/e3_correlation_report.md`'s early-return finding section → resolved, with a pointer to the corrected numbers.
- Append corrected headline numbers to `.claude/memory/session_2026_07_04_t1_t7_implementation.md` (mark the previous headline as superseded).
- `gitnexus_detect_changes()`, push, update **PR #26's body** with the corrected results and one paragraph each on: the operator bug, the line-shift finding (confirmed/refuted per C1), and the three-figure presentation.

---

## WHAT NOT TO DO

- Do not fix before verifying (C1 gates C2) — if the line-shift hypothesis is wrong, a "fix" for it would silently mask the real cause.
- Do not touch E2 artifacts (gold, reports, manual-check files) — base programs didn't change.
- Do not regenerate non-early-return mutants — that would invalidate cross-report comparability for no reason.
- Do not present a single aggregate detection number in the corrected report — the three-figure split (genuine-bug detection / equivalent-mutant specificity / base false-alarm) is the deliverable.
- Do not touch the still-open src/ backlog (`visit_Attribute`, per-layer statuses, timeouts, `merge_states`, adaptive n_runs, extractor merge-node precision from E2's worst-10).

## DEFINITION OF DONE

- Suite green (171 + new tests).
- C1 outcome documented (confirmed or actual cause found), C2 epsilon-test passing.
- New early-return mutants behaviorally non-equivalent (sanity gate reported).
- Corrected calibration + E3 reports with the three-figure split and before/after tables; old reports archived; `threshold.json` re-frozen.
- PR #26 updated; session memory appended.
