from typing import Dict, List, Set, Any, Callable

class OverWeakeningException(Exception):
    pass

class SpecificationRefiner:
    """
    NC-2: Counterexample-Guided Specification Repair (CGSR)
    
    Implements the ISOLATE -> WEAKEN -> SYNTHESIZE loop with a strict 
    over-weakening guard to prevent the property suite from collapsing 
    into a vacuous "accept-all" state.
    """
    
    def __init__(self, property_suite: Dict[str, List[str]], external_eval_fn: Callable[[Dict[str, List[str]]], float]):
        """
        :param property_suite: The tiered LTLf properties.
        :param external_eval_fn: A function that takes a property suite and 
                                 returns the external detection score (e.g. AUC or detection rate).
        """
        self.suite = property_suite
        self.eval_fn = external_eval_fn
        self.baseline_score = self.eval_fn(self.suite)
        
    def repair(self, failing_properties: Set[str], max_regression: float = 0.05) -> Dict[str, List[str]]:
        """
        Repairs the suite by weakening (dropping) the failing properties.
        Rejects the repair if external detection regresses by more than `max_regression`.
        """
        if not failing_properties:
            return self.suite
            
        # ISOLATE & WEAKEN: Create a proposed weakened suite by removing failing properties
        proposed_suite = {}
        for tier, props in self.suite.items():
            proposed_suite[tier] = [p for p in props if p not in failing_properties]
            
        # SYNTHESIZE: Evaluate the proposed suite against the external corpus
        new_score = self.eval_fn(proposed_suite)
        
        # GUARD: Check for over-weakening (H7b)
        regression = self.baseline_score - new_score
        
        if regression > max_regression:
            raise OverWeakeningException(
                f"Repair rejected: Over-weakening guard tripped. "
                f"Regression ({regression:.4f}) exceeds tolerance ({max_regression:.4f}). "
                f"Baseline: {self.baseline_score:.4f}, New: {new_score:.4f}."
            )
            
        # Accept repair
        self.suite = proposed_suite
        self.baseline_score = new_score
        return self.suite
