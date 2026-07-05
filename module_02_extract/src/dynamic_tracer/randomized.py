"""randomized.py -- randomized differential tester (RandomizedDifferentialTester).

(Auto-extracted verbatim from the original monolith during modularization.)
"""

from __future__ import annotations

import ast
import copy
import inspect
import random
from typing import Any, Callable, Optional, get_type_hints
from .comparator import DifferentialComparator
from .safe_exec import SAFE_BUILTINS
from .interpreter import WIRReferenceInterpreter
from .collector import WIRTraceCollector


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
        # Stub/task names (besides the entry function itself) the reference
        # interpreter should observe as synthetic task_entry/task_exit
        # events (E2) -- lets stub-call assignments show up in the expected
        # trace instead of being invisible WIR block statements.
        self._stub_task_names: set[str] = set(task_patterns) - {function_name}
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
        # String literal pool for guard-varying str params (D1): the empty
        # string alone means EVERY str param gets the identical input on
        # every run, collapsing input_coverage_score to 1/n_runs regardless
        # of program correctness. See [[session_2026_07_04_t1_t7_implementation]].
        self._string_pool = self._extract_string_pool()

    def _extract_arg_names(self) -> list[str]:
        tree = ast.parse(self.source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == self.function_name:
                    return [a.arg for a in node.args.args]
        return []

    def _extract_string_pool(self) -> list[str]:
        """Every string literal compared against something in the source --
        these are the guard-controlling values (e.g. "high", "urgent") that
        an input actually needs to hit to exercise both sides of a branch."""
        pool: set[str] = set()
        try:
            tree = ast.parse(self.source)
        except SyntaxError:
            return []
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                for side in (node.left, *node.comparators):
                    if isinstance(side, ast.Constant) and isinstance(side.value, str):
                        pool.add(side.value)
        return sorted(pool)

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
                # Sample from the guard-literal pool (so both sides of every
                # string guard actually get exercised) plus "" and a random
                # non-matching junk string (so unguarded/else paths still
                # get hit too). A uniformly random string alone would almost
                # never equal a specific guard literal like "high".
                choices = self._string_pool + ["", f"junk_{random.randint(0, 10**6)}"]
                inputs[param_name] = random.choice(choices)
            elif ann is dict or origin is dict:
                inputs[param_name] = {
                    f"role_{i}": random.randint(1, 5)
                    for i in range(random.randint(1, 3))
                }
            elif ann is list or origin is list:
                inputs[param_name] = [
                    f"action_{random.randint(1, 5)}"
                    for _ in range(random.randint(1, 3))
                ]
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
        # Share the tester's own compiled namespace (stub defs + SAFE_BUILTINS)
        # so WIR statements that call a task-API stub actually execute instead
        # of silently NameError-ing (see WIRReferenceInterpreter.exec_env), and
        # observe those calls as task events (E2) so they're visible in the trace.
        interpreter = WIRReferenceInterpreter(
            self.wir, exec_env=self._compiled_ns, task_names=self._stub_task_names
        )
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
