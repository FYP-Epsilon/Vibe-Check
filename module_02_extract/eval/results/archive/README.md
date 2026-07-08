# Archived calibration reports

These are kept, not deleted, because they're part of the documented
finding trail — each was superseded by a specific fix, and the numbers
themselves are evidence for what was broken.

## `e3_pairs_pre_b1_return_value.csv`, `e3_correlation_report_pre_b1_return_value.md`

Session B (B1, return-value observable). Not superseded — kept as
evidence that B1 was checked against the mutation corpus, not assumed
neutral. B1 added `return_value` comparison to the differential
comparator in BOTH modes (see `src/dynamic_tracer/comparator.py`), so
E3 was re-run in full (all 427 mutant/base pairs recomputed, not
resumed from the pre-B1 CSV) to check whether it moved. It didn't:
`eval/results/e3_pairs.csv` and `e3_correlation_report.md` are
byte-identical to these archived pre-B1 copies (Pearson r = 0.4085 /
0.5580 restricted, Spearman rho = 0.5400 / 0.5988 restricted, 11/427
equivalent). Diagnosed, not just observed: this corpus's mutation
operators (negate-guard, drop-step, reorder-steps, wrong-variable,
etc.) directly perturb control flow, so in strict mode a mutation
almost always already diverges on task-sequence or branch-decision
before return value would ever be the deciding channel -- for a
genuine miss, return_value has nothing left to add; for an equivalent
mutant, the return value agrees too, same as everything else. This is
the complement of B1's actual target: the natural-bug corpus's 6
previously-missed cases (`eval/results/cross_impl_mode_report.md`) are
specifically return-value-ONLY divergences between independently
written implementations that share identical branch structure and
task sequence -- a class of divergence that essentially does not occur
from directly mutating one program's own control-flow structure. See
`eval/results/session_b_report.md`'s B1 section for the full
instrument-gate numbers (natural-bug corpus, C5c both modes, full
strict calibration) where B1's effect is real and large.

## `calibration_report_differential_pre_a1a2.md`, `e3_pairs_pre_a1a2.csv`, `e3_correlation_report_pre_a1a2.md`

Session A (A1 + A2), before both fixes. Two backlog items from the
mechanical-fixes session:

1. **A1 — V2 masked V1 in differential mode.** `run_differential_verification`
   composed the final score with the standard OR-composition
   `1-(1-v1)(1-v2)`. In differential mode V1 has a real oracle (the base
   WIR) but V2 does not — it symbolically explores the *mutant's own*
   code with no actual/expected comparator, so its confidence isn't
   "no bug found" evidence. On a stub-free scalar workflow this floored
   `combined_confidence` at v2's self-referential 0.5 even when v1
   detected with certainty (see
   `eval/test_calibrate.py::test_value_only_guard_mutation_now_detected`).
   Fixed by making `combined_confidence = v1_confidence` in differential
   mode only (self-mode `/verify` composition is untouched); `v2_confidence`
   stays in the certificate as telemetry.
2. **A2 — constant-perturb undetected for a sampling reason.**
   `RandomizedDifferentialTester`'s string pool came only from the
   *mutant's own* source, so a constant-perturb mutant's pool held just
   the mutated literal — random sampling often drew neither the original
   nor mutated value in a 10-run budget, so the branch decision agreed
   vacuously on both sides. Fixed by (a) seeding the pool with the BASE
   program's own guard literals too (`extract_guard_string_literals`,
   threaded via `extra_str_literals`), and (b) round-robin-first sampling
   that guarantees every distinct pool literal is drawn at least once
   before random sampling resumes.

