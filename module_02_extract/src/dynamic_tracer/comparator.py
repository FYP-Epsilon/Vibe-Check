"""comparator.py -- differential trace comparator (DifferentialComparator).

(Auto-extracted verbatim from the original monolith during modularization.)
"""

from __future__ import annotations

from typing import Any, Callable, Optional, get_type_hints


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
