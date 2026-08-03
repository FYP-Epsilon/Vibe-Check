"""Module 01 corpus-scale evaluation harness (FLOW-BENCH).

Layout mirrors ``module_02_extract/eval/``:

    gold_bpmn.py    independent XML labeler (never imports src/)
    soundness.py    primary metric -- does a suite admit its own diagram?
    mutate_eval.py  secondary metric -- discriminative kill ratio
    report.py       emits results/m01_eval_report.md + per-diagram CSV
"""
