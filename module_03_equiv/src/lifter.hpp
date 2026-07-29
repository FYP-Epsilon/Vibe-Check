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
    ~AdvancedLifter() = default;

    AdvancedLifter(const AdvancedLifter&) = delete;
    AdvancedLifter& operator=(const AdvancedLifter&) = delete;

    // ── Phase A ──────────────────────────────────────────────────────────

    void parse_wir_types(const std::string& wir_json_str);
    spot::twa_graph_ptr lift_to_lts(const std::string& wir_json_str);
    spot::twa_graph_ptr build_spot_automaton(const std::string& wir_json_str);
    LifterDiagnostics get_last_diagnostics() const;

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
 * Produced by check_compliance(). verdict is one of:
 *   - "COMPLIANT"    the code satisfies the property; counter_example_trace is empty.
 *   - "VIOLATION"    the code violates the property; counter_example_trace describes
 *                    the accepting run of the synchronous product (code ⊗ ¬φ).
 *   - "INCONCLUSIVE" the property mentions at least one atomic proposition that
 *                    never appears anywhere in code_aut. Emptiness was NOT checked in
 *                    this case: an atom the code automaton's edges never mention is
 *                    unconstrained in the product, which lets the emptiness search
 *                    resolve it in whichever direction proves a violation, producing a
 *                    confident-looking VIOLATION on code that never actually exhibits
 *                    the behavior being flagged. unmatched_atoms lists the offending
 *                    proposition names.
 */
struct ComplianceResult {
    std::string verdict = "COMPLIANT";
    std::string counter_example_trace;          ///< Empty unless verdict == "VIOLATION".
    std::vector<std::string> unmatched_atoms;   ///< Populated only when verdict == "INCONCLUSIVE".
};

/**
 * @brief Model-check a code automaton against an LTL property string.
 *
 * Algorithm:
 *   1. Parse ltl_string via spot::parse_infix_psl().
 *   2. Collect the property's atomic propositions and compare against code_aut's
 *      registered APs (code_aut->ap()). If any propositions in the formula never
 *      appear on code_aut, return INCONCLUSIVE without model-checking — an atom the
 *      code side never mentions is unconstrained in the product, so the emptiness
 *      search can resolve it however proves a violation, regardless of what the code
 *      under test actually does.
 *   3. Negate the formula (violation property).
 *   4. Translate the negated formula into a Büchi automaton using the
 *      SAME bdd_dict as code_aut (critical for correct product).
 *   5. Compute the synchronous product: code_aut ⊗ violation_aut.
 *   6. Run emptiness check on the product.
 *   7. If the product is empty → COMPLIANT; otherwise → VIOLATION with counter-example.
 *
 * @param code_aut   The automaton to check (must have Büchi acceptance).
 * @param ltl_string An LTL/PSL formula string (SPOT infix syntax).
 * @return ComplianceResult with verdict and optional counter-example / unmatched atoms.
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
