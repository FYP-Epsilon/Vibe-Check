"""
z3_sym_engine.py
================
Phase 2: Perfecting Symbolic Refinement with Z3 (V2)
Module 02 -- Verified IR Extraction

This module implements:
  P2.1  Z3VariableRegistry       -- automatic sort inference & versioning
  P2.2  BoundedConcolicEngine    -- concolic execution with path exploration
  P2.3  k-Bounded Loop Unrolling + QCE State Merging
  P2.4  Incremental Confidence Accumulation + V2 certificate
"""

from __future__ import annotations

import ast
import copy
import inspect
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import z3

SAFE_BUILTINS = {
    "len": len, "range": range, "enumerate": enumerate, "zip": zip,
    "map": map, "filter": filter, "abs": abs, "min": min, "max": max,
    "sum": sum, "round": round, "str": str, "int": int, "float": float,
    "bool": bool, "list": list, "dict": dict, "tuple": tuple, "set": set,
    "type": type, "isinstance": isinstance, "hasattr": hasattr, "getattr": getattr,
}

try:
    from .ast_extractor import CFGExtractor, _unparse
except ImportError:
    from ast_extractor import CFGExtractor, _unparse


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _safe_eval(expr: str, env: dict[str, Any]) -> Any:
    """Evaluate *expr* in a restricted environment."""
    return eval(expr, {"__builtins__": {}}, env)


def _safe_exec(stmts: list[str], env: dict[str, Any]) -> None:
    """Execute a list of statement strings inside *env*."""
    if not stmts:
        return
    code = "\n".join(stmts)
    exec(code, {"__builtins__": {}}, env)


# ----------------------------------------------------------------------
# P2.1  Z3VariableRegistry
# ----------------------------------------------------------------------

