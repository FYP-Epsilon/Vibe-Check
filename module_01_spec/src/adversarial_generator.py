import json
from typing import Dict, List, Any

class AdversarialGenerator:
    """
    Predictive Defense System (LLM Red-Teaming)
    Proactively hallucinates 'deceptive traces' (bypassing business rules)
    and generates strict LTLf killer properties against them.
    """
    def __init__(self):
        # In a real environment, this would initialize an LLM pipeline
        # e.g., self.model = pipeline('text-generation', model='phi-2')
        self.red_team_enabled = True

    def generate_deceptive_traces(self, semantic_graph: Dict[str, Any]) -> List[List[str]]:
        """
        Uses an LLM (simulated here) to find logical loopholes in the BPMN
        and hallucinates adversarial traces that bypass rules.
        """
        states = semantic_graph.get("states", [])
        tasks = [s for s in states if s.get("node_type") == "task"]
        
        deceptive_traces = []
        
        # Simulated LLM hallucination: 
        # "Generate a trace where an end event occurs without a critical task"
        # Or bypassing an explicit gateway check.
        if len(tasks) >= 2:
            # Let's say we have 'Approve' and 'Reject'
            # Hallucinate: Start -> skip Approve -> End
            start_props = [s["atomic_propositions"][0] for s in states if s["node_type"] == "startEvent"]
            end_props = [s["atomic_propositions"][0] for s in states if s["node_type"] == "endEvent"]
            task_props = [t["atomic_propositions"][-1] for t in tasks]
            
            if start_props and end_props and task_props:
                # Deceptive trace: [start, end] skipping tasks
                deceptive_traces.append([start_props[0], end_props[0]])
                
                # Deceptive trace: out of order tasks
                deceptive_traces.append([task_props[-1], task_props[0]])
                
        return deceptive_traces

    def synthesize_killer_properties(self, deceptive_traces: List[List[str]]) -> List[str]:
        """
        Compiles the hallucinated deceptive traces into formal LTLf 
        properties that mathematically forbid them.
        """
        killers = []
        for trace in deceptive_traces:
            if len(trace) >= 2:
                event_a = trace[0]
                event_b = trace[-1]
                # Since the LTLf evaluator doesn't support the Past operator O(...),
                # and Module 03 does not bridge the Next operator X(...),
                # we forbid event_b from ever happening after event_a using G(...).
                killers.append(f"G({event_a} -> !F({event_b}))")
        
        return killers
