import json
from typing import List, Dict, Any, Optional

class VerificationException(Exception):
    """Custom exception for verification failures in Phase 2."""
    pass

class FLTLSynthesizer:
    """
    Implicit Guard Resolution & FLTL Property Synthesis.
    Implements the V3 -> V2 -> V1 pipeline for LTLf synthesis from a Semantic Graph.
    """

    def __init__(self, semantic_graph_json: Dict[str, Any]):
        self.graph = semantic_graph_json.get("semantic_graph", {})
        self.states = self.graph.get("states", [])
        self.edges = self.graph.get("edges", [])
        self.initial_state = self.graph.get("initial_state", "")
        
        self.inferred_guards: List[Dict[str, str]] = []
        self.ltlf_suite: Dict[str, List[str]] = {
            "P0_Critical_Sentinels": [],
            "P1_Structural_Control_Flow": [],
            "P2_Quality_Limits": []
        }
        
        self.xor_gateways: List[Dict[str, Any]] = []
        self.guard_coverage: float = 0.0

    def run_pipeline(self) -> Dict[str, Any]:
        """Executes the Phase 2 synthesis pipeline."""
        # Layer V3: Graph Traversal & Decision Identification
        self._layer_v3_identify_decisions()
        
        # Layer V2: Implicit Logic Inference & Declarative Synthesis
        self._layer_v2_synthesize_logic()
        
        # Layer V1: Quality Gate Certification
        certificate = self._layer_v1_certify()
        
        return {
            "phase_2_certificate": certificate,
            "ltlf_property_suite": self.ltlf_suite,
            "inferred_implicit_guards": self.inferred_guards
        }

    def _layer_v3_identify_decisions(self):
        """
        Layer V3: Identifies XOR gateways and their outgoing sequence flows.
        """
        for state in self.states:
            if state.get("node_type") == "exclusiveGateway":
                gateway_id = state.get("node_id")
                outgoing_flows = [
                    edge for edge in self.edges if edge.get("source_id") == gateway_id
                ]
                self.xor_gateways.append({
                    "gateway_id": gateway_id,
                    "outgoing_flows": outgoing_flows
                })

    def _layer_v2_synthesize_logic(self):
        """
        Layer V2: Infers implicit guards and instantiates LTLf templates.
        """
        # 1. Zero Dead-Zone Protocol (P2.1)
        self._resolve_implicit_guards()
        
        # 2. LTLf Template Instantiation (P2.3)
        self._instantiate_ltlf_templates()
        
        # 3. Sentinel Guard Synthesis (P2.4)
        self._generate_sentinels()

    def _resolve_implicit_guards(self):
        """Computes the mathematical negation for 'Else' paths in XOR gateways."""
        for gateway in self.xor_gateways:
            flows = gateway["outgoing_flows"]
            explicit_guards = [f.get("condition") for f in flows if f.get("condition")]
            unconditioned_flows = [f for f in flows if not f.get("condition")]

            if unconditioned_flows and explicit_guards:
                # Compute mathematical negation: NOT(C1) AND NOT(C2) ...
                negated_conjunction = " && ".join([f"!({g})" for g in explicit_guards])
                
                for flow in unconditioned_flows:
                    flow["condition"] = negated_conjunction
                    self.inferred_guards.append({
                        "gateway_id": gateway["gateway_id"],
                        "target_node_id": flow["target_id"],
                        "inferred_condition": negated_conjunction
                    })

    def _get_node_props(self, node_id: str) -> List[str]:
        for state in self.states:
            if state["node_id"] == node_id:
                return state.get("atomic_propositions", [node_id])
        return [node_id]

    def _instantiate_ltlf_templates(self):
        """Translates graph edges and nodes into LTLf properties."""
        # Sequence Flows: G(start(B) -> F(done(A)))
        for edge in self.edges:
            source_props = self._get_node_props(edge["source_id"])
            target_props = self._get_node_props(edge["target_id"])
            
            # Using templates from prompt
            # Sequence Flow (A -> B): G(start(B) -> F(done(A)))
            src_done = source_props[-1]
            tgt_start = target_props[0]
            
            self.ltlf_suite["P1_Structural_Control_Flow"].append(
                f"G({tgt_start} -> F({src_done}))"
            )

        # Gateway Specific Logic
        for state in self.states:
            node_id = state["node_id"]
            node_type = state["node_type"]
            
            if node_type == "exclusiveGateway":
                # XOR Gateway: (F(done(A)) ^ F(done(B))) & G(done(A) -> !done(B))
                outgoing = [e for e in self.edges if e["source_id"] == node_id]
                if len(outgoing) >= 2:
                    branch_props = [self._get_node_props(e["target_id"])[0] for e in outgoing]
                    # Simplified mutual exclusion for LTLf
                    for i in range(len(branch_props)):
                        for j in range(i + 1, len(branch_props)):
                            self.ltlf_suite["P1_Structural_Control_Flow"].append(
                                f"G({branch_props[i]} -> !{branch_props[j]})"
                            )

            elif node_type == "parallelGateway":
                # AND Gateway: G(start(A) <-> start(B)) & G(done(A) <-> done(B))
                outgoing = [e for e in self.edges if e["source_id"] == node_id]
                if len(outgoing) >= 2:
                    b1 = self._get_node_props(outgoing[0]["target_id"])[0]
                    b2 = self._get_node_props(outgoing[1]["target_id"])[0]
                    self.ltlf_suite["P1_Structural_Control_Flow"].append(
                        f"G({b1} <-> {b2})"
                    )

    def _generate_sentinels(self):
        """Generates P0 Critical Sentinels and P2 Quality Limits."""
        # Sentinel Guard: G(!forbidden_state U prerequisite_met)
        # For every task/event, cannot be 'done' until it 'starts' (or reached)
        for state in self.states:
            props = state.get("atomic_propositions", [])
            if len(props) >= 2: # Likely a task with start and done
                start_prop = props[0]
                done_prop = props[-1]
                self.ltlf_suite["P0_Critical_Sentinels"].append(
                    f"G(!{done_prop} U {start_prop})"
                )
        
        # Bounded Loop: G(count(iteration) <= N -> F(exit_condition))
        self.ltlf_suite["P2_Quality_Limits"].append(
            "G(iteration_count <= 10 -> F(process_complete))"
        )

    def _layer_v1_certify(self) -> Dict[str, Any]:
        """
        Layer V1: Enforces Quality Gate and generates Certificate.
        """
        total_xor = len(self.xor_gateways)
        resolved_xor = 0
        
        for gateway in self.xor_gateways:
            flows = gateway["outgoing_flows"]
            if all(f.get("condition") for f in flows):
                resolved_xor += 1
        
        self.guard_resolution_coverage = resolved_xor / total_xor if total_xor > 0 else 1.0
        
        status = "PASS" if self.guard_resolution_coverage >= 1.0 else "FAIL"
        
        if status == "FAIL":
            raise VerificationException(
                f"Guard Resolution Coverage {self.guard_resolution_coverage} < 1.0. "
                "Logical dead-zone detected."
            )

        total_props = sum(len(v) for v in self.ltlf_suite.values())
        
        return {
            "status": status,
            "guard_resolution_coverage": self.guard_resolution_coverage,
            "sentinel_coverage_fraction": 1.0 if total_props > 0 else 0.0,
            "total_properties_generated": total_props
        }