class Z3VariableRegistry:
    """
    Bridges Python's dynamic typing to Z3's static sort system.

    Responsibilities
    ----------------
    * Automatic sort inference from runtime Python values.
    * Variable versioning when a name is re-bound to a different type.
    * Flattening of nested dictionaries into dot-path scalar variables.
    * Array / list encoding via ``z3.ArraySort`` or finite scalar expansion.
    """

    def __init__(self) -> None:
        # Maps a Python variable name to its current Z3 expression.
        self._registry: dict[str, z3.ExprRef] = {}
        # Version counters for type-changing variables (x -> x_0, x_1, ...).
        self._version_counter: dict[str, int] = {}
        # Type history per variable name.
        self._type_history: dict[str, list[type]] = {}
        # Flattened dictionary fields: "order_total" -> z3.Int("order_total")
        self._flat_registry: dict[str, z3.ExprRef] = {}

    # -- sort inference --------------------------------------------------

    @staticmethod
    def infer_sort(value: Any) -> z3.SortRef:
        """Map a Python runtime value to its closest Z3 sort."""
        match value:
            case bool():
                return z3.BoolSort()
            case int():
                return z3.IntSort()
            case float():
                return z3.RealSort()
            case str():
                # Encode strings as integer tokens for arithmetic constraints.
                return z3.IntSort()
            case list() if len(value) > 0:
                elem_sort = Z3VariableRegistry.infer_sort(value[0])
                return z3.ArraySort(z3.IntSort(), elem_sort)
            case dict() if len(value) > 0:
                # Dicts are handled via flattening; this sort is for the
                # generic dict reference itself (rarely used directly).
                first_val = next(iter(value.values()))
                return Z3VariableRegistry.infer_sort(first_val)
            case _:
                sort_name = f"PyObject_{type(value).__name__}"
                return z3.DeclareSort(sort_name)

    # -- public API ------------------------------------------------------

    def declare(self, name: str, value: Any) -> z3.ExprRef:
        """
        Declare or retrieve a Z3 constant for *name* bound to *value*.

        If the type of *value* differs from the last recorded type for
        *name*, a new versioned constant is created (e.g. ``x_1``).
        """
        py_type = type(value)
        if name in self._registry:
            if self._type_history[name][-1] == py_type:
                return self._registry[name]
            # Type transition -- version the variable.
            self._version_counter[name] = self._version_counter.get(name, 0) + 1
            versioned_name = f"{name}_{self._version_counter[name]}"
            sort = self.infer_sort(value)
            const = z3.Const(versioned_name, sort)
            self._registry[name] = const
            self._type_history[name].append(py_type)
            return const

        # First time seeing this name.
        sort = self.infer_sort(value)
        const = z3.Const(name, sort)
        self._registry[name] = const
        self._type_history[name] = [py_type]
        return const

    def get(self, name: str) -> Optional[z3.ExprRef]:
        """Return the current Z3 expression for *name*, or *None*."""
        return self._registry.get(name)

    def version_variable(self, name: str, new_value: Any) -> z3.ExprRef:
        """Force a new versioned constant for *name* regardless of type."""
        self._version_counter[name] = self._version_counter.get(name, 0) + 1
        versioned_name = f"{name}_{self._version_counter[name]}"
        sort = self.infer_sort(new_value)
        const = z3.Const(versioned_name, sort)
        self._registry[name] = const
        self._type_history.setdefault(name, []).append(type(new_value))
        return const

    # -- dict flattening -------------------------------------------------

    def flatten_dict(self, name: str, value: dict[str, Any]) -> dict[str, z3.ExprRef]:
        """
        Flatten a nested dict into scalar Z3 variables using dot-path notation.

        Example::

            {"items": [{"price": 10}], "total": 20}
            -> order_items_0_price = z3.Int("order_items_0_price")
               order_total          = z3.Int("order_total")

        Returns a mapping from flattened key to Z3 expression.
        """
        result: dict[str, z3.ExprRef] = {}

        def _recurse(prefix: str, obj: Any) -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    safe_k = str(k).replace(".", "_")
                    _recurse(f"{prefix}_{safe_k}", v)
            elif isinstance(obj, list):
                for idx, v in enumerate(obj):
                    _recurse(f"{prefix}_{idx}", v)
            else:
                sort = self.infer_sort(obj)
                const = z3.Const(prefix, sort)
                self._flat_registry[prefix] = const
                result[prefix] = const

        _recurse(name, value)
        return result

    def get_flat(self, flat_name: str) -> Optional[z3.ExprRef]:
        """Retrieve a flattened field by its dot-path key."""
        return self._flat_registry.get(flat_name)

    # -- list / array helpers --------------------------------------------

    def declare_array(self, name: str, elem_sort: z3.SortRef, size_hint: int = 0) -> z3.ArrayRef:
        """Declare a Z3 Array variable for list-like structures."""
        arr = z3.Array(name, z3.IntSort(), elem_sort)
        self._registry[name] = arr
        return arr

    def declare_finite_array(self, name: str, values: list[Any]) -> list[z3.ExprRef]:
        """
        Finite modelling: allocate one scalar Z3 variable per index.

        Returns a list of scalar expressions ``[name_0, name_1, ...]``.
        """
        scalars: list[z3.ExprRef] = []
        sort = self.infer_sort(values[0]) if values else z3.IntSort()
        for idx in range(len(values)):
            scalar = z3.Const(f"{name}_{idx}", sort)
            scalars.append(scalar)
            self._flat_registry[f"{name}_{idx}"] = scalar
        self._registry[name] = scalars[0]  # placeholder reference
        return scalars


# ----------------------------------------------------------------------
# Symbolic Expression Evaluator (Python AST -> Z3)
# ----------------------------------------------------------------------