Post-fix: Youden's J 0.9017 → 0.9600, genuine-bug detection 0.9571 →
0.9952, `constant-perturb` detection 0/9 → 8/9 (the 1 remaining straggler
has a guard value fed by two independent `str` parameters sharing one
round-robin queue — diagnosed in `calibration_report_differential.md`,
not a numeric-literal case as anticipated going in). False-alarm rate is
**unchanged** at 0.0588 — checked directly (clean pre-session worktree vs.
this branch): `v2_confidence` is 0.0 for every base program in this
container-heavy FLOW-BENCH corpus, so V2 contributed no OR-composition
padding to the negative class before A1 and removing it had nothing to
take away. E3's Pearson r/Spearman rho *recovered* (0.3653/0.5212 →
0.4085/0.5400 full corpus) rather than dropping further, since A1 removes
a saturating term and A2 restores graded signal for `constant-perturb`
specifically. See `eval/results/calibration_report_differential.md`'s
"Composition change (A1)" and "vs pre-A1/A2 baseline" sections, and
`eval/results/e3_correlation_report.md`'s "recovered after Session A"
section, for the full detail.

## `calibration_report_differential_pre_branch_decision.md`, `e3_pairs_pre_branch_decision.csv`, `e3_correlation_report_pre_branch_decision.md`