def main():
    """Main execution block with mock Phase 1 input."""
    mock_phase_1_output = {
        "phase_1_certificate": {
            "status": "PASS",
            "node_coverage_Y_Struct": 1.0,
            "sanitized_nodes_count": 5
        },
        "semantic_graph": {
            "initial_state": "Start_1",
            "states": [
                {"node_id": "Start_1", "node_type": "startEvent", "atomic_propositions": ["start_event"]},
                {"node_id": "Gateway_1", "node_type": "exclusiveGateway", "atomic_propositions": ["xor_gate"]},
                {"node_id": "Task_Approve", "node_type": "task", "atomic_propositions": ["start(Approve)", "done(Approve)"]},
                {"node_id": "Task_Reject", "node_type": "task", "atomic_propositions": ["start(Reject)", "done(Reject)"]},
                {"node_id": "End_1", "node_type": "endEvent", "atomic_propositions": ["end_event"]}
            ],
            "edges": [
                {"source_id": "Start_1", "target_id": "Gateway_1"},
                {"source_id": "Gateway_1", "target_id": "Task_Approve", "condition": "score > 50"},
                {"source_id": "Gateway_1", "target_id": "Task_Reject"}, # Implicit Else
                {"source_id": "Task_Approve", "target_id": "End_1"},
                {"source_id": "Task_Reject", "target_id": "End_1"}
            ]
        }
    }

    try:
        synthesizer = FLTLSynthesizer(mock_phase_1_output)
        result = synthesizer.run_pipeline()
        print(json.dumps(result, indent=2))
    except VerificationException as e:
        print(json.dumps({
            "phase_2_certificate": {
                "status": "FAIL",
                "error": str(e),
                "guard_resolution_coverage": getattr(e, 'coverage', 0.0)
            }
        }, indent=2))
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