class SymbolicEvaluator(ast.NodeVisitor):
    """
    Convert a Python expression AST into an equivalent Z3 expression.

    Supports the subset most commonly generated by LLMs for workflow
    conditions: literals, names, arithmetic, comparisons, and boolean
    connectives.
    """

    def __init__(
        self,
        registry: Z3VariableRegistry,
        symbolic_state: dict[str, z3.ExprRef],
    ) -> None:
        self.registry = registry
        self.symbolic_state = symbolic_state

    def eval(self, node: ast.AST) -> z3.ExprRef:
        """Entry point -- dispatch to ``visit_*``."""
        method = getattr(self, f"visit_{type(node).__name__}", self.generic_visit)
        return method(node)

    def generic_visit(self, node: ast.AST) -> z3.ExprRef:
        raise NotImplementedError(
            f"Symbolic evaluation not supported for {type(node).__name__}"
        )

    # -- literals --------------------------------------------------------

    def visit_Constant(self, node: ast.Constant) -> z3.ExprRef:
        v = node.value
        if isinstance(v, bool):
            return z3.BoolVal(v)
        elif isinstance(v, int):
            return z3.IntVal(v)
        elif isinstance(v, float):
            return z3.RealVal(v)
        elif isinstance(v, str):
            # String-as-token encoding.
            return z3.IntVal(hash(v) & 0x7FFFFFFF)
        else:
            sort = self.registry.infer_sort(v)
            return z3.Const(f"const_{id(v)}", sort)

    def visit_Name(self, node: ast.Name) -> z3.ExprRef:
        if node.id in self.symbolic_state:
            return self.symbolic_state[node.id]
        reg = self.registry.get(node.id)
        if reg is not None:
            return reg
        # Undeclared name -- create an uninterpreted placeholder.
        placeholder = z3.Const(node.id, z3.DeclareSort("PyObject"))
        self.symbolic_state[node.id] = placeholder
        return placeholder

    # -- arithmetic ------------------------------------------------------

    def visit_BinOp(self, node: ast.BinOp) -> z3.ExprRef:
        left = self.eval(node.left)
        right = self.eval(node.right)

        if isinstance(node.op, ast.Add):
            return left + right
        elif isinstance(node.op, ast.Sub):
            return left - right
        elif isinstance(node.op, ast.Mult):
            return left * right
        elif isinstance(node.op, ast.Div):
            return left / right
        elif isinstance(node.op, ast.FloorDiv):
            # Z3 has no native floor-div; approximate with ToReal/ToInt.
            return z3.ToInt(left / right)
        elif isinstance(node.op, ast.Mod):
            return left % right
        elif isinstance(node.op, ast.Pow):
            # Z3 has no native power for integers; keep uninterpreted.
            sort = z3.IntSort() if left.sort() == z3.IntSort() else z3.RealSort()
            return z3.Const(f"pow_{id(node)}", sort)
        else:
            raise NotImplementedError(f"BinOp {type(node.op).__name__}")

    # -- comparisons -----------------------------------------------------

    def visit_Compare(self, node: ast.Compare) -> z3.ExprRef:
        left = self.eval(node.left)
        result: list[z3.BoolRef] = []

        for op, comparator in zip(node.ops, node.comparators):
            right = self.eval(comparator)
            if isinstance(op, ast.Eq):
                result.append(left == right)
            elif isinstance(op, ast.NotEq):
                result.append(left != right)
            elif isinstance(op, ast.Lt):
                result.append(left < right)
            elif isinstance(op, ast.LtE):
                result.append(left <= right)
            elif isinstance(op, ast.Gt):
                result.append(left > right)
            elif isinstance(op, ast.GtE):
                result.append(left >= right)
            else:
                result.append(z3.BoolVal(True))  # fallback
            left = right  # chained comparison semantics

        if len(result) == 1:
            return result[0]
        return z3.And(*result)

    # -- boolean connectives ---------------------------------------------

    def visit_BoolOp(self, node: ast.BoolOp) -> z3.ExprRef:
        vals = [self.eval(v) for v in node.values]
        if isinstance(node.op, ast.And):
            return z3.And(*vals)
        elif isinstance(node.op, ast.Or):
            return z3.Or(*vals)
        else:
            raise NotImplementedError(f"BoolOp {type(node.op).__name__}")

    def visit_UnaryOp(self, node: ast.UnaryOp) -> z3.ExprRef:
        val = self.eval(node.operand)
        if isinstance(node.op, ast.Not):
            return z3.Not(val)
        elif isinstance(node.op, ast.UAdd):
            return +val
        elif isinstance(node.op, ast.USub):
            return -val
        else:
            raise NotImplementedError(f"UnaryOp {type(node.op).__name__}")

    def visit_NamedExpr(self, node: ast.NamedExpr) -> z3.ExprRef:
        """Walrus operator: evaluate RHS and bind to target symbolically."""
        value = self.eval(node.value)
        target_name = node.target.id if isinstance(node.target, ast.Name) else _unparse(node.target)
        self.symbolic_state[target_name] = value
        return value

    def visit_Call(self, node: ast.Call) -> z3.ExprRef:
        """
        Function calls are treated as uninterpreted functions.
        We create a fresh constant whose sort is inferred from the
        function name heuristic (e.g. ``len`` -> IntSort).
        """
        func_name = _unparse(node.func)
        # Simple heuristic: len -> Int, anything else -> generic.
        sort = z3.IntSort() if func_name == "len" else z3.DeclareSort("PyObject")
        return z3.Const(f"call_{func_name}_{id(node)}", sort)

    def visit_Subscript(self, node: ast.Subscript) -> z3.ExprRef:
        """e.g. ``order["total"]`` -- look up in flattened registry."""
        base = _unparse(node.value)
        idx = _unparse(node.slice)
        flat_key = f"{base}_{idx}"
        flat = self.registry.get_flat(flat_key)
        if flat is not None:
            return flat
        # Fallback: array select if base is an Array.
        if base in self.symbolic_state:
            arr = self.symbolic_state[base]
            if isinstance(arr, z3.ArrayRef):
                index_expr = self.eval(node.slice)
                return z3.Select(arr, index_expr)
        return z3.Const(flat_key, z3.DeclareSort("PyObject"))


