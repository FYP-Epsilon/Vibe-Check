#include "lifter.hpp"
#include <nlohmann/json.hpp>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <stdexcept>
#include <iostream>
#include <queue>
#include <set>
#include <stack>
#include <map>
#include <tuple>
#include <algorithm>
#include <sstream>
#include <spot/twaalgos/sccinfo.hh>
#include <spot/twaalgos/canonicalize.hh>
#include <spot/twaalgos/isdet.hh>
#include <spot/twaalgos/simulation.hh>
#include <spot/twaalgos/postproc.hh>
#include <spot/misc/hash.hh>

namespace py = pybind11;
using json = nlohmann::json;

namespace vibecheck {

AdvancedLifter::AdvancedLifter() {
    // Safe instantiation of the shared spot::bdd_dict_ptr.
    // Dictates the algebraic management of BDD variables preventing memory bloat.
    dict_ = spot::make_bdd_dict();
    if (!dict_) {
        throw std::runtime_error("Failed to initialize SPOT BDD dictionary.");
    }
    // Create a persistent registry automaton to own AP registrations.
    // SPOT requires APs to be registered on an automaton (twa), not on the dict directly.
    // This registry shares the dict with all automata created by this lifter.
    registry_aut_ = spot::make_twa_graph(dict_);
}

spot::bdd_dict_ptr AdvancedLifter::get_dict() const {
    return dict_;
}

std::unordered_map<std::string, int> AdvancedLifter::get_variable_map() const {
    return bdd_vars_;
}

void AdvancedLifter::register_variable(const std::string& var_name) {
    if (bdd_vars_.find(var_name) == bdd_vars_.end()) {
        // Register as a distinct atomic proposition via the registry automaton.
        // This ensures the BDD variable is properly owned and tracked.
        int bdd_idx = registry_aut_->register_ap(var_name);
        bdd_vars_[var_name] = bdd_idx;
        
        // Track tau-related APs for optimized is_tau checks
        if (var_name == "tau" || var_name == "silent" || var_name == "_") {
            tau_bdd_indices_.push_back(bdd_idx);
        }
    }
}

void AdvancedLifter::register_unresolved_type(const std::string& var_name) {
    // Conservative over-approximation (Gotcha Mitigation):
    // Allocate a fresh, anonymous BDD variable to represent non-deterministic choice.
    // This strictly prevents false positives in formal equivalence evaluation.
    std::string nd_var_name = var_name + "_ANY";
    if (bdd_vars_.find(nd_var_name) == bdd_vars_.end()) {
        int bdd_idx = registry_aut_->register_ap(nd_var_name);
        bdd_vars_[nd_var_name] = bdd_idx;
        // Unresolved types are NOT tau by default; they represent unknown observable actions or data.
    }
}

void AdvancedLifter::set_bpmn_tasks(const std::vector<std::string>& tasks) {
    bpmn_tasks_ = tasks;
}

std::string AdvancedLifter::normalize(const std::string& s) {
    std::string out;
    for (char c : s) {
        if (std::isalnum(c)) {
            out += std::tolower(c);
        }
    }
    return out;
}

size_t AdvancedLifter::levenshtein_distance(const std::string& s1, const std::string& s2) {
    const size_t m = s1.size();
    const size_t n = s2.size();
    if (m == 0) return n;
    if (n == 0) return m;

    std::vector<std::vector<size_t>> d(m + 1, std::vector<size_t>(n + 1));
    for (size_t i = 0; i <= m; ++i) d[i][0] = i;
    for (size_t j = 0; j <= n; ++j) d[0][j] = j;

    for (size_t j = 1; j <= n; ++j) {
        for (size_t i = 1; i <= m; ++i) {
            size_t substitution_cost = (s1[i - 1] == s2[j - 1]) ? 0 : 1;
            d[i][j] = std::min({d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + substitution_cost});
        }
    }
    return d[m][n];
}

std::string AdvancedLifter::semantic_match(const std::string& action_name) {
    if (bpmn_tasks_.empty()) return "unlabeled_task";

    std::string norm_action = normalize(action_name);

    // Tier 1: Exact Lexical Match
    for (const auto& task : bpmn_tasks_) {
        if (norm_action == normalize(task)) {
            return task;
        }
    }

    // Tier 2: Levenshtein Distance (Threshold <= 2)
    for (const auto& task : bpmn_tasks_) {
        if (levenshtein_distance(norm_action, normalize(task)) <= 2) {
            return task;
        }
    }

    // Tier 3: NLP Embedding Match (Threshold >= 0.85)
    // Note: We utilize the Pybind11 bridge to call out to the Sentence-BERT model
    // instantiated in the Python wrapper.
    try {
        py::gil_scoped_acquire acquire;
        py::object nlp_utils;
        // Try both import paths: direct (when src/ is in sys.path) and package (when running from project root)
        try {
            nlp_utils = py::module_::import("nlp_utils");
        } catch (...) {
            nlp_utils = py::module_::import("src.nlp_utils");
        }
        py::object scorer = nlp_utils.attr("compute_max_similarity");
        
        py::object result = scorer(action_name, bpmn_tasks_);
        py::tuple res_tuple = result.cast<py::tuple>();
        
        double score = res_tuple[0].cast<double>();
        std::string best_task = res_tuple[1].cast<std::string>();
        
        if (score >= 0.85) {
            return best_task;
        }
    } catch (const std::exception& e) {
        // Fallback or log if NLP engine fails
        std::cerr << "NLP Matching Error: " << e.what() << std::endl;
    }

    return "unlabeled_task";
}

void AdvancedLifter::parse_wir_types(const std::string& wir_json_str) {
    json wir;
    try {
        wir = json::parse(wir_json_str);
    } catch (const json::parse_error& e) {
        throw std::invalid_argument(std::string("WIR JSON parsing failed: ") + e.what());
    }

    // 1. Explicit variable registration derived from WIR-Data Layer classification
    if (wir.contains("control_variables") && wir["control_variables"].is_array()) {
        for (const auto& item : wir["control_variables"]) {
            register_variable(item.get<std::string>());
        }
    }

    if (wir.contains("data_variables") && wir["data_variables"].is_array()) {
        for (const auto& item : wir["data_variables"]) {
            register_variable(item.get<std::string>());
        }
    }

    // 2. WIR-Type Layer Processing: Process dynamically inferred types and annotations
    if (wir.contains("types") && wir["types"].is_object()) {
        for (auto it = wir["types"].begin(); it != wir["types"].end(); ++it) {
            std::string var_name = it.key();
            std::string type_val = it.value().get<std::string>();

            if (type_val == "Any" || type_val == "Union" || type_val == "Unresolved") {
                register_unresolved_type(var_name);
            } else {
                // For concrete Literal-Inferred, Function-Return, or Annotation Types
                register_variable(var_name);
            }
        }
    }
}

spot::twa_graph_ptr AdvancedLifter::lift_to_lts(const std::string& wir_json_str) {
    json wir = json::parse(wir_json_str);
    auto aut = spot::make_twa_graph(dict_);

    // Copy all previously registered APs from the registry automaton
    aut->copy_ap_of(registry_aut_);

    std::unordered_map<std::string, unsigned> state_map;

    std::string entry_node = wir.value("entry_node", "");
    if (entry_node.empty() && wir.contains("nodes") && !wir["nodes"].empty()) {
        if (wir["nodes"][0].is_string()) entry_node = wir["nodes"][0];
        else if (wir["nodes"][0].is_object()) entry_node = wir["nodes"][0]["id"];
    }

    // Preliminary pass to create states
    if (wir.contains("nodes")) {
        for (const auto& node : wir["nodes"]) {
            std::string id;
            if (node.is_string()) id = node;
            else id = node["id"];
            
            unsigned s = aut->new_state();
            state_map[id] = s;
            if (id == entry_node) {
                aut->set_init_state(s);
            }
        }
    }

    // Edges pass
    if (wir.contains("edges")) {
        for (const auto& edge : wir["edges"]) {
            std::string src_id = edge.contains("src") ? edge["src"].get<std::string>() : edge["source"].get<std::string>();
            std::string dst_id = edge.contains("dst") ? edge["dst"].get<std::string>() : edge["target"].get<std::string>();
            std::string guard = "true";
            if (edge.contains("condition") && !edge["condition"].is_null()) {
                guard = edge["condition"].get<std::string>();
            } else if (edge.contains("guard") && !edge["guard"].is_null()) {
                guard = edge["guard"].get<std::string>();
            }

            if (state_map.find(src_id) == state_map.end() || state_map.find(dst_id) == state_map.end()) {
                continue;
            }

            bdd cond_bdd;
            if (guard == "true") {
                cond_bdd = bddtrue;
            } else {
                // Check if it's an action to be semantically matched
                std::string action = semantic_match(guard);
                if (action != "unlabeled_task") {
                    register_variable(action);
                    // Re-register on this automaton if not already there
                    aut->register_ap(action);
                    cond_bdd = bdd_ithvar(bdd_vars_[action]);
                } else {
                    // It's a boolean guard on variables
                    // For now, simple AP registration. 
                    // In a full implementation, we'd parse the expression.
                    register_variable(guard);
                    aut->register_ap(guard);
                    cond_bdd = bdd_ithvar(bdd_vars_[guard]);
                }
            }
            aut->new_edge(state_map[src_id], state_map[dst_id], cond_bdd);
        }
    }

    // Prune unreachable states using BFS
    std::set<unsigned> reachable;
    std::queue<unsigned> q;
    unsigned init_state = aut->get_init_state_number();
    q.push(init_state);
    reachable.insert(init_state);

    while (!q.empty()) {
        unsigned curr = q.front();
        q.pop();
        for (auto& edge : aut->out(curr)) {
            if (reachable.find(edge.dst) == reachable.end()) {
                reachable.insert(edge.dst);
                q.push(edge.dst);
            }
        }
    }

    // TODO: Actually remove unreachable states from aut if needed, 
    // but often we just care about the reachable subgraph.
    // Spot's postproc can clean up.

    // Deadlock detection: non-terminal states with no outgoing edges
    std::string exit_node = wir.value("exit_node", "");
    unsigned exit_s = (exit_node != "" && state_map.count(exit_node)) ? state_map[exit_node] : (unsigned)-1;

    for (unsigned s = 0; s < aut->num_states(); ++s) {
        if (reachable.count(s) && s != exit_s) {
            if (aut->out(s).begin() == aut->out(s).end()) {
                std::cerr << "Deadlock detected at state " << s << std::endl;
            }
        }
    }

    return aut;
}

bool AdvancedLifter::is_tau(bdd cond) {
    if (cond == bddtrue) return true;
    for (int idx : tau_bdd_indices_) {
        if (cond == bdd_ithvar(idx)) return true;
    }
    return false;
}

std::vector<bool> AdvancedLifter::compute_divergence(const spot::twa_graph_ptr& graph) {
    unsigned n = graph->num_states();
    std::vector<bool> is_divergent(n, false);
    
    std::vector<std::vector<unsigned>> tau_adj(n);
    std::vector<std::vector<unsigned>> tau_rev_adj(n);
    for (unsigned s = 0; s < n; ++s) {
        for (auto& edge : graph->out(s)) {
            if (is_tau(edge.cond)) {
                tau_adj[s].push_back(edge.dst);
                tau_rev_adj[edge.dst].push_back(s);
            }
        }
    }

    std::vector<int> disc(n, -1), low(n, -1);
    std::vector<bool> on_stack(n, false);
    std::stack<unsigned> st;
    int timer = 0;
    std::vector<unsigned> divergent_roots;

    auto dfs = [&](auto self, unsigned u) -> void {
        disc[u] = low[u] = ++timer;
        st.push(u);
        on_stack[u] = true;

        for (unsigned v : tau_adj[u]) {
            if (disc[v] == -1) {
                self(self, v);
                low[u] = std::min(low[u], low[v]);
            } else if (on_stack[v]) {
                low[u] = std::min(low[u], (int)disc[v]);
            }
        }

        if (low[u] == disc[u]) {
            std::vector<unsigned> component;
            while (true) {
                unsigned v = st.top();
                st.pop();
                on_stack[v] = false;
                component.push_back(v);
                if (u == v) break;
            }
            bool is_cycle = false;
            if (component.size() > 1) {
                is_cycle = true;
            } else {
                for (unsigned v : tau_adj[u]) {
                    if (v == u) { is_cycle = true; break; }
                }
            }
            if (is_cycle) {
                for (unsigned v : component) {
                    if (!is_divergent[v]) {
                        is_divergent[v] = true;
                        divergent_roots.push_back(v);
                    }
                }
            }
        }
    };

    for (unsigned i = 0; i < n; ++i) {
        if (disc[i] == -1) dfs(dfs, i);
    }

    std::queue<unsigned> q;
    for (unsigned v : divergent_roots) q.push(v);
    
    while (!q.empty()) {
        unsigned u = q.front();
        q.pop();
        for (unsigned v : tau_rev_adj[u]) {
            if (!is_divergent[v]) {
                is_divergent[v] = true;
                q.push(v);
            }
        }
    }

    return is_divergent;
}

spot::twa_graph_ptr AdvancedLifter::tarjan_tau_collapse(const spot::twa_graph_ptr& graph) {
    unsigned n = graph->num_states();
    std::vector<int> disc(n, -1), low(n, -1);
    std::vector<bool> on_stack(n, false);
    std::stack<unsigned> st;
    int timer = 0;

    std::vector<int> scc_id(n, -1);
    int scc_count = 0;

    auto dfs = [&](auto self, unsigned u) -> void {
        disc[u] = low[u] = ++timer;
        st.push(u);
        on_stack[u] = true;

        for (auto& edge : graph->out(u)) {
            if (is_tau(edge.cond)) {
                unsigned v = edge.dst;
                if (disc[v] == -1) {
                    self(self, v);
                    low[u] = std::min(low[u], low[v]);
                } else if (on_stack[v]) {
                    low[u] = std::min(low[u], (int)disc[v]);
                }
            }
        }

        if (low[u] == disc[u]) {
            while (true) {
                unsigned v = st.top();
                st.pop();
                on_stack[v] = false;
                scc_id[v] = scc_count;
                if (u == v) break;
            }
            scc_count++;
        }
    };

    for (unsigned i = 0; i < n; ++i) {
        if (disc[i] == -1) dfs(dfs, i);
    }

    auto collapsed = spot::make_twa_graph(graph->get_dict());
    // Copy APs from the source graph
    collapsed->copy_ap_of(graph);

    for (int i = 0; i < scc_count; ++i) collapsed->new_state();
    
    collapsed->set_init_state(scc_id[graph->get_init_state_number()]);

    for (unsigned s = 0; s < n; ++s) {
        for (auto& edge : graph->out(s)) {
            if (is_tau(edge.cond)) {
                if (scc_id[s] != scc_id[edge.dst]) {
                    collapsed->new_edge(scc_id[s], scc_id[edge.dst], bddtrue);
                }
            } else {
                collapsed->new_edge(scc_id[s], scc_id[edge.dst], edge.cond);
            }
        }
    }

    // Merge duplicate edges
    collapsed->merge_edges();
    return collapsed;
}

std::vector<size_t> AdvancedLifter::refine_blocks(const spot::twa_graph_ptr& combined, const std::vector<bool>& divergent) {
    unsigned n = combined->num_states();
    std::vector<size_t> block_id(n, 0);
    
    auto get_initial_signature = [&](unsigned s) {
        std::set<int> labels;
        for (auto& edge : combined->out(s)) {
            if (!is_tau(edge.cond)) {
                labels.insert(edge.cond.id());
            }
        }
        return std::make_pair(divergent[s], labels);
    };

    std::map<std::pair<bool, std::set<int>>, size_t> sig_to_block;
    for (unsigned s = 0; s < n; ++s) {
        auto sig = get_initial_signature(s);
        if (sig_to_block.find(sig) == sig_to_block.end()) {
            sig_to_block[sig] = sig_to_block.size();
        }
        block_id[s] = sig_to_block[sig];
    }

    bool changed = true;
    while (changed) {
        changed = false;
        
        std::vector<std::set<size_t>> tau_reachable_blocks(n);
        std::vector<std::map<int, std::set<size_t>>> observable_reachable_blocks(n);

        std::vector<unsigned> topo_order;
        std::vector<int> in_degree(n, 0);
        for (unsigned s = 0; s < n; ++s) {
            for (auto& edge : combined->out(s)) {
                if (is_tau(edge.cond)) in_degree[edge.dst]++;
            }
        }
        std::queue<unsigned> q;
        for (unsigned s = 0; s < n; ++s) if (in_degree[s] == 0) q.push(s);
        while (!q.empty()) {
            unsigned u = q.front(); q.pop();
            topo_order.push_back(u);
            for (auto& edge : combined->out(u)) {
                if (is_tau(edge.cond)) {
                    if (--in_degree[edge.dst] == 0) q.push(edge.dst);
                }
            }
        }

        for (auto it = topo_order.rbegin(); it != topo_order.rend(); ++it) {
            unsigned s = *it;
            for (auto& edge : combined->out(s)) {
                if (!is_tau(edge.cond)) {
                    observable_reachable_blocks[s][edge.cond.id()].insert(block_id[edge.dst]);
                } else {
                    unsigned dst = edge.dst;
                    tau_reachable_blocks[s].insert(block_id[dst]);
                    tau_reachable_blocks[s].insert(tau_reachable_blocks[dst].begin(), tau_reachable_blocks[dst].end());
                    for (auto const& [label, blocks] : observable_reachable_blocks[dst]) {
                        observable_reachable_blocks[s][label].insert(blocks.begin(), blocks.end());
                    }
                }
            }
        }
        
        for (unsigned s = 0; s < n; ++s) {
            for (auto& edge : combined->out(s)) {
                if (!is_tau(edge.cond)) {
                    unsigned dst = edge.dst;
                    observable_reachable_blocks[s][edge.cond.id()].insert(tau_reachable_blocks[dst].begin(), tau_reachable_blocks[dst].end());
                }
            }
        }

        using RefinedSig = std::tuple<size_t, std::set<size_t>, std::map<int, std::set<size_t>>>;
        std::map<RefinedSig, size_t> refined_sig_to_block;
        std::vector<size_t> next_block_id(n);
        for (unsigned s = 0; s < n; ++s) {
            RefinedSig sig = std::make_tuple(block_id[s], tau_reachable_blocks[s], observable_reachable_blocks[s]);
            if (refined_sig_to_block.find(sig) == refined_sig_to_block.end()) {
                refined_sig_to_block[sig] = refined_sig_to_block.size();
            }
            next_block_id[s] = refined_sig_to_block[sig];
        }

        if (next_block_id != block_id) {
            block_id = next_block_id;
            changed = true;
        }
    }
    return block_id;
}

bool AdvancedLifter::check_stuttering_bisimulation(const spot::twa_graph_ptr& aut1, const spot::twa_graph_ptr& aut2) {
    auto combined = spot::make_twa_graph(dict_);
    // Copy APs from both automata
    combined->copy_ap_of(aut1);
    combined->copy_ap_of(aut2);

    unsigned n1 = aut1->num_states();
    unsigned n2 = aut2->num_states();
    std::vector<unsigned> map1(n1), map2(n2);
    for (unsigned i = 0; i < n1; ++i) map1[i] = combined->new_state();
    for (unsigned i = 0; i < n2; ++i) map2[i] = combined->new_state();
    for (unsigned s = 0; s < n1; ++s) for (auto& edge : aut1->out(s)) combined->new_edge(map1[s], map1[edge.dst], edge.cond);
    for (unsigned s = 0; s < n2; ++s) for (auto& edge : aut2->out(s)) combined->new_edge(map2[s], map2[edge.dst], edge.cond);

    unsigned n = combined->num_states();
    std::vector<int> disc(n, -1), low(n, -1);
    std::vector<bool> on_stack(n, false);
    std::stack<unsigned> st;
    int timer = 0;
    std::vector<int> scc_id(n, -1);
    int scc_count = 0;
    std::vector<bool> scc_divergent;

    auto dfs = [&](auto self, unsigned u) -> void {
        disc[u] = low[u] = ++timer;
        st.push(u);
        on_stack[u] = true;
        for (auto& edge : combined->out(u)) {
            if (is_tau(edge.cond)) {
                unsigned v = edge.dst;
                if (disc[v] == -1) {
                    self(self, v);
                    low[u] = std::min(low[u], low[v]);
                } else if (on_stack[v]) {
                    low[u] = std::min(low[u], (int)disc[v]);
                }
            }
        }
        if (low[u] == disc[u]) {
            std::vector<unsigned> component;
            while (true) {
                unsigned v = st.top();
                st.pop();
                on_stack[v] = false;
                scc_id[v] = scc_count;
                component.push_back(v);
                if (u == v) break;
            }
            bool is_cycle = component.size() > 1;
            if (!is_cycle) {
                for (auto& edge : combined->out(u)) if (is_tau(edge.cond) && edge.dst == u) is_cycle = true;
            }
            scc_divergent.push_back(is_cycle);
            scc_count++;
        }
    };
    for (unsigned i = 0; i < n; ++i) if (disc[i] == -1) dfs(dfs, i);

    std::vector<std::vector<unsigned>> scc_rev_adj(scc_count);
    for (unsigned s = 0; s < n; ++s) {
        for (auto& edge : combined->out(s)) {
            if (is_tau(edge.cond) && scc_id[s] != scc_id[edge.dst]) {
                scc_rev_adj[scc_id[edge.dst]].push_back(scc_id[s]);
            }
        }
    }
    std::queue<unsigned> q;
    for (int i = 0; i < scc_count; ++i) if (scc_divergent[i]) q.push(i);
    while (!q.empty()) {
        unsigned u = q.front(); q.pop();
        for (unsigned v : scc_rev_adj[u]) {
            if (!scc_divergent[v]) {
                scc_divergent[v] = true;
                q.push(v);
            }
        }
    }

    auto collapsed = spot::make_twa_graph(dict_);
    collapsed->copy_ap_of(combined);
    for (int i = 0; i < scc_count; ++i) collapsed->new_state();
    for (unsigned s = 0; s < n; ++s) {
        for (auto& edge : combined->out(s)) {
            if (is_tau(edge.cond)) {
                if (scc_id[s] != scc_id[edge.dst]) collapsed->new_edge(scc_id[s], scc_id[edge.dst], bddtrue);
            } else {
                collapsed->new_edge(scc_id[s], scc_id[edge.dst], edge.cond);
            }
        }
    }
    collapsed->merge_edges();

    auto block_ids = refine_blocks(collapsed, scc_divergent);
    
    return block_ids[scc_id[map1[aut1->get_init_state_number()]]] == block_ids[scc_id[map2[aut2->get_init_state_number()]]];
}

std::string AdvancedLifter::compute_deterministic_hash(const spot::twa_graph_ptr& graph) {
    auto canon = spot::canonicalize(graph);
    std::stringstream ss;
    for (unsigned s = 0; s < canon->num_states(); ++s) {
        std::vector<std::string> edges;
        for (auto& edge : canon->out(s)) {
            edges.push_back(std::to_string(edge.cond.id()) + "->" + std::to_string(edge.dst));
        }
        std::sort(edges.begin(), edges.end());
        ss << "S" << s << ":";
        for (const auto& e : edges) ss << e << ";";
    }
    
    std::string s = ss.str();
    size_t h = std::hash<std::string>{}(s);
    char buf[64];
    snprintf(buf, sizeof(buf), "%016zx", h);
    return std::string(buf);
}

} // namespace vibecheck

