"""dominators.py -- networkx-based dominator analysis (DominatorAnalyzer).

(Auto-extracted verbatim from the original monolith during modularization.)
"""

from __future__ import annotations

from typing import Any, Optional
import networkx as nx


class DominatorAnalyzer:
    """
    Compute immediate dominators and dominance frontiers using NetworkX.

    The dominator tree provides the structural proof required by V3:
    if node *d* dominates node *n*, then every path from the entry to
    *n* must pass through *d*.  This lets us verify BPMN ordering
    constraints (e.g. "Gateway CreditCheckPassed must precede
    Task ApproveLoan") syntactically.
    """

    def __init__(self, wir: dict[str, Any]) -> None:
        self.wir = wir
        self.g: nx.DiGraph = nx.DiGraph()
        self._build_graph()

    # -- internal helpers ------------------------------------------------

    def _build_graph(self) -> None:
        """Populate the NetworkX digraph from the WIR edge list."""
        for n in self.wir.get("nodes", []):
            self.g.add_node(n["id"], **n)
        for e in self.wir.get("edges", []):
            self.g.add_edge(e["source"], e["target"], **e)

    # -- public API ------------------------------------------------------

    def compute_immediate_dominators(self) -> dict[str, Optional[str]]:
        """
        Return a mapping ``{node_id: immediate_dominator_id}``.

        The entry node maps to ``None``.  If the graph is not reachable
        from the entry (e.g. disconnected due to incomplete exception
        handling), nodes outside the reachable set are omitted.
        """
        entry = self.wir.get("entry_node")
        if entry is None or entry not in self.g:
            return {}

        try:
            idoms = nx.immediate_dominators(self.g, entry)
        except nx.NetworkXError:
            # nx.immediate_dominators raises if entry does not reach all nodes.
            # We fall back to the reachable subgraph.
            reachable = nx.descendants(self.g, entry) | {entry}
            sub = self.g.subgraph(reachable).copy()
            idoms = nx.immediate_dominators(sub, entry)

        # Convert to serialisable dict; entry node has no idom.
        return {node: (dom if dom != node else None)
                for node, dom in idoms.items()}

    def compute_dominance_frontier(self) -> dict[str, set[str]]:
        """
        Return the dominance frontier for every node.

        A node *n* is in the dominance frontier of *d* iff *d* dominates
        a predecessor of *n* but does not strictly dominate *n*.
        """
        entry = self.wir.get("entry_node")
        if entry is None or entry not in self.g:
            return {}

        # Restrict to reachable nodes
        reachable = nx.descendants(self.g, entry) | {entry}
        sub = self.g.subgraph(reachable).copy()

        # nx.immediate_dominators's entry-node convention is version-
        # dependent: confirmed idom[entry] == entry on networkx 3.2.1,
        # confirmed entry omitted from the dict entirely on networkx 3.6.1
        # (see test_dominators.py's module docstring for how this was
        # diagnosed). Either way, the frontier walk below climbs this
        # chain via idoms.get(cur) expecting to eventually hit None -- on
        # a version where entry maps to itself, idoms.get(entry) keeps
        # returning entry forever once the climb reaches it, an infinite
        # loop, not a slow computation. Normalize the same way
        # compute_immediate_dominators() already does, so entry's chain
        # ends at None on every networkx version, not just the ones that
        # already omit or already null out the key.
        raw_idoms = nx.immediate_dominators(sub, entry)
        idoms = {node: (dom if dom != node else None) for node, dom in raw_idoms.items()}

        # Build dominator tree
        dom_tree: dict[str, set[str]] = {n: set() for n in sub.nodes()}
        for node, dom in idoms.items():
            if dom is not None:
                dom_tree[dom].add(node)

        # Compute frontier -- textbook Cytron et al. algorithm: for each
        # node with >=2 predecessors, walk each predecessor's own idom
        # chain up to (but not including) the node's own immediate
        # dominator, adding the node to every runner's frontier along the
        # way. The previous version compared `_dominates(node, runner)`
        # instead of `runner == idoms.get(node)` -- domination only flows
        # from ancestor to descendant in the idom tree, so a node almost
        # never dominates any of its own idom-chain ancestors, meaning
        # that check essentially never fired and the walk ran all the way
        # to the root instead of stopping at the node's immediate
        # dominator. Confirmed wrong on a plain diamond CFG (entry -> A,
        # entry -> B, A -> merge, B -> merge): produced frontier[entry] =
        # {merge}, when entry -- dominating the entire reachable graph --
        # must have an empty frontier.
        frontier: dict[str, set[str]] = {n: set() for n in sub.nodes()}

        for node in sub.nodes():
            preds = list(sub.predecessors(node))
            if len(preds) >= 2:
                node_idom = idoms.get(node)
                for pred in preds:
                    runner: Optional[str] = pred
                    while runner is not None and runner != node_idom:
                        frontier[runner].add(node)
                        runner = idoms.get(runner)

        return frontier

    def verify_ordering(self, required_before: str, required_after: str) -> dict[str, Any]:
        """
        V3 syntactic pre-check: verify that *required_before* dominates
        *required_after* in the CFG.

        Returns a dictionary with ``passed``, ``reason``, and the
        dominator path.
        """
        idoms = self.compute_immediate_dominators()
        if required_after not in idoms:
            return {
                "passed": False,
                "reason": f"'{required_after}' is not reachable from entry",
                "path": [],
            }

        # Walk the idom chain from required_after back to entry.
        path: list[str] = [required_after]
        cur: Optional[str] = idoms.get(required_after)
        while cur is not None:
            path.append(cur)
            if cur == required_before:
                return {
                    "passed": True,
                    "reason": f"'{required_before}' dominates '{required_after}'",
                    "path": list(reversed(path)),
                }
            cur = idoms.get(cur)

        return {
            "passed": False,
            "reason": f"'{required_before}' does NOT dominate '{required_after}'",
            "path": list(reversed(path)),
        }
