# Module 02 Calibration Report (Differential-Mode)

Mode: `differential`. Seed: `1234`. CALIB/EVAL split: 50/50 stratified by base-program tag.

## Threshold selection (CALIB)

- Youden's J-optimal tau: **0.1000**
- Youden's J at tau: 0.0506
- CALIB positives (buggy): 209
- CALIB negatives (correct): 50

## Held-out evaluation (EVAL)

- Detection rate (recall on buggy): 0.4318 (95% CI [0.365, 0.500], n=220)
- False-alarm rate (buggy-predicted among correct): 0.3922 (95% CI [0.258, 0.539], n=51)

## Detection rate by mutation operator (EVAL)

| operator | n | detected | detection rate |
|---|---|---|---|
| boundary-shift | 1 | 1 | 1.000 |
| constant-perturb | 10 | 1 | 0.100 |
| corrupt-container-op | 17 | 17 | 1.000 |
| drop-step | 51 | 22 | 0.431 |
| early-return | 51 | 7 | 0.137 |
| negate-guard | 17 | 6 | 0.353 |
| reorder-steps | 50 | 21 | 0.420 |
| swap-branches | 5 | 2 | 0.400 |
| wrong-variable | 18 | 18 | 1.000 |

## Known limitations (why detection is weak, not tuned away)

Detection rate (0.43) and false-alarm rate (0.39) are close to each
other -- this is a near-coin-flip signal, not a working detector.
Two independent, verified causes, neither fixed in this session:

1. **The reference interpreter cannot execute task-API calls.**
   `WIRReferenceInterpreter._exec_stmt` runs `exec(stmt, {"__builtins__": {}}, state)` -- no access to the
   compiled stub defs, so any assignment that calls a user-defined
   function (e.g. `incident = ServiceNow_..._incident()`) silently
   fails and never populates `state`. Every guard reading that
   variable then falls to its permissive-False default, and any
   for-loop over its result gets an empty iterable. This holds for
   BOTH self-mode and differential-mode WIRs -- switching the
   oracle to the base program's WIR (this session's fix) does not
   help, because the base program's own reference execution is
   equally broken. Confirmed directly: base program uid_4 scores
   combined_confidence 0.0 under differential mode -- the
   *correct* program fails its own differential check, so there is
   no working baseline to separate mutants from.
2. **Value-only mutations (negate-guard, boundary-shift,
   constant-perturb) produce identical trace *shape*.** D3 made
   branch-decision comparison possible when both sides carry
   `taken_branch`, but the real actual-side collector never does
   (collector.py has no decision field on branch_point events),
   so this stays a no-op for real runs by design (see D3's commit).
   Verified directly on a hand-crafted base/mutant pair with zero
   function calls involved: identical combined_confidence on both.

Per-operator numbers above should be read as noise from cause (1),
not as evidence those operators are individually easier/harder to
detect. Fixing cause (1) (giving the interpreter a real compiled
namespace) is the next session's highest-priority item -- see
session memory for the full layered diagnosis.