"""tracer.py -- symbolic path tracer (BranchRecord, WIRSymbolicTracer).

(Auto-extracted verbatim from the original monolith during modularization.)
"""

from __future__ import annotations

import ast
import copy
from dataclasses import dataclass, field
from typing import Any, Optional
import z3
try:
    from ..ast_extractor import CFGExtractor, _unparse
except ImportError:
    from ast_extractor import CFGExtractor, _unparse
from .registry import Z3VariableRegistry
from .evaluator import SymbolicEvaluator
from .safe_exec import _safe_eval


@dataclass
class BranchRecord:
    """One branch decision recorded during symbolic tracing."""
    node_id: str
    guard_str: str
    taken: bool
    symbolic_guard: z3.BoolRef


class WIRSymbolicTracer:
    """
    Walk a WIR (produced by :class:`CFGExtractor`) following the same
    path as a concrete execution, building the symbolic path condition.
    """

    def __init__(
        self,
        wir: dict[str, Any],
        registry: Z3VariableRegistry,
        inputs: dict[str, Any],
        function_name: Optional[str] = None,
        max_k: int = 3,
    ) -> None:
        self.wir = wir
        self.registry = registry
        self.inputs = inputs
        self.function_name = function_name
        self.max_k = max_k

        # Concrete state evolves as we "execute" assignment blocks.
        self.concrete_state: dict[str, Any] = copy.deepcopy(inputs)
        # Symbolic state maps variable names to Z3 expressions.
        self.symbolic_state: dict[str, z3.ExprRef] = {}
        # Initialise symbolic inputs.
        for name, value in inputs.items():
            self.symbolic_state[name] = registry.declare(name, value)

        self.path_condition: z3.BoolRef = z3.BoolVal(True)
        self.branches: list[BranchRecord] = []
        self.loop_counters: dict[str, int] = {}
        self._for_iterators: dict[str, dict] = {}

        # Select the node map (function-level or module-level).
        if function_name and function_name in wir.get("functions", {}):
            func_wir = wir["functions"][function_name]
            self.nodes: dict[str, dict[str, Any]] = {n["id"]: n for n in func_wir["nodes"]}
            self.entry = func_wir["entry_node"]
            self.exit = func_wir["exit_node"]
        else:
            self.nodes = {n["id"]: n for n in wir["nodes"]}
            self.entry = wir["entry_node"]
            self.exit = wir["exit_node"]

    # -- public API ------------------------------------------------------

    def trace(self) -> tuple[z3.BoolRef, list[BranchRecord]]:
        """
        Follow the WIR graph and return ``(path_condition, branches)``.
        """
        current = self.entry
        steps = 0
        max_steps = 1000  # safety valve against infinite CFG traversal

        while current != self.exit and steps < max_steps:
            steps += 1
            node = self.nodes.get(current)
            if node is None:
                break

            handler = getattr(self, f"_handle_{node['type']}", self._handle_block)
            nxt = handler(node)
            if nxt is None:
                break
            current = nxt

        return self.path_condition, self.branches

    # -- node handlers ---------------------------------------------------

    def _handle_entry(self, node: dict[str, Any]) -> Optional[str]:
        return node["successors"][0] if node["successors"] else None

    def _handle_exit(self, node: dict[str, Any]) -> Optional[str]:
        return None

    def _handle_block(self, node: dict[str, Any]) -> Optional[str]:
        """Execute every statement in the block concretely and symbolically."""
        for stmt in node.get("code", []):
            self._exec_stmt(stmt)
        return node["successors"][0] if node["successors"] else None

    def _handle_task(self, node: dict[str, Any]) -> Optional[str]:
        return self._handle_block(node)

    def _handle_gateway(self, node: dict[str, Any]) -> Optional[str]:
        guard_str = node.get("guard", "True")
        concrete_val = self._eval_concrete(guard_str)
        symbolic_guard = self._eval_symbolic(guard_str)

        self.branches.append(
            BranchRecord(
                node_id=node["id"],
                guard_str=guard_str,
                taken=bool(concrete_val),
                symbolic_guard=symbolic_guard,
            )
        )

        if concrete_val:
            self.path_condition = z3.And(self.path_condition, symbolic_guard)
            return node["successors"][0] if len(node["successors"]) > 0 else None
        else:
            self.path_condition = z3.And(self.path_condition, z3.Not(symbolic_guard))
            return node["successors"][1] if len(node["successors"]) > 1 else None

    def _handle_loop(self, node: dict[str, Any]) -> Optional[str]:
        loop_id = node["id"]

        if node.get("guard", "").startswith("iter "):
            iterable_expr = node["guard"][5:].strip()
            if loop_id not in self._for_iterators:
                try:
                    iterable = _safe_eval(iterable_expr, self.concrete_state)
                except Exception:
                    iterable = []
                if not isinstance(iterable, (list, tuple)):
                    iterable = list(iterable)
                target_var = node.get("data_vars", [None])[0]
                self._for_iterators[loop_id] = {"iterable": iterable, "idx": 0, "target_var": target_var}
            it = self._for_iterators[loop_id]
            if it["idx"] < len(it["iterable"]):
                self.concrete_state[it["target_var"]] = it["iterable"][it["idx"]]
                self.symbolic_state[it["target_var"]] = self.registry.declare(it["target_var"], it["iterable"][it["idx"]])
                it["idx"] += 1
                self.branches.append(
                    BranchRecord(
                        node_id=loop_id,
                        guard_str=f"next({iterable_expr})",
                        taken=True,
                        symbolic_guard=z3.BoolVal(True),
                    )
                )
                return node["successors"][0]
            else:
                del self._for_iterators[loop_id]
                self.branches.append(
                    BranchRecord(
                        node_id=loop_id,
                        guard_str=f"next({iterable_expr})",
                        taken=False,
                        symbolic_guard=z3.BoolVal(False),
                    )
                )
                return node["successors"][1] if len(node.get("successors", [])) > 1 else node["successors"][0]

        iteration = self.loop_counters.get(loop_id, 0)

        if iteration >= self.max_k:
            # Havoc: replace loop-modified variables with fresh symbols.
            self._apply_havoc(node)
            self.loop_counters[loop_id] = iteration + 1
            # Exit the loop (second successor, if present, else first).
            return node["successors"][1] if len(node["successors"]) > 1 else node["successors"][0]

        guard_str = node.get("guard", "True")
        concrete_val = self._eval_concrete(guard_str)
        symbolic_guard = self._eval_symbolic(guard_str)

        self.branches.append(
            BranchRecord(
                node_id=loop_id,
                guard_str=guard_str,
                taken=bool(concrete_val),
                symbolic_guard=symbolic_guard,
            )
        )

        if concrete_val:
            self.path_condition = z3.And(self.path_condition, symbolic_guard)
            self.loop_counters[loop_id] = iteration + 1
            # Body is typically the first successor.
            return node["successors"][0]
        else:
            self.path_condition = z3.And(self.path_condition, z3.Not(symbolic_guard))
            # Exit loop.
            return node["successors"][1] if len(node["successors"]) > 1 else node["successors"][0]

    def _handle_break(self, node: dict[str, Any]) -> Optional[str]:
        # Break nodes link directly to the loop exit in the CFG.
        return node["successors"][0] if node["successors"] else None

    def _handle_continue(self, node: dict[str, Any]) -> Optional[str]:
        return node["successors"][0] if node["successors"] else None

    def _handle_return(self, node: dict[str, Any]) -> Optional[str]:
        # Return nodes usually have no successors in our CFG.
        return None

    # -- concrete / symbolic evaluation ----------------------------------

    def _eval_concrete(self, expr: str) -> Any:
        if expr.startswith("iter "):
            return True
        try:
            return _safe_eval(expr, self.concrete_state)
        except (NameError, KeyError):
            return False
        except Exception:
            # Concrete guard fallback: False on error to prevent fake path coverage.
            return False

    def _eval_symbolic(self, expr: str) -> z3.ExprRef:
        try:
            tree = ast.parse(expr, mode="eval")
            ev = SymbolicEvaluator(self.registry, self.symbolic_state, self.concrete_state)
            return ev.eval(tree.body)
        except (NotImplementedError, SyntaxError):
            # Symbolic guard fallback: False on error to prevent fake path coverage.
            return z3.BoolVal(False)
        except Exception:
            # Symbolic guard fallback: False on error to prevent fake path coverage.
            return z3.BoolVal(False)

    # -- statement execution ---------------------------------------------

    def _exec_stmt(self, stmt: str) -> None:
        """
        Execute a single statement string both concretely and symbolically.

        We only handle simple assignments; anything else is executed
        concretely but ignored symbolically.
        """
        try:
            tree = ast.parse(stmt, mode="exec")
        except SyntaxError:
            return

        for child in ast.walk(tree):
            if isinstance(child, ast.Assign):
                self._exec_assign(child)
            elif isinstance(child, ast.AnnAssign):
                self._exec_annassign(child)
            elif isinstance(child, ast.AugAssign):
                self._exec_augassign(child)

    def _exec_assign(self, node: ast.Assign) -> None:
        rhs_expr = _unparse(node.value)
        try:
            concrete_val = _safe_eval(rhs_expr, self.concrete_state)
        except Exception:
            return
        symbolic_val = self._eval_symbolic(rhs_expr)

        for tgt in node.targets:
            tgt_name = self._target_name(tgt)
            if tgt_name:
                self.concrete_state[tgt_name] = concrete_val
                self.symbolic_state[tgt_name] = symbolic_val
                # Ensure the registry knows about this name.
                if self.registry.get(tgt_name) is None:
                    self.registry.declare(tgt_name, concrete_val)

    def _exec_annassign(self, node: ast.AnnAssign) -> None:
        if node.value is None:
            return
        rhs_expr = _unparse(node.value)
        try:
            concrete_val = _safe_eval(rhs_expr, self.concrete_state)
        except Exception:
            return
        symbolic_val = self._eval_symbolic(rhs_expr)
        tgt_name = self._target_name(node.target)
        if tgt_name:
            self.concrete_state[tgt_name] = concrete_val
            self.symbolic_state[tgt_name] = symbolic_val
            if self.registry.get(tgt_name) is None:
                self.registry.declare(tgt_name, concrete_val)

    def _exec_augassign(self, node: ast.AugAssign) -> None:
        tgt_name = self._target_name(node.target)
        if not tgt_name:
            return
        rhs_expr = _unparse(node.value)
        op_map = {
            ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
            ast.FloorDiv: "//", ast.Mod: "%", ast.Pow: "**",
        }
        op_str = op_map.get(type(node.op), "+")
        full_expr = f"({tgt_name}) {op_str} ({rhs_expr})"
        try:
            concrete_val = _safe_eval(full_expr, self.concrete_state)
        except Exception:
            return
        symbolic_val = self._eval_symbolic(full_expr)
        self.concrete_state[tgt_name] = concrete_val
        self.symbolic_state[tgt_name] = symbolic_val

    @staticmethod
    def _target_name(node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Name):
            return node.id
        return None

    # -- havoc -----------------------------------------------------------

    def _apply_havoc(self, loop_node: dict[str, Any]) -> None:
        """
        After *k* unrollings, assign fresh non-deterministic symbols to
        every variable that may be modified inside the loop body.
        """
        modified: set[str] = set()
        body_ids = self._collect_body_ids(loop_node)
        for bid in body_ids:
            n = self.nodes.get(bid, {})
            modified.update(n.get("data_vars", []))
            modified.update(n.get("control_vars", []))

        for var in modified:
            concrete_val = self.concrete_state.get(var, 0)
            sort = self.registry.infer_sort(concrete_val)
            havoc = z3.Const(f"{var}_havoc_{loop_node['id']}", sort)
            self.symbolic_state[var] = havoc

    def _collect_body_ids(self, loop_node: dict[str, Any]) -> set[str]:
        """BFS collect all node IDs reachable from the loop body successor."""
        body_entry = loop_node["successors"][0] if loop_node["successors"] else None
        if body_entry is None:
            return set()
        reachable: set[str] = set()
        frontier = [body_entry]
        while frontier:
            nid = frontier.pop()
            if nid in reachable or nid == loop_node["id"]:
                continue
            reachable.add(nid)
            n = self.nodes.get(nid, {})
            for succ in n.get("successors", []):
                if succ != loop_node["id"]:
                    frontier.append(succ)
        return reachable
