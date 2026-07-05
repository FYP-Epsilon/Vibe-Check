"""interpreter.py -- WIR reference interpreter (WIRReferenceInterpreter).

(Auto-extracted verbatim from the original monolith during modularization.)
"""

from __future__ import annotations

import ast
from typing import Any, Callable, Optional, get_type_hints
from .safe_exec import _safe_eval, SAFE_BUILTINS


class WIRReferenceInterpreter:
    """
    Deterministic interpreter for a WIR subgraph.

    Walks the WIR control-flow graph with concrete inputs, emitting a
    theoretical trace of task entry/exit events and branch decisions.
    This trace represents the *expected* behaviour against which the
    actual execution trace is compared.
    """

    def __init__(
        self,
        wir: dict[str, Any],
        exec_env: Optional[dict[str, Any]] = None,
        task_names: Optional[set[str]] = None,
    ) -> None:
        self.wir = wir
        self.nodes: dict[str, dict[str, Any]] = {
            n["id"]: n for n in wir.get("nodes", [])
        }
        self.trace_log: list[dict[str, Any]] = []
        self._for_iterators: dict[str, dict] = {}
        # Names (besides the entry function itself) whose calls should be
        # observed as synthetic task_entry/task_exit events -- mirrors what
        # the actual-side collector records when the real code calls one of
        # these (e.g. a task-API stub). Assignments like
        # ``incident = get_incident()`` are WIR *block* statements, not
        # "task"-type nodes, so without this they were completely invisible
        # in the reference trace regardless of E1's exec_env fix.
        self.task_names: set[str] = task_names or set()
        self._stmt_call_cache: dict[str, Optional[str]] = {}
        # Execution environment for WIR statement strings. Without this, an
        # assignment that calls a user-defined function (e.g. a task-API
        # stub) silently NameErrors and never populates state -- passing the
        # tester's own compiled namespace (stub defs + SAFE_BUILTINS) here
        # lets those assignments actually run. None preserves the original
        # empty-builtins behavior for callers that don't supply one.
        if exec_env is not None:
            self._exec_globals: dict[str, Any] = dict(exec_env)
            self._exec_globals.setdefault("__builtins__", SAFE_BUILTINS)
        else:
            self._exec_globals = {"__builtins__": {}}
        # Counts _exec_stmt/_eval_guard failures so a reference execution
        # that fails on every statement can't silently look like a clean,
        # simply-short trace.
        self.exec_errors: int = 0

    def execute(self, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Execute the WIR with *inputs* and return the expected trace.
        """
        state: dict[str, Any] = dict(inputs)
        self._for_iterators = {}
        current: Optional[str] = self.wir.get("entry_node")
        exit_node: str = self.wir.get("exit_node", "")
        steps = 0
        max_steps = 1000

        while current is not None and current != exit_node and steps < max_steps:
            steps += 1
            node = self.nodes.get(current)
            if node is None:
                break

            nxt = self._step(node, state)
            current = nxt

        if steps >= max_steps:
            self.trace_log.append(
                {"event": "_warning", "message": "Step limit exceeded — possible infinite loop."}
            )

        if self.exec_errors:
            self.trace_log.append(
                {"event": "_exec_errors", "count": self.exec_errors}
            )

        return self.trace_log

    def _step(self, node: dict[str, Any], state: dict[str, Any]) -> Optional[str]:
        """Execute a single WIR node and return the next node id."""
        node_type = node.get("type", "block")

        if node_type == "task":
            task_name = node.get("code", ["unknown_task"])[0]
            self.trace_log.append({"event": "task_entry", "task": task_name})
            for stmt in node.get("code", []):
                self._exec_stmt(stmt, state)
            self.trace_log.append({"event": "task_exit", "task": task_name})
            return self._first_successor(node)

        if node_type == "gateway":
            guard_val = self._eval_guard(node.get("guard", "True"), state)
            code_list = node.get("code", [])
            label = code_list[0] if code_list else "gateway"
            self.trace_log.append({
                "event": "branch_point",
                "task": label,
                "taken_branch": guard_val,
            })
            succs = node.get("successors", [])
            if len(succs) >= 2:
                return succs[0] if guard_val else succs[1]
            return self._first_successor(node)

        if node_type == "loop":
            guard = node.get("guard", "")
            if guard.startswith("iter "):
                iterable_expr = guard[5:].strip()
                if node["id"] not in self._for_iterators:
                    try:
                        iterable = _safe_eval(iterable_expr, state)
                    except Exception:
                        iterable = []
                    if not isinstance(iterable, (list, tuple)):
                        iterable = list(iterable)
                    self._for_iterators[node["id"]] = {
                        "iterable": iterable,
                        "idx": 0,
                        "target_var": node.get("data_vars", [None])[0],
                    }
                it = self._for_iterators[node["id"]]
                if it["idx"] < len(it["iterable"]):
                    target_vars = node.get("data_vars", [])
                    item = it["iterable"][it["idx"]]
                    if len(target_vars) == 1:
                        state[target_vars[0]] = item
                    elif len(target_vars) > 1 and isinstance(item, (list, tuple)):
                        for i, var in enumerate(target_vars):
                            state[var] = item[i] if i < len(item) else None
                    else:
                        state[target_vars[0]] = item
                    it["idx"] += 1
                    self.trace_log.append({
                        "event": "branch_point",
                        "task": f"loop_{node['id']}",
                        "taken_branch": True,
                    })
                    return node["successors"][0]
                else:
                    del self._for_iterators[node["id"]]
                    self.trace_log.append({
                        "event": "branch_point",
                        "task": f"loop_{node['id']}",
                        "taken_branch": False,
                    })
                    succs = node.get("successors", [])
                    return succs[1] if len(succs) > 1 else succs[0]
            else:
                guard_val = self._eval_guard(node.get("guard", "True"), state)
                self.trace_log.append({
                    "event": "branch_point",
                    "task": f"loop_{node['id']}",
                    "taken_branch": guard_val,
                })
                succs = node.get("successors", [])
                if len(succs) >= 2:
                    return succs[0] if guard_val else succs[1]
                return self._first_successor(node)

        if node_type == "return":
            for stmt in node.get("code", []):
                self._exec_stmt_observed(stmt, state)
            return None  # Stop execution at return

        if node_type in ("entry", "exit", "block", "break", "continue"):
            for stmt in node.get("code", []):
                self._exec_stmt_observed(stmt, state)
            return self._first_successor(node)

        # Unknown / unhandled node type -- skip safely.
        return self._first_successor(node)

    @staticmethod
    def _first_successor(node: dict[str, Any]) -> Optional[str]:
        succs = node.get("successors", [])
        return succs[0] if succs else None

    def _eval_guard(self, expr: str, state: dict[str, Any]) -> bool:
        if expr.startswith("iter "):
            return True
        if expr.startswith("next("):
            name = expr[5:-1].strip()
            it = self._for_iterators.get(name)
            if it is None:
                return False
            return it["idx"] < len(it["iterable"])
        if expr.startswith("exhausted("):
            name = expr[10:-1].strip()
            it = self._for_iterators.get(name)
            if it is None:
                return False
            return it["idx"] >= len(it["iterable"])
        try:
            return bool(_safe_eval(expr, state))
        except (NameError, KeyError):
            self.exec_errors += 1
            return False
        except Exception:
            # Permissive fallback: guard assumed False on error.
            self.exec_errors += 1
            return False

    def _exec_stmt(self, stmt: str, state: dict[str, Any]) -> None:
        try:
            exec(stmt, self._exec_globals, state)
        except Exception:
            self.exec_errors += 1

    def _stmt_task_call_name(self, stmt: str) -> Optional[str]:
        """If *stmt* calls a name in self.task_names anywhere in its RHS,
        return that name; else None. Cached per statement string since the
        same WIR statement can execute many times (loop bodies)."""
        if stmt in self._stmt_call_cache:
            return self._stmt_call_cache[stmt]
        result: Optional[str] = None
        if self.task_names:
            try:
                tree = ast.parse(stmt, mode="exec")
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id in self.task_names
                    ):
                        result = node.func.id
                        break
            except SyntaxError:
                result = None
        self._stmt_call_cache[stmt] = result
        return result

    def _exec_stmt_observed(self, stmt: str, state: dict[str, Any]) -> None:
        """Execute *stmt*; if it calls a known task/stub name, wrap it with
        synthetic task_entry/task_exit events mirroring what the actual-side
        collector records when the real code makes that call. The stub's
        internals are never traced into -- it's an opaque call from this
        interpreter's perspective, exactly as for the real execution."""
        task_name = self._stmt_task_call_name(stmt)
        if task_name is not None:
            self.trace_log.append({"event": "task_entry", "function": task_name})
        self._exec_stmt(stmt, state)
        if task_name is not None:
            self.trace_log.append({"event": "task_exit", "function": task_name})
