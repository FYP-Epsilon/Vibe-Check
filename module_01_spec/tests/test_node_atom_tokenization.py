"""
tests/test_node_atom_tokenization.py
====================================
Found while fixing FlowBench defect #1, and previously invisible because of it.

semantic_extractor emits `node({clean_name})` as the atomic proposition for
every non-task node, but ltlf_eval's TOKEN_SPEC had rules only for `start(...)`
and `done(...)`. `node(X)` therefore tokenized as IDENT_ATOM + LPAREN and the
parser raised "Expected token RPAREN, got LPAREN" -- so every P0 sentinel and
P1 control-flow property written over a node proposition was unparseable.

This never surfaced in the corpus because the malformed P2 comment property
(defect #1) failed first on all 148 diagrams and masked it. With defect #1
fixed alone, Phase 4 still failed on 134/148; only after adding the NODE_ATOM
rule does it produce a real certificate on 148/148.

Names carrying ':' or '.' are pinned too: those hit the MISMATCH rule and
produced a second, distinct error class ("Unexpected character ':'").
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from ltlf_eval import evaluate_ltlf


def test_node_atom_parses_when_nested_in_a_temporal_operator():
    """The observed failure shape: a node proposition inside G(...) and F(...).
    Pinned as the exact formula the corpus produced, not a simplified stand-in."""
    formula = "G(node(Start) -> !F(node(End)))"
    # Must not raise. The trace makes the antecedent true so the body is
    # genuinely evaluated rather than short-circuited at parse time.
    evaluate_ltlf(formula, [{"node(Start)"}])


def test_node_atom_with_punctuation_in_the_name():
    """Second error class from the same root cause: BPMN labels reach the
    proposition as-is, so ':' and '.' appear inside node(...). Without a
    NODE_ATOM rule these hit MISMATCH and raised on the character itself."""
    formula = "!node(Merge) W node(Decision:_folder.name)"
    evaluate_ltlf(formula, [{"node(Decision:_folder.name)"}])


def test_node_atom_truth_value_is_membership_not_always_true():
    """A tokenizer fix that made every node(...) atom vacuously true would
    also make these formulas 'parse', so the semantics are pinned: the atom
    must be satisfied only when present in the trace state."""
    assert evaluate_ltlf("node(A)", [{"node(A)"}]) is True
    assert evaluate_ltlf("node(A)", [{"node(B)"}]) is False


def test_existing_start_and_done_atoms_still_parse():
    """The NODE_ATOM rule is inserted into an ordered TOKEN_SPEC, where an
    over-broad pattern could shadow its neighbours. Guarding the two atom
    forms that already worked."""
    assert evaluate_ltlf("!done(A) W start(A)", [{"start(A)"}]) is True
