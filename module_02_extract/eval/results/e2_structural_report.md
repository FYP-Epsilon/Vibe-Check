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

**Please eyeball these 10 randomly sampled uids** (seed 42) --
gold-vs-extracted rendered side-by-side in `eval/results/e2_manual_check/`:
4, 14, 15, 18, 29, 32, 36, 82, 87, 95. This is the human-validation
step that makes the gold citable; ~15 minutes.

## Aggregate (micro, across all scored programs)

- Programs scored: 101 (extraction failed: 0)
- Node precision/recall/F1: 0.8255 / 1.0000 / **0.9044**
- Edge precision/recall/F1: 0.6204 / 0.7589 / **0.6827**
- Strong node matches: 473, weak (order-fallback) matches: 0

## Per-tag breakdown

| tag | n | node F1 | edge F1 |
|---|---|---|---|
| conditional | 19 | 0.8400 | 0.5515 |
| conditional_update | 26 | 0.8333 | 0.5150 |
| linear | 34 | 1.0000 | 1.0000 |
| linear_update | 22 | 1.0000 | 1.0000 |

## Worst 10 by node F1 (extractor-bug leads for a future session)

| uid | tag | node F1 | edge F1 | node fp | node fn | diagnosis |
|---|---|---|---|---|---|---|
| 17 | conditional_update | 0.769 | 0.400 | 3 | 0 | 3 extra extracted node(s) (likely merge/exit bookkeeping) |
| 20 | conditional | 0.769 | 0.400 | 3 | 0 | 3 extra extracted node(s) (likely merge/exit bookkeeping) |
| 28 | conditional | 0.769 | 0.400 | 3 | 0 | 3 extra extracted node(s) (likely merge/exit bookkeeping) |
| 69 | conditional | 0.769 | 0.400 | 3 | 0 | 3 extra extracted node(s) (likely merge/exit bookkeeping) |
| 87 | conditional_update | 0.769 | 0.400 | 3 | 0 | 3 extra extracted node(s) (likely merge/exit bookkeeping) |
| 90 | conditional_update | 0.769 | 0.400 | 3 | 0 | 3 extra extracted node(s) (likely merge/exit bookkeeping) |
| 100 | conditional_update | 0.769 | 0.400 | 3 | 0 | 3 extra extracted node(s) (likely merge/exit bookkeeping) |
| 15 | conditional_update | 0.778 | 0.455 | 4 | 0 | 4 extra extracted node(s) (likely merge/exit bookkeeping) |
| 16 | conditional_update | 0.778 | 0.455 | 4 | 0 | 4 extra extracted node(s) (likely merge/exit bookkeeping) |
| 9 | conditional | 0.783 | 0.483 | 5 | 0 | 5 extra extracted node(s) (likely merge/exit bookkeeping) |
