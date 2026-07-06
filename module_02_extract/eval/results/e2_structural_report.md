# E2: WIR Structural Accuracy Report

## Methods

Gold structure comes from `eval/gold_wir.py`, an independent
ast-only labeler that **never imports `src/ast_extractor/`**
(enforced by an import-scan test) -- grading the extractor against
its own code would be circular and meaningless. Extracted WIR comes
from `run_v3_pipeline` (`src/ast_extractor/pipeline.py`) on the same
101 FLOW-BENCH corpus programs used throughout this evaluation.

Node matching: greedy 1:1 on (type, normalized text); nodes that
align by (type, order-within-type) but not by text count separately
as `weak_matches` (still counted as matched for edge scoring). Edge
matching: an extracted edge matches a gold edge iff both endpoints
matched 1:1 and direction agrees; edge labels are not required to
agree (reported separately would require label-normalization work
not undertaken this session -- out of scope).

Human-validated (seed 42, uids 4, 14, 15, 18, 29, 32, 36, 82, 87, 95): see `eval/results/e2_manual_check/VERDICT.md`. That review was done
against the pre-contraction extractor output (before the F1 fix
below) and confirmed every extra extracted node was blank
merge/exit bookkeeping, zero genuine extraction errors -- exactly
what F1 then removed. The manual-check render files and gold are
intentionally left untouched by F1 (they're the validated
evidence a fix was warranted, not something to regenerate).

## Aggregate (micro, across all scored programs)

- Programs scored: 101 (extraction failed: 0)
- Node precision/recall/F1: 1.0000 / 1.0000 / **1.0000**
- Edge precision/recall/F1: 1.0000 / 1.0000 / **1.0000**
- Strong node matches: 473, weak (order-fallback) matches: 0

## vs pre-contraction baseline (F1 fix)

| metric | pre-contraction (archived) | post-contraction |
|---|---|---|
| Node precision | 0.8255 | 1.0000 |
| Node recall | 1.0000 | 1.0000 |
| Node F1 | 0.9044 | 1.0000 |
| Edge precision | 0.6204 | 1.0000 |
| Edge recall | 0.7589 | 1.0000 |
| Edge F1 | 0.6827 | 1.0000 |

Pre-contraction reports archived at `eval/results/archive/e2_structural_report_pre_bookkeeping_contraction.md` and `.../e2_per_program_pre_bookkeeping_contraction.csv`. The gap
closes entirely: F1 is a pure post-construction graph-contraction
pass (`contract_bookkeeping_nodes` in
`src/ast_extractor/cfg_extractor.py`) removing the blank merge/exit
nodes VERDICT.md confirmed were the whole precision gap -- no
change to what the visitors extract, verified by zero new V3 abort
gate failures across all 101 corpus programs (node_coverage stayed
at 1.0 for every one) and the differential calibration not moving
(task events don't ride on blank nodes).

## Per-tag breakdown

| tag | n | node F1 | edge F1 |
|---|---|---|---|
| conditional | 19 | 1.0000 | 1.0000 |
| conditional_update | 26 | 1.0000 | 1.0000 |
| linear | 34 | 1.0000 | 1.0000 |
| linear_update | 22 | 1.0000 | 1.0000 |

## Worst 10 by node F1 (extractor-bug leads for a future session)

| uid | tag | node F1 | edge F1 | node fp | node fn | diagnosis |
|---|---|---|---|---|---|---|
| 1 | linear | 1.000 | 1.000 | 0 | 0 | n/a |
| 2 | conditional | 1.000 | 1.000 | 0 | 0 | n/a |
| 3 | conditional | 1.000 | 1.000 | 0 | 0 | n/a |
| 4 | conditional | 1.000 | 1.000 | 0 | 0 | n/a |
| 5 | conditional | 1.000 | 1.000 | 0 | 0 | n/a |
| 6 | conditional | 1.000 | 1.000 | 0 | 0 | n/a |
| 7 | conditional | 1.000 | 1.000 | 0 | 0 | n/a |
| 8 | linear | 1.000 | 1.000 | 0 | 0 | n/a |
| 9 | conditional | 1.000 | 1.000 | 0 | 0 | n/a |
| 10 | conditional | 1.000 | 1.000 | 0 | 0 | n/a |
