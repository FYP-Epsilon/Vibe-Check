"""
Phase C: Pairwise Behavioural Clustering
==========================================
Feeds lifted automata into the stuttering engine to build a Behavioral
Equivalence Matrix. Groups clusters via Union-Find, selects a
representative LTS (lowest cyclomatic complexity), and flags isolated
models as "Singleton Anomalies".

Pure Python — no external dependencies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .lifter import LTS
    from .stuttering_engine import StutteringEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class ClusterResult:
    """Outcome of the behavioural clustering phase."""
    clusters: dict[int, list[str]] = field(default_factory=dict)
    representatives: dict[int, str] = field(default_factory=dict)
    singleton_anomalies: list[str] = field(default_factory=list)
    equivalence_matrix: dict[tuple[str, str], bool] = field(default_factory=dict)
    num_clusters: int = 0


# ---------------------------------------------------------------------------
# Union-Find (Disjoint Set Union) with path compression and union by rank
# ---------------------------------------------------------------------------

class _UnionFind:
    """Lightweight Union-Find with path compression and union by rank."""

    def __init__(self, elements: list[str]) -> None:
        self.parent: dict[str, str] = {e: e for e in elements}
        self.rank: dict[str, int] = {e: 0 for e in elements}

    def find(self, x: str) -> str:
        """Find with path compression."""
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        # Path compression
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        """Union by rank."""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1

    def groups(self) -> dict[str, list[str]]:
        """Return {root: [members, …]} mapping."""
        clusters: dict[str, list[str]] = {}
        for elem in self.parent:
            root = self.find(elem)
            clusters.setdefault(root, []).append(elem)
        return clusters


# ---------------------------------------------------------------------------
# Clusterer
# ---------------------------------------------------------------------------

class BehavioralClusterer:
    """
    Builds a Behavioral Equivalence Matrix via pairwise stuttering
    bisimulation checks, then clusters LTS models using Union-Find.

    Usage::

        engine   = StutteringEngine()
        cluster  = BehavioralClusterer(engine)
        result   = cluster.cluster(lts_list)
    """

    def __init__(self, engine: "StutteringEngine") -> None:
        self.engine = engine

    # -- public API --------------------------------------------------------

    def cluster(self, lts_list: list["LTS"]) -> ClusterResult:
        """
        Cluster a list of LTS objects by behavioural equivalence.

        Steps:
            1. Build pairwise equivalence matrix.
            2. Union-Find clustering.
            3. Select representatives (min cyclomatic complexity).
            4. Flag singleton anomalies.
        """
        if not lts_list:
            return ClusterResult()

        # Step 1
        matrix = self._build_equivalence_matrix(lts_list)

        # Step 2
        raw_clusters = self._union_find_cluster(lts_list, matrix)

        # Step 3
        lts_by_name = {l.name: l for l in lts_list}
        # Assign integer IDs
        clusters: dict[int, list[str]] = {}
        for idx, (_, members) in enumerate(sorted(raw_clusters.items())):
            clusters[idx] = sorted(members)

        representatives = self._select_representatives(clusters, lts_by_name)

        # Step 4
        singletons = [
            members[0]
            for members in clusters.values()
            if len(members) == 1
        ]

        result = ClusterResult(
            clusters=clusters,
            representatives=representatives,
            singleton_anomalies=singletons,
            equivalence_matrix=matrix,
            num_clusters=len(clusters),
        )

        logger.info(
            "Clustering complete: %d clusters, %d singletons.",
            result.num_clusters,
            len(singletons),
        )
        for cid, members in clusters.items():
            logger.info(
                "  Cluster %d: %s (rep=%s)",
                cid,
                members,
                representatives.get(cid, "?"),
            )
        if singletons:
            logger.warning("Singleton anomalies: %s", singletons)

        return result

    # -- equivalence matrix ------------------------------------------------

    def _build_equivalence_matrix(
        self, lts_list: list["LTS"]
    ) -> dict[tuple[str, str], bool]:
        """
        O(n²) pairwise bisimilarity comparison.

        Returns:
            Symmetric matrix as dict[(name_i, name_j)] → bool.
        """
        matrix: dict[tuple[str, str], bool] = {}
        n = len(lts_list)

        # Reflexive
        for l in lts_list:
            matrix[(l.name, l.name)] = True

        # Pairwise
        comparisons = 0
        for i in range(n):
            for j in range(i + 1, n):
                a, b = lts_list[i], lts_list[j]
                result = self.engine.are_bisimilar(a, b)
                matrix[(a.name, b.name)] = result
                matrix[(b.name, a.name)] = result
                comparisons += 1
                logger.debug(
                    "Bisimilarity %s ↔ %s: %s",
                    a.name,
                    b.name,
                    "YES" if result else "NO",
                )

        logger.info(
            "Equivalence matrix built: %d pairwise comparisons.", comparisons
        )
        return matrix

    # -- union-find clustering ---------------------------------------------

    def _union_find_cluster(
        self,
        lts_list: list["LTS"],
        matrix: dict[tuple[str, str], bool],
    ) -> dict[str, list[str]]:
        """Group bisimilar LTS using Union-Find."""
        names = [l.name for l in lts_list]
        uf = _UnionFind(names)

        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                if matrix.get((names[i], names[j]), False):
                    uf.union(names[i], names[j])

        return uf.groups()

    # -- representative selection ------------------------------------------

    def _select_representatives(
        self,
        clusters: dict[int, list[str]],
        lts_by_name: dict[str, "LTS"],
    ) -> dict[int, str]:
        """
        For each cluster, pick the LTS with the minimum cyclomatic
        complexity.  Ties broken by lexicographic name ordering.
        """
        reps: dict[int, str] = {}
        for cid, members in clusters.items():
            best = min(
                members,
                key=lambda n: (
                    lts_by_name[n].cyclomatic_complexity()
                    if n in lts_by_name
                    else float("inf"),
                    n,
                ),
            )
            reps[cid] = best
        return reps
