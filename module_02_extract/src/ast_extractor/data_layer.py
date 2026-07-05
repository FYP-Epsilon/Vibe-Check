"""data_layer.py -- control- vs data-variable classification (WIRDataLayer).

(Auto-extracted verbatim from the original monolith during modularization.)
"""

from __future__ import annotations

import copy
from typing import Any, Optional


class WIRDataLayer:
    """
    Classify variables into *control* (appear in branch conditions) and
    *data* (only used in computations).

    Performs a lightweight reaching-definitions style analysis over the
    CFG so that downstream V2 symbolic execution knows which variables
    must be tracked with full precision.
    """

    def __init__(self, wir: dict[str, Any]) -> None:
        self.wir = wir
        self.control_vars: set[str] = set()
        self.data_vars: set[str] = set()
        self._analyze()

    def _analyze(self) -> None:
        """Scan every WIR node and collect variable usages.

        Recursively descends into function sub-CFGs so that variables
        defined inside functions are also classified.
        """
        def _scan(node_list: list[dict[str, Any]]) -> None:
            for node in node_list:
                self.control_vars.update(node.get("control_vars", []))
                self.data_vars.update(node.get("data_vars", []))

        _scan(self.wir.get("nodes", []))
        for func_wir in self.wir.get("functions", {}).values():
            _scan(func_wir.get("nodes", []))

        # A variable that appears in both sets is *control* (the more
        # restrictive classification takes precedence).
        self.data_vars -= self.control_vars

    def get_classification(self) -> dict[str, list[str]]:
        return {
            "control_variables": sorted(self.control_vars),
            "data_variables": sorted(self.data_vars),
        }

    def annotate_wir(self) -> dict[str, Any]:
        """Return a new WIR with global control/data variable lists."""
        new_wir = copy.deepcopy(self.wir)
        classification = self.get_classification()
        new_wir["control_variables"] = classification["control_variables"]
        new_wir["data_variables"] = classification["data_variables"]
        return new_wir
