//lifter.hpp
//
// Phase A + B + D: Lifting WIR → SPOT twa_graph + Stuttering Bisimulation + Model Checking
// =====================================================================
// Core C++ engine for the VibeCheck 3-Phase Post-Hoc Auditor.
// Transforms Module 02's Workflow Intermediate Representation (WIR)
// into a formal Labeled Transition System backed by SPOT's twa_graph,
// then performs divergence-sensitive stuttering bisimulation minimization.
//
// Architectural invariant: ALL automaton construction, SCC analysis,
// partition refinement, and BDD algebra happen in C++ via libspot.
// Python sees only the Pybind11 surface.

#pragma once
#ifndef VIBECHECK_LIFTER_HPP
#define VIBECHECK_LIFTER_HPP

#include <spot/twa/twagraph.hh>
#include <spot/twa/bdddict.hh>
#include <string>
#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <memory>
#include <optional>

namespace vibecheck {

// ---------------------------------------------------------------------------
// Phase A - Diagnostics
// ---------------------------------------------------------------------------

/**
 * @brief Telemetry produced during a single lift operation (Phase A).
 */
struct LifterDiagnostics {
    unsigned total_states      = 0;
    unsigned total_edges       = 0;
    unsigned observable_edges  = 0;
    unsigned tau_edges         = 0;
    unsigned deadlock_states   = 0;
    unsigned unreachable_states = 0;
    std::vector<std::string> matched_aps;
    std::vector<std::string> unmatched_actions;
};

// ---------------------------------------------------------------------------
// Phase A - WIR Deserialization Types
// ---------------------------------------------------------------------------

/**
 * @brief Safe container for a single WIR node parsed from JSON.
 *
 * Schema contract:
 *   { "id": string, "type": string, "ast_type": string|null, "guard": string|null }
 *
 * Design:
 *   - `guard` and `ast_type` use std::optional<std::string> to map JSON null
 *     to std::nullopt without ever calling json::get<std::string>() on null.
 *   - `ast_type` is optional because non-branching nodes (entry, exit, task)
 *     frequently omit it in real WIR payloads.
 */
struct WirNode {
    std::string                 id;                         ///< Unique node identifier.
    std::string                 type      = "block";        ///< CFG node type (entry/exit/task/gateway/loop/block).
    std::optional<std::string>  ast_type  = std::nullopt;   ///< Python AST type (For, If, While…); absent on non-branch nodes.
    std::optional<std::string>  guard     = std::nullopt;   ///< Guard condition; null means unconditional / tau.
};

/**
 * @brief Safe container for a single WIR edge parsed from JSON.
 *
 * Schema contract:
 *   { "source": string, "target": string, "guard": string|null }
 *
 * Design:
 *   - source/target are non-optional — an edge without endpoints is
 *     structurally invalid and must be rejected at parse time.
 *   - guard follows the same std::optional pattern as WirNode::guard.
 */
struct WirEdge {
    std::string                 source;                     ///< Source node ID.
    std::string                 target;                     ///< Target node ID.
    std::optional<std::string>  guard     = std::nullopt;   ///< Guard condition; null means unconditional / tau.
};

// ---------------------------------------------------------------------------
// Phase A - SpotAutomatonBuilder (safe bdd_dict + twa_graph encapsulation)
// ---------------------------------------------------------------------------

/**
 * @brief Safe encapsulation of SPOT's bdd_dict + twa_graph lifecycle.
 *
 * Manages construction of an empty SPOT automaton and guarantees
 * that the twa_graph is destroyed BEFORE the bdd_dict, preventing
 * assert_emptiness() failures regardless of member declaration order
 * or Python GC timing.
 *
 * Invariants:
 *   - dict_ is always non-null after construction.
 *   - graph_ is always non-null after construction.
 *   - graph_ internally holds a shared_ptr to dict_ (SPOT's design).
 *   - Destructor explicitly resets graph_ before dict_ dies.
 */
class SpotAutomatonBuilder {
public:
    SpotAutomatonBuilder();
    ~SpotAutomatonBuilder();

