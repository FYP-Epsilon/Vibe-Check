# Module 02 Calibration Report

Seed: `1234`. CALIB/EVAL split: 50/50 stratified by base-program tag.

## Threshold selection (CALIB)

- Youden's J-optimal tau: **0.0000**
- Youden's J at tau: 0.0000
- CALIB positives (buggy): 209
- CALIB negatives (correct): 50

## Held-out evaluation (EVAL)

- Detection rate (recall on buggy): 0.0000 (95% CI [0.000, 0.017], n=220)
- False-alarm rate (buggy-predicted among correct): 0.0000 (95% CI [0.000, 0.070], n=51)

## Detection rate by mutation operator (EVAL)

| operator | n | detected | detection rate |
|---|---|---|---|
| boundary-shift | 1 | 0 | 0.000 |
| constant-perturb | 10 | 0 | 0.000 |
| corrupt-container-op | 17 | 0 | 0.000 |
| drop-step | 51 | 0 | 0.000 |
| early-return | 51 | 0 | 0.000 |
| negate-guard | 17 | 0 | 0.000 |
| reorder-steps | 50 | 0 | 0.000 |
| swap-branches | 5 | 0 | 0.000 |
| wrong-variable | 18 | 0 | 0.000 |
