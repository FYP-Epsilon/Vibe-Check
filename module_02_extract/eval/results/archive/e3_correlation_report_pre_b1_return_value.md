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
- Pearson r = 0.4085, 95% CI [0.3262, 0.4846]
- Spearman rho = 0.5400

### Restricted to semantic_diff_rate > 0 (n=416)

- Pearson r = 0.5580, 95% CI [0.4880, 0.6208]
- Spearman rho = 0.5988

### r and rho dropped after F2 (mechanical-fixes session) -- investigated, not a regression

Pre-F2 (archived `archive/e3_correlation_report_pre_branch_decision.md`): Pearson r = 0.4359 (0.6493 restricted), Spearman rho = 0.6774 (0.7632 restricted). F2 gave the actual-side collector a `taken_branch` field (PEP 669 BRANCH events, settrace next-line fallback), so a mismatched branch decision now fails a run's trace comparison the same way a mismatched task sequence always did. Checked directly (`e3_pairs.csv` diffed pre/post): every `negate-guard` mutant's `combined_confidence` collapsed to exactly 0.0 regardless of its `semantic_diff_rate` (previously graded 0.1-0.32, loosely tracking severity), and most `constant-perturb` mutants dropped from 0.8 to a shared 0.32 floor. This is score *saturation*, not noise: F2 makes the certificate a sharper pass/fail detector (see the three-figure calibration report's Youden's J moving 0.8532 -> 0.9017 and `negate-guard` detection 8/14 -> 14/14), which flattens the graded relationship this correlation measures. The ground-truth side is untouched -- the equivalent-mutant table below is byte-identical to the pre-F2 run (11/427, same per-operator breakdown), confirming the shift is entirely on the certificate side, exactly where F2 touched.

### r and rho recovered after Session A (A1 composition + A2 literal coverage)

Pre-Session-A (archived `archive/e3_correlation_report_pre_a1a2.md`): Pearson r = 0.3653 (0.5326 restricted), Spearman rho = 0.5212 (0.5784 restricted). This run: Pearson r = 0.4085 (0.5580 restricted), Spearman rho = 0.5400 (0.5988 restricted) -- both correlations moved back up, not down. A1 (differential verdict = v1_confidence alone, no V2 OR-padding) removes a saturating term that flattened graded scores toward 0 or 1 regardless of severity; A2 (round-robin string-pool + base-guard-literal seeding) additionally moved `constant-perturb` off its 0.32 floor for 8/9 mutants (see the calibration report), restoring a graded relationship for exactly the operator F2 had flattened hardest. The equivalent-mutant count (11/427) is unchanged -- ground truth is untouched, confirming the shift is entirely on the certificate side, same as the F2 transition above.

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
