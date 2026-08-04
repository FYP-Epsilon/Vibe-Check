from typing import List, Dict, Set, Any, Tuple
import copy

try:
    from .ltlf_progression import (
        parse, progress, simplify, extract_obligations, 
        is_satisfied_at_end, TRUE, FALSE, LTLfFormula
    )
except ImportError:
    from ltlf_progression import (
        parse, progress, simplify, extract_obligations, 
        is_satisfied_at_end, TRUE, FALSE, LTLfFormula
    )

class PBCTSEngine:
    """
    Progression-Based Constructive Trace Synthesizer (PBCTS).
    Generates execution traces directly from LTLf property suites.
    """
    
    def __init__(self, property_suite: Dict[str, List[str]], bound_k: int, max_traces: int = 200):
        self.property_suite = property_suite
        self.bound_k = bound_k
        self.max_traces = max_traces
        self.ap: Set[str] = set()
        
        self.scov_stats = {
            "nodes_visited": 0,
            "nodes_total": 0,
            "branches_exercised": 0,
            "branches_total": 0,
            "depth_reached": 0
        }
        self._progress_cache: Dict[Tuple[LTLfFormula, frozenset], LTLfFormula] = {}
        
    def run(self) -> List[List[Set[str]]]:
        formulas_str = []
        for suite, formulas in self.property_suite.items():
            formulas_str.extend(formulas)
            
        if not formulas_str:
            return []
            
        # Parse all formulas
        parsed_formulas = [parse(f) for f in formulas_str]
        
        # Conjoin all formulas
        phi = parsed_formulas[0]
        for i in range(1, len(parsed_formulas)):
            phi = LTLfFormula(op="and", left=phi, right=parsed_formulas[i])
            
        phi = simplify(phi)
        self.ap = self._extract_all_ap(phi)
        
        results = []
        self._enumerate(phi, self.bound_k, [], results)
        
        return results
        
    def _extract_all_ap(self, node: LTLfFormula) -> Set[str]:
        if not node:
            return set()
        if node.op == "atom":
            return {node.atom}
        ap = set()
        if node.left: ap |= self._extract_all_ap(node.left)
        if node.right: ap |= self._extract_all_ap(node.right)
        return ap
        
    def _enumerate(self, phi: LTLfFormula, steps_remaining: int, trace_so_far: List[Set[str]], results: List[List[Set[str]]]):
        self.scov_stats["nodes_total"] += 1
        
        if len(results) >= self.max_traces:
            return
            
        phi = simplify(phi)
        
        if phi.op == "TRUE":
            self.scov_stats["nodes_visited"] += 1
            results.append(trace_so_far)
            return
            
        if phi.op == "FALSE":
            self.scov_stats["nodes_visited"] += 1
            return
            
        if steps_remaining == 0:
            self.scov_stats["nodes_visited"] += 1
            if is_satisfied_at_end(phi):
                results.append(trace_so_far)
            return
            
        must_true, must_false, free = extract_obligations(phi)
        
        if must_true & must_false:
            self.scov_stats["nodes_visited"] += 1
            return
            
        self.scov_stats["nodes_visited"] += 1
        num_branches = 1 << len(free)
        self.scov_stats["branches_total"] += num_branches
        
        free_list = list(free)
        for i in range(num_branches):
            if len(results) >= self.max_traces:
                break
                
            subset = set()
            for j in range(len(free_list)):
                if (i & (1 << j)):
                    subset.add(free_list[j])
                    
            P = must_true | subset
            # BPMN model assumes interleaving semantics (at most one proposition active at a time)
            if len(P) > 1:
                continue
            
            P_frozen = frozenset(P)
            
            cache_key = (phi, P_frozen)
            if cache_key in self._progress_cache:
                phi_next = self._progress_cache[cache_key]
            else:
                phi_next = progress(phi, P)
                phi_next = simplify(phi_next)
                self._progress_cache[cache_key] = phi_next
            
            self.scov_stats["branches_exercised"] += 1
            if len(trace_so_far) + 1 > self.scov_stats["depth_reached"]:
                self.scov_stats["depth_reached"] = len(trace_so_far) + 1
                
            self._enumerate(phi_next, steps_remaining - 1, trace_so_far + [P], results)
            
    def get_scov(self) -> Dict[str, float]:
        """Returns the Specification Coverage (SCov) metrics."""
        if self.scov_stats["nodes_total"] == 0:
            scov_node = 1.0
        else:
            scov_node = self.scov_stats["nodes_visited"] / self.scov_stats["nodes_total"]
        
        if self.scov_stats["branches_total"] == 0:
            scov_branch = 1.0
        else:
            scov_branch = self.scov_stats["branches_exercised"] / self.scov_stats["branches_total"]
            
        scov_depth = self.scov_stats["depth_reached"] / self.bound_k if self.bound_k > 0 else 1.0
        
        scov = (0.4 * scov_node) + (0.4 * scov_branch) + (0.2 * scov_depth)
        
        return {
            "SCov": round(scov, 4),
            "SCov_node": round(scov_node, 4),
            "SCov_branch": round(scov_branch, 4),
            "SCov_depth": round(scov_depth, 4),
            "obligation_nodes_visited": self.scov_stats["nodes_visited"],
            "obligation_nodes_total": self.scov_stats["nodes_total"]
        }
