"""guards.py -- guard-condition flattening to CNF (GuardExtractor).

(Auto-extracted verbatim from the original monolith during modularization.)
"""

from __future__ import annotations

import ast
from typing import Any, Optional
from .models import CNF, Literal
from .helpers import _unparse, _collect_vars


class GuardExtractor:
    """
    Flatten Python boolean expressions into Conjunctive Normal Form (CNF).

    The extractor handles:
    * ``and`` / ``or`` / ``not`` via De Morgan's laws
    * Comparison operator inversion so that every literal is positive
    * Short-circuit semantics encoded as explicit ITE annotations
    * Collection of the typed variable inventory for each literal
    """

    def __init__(self) -> None:
        self.ite_counter: int = 0

    # -- public API ------------------------------------------------------

    def extract(self, node: ast.AST) -> CNF:
        """
        Convert an arbitrary expression AST into CNF.

        Returns a list of clauses where each clause is a list of
        :class:`Literal` objects.
        """
        nnf = self._to_nnf(node)
        return self._nnf_to_cnf(nnf)

    def extract_with_inventory(self, node: ast.AST) -> dict[str, Any]:
        """
        Like :py:meth:`extract` but also returns the variable inventory.
        """
        cnf = self.extract(node)
        inventory: dict[str, list[str]] = {}
        for clause in cnf:
            for lit in clause:
                for v in lit.vars_involved:
                    inventory.setdefault(v, []).append(lit.text)
        return {
            "cnf": [[lit.to_dict() for lit in clause] for clause in cnf],
            "inventory": inventory,
        }

    # -- NNF conversion --------------------------------------------------

    def _to_nnf(self, node: ast.AST, negated: bool = False) -> ast.AST:
        """
        Push negations inward until the tree contains only positive
        literals, ``And``, and ``Or`` nodes.
        """
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return self._to_nnf(node.operand, not negated)

        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                if negated:
                    # not(a and b) -> (not a) or (not b)
                    new_values = [self._to_nnf(v, True) for v in node.values]
                    return ast.BoolOp(op=ast.Or(), values=new_values)
                else:
                    new_values = [self._to_nnf(v, False) for v in node.values]
                    return ast.BoolOp(op=ast.And(), values=new_values)
            elif isinstance(node.op, ast.Or):
                if negated:
                    # not(a or b) -> (not a) and (not b)
                    new_values = [self._to_nnf(v, True) for v in node.values]
                    return ast.BoolOp(op=ast.And(), values=new_values)
                else:
                    new_values = [self._to_nnf(v, False) for v in node.values]
                    return ast.BoolOp(op=ast.Or(), values=new_values)

        if isinstance(node, ast.Compare) and negated:
            return self._invert_compare(node)

        if negated:
            # Generic fallback: wrap in UnaryOp Not
            return ast.UnaryOp(op=ast.Not(), operand=node)

        return node

    @staticmethod
    def _invert_compare(node: ast.Compare) -> ast.Compare:
        """
        Invert every comparator in a comparison chain.

        ``not (x < y)`` → ``x >= y``, etc.
        """
        mapping = {
            ast.Eq: ast.NotEq,
            ast.NotEq: ast.Eq,
            ast.Lt: ast.GtE,
            ast.LtE: ast.Gt,
            ast.Gt: ast.LtE,
            ast.GtE: ast.Lt,
            ast.Is: ast.IsNot,
            ast.IsNot: ast.Is,
            ast.In: ast.NotIn,
            ast.NotIn: ast.In,
        }
        new_ops = []
        for op in node.ops:
            inv = mapping.get(type(op))
            if inv is None:
                # Fallback: wrap whole compare in not
                return ast.UnaryOp(op=ast.Not(), operand=node)  # type: ignore[return-value]
            new_ops.append(inv())
        return ast.Compare(left=node.left, ops=new_ops, comparators=node.comparators)

    # -- CNF conversion --------------------------------------------------

    def _nnf_to_cnf(self, node: ast.AST) -> CNF:
        """Recursively convert a negation-free AST into CNF."""
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                result: CNF = []
                for v in node.values:
                    result.extend(self._nnf_to_cnf(v))
                return result
            elif isinstance(node.op, ast.Or):
                cnfs = [self._nnf_to_cnf(v) for v in node.values]
                return self._distribute_or(cnfs)

        # Atomic literal
        lit = self._make_literal(node)
        return [[lit]]

    def _distribute_or(self, cnfs: list[CNF]) -> CNF:
        """
        Distribute disjunction over conjunction.

        ``(a ∧ b) ∨ (c ∧ d)`` → ``(a ∨ c) ∧ (a ∨ d) ∧ (b ∨ c) ∧ (b ∨ d)``

        We flatten the result so that each element of the cross-product
        becomes a single clause.
        """
        # Each CNF is a list of clauses.  The OR of two CNFs is the
        # cross-product of their clause lists, merging clauses.
        result: CNF = [[]]
        for cnf in cnfs:
            new_result: CNF = []
            for clause_a in result:
                for clause_b in cnf:
                    merged = clause_a + clause_b
                    new_result.append(merged)
            result = new_result
        return result

    def _make_literal(self, node: ast.AST) -> Literal:
        """Create a Literal from an atomic AST node."""
        negated = isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not)
        if negated:
            inner = node.operand
            text = f"not ({_unparse(inner)})"
            vars_involved = _collect_vars(inner)
            return Literal(negated=True, ast_node=inner, text=text, vars_involved=vars_involved)

        text = _unparse(node)
        vars_involved = _collect_vars(node)
        return Literal(negated=False, ast_node=node, text=text, vars_involved=vars_involved)

    # -- short-circuit ITE helpers ---------------------------------------

    def encode_short_circuit(self, node: ast.BoolOp) -> str:
        """
        Produce an explicit ITE string for a BoolOp.

        ``a and b`` → ``ITE(a, b, False)``
        ``a or b``  → ``ITE(a, True, b)``
        """
        if isinstance(node.op, ast.And):
            parts = [_unparse(v) for v in node.values]
            # Right-associate for multi-way And
            result = f"ITE({parts[0]}, {parts[1]}, False)"
            for p in parts[2:]:
                result = f"ITE({p}, {result}, False)"
            return result
        elif isinstance(node.op, ast.Or):
            parts = [_unparse(v) for v in node.values]
            result = f"ITE({parts[0]}, True, {parts[1]})"
            for p in parts[2:]:
                result = f"ITE({p}, True, {result})"
            return result
        return _unparse(node)
