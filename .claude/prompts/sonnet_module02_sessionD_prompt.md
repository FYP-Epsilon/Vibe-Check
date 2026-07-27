# SESSION MANDATE — Module 02, Session D: cross-implementation comparison mode

You are closing the last measured gap in VibeCheck's Module 02 (`C:\Research\FYP\Vibe-Check`): Session C measured an implementation-freedom false-alarm rate of **0.25** (5/20 behaviorally-equivalent, differently-written correct variants flagged) vs 0.0588 on untouched bases, with the divergence-source breakdown showing branch_point events dominating (70/90 pooled divergences) — the comparator punishes different branch *structure* even when observable *behavior* matches. The scoped fix, named in `eval/results/multi_impl_report.md` and deliberately not built then: a **comparison mode that aligns on task events only** for cross-implementation verification. This session builds it, measures it, and — equally important — measures what mutation detection would lose under it, so the mode-selection rule is defended by data.

**Precondition**: PRs #30 and #31 must be merged into `develop` (check `gh pr view 30 --json state`, same for 31). If either is open, STOP and tell the user. **Branch**: `feat/mod2/cross-impl-comparison` off `develop`. Baseline: **221 tests passing**.

## The design (and the principle behind it)

Two different verification questions need two different trace abstractions:

- **Same-lineage comparison** (a mutant of the same source vs its base WIR): branch structure is shared by construction, so branch-decision divergence is *signal* — this is what F2/Session A exploited (negate-guard 8/14 → 14/14; constant-perturb 0/9 → 8/9). Mode: **strict** (current behavior, stays the default).
- **Cross-implementation comparison** (an independently-written program vs a reference WIR): branch structure legitimately differs between correct implementations, so branch events are *noise*; only the observable task behavior (which stubs run, in what order, plus exceptions) is comparable. Mode: **task_only**.

The mode-selection rule to document everywhere: *strict when the two sides share source lineage; task_only when they are independent implementations.* This is not a knob to tune per-result — it is decided by what the comparison can assume shared, before looking at any number.

## Verified anchors (re-read before editing)

- `src/dynamic_tracer/comparator.py::_normalise` — emits `("task_entry", name)`, `("task_exit", name)`, `("branch_point", taken?)`, `("exception", type)` tuples; the LCS runs over these.
- `DifferentialComparator` is instantiated inside `RandomizedDifferentialTester.run()` (`src/dynamic_tracer/randomized.py`); parameters thread from `run_v1_pipeline` (`src/dynamic_tracer/pipeline.py`) and `eval/calibrate.py::run_differential_verification`.
- Session C's experiment runners and corpus: `eval/variants/` (manifest, 20 admitted, 164 rejected-behavioral), the C5b/C5c code (locate it — it landed with Session C in `eval/`, likely alongside `gen_variants.py`).
- Numbers that must not move: strict-mode genuine-bug detection **0.9952**, FA **0.0588**, τ=0.10 (`eval/threshold.json`).

## Ground rules

- GitNexus workflow per `CLAUDE.md`; suite green after every task incl. parity tests; stdlib only; archive superseded reports with README lines.
- Report numbers as-is. The D3 control experiment below is *expected* to show task_only losing mutation-detection power — that expected loss is the justification for having two modes, so measure it cleanly rather than avoiding it.

---

## D1 — The mode itself

Add `comparison_mode: str = "strict"` (values `"strict" | "task_only"`) threaded `run_differential_verification` → `run_v1_pipeline` → `RandomizedDifferentialTester` → `DifferentialComparator`. In `task_only` mode, `_normalise` keeps task and exception tuples and **drops branch_point tuples entirely** (do not keep them decision-less — a count mismatch is exactly the style noise being excluded). Default `"strict"` everywhere; the `/verify` self-mode path is untouched.

**Tests**: unit tests for `_normalise` in both modes; a pair of hand-built traces identical in task events but different in branch structure → similarity 1.0 in task_only, < 1.0 in strict; **strict-mode regression**: the existing comparator tests all pass unmodified.

## D2 — Re-run the Session C experiments in task_only mode

- **C5b re-run (the payoff)**: the 20 admitted variants vs their base WIRs, task_only. Pre-registered expectation (write before running): the 3 clear style-punishment false alarms recover; the 2 exception/marginal ones may not (exceptions still compare — correctly). Report FA with CI, per-variant table (same format as the corrected C5b table), and before/after vs the 0.25.
- **C5c re-run (the guard)**: the 164 natural-bug variants, task_only. Logic-class detection was 0.9118 in strict mode — measure what task_only gives; logic bugs that diverge only in branch decisions but not in stub sequence will be missed here. If logic detection drops materially, say so plainly — it sharpens the mode-selection tradeoff rather than undermining it (cross-impl mode trades some bug sensitivity for style tolerance; quantifying that trade is the contribution).
- While in there: **diagnose the 6 strict-mode logic misses** (68−62) from Session C using the admission records' first-divergent-input evidence — specifically whether any diverge *only in return value* (which V1 traces don't compare at all). Diagnosis only, one line each; if return-value-only divergence shows up, name "return-value observable in V1 traces" as a scoped backlog item. Do not implement it.

## D3 — The control: mutation calibration under task_only (justifies the rule)

Run the full differential mutation calibration once in task_only mode (nothing re-frozen — this is a control experiment, clearly labeled). Expectation: negate-guard and constant-perturb collapse back toward their pre-F2/pre-A2 levels since their detection rides on branch decisions. Present strict-vs-task_only side by side in the report — this table is the data-driven answer to "why not always use the forgiving mode?", which is the first question an examiner will ask about D1.

## D4 — Report + wrap-up

- `eval/results/cross_impl_mode_report.md`: the mode-selection rule and its rationale; D2's before/after C5b table + C5c task_only numbers + the 6-miss diagnosis; D3's control table; caveats (n=20 small; single-sample-per-model, carried from Session C).
- Update `docs/module02/11_multi_impl_corpus_contract.md` with one paragraph: which comparison mode M03-adjacent consumers should use for cross-implementation equivalence checking, and why.
- Strict-mode regression proof in the report: re-run the standard differential calibration in strict mode and show the numbers are byte-identical to Session A's (0.9952 / 0.0588 / J=0.9600).
- Suite green (221 + new tests); `gitnexus_detect_changes()`; PR to `develop`: `feat(mod2): cross-implementation comparison mode (task-event alignment)` — body: the rule, the C5b before/after, the D3 control table, the strict-mode regression proof. Append numbers to the session memory file.

## WHAT NOT TO DO

- Do not change the default mode anywhere, and do not let task_only leak into the mutation-calibration path or `/verify` — the D3 control run is explicitly labeled and not persisted as anyone's operating point.
- Do not re-freeze `threshold.json` — no operating threshold changes this session.
- Do not implement return-value observables (diagnosis only), per-guard-site literal coverage, or any Session B item (per-layer statuses, wall-clock timeout, merge_states, adaptive n_runs) — those are the next and final engineering session.
- Do not regenerate variants or touch the admission verdicts — the Session C corpus and manifest are frozen inputs here.

## DEFINITION OF DONE

- `comparison_mode` implemented, default-strict, unit-tested both ways; parity + full suite green.
- C5b task_only re-run with before/after (expected: FA well below 0.25); C5c task_only measured; 6-miss diagnosis written.
- D3 control table (strict vs task_only on mutation calibration) in the report.
- Strict-mode regression proof: Session A numbers reproduced exactly.
- Contract doc updated; PR open; memory appended.
