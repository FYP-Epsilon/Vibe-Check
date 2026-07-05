"""test_e2.py -- unit tests for e2_structural.py's matching logic (X2).

Hand-built gold/extracted pairs, not the real corpus -- isolates the
matching algorithm itself from any extractor behavior.
"""

from __future__ import annotations

from eval.e2_structural import match_edges, match_nodes, score_program, _prf1


def _gold_node(gid, ntype, code):
    return {"gold_id": gid, "type": ntype, "code": code}


def _gold_edge(src, dst, label="seq"):
    return {"src_gold_id": src, "dst_gold_id": dst, "label": label}


def _ext_node(nid, ntype, code=None, guard=None):
    n = {"id": nid, "type": ntype}
    if code is not None:
        n["code"] = [code]
    if guard is not None:
        n["guard"] = guard
    return n


def _ext_edge(src, dst, guard=None):
    e = {"source": src, "target": dst}
    if guard is not None:
        e["guard"] = guard
    return e


class TestMatchNodes:
    def test_perfect_match(self):
        gold_nodes = [_gold_node("g1", "block", "a = 1"), _gold_node("g2", "return", "return a")]
        ext_nodes = [_ext_node("n1", "block", code="a = 1"), _ext_node("n2", "return", code="return a")]
        mapping, strong, weak = match_nodes(gold_nodes, ext_nodes)
        assert mapping == {"g1": "n1", "g2": "n2"}
        assert strong == 2
        assert weak == 0

    def test_missing_node_is_unmatched(self):
        gold_nodes = [_gold_node("g1", "block", "a = 1"), _gold_node("g2", "return", "return a")]
        ext_nodes = [_ext_node("n1", "block", code="a = 1")]  # return node missing
        mapping, strong, weak = match_nodes(gold_nodes, ext_nodes)
        assert mapping == {"g1": "n1"}
        assert "g2" not in mapping
        assert strong == 1

    def test_extra_extracted_node_is_unmatched(self):
        gold_nodes = [_gold_node("g1", "block", "a = 1")]
        ext_nodes = [_ext_node("n1", "block", code="a = 1"), _ext_node("n2", "block", code="")]  # synthetic merge
        mapping, strong, weak = match_nodes(gold_nodes, ext_nodes)
        assert mapping == {"g1": "n1"}
        assert "n2" not in mapping.values()

    def test_weak_match_on_order_when_text_differs(self):
        # for-loop gold text "items" vs extracted's raw guard text differing
        # in a way normalization doesn't cover -- falls back to order.
        gold_nodes = [_gold_node("g1", "loop", "for x in items")]
        ext_nodes = [_ext_node("n1", "loop", guard="some_other_text_entirely")]
        mapping, strong, weak = match_nodes(gold_nodes, ext_nodes)
        assert mapping == {"g1": "n1"}
        assert strong == 0
        assert weak == 1

    def test_gateway_uses_guard_field_not_code(self):
        gold_nodes = [_gold_node("g1", "gateway", "x > 0")]
        ext_nodes = [_ext_node("n1", "gateway", guard="x > 0")]  # code left empty, as cfg_extractor does
        mapping, strong, weak = match_nodes(gold_nodes, ext_nodes)
        assert mapping == {"g1": "n1"}
        assert strong == 1

    def test_loop_normalization_iter_prefix(self):
        gold_nodes = [_gold_node("g1", "loop", "for x in items")]
        ext_nodes = [_ext_node("n1", "loop", guard="iter items")]
        mapping, strong, weak = match_nodes(gold_nodes, ext_nodes)
        assert mapping == {"g1": "n1"}
        assert strong == 1


class TestMatchEdges:
    def test_perfect_match(self):
        node_mapping = {"g1": "n1", "g2": "n2"}
        gold_edges = [_gold_edge("g1", "g2")]
        ext_edges = [_ext_edge("n1", "n2")]
        tp, fp, fn = match_edges(gold_edges, ext_edges, node_mapping)
        assert (tp, fp, fn) == (1, 0, 0)

    def test_swapped_direction_does_not_match(self):
        node_mapping = {"g1": "n1", "g2": "n2"}
        gold_edges = [_gold_edge("g1", "g2")]
        ext_edges = [_ext_edge("n2", "n1")]  # reversed
        tp, fp, fn = match_edges(gold_edges, ext_edges, node_mapping)
        assert tp == 0
        assert fn == 1
        assert fp == 1

    def test_unmatched_endpoint_excludes_gold_edge(self):
        # g2 has no extracted counterpart -> this gold edge can't be scored
        # as a false negative in extracted-id space, so it's simply dropped
        # from the translated set (not double-penalized).
        node_mapping = {"g1": "n1"}
        gold_edges = [_gold_edge("g1", "g2")]
        ext_edges = []
        tp, fp, fn = match_edges(gold_edges, ext_edges, node_mapping)
        assert (tp, fp, fn) == (0, 0, 0)

    def test_extra_extracted_edge_is_false_positive(self):
        node_mapping = {"g1": "n1", "g2": "n2"}
        gold_edges = [_gold_edge("g1", "g2")]
        ext_edges = [_ext_edge("n1", "n2"), _ext_edge("n2", "n1")]
        tp, fp, fn = match_edges(gold_edges, ext_edges, node_mapping)
        assert (tp, fp, fn) == (1, 1, 0)


class TestScoreProgramF1:
    def test_perfect_match_gives_f1_one(self):
        gold = {
            "nodes": [_gold_node("g1", "block", "a = 1"), _gold_node("g2", "return", "return a")],
            "edges": [_gold_edge("g1", "g2")],
        }
        extracted = {
            "nodes": [_ext_node("n1", "block", code="a = 1"), _ext_node("n2", "return", code="return a")],
            "edges": [_ext_edge("n1", "n2")],
        }
        scores = score_program(gold, extracted)
        node_p, node_r, node_f1 = _prf1(scores["node_tp"], scores["node_fp"], scores["node_fn"])
        edge_p, edge_r, edge_f1 = _prf1(scores["edge_tp"], scores["edge_fp"], scores["edge_fn"])
        assert node_f1 == 1.0
        assert edge_f1 == 1.0

    def test_one_missing_node_gives_known_precision_recall(self):
        gold = {
            "nodes": [_gold_node("g1", "block", "a = 1"), _gold_node("g2", "return", "return a")],
            "edges": [_gold_edge("g1", "g2")],
        }
        extracted = {
            "nodes": [_ext_node("n1", "block", code="a = 1")],  # return node missing
            "edges": [],
        }
        scores = score_program(gold, extracted)
        node_p, node_r, _ = _prf1(scores["node_tp"], scores["node_fp"], scores["node_fn"])
        assert node_p == 1.0  # everything extracted was correct
        assert node_r == 0.5  # half of gold recovered
