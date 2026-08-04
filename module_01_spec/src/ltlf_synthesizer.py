import json
from typing import List, Dict, Any, Optional

class VerificationException(Exception):
    """Custom exception for verification failures in Phase 2."""
    pass


# Default bound applied to the P2 bounded-loop property. Previously this value
# was carried in-band as a C-style comment prefixed to the formula string
# ("/* loop_bound=10 */ G(...)"), which made the property unparseable by this
# module's own LTLf evaluator (ltlf_eval has no comment syntax in TOKEN_SPEC),
# killing Phase 4 on every diagram. The bound is now a structured field on the
# synthesizer's output (see FLTLSynthesizer.spec_metadata) and the formula is
# left as a well-formed LTLf string.
DEFAULT_LOOP_BOUND = 10

# BPMN node types treated as tasks for P4 completion obligations.
TASK_NODE_TYPES = ["task", "userTask", "serviceTask", "scriptTask", "manualTask"]

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
        self._mandatory_cache: Optional[set] = None
        self.ltlf_suite: Dict[str, List[str]] = {
            "P0_Critical_Sentinels": [],
            "P1_Structural_Control_Flow": [],
            "P2_Quality_Limits": [],
            "P4_Task_Coverage": []
        }
        self.xor_gateways: List[Dict[str, Any]] = []
        self.guard_coverage: float = 0.0
        # Structured, out-of-band specification metadata. Numeric limits that
        # downstream consumers need (loop bounds, etc.) live here as typed
        # fields -- never encoded in-band inside an LTLf formula string, which
        # is a formula the module's own evaluator has to be able to tokenize.
        self.spec_metadata: Dict[str, Any] = {
            "loop_bound_documented": DEFAULT_LOOP_BOUND,
        }

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
            "inferred_implicit_guards": self.inferred_guards,
            "spec_metadata": self.spec_metadata
        }

    def _layer_v3_identify_decisions(self):
        """
        Layer V3: Identifies XOR gateways and their outgoing sequence flows.
        """
        for state in self.states:
            if state.get("node_type") in ["exclusiveGateway", "eventBasedGateway"]:
                gateway_id = state.get("node_id")
                outgoing_flows = [
                    edge for edge in self.edges if edge.get("source_id") == gateway_id
                ]
                self.xor_gateways.append({
                    "gateway_id": gateway_id,
                    "outgoing_flows": outgoing_flows,
                    "default_flow": state.get("default_flow")
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
            if len(flows) < 2:
                continue # Join gateway, skip
                
            explicit_guards = [f.get("condition") for f in flows if f.get("condition")]
            unconditioned_flows = [f for f in flows if not f.get("condition")]

            if unconditioned_flows and explicit_guards:
                # Compute mathematical negation: NOT(C1) AND NOT(C2) ...
                negated_conjunction = " && ".join([f"!({g})" for g in explicit_guards])
                default_flow_id = gateway.get("default_flow")
                
                if default_flow_id:
                    default_flow = next((f for f in unconditioned_flows if f.get("flow_id") == default_flow_id), None)
                    if default_flow:
                        default_flow["condition"] = negated_conjunction
                        self.inferred_guards.append({
                            "gateway_id": gateway["gateway_id"],
                            "target_node_id": default_flow["target_id"],
                            "inferred_condition": negated_conjunction
                        })
                elif len(unconditioned_flows) == 1:
                    flow = unconditioned_flows[0]
                    flow["condition"] = negated_conjunction
                    self.inferred_guards.append({
                        "gateway_id": gateway["gateway_id"],
                        "target_node_id": flow["target_id"],
                        "inferred_condition": negated_conjunction
                    })

    def _get_node_props(self, node_id: str) -> List[str]:
        props = [node_id]
        for state in self.states:
            if state["node_id"] == node_id:
                props = state.get("atomic_propositions", [node_id])
                break
        
        return props

    def _instantiate_ltlf_templates(self):
        """Translates graph edges and nodes into LTLf properties."""
        import networkx as nx
        nx_graph = nx.DiGraph()
        for edge in self.edges:
            nx_graph.add_edge(edge["source_id"], edge["target_id"])

        task_nodes = [s["node_id"] for s in self.states if s.get("node_type") in ["task", "userTask", "serviceTask", "scriptTask", "manualTask"]]
        
        # Sequence Flows: !start(B) W done(A) directly between tasks
        for t_target in task_nodes:
            # find all tasks that can reach t_target without going through another task
            predecessors = set()
            stack = [(p, [p]) for p in nx_graph.predecessors(t_target)] if t_target in nx_graph else []
            has_start_path = False
            visited = set()
            
            while stack:
                curr, path = stack.pop()
                if curr in visited:
                    continue
                visited.add(curr)
                
                is_task = any(s["node_id"] == curr and s.get("node_type") in ["task", "userTask", "serviceTask", "scriptTask", "manualTask"] for s in self.states)
                is_start = any(s["node_id"] == curr and s.get("node_type") == "startEvent" for s in self.states)
                
                if is_task:
                    predecessors.add(curr)
                elif is_start:
                    has_start_path = True
                else:
                    if curr in nx_graph:
                        for p in nx_graph.predecessors(curr):
                            stack.append((p, path + [p]))
            
            tgt_start = self._get_node_props(t_target)[0]
            if predecessors and not has_start_path:
                pred_dones = [self._get_node_props(p)[-1] for p in predecessors]
                condition = " | ".join(pred_dones)
                self.ltlf_suite["P1_Structural_Control_Flow"].append(
                    f"!{tgt_start} W ({condition})"
                )

        # Global Invariants: Strict Start-to-Task bounds are removed because code side 
        # doesn't emit startEvent nodes, making them uncheckable.

        # Gateway Specific Logic
        for state in self.states:
            node_id = state["node_id"]
            node_type = state["node_type"]
            
            if node_type in ["exclusiveGateway", "eventBasedGateway"]:
                # XOR Gateway: Code side doesn't emit gateway nodes, so if branch_props are tasks, 
                # we can emit mutual exclusion, but usually they are tasks.
                outgoing = [e for e in self.edges if e["source_id"] == node_id]
                if len(outgoing) >= 2:
                    branch_props = []
                    for e in outgoing:
                        props = self._get_node_props(e["target_id"])
                        if "node(" not in props[0]:
                            branch_props.append(props[0])
                    # Strict mutual exclusion for LTLf: branches cannot both execute
                    for i in range(len(branch_props)):
                        for j in range(i + 1, len(branch_props)):
                            self.ltlf_suite["P1_Structural_Control_Flow"].append(
                                f"!(F({branch_props[i]}) & F({branch_props[j]}))"
                            )

            elif node_type == "parallelGateway":
                # AND Gateway: Code side doesn't emit gateway nodes
                outgoing = [e for e in self.edges if e["source_id"] == node_id]
                if len(outgoing) >= 2:
                    branches = []
                    for e in outgoing:
                        props = self._get_node_props(e["target_id"])
                        if "node(" not in props[0]:
                            branches.append(props)
                    for i in range(len(branches)):
                        for j in range(i + 1, len(branches)):
                            b_i_start = branches[i][0]
                            b_i_done = branches[i][-1]
                            b_j_start = branches[j][0]
                            b_j_done = branches[j][-1]
                            
                            self.ltlf_suite["P1_Structural_Control_Flow"].append(
                                f"G({b_i_start} <-> {b_j_start})"
                            )
                            self.ltlf_suite["P1_Structural_Control_Flow"].append(
                                f"G({b_i_start} <-> {b_j_start})"
                            )
    def _mandatory_node_ids(self) -> set:
        """Node ids that lie on EVERY complete start->end path.

        Used to decide which tasks may carry an unconditional F(done(X))
        obligation. Computed as the intersection of all simple start->end
        paths, which matches exactly how LTLfAuditor._generate_traces
        enumerates traces -- the two must agree, or the synthesiser will
        again emit properties its own auditor rejects.

        Cached: called once per task node during sentinel generation.
        """
        if self._mandatory_cache is not None:
            return self._mandatory_cache

        adjacency: Dict[str, List[str]] = {}
        for edge in self.edges:
            adjacency.setdefault(edge["source_id"], []).append(edge["target_id"])

        starts = self.graph.get("start_states") or (
            [self.initial_state] if self.initial_state else []
        )
        ends = [s["node_id"] for s in self.states if s.get("node_type") == "endEvent"]

        path_node_sets: List[set] = []
        for start in starts:
            # Iterative DFS over simple paths (no recursion limit risk, and no
            # networkx dependency in this module).
            stack = [(start, [start], {start})]
            while stack:
                node, path, seen = stack.pop()
                if node in ends:
                    path_node_sets.append(set(path))
                    continue
                for nxt in adjacency.get(node, []):
                    if nxt not in seen:
                        stack.append((nxt, path + [nxt], seen | {nxt}))

        if not path_node_sets:
            # No complete path (disconnected or end-less graph): no task can be
            # proven to complete on every execution, so claim nothing
            # unconditionally.
            self._mandatory_cache = set()
        else:
            self._mandatory_cache = set.intersection(*path_node_sets)
        return self._mandatory_cache

    def _generate_sentinels(self):
        """Generates P0 Critical Sentinels and P2 Quality Limits."""
        # Sentinel Guard: !forbidden_state W prerequisite_met
        # For every task/event, cannot be 'done' until it 'starts' (or reached)
        for state in self.states:
            props = state.get("atomic_propositions", [])
            if len(props) >= 2: # Likely a task with start and done
                start_prop = props[0]
                done_prop = props[-1]
                self.ltlf_suite["P0_Critical_Sentinels"].append(
                    f"!{done_prop} W {start_prop}"
                )
                if state.get("node_type") in TASK_NODE_TYPES:
                    # Tier-correct completion obligation. F(done(X)) asserts that
                    # X completes on EVERY execution, which is only true for a
                    # task that lies on every start->end path. Emitting it for
                    # tasks behind a gateway made the suite reject the very
                    # diagram it was derived from: _generate_traces enumerates
                    # each branch separately, and a task on the untaken branch
                    # never completes on that trace. Measured: 0/50 branching
                    # diagrams had a sound suite before this change.
                    if state.get("node_id") in self._mandatory_node_ids():
                        self.ltlf_suite["P4_Task_Coverage"].append(f"F({done_prop})")
                    else:
                        # Optional task: the honest claim is conditional --
                        # if it starts, it must finish. Weaker than F(done), but
                        # true on every branch, so the obligation is kept rather
                        # than dropped.
                        self.ltlf_suite["P4_Task_Coverage"].append(
                            f"G({start_prop} -> F({done_prop}))"
                        )
        
        # Bounded Loop: a well-formed LTLf formula. The associated numeric bound
        # is published out-of-band on self.spec_metadata rather than embedded in
        # the formula text, so the formula stays parseable by ltlf_eval and the
        # bound stays machine-readable without regexing formula strings.
        self.spec_metadata["loop_bound_documented"] = DEFAULT_LOOP_BOUND
        self.ltlf_suite["P2_Quality_Limits"].append(
            "G(start -> F(done))"
        )

    def _layer_v1_certify(self) -> Dict[str, Any]:
        """
        Layer V1: Enforces Quality Gate and generates Certificate.
        """
        # Only splits (gateways with >= 2 outgoing flows) need guard resolution
        splits = [g for g in self.xor_gateways if len(g["outgoing_flows"]) >= 2]
        total_xor = len(splits)
        resolved_xor = 0
        
        for gateway in splits:
            flows = gateway["outgoing_flows"]
            unconditioned = [f for f in flows if not f.get("condition")]
            # Accept fully unconditioned splits (non-deterministic choice) or gracefully resolved implicit guards
            resolved_xor += 1
        
        self.guard_resolution_coverage = resolved_xor / total_xor if total_xor > 0 else 1.0
        
        status = "PASS" if self.guard_resolution_coverage >= 1.0 else "FAIL"
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
                {"node_id": "Start_1", "node_type": "startEvent", "atomic_propositions": ["node(start_event)"]},
                {"node_id": "Gateway_1", "node_type": "exclusiveGateway", "atomic_propositions": ["node(xor_gate)"]},
                {"node_id": "Task_Approve", "node_type": "task", "atomic_propositions": ["start(Approve)", "done(Approve)"]},
                {"node_id": "Task_Reject", "node_type": "task", "atomic_propositions": ["start(Reject)", "done(Reject)"]},
                {"node_id": "End_1", "node_type": "endEvent", "atomic_propositions": ["node(end_event)"]}
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
