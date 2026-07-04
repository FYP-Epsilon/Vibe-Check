"""concolic.py -- bounded concolic engine (BoundedConcolicEngine).

(Auto-extracted verbatim from the original monolith during modularization.)
"""

from __future__ import annotations

import copy
import inspect
import sys
from typing import Any, Optional
import z3
try:
    from .ast_extractor import CFGExtractor, _unparse
except ImportError:
    from ast_extractor import CFGExtractor, _unparse
from .tracer import BranchRecord, WIRSymbolicTracer
from .registry import Z3VariableRegistry
from .safe_exec import SAFE_BUILTINS


class BoundedConcolicEngine:
    """
    Bounded concolic execution engine.

    Iteratively executes a target function with concrete inputs,
    records the symbolic path condition, queries Z3 for alternative
    inputs that explore unexplored branches, and applies k-bounding
    and QCE state merging to control path explosion.
    """

    def __init__(
        self,
        source: str,
        function_name: str,
        max_k: int = 3,
        query_budget: int = 500,
        timeout_ms: int = 5000,
        compiled_ns: Optional[dict[str, Any]] = None,
    ) -> None:
        self.source = source
        self.function_name = function_name
        self.max_k = max_k
        self.query_budget = query_budget
        self.timeout_ms = timeout_ms

        # Compile the source once so we can call the target function.
        if compiled_ns is not None:
            self._compiled_ns = compiled_ns
        else:
            self._compiled_ns: dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
            exec(compile(self.source, "<string>", "exec"), self._compiled_ns)

        # Pre-extract the WIR (Phase 1) for symbolic tracing.
        self.wir = CFGExtractor().extract(self.source)

        # Build a comprehensive node map that includes top-level nodes AND
        # every node inside function sub-CFGs.  This is required for QCE
        # and reachability analysis to see into function bodies.
        self._node_map: dict[str, dict[str, Any]] = {
            n["id"]: n for n in self.wir.get("nodes", [])
        }
        for func_wir in self.wir.get("functions", {}).values():
            for n in func_wir.get("nodes", []):
                self._node_map[n["id"]] = n

        # Shared Z3 registry across all concolic iterations so that path
        # conditions refer to the same constant objects.
        self.registry = Z3VariableRegistry()

        # Exploration bookkeeping.
        self.explored_path_conditions: list[z3.BoolRef] = []
        self.covered_edges: set[tuple[str, str]] = set()
        self.state_pool: dict[str, list[tuple[dict[str, Any], dict[str, z3.ExprRef]]]] = {}

        # Persistent solver for incremental solving.  Blocking clauses
        # (Not(explored_pc)) are monotonic across iterations, so we assert them
        # once on a reused solver instead of rebuilding the whole constraint set
        # every solve.  See _solve_for_inputs.
        self._solver = z3.Solver()
        self._solver.set("timeout", self.timeout_ms)
        self._blocked_count = 0

        # Statistics for P2.4 confidence.
        self.feasible_paths = 0
        self.total_paths = 0
        self.timeouts = 0
        self.solver_successes = 0
        self.iteration = 0
        self.input_mismatch_count = 0

    # -- public API ------------------------------------------------------

    def run(self, initial_inputs: dict[str, Any]) -> dict[str, Any]:
        """
        Run the bounded concolic loop starting from *initial_inputs*.

        Returns a V2 certificate dictionary.
        """
        inputs = copy.deepcopy(initial_inputs)

        while self.iteration < self.query_budget:
            next_inputs = self._concolic_iteration(inputs)
            if next_inputs is None:
                break
            inputs = next_inputs
            self.iteration += 1

            cert = self._emit_certificate()
            # Require a minimum number of iterations before declaring victory
            # so that we don't stop after the very first feasible path.
            if cert["confidence"] >= 0.95 and self.iteration >= 3:
                return cert
            if cert["confidence"] < 0.80 and self.iteration >= 50:
                # Early stall detection: after 50 iterations if confidence
                # is still below 0.80 we flag V1 fallback.
                cert["trigger_v1"] = True
                return cert

        cert = self._emit_certificate()
        if self.iteration == 0 and self.input_mismatch_count > 0:
            func = self._compiled_ns[self.function_name]
            sig = inspect.signature(func)
            has_container = False
            for param in sig.parameters.values():
                ann = param.annotation
                origin = getattr(ann, "__origin__", None)
                if ann is list or ann is dict or origin is list or origin is dict:
                    has_container = True
                    break
            if has_container:
                cert["confidence"] = 0.0
                cert["trigger_v1"] = True
                cert["message"] = "V2 skipped: uninterpreted container types"
        return cert

    def _concolic_iteration(
        self, inputs: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """
        One full concolic iteration:
        concrete execution -> symbolic trace -> solver query -> new inputs.
        """
        # 1. Concrete execution.
        try:
            concrete_result = self._execute_concrete(inputs)
        except (TypeError, KeyError, IndexError, AttributeError, ZeroDivisionError,
                 NameError, ValueError, RecursionError):
            self.input_mismatch_count += 1
            return None

        # 2. Symbolic trace (reuses the engine's persistent registry).
        tracer = WIRSymbolicTracer(
            self.wir,
            self.registry,
            inputs,
            function_name=self.function_name,
            max_k=self.max_k,
        )
        path_condition, branches = tracer.trace()

        # Record coverage.
        for b in branches:
            edge = (b.node_id, str(b.taken))
            self.covered_edges.add(edge)

        # 3. Store the explored path condition.
        self.explored_path_conditions.append(path_condition)
        self.total_paths += 1

        # 4. Try to find a new path by negating the last *taken* branch.
        new_pc = self._negate_last_branch(path_condition, branches)
        if new_pc is None:
            return None

        # 5. Solve for new inputs.
        new_inputs = self._solve_for_inputs(new_pc, inputs)
        if new_inputs is not None:
            self.feasible_paths += 1
            self.solver_successes += 1
        return new_inputs

    # -- concrete execution ----------------------------------------------

    def _execute_concrete(self, inputs: dict[str, Any]) -> Any:
        func = self._compiled_ns[self.function_name]
        max_concrete_steps = 2000
        target_file = "<string>"
        step_count = 0

        def _on_line(code: Any, line_number: int) -> Any:
            nonlocal step_count
            if code.co_filename == target_file:
                step_count += 1
                if step_count > max_concrete_steps:
                    raise RuntimeError(
                        f"Concrete execution exceeded {max_concrete_steps} steps — possible infinite loop."
                    )
            # Never return DISABLE: every execution of every line must be counted
            # so runaway loops are still detected.
            return None

        # PEP 669 sys.monitoring is ~orders of magnitude cheaper than settrace
        # for this counter (no per-line frame materialisation).  Fall back to
        # settrace on Python < 3.12 or if all monitoring tool ids are taken.
        mon = getattr(sys, "monitoring", None)
        tool_id = self._acquire_monitoring_tool_id(mon) if mon is not None else None
        if tool_id is None:
            return self._execute_concrete_settrace(
                func, inputs, target_file, max_concrete_steps
            )

        try:
            mon.register_callback(tool_id, mon.events.LINE, _on_line)
            mon.set_events(tool_id, mon.events.LINE)
            try:
                return func(**copy.deepcopy(inputs))
            finally:
                mon.set_events(tool_id, mon.events.NO_EVENTS)
                mon.register_callback(tool_id, mon.events.LINE, None)
        finally:
            mon.free_tool_id(tool_id)

    @staticmethod
    def _acquire_monitoring_tool_id(mon: Any) -> Optional[int]:
        """Reserve a free ``sys.monitoring`` tool id (0–5), or None if none free."""
        for tid in range(6):
            if mon.get_tool(tid) is None:
                try:
                    mon.use_tool_id(tid, "vibecheck.concrete_guard")
                    return tid
                except ValueError:
                    continue
        return None

    def _execute_concrete_settrace(
        self,
        func: Any,
        inputs: dict[str, Any],
        target_file: str,
        max_concrete_steps: int,
    ) -> Any:
        """``sys.settrace`` fallback step-counter (Python < 3.12 / tool ids busy)."""
        concrete_step_count = 0

        def concrete_guard(frame: Any, event: str, arg: Any) -> Any:
            nonlocal concrete_step_count
            if event == "line" and frame.f_code.co_filename == target_file:
                concrete_step_count += 1
                if concrete_step_count > max_concrete_steps:
                    raise RuntimeError(
                        f"Concrete execution exceeded {max_concrete_steps} steps — possible infinite loop."
                    )
            return concrete_guard

        old_trace = sys.gettrace()
        sys.settrace(concrete_guard)
        try:
            return func(**copy.deepcopy(inputs))
        finally:
            sys.settrace(old_trace)

    # -- path manipulation -----------------------------------------------

    @staticmethod
    def _negate_last_branch(
        path_condition: z3.BoolRef,
        branches: list[BranchRecord],
    ) -> Optional[z3.BoolRef]:
        """
        Create a new path condition by negating the last branch decision,
        while keeping all earlier conditions unchanged.

        Works for both *taken* and *not-taken* branches so that paths
        where every guard evaluated to False can still be negated.
        """
        if not branches:
            return None

        # Walk backwards and negate the first branch we encounter.
        for idx in range(len(branches) - 1, -1, -1):
            b = branches[idx]
            parts: list[z3.BoolRef] = []
            for earlier in branches[:idx]:
                parts.append(
                    earlier.symbolic_guard if earlier.taken else z3.Not(earlier.symbolic_guard)
                )
            # Negate the current branch decision.
            parts.append(
                z3.Not(b.symbolic_guard) if b.taken else b.symbolic_guard
            )
            if len(parts) == 1:
                return parts[0]
            return z3.And(*parts)

        return None

    def _solve_for_inputs(
        self,
        path_condition: z3.BoolRef,
        template: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """
        Query Z3 for a model that satisfies *path_condition*.

        Extract concrete values for every key in *template*.
        """
        solver = self._solver

        # Blocking clauses Not(explored_pc) are monotonic across iterations, so
        # assert only the ones discovered since the previous solve and keep them
        # permanently.  This makes the run O(n) in total assertions rather than
        # rebuilding all n blocking clauses on every iteration (O(n^2)).
        explored = self.explored_path_conditions
        while self._blocked_count < len(explored):
            solver.add(z3.Not(explored[self._blocked_count]))
            self._blocked_count += 1

        # The query for this iteration (path_condition) is transient: assert it
        # inside a push/pop scope so it does not pollute subsequent solves.
        solver.push()
        try:
            solver.add(path_condition)
            result = solver.check()

            if result == z3.unknown:
                self.timeouts += 1
                return None
            if result == z3.unsat:
                return None

            model = solver.model()
            new_inputs: dict[str, Any] = {}

            for key, original_value in template.items():
                z3_expr = None
                # Try to find the variable in the model by name.
                for decl in model.decls():
                    if decl.name() == key:
                        z3_expr = model[decl]
                        break

                if z3_expr is None:
                    # Variable was unconstrained -- keep original.
                    new_inputs[key] = original_value
                    continue

                # Convert Z3 value back to Python.
                val = self._z3_to_python(z3_expr, type(original_value))
                new_inputs[key] = val

            return new_inputs
        finally:
            solver.pop()

    @staticmethod
    def _z3_to_python(z3_val: Any, py_type: type) -> Any:
        """Best-effort conversion from a Z3 model value to a Python value."""
        if hasattr(z3_val, "as_long"):
            v = z3_val.as_long()
            if py_type == bool:
                return bool(v)
            if py_type == float:
                return float(v)
            return v
        if hasattr(z3_val, "as_fraction"):
            v = float(z3_val.as_fraction())
            if py_type == int:
                return int(v)
            return v
        if z3.is_true(z3_val):
            return True
        if z3.is_false(z3_val):
            return False
        # Fallback -- return the raw Z3 value and hope the caller handles it.
        return z3_val

    # -- QCE state merging (Layer 2) -------------------------------------

    def qce_predicts_savings(
        self,
        node_id: str,
        state_a: dict[str, z3.ExprRef],
        state_b: dict[str, z3.ExprRef],
    ) -> bool:
        """
        Query Count Estimation heuristic.

        Returns *True* (merge is profitable) when the variables that
        differ between *state_a* and *state_b* are **cold** -- i.e.
        they do not appear in any branch condition reachable from
        *node_id*.
        """
        differing = {k for k in state_a if k in state_b and state_a[k] is not state_b[k]}
        differing |= {k for k in state_b if k not in state_a}
        differing |= {k for k in state_a if k not in state_b}

        if not differing:
            return True  # identical states -- merging is free.

        # Collect all control variables in successor gateways.
        future_control_vars: set[str] = set()
        reachable = self._reachable_from(node_id)
        for nid in reachable:
            n = self._node_map.get(nid, {})
            if n.get("type") == "gateway":
                future_control_vars.update(n.get("control_vars", []))

        # If no differing variable is used in future branches, merge.
        return differing.isdisjoint(future_control_vars)

    def merge_states(
        self,
        guard: z3.BoolRef,
        state_a: dict[str, z3.ExprRef],
        state_b: dict[str, z3.ExprRef],
    ) -> dict[str, z3.ExprRef]:
        """
        Merge two symbolic states into one using ITE chains.

        For every differing variable ``v``:
            ``v_merged = ITE(guard, state_a[v], state_b[v])``
        """
        merged: dict[str, z3.ExprRef] = {}
        all_keys = set(state_a) | set(state_b)
        for k in all_keys:
            va = state_a.get(k)
            vb = state_b.get(k)
            if va is None:
                merged[k] = vb
            elif vb is None:
                merged[k] = va
            elif va.eq(vb):
                merged[k] = va
            else:
                merged[k] = z3.If(guard, va, vb)
        return merged

    def _reachable_from(self, node_id: str) -> set[str]:
        """BFS over the WIR graph starting at *node_id*."""
        reachable: set[str] = set()
        frontier = [node_id]
        while frontier:
            nid = frontier.pop()
            if nid in reachable:
                continue
            reachable.add(nid)
            n = self._node_map.get(nid, {})
            for succ in n.get("successors", []):
                frontier.append(succ)
        return reachable

    # -- P2.4 certificate ------------------------------------------------

    def _emit_certificate(self) -> dict[str, Any]:
        """Build the V2 confidence certificate."""
        feasible = self.feasible_paths
        total = max(self.total_paths, 1)
        timeout_rate = self.timeouts / max(self.iteration, 1)
        solver_rate = self.solver_successes / max(self.iteration, 1)

        confidence = (feasible / total) * (1 - timeout_rate) * solver_rate

        # Branch diversity check
        total_gateways = sum(
            1 for n in self._node_map.values() if n.get("type") == "gateway"
        )
        diverse_gateways = 0
        for node_id, n in self._node_map.items():
            if n.get("type") == "gateway":
                has_true = (node_id, "True") in self.covered_edges
                has_false = (node_id, "False") in self.covered_edges
                if has_true and has_false:
                    diverse_gateways += 1

        branch_diversity_score = (
            diverse_gateways / total_gateways if total_gateways > 0 else 1.0
        )

        if confidence > 0 and total_gateways > 0 and branch_diversity_score < 0.5:
            confidence = min(confidence, 0.80)
            message = "V2 symbolic refinement in progress: insufficient branch diversity."
        elif confidence >= 0.95:
            message = "V2 symbolic refinement complete."
        else:
            message = "V2 symbolic refinement in progress or stalled."

        total_branches_explored = len(self.covered_edges)
        if total_branches_explored < 2 and confidence > 0.80:
            confidence = min(confidence, 0.75)
            message = "V2 symbolic refinement incomplete: fewer than 2 branches explored."

        return {
            "version": "V2",
            "confidence": confidence,
            "iterations": self.iteration,
            "feasible_paths": feasible,
            "total_paths": total,
            "timeout_rate": timeout_rate,
            "solver_success_rate": solver_rate,
            "covered_edges": len(self.covered_edges),
            "branch_diversity_score": branch_diversity_score,
            "total_branches_explored": total_branches_explored,
            "input_mismatch_count": self.input_mismatch_count,
            "trigger_v1": False,
            "message": message,
        }
