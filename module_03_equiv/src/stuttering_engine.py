"""
Phase B: Divergence-Sensitive Stuttering Bisimulation Engine
=============================================================
Pre-processes LTS using Tarjan's SCC algorithm to isolate the purely
silent τ-subgraph, flagging cycles with ``is_divergent = True``.
Executes a Naive Partition Refinement loop (O(n²)) to group states
into equivalence classes.

All operations are pure Python with no external dependencies.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .lifter import LTS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class StutteringResult:
    """Outcome of the divergence-sensitive stuttering analysis."""
    equivalence_classes: dict[int, set[str]] = field(default_factory=dict)
    state_to_block: dict[str, int] = field(default_factory=dict)
    divergent_states: set[str] = field(default_factory=set)
    num_blocks: int = 0
    scc_components: list[set[str]] = field(default_factory=list)
    divergent_sccs: list[set[str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class StutteringEngine:
    """
    Implements divergence-sensitive stuttering bisimulation via:

    1. Tau-subgraph extraction
    2. Iterative Tarjan SCC decomposition
    3. Divergence identification and backward propagation
    4. Naive O(n²) partition refinement
    """

    def __init__(self) -> None:
        pass

    # -- public API --------------------------------------------------------

    def compute(self, lts: "LTS") -> StutteringResult:
        """
        Run the full stuttering analysis pipeline on a single LTS.

        Returns:
            A :class:`StutteringResult` with equivalence classes,
            divergence information, and SCC decomposition.
        """
        all_states = set(lts.states.keys())
        if not all_states:
            return StutteringResult()

        # Step 1: build tau-only adjacency
        fwd_adj, rev_adj = self._build_tau_adjacency(lts)

        # Step 2: Tarjan SCC on the tau-subgraph
        sccs = self._tarjan_scc(all_states, fwd_adj)

        # Step 3: identify divergent SCCs
        div_states, div_sccs = self._identify_divergent_sccs(sccs, fwd_adj)

        # Step 4: propagate divergence backwards
        div_states = self._propagate_divergence(div_states, rev_adj, all_states)

        # Step 5: partition refinement
        state_to_block, block_to_states = self._naive_partition_refinement(
            lts, div_states
        )

        result = StutteringResult(
            equivalence_classes=block_to_states,
            state_to_block=state_to_block,
            divergent_states=div_states,
            num_blocks=len(block_to_states),
            scc_components=sccs,
            divergent_sccs=div_sccs,
        )
        logger.info(
            "Stuttering analysis complete: %d blocks, %d divergent states, %d SCCs",
            result.num_blocks,
            len(result.divergent_states),
            len(result.scc_components),
        )
        return result

    def are_bisimilar(self, lts1: "LTS", lts2: "LTS") -> bool:
        """
        Check whether two LTS are divergence-sensitive stuttering bisimilar.

        Merges both LTS into a single combined LTS (with prefixed state IDs)
        and checks whether their initial states fall into the same
        equivalence class after partition refinement.
        """
        from .lifter import LTS as LTSClass

        combined = LTSClass(name=f"combined_{lts1.name}_{lts2.name}")

        prefix1 = f"{lts1.name}::"
        prefix2 = f"{lts2.name}::"

        # Merge states
        for sid, meta in lts1.states.items():
            combined.states[prefix1 + sid] = dict(meta)
        for sid, meta in lts2.states.items():
            combined.states[prefix2 + sid] = dict(meta)

        # Merge transitions
        for src, tgt, lbl in lts1.transitions:
            combined.transitions.append((prefix1 + src, prefix1 + tgt, lbl))
        for src, tgt, lbl in lts2.transitions:
            combined.transitions.append((prefix2 + src, prefix2 + tgt, lbl))

        combined.initial_state = prefix1 + lts1.initial_state
        combined.atomic_propositions = (
            lts1.atomic_propositions | lts2.atomic_propositions
        )

        result = self.compute(combined)

        init1 = prefix1 + lts1.initial_state
        init2 = prefix2 + lts2.initial_state

        block1 = result.state_to_block.get(init1)
        block2 = result.state_to_block.get(init2)

        bisimilar = block1 is not None and block1 == block2
        logger.info(
            "Bisimilarity check %s vs %s: %s (blocks %s / %s)",
            lts1.name,
            lts2.name,
            "BISIMILAR" if bisimilar else "NOT BISIMILAR",
            block1,
            block2,
        )
        return bisimilar

    # -- tau adjacency -----------------------------------------------------

    def _build_tau_adjacency(
        self, lts: "LTS"
    ) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        """
        Build forward and reverse adjacency lists for the tau-subgraph.

        A transition is considered *silent* (tau) when its label is
        ``'tau'`` or ``'true'`` (universal boolean guard).
        """
        fwd: dict[str, list[str]] = {s: [] for s in lts.states}
        rev: dict[str, list[str]] = {s: [] for s in lts.states}

        for src, tgt, lbl in lts.transitions:
            if lbl in ("tau", "true"):
                fwd.setdefault(src, []).append(tgt)
                rev.setdefault(tgt, []).append(src)

        return fwd, rev

    # -- iterative Tarjan --------------------------------------------------

    def _tarjan_scc(
        self, states: set[str], adj: dict[str, list[str]]
    ) -> list[set[str]]:
        """
        Iterative Tarjan's SCC algorithm (avoids Python recursion limit).

        Parameters:
            states: The full vertex set.
            adj:    Forward adjacency for the tau-subgraph.

        Returns:
            List of SCCs (each a ``set[str]``).
        """
        index_counter = [0]
        stack: list[str] = []
        on_stack: set[str] = set()
        index_map: dict[str, int] = {}
        lowlink: dict[str, int] = {}
        sccs: list[set[str]] = []

        # Explicit DFS call-stack frames: (node, neighbor_iterator, phase)
        ENTER = 0
        RESUME = 1

        for root in states:
            if root in index_map:
                continue

            call_stack: list[tuple[str, int, list[str], int]] = [
                (root, ENTER, list(adj.get(root, [])), 0)
            ]

            while call_stack:
                node, phase, neighbors, ni = call_stack[-1]

                if phase == ENTER:
                    index_map[node] = index_counter[0]
                    lowlink[node] = index_counter[0]
                    index_counter[0] += 1
                    stack.append(node)
                    on_stack.add(node)
                    # move to RESUME to iterate neighbors
                    call_stack[-1] = (node, RESUME, neighbors, 0)
                    continue

                # phase == RESUME
                if ni < len(neighbors):
                    w = neighbors[ni]
                    call_stack[-1] = (node, RESUME, neighbors, ni + 1)

                    if w not in index_map:
                        # "recurse" into w
                        call_stack.append(
                            (w, ENTER, list(adj.get(w, [])), 0)
                        )
                    elif w in on_stack:
                        lowlink[node] = min(lowlink[node], index_map[w])
                else:
                    # All neighbors processed — post-order work
                    if lowlink[node] == index_map[node]:
                        component: set[str] = set()
                        while True:
                            w = stack.pop()
                            on_stack.discard(w)
                            component.add(w)
                            if w == node:
                                break
                        sccs.append(component)

                    call_stack.pop()
                    if call_stack:
                        parent_node = call_stack[-1][0]
                        lowlink[parent_node] = min(
                            lowlink[parent_node], lowlink[node]
                        )

        return sccs

    # -- divergence identification -----------------------------------------

    def _identify_divergent_sccs(
        self,
        sccs: list[set[str]],
        adj: dict[str, list[str]],
    ) -> tuple[set[str], list[set[str]]]:
        """
        An SCC is divergent iff:
        * ``|SCC| > 1``, **or**
        * it contains a self-loop in the tau-adjacency.
        """
        divergent_states: set[str] = set()
        divergent_sccs: list[set[str]] = []

        for scc in sccs:
            is_div = False
            if len(scc) > 1:
                is_div = True
            else:
                # Check for self-loop
                (single,) = scc
                if single in adj.get(single, []):
                    is_div = True

            if is_div:
                divergent_sccs.append(scc)
                divergent_states.update(scc)

        logger.debug(
            "Identified %d divergent SCCs out of %d total.",
            len(divergent_sccs),
            len(sccs),
        )
        return divergent_states, divergent_sccs

    # -- backward divergence propagation -----------------------------------

    def _propagate_divergence(
        self,
        divergent_states: set[str],
        reverse_adj: dict[str, list[str]],
        all_states: set[str],
    ) -> set[str]:
        """
        BFS backwards through the reverse tau-adjacency to propagate
        divergence: any state that can *reach* a divergent SCC via
        tau-transitions is itself divergent.
        """
        visited = set(divergent_states)
        queue = deque(divergent_states)

        while queue:
            u = queue.popleft()
            for v in reverse_adj.get(u, []):
                if v not in visited:
                    visited.add(v)
                    queue.append(v)

        new_count = len(visited) - len(divergent_states)
        if new_count:
            logger.debug(
                "Propagated divergence to %d additional states.", new_count
            )
        return visited

    # -- naive partition refinement ----------------------------------------

    def _naive_partition_refinement(
        self,
        lts: "LTS",
        divergent_states: set[str],
    ) -> tuple[dict[str, int], dict[int, set[str]]]:
        """
        O(n²) naive partition refinement for stuttering equivalence.

        Initial partition groups states by:
            (is_divergent, frozenset of observable outgoing labels)

        Refinement iterates until fixpoint, using signatures:
            (current_block, tau-reachable blocks, observable (label, target_block) pairs)
        """
        all_states = list(lts.states.keys())
        if not all_states:
            return {}, {}

        # Build per-state outgoing info
        obs_out: dict[str, set[str]] = {s: set() for s in all_states}
        tau_out: dict[str, list[str]] = {s: [] for s in all_states}
        obs_edges: dict[str, list[tuple[str, str]]] = {s: [] for s in all_states}

        for src, tgt, lbl in lts.transitions:
            if lbl in ("tau", "true"):
                tau_out.setdefault(src, []).append(tgt)
            else:
                obs_out.setdefault(src, set()).add(lbl)
                obs_edges.setdefault(src, []).append((lbl, tgt))

        # --- Initial partition ---
        sig_to_block: dict[tuple[bool, frozenset[str]], int] = {}
        state_to_block: dict[str, int] = {}
        next_block_id = 0

        for s in all_states:
            is_div = s in divergent_states
            sig = (is_div, frozenset(obs_out.get(s, set())))
            if sig not in sig_to_block:
                sig_to_block[sig] = next_block_id
                next_block_id += 1
            state_to_block[s] = sig_to_block[sig]

        # --- Refinement loop ---
        max_iterations = len(all_states) ** 2  # safety bound
        for iteration in range(max_iterations):
            new_block_map: dict[tuple, int] = {}
            new_state_to_block: dict[str, int] = {}
            new_id = 0

            for s in all_states:
                # Tau-reachable blocks
                tau_blocks = frozenset(
                    state_to_block[t]
                    for t in tau_out.get(s, [])
                    if t in state_to_block
                )
                # Observable edges → (label, target_block)
                obs_pairs = frozenset(
                    (lbl, state_to_block[t])
                    for lbl, t in obs_edges.get(s, [])
                    if t in state_to_block
                )

                refined_sig = (state_to_block[s], tau_blocks, obs_pairs)
                if refined_sig not in new_block_map:
                    new_block_map[refined_sig] = new_id
                    new_id += 1
                new_state_to_block[s] = new_block_map[refined_sig]

            if new_state_to_block == state_to_block:
                logger.debug(
                    "Partition refinement stabilised after %d iterations.",
                    iteration + 1,
                )
                break
            state_to_block = new_state_to_block
        else:
            logger.warning(
                "Partition refinement hit safety bound (%d iterations).",
                max_iterations,
            )

        # --- Invert to block → states ---
        block_to_states: dict[int, set[str]] = {}
        for s, b in state_to_block.items():
            block_to_states.setdefault(b, set()).add(s)

        logger.info(
            "Partition refinement result: %d equivalence classes for %d states.",
            len(block_to_states),
            len(all_states),
        )
        return state_to_block, block_to_states
