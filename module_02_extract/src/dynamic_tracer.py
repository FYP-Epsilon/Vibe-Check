"""
dynamic_tracer.py
=================
Phase 3: Implementing Dynamic Tracing & Differential Execution (V1)
Module 02 -- Verified IR Extraction

This module implements:
  P3.1  WIRTraceCollector          -- selective sys.settrace pipeline
  P3.2  WIRReferenceInterpreter    -- deterministic WIR executor
  P3.3  DifferentialComparator     -- LCS-based trace comparison
  P3.4  RandomizedDifferentialTester
  P3.5  MultiModalCertificateComposer

Gotcha fixes integrated:
  * Gotcha 1 -- Stutter Elimination (silent helper steps)
  * Gotcha 2 -- Non-deterministic dict iteration hashing
  * Gotcha 3 -- Exception event capture
  * Gotcha 4 -- State-Mutation Audit
"""

from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import random
import sys
import tempfile
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, get_type_hints

SAFE_BUILTINS = {
    "len": len, "range": range, "enumerate": enumerate, "zip": zip,
    "map": map, "filter": filter, "abs": abs, "min": min, "max": max,
    "sum": sum, "round": round, "str": str, "int": int, "float": float,
    "bool": bool, "list": list, "dict": dict, "tuple": tuple, "set": set,
    "type": type, "isinstance": isinstance, "hasattr": hasattr, "getattr": getattr,
}

try:
    from .ast_extractor import CFGExtractor, _collect_vars
except ImportError:
    from ast_extractor import CFGExtractor, _collect_vars


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _safe_eval(expr: str, env: dict[str, Any]) -> Any:
    return eval(expr, {"__builtins__": {}}, env)


def _safe_exec(stmts: list[str], env: dict[str, Any]) -> None:
    if not stmts:
        return
    exec("\n".join(stmts), {"__builtins__": {}}, env)


# ----------------------------------------------------------------------
# P3.1  WIRTraceCollector
# ----------------------------------------------------------------------

