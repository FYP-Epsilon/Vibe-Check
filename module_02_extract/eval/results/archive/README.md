# Archived calibration reports

These are kept, not deleted, because they're part of the documented
finding trail — each was superseded by a specific fix, and the numbers
themselves are evidence for what was broken.

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
