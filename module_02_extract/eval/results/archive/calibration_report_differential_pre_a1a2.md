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

- Youden's J-optimal tau: **0.1000** (J=0.9017)

## Three-figure result (EVAL, held out)

1. **Genuine-bug detection**: 0.9571 (95% CI [0.920, 0.980], n=210)
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
| Youden's J | 0.8069 | 0.9017 |
| Detection / genuine-bug detection | 0.8636 (conflated) | 0.9571 |
| False-alarm rate | 0.0588 | 0.0588 |

Pre-correction reports archived at `eval/results/archive/calibration_report_differential_pre_lineshift_fix.md` and `eval/results/archive/e3_correlation_report_pre_earlyreturn_fix.md`.

## vs pre-F2 baseline (branch-decision field)

| metric | pre-F2 (archived) | post-F2 |
|---|---|---|
| Youden's J | 0.8532 | 0.9017 |
| Genuine-bug detection | 0.9286 | 0.9571 |
| False-alarm rate | 0.0588 | 0.0588 (unchanged, as required) |

Pre-F2 report archived at `eval/results/archive/calibration_report_differential_pre_branch_decision.md` (E3 side: `archive/e3_pairs_pre_branch_decision.csv`, `archive/e3_correlation_report_pre_branch_decision.md`).

## Detection rate by operator, genuinely-buggy mutants only (EVAL)

| operator | n | detected | detection rate |
|---|---|---|---|
| constant-perturb | 9 | 0 | 0.000 |
| corrupt-container-op | 16 | 16 | 1.000 |
| drop-step | 51 | 51 | 1.000 |
| early-return | 49 | 49 | 1.000 |
| negate-guard | 14 | 14 | 1.000 |
| reorder-steps | 49 | 49 | 1.000 |
| swap-branches | 4 | 4 | 1.000 |
| wrong-variable | 18 | 18 | 1.000 |

`negate-guard` reaching 14/14 here is F2 actually working, not a re-measurement of the same thing: pre-F2 it was 8/14 (see the archived report) -- a negated guard flips the branch decision on virtually every run, and now that the actual-side collector emits `taken_branch`, the comparator's D3 pathway catches every one of those mismatches directly instead of relying on the mutation happening to also perturb the task-call sequence.

`constant-perturb`'s 0.000 here is NOT an F2 no-op -- checked
directly in `e3_pairs.csv`: F2 does move this operator's
`combined_confidence`, from a 0.8 ceiling pre-F2 down to a 0.32
floor for the mutants it affects (a compared string literal
changes -- no different stub gets called, but the taken_branch
mismatch now still drags V1 confidence down). It just doesn't
cross tau=0.1000: the branch decision only diverges on some
fraction of the n_runs=10 random inputs (whichever hit the
mutated literal), not all of them, so V1 confidence lands well
above the guard-negation case's hard 0.0 floor. Raising
n_runs or picking inputs that reliably exercise the mutated
literal would sharpen this further; out of scope here (F2 was
the collector's decision field, not the input generator).
n=9 in this EVAL split is small; the per-operator rate should
be read with that in mind.
