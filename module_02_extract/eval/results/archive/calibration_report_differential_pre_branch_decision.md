# Module 02 Corrected Calibration Report (Differential Mode)

Seed: `1234`. CALIB/EVAL split: 50/50 stratified by base-program tag.
tau selected on CALIB using ONLY genuinely-buggy mutants (semantic_diff_rate > 0) as positives and base programs as negatives -- equivalent mutants are excluded from tau selection.

## Why this report exists

The prior differential report's single 'detection rate' figure
conflated genuinely-buggy mutants with behaviorally-equivalent
ones (semantic_diff_rate == 0, from eval/e3_correlation.py's
code-vs-code ground truth -- the WIR never touches that side).
A correctly-unflagged equivalent mutant looks identical to a
missed genuine bug in that single number. This report separates
them into three figures. It also incorporates two fixes: C2
(branch_lines derived from the mutant's own WIR, not the base's
-- line-shift false positives) and C3 (op_early_return actually
cuts logic now, not a no-op).

- Youden's J-optimal tau: **0.1000** (J=0.8532)

## Three-figure result (EVAL, held out)

1. **Genuine-bug detection**: 0.9286 (95% CI [0.885, 0.959], n=210)
2. **Equivalent-mutant specificity**: 0.1111 (95% CI [0.003, 0.482], n=9)
3. **False-alarm rate (untouched bases)**: 0.0588 (95% CI [0.012, 0.162], n=51)

### Reading figure 2 (n=9, wide CI -- investigated, not a new bug)

EVAL contains only 9 equivalent mutants (clustered on 5 distinct
base uids -- one base can contribute several operators' worth),
so this CI is necessarily wide. Checked directly: 8 of the 9
score `combined_confidence` **exactly identical** to their own
base's own score -- i.e. where the base itself already sits
below tau (contributing to figure 3's false-alarm rate), an
equivalent mutant correctly inherits that same status, and C2's
fix leaves no residual line-shift artifact (confirmed by the
exact-match evidence, not inferred). The 1 exception (uid 3's
early-return mutant, 0.0 vs base 0.300) was checked directly: the
cut-off code guarded on `folder['name'] == None`, and E3's local
input generator never produces the value `None` for a str-typed
parameter (only pool literals / "" / junk strings), so its
semantic_diff_rate==0 verdict is itself a false negative from
E3's own documented N=25 sampling limitation -- the certificate's
flag is arguably the more correct call here, not a bug to fix.

## vs pre-correction aggregate baseline

| metric | pre-correction (archived) | corrected |
|---|---|---|
| Youden's J | 0.8069 | 0.8532 |
| Detection / genuine-bug detection | 0.8636 (conflated) | 0.9286 |
| False-alarm rate | 0.0588 | 0.0588 |

Pre-correction reports archived at `eval/results/archive/calibration_report_differential_pre_lineshift_fix.md` and `eval/results/archive/e3_correlation_report_pre_earlyreturn_fix.md`.

## Detection rate by operator, genuinely-buggy mutants only (EVAL)

| operator | n | detected | detection rate |
|---|---|---|---|
| constant-perturb | 9 | 0 | 0.000 |
| corrupt-container-op | 16 | 16 | 1.000 |
| drop-step | 51 | 51 | 1.000 |
| early-return | 49 | 49 | 1.000 |
| negate-guard | 14 | 8 | 0.571 |
| reorder-steps | 49 | 49 | 1.000 |
| swap-branches | 4 | 4 | 1.000 |
| wrong-variable | 18 | 18 | 1.000 |

`constant-perturb`'s 0.000 here is consistent with the prior
session's D3 finding, not a new surprise: it's a "value-only"
mutation (a compared literal changes, no different stub gets
called), which is exactly the class D3 predicted would need a
branch-decision field on the real collector (still missing,
explicitly out of scope) to detect via anything other than
task-sequence divergence. n=9 in this EVAL split is small; the
per-operator rate should be read with that in mind.
