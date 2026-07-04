# Archived calibration reports

These are kept, not deleted, because they're part of the documented
finding trail — each was superseded by a specific fix, and the numbers
themselves are evidence for what was broken.

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
working detector, not a coin flip.
