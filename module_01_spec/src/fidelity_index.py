from typing import Dict, Any, Tuple, Set

class SemanticFidelityIndex:
    """
    Semantic Fidelity Index (SFI) Calculator.
    
    Monotonicity Statement and Assumptions:
    =======================================
    Claim (Empirical Monotonicity): For nested error chains e1 ⊂ e2 (where e2 represents 
    strictly more structural information loss/corruption than e1), the SFI monotonically decreases:
    SFI(spec, e2) <= SFI(spec, e1) + ε (where ε is a small noise tolerance).
    
    Proof/Design Justification:
    To guarantee monotonicity under element-drop (information loss) perturbations, SFI is 
    designed as a normalized intersection-over-original ratio for nodes and edges, rather 
    than a complex combination of Graph Edit Distance (GED) and Jaccard which can behave 
    non-monotonically. 
    
    SFI = (|V_original ∩ V_mutant| + |E_original ∩ E_mutant|) / (|V_original| + |E_original|)
    
    Assumption 1: Information loss is modeled as structural deletion (nodes dropped, edges broken).
    Assumption 2: Node and Edge sets are uniquely identifiable by their structural IDs.
    Under these assumptions, removing an element strictly decreases the numerator while the 
    denominator remains constant, guaranteeing a monotonically decreasing SFI.
    """

    @staticmethod
    def calculate(original_graph: Dict[str, Any], mutant_graph: Dict[str, Any]) -> float:
        """
        Calculates the SFI between the original semantic graph and a mutant graph.
        Returns a value in [0, 1].
        """
        orig_nodes = SemanticFidelityIndex._extract_nodes(original_graph)
        orig_edges = SemanticFidelityIndex._extract_edges(original_graph)
        
        mut_nodes = SemanticFidelityIndex._extract_nodes(mutant_graph)
        mut_edges = SemanticFidelityIndex._extract_edges(mutant_graph)
        
        orig_total = len(orig_nodes) + len(orig_edges)
        if orig_total == 0:
            return 1.0 # Vacuous case

        node_intersect = orig_nodes.intersection(mut_nodes)
        edge_intersect = orig_edges.intersection(mut_edges)
        
        intersect_total = len(node_intersect) + len(edge_intersect)
        
        sfi = intersect_total / orig_total
        return float(sfi)

    @staticmethod
    def _extract_nodes(graph: Dict[str, Any]) -> Set[str]:
        # Using a tuple of (node_id, node_type) to represent a node
        nodes = set()
        for state in graph.get("states", []):
            nodes.add((state.get("node_id"), state.get("node_type")))
        return nodes

    @staticmethod
    def _extract_edges(graph: Dict[str, Any]) -> Set[Tuple[str, str, str]]:
        # Using a tuple of (source, target, condition) to represent an edge
        edges = set()
        for edge in graph.get("edges", []):
            edges.add((edge.get("source_id"), edge.get("target_id"), edge.get("condition", "")))
        return edges
