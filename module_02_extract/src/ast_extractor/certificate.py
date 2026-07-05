"""certificate.py -- V3 syntactic-correctness certificate (V3Certificate).

(Auto-extracted verbatim from the original monolith during modularization.)
"""

from __future__ import annotations

import ast
from typing import Any, Optional


class V3Certificate:
    """
    Generate the Phase-1 syntactic correctness certificate.

    The certificate contains:
    * node_coverage      – fraction of AST statement nodes mapped to WIR
    * edge_coverage      – fraction of control-flow edges preserved
    * guard_success_rate – fraction of branch conditions decomposed into CNF
    * unsupported list   – constructs that could not be modelled
    * abort flag         – set when node_coverage < 0.95
    """

    def __init__(
        self,
        source: str,
        wir: dict[str, Any],
        guard_results: dict[str, Any],
    ) -> None:
        self.source = source
        self.wir = wir
        self.guard_results = guard_results
        self.tree = ast.parse(source)

    # -- public API ------------------------------------------------------

    def generate(self) -> dict[str, Any]:
        """Build and return the certificate dictionary."""
        node_cov = self._compute_node_coverage()
        edge_cov = self._compute_edge_coverage()
        guard_rate = self._compute_guard_success_rate()
        unsupported = self.wir.get("unsupported_constructs", [])

        abort = node_cov < 0.95

        cert = {
            "version": "V3",
            "node_coverage": node_cov,
            "edge_coverage": edge_cov,
            "guard_success_rate": guard_rate,
            "unsupported_constructs": unsupported,
            "abort": abort,
            # NOTE: this is an extraction-fidelity score (how much of the AST
            # was captured in the WIR), not a correctness signal. It must
            # never saturate to 1.0 -- a saturated V3 confidence made the
            # multi-modal OR-composition vacuous (any structurally
            # extractable program passed, regardless of behavior). See
            # MultiModalCertificateComposer.compose, which now treats V3 as
            # a pass/fail gate rather than an OR-composed confidence term.
            "confidence": node_cov,
            "message": (
                "ABORT: node coverage below 0.95 threshold — manual review required."
                if abort else "V3 structural extraction passed quality gate."
            ),
        }
        return cert

    # -- metric helpers --------------------------------------------------

    def _compute_node_coverage(self) -> float:
        """
        Fraction of significant AST nodes that have a corresponding WIR node.

        We count all statement nodes in the original AST (excluding
        expressions nested inside statements) and compare against the
        number of WIR nodes of type ``block``, ``gateway``, ``loop``,
        ``task``, etc.  Function sub-CFGs are included in the count.
        """
        ast_stmt_count = 0
        for child in ast.walk(self.tree):
            if isinstance(child, ast.stmt):
                ast_stmt_count += 1

        def _count_significant(node_list: list[dict[str, Any]]) -> int:
            return sum(
                1 for n in node_list if n["type"] not in ("entry", "exit")
            )

        # Count WIR nodes that are not purely structural (entry/exit)
        wir_count = _count_significant(self.wir.get("nodes", []))
        for func_wir in self.wir.get("functions", {}).values():
            wir_count += _count_significant(func_wir.get("nodes", []))

        if ast_stmt_count == 0:
            return 1.0
        return min(wir_count / ast_stmt_count, 1.0)

    def _compute_edge_coverage(self) -> float:
        """
        Heuristic edge coverage: we assume every conditional statement
        contributes at least two edges.  The ratio of actual edges to
        expected edges gives a rough coverage score.

        Function sub-CFG edges are included in the count.
        """
        edges = list(self.wir.get("edges", []))
        for func_wir in self.wir.get("functions", {}).values():
            edges.extend(func_wir.get("edges", []))
        if not edges:
            return 1.0

        # Count conditional constructs in AST
        expected = 0
        for child in ast.walk(self.tree):
            if isinstance(child, (ast.If, ast.While, ast.For)):
                expected += 2
            elif isinstance(child, ast.Try):
                expected += 2 + len(child.handlers)
            elif isinstance(child, ast.TryStar):
                expected += 2 + len(child.handlers)
            elif isinstance(child, ast.Match):
                expected += len(child.cases) + 1

        if expected == 0:
            return 1.0
        return min(len(edges) / expected, 1.0)

    def _compute_guard_success_rate(self) -> float:
        """
        Fraction of branch conditions that were successfully parsed into
        CNF without falling back to an opaque string.
        """
        guards = self.guard_results
        total = guards.get("total", 0)
        success = guards.get("success", 0)
        if total == 0:
            return 1.0
        return success / total
