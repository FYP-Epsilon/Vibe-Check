# E2 Manual Validation Verdict — 2026-07-06

Human review of the 10 randomly sampled (seed 42) gold-vs-extracted pairs
requested by `eval/results/e2_structural_report.md`. Reviewer: project author.

| uid | pattern | gold nodes | extracted nodes | extra blank nodes | verdict |
|---|---|---|---|---|---|
| 4 | if/elif in for | 8 | 12 | 4 (merge/exit) | PASS |
| 14 | if in for | 6 | 9 | 3 (merge/exit) | PASS |
| 15 | if/elif in for | 7 | 11 | 4 (merge/exit) | PASS |
| 18 | if in for | 6 | 9 | 3 (merge/exit) | PASS |
| 29 | linear | 5 | 5 | 0 | PASS |
| 32 | linear | 4 | 4 | 0 | PASS |
| 36 | linear | 3 | 3 | 0 | PASS |
| 82 | linear | 6 | 6 | 0 | PASS |
| 87 | negated if in for | 5 | 8 | 3 (merge/exit) | PASS |
| 95 | if/else in for | 6 | 8 | 2 (merge/exit) | PASS |

Findings:

- **No gold node was dropped or misrepresented in any file** — validates both
  the extractor's 100% node recall and the independent gold labeler
  (`eval/gold_wir.py`) itself.
- **Every extra extracted node is a blank merge/exit bookkeeping node** sitting
  at branch-merge or loop-exit junctions. This upgrades the E2 report's
  worst-10 diagnosis from "likely merge/exit bookkeeping" to **confirmed**:
  the entire node-precision gap (0.8255) and the edge-precision gap trace to
  these synthetic nodes, not to extraction errors.
- Detail checks that passed: re-assigned variables kept as separate sequential
  statements (uid 82); negated guard preserved verbatim (uid 87); else-branch
  represented as negated-guard edge (uid 95).

Consequence: the E2 aggregate numbers (node F1 0.9044, edge F1 0.6827) are
**conservative** — they measure the extractor's current output against a
semantic-node-only gold. Suppressing or annotating the bookkeeping nodes in
the emitted WIR (already on the backlog from the worst-10 list) would raise
measured precision without changing extraction behavior. The gold itself is
now human-validated and citable.
