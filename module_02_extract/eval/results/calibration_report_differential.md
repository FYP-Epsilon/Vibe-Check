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

## Composition change (A1): V1 is the differential verdict

Every score below is computed with `combined_confidence = v1_confidence` in differential mode, not the standard OR-composition
`1-(1-v1)(1-v2)` (still used unchanged by self-mode `/verify`). In
differential mode V1 has a real oracle (the base program's WIR) but
V2 does not -- it symbolically explores the MUTANT's own code with
no actual/expected comparator, so a high v2_confidence means "the
mutant is internally consistent with itself," not "no bug found."
OR-composing it padded every score, buggy and correct alike, with a
term carrying no detection signal: a negate-guard mutant on a
stub-free scalar workflow could score v1=0.0 (perfect detection) yet
combined=0.5, because self-referential v2=0.5 floored the OR (see
`eval/test_calibrate.py::test_value_only_guard_mutation_now_detected`).
`v2_confidence` stays in every certificate as telemetry (spec-path
coverage), it just no longer participates in the verdict.

- Youden's J-optimal tau: **0.1000** (J=0.9600)

## Three-figure result (EVAL, held out)

1. **Genuine-bug detection**: 0.9952 (95% CI [0.974, 1.000], n=210)
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
| Youden's J | 0.8069 | 0.9600 |
| Detection / genuine-bug detection | 0.8636 (conflated) | 0.9952 |
| False-alarm rate | 0.0588 | 0.0588 |

Pre-correction reports archived at `eval/results/archive/calibration_report_differential_pre_lineshift_fix.md` and `eval/results/archive/e3_correlation_report_pre_earlyreturn_fix.md`.

## vs pre-F2 baseline (branch-decision field)

| metric | pre-F2 (archived) | post-F2 |
|---|---|---|
| Youden's J | 0.8532 | 0.9600 |
| Genuine-bug detection | 0.9286 | 0.9952 |
| False-alarm rate | 0.0588 | 0.0588 (unchanged, as required) |

Pre-F2 report archived at `eval/results/archive/calibration_report_differential_pre_branch_decision.md` (E3 side: `archive/e3_pairs_pre_branch_decision.csv`, `archive/e3_correlation_report_pre_branch_decision.md`).

## vs pre-A1/A2 baseline (composition + literal-coverage session)

| metric | pre-A1/A2 (archived) | post-A1/A2 |
|---|---|---|
| Youden's J | 0.9017 | 0.9600 |
| Genuine-bug detection | 0.9571 | 0.9952 |
| False-alarm rate | 0.0588 | 0.0588 |

**Honest-risk clause (pre-committed in the session mandate): false-alarm rate did NOT rise.** It is unchanged at 0.0588 (51 bases, same count flagged as before A1). This is not a coincidence masking
traded-off bases -- checked directly (a clean pre-session worktree
vs. this branch, same 101 base programs): `v2_confidence` is 0.0
for every FLOW-BENCH-derived base program in this corpus
(container-shaped inputs make V2 bail, the same reason corpus
negate-guard mutants score v1=0 without V2 rescue, noted in the
F2-era regression test). Since V2 already contributed no
OR-composition padding to this corpus's negative class before A1,
removing it from the verdict had nothing to take away. A1's
masking risk is real for stub-free/scalar-input programs (the case
the session mandate names and
`test_value_only_guard_mutation_now_detected` demonstrates
directly) -- this corpus's FLOW-BENCH-style programs are
container-heavy and so do not exercise that risk. No newly-flagged
bases; no per-base diagnosis is needed and the >0.15 hard-stop was
not approached.

## Detection rate by operator, genuinely-buggy mutants only (EVAL)

| operator | n | detected | detection rate |
|---|---|---|---|
| constant-perturb | 9 | 8 | 0.889 |
| corrupt-container-op | 16 | 16 | 1.000 |
| drop-step | 51 | 51 | 1.000 |
| early-return | 49 | 49 | 1.000 |
| negate-guard | 14 | 14 | 1.000 |
| reorder-steps | 49 | 49 | 1.000 |
| swap-branches | 4 | 4 | 1.000 |
| wrong-variable | 18 | 18 | 1.000 |

`negate-guard` reaching 14/14 here is F2 actually working, not a re-measurement of the same thing: pre-F2 it was 8/14 (see the archived report) -- a negated guard flips the branch decision on virtually every run, and now that the actual-side collector emits `taken_branch`, the comparator's D3 pathway catches every one of those mismatches directly instead of relying on the mutation happening to also perturb the task-call sequence.

`constant-perturb` moved off 0/9 to 8/9 here -- this is A2 (round-robin
string-pool sampling + seeding the pool with the BASE
program's own guard literals, not just the mutant's) actually
working, not a re-measurement of the same thing. Before A2,
V1's pool came only from the mutant's OWN source -- for a
constant-perturb mutant that pool is the single mutated
literal, so a random run had only a small chance of ALSO
drawing the original literal, and many runs exercised neither
value -- the branch decision agreed vacuously on both sides.
Guaranteeing both literals are drawn at least once within the
n_runs=10 budget is what surfaces the taken_branch mismatch.

The remaining 1/9 straggler (uid_4's `'urgent'` -> `'urgent_MUTATED'` mutant, checked directly) is not the numeric-literal case
anticipated going into this session -- it's still a string
guard. Its root cause is different: uid_4's base has TWO
guards on `issue['priority']` (`== 'urgent'` and
`== 'low'`), and the guarded value is a dict field
populated from TWO independent `str` parameters
(`issues_priority_0`/`issues_priority_1`). A2's round-robin
queue is shared across a function's str params, not
per-guard-site: the union pool here is 3 literals
(`'low'`, `'urgent'`, `'urgent_MUTATED'` -- `'low'` is
unmutated and shared by both mutant and base), so it takes
TWO runs to drain across 2 params, not one -- checked
directly: run 0 draws `{p0: 'low', p1: 'urgent'}`, run 1
draws `{p0: 'urgent_MUTATED', p1: 'low'}`. Both happen to
be forced-divergent (run 0's p1='urgent' hits the base-only
branch; run 1's p0='urgent_MUTATED' hits the mutant-only
branch), but that's still only 2 of the 10-run budget. The
other 8 revert to uniform random sampling per param, which
rarely re-hits either specific literal, so most runs agree
vacuously and V1 confidence lands at 0.36 -- well above
tau, unlike the single-guard/single-str-param mutants where
the guaranteed runs' effect dominates a larger share of the
budget. Sharpening this (e.g. per-guard-site literal
coverage instead of one function-wide queue) is a real
backlog item, out of scope here.
