# E2E Evaluation Harness -- First Real Run

Next Steps.md item #7. See `demo/eval_e2e/harness.py`'s module docstring
for the full ground-truth-provenance and sample-size caveats before
quoting any number below.

- Gold specs (checkable + >=1 confirmed-COMPLIANT real variant): **6** (uids [45, 72, 76, 77, 84, 85])
- Order-mutation trials (drop_step + swap_adjacent): 26
- Perturbation trials (order-preserving, verified): 2

## Finding: task-drop defects are frequently unobservable, not just undetected

Checked empirically (not assumed): a mutation that drops a task's own call entirely often makes that task's own atom vanish from what the code-side matcher can observe. When that happens, the pipeline correctly reports `INCONCLUSIVE` (it cannot claim an ordering result over a task it can no longer see happening) rather than a wrong `COMPLIANT`. This is honest behavior, not a detection failure -- so it is reported as its own rate, **excluded from the detection-rate denominator below**, rather than being silently averaged into a single misleading number. It does NOT happen for every drop -- when the dropped task isn't the one an applicable property actually references, the property stays (correctly or incorrectly) resolvable, so drop_step splits across all three outcomes; see the JSON results for the per-mutant breakdown.

**Abstention rate: 0.462** (95% CI [0.27, 0.67], n=26) -- fraction of order-mutation trials where the pipeline honestly abstained (`INCONCLUSIVE`, atom unmatched) rather than committing to a verdict.

## Detection rate

**0.357** (95% CI [0.13, 0.65], n=14) -- of the order-mutation trials where the pipeline committed to a verdict (excludes the abstentions above), the fraction correctly flagged VIOLATION on the same property gold satisfied with fully-matched atoms.

By mutation kind (n / detected / missed-as-compliant / abstained-inconclusive):

- `drop_step`: 16 / 0 / 4 / 12
- `swap_adjacent`: 10 / 5 / 5 / 0

## False-alarm rate

**0.000** (95% CI [0.00, 0.84], n=2) -- fraction of verified order-preserving literal perturbations the pipeline incorrectly flagged VIOLATION on. Note: unmutated gold variants are deliberately excluded from this denominator -- they were selected *because* they already verified COMPLIANT, so including them would be circular; only the perturbation mutants (novel relative to selection) are counted.

## Counterexample quality

**0.800** (95% CI [0.28, 0.99], n=5) -- of the mutations the pipeline correctly detected, the fraction whose rendered counterexample named every BPMN task the violated property's own formula references (a narrow, mechanical yes/no -- not a subjective rubric; see the PR body for why this scope was chosen).

## Discarded candidates

- uid 72: no eligible literal for perturb_constant
- uid 76: no eligible literal for perturb_constant
- uid 84: no eligible literal for perturb_constant
- uid 85: no eligible literal for perturb_constant