    // Non-copyable, non-movable (shared_ptr holder handles sharing)
    SpotAutomatonBuilder(const SpotAutomatonBuilder&) = delete;
    SpotAutomatonBuilder& operator=(const SpotAutomatonBuilder&) = delete;

    /// Access the underlying automaton (never null after construction).
    spot::twa_graph_ptr get_graph() const;

    /// Access the BDD dictionary (never null after construction).
    spot::bdd_dict_ptr get_dict() const;

    /// Number of states currently in the automaton.
    unsigned num_states() const;

    /// Number of edges currently in the automaton.
    unsigned num_edges() const;

private:
    // ORDER MATTERS for fallback safety, but the explicit destructor
    // makes this a defense-in-depth rather than the sole protection.
    spot::bdd_dict_ptr  dict_;    ///< Destroyed LAST  (declared first).
    spot::twa_graph_ptr graph_;   ///< Destroyed FIRST (declared second).
};

// ---------------------------------------------------------------------------
// Phase B Result — returned by compute_bisimulation_full()
// ---------------------------------------------------------------------------

/**
 * @brief Full result of divergence-sensitive stuttering bisimulation (Phase B).
 *
 * Contains the quotient automaton, the state→block partition mapping,
 * and the per-state divergence vector.
 */
struct BisimulationResult {
    spot::twa_graph_ptr quotient;       ///< Minimized quotient automaton.
    unsigned original_states  = 0;      ///< States in the input graph.
    unsigned quotient_states  = 0;      ///< States in the quotient.
    unsigned num_divergent    = 0;      ///< Number of divergent input states.
    unsigned num_partition_blocks = 0;  ///< Number of equivalence classes at fixed point.
    std::vector<unsigned> partition;    ///< state → equivalence-class (block) mapping.
    std::vector<bool> divergent;        ///< state → divergence flag.
};

// ---------------------------------------------------------------------------
// AdvancedLifter — the core engine class
// ---------------------------------------------------------------------------

class AdvancedLifter {
public:
    AdvancedLifter();
    ~AdvancedLifter();

    AdvancedLifter(const AdvancedLifter&) = delete;
    AdvancedLifter& operator=(const AdvancedLifter&) = delete;

    // ── Phase A ──────────────────────────────────────────────────────────

    void parse_wir_types(const std::string& wir_json_str);
    spot::twa_graph_ptr lift_to_lts(const std::string& wir_json_str);
    spot::twa_graph_ptr build_spot_automaton(const std::string& wir_json_str);
    LifterDiagnostics get_last_diagnostics() const;

    /**
     * @brief Parse a specific function block from the WIR JSON into typed
     *        WirNode and WirEdge vectors.
     *
     * Navigates root["functions"][function_key], extracts only nodes/edges,
     * and ignores all other top-level noise (dominators, certificate, etc.).
     *
     * @param wir_json_str  Full WIR JSON string (root object).
     * @param function_key  Key inside the "functions" dictionary to extract.
     * @return Pair of (nodes, edges) vectors.
     *
     * @throws std::invalid_argument  If JSON is malformed or the function key
     *                                 is not found.
     */
    std::pair<std::vector<WirNode>, std::vector<WirEdge>>
    parse_wir_function(const std::string& wir_json_str,
                       const std::string& function_key);


    // ── Phase B — Divergence Detection ───────────────────────────────────

    /**
     * @brief Detect divergent states via spot::scc_info on the silent subgraph.
     *
     * Algorithm:
     *   1. Build a silent subgraph containing only tau-transitions.
     *   2. Run spot::scc_info to find SCCs in the silent subgraph.
     *   3. Mark states in non-trivial SCCs (size > 1 or single-state
     *      with tau self-loop) as directly divergent.
     *   4. Backward BFS from divergent states along tau edges:
     *      any state that can reach a divergent SCC via tau-only
     *      transitions is also marked divergent.
     *
     * @param graph The twa_graph to analyze.
     * @return Per-state divergence flags (indexed by state number).
     */
    std::vector<bool> detect_divergent_states(const spot::twa_graph_ptr& graph);

