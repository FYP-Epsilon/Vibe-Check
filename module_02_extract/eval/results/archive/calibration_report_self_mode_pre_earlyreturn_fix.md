# Module 02 Calibration Report (Self-Mode)

Mode: `self`. Seed: `1234`. CALIB/EVAL split: 50/50 stratified by base-program tag.

## Threshold selection (CALIB)

- Youden's J-optimal tau: **0.1000**
- Youden's J at tau: 0.2997
- CALIB positives (buggy): 209
- CALIB negatives (correct): 50

## Held-out evaluation (EVAL)

- Detection rate (recall on buggy): 0.3727 (95% CI [0.309, 0.440], n=220)
- False-alarm rate (buggy-predicted among correct): 0.0588 (95% CI [0.012, 0.162], n=51)

## Detection rate by mutation operator (EVAL)

| operator | n | detected | detection rate |
|---|---|---|---|
| boundary-shift | 1 | 1 | 1.000 |
| constant-perturb | 10 | 1 | 0.100 |
| corrupt-container-op | 17 | 17 | 1.000 |
| drop-step | 51 | 19 | 0.373 |
| early-return | 51 | 3 | 0.059 |
| negate-guard | 17 | 3 | 0.176 |
| reorder-steps | 50 | 19 | 0.380 |
| swap-branches | 5 | 1 | 0.200 |
| wrong-variable | 18 | 18 | 1.000 |

## Interpretation

This is the first *valid* self-mode run -- the prior self-mode
report (archived at `eval/results/archive/calibration_report_self_mode_pre_functionfix.md`)
measured a trivial stub function due to the function-selection bug
fixed earlier this session, not `workflow`.

Self-mode's oracle is still architecturally self-referential (the
WIR is re-derived from the mutant itself), so a mutation that
changes behavior *without* raising an exception is invisible by
construction: both sides reflect the same mutated structure. The
non-trivial detection rate seen here (0.373) comes almost entirely
from a different, real signal: mutations that make the *actual*
Python code raise an exception (e.g. `corrupt-container-op`'s
KeyError on a renamed dict key, `wrong-variable`'s NameError) are
recorded as an `exception` trace event by the real collector, but
the reference interpreter swallows the equivalent failure silently
(`_exec_stmt`/`_eval_guard` catch and count it, never emit a trace
event) -- so those operators sit at 1.000 while purely-logical
mutations (`early-return`, `negate-guard`) stay low. This is a
genuine, if narrow, self-mode detection channel worth keeping in
mind, not a contradiction of the self-referential-oracle finding.