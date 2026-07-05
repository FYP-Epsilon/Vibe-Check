"""test_calibrate_corrected.py -- unit tests for the three-figure corrected
calibration analysis (C4).

Synthetic records, not the real corpus -- isolates the classification and
threshold-selection logic from any certificate-scoring behavior.
"""

from __future__ import annotations

from eval.calibrate_corrected import three_figure_eval, youdens_j_on_genuine


def _rec(uid, cls, score, operator=None):
    return {"uid": uid, "class": cls, "operator": operator, "tag": "t", "combined_confidence": score}


class TestYoudensJOnGenuine:
    def test_excludes_equivalent_class_from_selection(self):
        # Equivalent mutants sit right where a naive selector would want to
        # draw the line -- if they leaked into selection, tau would move.
        records = [
            _rec(1, "correct", 0.9), _rec(2, "correct", 0.95),
            _rec(3, "buggy", 0.1), _rec(4, "buggy", 0.05),
            _rec(5, "equivalent", 0.5), _rec(6, "equivalent", 0.5),
        ]
        tau, j = youdens_j_on_genuine(records)
        # A perfect split exists between {0.9,0.95} (correct) and
        # {0.1,0.05} (buggy) -- tau should land in that gap, J should be 1.0,
        # regardless of the equivalent-class scores sitting in between.
        assert j == 1.0
        assert 0.1 < tau <= 0.9


class TestThreeFigureEval:
    def test_all_three_figures_computed_independently(self):
        records = [
            _rec(1, "correct", 0.9),           # not flagged -> ok
            _rec(2, "correct", 0.05),          # flagged -> false alarm
            _rec(3, "buggy", 0.05, "op_a"),    # flagged -> detected
            _rec(4, "buggy", 0.9, "op_a"),     # not flagged -> missed
            _rec(5, "equivalent", 0.9),        # not flagged -> correct
            _rec(6, "equivalent", 0.05),       # flagged -> false flag
        ]
        result = three_figure_eval(records, tau=0.5)
        assert result["detection_rate"] == 0.5   # 1/2 buggy detected
        assert result["n_genuine"] == 2
        assert result["equivalent_specificity"] == 0.5  # 1/2 equivalent correctly unflagged
        assert result["n_equivalent"] == 2
        assert result["false_alarm_rate"] == 0.5  # 1/2 correct flagged
        assert result["n_correct"] == 2

    def test_per_operator_breakdown_only_covers_genuine_class(self):
        records = [
            _rec(1, "buggy", 0.1, "op_a"),
            _rec(2, "buggy", 0.9, "op_b"),
            _rec(3, "equivalent", 0.1, "op_a"),  # must not leak into op_a's count
        ]
        result = three_figure_eval(records, tau=0.5)
        assert result["by_operator"]["op_a"]["n"] == 1
        assert result["by_operator"]["op_a"]["detected"] == 1
        assert result["by_operator"]["op_b"]["n"] == 1
        assert result["by_operator"]["op_b"]["detected"] == 0

    def test_empty_class_yields_none_rate(self):
        records = [_rec(1, "correct", 0.9)]
        result = three_figure_eval(records, tau=0.5)
        assert result["detection_rate"] is None
        assert result["n_genuine"] == 0
