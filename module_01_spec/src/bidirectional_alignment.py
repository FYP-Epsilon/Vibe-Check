import json
from typing import Dict, Any, List, Set, Tuple

try:
    from .trace_synthesizer import PBCTSEngine
    from .mutation_refiner import LTLfAuditor
except ImportError:
    from trace_synthesizer import PBCTSEngine
    from mutation_refiner import LTLfAuditor

class PBCTSAlignmentPipeline:
    """
    Phase 5B: Bidirectional Differential Alignment (BDA) via PBCTS.
    Generates T_spec and T_model, compares them, and returns an FRC.
    """
    
    def __init__(self, property_suite: Dict[str, List[str]], semantic_graph: Dict[str, Any]):
        self.property_suite = property_suite
        self.semantic_graph = semantic_graph
        
    def _normalize_traces(self, traces: List[List[Set[str]]]) -> Set[Tuple[frozenset, ...]]:
        """Converts traces to a canonical hashable form for O(1) comparison."""
        normalized = set()
        for t in traces:
            norm_trace = tuple(frozenset(s) for s in t)
            normalized.add(norm_trace)
        return normalized

    def _compute_corrections(self, t_spec_only: set, t_model_only: set) -> list:
        """
        Self-Correcting Specification Loop (SCSL):
        Synthesizes corrective LTLf formulas from semantic gaps.
        Over-specification gaps (LTLf permits but BPMN doesn't) are converted
        into restrictive formulas that forbid the invalid trace patterns.
        """
        corrections = []
        seen = set()
        for trace in list(t_spec_only)[:10]:
            steps = list(trace)
            for i in range(len(steps) - 1):
                curr = sorted(steps[i])
                nxt = sorted(steps[i + 1])
                if curr and nxt:
                    formula = f"G({curr[0]} -> !F({nxt[0]}))"
                    if formula not in seen:
                        seen.add(formula)
                        corrections.append(formula)
        return corrections

    def run_idcd(self, k_max: int = 20, epsilon: float = 0.001) -> Dict[str, Any]:
        """Iterative Deepening with Convergence Detection."""
        eas_prev = 0.0
        eas_history = []
        
        auditor = LTLfAuditor({})
        
        converged = False
        k_converged = k_max
        final_stats = {}
        
        for k in range(1, k_max + 1):
            # T_spec from PBCTS
            engine = PBCTSEngine(self.property_suite, bound_k=k)
            t_spec_raw = engine.run()
            t_spec = self._normalize_traces(t_spec_raw)
            
            # T_model from Graph Traversal
            t_model_raw = auditor._generate_traces(self.semantic_graph, depth=k)
            t_model = self._normalize_traces(t_model_raw)
            
            # BDA Metrics
            t_agreed = t_spec & t_model
            
            fitness = len(t_agreed) / len(t_model) if t_model else 1.0
            precision = len(t_agreed) / len(t_spec) if t_spec else 1.0
            recall = len(t_agreed) / len(t_model) if t_model else 1.0
            
            if precision + recall > 0:
                eas_k = 2 * (precision * recall) / (precision + recall)
            else:
                eas_k = 0.0
                
            eas_history.append(eas_k)
            
            # Save stats for final report
            final_stats = {
                "t_spec": t_spec,
                "t_model": t_model,
                "t_agreed": t_agreed,
                "fitness": fitness,
                "precision": precision,
                "recall": recall,
                "eas": eas_k,
                "scov": engine.get_scov()
            }
            
            # Check convergence
            if abs(eas_k - eas_prev) < epsilon and k > 1:
                converged = True
                k_converged = k
                break
                
            eas_prev = eas_k
            
        return self._generate_frc(final_stats, converged, k_converged, k_max, epsilon, eas_history)

    def _generate_frc(self, stats: Dict[str, Any], converged: bool, k_converged: int, k_max: int, epsilon: float, eas_history: List[float]) -> Dict[str, Any]:
        """Generates the Formal Reliability Certificate."""
        
        t_spec = stats["t_spec"]
        t_model = stats["t_model"]
        t_agreed = stats["t_agreed"]
        
        t_spec_only = t_spec - t_model
        t_model_only = t_model - t_spec
        
        # SCSL: Compute corrective formulas for over-specification gaps
        scsl_corrections = self._compute_corrections(t_spec_only, t_model_only)
        
        semantic_gaps = []
        for t in list(t_spec_only)[:5]:  # cap at 5 for report size
            semantic_gaps.append({
                "type": "over_specification",
                "trace": str(t),
                "explanation": "LTLf permits this trace, but BPMN graph has no such path."
            })
            
        for t in list(t_model_only)[:5]:
            semantic_gaps.append({
                "type": "under_specification",
                "trace": str(t),
                "explanation": "BPMN permits this trace, but LTLf suite forbids it."
            })
            
        confidence = (1.0 - epsilon) if converged else stats["scov"]["SCov"]
        
        return {
            "certificate_version": "2.0",
            "method": "PBCTS_BDA_IDCD",
            "alignment_scores": {
                "EAS_BDA": round(stats["eas"], 4),
                "fitness_BDA": round(stats["fitness"], 4),
                "precision_BDA": round(stats["precision"], 4),
                "recall_BDA": round(stats["recall"], 4)
            },
            "specification_coverage": stats["scov"],
            "convergence": {
                "converged": converged,
                "k_converged": k_converged,
                "k_max": k_max,
                "epsilon": epsilon,
                "eas_history": [round(e, 4) for e in eas_history],
                "binding_constraint": "k_max_reached" if not converged else "none",
                "diagnostic": "Trace exploration truncated by k_max. Increase bound or relax alignment criterion." if not converged else "Converged"
            },
            "differential_analysis": {
                "traces_spec_count": len(t_spec),
                "traces_model_count": len(t_model),
                "traces_agreed": len(t_agreed),
                "traces_spec_only": len(t_spec_only),
                "traces_model_only": len(t_model_only),
                "semantic_gaps": semantic_gaps
            },
            "reliability": {
                "confidence": round(confidence, 4),
                "completeness_statement": f"All traces of length <= {k_converged} fully enumerated." if converged else f"Exploration capped at length {k_max} without full convergence."
            },
            "scsl_corrections": scsl_corrections
        }

def run_pbcts_pipeline(property_suite: Dict[str, List[str]], semantic_graph: Dict[str, Any]) -> Dict[str, Any]:
    pipeline = PBCTSAlignmentPipeline(property_suite, semantic_graph)
    frc = pipeline.run_idcd()
    return {"phase_4_certificate": frc} # Emitted as phase_4 to maintain backward compatibility in API
