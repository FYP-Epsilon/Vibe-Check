import time
import json
import threading
import os
from typing import Dict, List, Any, Set, Optional, Tuple

import networkx as nx

try:
    from .formula_normalizer import FormulaNormalizer
except ImportError:
    from formula_normalizer import FormulaNormalizer

try:
    from .ltlf_eval import evaluate_ltlf
except ImportError:
    from ltlf_eval import evaluate_ltlf

try:
    import spot
except ImportError:
    spot = None




class AutomataLifter:
    """
    Phase 4: Automata-Theoretic Lifting via SPOT.

    Compiles validated LTLf properties into deterministic finite automata,
    performs bidirectional language-inclusion checks against the BPMN source
    graph, computes Graph Edit Distance structural diagnostics, and exports
    HOA-format monitors for Module 03 consumption.
    """

    def __init__(
        self,
        property_suite: Dict[str, Any],
        semantic_graph: Dict[str, Any],
        loop_bound: int = 5,
        timeout: float = 2.0,
    ):
        # Accept both raw suite and Phase-3 wrapped format
        self.property_suite = property_suite.get("refined_ltlf_property_suite", property_suite)
        self.semantic_graph = semantic_graph
        self.loop_bound = loop_bound
        self.timeout = timeout

        # Internal state
        self.monitors: Dict[str, List[Dict[str, Any]]] = {}
        self.errors: List[Dict[str, Any]] = []
        self.compilation_timeouts: List[str] = []

        # Language inclusion results
        self._lang_forward: bool = True
        self._lang_reverse: bool = True
        self._lang_counterexamples: List[Dict[str, Any]] = []

        # GED results
        self._ged_score: float = 0.0
        self._ged_diagnostics: Dict[str, Any] = {}

    # ── Public API ───────────────────────────────────────────────────

    def run_pipeline(self) -> Dict[str, Any]:
        """
        Executes the full Phase 4 pipeline:
        1. Compile properties → SPOT monitors (if SPOT available)
        2. Language-inclusion check (works without SPOT)
        3. GED structural diagnostics (works without SPOT)
        Returns a comprehensive result dict.
        """
        # Step 1: Compile to SPOT automata (optional — needs SPOT)
        self._compile_monitors()

        # Step 2: Language inclusion (always runs — trace-based)
        inclusion = self.check_language_inclusion()

        # Step 3: GED diagnostics (always runs)
        ged_score = self.compute_ged()

        return self._build_result()

    def check_language_inclusion(self) -> Dict[str, Any]:
        """
        Bidirectional language-inclusion check.

        Forward  (L(G_BPMN) ⊆ L(A_SPEC)):
            Every trace from the BPMN graph must satisfy ALL properties.
        Reverse  (L(A_SPEC) ⊆ L(G_BPMN)):
            The property suite must not accept traces that are impossible
            in the BPMN graph. Checked by verifying that no property
            vacuously accepts disconnected or unreachable paths.

        Both checks use the LTLf evaluator directly — no SPOT needed.
        """
        all_properties = self._collect_properties()
        traces = self._generate_traces(self.semantic_graph)

        # ── Forward: every BPMN trace satisfies every property ──
        self._lang_forward = True
        for trace in traces:
            for prop in all_properties:
                try:
                    if not evaluate_ltlf(prop, trace):
                        self._lang_forward = False
                        self._lang_counterexamples.append({
                            "direction": "forward",
                            "property": prop,
                            "trace": [list(s) for s in trace],
                        })
                except Exception as e:
                    self.errors.append({
                        "error": "evaluation_error",
                        "property": prop,
                        "details": str(e),
                    })

        # ── Reverse: properties don't over-accept ──
        # Check: synthesize "negative traces" by permuting proposition
        # steps and verify that at least one property rejects them.
        self._lang_reverse = True
        negative_traces = self._generate_negative_traces(traces)
        for neg_trace in negative_traces:
            all_pass = True
            for prop in all_properties:
                try:
                    if not evaluate_ltlf(prop, neg_trace):
                        all_pass = False
                        break
                except Exception:
                    all_pass = False
                    break
            if all_pass and neg_trace not in traces:
                # A negative trace passed all properties — over-permissive
                self._lang_reverse = False
                self._lang_counterexamples.append({
                    "direction": "reverse",
                    "property": "(all passed)",
                    "trace": [list(s) for s in neg_trace],
                })

        return {
            "forward": self._lang_forward,
            "reverse": self._lang_reverse,
            "counterexamples": self._lang_counterexamples,
        }

    def compute_ged(self) -> float:
        """
        Computes the normalized Graph Edit Distance between the BPMN
        source graph and the automaton structure (if compiled) or
        the property-implied dependency graph.

        Returns a normalized GED in [0, 1] where 0 = identical structure.
        """
        bpmn_graph = self._build_nx_graph(self.semantic_graph)
        spec_graph = self._build_spec_graph()

        n_bpmn = max(bpmn_graph.number_of_nodes(), 1)
        n_spec = max(spec_graph.number_of_nodes(), 1)
        max_nodes = max(n_bpmn, n_spec)

        # For small graphs use exact GED; for large ones approximate
        if max_nodes <= 20:
            try:
                ged_gen = nx.optimize_graph_edit_distance(bpmn_graph, spec_graph)
                raw_ged = next(ged_gen)
            except (StopIteration, nx.NetworkXError, ImportError, ModuleNotFoundError):
                # numpy not available (required by networkx GED) — fall back
                raw_ged = abs(n_bpmn - n_spec) + abs(
                    bpmn_graph.number_of_edges() - spec_graph.number_of_edges()
                )
        else:
            # Approximate: node-count diff + edge-count diff
            raw_ged = abs(n_bpmn - n_spec) + abs(
                bpmn_graph.number_of_edges() - spec_graph.number_of_edges()
            )

        # Normalize by max possible edits
        max_possible = n_bpmn + n_spec + bpmn_graph.number_of_edges() + spec_graph.number_of_edges()
        self._ged_score = raw_ged / max_possible if max_possible > 0 else 0.0

        self._ged_diagnostics = {
            "raw_ged": raw_ged,
            "normalized_ged": round(self._ged_score, 4),
            "bpmn_nodes": n_bpmn,
            "bpmn_edges": bpmn_graph.number_of_edges(),
            "spec_nodes": spec_graph.number_of_nodes(),
            "spec_edges": spec_graph.number_of_edges(),
            "method": "exact" if max_nodes <= 20 else "approximate",
        }

        return self._ged_score

    def export_hoa(self, filepath: str) -> None:
        """
        Exports all compiled HOA automata to a single file.
        Each automaton is separated by a comment line with the original property.
        """
        lines: List[str] = []
        lines.append("// VibeCheck Module 01 — Phase 4 HOA Export")
        lines.append(f"// Loop bound: {self.loop_bound}")
        lines.append(f"// Properties compiled: {sum(len(m) for m in self.monitors.values())}")
        lines.append("")

        for tier, monitors in self.monitors.items():
            for mon in monitors:
                lines.append(f"// Tier: {tier}")
                lines.append(f"// Original: {mon['original_ltlf']}")
                lines.append(f"// Normalized: {mon['spot_normalized']}")
                hoa = mon.get("hoa_automaton", "")
                if hoa:
                    lines.append(hoa)
                lines.append("")

        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def get_monitor_export(self) -> List[Dict[str, Any]]:
        """
        Returns the monitor suite in a format compatible with Module 03.
        M03's model_checker.py expects (name, monitor_LTS) tuples.
        """
        export: List[Dict[str, Any]] = []
        for tier, monitors in self.monitors.items():
            for mon in monitors:
                export.append({
                    "name": mon["original_ltlf"],
                    "tier": tier,
                    "spot_normalized": mon["spot_normalized"],
                    "hoa": mon.get("hoa_automaton", ""),
                })
        return export

    # ── SPOT Compilation ─────────────────────────────────────────────

    def _compile_monitors(self) -> None:
        """Compiles each property in the suite to a SPOT monitor automaton."""
        if spot is None:
            self.errors.append({
                "error": "environment_error",
                "details": "SPOT library is not installed. HOA compilation skipped. "
                           "Language inclusion and GED checks will still run.",
            })
            return

        for tier, properties in self.property_suite.items():
            if not isinstance(properties, list):
                continue

            self.monitors[tier] = []
            for prop in properties:
                if prop == "no killer found":
                    continue

                norm_prop = FormulaNormalizer.normalize(prop)
                result_container: Dict[str, Any] = {}

                # Thread-based per-property timeout
                def _compile():
                    try:
                        f = spot.formula(norm_prop)
                        aut = f.translate("monitor")
                        result_container["hoa"] = aut.to_str("hoa")
                    except Exception as e:
                        result_container["error"] = str(e)

                t = threading.Thread(target=_compile, daemon=True)
                t.start()
                t.join(timeout=self.timeout)

                if t.is_alive():
                    self.compilation_timeouts.append(prop)
                    self.errors.append({"error": "timeout", "property": prop})
                    continue

                if "error" in result_container:
                    self.errors.append({
                        "error": "parser_reject",
                        "property": prop,
                        "details": result_container["error"],
                    })
                else:
                    self.monitors[tier].append({
                        "original_ltlf": prop,
                        "spot_normalized": norm_prop,
                        "hoa_automaton": result_container.get("hoa", ""),
                    })

    # ── Trace Generation ─────────────────────────────────────────────

    def _generate_traces(
        self, graph: Dict[str, Any], cutoff: Optional[int] = None
    ) -> List[List[Set[str]]]:
        """
        Generates bounded execution traces from the semantic graph.
        Mirrors LTLfAuditor._generate_traces from mutation_refiner.py.
        """
        nx_graph = nx.DiGraph()
        for edge in graph.get("edges", []):
            nx_graph.add_edge(edge["source_id"], edge["target_id"])

        start_states = graph.get("start_states", [])
        if not start_states:
            initial = graph.get("initial_state")
            start_states = [initial] if initial else []

        end_nodes = [
            s["node_id"]
            for s in graph.get("states", [])
            if s.get("node_type") == "endEvent"
        ]
        if not end_nodes:
            end_nodes = [
                n for n in nx_graph.nodes() if nx_graph.out_degree(n) == 0
            ]

        num_nodes = len(nx_graph.nodes())
        if cutoff is not None:
            path_cutoff = min(cutoff, num_nodes)
        else:
            path_cutoff = min(20, num_nodes) if num_nodes > 0 else 0

        all_paths: List[List[str]] = []
        try:
            for start in start_states:
                if start not in nx_graph:
                    continue
                for end in end_nodes:
                    if end not in nx_graph:
                        continue
                    gen = nx.all_simple_paths(
                        nx_graph, source=start, target=end, cutoff=path_cutoff
                    )
                    count = 0
                    for path in gen:
                        all_paths.append(path)
                        count += 1
                        if count >= 50 or len(all_paths) >= 100:
                            break
                    if len(all_paths) >= 100:
                        break
                if len(all_paths) >= 100:
                    break
        except Exception:
            pass

        # Convert node paths to proposition traces
        node_map = {
            s["node_id"]: s.get("atomic_propositions", [])
            for s in graph.get("states", [])
        }
        traces: List[List[Set[str]]] = []
        for path in all_paths[:20]:
            trace: List[Set[str]] = []
            for node_id in path:
                props = node_map.get(node_id, [])
                if len(props) > 1:
                    # Emit start(X) and done(X) as separate consecutive steps
                    for p in props:
                        trace.append({p})
                elif len(props) == 1:
                    trace.append({props[0]})
                else:
                    trace.append(set())
            traces.append(trace)
        return traces

    def _generate_negative_traces(
        self, positive_traces: List[List[Set[str]]]
    ) -> List[List[Set[str]]]:
        """
        Generates plausible negative traces by mutating internal steps of positive ones.
        Used for reverse language-inclusion checks.
        
        It avoids mutating the first (start) and last (end) steps because
        dropping the end step creates a prefix trace that trivially passes
        'weak until' (W) safety properties.
        """
        negatives: List[List[Set[str]]] = []
        for trace in positive_traces[:5]:
            if len(trace) < 4:
                continue

            # 1. Drop each single internal step
            for i in range(1, len(trace) - 1):
                dropped = trace[:i] + trace[i+1:]
                negatives.append(dropped)
                
            # 2. Swap adjacent internal steps
            for i in range(1, len(trace) - 2):
                swapped = list(trace)
                swapped[i], swapped[i+1] = swapped[i+1], swapped[i]
                if swapped != list(trace):
                    negatives.append(swapped)
                    
            # 3. Swap first two steps (breaks start_event ordering)
            if len(trace) >= 2:
                swapped = list(trace)
                swapped[0], swapped[1] = swapped[1], swapped[0]
                if swapped != list(trace):
                    negatives.append(swapped)

        return negatives

    # ── Graph Construction ───────────────────────────────────────────

    def _build_nx_graph(self, semantic_graph: Dict[str, Any]) -> nx.DiGraph:
        """Builds a NetworkX DiGraph from the semantic graph."""
        g = nx.DiGraph()
        for state in semantic_graph.get("states", []):
            g.add_node(state["node_id"], **state)
        for edge in semantic_graph.get("edges", []):
            g.add_edge(edge["source_id"], edge["target_id"])
        return g

    def _build_spec_graph(self) -> nx.DiGraph:
        """
        Builds a dependency graph implied by the property suite.
        Each ordering constraint !start(B) W done(A) creates edge A → B.
        """
        import re

        g = nx.DiGraph()
        all_props = self._collect_properties()

        for prop in all_props:
            # Match ordering templates: !start(X) W done(Y)  or  !X W Y
            m = re.match(
                r"^!(?:start\()?(\w+)\)?(?:\s+W\s+)(?:done\()?(\w+)\)?$",
                prop.strip(),
            )
            if m:
                target = m.group(1)
                source = m.group(2)
                g.add_edge(source, target)
            else:
                # Match G(X -> !Y) mutex patterns
                m2 = re.match(
                    r"^G\((\w+)\s*->\s*!(\w+)\)$",
                    prop.strip(),
                )
                if m2:
                    g.add_node(m2.group(1))
                    g.add_node(m2.group(2))

        return g

    # ── Helpers ───────────────────────────────────────────────────────

    def _collect_properties(self) -> List[str]:
        """Collects all properties from the suite, skipping non-list tiers."""
        props: List[str] = []
        for tier, entries in self.property_suite.items():
            if isinstance(entries, list):
                for p in entries:
                    if p and p != "no killer found":
                        props.append(p)
        return props

    def _build_result(self) -> Dict[str, Any]:
        """Builds the comprehensive Phase 4 result."""
        monitors_compiled = sum(len(m) for m in self.monitors.values())
        monitors_failed = len([
            e for e in self.errors
            if e.get("error") in ("parser_reject", "timeout")
        ])

        has_env_error = any(e.get("error") == "environment_error" for e in self.errors)
        has_inclusion_fail = not self._lang_forward or not self._lang_reverse

        if has_inclusion_fail:
            status = "FAIL"
        elif self.errors and not has_env_error:
            status = "FAIL_WITH_ERRORS"
        elif has_env_error and monitors_compiled == 0:
            status = "PASS_NO_SPOT"
        else:
            status = "PASS"

        return {
            "phase_4_certificate": {
                "status": status,
                "monitors_compiled": monitors_compiled,
                "monitors_failed": monitors_failed,
                "language_inclusion_forward": self._lang_forward,
                "language_inclusion_reverse": self._lang_reverse,
                "language_inclusion_counterexamples": self._lang_counterexamples,
                "ged_score": round(self._ged_score, 4),
                "ged_diagnostics": self._ged_diagnostics,
                "loop_bound_documented": self.loop_bound,
                "compilation_timeouts": self.compilation_timeouts,
                "errors_count": len(self.errors),
            },
            "monitors": self.monitors,
            "errors": self.errors,
            # Top-level convenience fields for test consumption
            "language_inclusion_forward": self._lang_forward,
            "language_inclusion_reverse": self._lang_reverse,
            "ged": round(self._ged_score, 4),
        }
