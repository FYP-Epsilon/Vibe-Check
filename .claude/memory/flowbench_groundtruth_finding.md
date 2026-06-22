---
name: flowbench-groundtruth-finding
description: Public IBM FLOW-BENCH has no executable Python impls or correctness labels — E1 needs a mutation corpus
metadata:
  type: project
---

Verified 2026-05-30 from `github.com/IBM/flow-bench` README + arXiv:2505.11646 (Duesterwald et al., EMNLP 2025 Industry).

The **public** FLOW-BENCH record is `{utterance (NL), prior_sequence, prior_context, bpmn ($ref), expected_output (ground-truth pythonic sequence + bpmn)}`. The "Python" is a **constrained Python-syntax IR** (assignment / if / for / while / function calls) for an NL→BPMN *generation* task — **NOT** executable LLM implementations, and there are **no correct-vs-buggy correctness labels** (tags only mark linear/conditional + create/update/delete).

**Why:** Module 02's experiment E1 ("≥95% bug detection") therefore has **no native ground-truth source** in the public dataset, regardless of sample size. The brief's "101 triplets / executable Python / 80 dev–21 eval split" is a **group-derived/augmented artifact**, not the published dataset — its provenance must be confirmed and documented as group-produced.

**How to apply:** Build E1's evaluation corpus by **mutation** of FLOW-BENCH workflows (≥40 buggy / ≥40 correct, disjoint CALIB⟂EVAL). Detection rates are then for *injected* defect classes — state that caveat. The 21-sample eval split is statistically fatal for a "≥95%" claim anyway: exact-binomial power 0.34, and 95% lower bound is only 0.867 even at a perfect 21/21. Full R&D synthesis in [[module02-rd-deliverable]] (`.claude/module02_rd_deliverable.md`).