Differential calibration and E3 correlation runs from before F2
(mechanical-fixes session, collector branch-decision half). Before F2,
`src/dynamic_tracer/collector.py`'s actual-side trace never carried a
`taken_branch` field on `branch_point` events (only the WIR reference
interpreter did), so the comparator's `_both_sides_have_taken` gate
always failed and D3's decision-aware comparison was permanently a
no-op — a mutation could only be caught via task-sequence divergence,
never via a flipped branch decision alone. Fixed by wiring
`sys.monitoring.events.BRANCH` on the native backend (falling back to
next-line inference against `branch_arms` -- per-branch-line
(true_line, false_line) derived from the code-under-test's own WIR,
same anti-circularity split as C2's `branch_lines`) on `sys.settrace`;
both backends converge on the same next-line fallback for whatever
BRANCH left ambiguous (compound conditions, a for-loop's
continue-iterating case landing back on its own line), verified by
`tests/test_dynamic_tracer_parity.py`.

Post-fix: Youden's J 0.8532 → 0.9017, genuine-bug detection 0.9286 →
0.9571, `negate-guard` detection 8/14 → 14/14 (every one of these
mutants flips the branch decision on nearly every run, exactly the
class D3 could never see before). `constant-perturb` stayed 0/9 in
this EVAL split despite `combined_confidence` measurably dropping
(0.8 ceiling → 0.32 floor for affected mutants) — it just doesn't
cross tau=0.1 (see `calibration_report_differential.md`'s per-operator
note for the full explanation). False-alarm rate (0.0588) and
equivalent-mutant specificity (0.1111, n=9, same 5 base uids) are
unchanged, as required — F2 only touches the actual-side collector,
never the oracle or the E3 ground truth (E3's equivalent-mutant table
is byte-identical pre/post, 11/427, confirming the ground truth side
was untouched). E3's Pearson r (0.4359 → 0.3653 full corpus) and
Spearman rho (0.6774 → 0.5212) *dropped* — investigated in
`e3_correlation_report.md`: this is score saturation (many mutants'
`combined_confidence` collapsing to a shared floor/ceiling regardless
of `semantic_diff_rate` magnitude), a side effect of the detector
becoming a sharper pass/fail signal, not a sign the certificate got
worse at its actual job (the three-figure calibration numbers above
are the ones that matter for that).

## `e2_structural_report_pre_bookkeeping_contraction.md`, `e2_per_program_pre_bookkeeping_contraction.csv`

E2 run before the F1 fix (mechanical-fixes session). Node P/R/F1 =
0.8255/1.0000/0.9044, edge P/R/F1 = 0.6204/0.7589/0.6827. Human-validated
(`eval/results/e2_manual_check/VERDICT.md`, 10/10 sampled programs): every
precision-gap node was a blank merge/exit bookkeeping node the extractor's
`visit_If`/loop visitors/`visit_Try`/`visit_TryStar`/`visit_Match` create to
join branches or mark loop/exception exits — zero genuine extraction errors.
Fixed by `contract_bookkeeping_nodes` (`src/ast_extractor/cfg_extractor.py`),
a post-construction graph-contraction pass (the visitors themselves are
untouched — those nodes are load-bearing during construction, e.g.
`visit_Try`'s finally-clause rerouting). Post-fix: node and edge P/R/F1 all
**1.0000** across all 101 corpus programs, with zero new V3 abort-gate
failures and the differential calibration numbers unchanged (task events
don't ride on blank nodes). See `eval/results/e2_structural_report.md`'s
"vs pre-contraction baseline" table.

## `calibration_report_self_mode_pre_functionfix.md`

Self-mode run from the T7 session. **Invalid**: `_run_verification`
selected `function_name = next(iter(functions))` — whichever function the
source defines *first*. Every `eval/flowbench_adapter.py`-generated
program defines its task-API stub(s) before `workflow`, so this measured
a trivial stub (zero branches), never the actual orchestration logic, for
all 101 corpus programs and 429 mutants. Fixed by `_select_entry_function`
(commit `be47afe`).

## `calibration_report_differential_pre_e1e2.md`

Differential-mode run from the D1-D5 session, with the function-selection
bug already fixed but before E1/E2. Youden's J = 0.0506 (near-zero),
detection 0.432 vs false-alarm 0.392 (a near-coin-flip signal). Diagnosed
two causes:

1. `WIRReferenceInterpreter._exec_stmt` couldn't execute any statement
   that calls a user-defined function (stub calls silently NameError'd
   and never populated `state`) — fixed by E1 (commit `2fc1af7`).
2. Stub-call assignments are WIR *block* statements, not "task"-type
   nodes, so neither trace side emitted a task_entry/task_exit event for
   them even once E1 made them executable — fixed by E2 (commit `b28d245`).

See `eval/results/calibration_report.md` (self-mode) and
`eval/results/calibration_report_differential.md` (siblings of this
directory, not inside it) for the current, valid measurements, and
`.claude/memory/session_2026_07_04_t1_t7_implementation.md` for the full
diagnosis and before/after numbers. Post-alignment (E1+E2) differential
result: Youden's J = 0.807, detection 0.864 vs false-alarm 0.059 -- a
working detector, not a coin flip. **This aggregate 0.864 figure was
itself superseded by the correction session below** (it conflated
genuinely-buggy and behaviorally-equivalent mutants into one class).

## `calibration_report_differential_pre_lineshift_fix.md`, `calibration_report_self_mode_pre_earlyreturn_fix.md`, `e3_correlation_report_pre_earlyreturn_fix.md`, `e3_pairs_pre_earlyreturn_fix.csv`

Correction session (C1-C5). Two bugs found while investigating the E3
session's "early-return is 101/101 equivalent" finding:

1. **Line-shift false positives** (C1, confirmed empirically before
   fixing anything): `run_differential_verification` derived
   `branch_lines` from the *base* program's WIR. Any single-statement
   insertion/deletion mutation shifts every subsequent line in the
   mutant relative to the base, so the collector watched the wrong
   lines, producing spurious divergence unrelated to any real behavior
   change. A/B test on 3 real early-return mutants: 2 of 3 were false
   flags that recovered to exactly their base's own score once
   `branch_lines` came from the mutant's own WIR instead. Fixed (C2).
2. **`op_early_return` was a no-op** (found in the E2/E3 session, fixed
   here as C3): it inserted its return immediately before the
   function's existing trailing `return None`, cutting nothing.

Corrected differential report presents three figures instead of one
aggregate: genuine-bug detection (0.929, was 0.864 conflated),
equivalent-mutant specificity, and false-alarm rate on untouched bases
(unchanged, 0.059) -- see `eval/results/calibration_report_differential.md`
for the full breakdown and the investigation of why figure 2's small
sample (n=9) looks noisy (it isn't a new bug -- checked directly).
