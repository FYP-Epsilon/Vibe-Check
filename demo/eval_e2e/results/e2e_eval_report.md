# E2E Evaluation Harness -- First Real Run

Next Steps.md item #7. See `demo/eval_e2e/harness.py`'s module docstring
for the full ground-truth-provenance and sample-size caveats before
quoting any number below.

- Gold specs (checkable + >=1 confirmed-COMPLIANT real variant): **18** (uids [11, 45, 47, 48, 49, 50, 71, 72, 73, 75, 76, 77, 78, 81, 84, 85, 88, 100])
- Order-mutation trials (drop_step + swap_adjacent): 60
- Perturbation trials (order-preserving, verified): 9

## Finding: task-drop defects are frequently unobservable, not just undetected

Checked empirically (not assumed): a mutation that drops a task's own call entirely often makes that task's own atom vanish from what the code-side matcher can observe. When that happens, the pipeline correctly reports `INCONCLUSIVE` (it cannot claim an ordering result over a task it can no longer see happening) rather than a wrong `COMPLIANT`. This is honest behavior, not a detection failure -- so it is reported as its own rate, **excluded from the detection-rate denominator below**, rather than being silently averaged into a single misleading number. It does NOT happen for every drop -- when the dropped task isn't the one an applicable property actually references, the property stays (correctly or incorrectly) resolvable, so drop_step splits across all three outcomes; see the JSON results for the per-mutant breakdown.

**Abstention rate: 0.383** (95% CI [0.26, 0.52], n=60) -- fraction of order-mutation trials where the pipeline honestly abstained (`INCONCLUSIVE`, atom unmatched) rather than committing to a verdict.

## Detection rate

**0.162** (95% CI [0.06, 0.32], n=37) -- of the order-mutation trials where the pipeline committed to a verdict (excludes the abstentions above), the fraction correctly flagged VIOLATION on the same property gold satisfied with fully-matched atoms.

By mutation kind (n / detected / missed-as-compliant / abstained-inconclusive):

- `drop_step`: 38 / 0 / 15 / 23
- `swap_adjacent`: 22 / 6 / 16 / 0

## False-alarm rate

**0.000** (95% CI [0.00, 0.34], n=9) -- fraction of verified order-preserving literal perturbations the pipeline incorrectly flagged VIOLATION on. Note: unmutated gold variants are deliberately excluded from this denominator -- they were selected *because* they already verified COMPLIANT, so including them would be circular; only the perturbation mutants (novel relative to selection) are counted.

## Counterexample quality

**0.833** (95% CI [0.36, 1.00], n=6) -- of the mutations the pipeline correctly detected, the fraction whose rendered counterexample named every BPMN task the violated property's own formula references (a narrow, mechanical yes/no -- not a subjective rubric; see the PR body for why this scope was chosen).

## Discarded candidates

- uid 50: no eligible literal for perturb_constant
- uid 71: no eligible literal for perturb_constant
- uid 72: no eligible literal for perturb_constant
- uid 73: no eligible literal for perturb_constant
- uid 75: no eligible literal for perturb_constant
- uid 76: no eligible literal for perturb_constant
- uid 78: no eligible literal for perturb_constant
- uid 84: no eligible literal for perturb_constant
- uid 85: no eligible literal for perturb_constant
