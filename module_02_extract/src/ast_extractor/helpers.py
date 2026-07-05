"""helpers.py -- small AST helper utilities.

(Auto-extracted verbatim from the original monolith during modularization.)
"""

from __future__ import annotations

import ast
from typing import Any, Optional


def _unparse(node: ast.AST) -> str:
    """Safe ``ast.unparse`` wrapper."""
    try:
        return ast.unparse(node)
    except Exception:
        return f"<{type(node).__name__}>"


def _extract_name(node: ast.AST) -> Optional[str]:
    """Return a simple variable name, or *None* for complex expressions."""
    if isinstance(node, ast.Name):
        return node.id
    return None


def _collect_vars(node: ast.AST) -> list[str]:
    """Return a sorted, deduplicated list of variable names in *node*."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
    return sorted(names)
