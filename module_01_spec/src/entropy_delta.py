import re
from typing import List, Dict, Any, Tuple
from collections import Counter

class EntropyDeltaLocator:
    """
    NC-4 Error Localization (Entropy Delta ΔS).
    
    This implements the bounded-|L| definition for fault localization.
    When a mutant diagram fails a subset of properties (L_fail ⊂ L), this 
    module computes the 'entropy delta' by inspecting the atomic propositions 
    involved in the violated properties to predict the structural element 
    (node/gateway) that was mutated.
    """

    @staticmethod
    def localize_fault(failing_properties: List[str], semantic_graph: Dict[str, Any]) -> List[Tuple[str, float]]:
        """
        Given a list of failing LTLf properties, returns a ranked list of 
        suspected node IDs with their localization score.
        
        Score is based on frequency of atomic proposition involvement in the 
        failing subset (a proxy for ΔS impact).
        """
        if not failing_properties:
            return []

        # 1. Extract all atomic propositions mentioned in the failing properties
        # They are usually in the form: start(NodeID), done(NodeID), or just NodeID
        mentioned_props = []
        
        for prop in failing_properties:
            # Extract all alphanumeric words (with underscores)
            words = re.findall(r'\b[a-zA-Z0-9_]+\b', prop)
            for w in words:
                if w not in ['G', 'F', 'X', 'W', 'U', 'start', 'done']:
                    mentioned_props.append(w)

        # 2. Map propositions back to graph node_ids
        # Build a reverse mapping from atomic_propositions -> node_id
        prop_to_node = {}
        for state in semantic_graph.get("states", []):
            node_id = state.get("node_id")
            for ap in state.get("atomic_propositions", []):
                # Clean ap for matching
                clean_ap = ap.replace("start(", "").replace("done(", "").replace(")", "")
                prop_to_node[clean_ap] = node_id
            # Also map the node_id itself
            prop_to_node[node_id] = node_id

        # 3. Count frequencies (Entropy contribution proxy)
        node_scores = Counter()
        for p in mentioned_props:
            if p in prop_to_node:
                node_id = prop_to_node[p]
                node_scores[node_id] += 1.0
            else:
                node_scores[p] += 1.0

        # 3.5 Common Upstream Attribution
        # If the formula only mentions branches (TaskA, TaskB), the actual fault 
        # might be the gateway splitting them. 
        preds = {}
        for edge in semantic_graph.get("edges", []):
            src = edge.get("source_id")
            tgt = edge.get("target_id")
            if tgt not in preds:
                preds[tgt] = []
            preds[tgt].append(src)

        upstream_scores = Counter()
        # For each predecessor, count how many of its targets were mentioned
        pred_to_mentioned_targets = Counter()
        for node_id in node_scores.keys():
            for p_id in preds.get(node_id, []):
                pred_to_mentioned_targets[p_id] += 1
                
        for p_id, count in pred_to_mentioned_targets.items():
            if count >= 2:
                upstream_scores[p_id] += 2.0 * count
            else:
                upstream_scores[p_id] += 0.2
                
        for node_id, score in upstream_scores.items():
            node_scores[node_id] += score

        # 4. Normalize scores to create a probability/ranking distribution
        total_mentions = sum(node_scores.values())
        ranked_suspects = []
        if total_mentions > 0:
            for node, count in node_scores.most_common():
                ranked_suspects.append((node, count / total_mentions))
                
        return ranked_suspects