# ----------------------------------------------------------------------
# WIR Symbolic Tracer
# ----------------------------------------------------------------------

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
            ev = SymbolicEvaluator(self.registry, self.symbolic_state)
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


# ----------------------------------------------------------------------
# P2.2 / P2.3  BoundedConcolicEngine
# ----------------------------------------------------------------------

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
        except (TypeError, KeyError, IndexError, AttributeError, ZeroDivisionError):
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
        concrete_step_count = 0
        target_file = "<string>"

        def concrete_guard(frame, event, arg):
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
            result = func(**copy.deepcopy(inputs))
        finally:
            sys.settrace(old_trace)
        return result

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
        solver = z3.Solver()
        solver.set("timeout", self.timeout_ms)
        solver.reset()  # Reset solver state to prevent constraint accumulation across iterations.
        solver.add(path_condition)

        # Also add constraints that we haven't seen this exact PC before.
        for pc in self.explored_path_conditions:
            solver.add(z3.Not(pc))

        start = time.time()
        result = solver.check()
        elapsed = (time.time() - start) * 1000

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

        solver.reset()  # Reset solver state to prevent constraint accumulation across iterations.
        return new_inputs

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


# ----------------------------------------------------------------------
# Convenience orchestrator
# ----------------------------------------------------------------------

def run_v2_pipeline(
    source: str,
    function_name: str,
    initial_inputs: dict[str, Any],
    max_k: int = 3,
    query_budget: int = 500,
    compiled_ns: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    End-to-end Phase-2 pipeline.

    1. Runs the :class:`BoundedConcolicEngine` on *function_name*.
    2. Returns the V2 certificate plus the final concrete / symbolic
       states from the last iteration.
    """
    engine = BoundedConcolicEngine(
        source=source,
        function_name=function_name,
        max_k=max_k,
        query_budget=query_budget,
        compiled_ns=compiled_ns,
    )
    cert = engine.run(initial_inputs)
    return {
        "certificate": cert,
        "engine": engine,
    }