    // ── Phase B — Stuttering Bisimulation (Groote–Vaandrager) ────────────

    /**
     * @brief Minimize a twa_graph via divergence-sensitive stuttering bisimulation.
     *
     * Produces a quotient automaton where each state represents an
     * equivalence class under the Groote–Vaandrager relation.
     *
     * @param graph The twa_graph to minimize.
     * @return The quotient twa_graph.
     */
    spot::twa_graph_ptr minimize_stuttering(const spot::twa_graph_ptr& graph);

    /**
     * @brief Full bisimulation analysis with diagnostics.
     *
     * Like minimize_stuttering() but returns the partition, divergence
     * vector, and state counts alongside the quotient.
     *
     * @param graph The twa_graph to analyze.
     * @return BisimulationResult with quotient + metadata.
     */
    BisimulationResult compute_bisimulation_full(const spot::twa_graph_ptr& graph);

    /**
     * @brief Check whether two automata are stuttering bisimilar.
     *
     * Builds their disjoint union, runs Phase B on the combined graph,
     * and checks if the initial states fall in the same partition block.
     */
    bool check_stuttering_bisimulation(const spot::twa_graph_ptr& aut1,
                                       const spot::twa_graph_ptr& aut2);

    /**
     * @brief Collapse tau-SCCs into macro-states using spot::scc_info.
     *
     * Retained for backward compatibility. For full minimization,
     * prefer minimize_stuttering().
     */
    spot::twa_graph_ptr tarjan_tau_collapse(const spot::twa_graph_ptr& graph);

    // ── Hashing / Matching / Accessors ───────────────────────────────────

    void set_bpmn_tasks(const std::vector<std::string>& tasks);
    std::string semantic_match(const std::string& action_name);
    spot::bdd_dict_ptr get_dict() const;
    std::unordered_map<std::string, int> get_variable_map() const;

private:
    // ── Core state ───────────────────────────────────────────────────────
    spot::bdd_dict_ptr dict_;
    spot::twa_graph_ptr registry_aut_;
    std::unordered_map<std::string, int> bdd_vars_;
    std::vector<int> tau_bdd_indices_;
    std::vector<std::string> bpmn_tasks_;
    LifterDiagnostics last_diag_;
    std::unordered_set<std::string> matched_aps_set_;
    std::unordered_set<std::string> unmatched_actions_set_;

    // ── Phase A helpers ──────────────────────────────────────────────────
    bool is_tau(bdd cond);
    size_t levenshtein_distance(const std::string& s1, const std::string& s2);
    std::string normalize(const std::string& s);
    void register_variable(const std::string& var_name);
    void register_unresolved_type(const std::string& var_name);
    std::vector<std::string> extract_actions_from_code(const std::vector<std::string>& code_lines);
    bdd resolve_edge_label(const spot::twa_graph_ptr& aut, const std::string& raw_guard);
    bdd resolve_task_label(const spot::twa_graph_ptr& aut, const std::string& node_type,
                           const std::vector<std::string>& code_lines);
    bdd ensure_ap(const spot::twa_graph_ptr& aut, const std::string& ap_name);

    // ── Phase B helpers ──────────────────────────────────────────────────

    /**
     * @brief Build the silent subgraph (tau-only transitions).
     *
     * Returns a twa_graph with n+1 states where states 0..n-1 mirror
     * the original graph and state n is a synthetic super-initial
     * with tau edges to every other state. This ensures spot::scc_info
     * sees all states as reachable (states reachable only via observable
     * transitions in the original would otherwise be missed).
     */
    spot::twa_graph_ptr build_silent_subgraph(const spot::twa_graph_ptr& graph);

