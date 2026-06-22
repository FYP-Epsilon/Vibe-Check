//lifter.hpp

#pragma once
#ifndef VIBECHECK_LIFTER_HPP
#define VIBECHECK_LIFTER_HPP

#include <spot/twa/twagraph.hh>
#include <spot/twa/bdddict.hh>
#include <string>
#include <vector>
#include <unordered_map>
#include <memory>

namespace vibecheck {

/**
 * @brief AdvancedLifter transforms WIR JSON into a formal SPOT LTS (twa_graph).
 *
 * Milestone P1.1: WIR-Type Layer Parser and BDD Dictionary Initialization.
 * Seamlessly interfaces with Module 02's output adhering to shared_schemas/wir_schema.json.
 */
class AdvancedLifter {
public:
    /**
     * @brief Constructor safely initializes the centralized shared SPOT BDD dictionary.
     */
    AdvancedLifter();
    
    ~AdvancedLifter() = default;

    // Disallow copy/move to strictly manage the dict_ ownership and prevent Pybind11 memory leaks
    AdvancedLifter(const AdvancedLifter&) = delete;
    AdvancedLifter& operator=(const AdvancedLifter&) = delete;

    /**
     * @brief Parses the WIR-Type layer from the provided JSON string.
     * 
     * Identifies control and data variables, processes inferred types,
     * and registers them in the BDD dictionary. Applies conservative
     * over-approximation for Any/Union types by allocating anonymous BDD vars.
     * 
     * @param wir_json_str The WIR JSON payload as a string.
     */
    void parse_wir_types(const std::string& wir_json_str);

    /**
     * @brief Lifts WIR JSON to a SPOT LTS (twa_graph).
     * 
     * @param wir_json_str The WIR JSON payload.
     * @return A shared pointer to the generated SPOT graph.
     */
    spot::twa_graph_ptr lift_to_lts(const std::string& wir_json_str);

    /**
     * @brief Collapses SCCs in the tau-subgraph into macro-states.
     * 
     * @param graph The graph to process.
     * @return A new graph with tau-SCCs collapsed.
     */
    spot::twa_graph_ptr tarjan_tau_collapse(const spot::twa_graph_ptr& graph);

    /**
     * @brief Implements the Groote & Vaandrager algorithm for divergence-sensitive stuttering bisimulation.
     * 
     * @param aut1 First automaton.
     * @param aut2 Second automaton.
     * @return True if stuttering bisimilar.
     */
    bool check_stuttering_bisimulation(const spot::twa_graph_ptr& aut1, const spot::twa_graph_ptr& aut2);

    /**
     * @brief Generates a SHA-256 signature for minimized graphs.
     * 
     * @param graph The graph to hash.
     * @return SHA-256 hash string.
     */
    std::string compute_deterministic_hash(const spot::twa_graph_ptr& graph);

    /**
     * @brief Sets the list of reference BPMN task names for semantic matching.
     * @param tasks Vector of task names from the specification.
     */
    void set_bpmn_tasks(const std::vector<std::string>& tasks);

    /**
     * @brief Performs a 3-tier semantic match to map an LLM action to a BPMN task.
     * Tier 1: Lexical, Tier 2: Levenshtein, Tier 3: NLP (via Python callback).
     * 
     * @param action_name The function/action name from LLM code.
     * @return The matched BPMN task name, or "unlabeled_task" if no match.
     */
    std::string semantic_match(const std::string& action_name);

    /**
     * @brief Returns the shared BDD dictionary pointer.
     */
    spot::bdd_dict_ptr get_dict() const;
    
    /**
     * @brief Returns the map of variable names to their BDD variable indices.
     */
    std::unordered_map<std::string, int> get_variable_map() const;

private:
    // Centralized shared BDD dictionary
    spot::bdd_dict_ptr dict_;

    // Persistent registry automaton that owns AP registrations.
    // SPOT requires APs to be registered on an automaton (not the dict directly).
    // All created automata share this dict and copy APs from this registry.
    spot::twa_graph_ptr registry_aut_;
    
    // Maps variable names (APs) to BDD indices
    std::unordered_map<std::string, int> bdd_vars_;

    // Indices of BDD variables that represent tau (silent) transitions
    std::vector<int> tau_bdd_indices_;

    // Reference BPMN tasks for Milestone P1.2
    std::vector<std::string> bpmn_tasks_;

    /**
     * @brief Identifies divergent states (those that can reach a tau-cycle).
     */
    std::vector<bool> compute_divergence(const spot::twa_graph_ptr& graph);

    /**
     * @brief Helper to check if a BDD represents a tau (silent) transition.
     */
    bool is_tau(bdd cond);

    /**
     * @brief Internal implementation of partition refinement.
     */
    std::vector<size_t> refine_blocks(const spot::twa_graph_ptr& combined, const std::vector<bool>& divergent);

    /**
     * @brief Computes the Levenshtein distance between two strings.
     */
    size_t levenshtein_distance(const std::string& s1, const std::string& s2);

    /**
     * @brief Normalizes a string (lowercase, remove underscores/hyphens) for lexical matching.
     */
    std::string normalize(const std::string& s);

    /**
     * @brief Registers a variable name as an Atomic Proposition (AP) in the BDD dictionary.
     * @param var_name The name of the variable to register.
     */
    void register_variable(const std::string& var_name);
    
    /**
     * @brief Registers an unresolved type (Any/Union) as a non-deterministic choice variable.
     * @param var_name The name of the unresolved variable.
     */
    void register_unresolved_type(const std::string& var_name);
};

} // namespace vibecheck

#endif // VIBECHECK_LIFTER_HPP
