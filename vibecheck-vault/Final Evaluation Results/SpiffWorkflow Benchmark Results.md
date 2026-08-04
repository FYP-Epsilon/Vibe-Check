# SpiffWorkflow Dataset Benchmark Results

> [!info] What this page is
> A plain-English report on VibeCheck's SpiffWorkflow dataset integration — expanding the gold-standard evaluation corpus from 18 pairs (FLOW-BENCH) to **65 gold pairs total** by ingesting executable BPMN diagrams and Python workflow implementations from SpiffWorkflow (`spiff-example-cli` and `sample-process-models`). Also documents a precedence-formula soundness bug found and fixed during a later pass, and why the corrected numbers look slightly different from the first ingestion.

## 1. Why SpiffWorkflow?

IBM FLOW-BENCH provides LLM-generated Python workflow code, but has no native ground-truth labels for code correctness. By contrast, **SpiffWorkflow** (Python's native BPMN engine) provides **natively executable, verified (BPMN diagram, Python script) pairs** designed specifically to execute business process workflows.

Integrating SpiffWorkflow expands VibeCheck's gold evaluation set from 18 pairs (FLOW-BENCH) to **65 pairs total** (47 SpiffWorkflow + 18 FLOW-BENCH), providing a much larger baseline for pipeline measurement without relying solely on synthetic mutation selection.

## 2. Benchmark Results (current, corrected)

- **Gold Specs Ingested:** 47
- **Order-Mutation Trials (drop_step + swap_adjacent):** 301
- **Perturbation Trials (order-preserving):** 47

| Metric | Value | 95% Confidence Interval | Sample Size |
|---|---|---|---|
| **Abstention Rate** | **44.2%** | [38.5%, 50.0%] | n=301 |
| **Detection Rate (Decisive)** | **30.4%** | [23.5%, 37.9%] | n=168 |
| **False-Alarm Rate** | **0.0%** | [0.0%, 7.5%] | n=47 |
| **Counterexample Quality** | **74.5%** | [60.4%, 85.7%] | n=51 |

## 3. The precedence-formula bug: what happened, and why the numbers moved

A later change to `ltlf_synthesizer.py` (intended to make precedence formulas stricter, "pairwise strict precedence LTLf synthesis") introduced two defects at once:

1. **OR became AND at merge points.** A task with multiple predecessors used to require "at least one predecessor finished" (`!start(T) W (doneA | doneB)`) — correct for an exclusive/XOR-gateway merge, where only one branch ever actually runs. The change emitted one independent formula per predecessor instead, which — checked together — silently became "*all* predecessors must finish," which is only correct for a genuine parallel (AND-join) gateway. Applied to an XOR merge, it would flag a real execution as a violation just for having taken one branch instead of both.
2. **A start-reachability guard was dropped.** The original code only emitted a precedence formula when a target task was reachable *exclusively* through other tasks (`not has_start_path`). The change removed that check, so tasks reachable both directly from the start event *and* via another task got a precedence requirement they shouldn't have had.

Empirically, verified against the real corpus: **5 of the 47 gold pairs failed their own ingestion self-consistency check** because of these two defects (their synthesized "gold-compliant" reference trace tripped a violation against their own spec) and were silently dropped, shrinking the usable corpus to 42 without it being visible in the headline metrics. Detection rate on that smaller, silently-selected 42-pair corpus read as 31.6% — a number that looked like an improvement but was actually inflated by an unsound precedence check plus a shrunken, self-selected sample.

**Fix:** restored the `not has_start_path` guard, and made the OR-vs-AND choice conditional on the merge actually being a `parallelGateway` (real AND-join) rather than applying AND unconditionally to every multi-predecessor merge. Also removed a separate, unrelated issue: `synthesized_mutant_killers` properties were exact duplicates of properties already checked under `P1_Structural_Control_Flow` (confirmed in `mutation_refiner.py`), so they were being checked twice under two tier names — deduped so each formula is checked once.

**Result, isolated (via a controlled A/B re-ingestion holding the corpus fixed):**
- The precedence fix alone recovers the full 47-pair corpus (verified: all 5 previously-dropped pairs pass ingestion again).
- The dedup fix has no effect on corpus size or detection rate — it only removes double-counted checks.
- On the same 47-spec, 301-trial corpus the very first ingestion measured (28.6% detection, 75.0% counterexample quality), the corrected pipeline now measures **30.4% / 74.5%** — a small, genuine improvement, not the earlier +3pp illusion. The gain comes from the fix correctly enforcing parallel-gateway AND-joins for the first time, which neither the original nor the buggy version handled correctly. The two confidence intervals ([21.9%, 36.0%] vs [23.5%, 37.9%]) overlap substantially, so this should be read as "consistent with a small real improvement," not a statistically confirmed one at this sample size.

This is a second, independent instance of the pattern already documented in the Module 03 thesis chapter: a soundness fix can lower or barely move a headline detection number while making the underlying claim more defensible — fidelity, not raw detection rate, is the right thing to optimize for a translation-validation tool.

## 4. Key Findings

1. **Modest, honest detection rate:** the decisive detection rate is **30.4%** (compared to 16.2% on FLOW-BENCH), showing real but limited rule coverage on structured process models — not the earlier, bug-inflated 31.6%.
2. **Zero false alarms, but this claim is currently under-powered.** Across 47 order-preserving literal perturbations, the pipeline generated 0 false alarms. However, `generate_python_workflow()` (the synthetic gold-trace generator used by both ingestion and the harness) always emits a fully linear trace that runs every task regardless of branch structure — it cannot currently produce a trace that takes only one side of an XOR gateway. So this result does not yet demonstrate that the exact class of bug fixed in §3 can't recur on a real branch-exclusive execution; it demonstrates only that it doesn't occur under this benchmark's linear-trace methodology. Making the harness branch-aware is flagged as follow-up work to close this gap.
3. **Honest Abstention:** Similar to FLOW-BENCH, when a task-drop mutation renders a task's atomic proposition unobservable, the pipeline honestly abstains (`INCONCLUSIVE`, 44.2%) rather than guessing incorrectly.

## 5. Sources

- `demo/spiffworkflow/ingest.py` (automated dataset ingestion script)
- `demo/spiffworkflow/harness.py` (evaluation harness script)
- `demo/spiffworkflow/results/spiffworkflow_eval_report.md` & `spiffworkflow_eval_results.json`
- `module_01_spec/src/ltlf_synthesizer.py` (`_instantiate_ltlf_templates` — precedence-formula fix)
- `module_03_equiv/src/property_ingest.py` (`load_property_suite` — cross-tier dedup fix)