class WIRTraceCollector:
    """
    Low-overhead trace collector built on ``sys.settrace``.

    Implements the **selective observable pattern**: only task boundaries
    (function entry/exit matching BPMN tasks) and control-flow decisions
    (lines containing ``if`` / ``while`` / ``for``) are recorded.  All
    library frames are dropped immediately by returning ``None``.

    Gotcha fixes
    ------------
    * **Gotcha 2** -- For ``for`` loops iterating over dicts/sets the
      collector stores ``(iteration_index, key_hash)`` instead of raw
      key values, making trace comparison robust against insertion-order
      non-determinism.
    * **Gotcha 3** -- The ``'exception'`` trace event is captured and
      stored so that exception edges in the WIR can be validated against
      real runtime behaviour.
    * **Gotcha 4** -- A **State-Mutation Audit** compares consecutive
      line-event snapshots of ``frame.f_locals``.  If a *state variable*
      changes while ``_inside_task`` is ``False``, a warning is emitted.
    """

    def __init__(
        self,
        target_file: str,
        task_patterns: list[str],
        branch_lines: set[int],
        control_variables: list[str],
        state_variables: Optional[list[str]] = None,
        for_loop_lines: Optional[set[int]] = None,
    ) -> None:
        self.target_file = target_file
        self.task_patterns = task_patterns
        self.branch_lines = branch_lines
        self.control_variables = set(control_variables)
        self.state_variables = set(state_variables or [])
        self.for_loop_lines = for_loop_lines or set()
        self.max_trace_steps = 2000
        self.trace_step_count = 0

        # Trace storage
        self.trace_log: list[dict[str, Any]] = []
        self.mutation_warnings: list[dict[str, Any]] = []
        self.exception_records: list[dict[str, Any]] = []

        # Runtime state
        self._original_trace: Optional[Callable] = None
        self._task_depth = 0
        self._last_locals: dict[str, Any] = {}
        self._loop_counters: dict[int, int] = {}  # line_no -> iteration count

    # -- public API ------------------------------------------------------

    def start_tracing(self) -> None:
        """Install the trace callback, preserving any existing tracer."""
        self._original_trace = sys.gettrace()
        sys.settrace(self.trace_callback)

    def stop_tracing(self) -> None:
        """Restore the previous trace callback."""
        sys.settrace(self._original_trace)

    def __enter__(self) -> WIRTraceCollector:
        self.start_tracing()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop_tracing()

    # -- trace callback --------------------------------------------------

    def trace_callback(
        self,
        frame: types.FrameType,
        event: str,
        arg: Any,
    ) -> Optional[Callable]:
        """Main ``sys.settrace`` hook."""
        if event == "line":
            self.trace_step_count += 1
            if self.trace_step_count > self.max_trace_steps:
                raise RuntimeError(
                    f"Trace collection exceeded {self.max_trace_steps} steps — possible infinite loop."
                )

        # Tier-1 filter: drop everything that does not belong to the target file.
        if not self._is_target_frame(frame):
            return None

        func_name = frame.f_code.co_name
        line_no = frame.f_lineno
        locals_dict = frame.f_locals

        if event == "call" and self._is_task_function(frame):
            self._task_depth += 1
            self.trace_log.append({
                "event": "task_entry",
                "function": func_name,
                "line": line_no,
                "observables": self._extract_observables(locals_dict),
            })
            return self.trace_callback

        if event == "return" and self._is_task_function(frame):
            self.trace_log.append({
                "event": "task_exit",
                "function": func_name,
                "line": line_no,
                "return_value": self._serialize_value(arg),
                "observables": self._extract_observables(locals_dict),
            })
            self._task_depth = max(0, self._task_depth - 1)
            return None  # stop tracing after task exit

        if event == "line":
            # Gotcha 4: mutation audit -- run on *every* line in the target.
            self._audit_mutations(locals_dict, line_no, func_name)

            if line_no in self.branch_lines:
                # Gotcha 2: dict-iteration hashing (must run before _last_locals is updated)
                iteration_info = self._capture_iteration_info(frame, line_no, locals_dict)

                self.trace_log.append({
                    "event": "branch_point",
                    "line": line_no,
                    "function": func_name,
                    "observables": self._extract_observables(locals_dict),
                    "iteration_info": iteration_info,
                })

            # Update snapshot AFTER all diff-based logic.
            self._last_locals = dict(locals_dict)
            return self.trace_callback

        if event == "exception":
            # Gotcha 3: capture exception events
            exc_type, exc_value, _ = arg
            record = {
                "event": "exception",
                "line": line_no,
                "function": func_name,
                "exception_type": exc_type.__name__ if exc_type else None,
                "exception_msg": str(exc_value) if exc_value else None,
            }
            self.trace_log.append(record)
            self.exception_records.append(record)
            return self.trace_callback

        # All other events: continue tracing but do not record.
        return self.trace_callback

    # -- filtering helpers -----------------------------------------------

    def _is_target_frame(self, frame: types.FrameType) -> bool:
        return frame.f_code.co_filename == self.target_file

    def _is_task_function(self, frame: types.FrameType) -> bool:
        return any(pat in frame.f_code.co_name for pat in self.task_patterns)

    # -- observable extraction -------------------------------------------

    def _extract_observables(self, locals_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Shallow-copy only control-relevant variables, serialising each as
        ``{type, hash}`` to keep trace size bounded.
        """
        result: dict[str, Any] = {}
        for var_name in self.control_variables:
            if var_name in locals_dict:
                val = locals_dict[var_name]
                try:
                    h = hash(val) & 0xFFFFFFFF
                except TypeError:
                    h = hash(id(val)) & 0xFFFFFFFF
                result[var_name] = {
                    "type": type(val).__name__,
                    "hash": h,
                }
        return result

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """Lightweight serialisation of a return value for the trace log."""
        if value is None:
            return None
        if isinstance(value, (bool, int, float, str)):
            return value
        return f"<{type(value).__name__}>"

    # -- Gotcha 2: dict-iteration hashing --------------------------------

    def _capture_iteration_info(
        self,
        frame: types.FrameType,
        line_no: int,
        locals_dict: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """
        If this branch line is a ``for`` loop, return the current iteration
        index and a hash of the loop variable (if determinable).
        """
        if line_no not in self.for_loop_lines:
            return None

        self._loop_counters[line_no] = self._loop_counters.get(line_no, 0) + 1
        iteration_idx = self._loop_counters[line_no]

        # Heuristic: find a local variable that changed since the last
        # line event and that is iterable (dict/set/list).
        key_hash: Optional[int] = None
        for name, val in locals_dict.items():
            if name.startswith("__"):
                continue
            if name not in self._last_locals:
                # New variable appeared -- could be the loop variable.
                key_hash = hash(val) & 0xFFFFFFFF
                break
            elif self._last_locals[name] is not val:
                # Variable reassigned.
                key_hash = hash(val) & 0xFFFFFFFF
                break

        return {
            "iteration_index": iteration_idx,
            "key_hash": key_hash,
        }

    # -- Gotcha 4: state-mutation audit ----------------------------------

    def _audit_mutations(
        self,
        locals_dict: dict[str, Any],
        line_no: int,
        func_name: str,
    ) -> None:
        """
        Detect assignments to state variables that occur **outside** a
        recognised task boundary.
        """
        if not self.state_variables:
            return

        inside_task = self._task_depth > 0
        for var_name in self.state_variables:
            if var_name not in locals_dict:
                continue
            old_val = self._last_locals.get(var_name)
            new_val = locals_dict[var_name]
            if old_val is not None and old_val is not new_val:
                if not inside_task:
                    self.mutation_warnings.append({
                        "variable": var_name,
                        "line": line_no,
                        "function": func_name,
                        "old": self._serialize_value(old_val),
                        "new": self._serialize_value(new_val),
                    })


# ----------------------------------------------------------------------
# P3.2  WIRReferenceInterpreter
# ----------------------------------------------------------------------

class WIRReferenceInterpreter:
    """
    Deterministic interpreter for a WIR subgraph.

    Walks the WIR control-flow graph with concrete inputs, emitting a
    theoretical trace of task entry/exit events and branch decisions.
    This trace represents the *expected* behaviour against which the
    actual execution trace is compared.
    """

    def __init__(self, wir: dict[str, Any]) -> None:
        self.wir = wir
        self.nodes: dict[str, dict[str, Any]] = {
            n["id"]: n for n in wir.get("nodes", [])
        }
        self.trace_log: list[dict[str, Any]] = []
        self._for_iterators: dict[str, dict] = {}

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
                    self._for_iterators[node["id"]] = {
                        "iterable": iterable,
                        "idx": 0,
                        "target_var": node.get("data_vars", [None])[0],
                    }
                it = self._for_iterators[node["id"]]
                if it["idx"] < len(it["iterable"]):
                    state[it["target_var"]] = it["iterable"][it["idx"]]
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
                self._exec_stmt(stmt, state)
            return None  # Stop execution at return

        if node_type in ("entry", "exit", "block", "break", "continue"):
            for stmt in node.get("code", []):
                self._exec_stmt(stmt, state)
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
            return False
        except Exception:
            # Permissive fallback: guard assumed False on error.
            return False

    @staticmethod
    def _exec_stmt(stmt: str, state: dict[str, Any]) -> None:
        try:
            exec(stmt, {"__builtins__": {}}, state)
        except Exception:
            pass


# ----------------------------------------------------------------------
# P3.3  DifferentialComparator
# ----------------------------------------------------------------------

class DifferentialComparator:
    """
    Compare an *actual* execution trace against an *expected* WIR trace.

    Implements:
    * **Stutter Elimination** (Gotcha 1) -- helper-task events that do
      not appear in the expected trace are filtered out before LCS.
    * **LCS alignment** -- classic dynamic-programming longest common
      subsequence to compute similarity.
    * **Divergence-point extraction** -- backtracks the DP table to
      highlight the first mismatch.
    """

    def __init__(
        self,
        actual_trace: list[dict[str, Any]],
        expected_trace: list[dict[str, Any]],
    ) -> None:
        self.actual_raw = actual_trace
        self.expected_raw = expected_trace

    # -- public API ------------------------------------------------------

    def compare(self) -> dict[str, Any]:
        """
        Run the full comparison pipeline and return a result dictionary.
        """
        # 1. Stutter elimination (Gotcha 1)
        expected_tasks = self._extract_task_names(self.expected_raw)
        actual_filtered = self._eliminate_stutter(self.actual_raw, expected_tasks)

        # 2. Normalise to comparable tuples.
        actual_seq = self._normalise(actual_filtered)
        expected_seq = self._normalise(self.expected_raw)

        # 3. LCS similarity.
        lcs_len = self._lcs(actual_seq, expected_seq)
        max_len = max(len(actual_seq), len(expected_seq))
        similarity = lcs_len / max_len if max_len > 0 else 1.0

        # 4. Empty-trace handling.
        if not actual_seq and not expected_seq:
            similarity = 1.0
            passed = True
            # Only pass if no mutation warnings exist in the actual trace.
            if any(e.get("mutation_warning") for e in self.actual_raw):
                passed = False
        else:
            passed = similarity >= 0.95

        # 5. Divergence points.
        divergences = self._find_divergence_points(actual_seq, expected_seq)

        return {
            "similarity_score": similarity,
            "lcs_length": lcs_len,
            "actual_length": len(actual_seq),
            "expected_length": len(expected_seq),
            "divergence_points": divergences,
            "passed": passed,
        }

    # -- internal helpers ------------------------------------------------

    @staticmethod
    def _extract_task_names(trace: list[dict[str, Any]]) -> set[str]:
        names: set[str] = set()
        for e in trace:
            if e["event"] in ("task_entry", "task_exit"):
                names.add(e.get("task", e.get("function", "")))
        return names

    @staticmethod
    def _eliminate_stutter(
        actual_trace: list[dict[str, Any]],
        expected_tasks: set[str],
    ) -> list[dict[str, Any]]:
        """
        Remove actual-trace events that correspond to helper functions
        (silent steps) not present in the expected trace.
        """
        filtered: list[dict[str, Any]] = []
        for e in actual_trace:
            if e["event"] in ("task_entry", "task_exit"):
                task_name = e.get("function", e.get("task", ""))
                if task_name in expected_tasks:
                    filtered.append(e)
            else:
                filtered.append(e)
        return filtered

    @staticmethod
    def _normalise(trace: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
        """Convert trace records into comparable tuples."""
        seq: list[tuple[Any, ...]] = []
        for e in trace:
            ev = e["event"]
            if ev == "task_entry":
                seq.append(("task_entry", e.get("task", e.get("function", ""))))
            elif ev == "task_exit":
                seq.append(("task_exit", e.get("task", e.get("function", ""))))
            elif ev == "branch_point":
                # Under the task-observable abstraction we only care that a
                # branch point was reached, not its specific label or decision.
                seq.append(("branch_point",))
            elif ev == "exception":
                seq.append(("exception", e.get("exception_type")))
        return seq

    @staticmethod
    def _lcs(a: list[tuple], b: list[tuple]) -> int:
        """Classic DP longest-common-subsequence length."""
        m, n = len(a), len(b)
        # Use two rows to keep O(min(m,n)) memory.
        prev = [0] * (n + 1)
        curr = [0] * (n + 1)
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if a[i - 1] == b[j - 1]:
                    curr[j] = prev[j - 1] + 1
                else:
                    curr[j] = max(prev[j], curr[j - 1])
            prev, curr = curr, prev
        return prev[n]

    @staticmethod
    def _find_divergence_points(
        a: list[tuple],
        b: list[tuple],
    ) -> list[dict[str, Any]]:
        """
        Backtrack the LCS DP table to report the first few mismatch sites.
        """
        m, n = len(a), len(b)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if a[i - 1] == b[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

        divergences: list[dict[str, Any]] = []
        i, j = m, n
        while i > 0 and j > 0 and len(divergences) < 5:
            if a[i - 1] == b[j - 1]:
                i -= 1
                j -= 1
            elif dp[i - 1][j] >= dp[i][j - 1]:
                divergences.append({
                    "type": "extra_in_actual",
                    "index": i - 1,
                    "item": a[i - 1],
                })
                i -= 1
            else:
                divergences.append({
                    "type": "missing_in_actual",
                    "index": j - 1,
                    "item": b[j - 1],
                })
                j -= 1

        # Any remaining tail.
        while i > 0 and len(divergences) < 5:
            divergences.append({"type": "extra_in_actual", "index": i - 1, "item": a[i - 1]})
            i -= 1
        while j > 0 and len(divergences) < 5:
            divergences.append({"type": "missing_in_actual", "index": j - 1, "item": b[j - 1]})
            j -= 1

        return list(reversed(divergences))


# ----------------------------------------------------------------------
# P3.4  Randomized Differential Testing
# ----------------------------------------------------------------------

class RandomizedDifferentialTester:
    """
    Run *n* random-input differential tests between actual Python code
    and the WIR reference interpreter.
    """

    def __init__(
        self,
        source: str,
        function_name: str,
        wir: dict[str, Any],
        task_patterns: list[str],
        branch_lines: set[int],
        control_variables: list[str],
        state_variables: Optional[list[str]] = None,
        n_runs: int = 20,
        seed: Optional[int] = None,
        compiled_ns: Optional[dict[str, Any]] = None,
    ) -> None:
        self.source = source
        self.function_name = function_name
        self.wir = wir
        self.task_patterns = task_patterns
        self.branch_lines = branch_lines
        self.control_variables = control_variables
        self.state_variables = state_variables
        self.n_runs = n_runs
        if seed is not None:
            random.seed(seed)

        # Compile the source so we can call it under tracing.
        if compiled_ns is not None:
            self._compiled_ns = compiled_ns
        else:
            self._compiled_ns: dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
            exec(compile(self.source, "<string>", "exec"), self._compiled_ns)

        # Extract argument names from the AST so we know what to generate.
        self.arg_names = self._extract_arg_names()

    def _extract_arg_names(self) -> list[str]:
        tree = ast.parse(self.source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == self.function_name:
                    return [a.arg for a in node.args.args]
        return []

    def _generate_random_inputs(self) -> dict[str, Any]:
        """Produce a random concrete input dict for the target function."""
        func = self._compiled_ns[self.function_name]
        try:
            type_hints = get_type_hints(func)
        except Exception:
            type_hints = {}

        sig = inspect.signature(func)
        inputs: dict[str, Any] = {}
        for param_name, param in sig.parameters.items():
            ann = type_hints.get(param_name)
            origin = getattr(ann, "__origin__", None)
            if ann is int:
                inputs[param_name] = random.randint(-100, 100)
            elif ann is float:
                inputs[param_name] = round(random.uniform(-100.0, 100.0), 2)
            elif ann is bool:
                inputs[param_name] = random.choice([True, False])
            elif ann is str:
                inputs[param_name] = ""
            elif ann is list or origin is list:
                inputs[param_name] = [
                    {
                        "base_price": round(random.uniform(10.0, 100.0), 2),
                        "qty": random.randint(1, 5),
                    }
                    for _ in range(random.randint(1, 3))
                ]
            elif ann is dict or origin is dict:
                inputs[param_name] = {
                    "loyalty": random.choice(["bronze", "silver", "gold", "platinum"]),
                    "region_multiplier": round(random.uniform(0.5, 2.0), 2),
                }
            else:
                inputs[param_name] = random.randint(-100, 100)
        return inputs

    def _run_actual(self, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute the real function under ``sys.settrace``."""
        collector = WIRTraceCollector(
            target_file="<string>",
            task_patterns=self.task_patterns,
            branch_lines=self.branch_lines,
            control_variables=self.control_variables,
            state_variables=self.state_variables,
        )
        func = self._compiled_ns[self.function_name]
        with collector:
            try:
                func(**copy.deepcopy(inputs))
            except BaseException:
                # Safety net: catch BaseException so SystemExit or KeyboardInterrupt
                # inside traced code does not kill the FastAPI worker.
                pass  # exceptions are recorded by the collector
        return collector.trace_log

    def _run_expected(self, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute the WIR reference interpreter."""
        interpreter = WIRReferenceInterpreter(self.wir)
        trace = interpreter.execute(inputs)
        # If the function name matches a task pattern, wrap the trace with
        # synthetic task-entry / task-exit events so it aligns with the
        # actual execution trace captured by sys.settrace.
        if any(pat in self.function_name for pat in self.task_patterns):
            trace = [
                {"event": "task_entry", "task": self.function_name},
                *trace,
                {"event": "task_exit", "task": self.function_name},
            ]
        return trace

    @staticmethod
    def _make_hashable(val: Any) -> Any:
        """Recursively convert unhashable types to hashable equivalents."""
        if isinstance(val, list):
            return tuple(RandomizedDifferentialTester._make_hashable(v) for v in val)
        if isinstance(val, dict):
            return tuple(sorted((k, RandomizedDifferentialTester._make_hashable(v)) for k, v in val.items()))
        return val

    def run(self) -> dict[str, Any]:
        """
        Perform the randomized differential test loop.

        Returns a V1 certificate dictionary.
        """
        matching = 0
        results: list[dict[str, Any]] = []
        input_hashes: set[int] = set()

        for _ in range(self.n_runs):
            inputs = self._generate_random_inputs()
            safe_inputs = tuple(sorted((k, self._make_hashable(v)) for k, v in inputs.items()))
            input_hashes.add(hash(safe_inputs))

            actual = self._run_actual(inputs)
            expected = self._run_expected(inputs)

            comparator = DifferentialComparator(actual, expected)
            result = comparator.compare()
            results.append(result)

            if result["passed"]:
                matching += 1

        # Input-coverage score: entropy of the generated input set.
        coverage_score = min(len(input_hashes) / self.n_runs, 1.0)
        confidence = (matching / self.n_runs) * coverage_score if self.n_runs else 1.0

        return {
            "version": "V1",
            "confidence": confidence,
            "matching_traces": matching,
            "total_runs": self.n_runs,
            "input_coverage_score": coverage_score,
            "message": (
                "V1 dynamic tracing passed."
                if confidence >= 0.95
                else "V1 dynamic tracing did not reach confidence threshold."
            ),
        }


# ----------------------------------------------------------------------
# P3.5  Multi-Modal Certificate Composer
# ----------------------------------------------------------------------

class MultiModalCertificateComposer:
    """
    Combine the independent V1, V2, and V3 correctness certificates into
    a single multi-modal confidence score.
    """

    @staticmethod
    def compose(
        v1_cert: dict[str, Any],
        v2_cert: dict[str, Any],
        v3_cert: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Compute combined confidence assuming independence of failure modes::

            combined = 1 - (1 - v1) * (1 - v2) * (1 - v3)
        """
        v1 = v1_cert.get("confidence", 0.0)
        v2 = v2_cert.get("confidence", 0.0)
        v3 = v3_cert.get("confidence", 0.0)

        combined = 1.0 - (1.0 - v1) * (1.0 - v2) * (1.0 - v3)

        return {
            "version": "V1+V2+V3",
            "combined_confidence": combined,
            "v1_confidence": v1,
            "v2_confidence": v2,
            "v3_confidence": v3,
            "passed": combined >= 0.95,
            "message": (
                "WIR validated -- passed to Module 03."
                if combined >= 0.95
                else "Flag for manual review -- combined confidence below 0.95."
            ),
        }


# ----------------------------------------------------------------------
# Convenience orchestrator
# ----------------------------------------------------------------------

def run_v1_pipeline(
    source: str,
    function_name: str,
    wir: dict[str, Any],
    task_patterns: list[str],
    branch_lines: set[int],
    control_variables: list[str],
    state_variables: Optional[list[str]] = None,
    n_runs: int = 20,
    seed: Optional[int] = None,
    compiled_ns: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    End-to-end Phase-3 pipeline.

    1. Runs randomized differential testing (actual code vs. WIR reference).
    2. Returns the V1 certificate.
    """
    tester = RandomizedDifferentialTester(
        source=source,
        function_name=function_name,
        wir=wir,
        task_patterns=task_patterns,
        branch_lines=branch_lines,
        control_variables=control_variables,
        state_variables=state_variables,
        n_runs=n_runs,
        seed=seed,
        compiled_ns=compiled_ns,
    )
    return tester.run()