    /**
     * @brief Groote–Vaandrager partition refinement.
     *
     * Iterative splitter-based algorithm:
     *   1. Initial partition separates divergent from non-divergent states.
     *   2. For each splitter (action a, target block B'):
     *      - Find states in each block that can stuttering-reach
     *        (via inert tau within the block) a state with an
     *        a-transition to B'.
     *      - Split blocks where not all states are stable.
     *   3. Repeat until fixed point.
     *
     * @return Per-state block assignment (contiguously numbered 0..k-1).
     */
    std::vector<unsigned> partition_refinement(const spot::twa_graph_ptr& graph,
                                               const std::vector<bool>& divergent);

    /**
     * @brief Build the quotient automaton from a partition.
     *
     * One state per block; inert tau-transitions (within a block)
     * are absorbed; inter-block edges are de-duplicated via merge_edges().
     */
    spot::twa_graph_ptr build_quotient(const spot::twa_graph_ptr& graph,
                                       const std::vector<unsigned>& partition,
                                       unsigned num_blocks);
};

// ---------------------------------------------------------------------------
// Phase D — Compliance Result
// ---------------------------------------------------------------------------

/**
 * @brief Result of checking a code automaton against an LTL specification.
 *
 * Produced by check_compliance(). If is_compliant is true, the code satisfies
 * the property and counter_example_trace is empty. Otherwise, the trace
 * contains a human-readable description of the accepting run of the
 * synchronous product (code ⊗ ¬φ).
 */
struct ComplianceResult {
    bool is_compliant = true;                   ///< True if PASS, false if FAIL.
    std::string counter_example_trace;          ///< Empty if PASS; formatted trace if FAIL.
};

/**
 * @brief Model-check a code automaton against an LTL property string.
 *
 * Algorithm:
 *   1. Parse ltl_string via spot::parse_infix_psl().
 *   2. Negate the formula (violation property).
 *   3. Translate the negated formula into a Büchi automaton using the
 *      SAME bdd_dict as code_aut (critical for correct product).
 *   4. Compute the synchronous product: code_aut ⊗ violation_aut.
 *   5. Run emptiness check on the product.
 *   6. If the product is empty → PASS; otherwise → FAIL with counter-example.
 *
 * @param code_aut   The automaton to check (must have Büchi acceptance).
 * @param ltl_string An LTL/PSL formula string (SPOT infix syntax).
 * @return ComplianceResult with verdict and optional counter-example.
 */
ComplianceResult check_compliance(const spot::twa_graph_ptr& code_aut,
                                  const std::string& ltl_string);

// ---------------------------------------------------------------------------
// Free function — convenience Pybind11 entry point
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Phase C — Clustering Result
// ---------------------------------------------------------------------------

/**
 * @brief A single equivalence cluster produced by cluster_implementations().
 *
 * Each cluster contains:
 *  - The original input-vector indices of all isomorphic graphs.
 *  - A representative graph chosen by (lowest state count, then lowest edge count).
 */
struct ClusterEntry {
    std::vector<unsigned> indices;         ///< Original vector indices belonging to this cluster.
    spot::twa_graph_ptr   representative;  ///< Simplest graph in this cluster.
};

/**
 * @brief Group quotient automata by graph isomorphism (Phase C).
 *
 * PRECONDITION: All graphs in @p automata MUST share the same bdd_dict.
 * This is enforced by constructing them from a single AdvancedLifter instance.
 *
 * Algorithm:
 *   1. For each new graph, compare against the representative of every
 *      existing cluster using spot::are_isomorphic().
 *   2. If isomorphic, add to that cluster.
 *   3. Otherwise, start a new cluster.
 *   4. Within each cluster, the representative is the graph with the
 *      lowest state count; ties broken by lowest edge count.
 *
 * @param automata Vector of minimized quotient twa_graph_ptr (all sharing one bdd_dict).
 * @return Map from cluster_id (0-based) to ClusterEntry.
 */
std::unordered_map<unsigned, ClusterEntry> cluster_implementations(
    const std::vector<spot::twa_graph_ptr>& automata);

} // namespace vibecheck

#endif // VIBECHECK_LIFTER_HPP
