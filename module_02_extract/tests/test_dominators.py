"""
tests/test_dominators.py
==========================
Next Steps.md item #13a: investigating why TestWIRDataLayer/TestV3Certificate/
TestEndToEnd hang indefinitely under Python 3.9 found the root cause is
actually networkx-version-dependent, not Python-version-dependent per se
(the two happen to correlate in this project's two dev venvs, since the
older networkx pinned for Python 3.9 compatibility is the one exhibiting
this): two real bugs in compute_dominance_frontier(), both fixed here and
pinned against regressing.

1. INFINITE LOOP (the actual hang): nx.immediate_dominators's own
   idom[entry] == entry self-mapping convention is version-dependent --
   confirmed present in networkx 3.2.1 (this project's Python-3.9 venv,
   where the hang was originally observed) and absent (entry omitted from
   the dict entirely) in networkx 3.6.1 (this project's Python-3.11 venv,
   where run_v3_pipeline was separately confirmed not to hang). The
   frontier computation's own idoms dict was built raw from whichever
   networkx returns, unlike compute_immediate_dominators() which already
   normalizes self-mapping to None. _dominates()'s walk-up-the-idom-chain
   loop (and the frontier loop below it) climb via idoms.get(cur)
   expecting to eventually hit None -- on a version where entry maps to
   itself, once the climb reaches entry it never terminates.

2. WRONG VALUES (found while fixing #1, before this file existed to catch
   it): the frontier loop's stopping condition was `not _dominates(node,
   runner)` instead of the textbook Cytron et al. `runner != idom(node)`.
   Domination only flows ancestor->descendant in the idom tree, so a node
   essentially never dominates its own idom-chain ancestors -- meaning
   the old condition almost never fired, and the walk ran all the way to
   the root instead of stopping at the node's own immediate dominator.
   Confirmed via a plain diamond CFG: produced frontier[entry] = {merge},
   when entry -- dominating the entire reachable graph -- must have an
   empty frontier.

Currently inert in production (confirmed by grep: nothing outside this
file and pipeline.py's own assignment reads wir["dominance_frontier"],
and it isn't part of shared_schemas/wir_schema.json), but the infinite
loop is a real, live risk: run_v3_pipeline (module_02's actual extraction
entrypoint, called from every /verify request) calls straight into it.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from ast_extractor.dominators import DominatorAnalyzer


def _diamond_wir():
    """entry -> A, entry -> B, A -> merge, B -> merge."""
    return {
        "entry_node": "entry",
        "nodes": [{"id": n} for n in ["entry", "A", "B", "merge"]],
        "edges": [
            {"source": "entry", "target": "A"},
            {"source": "entry", "target": "B"},
            {"source": "A", "target": "merge"},
            {"source": "B", "target": "merge"},
        ],
    }


def _nested_diamond_wir():
    """Two diamonds in sequence: entry->A,B->merge1->C,D->merge2."""
    return {
        "entry_node": "entry",
        "nodes": [{"id": n} for n in ["entry", "A", "B", "C", "D", "merge1", "merge2"]],
        "edges": [
            {"source": "entry", "target": "A"},
            {"source": "entry", "target": "B"},
            {"source": "A", "target": "merge1"},
            {"source": "B", "target": "merge1"},
            {"source": "merge1", "target": "C"},
            {"source": "merge1", "target": "D"},
            {"source": "C", "target": "merge2"},
            {"source": "D", "target": "merge2"},
        ],
    }


class TestComputeDominanceFrontierTerminates:
    """Regression for bug #1 -- these must return promptly, not hang.
    A hanging assertion isn't expressible directly in pytest, so the
    proof is simply that this test file completes at all; a true
    regression here would make the whole suite time out."""

    def test_diamond_terminates_and_returns_all_nodes(self):
        frontier = DominatorAnalyzer(_diamond_wir()).compute_dominance_frontier()
        assert set(frontier.keys()) == {"entry", "A", "B", "merge"}

    def test_nested_diamond_terminates(self):
        frontier = DominatorAnalyzer(_nested_diamond_wir()).compute_dominance_frontier()
        assert set(frontier.keys()) == {"entry", "A", "B", "C", "D", "merge1", "merge2"}


class TestComputeDominanceFrontierCorrectness:
    """Regression for bug #2 -- the actual frontier *values*, not just
    termination. Expected values are textbook (Cytron et al.) dominance
    frontiers for these shapes, cross-checked by hand in this file's own
    module docstring."""

    def test_diamond_frontier_values(self):
        frontier = DominatorAnalyzer(_diamond_wir()).compute_dominance_frontier()
        assert frontier == {
            "entry": set(),
            "A": {"merge"},
            "B": {"merge"},
            "merge": set(),
        }

    def test_entry_frontier_is_always_empty_when_entry_dominates_everything(self):
        """The specific wrong value bug #2 produced: entry dominates the
        entire reachable graph, so nothing can ever be 'just outside' its
        dominated region -- its frontier must be empty regardless of
        graph shape."""
        for wir in (_diamond_wir(), _nested_diamond_wir()):
            frontier = DominatorAnalyzer(wir).compute_dominance_frontier()
            assert frontier["entry"] == set()

    def test_nested_diamond_frontier_values(self):
        frontier = DominatorAnalyzer(_nested_diamond_wir()).compute_dominance_frontier()
        assert frontier == {
            "entry": set(),
            "A": {"merge1"},
            "B": {"merge1"},
            "merge1": set(),
            "C": {"merge2"},
            "D": {"merge2"},
            "merge2": set(),
        }

    def test_linear_chain_has_no_frontiers(self):
        """No node has >=2 predecessors, so every frontier is empty."""
        wir = {
            "entry_node": "entry",
            "nodes": [{"id": n} for n in ["entry", "mid", "end"]],
            "edges": [
                {"source": "entry", "target": "mid"},
                {"source": "mid", "target": "end"},
            ],
        }
        frontier = DominatorAnalyzer(wir).compute_dominance_frontier()
        assert all(s == set() for s in frontier.values())


class TestComputeImmediateDominatorsUnaffected:
    """compute_immediate_dominators() is untouched by this fix -- pinning
    its existing behavior.

    Cross-networkx-version note (found while diagnosing this exact bug):
    networkx's own immediate_dominators() self-maps the entry node
    (idom[entry] == entry) on some versions (confirmed: 3.2.1, the one in
    this project's Python-3.9 dev venv, the version that actually produces
    the original infinite loop) and omits entry as a key entirely on
    others (confirmed: 3.6.1, this project's Python-3.11 venv) -- so
    "entry has no real dominator" must be checked via .get("entry"),
    which is None either way, not by asserting the dict's exact key set."""

    def test_entry_has_no_dominator(self):
        idoms = DominatorAnalyzer(_diamond_wir()).compute_immediate_dominators()
        assert idoms.get("entry") is None

    def test_diamond_idoms(self):
        idoms = DominatorAnalyzer(_diamond_wir()).compute_immediate_dominators()
        assert idoms.get("A") == "entry"
        assert idoms.get("B") == "entry"
        assert idoms.get("merge") == "entry"
        assert idoms.get("entry") is None
