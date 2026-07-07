# E3: Certificate Score vs Code-vs-Code Correctness

## Methods

Ground truth (`semantic_diff_rate`): base and mutant `workflow` are
each executed directly on the SAME 25 seeded random inputs
(type-hint-driven generation reimplemented locally in this module,
not imported from `RandomizedDifferentialTester`; string params
sampled from a guard-literal pool extracted from the source, as
elsewhere in this eval suite). Each run's observable behavior is
the sequence of stub calls (every non-entry top-level function is
wrapped to log its name before delegating -- stubs are
deterministic echoes by construction, eval/mutate.py never mutates
them) plus the return value. `semantic_diff_rate` is the fraction
of the N inputs where these differ. **The WIR never appears on
this side of the experiment** -- it is the thing being evaluated.

Certificate score: `combined_confidence` from
`eval/calibrate.py`'s `run_differential_verification` (mutant
verified against its base program's WIR) -- the same detector
measured in the E1 calibration run.

Caveat: N=25 bounds the equivalent-mutant count from
above -- a mutant that differs only on inputs not sampled in
these 25 looks equivalent here but may not be with a
larger sample. Read the equivalent count as "at least this many
are indistinguishable at this sample size," not an exact count.

## Correlation: 1 - combined_confidence vs semantic_diff_rate

- n = 427 mutants scored (execution failed: 0)
- Pearson r = 0.3653, 95% CI [0.2801, 0.4448]
- Spearman rho = 0.5212

### Restricted to semantic_diff_rate > 0 (n=416)

- Pearson r = 0.5326, 95% CI [0.4600, 0.5981]
- Spearman rho = 0.5784

## Equivalent mutants (semantic_diff_rate == 0 at N=25): 11 / 427

| operator | equivalent | total |
|---|---|---|
| boundary-shift | 1 | 1 |
| constant-perturb | 1 | 21 |
| corrupt-container-op | 1 | 30 |
| drop-step | 0 | 101 |
| early-return | 1 | 99 |
| negate-guard | 5 | 32 |
| reorder-steps | 1 | 99 |
| swap-branches | 1 | 8 |
| wrong-variable | 0 | 36 |

## RESOLVED: early-return no longer a mutate.py implementation bug

An earlier run of this report found `early-return` at 99/99 equivalent mutants -- `op_early_return` inserted its return immediately before the function's existing trailing `return None`, cutting nothing. Fixed (see `eval/mutate.py`'s current `op_early_return` and its commit message): the operator now inserts at a seeded-random index that always precedes a real statement. Current run: 1/99 equivalent -- consistent with the other operators' background rate, not a systematic bug anymore. Corrected calibration numbers (genuine-bug detection / equivalent-mutant specificity / false-alarm three-figure split) are in `eval/results/calibration_report_differential.md`; the pre-correction numbers are archived in `eval/results/archive/`.
