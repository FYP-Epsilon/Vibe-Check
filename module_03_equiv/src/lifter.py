"""
Phase A: Advanced Python Lifter
================================
Ingests WIR JSON payloads and produces Labeled Transition Systems (LTS)
as pure Python data structures. Implements:

  - Binary quality gate (aborts if guard_success_rate < confidence_threshold)
  - Bounded Loop State Duplication up to loop_max
  - loop_exceeds_bound_error trap state generation
  - Nested FSM traversal via the 'functions' block
  - Distinct fallback mapping for unresolved/failed extractions to prevent tau-absorption
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class QualityGateError(Exception):
    """Raised when the WIR certificate fails the binary quality gate."""
    pass


# ---------------------------------------------------------------------------
# LTS data structure
# ---------------------------------------------------------------------------

class LTS:
    """
    Labeled Transition System — the core data structure exchanged between
    all four phases of the equivalence-checking pipeline.

    Attributes:
        name:                 Human-readable identifier (e.g. function name).
        states:               Mapping state_id → metadata dict.
        transitions:          List of (source, target, label) triples.
        initial_state:        The entry state identifier.
        exit_states:          Set of terminal state identifiers.
        atomic_propositions:  Observable labels (excludes 'tau' and 'true').
    """

    def __init__(self, name: str = "unnamed") -> None:
        self.name: str = name
        self.states: dict[str, dict[str, Any]] = {}
        self.transitions: list[tuple[str, str, str]] = []
        self.initial_state: str = ""
        self.exit_states: set[str] = set()
        self.atomic_propositions: set[str] = set()

    # -- query helpers -----------------------------------------------------

    def num_states(self) -> int:
        """Return the number of states."""
        return len(self.states)

    def num_transitions(self) -> int:
        """Return the number of transitions."""
        return len(self.transitions)

    def successors(self, state_id: str) -> list[tuple[str, str]]:
        """Return list of (target, label) for outgoing transitions of *state_id*."""
        return [
            (tgt, lbl) for src, tgt, lbl in self.transitions if src == state_id
        ]

    def cyclomatic_complexity(self) -> int:
        """
        McCabe cyclomatic complexity  M = E − N + 2P
        where E = edges, N = nodes, P = connected components (assumed 1).
        """
        e = self.num_transitions()
        n = self.num_states()
        p = 1  # single connected component assumption
        return e - n + 2 * p

    def __repr__(self) -> str:
        return (
            f"LTS(name={self.name!r}, states={self.num_states()}, "
            f"transitions={self.num_transitions()}, "
            f"initial={self.initial_state!r})"
        )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class LifterConfig:
    """Tuneable parameters for the WIR lifter."""
    confidence_threshold: float = 0.95
    loop_max: int = 3
    abort_on_low_confidence: bool = True


# ---------------------------------------------------------------------------
# WIRLifter
# ---------------------------------------------------------------------------

class WIRLifter:
    """
    Transforms a WIR JSON payload into one or more :class:`LTS` objects.

    Processing pipeline per invocation of :meth:`lift`:

    1. **Quality Gate** — validate the ``certificate`` block.
    2. **Top-level lift** — convert the root nodes/edges into an LTS.
    3. **Nested functions** — iterate ``functions`` and lift each sub-FSM.
    4. **Loop unrolling** — bounded state duplication for ``loop`` nodes.
    """

    def __init__(self, config: LifterConfig | None = None) -> None:
        self.config = config or LifterConfig()

    # -- public API --------------------------------------------------------

    def lift(self, wir_json: dict) -> list[LTS]:
        """
        Main entry point.

        Parameters:
            wir_json: Parsed WIR JSON dictionary.

        Returns:
            A list of LTS objects (top-level + one per nested function).

        Raises:
            QualityGateError: If the certificate fails validation.
        """
        self._check_quality_gate(wir_json)

        results: list[LTS] = []

        # --- top-level WIR ---
        if wir_json.get("nodes"):
            top_lts = self._lift_single(wir_json, name="__top_level__")
            results.append(top_lts)
            logger.info(
                "Lifted top-level LTS: %d states, %d transitions",
                top_lts.num_states(),
                top_lts.num_transitions(),
            )

        # --- nested functions ---
        for fn_name, fn_fragment in wir_json.get("functions", {}).items():
            fn_lts = self._lift_single(fn_fragment, name=fn_name)
            results.append(fn_lts)
            logger.info(
                "Lifted function '%s': %d states, %d transitions",
                fn_name,
                fn_lts.num_states(),
                fn_lts.num_transitions(),
            )

        if not results:
            logger.warning("WIR payload contained no liftable fragments.")

        return results

    # -- quality gate ------------------------------------------------------

    def _check_quality_gate(self, wir_json: dict) -> None:
        """
        Binary quality gate based on the WIR ``certificate`` block.

        Aborts (raises) when:
        * ``certificate.abort`` is ``True``, **or**
        * ``guard_success_rate`` < ``confidence_threshold``
          (and ``abort_on_low_confidence`` is enabled).
        """
        cert = wir_json.get("certificate", {})

        if cert.get("abort", False):
            msg = cert.get("message", "Certificate abort flag is set.")
            logger.error("Quality-gate ABORT: %s", msg)
            raise QualityGateError(f"Certificate abort: {msg}")

        confidence = cert.get("guard_success_rate", 0.0)
        threshold = self.config.confidence_threshold

        if confidence < threshold:
            detail = (
                f"guard_success_rate={confidence:.4f} < "
                f"threshold={threshold:.4f}"
            )
            if self.config.abort_on_low_confidence:
                logger.error("Quality-gate REJECT: %s", detail)
                raise QualityGateError(f"Low confidence — {detail}")
            else:
                logger.warning(
                    "Quality-gate WARNING (non-fatal): %s", detail
                )
        else:
            logger.info(
                "Quality-gate PASS: confidence=%.4f ≥ %.4f",
                confidence,
                threshold,
            )

    # -- single-fragment lifting -------------------------------------------

    def _lift_single(self, wir_fragment: dict, name: str) -> LTS:
        """Convert one WIR fragment (top-level or function) into an LTS."""
        lts = LTS(name=name)

        nodes: list[dict] = wir_fragment.get("nodes", [])
        edges: list[dict] = wir_fragment.get("edges", [])

        # 1. Build states
        nodes_by_id = self._create_states(nodes, lts)

        # 2. Set entry / exit
        entry = wir_fragment.get("entry_node", "")
        exit_node = wir_fragment.get("exit_node", "")

        if entry and entry in lts.states:
            lts.initial_state = entry
        elif lts.states:
            # Fallback: first node
            lts.initial_state = next(iter(lts.states))
            logger.warning(
                "No explicit entry_node; defaulting to '%s'",
                lts.initial_state,
            )

        if exit_node and exit_node in lts.states:
            lts.exit_states.add(exit_node)

        # Also mark any node whose type is 'exit'
        for sid, meta in lts.states.items():
            if meta.get("type") == "exit":
                lts.exit_states.add(sid)

        # 3. Build transitions
        self._create_transitions(edges, nodes_by_id, lts)

        # 4. Loop unrolling (bounded state duplication)
        self._apply_loop_unrolling(lts, nodes)

        return lts

    # -- state creation ----------------------------------------------------

    def _create_states(
        self, nodes: list[dict], lts: LTS
    ) -> dict[str, dict]:
        """
        Populate ``lts.states`` from the raw node list.

        Returns:
            nodes_by_id — convenience mapping for edge processing.
        """
        nodes_by_id: dict[str, dict] = {}

        for node in nodes:
            if isinstance(node, str):
                sid = node
                meta: dict[str, Any] = {"type": "block"}
            else:
                sid = node["id"]
                meta = {
                    "type": node.get("type", "block"),
                    "guard": node.get("guard"),
                    "ast_type": node.get("ast_type"),
                    "line": node.get("line"),
                    "code": node.get("code"),
                }

            lts.states[sid] = meta
            nodes_by_id[sid] = meta

        return nodes_by_id

    # -- transition creation -----------------------------------------------

    def _create_transitions(
        self,
        edges: list[dict],
        nodes_by_id: dict[str, dict],
        lts: LTS,
    ) -> None:
        """
        Convert WIR edges into LTS transitions.

        Guard mapping rules:
        * ``None`` / empty string → ``'tau'`` (silent)
        * Unresolvable / failed extraction → ``'unknown_unresolved_guard'`` (observable)
        * Otherwise → literal guard string (observable label)
        """
        for edge in edges:
            src = edge.get("source") or edge.get("src", "")
            tgt = edge.get("target") or edge.get("dst", "")

            if src not in lts.states or tgt not in lts.states:
                logger.warning(
                    "Edge (%s → %s) references unknown state; skipping.",
                    src, tgt,
                )
                continue

            raw_guard = edge.get("guard") or edge.get("condition")

            if raw_guard is None or raw_guard == "":
                label = "tau"
            else:
                label = self._resolve_guard(str(raw_guard))

            lts.transitions.append((src, tgt, label))

            if label not in ("tau", "true"):
                lts.atomic_propositions.add(label)

    def _resolve_guard(self, guard_str: str) -> str:
        """
        Attempt to resolve a raw guard string.

        If the guard is a recognisable boolean expression or loop
        iterator, return it as-is. If resolution fails (e.g. the
        string is garbled or extraction flagged a failure), fall back
        to an observable unique label identifier to prevent unintended 
        tau-stuttering absorption during partition refinement.
        """
        if not guard_str or guard_str.strip() == "":
            return "tau"

        guard_stripped = guard_str.strip()

        # Known safe patterns
        safe_prefixes = (
            "iter ", "not ", "len(", "is_", "has_",
        )
        safe_operators = ("==", "!=", "<", ">", "<=", ">=", " in ", " and ", " or ")

        # Accept any guard that contains operators or known prefixes
        for prefix in safe_prefixes:
            if guard_stripped.startswith(prefix):
                return guard_stripped
        for op in safe_operators:
            if op in guard_stripped:
                return guard_stripped

        # Accept simple identifiers (e.g. variable names used as boolean flags)
        if guard_stripped.isidentifier():
            return guard_stripped

        # Fallback: Force unresolvable to an observable label to prevent silent absorption
        logger.warning(
            "Guard '%s' unresolvable; fallback to observable distinct label.",
            guard_stripped,
        )
        return "unknown_unresolved_guard"

    # -- bounded loop state duplication ------------------------------------

    def _apply_loop_unrolling(self, lts: LTS, nodes: list[dict]) -> None:
        """
        Perform Bounded Loop State Duplication for every ``loop``-type node.
        """
        loop_nodes = [
            n for n in nodes
            if isinstance(n, dict) and n.get("type") == "loop"
        ]

        if not loop_nodes:
            return

        loop_max = self.config.loop_max

        for loop_node in loop_nodes:
            loop_id: str = loop_node["id"]
            guard = loop_node.get("guard", "true")

            # --- 1. Identify the genuine Loop Body Nodes via Reachability ---
            loop_body_nodes = set()
            frontier = [tgt for src, tgt, _ in lts.transitions if src == loop_id and tgt != loop_id]
            
            while frontier:
                current = frontier.pop(0)
                if current not in loop_body_nodes and current != loop_id:
                    loop_body_nodes.add(current)
                    successors = [tgt for src, tgt, _ in lts.transitions if src == current]
                    frontier.extend(successors)

            # --- 2. Classify Edges Accurately ---
            back_edges: list[tuple[str, str, str]] = []
            entry_edges: list[tuple[str, str, str]] = []
            forward_edges: list[tuple[str, str, str]] = []
            other_edges: list[tuple[str, str, str]] = []

            for src, tgt, lbl in lts.transitions:
                if tgt == loop_id:
                    if src in loop_body_nodes:
                        back_edges.append((src, tgt, lbl))
                    else:
                        entry_edges.append((src, tgt, lbl))
                elif src == loop_id:
                    forward_edges.append((src, tgt, lbl))
                else:
                    other_edges.append((src, tgt, lbl))

            if not back_edges and not forward_edges:
                logger.debug(
                    "Loop node '%s' has no recognisable body; skipping unrolling.",
                    loop_id,
                )
                continue

            # --- 3. Duplicate iterations ---
            new_transitions: list[tuple[str, str, str]] = list(other_edges)

            for k in range(loop_max):
                iter_id = f"{loop_id}_iter_{k}"
                lts.states[iter_id] = {
                    "type": "loop_iteration",
                    "guard": guard,
                    "iteration": k,
                    "original_loop": loop_id,
                }

                if k == 0:
                    for s, _t, l in entry_edges:
                        new_transitions.append((s, iter_id, l))
                    for _s, t, l in forward_edges:
                        new_transitions.append((iter_id, t, l))
                else:
                    prev_iter_id = f"{loop_id}_iter_{k - 1}"
                    for s, _t, l in back_edges:
                        src_mapped = s.replace(loop_id, prev_iter_id) if s == loop_id else s
                        new_transitions.append((src_mapped, iter_id, l))
                    for _s, t, l in forward_edges:
                        new_transitions.append((iter_id, t, l))

            # --- 4. Trap state for overflow ---
            trap_id = f"{loop_id}_loop_exceeds_bound_error"
            lts.states[trap_id] = {
                "type": "error",
                "error_kind": "loop_exceeds_bound_error",
                "original_loop": loop_id,
            }

            last_iter = f"{loop_id}_iter_{loop_max - 1}"
            for s, _t, l in back_edges:
                src_mapped = s.replace(loop_id, last_iter) if s == loop_id else s
                new_transitions.append((src_mapped, trap_id, l))

            lts.states.pop(loop_id, None)
            lts.transitions = new_transitions

            logger.info(
                "Unrolled loop '%s': %d iterations + trap state '%s'.",
                loop_id,
                loop_max,
                trap_id,
            )