"""
Phase D: Finite-Trace Reachability Model Checker
==================================================
Interleaves the Representative Automaton and the Negated Property
Monitor using on-the-fly product construction.  Uses BFS graph
traversal to identify any violating states (Pass/Fail output).

Handles ``loop_exceeds_bound_error`` trap states as safety violations
during BFS traversal.

Pure Python — no external dependencies.
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
class VerificationVerdict:
    """Result of a model-checking run."""
    result: str = "PASS"                            # 'PASS' or 'FAIL'
    violating_states: list[str] = field(default_factory=list)
    counterexample_trace: list[str] = field(default_factory=list)
    loop_bound_violations: list[str] = field(default_factory=list)
    states_explored: int = 0
    message: str = ""


# ---------------------------------------------------------------------------
# Property Monitor factory
# ---------------------------------------------------------------------------

class PropertyMonitor:
    """
    Factory for constructing negated property monitor LTS instances.

    A *negated* property monitor accepts (reaches a violating state)
    exactly when the system violates the property of interest.
    """

    @classmethod
    def from_reachability(cls, forbidden_label: str) -> "LTS":
        """
        Create a 2-state monitor that detects reachability of
        *forbidden_label*.

        States:
            ``mon_ok``        — initial, non-violating, self-loops on
                                everything except *forbidden_label*.
            ``mon_violating`` — absorbing violation state.

        Transitions:
            ``mon_ok`` → ``mon_violating`` on *forbidden_label*
            ``mon_ok`` → ``mon_ok``        on everything else (tau, true, any other label)
            ``mon_violating`` → ``mon_violating`` on everything (absorbing)
        """
        from .lifter import LTS

        mon = LTS(name=f"monitor_reachability_{forbidden_label}")

        mon.states["mon_ok"] = {"type": "monitor", "violating": False}
        mon.states["mon_violating"] = {"type": "monitor", "violating": True}

        mon.initial_state = "mon_ok"

        # Transition on the forbidden label → violating
        mon.transitions.append(("mon_ok", "mon_violating", forbidden_label))
        # Self-loops (represented with a special 'tau' self-loop — the
        # product construction handles non-matching labels by keeping
        # the monitor in place)
        mon.transitions.append(("mon_ok", "mon_ok", "tau"))
        mon.transitions.append(("mon_violating", "mon_violating", "tau"))

        mon.atomic_propositions.add(forbidden_label)

        return mon

    @classmethod
    def from_loop_bound_check(cls) -> "LTS":
        """
        Create a structural monitor that watches for
        ``loop_exceeds_bound_error`` trap states.

        This is a *structural* check: the monitor itself is trivially
        accepting — the :class:`ModelChecker` inspects system-side
        state metadata during BFS to detect the trap states.

        The monitor LTS has a single state that self-loops on all labels.
        """
        from .lifter import LTS

        mon = LTS(name="monitor_loop_bound")

        mon.states["mon_ok"] = {"type": "monitor", "violating": False}
        mon.states["mon_violating"] = {"type": "monitor", "violating": True}

        mon.initial_state = "mon_ok"

        # Universal self-loops — the monitor never transitions on its
        # own.  The ModelChecker forces a transition to mon_violating
        # when it detects a system-side trap state.
        mon.transitions.append(("mon_ok", "mon_ok", "tau"))
        mon.transitions.append(("mon_violating", "mon_violating", "tau"))

        return mon


# ---------------------------------------------------------------------------
# Model Checker
# ---------------------------------------------------------------------------

class ModelChecker:
    """
    Finite-trace reachability model checker.

    Uses on-the-fly (lazy) product construction with BFS traversal.
    """

    def __init__(self) -> None:
        pass

    # -- public API --------------------------------------------------------

    def check(self, system: "LTS", monitor: "LTS") -> VerificationVerdict:
        """
        Model-check *system* against the negated property *monitor*.

        The product automaton is constructed on-the-fly during BFS.
        A violation is detected when:

        1. The monitor component reaches a state marked ``violating``, **or**
        2. The system component is a ``loop_exceeds_bound_error`` trap state.

        Returns:
            A :class:`VerificationVerdict` with pass/fail, counterexample
            trace, and loop-bound violation info.
        """
        is_loop_bound_monitor = monitor.name == "monitor_loop_bound"
        return self._bfs_product_check(system, monitor, is_loop_bound_monitor)

    def check_all_properties(
        self,
        system: "LTS",
        properties: list[tuple[str, "LTS"]],
    ) -> list[tuple[str, VerificationVerdict]]:
        """
        Check multiple named properties against *system*.

        Parameters:
            system:     The system LTS (representative automaton).
            properties: List of ``(property_name, monitor_lts)`` tuples.

        Returns:
            List of ``(property_name, verdict)`` tuples.
        """
        results: list[tuple[str, VerificationVerdict]] = []
        for prop_name, monitor in properties:
            logger.info("Checking property '%s' ...", prop_name)
            verdict = self.check(system, monitor)
            logger.info(
                "Property '%s': %s (%s)",
                prop_name,
                verdict.result,
                verdict.message,
            )
            results.append((prop_name, verdict))
        return results

    # -- on-the-fly BFS product check --------------------------------------

    def _bfs_product_check(
        self,
        system: "LTS",
        monitor: "LTS",
        is_loop_bound_monitor: bool,
    ) -> VerificationVerdict:
        """
        On-the-fly product construction with BFS.

        Product states are encoded as ``"sys_state||mon_state"`` strings.
        """
        # Pre-compute successor indices for the system and monitor
        sys_succ = self._index_successors(system)
        mon_succ = self._index_successors(monitor)

        # Identify violating monitor states
        mon_violating = {
            sid
            for sid, meta in monitor.states.items()
            if meta.get("violating", False)
        }

        # BFS state
        initial = f"{system.initial_state}||{monitor.initial_state}"
        visited: set[str] = {initial}
        parent: dict[str, str | None] = {initial: None}
        queue: deque[str] = deque([initial])

        violating_states: list[str] = []
        loop_bound_violations: list[str] = []
        first_violation: str | None = None
        states_explored = 0

        while queue:
            current = queue.popleft()
            states_explored += 1

            sys_s, mon_s = current.split("||", 1)

            # --- Check for violations at this product state ---

            # (a) Monitor violation (label-based)
            if mon_s in mon_violating:
                violating_states.append(current)
                if first_violation is None:
                    first_violation = current

            # (b) Structural loop-bound violation
            sys_meta = system.states.get(sys_s, {})
            if (
                sys_meta.get("type") == "error"
                or sys_s.endswith("_loop_exceeds_bound_error")
            ):
                loop_bound_violations.append(current)
                if is_loop_bound_monitor and first_violation is None:
                    first_violation = current
                    violating_states.append(current)
                # Trap state: no outgoing transitions → skip expansion
                continue

            # --- Expand successors ---
            for tgt_sys, lbl in sys_succ.get(sys_s, []):
                if lbl in ("tau", "true"):
                    # System-side silent: monitor stays
                    next_prod = f"{tgt_sys}||{mon_s}"
                    if next_prod not in visited:
                        visited.add(next_prod)
                        parent[next_prod] = current
                        queue.append(next_prod)
                else:
                    # Observable: synchronise with monitor
                    for tgt_mon, mon_lbl in mon_succ.get(mon_s, []):
                        if mon_lbl == lbl:
                            next_prod = f"{tgt_sys}||{tgt_mon}"
                            if next_prod not in visited:
                                visited.add(next_prod)
                                parent[next_prod] = current
                                queue.append(next_prod)
                    # If monitor has no matching transition, also allow
                    # the monitor to stay if it has a tau self-loop
                    # (default "don't care" semantics)
                    for tgt_mon, mon_lbl in mon_succ.get(mon_s, []):
                        if mon_lbl in ("tau", "true") and tgt_mon == mon_s:
                            next_prod = f"{tgt_sys}||{mon_s}"
                            if next_prod not in visited:
                                visited.add(next_prod)
                                parent[next_prod] = current
                                queue.append(next_prod)
                            break

        # --- Build verdict ---
        if first_violation is not None:
            trace = self._reconstruct_trace(parent, first_violation)
            return VerificationVerdict(
                result="FAIL",
                violating_states=violating_states,
                counterexample_trace=trace,
                loop_bound_violations=loop_bound_violations,
                states_explored=states_explored,
                message=self._build_fail_message(
                    violating_states, loop_bound_violations, trace
                ),
            )
        else:
            return VerificationVerdict(
                result="PASS",
                violating_states=[],
                counterexample_trace=[],
                loop_bound_violations=loop_bound_violations,
                states_explored=states_explored,
                message=(
                    f"No violations detected. "
                    f"Explored {states_explored} product states."
                    + (
                        f" (Note: {len(loop_bound_violations)} loop-bound "
                        f"trap states encountered but no property violation.)"
                        if loop_bound_violations
                        else ""
                    )
                ),
            )

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _index_successors(
        lts: "LTS",
    ) -> dict[str, list[tuple[str, str]]]:
        """Build a state → [(target, label)] index for fast successor lookup."""
        idx: dict[str, list[tuple[str, str]]] = {}
        for src, tgt, lbl in lts.transitions:
            idx.setdefault(src, []).append((tgt, lbl))
        return idx

    @staticmethod
    def _reconstruct_trace(
        parent: dict[str, str | None], target: str
    ) -> list[str]:
        """Backtrack through BFS parent pointers to build the trace."""
        trace: list[str] = []
        current: str | None = target
        while current is not None:
            trace.append(current)
            current = parent.get(current)
        trace.reverse()
        return trace

    @staticmethod
    def _build_fail_message(
        violating: list[str],
        loop_violations: list[str],
        trace: list[str],
    ) -> str:
        """Construct a human-readable failure explanation."""
        parts: list[str] = [f"FAIL — {len(violating)} violation(s) detected."]

        if trace:
            parts.append(f"Counterexample trace ({len(trace)} steps): " +
                         " → ".join(trace[:10]))
            if len(trace) > 10:
                parts.append(f"  … ({len(trace) - 10} more steps)")

        if loop_violations:
            parts.append(
                f"Loop-bound trap states reached: "
                f"{', '.join(loop_violations[:5])}"
            )

        return " | ".join(parts)