// Pybind11 Binding
// Utilizing std::shared_ptr bound py::class_ to guarantee memory safety for bdd_dict and graph instances
// as detailed in Gotcha 1 (Pybind11 Memory Leaks and bdd_dict Ownership).
PYBIND11_MODULE(vibecheck_lifter, m) {
    m.doc() = "VibeCheck Advanced Lifter Module (C++ SPOT Integration)";

    // Minimal binding for spot::twa_graph so twa_graph_ptr can cross the C++/Python boundary.
    // We expose only the methods needed by tests and the Python orchestration layer.
    py::class_<spot::twa_graph, std::shared_ptr<spot::twa_graph>>(m, "TwaGraph")
        .def("num_states", &spot::twa_graph::num_states, "Returns the number of states in the automaton.")
        .def("num_edges", &spot::twa_graph::num_edges, "Returns the number of edges in the automaton.")
        .def("get_init_state_number", &spot::twa_graph::get_init_state_number,
             "Returns the initial state number.");

    py::class_<vibecheck::AdvancedLifter, std::shared_ptr<vibecheck::AdvancedLifter>>(m, "AdvancedLifter")
        .def(py::init<>())
        .def("parse_wir_types", &vibecheck::AdvancedLifter::parse_wir_types, 
             py::arg("wir_json_str"),
             "Parses WIR-Type layer JSON and registers variables to the BDD dictionary.")
        .def("lift_to_lts", &vibecheck::AdvancedLifter::lift_to_lts,
             py::arg("wir_json_str"),
             "Lifts WIR JSON to a SPOT LTS (twa_graph).")
        .def("tarjan_tau_collapse", &vibecheck::AdvancedLifter::tarjan_tau_collapse,
             py::arg("graph"),
             "Collapses SCCs in the tau-subgraph into macro-states.")
        .def("check_stuttering_bisimulation", &vibecheck::AdvancedLifter::check_stuttering_bisimulation,
             py::arg("aut1"), py::arg("aut2"),
             "Implements the Groote & Vaandrager algorithm for divergence-sensitive stuttering bisimulation.")
        .def("compute_deterministic_hash", &vibecheck::AdvancedLifter::compute_deterministic_hash,
             py::arg("graph"),
             "Generates a SHA-256 signature for minimized graphs.")
        .def("set_bpmn_tasks", &vibecheck::AdvancedLifter::set_bpmn_tasks,
             py::arg("tasks"),
             "Sets the reference BPMN tasks for semantic matching.")
        .def("semantic_match", &vibecheck::AdvancedLifter::semantic_match,
             py::arg("action_name"),
             "Maps an LLM action to a BPMN task using 3-tier matching.")
        .def("get_variable_map", &vibecheck::AdvancedLifter::get_variable_map,
             "Returns the internal mapping of variable names to BDD variable indices.");
}

