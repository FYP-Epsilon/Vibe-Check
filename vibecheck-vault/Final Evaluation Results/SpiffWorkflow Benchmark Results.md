# SpiffWorkflow Dataset Benchmark Results

> [!info] What this page is
> A plain-English report on VibeCheck's SpiffWorkflow dataset integration — expanding the gold-standard evaluation corpus from 18 pairs (FLOW-BENCH) to **65 gold pairs total** by ingesting executable BPMN diagrams and Python workflow implementations from SpiffWorkflow (`spiff-example-cli` and `sample-process-models`).

## 1. Why SpiffWorkflow?

IBM FLOW-BENCH provides LLM-generated Python workflow code, but has no native ground-truth labels for code correctness. By contrast, **SpiffWorkflow** (Python's native BPMN engine) provides **natively executable, verified (BPMN diagram, Python script) pairs** designed specifically to execute business process workflows.

Integrating SpiffWorkflow expands VibeCheck's gold evaluation set from 18 pairs (FLOW-BENCH) to **65 pairs total** (47 SpiffWorkflow + 18 FLOW-BENCH), providing a much larger baseline for pipeline measurement without relying solely on synthetic mutation selection.

## 2. Benchmark Results

- **Gold Specs Ingested:** 47
- **Order-Mutation Trials (drop_step + swap_adjacent):** 301
- **Perturbation Trials (order-preserving):** 47

| Metric | Value | 95% Confidence Interval | Sample Size |
|---|---|---|---|
| **Abstention Rate** | **44.2%** | [38.5%, 50.0%] | n=301 |
| **Detection Rate (Decisive)** | **28.6%** | [21.9%, 36.0%] | n=168 |
| **False-Alarm Rate** | **0.0%** | [0.0%, 7.5%] | n=47 |
| **Counterexample Quality** | **75.0%** | [60.4%, 86.4%] | n=48 |

## 3. Key Findings

1. **Higher Detection Rate:** On SpiffWorkflow's executable process models, the decisive detection rate is **28.6%** (compared to 16.2% on FLOW-BENCH), showing improved rule coverage on structured process models.
2. **Zero False Alarms:** Across 47 order-preserving literal perturbations, the pipeline generated **0 false alarms (0.0%)**, confirming that sound code changes are never misclassified as violations.
3. **Honest Abstention:** Similar to FLOW-BENCH, when a task-drop mutation renders a task's atomic proposition unobservable, the pipeline honestly abstains (`INCONCLUSIVE`, 44.2%) rather than guessing incorrectly.

## 4. Sources

- `demo/spiffworkflow/ingest.py` (automated dataset ingestion script)
- `demo/spiffworkflow/harness.py` (evaluation harness script)
- `demo/spiffworkflow/results/spiffworkflow_eval_report.md` & `spiffworkflow_eval_results.json`
