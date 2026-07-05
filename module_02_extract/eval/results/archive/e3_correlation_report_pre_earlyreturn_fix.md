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

- n = 429 mutants scored (execution failed: 0)
- Pearson r = 0.6238, 95% CI [0.5624, 0.6784]
- Spearman rho = 0.6198

### Restricted to semantic_diff_rate > 0 (n=318)

- Pearson r = 0.3164, 95% CI [0.2139, 0.4121]
- Spearman rho = 0.2408

## Equivalent mutants (semantic_diff_rate == 0 at N=25): 111 / 429

| operator | equivalent | total |
|---|---|---|
| boundary-shift | 1 | 1 |
| constant-perturb | 1 | 21 |
| corrupt-container-op | 1 | 30 |
| drop-step | 0 | 101 |
| early-return | 101 | 101 |
| negate-guard | 5 | 32 |
| reorder-steps | 1 | 99 |
| swap-branches | 1 | 8 |
| wrong-variable | 0 | 36 |

## Finding: early-return is a mutate.py implementation bug, not just a hard-to-detect operator

`early-return` shows 100% equivalent mutants -- verified by inspecting
generated mutant files directly, not just inferred from the rate: `eval/mutate.py`'s `op_early_return` inserts the new `return None` at `len(body) - 1`, i.e. immediately *before* the function's existing trailing statement. Every `eval/flowbench_adapter.py`-generated workflow already ends with a bare `return None` as that trailing statement, so the mutation fires at the exact same point the original would have -- it never actually cuts off any real logic (the for-loop/if-chain/stub calls all execute in full either way), it just duplicates the terminal no-op return as dead code. This reframes the earlier differential-mode calibration's ~0.43 detection rate for `early-return`: those weren't successfully detected genuine bugs surviving on hard-to-reach inputs -- they were **false positives on semantically-equivalent programs** (the certificate reporting `combined_confidence < tau` for code that is not actually buggy). Not fixed this session (`eval/mutate.py` is out of scope -- src/ and prior sessions' infra are frozen here), but this should be corrected before `early-return`'s detection numbers are cited anywhere as evidence of genuine bug detection.
