# Module 02 Calibration Report (Differential-Mode)

Mode: `differential`. Seed: `1234`. CALIB/EVAL split: 50/50 stratified by base-program tag.

## Threshold selection (CALIB)

- Youden's J-optimal tau: **0.1000**
- Youden's J at tau: 0.8069
- CALIB positives (buggy): 209
- CALIB negatives (correct): 50

## Held-out evaluation (EVAL)

- Detection rate (recall on buggy): 0.8636 (95% CI [0.811, 0.906], n=220)
- False-alarm rate (buggy-predicted among correct): 0.0588 (95% CI [0.012, 0.162], n=51)

## Detection rate by mutation operator (EVAL)

| operator | n | detected | detection rate |
|---|---|---|---|
| boundary-shift | 1 | 1 | 1.000 |
| constant-perturb | 10 | 10 | 1.000 |
| corrupt-container-op | 17 | 17 | 1.000 |
| drop-step | 51 | 51 | 1.000 |
| early-return | 51 | 22 | 0.431 |
| negate-guard | 17 | 17 | 1.000 |
| reorder-steps | 50 | 49 | 0.980 |
| swap-branches | 5 | 5 | 1.000 |
| wrong-variable | 18 | 18 | 1.000 |

## vs pre-alignment baseline

| metric | pre-alignment (archived) | post E1+E2 (this run) |
|---|---|---|
| Youden's J | 0.0506 | 0.8069 |
| Detection rate (EVAL) | 0.4318 | 0.8636 |
| False-alarm rate (EVAL) | 0.3922 | 0.0588 |

Pre-alignment archived at `eval/results/archive/calibration_report_differential_pre_e1e2.md`.

## Interpretation

E1 (real exec_env for the reference interpreter) and E2 (task-event
alignment for stub calls) together turned this from a near-coin-flip
signal into a working detector: detection and false-alarm rates are
now well-separated (95% CIs do not overlap), and the base program's
own differential check is no longer failing by construction (E1's
root cause -- uid_4 scoring 0.0 against its own WIR -- is fixed).

Per-operator, `negate-guard`/`boundary-shift`/`constant-perturb`
(the "value-only" class D3 predicted would need branch-decision
comparison) are now detected at or near 1.000 -- in the real
FLOW-BENCH corpus, unlike a minimal hand-crafted guard, the two
branches of a mutated guard typically call *different* stubs, so
E2's task-sequence divergence catches them without needing
collector.py's still-missing decision field. That deferred fix
(cause 3 in the session mandate) is not yet warranted by this data.

`early-return` sits lower (0.431) than the rest -- an early return
only removes trailing steps, so it's only detectable when the
random input happens to reach a branch whose subsequent stub calls
get cut off; many random runs don't reach that point at all. This
is a real, measured floor for this operator, not a bug.
`boundary-shift` and `swap-branches` have very small n (1 and 5
respectively -- FLOW-BENCH has few applicable sites for them) so
their 1.000/CI should be read as "consistent with detection", not
as a precise rate estimate.