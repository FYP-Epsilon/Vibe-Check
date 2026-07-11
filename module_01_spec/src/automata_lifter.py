import time
import json
from typing import Dict, List, Any
from .formula_normalizer import FormulaNormalizer

try:
    import spot
except ImportError:
    spot = None

class AutomataLifterException(Exception):
    """Exception for Automata Lifter phase failures."""
    pass

class AutomataLifter:
    """
    Phase 4: Automata Lifting.
    Transforms LTLf properties into executable monitors (automata) using SPOT.
    """
    def __init__(self, property_suite: Dict[str, Any], semantic_graph: Dict[str, Any], loop_bound: int = 5, timeout: float = 2.0):
        # We expect a property suite formatted like Phase 3 output
        self.property_suite = property_suite.get("refined_ltlf_property_suite", property_suite)
        self.semantic_graph = semantic_graph
        self.loop_bound = loop_bound
        self.timeout = timeout
        self.monitors = {}
        self.errors = []

    def run_pipeline(self) -> Dict[str, Any]:
        """
        Executes the Phase 4 lifting process.
        """
        if spot is None:
            # We mock the compilation if SPOT is not installed, returning a typed error
            # This handles cases running outside the Docker container.
            self.errors.append({"error": "environment_error", "details": "SPOT library is not installed."})
            return self._build_result()

        for tier, properties in self.property_suite.items():
            if not isinstance(properties, list):
                continue
                
            self.monitors[tier] = []
            for prop in properties:
                if prop == "no killer found":
                    continue
                    
                # 1. Normalize formula to SPOT grammar
                norm_prop = FormulaNormalizer.normalize(prop)
                
                start_time = time.time()
                try:
                    # 2. Parse and Compile LTL formula
                    f = spot.formula(norm_prop)
                    # Translate to monitor automaton
                    aut = f.translate("monitor")
                    
                    if time.time() - start_time > self.timeout:
                        self.errors.append({"error": "timeout", "property": prop})
                        continue
                        
                    self.monitors[tier].append({
                        "original_ltlf": prop,
                        "spot_normalized": norm_prop,
                        "hoa_automaton": aut.to_str('hoa')
                    })
                except Exception as e:
                    self.errors.append({"error": "parser_reject", "property": prop, "details": str(e)})

        # 3. Return the generated monitors and any typed errors
        return self._build_result()

    def _build_result(self) -> Dict[str, Any]:
        return {
            "phase_4_certificate": {
                "status": "PASS" if not self.errors else "FAIL_WITH_ERRORS",
                "monitors_generated": sum(len(m) for m in self.monitors.values()),
                "errors_count": len(self.errors),
                "loop_bound_documented": self.loop_bound
            },
            "monitors": self.monitors,
            "errors": self.errors
        }
