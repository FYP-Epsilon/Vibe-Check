"""registry.py -- Z3 variable registry / sort inference (Z3VariableRegistry).

(Auto-extracted verbatim from the original monolith during modularization.)
"""

from __future__ import annotations

from typing import Any, Optional
import z3


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
        # Reverse map for string tokenization (see SymbolicEvaluator.visit_Constant):
        # a str literal is encoded as an int token for arithmetic constraints, but
        # a solved model gives back only the token -- this lets _z3_to_python
        # decode it back into the original string instead of a bare int.
        self._string_tokens: dict[int, str] = {}

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

    # -- string tokenization -----------------------------------------------

    def register_string_token(self, token: int, literal: str) -> None:
        """Record that *token* encodes *literal* (called from visit_Constant
        every time a string literal is tokenized for Z3)."""
        self._string_tokens[token] = literal

    def resolve_string_token(self, token: int) -> Optional[str]:
        """Decode a solved model token back into its original string, if
        this registry ever tokenized it."""
        return self._string_tokens.get(token)

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
