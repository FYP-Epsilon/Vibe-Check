//lifter.cpp
//
// Phase A + B Implementation
// ==========================
// Phase A: WIR → SPOT twa_graph Lifter
// Phase B: Divergence-Sensitive Stuttering Bisimulation (Groote–Vaandrager)
//
// See lifter.hpp for the public API contract.

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
#include <regex>
#include <numeric>
#include <spot/twaalgos/sccinfo.hh>
#include <spot/twaalgos/canonicalize.hh>
#include <spot/twaalgos/isdet.hh>
#include <spot/twaalgos/simulation.hh>
#include <spot/twaalgos/postproc.hh>
#include <spot/misc/hash.hh>

namespace py = pybind11;
using json = nlohmann::json;

namespace vibecheck {

// ═══════════════════════════════════════════════════════════════════════════
// Construction / Dictionary Management
// ═══════════════════════════════════════════════════════════════════════════

AdvancedLifter::AdvancedLifter() {
    dict_ = spot::make_bdd_dict();
    if (!dict_) {
        throw std::runtime_error("Failed to initialize SPOT BDD dictionary.");
    }
    registry_aut_ = spot::make_twa_graph(dict_);
}

spot::bdd_dict_ptr AdvancedLifter::get_dict() const {
    return dict_;
}

std::unordered_map<std::string, int> AdvancedLifter::get_variable_map() const {
    return bdd_vars_;
}

LifterDiagnostics AdvancedLifter::get_last_diagnostics() const {
    return last_diag_;
}

// ═══════════════════════════════════════════════════════════════════════════
// AP Registration
// ═══════════════════════════════════════════════════════════════════════════

void AdvancedLifter::register_variable(const std::string& var_name) {
    if (bdd_vars_.find(var_name) == bdd_vars_.end()) {
        int bdd_idx = registry_aut_->register_ap(var_name);
        bdd_vars_[var_name] = bdd_idx;
        if (var_name == "tau" || var_name == "silent" || var_name == "_") {
            tau_bdd_indices_.push_back(bdd_idx);
        }
    }
}

void AdvancedLifter::register_unresolved_type(const std::string& var_name) {
    std::string nd_var_name = var_name + "_ANY";
    if (bdd_vars_.find(nd_var_name) == bdd_vars_.end()) {
        int bdd_idx = registry_aut_->register_ap(nd_var_name);
        bdd_vars_[nd_var_name] = bdd_idx;
    }
}

bdd AdvancedLifter::ensure_ap(const spot::twa_graph_ptr& aut, const std::string& ap_name) {
    register_variable(ap_name);
    aut->register_ap(ap_name);
    return bdd_ithvar(bdd_vars_[ap_name]);
}

// ═══════════════════════════════════════════════════════════════════════════
// Semantic Matching (3-Tier Cascade)
// ═══════════════════════════════════════════════════════════════════════════

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
    try {
        py::gil_scoped_acquire acquire;
        py::object nlp_utils;
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
        std::cerr << "NLP Matching Error: " << e.what() << std::endl;
    }

    return "unlabeled_task";
}

// ═══════════════════════════════════════════════════════════════════════════
// Phase A: Action Extraction from WIR Node Code Arrays
// ═══════════════════════════════════════════════════════════════════════════

std::vector<std::string> AdvancedLifter::extract_actions_from_code(const std::vector<std::string>& code_lines) {
    std::vector<std::string> actions;

    static const std::regex call_re(R"((?:^|[^a-zA-Z0-9_])([a-zA-Z_][a-zA-Z0-9_]*)\s*\()");

    static const std::unordered_set<std::string> structural_builtins = {
        "print", "len", "range", "int", "str", "float", "bool", "list",
        "dict", "set", "tuple", "type", "isinstance", "hasattr", "getattr",
        "setattr", "super", "enumerate", "zip", "map", "filter", "sorted",
        "reversed", "min", "max", "sum", "abs", "round", "open", "input",
        "format", "repr", "id", "hash", "iter", "next", "vars", "dir",
        "append", "extend", "insert", "remove", "pop", "clear", "copy",
        "update", "get", "keys", "values", "items", "join", "split",
        "strip", "replace", "startswith", "endswith", "lower", "upper",
        "find", "count", "index", "encode", "decode",
        "self", "__init__", "__str__", "__repr__", "__len__",
    };

    for (const auto& line : code_lines) {
        std::sregex_iterator it(line.begin(), line.end(), call_re);
        std::sregex_iterator end;

        for (; it != end; ++it) {
            std::string func_name = (*it)[1].str();
            if (structural_builtins.count(func_name)) {
                continue;
            }
            actions.push_back(func_name);
        }
    }

    return actions;
}

// ═══════════════════════════════════════════════════════════════════════════
// Phase A: Label Resolution (Edges and Task Nodes)
// ═══════════════════════════════════════════════════════════════════════════

bdd AdvancedLifter::resolve_edge_label(const spot::twa_graph_ptr& aut, const std::string& raw_guard) {
    if (raw_guard.empty() || raw_guard == "true") {
        return bddtrue;
    }

    std::string matched = semantic_match(raw_guard);
    if (matched != "unlabeled_task") {
        matched_aps_set_.insert(matched);
        return ensure_ap(aut, matched);
    }

    std::string trimmed = raw_guard;
    while (!trimmed.empty() && std::isspace(trimmed.front())) trimmed.erase(trimmed.begin());
    while (!trimmed.empty() && std::isspace(trimmed.back())) trimmed.pop_back();

    if (!trimmed.empty()) {
        std::string ap_name;
        for (char c : trimmed) {
            if (std::isalnum(c) || c == '_') {
                ap_name += c;
            } else if (c == ' ' || c == '.' || c == '-') {
                if (!ap_name.empty() && ap_name.back() != '_') {
                    ap_name += '_';
                }
            }
        }
        while (!ap_name.empty() && ap_name.back() == '_') ap_name.pop_back();

        if (!ap_name.empty()) {
            if (!std::isalpha(ap_name.front())) {
                ap_name = "g_" + ap_name;
            }
            return ensure_ap(aut, ap_name);
        }
    }

    return bddtrue;
}

bdd AdvancedLifter::resolve_task_label(const spot::twa_graph_ptr& aut,
                                        const std::string& node_type,
                                        const std::vector<std::string>& code_lines) {
    if (node_type != "task") {
        return bddtrue;
    }

    if (code_lines.empty()) {
        return bddtrue;
    }

    auto actions = extract_actions_from_code(code_lines);

    if (actions.empty()) {
        return bddtrue;
    }

    bdd result = bddtrue;
    bool has_observable = false;

    for (const auto& action : actions) {
        std::string matched = semantic_match(action);
        if (matched != "unlabeled_task") {
            matched_aps_set_.insert(matched);
            bdd ap_bdd = ensure_ap(aut, matched);
            if (has_observable) {
                result &= ap_bdd;
            } else {
                result = ap_bdd;
                has_observable = true;
            }
        } else {
            unmatched_actions_set_.insert(action);
        }
    }

    return result;
}

// ═══════════════════════════════════════════════════════════════════════════
// Phase A: WIR Type Layer Parsing
// ═══════════════════════════════════════════════════════════════════════════

void AdvancedLifter::parse_wir_types(const std::string& wir_json_str) {
    json wir;
    try {
        wir = json::parse(wir_json_str);
    } catch (const json::parse_error& e) {
        throw std::invalid_argument(std::string("WIR JSON parsing failed: ") + e.what());
    }

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

    if (wir.contains("types") && wir["types"].is_object()) {
        for (auto it = wir["types"].begin(); it != wir["types"].end(); ++it) {
            std::string var_name = it.key();
            std::string type_val = it.value().get<std::string>();

            if (type_val == "Any" || type_val == "Union" || type_val == "Unresolved") {
                register_unresolved_type(var_name);
            } else {
                register_variable(var_name);
            }
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Phase A: Core Lift — WIR JSON → SPOT twa_graph
// ═══════════════════════════════════════════════════════════════════════════

spot::twa_graph_ptr AdvancedLifter::lift_to_lts(const std::string& wir_json_str) {
    last_diag_ = LifterDiagnostics{};
    matched_aps_set_.clear();
    unmatched_actions_set_.clear();

    json wir;
    try {
        wir = json::parse(wir_json_str);
    } catch (const json::parse_error& e) {
        throw std::invalid_argument(std::string("WIR JSON parsing failed: ") + e.what());
    }

    auto aut = spot::make_twa_graph(dict_);
    aut->copy_ap_of(registry_aut_);

    std::unordered_map<std::string, unsigned> state_map;
    std::unordered_map<std::string, std::string> node_types;
    std::unordered_map<std::string, std::vector<std::string>> node_code;
    std::unordered_set<std::string> exit_node_ids;

    std::string entry_node = wir.value("entry_node", "");
    std::string exit_node  = wir.value("exit_node", "");

    if (wir.contains("nodes") && wir["nodes"].is_array()) {
        for (const auto& node : wir["nodes"]) {
            std::string id;
            std::string type = "block";
            std::vector<std::string> code;

            if (node.is_string()) {
                id = node.get<std::string>();
            } else if (node.is_object()) {
                id = node.value("id", "");
                type = node.value("type", "block");
                if (node.contains("code") && node["code"].is_array()) {
                    for (const auto& line : node["code"]) {
                        if (line.is_string()) {
                            code.push_back(line.get<std::string>());
                        }
                    }
                }
            }

            if (id.empty()) continue;

            unsigned s = aut->new_state();
            state_map[id] = s;
            node_types[id] = type;
            node_code[id] = std::move(code);

            if (id == entry_node) {
                aut->set_init_state(s);
            }

            if (type == "exit") {
                exit_node_ids.insert(id);
            }
        }
    }

    if (entry_node.empty() || state_map.find(entry_node) == state_map.end()) {
        if (!state_map.empty()) {
            if (wir.contains("nodes") && !wir["nodes"].empty()) {
                std::string first_id;
                if (wir["nodes"][0].is_string()) first_id = wir["nodes"][0].get<std::string>();
                else if (wir["nodes"][0].is_object()) first_id = wir["nodes"][0].value("id", "");
                if (!first_id.empty() && state_map.count(first_id)) {
                    aut->set_init_state(state_map[first_id]);
                }
            }
        }
    }

    if (!exit_node.empty()) {
        exit_node_ids.insert(exit_node);
    }

    if (wir.contains("edges") && wir["edges"].is_array()) {
        for (const auto& edge : wir["edges"]) {
            std::string src_id, dst_id;
            if (edge.contains("source")) src_id = edge["source"].get<std::string>();
            else if (edge.contains("src")) src_id = edge["src"].get<std::string>();

            if (edge.contains("target")) dst_id = edge["target"].get<std::string>();
            else if (edge.contains("dst")) dst_id = edge["dst"].get<std::string>();

            if (state_map.find(src_id) == state_map.end() ||
                state_map.find(dst_id) == state_map.end()) {
                continue;
            }

            bdd task_label = bddtrue;
            auto type_it = node_types.find(src_id);
            auto code_it = node_code.find(src_id);
            if (type_it != node_types.end() && code_it != node_code.end()) {
                task_label = resolve_task_label(aut, type_it->second, code_it->second);
            }

            std::string raw_guard;
            if (edge.contains("guard") && !edge["guard"].is_null()) {
                raw_guard = edge["guard"].get<std::string>();
            } else if (edge.contains("condition") && !edge["condition"].is_null()) {
                raw_guard = edge["condition"].get<std::string>();
            }

            bdd guard_label = resolve_edge_label(aut, raw_guard);

            bdd final_label;
            if (task_label == bddtrue && guard_label == bddtrue) {
                final_label = bddtrue;
            } else if (task_label == bddtrue) {
                final_label = guard_label;
            } else if (guard_label == bddtrue) {
                final_label = task_label;
            } else {
                final_label = task_label & guard_label;
            }

            aut->new_edge(state_map[src_id], state_map[dst_id], final_label);
        }
    }

    std::set<unsigned> reachable;
    if (aut->num_states() > 0) {
        std::queue<unsigned> q;
        unsigned init_state = aut->get_init_state_number();
        q.push(init_state);
        reachable.insert(init_state);

        while (!q.empty()) {
            unsigned curr = q.front();
            q.pop();
            for (auto& e : aut->out(curr)) {
                if (reachable.find(e.dst) == reachable.end()) {
                    reachable.insert(e.dst);
                    q.push(e.dst);
                }
            }
        }
    }

    unsigned tau_count = 0;
    unsigned obs_count = 0;
    unsigned deadlock_count = 0;

    for (unsigned s = 0; s < aut->num_states(); ++s) {
        if (!reachable.count(s)) continue;

        bool has_outgoing = false;
        for (auto& e : aut->out(s)) {
            has_outgoing = true;
            if (e.cond == bddtrue) {
                ++tau_count;
            } else {
                ++obs_count;
            }
        }

        if (!has_outgoing) {
            bool is_exit = false;
            for (const auto& [nid, sid] : state_map) {
                if (sid == s && exit_node_ids.count(nid)) {
                    is_exit = true;
                    break;
                }
            }
            if (!is_exit) {
                ++deadlock_count;
                std::cerr << "Deadlock detected at state " << s << std::endl;
            }
        }
    }

    last_diag_.total_states       = aut->num_states();
    last_diag_.total_edges        = aut->num_edges();
    last_diag_.observable_edges   = obs_count;
    last_diag_.tau_edges          = tau_count;
    last_diag_.deadlock_states    = deadlock_count;
    last_diag_.unreachable_states = static_cast<unsigned>(aut->num_states() - reachable.size());
    last_diag_.matched_aps        = std::vector<std::string>(matched_aps_set_.begin(), matched_aps_set_.end());
    last_diag_.unmatched_actions   = std::vector<std::string>(unmatched_actions_set_.begin(), unmatched_actions_set_.end());

    return aut;
}

// ═══════════════════════════════════════════════════════════════════════════
// Phase A: Single-Call Entry Point
// ═══════════════════════════════════════════════════════════════════════════

spot::twa_graph_ptr AdvancedLifter::build_spot_automaton(const std::string& wir_json_str) {
    parse_wir_types(wir_json_str);
    return lift_to_lts(wir_json_str);
}

spot::twa_graph_ptr build_spot_automaton(
    const std::string& wir_json_str,
    const std::vector<std::string>& bpmn_tasks) {

    auto lifter = std::make_shared<AdvancedLifter>();
    if (!bpmn_tasks.empty()) {
        lifter->set_bpmn_tasks(bpmn_tasks);
    }
    return lifter->build_spot_automaton(wir_json_str);
}

// ═══════════════════════════════════════════════════════════════════════════
// Shared: Tau detection
// ═══════════════════════════════════════════════════════════════════════════

bool AdvancedLifter::is_tau(bdd cond) {
    if (cond == bddtrue) return true;
    for (int idx : tau_bdd_indices_) {
        if (cond == bdd_ithvar(idx)) return true;
    }
    return false;
}

// ═══════════════════════════════════════════════════════════════════════════
// Phase B — Step 1: Silent Subgraph Construction
// ═══════════════════════════════════════════════════════════════════════════

spot::twa_graph_ptr AdvancedLifter::build_silent_subgraph(const spot::twa_graph_ptr& graph) {
    unsigned n = graph->num_states();
    auto silent = spot::make_twa_graph(graph->get_dict());

    if (n == 0) return silent;

    // Create n+1 states: [0..n-1] mirror the original graph,
    // [n] is a synthetic super-initial with tau edges to every
    // original state. This guarantees spot::scc_info sees all
    // states as reachable — including those reachable only via
    // observable transitions in the original graph.
    for (unsigned i = 0; i <= n; ++i) silent->new_state();
    silent->set_init_state(n);

    for (unsigned i = 0; i < n; ++i) {
        silent->new_edge(n, i, bddtrue);
    }

    // Copy only tau transitions from the original graph
    for (unsigned s = 0; s < n; ++s) {
        for (auto& e : graph->out(s)) {
            if (is_tau(e.cond)) {
                silent->new_edge(s, e.dst, bddtrue);
            }
        }
    }

    return silent;
}

// ═══════════════════════════════════════════════════════════════════════════
// Phase B — Step 1: Divergence Detection (Livelock Catching)
// ═══════════════════════════════════════════════════════════════════════════

std::vector<bool> AdvancedLifter::detect_divergent_states(const spot::twa_graph_ptr& graph) {
    unsigned n = graph->num_states();
    if (n == 0) return {};

    std::vector<bool> divergent(n, false);

    // ── 1. Build silent subgraph ────────────────────────────────────────
    auto silent = build_silent_subgraph(graph);

    // ── 2. Run spot::scc_info on the silent subgraph ────────────────────
    spot::scc_info si(silent);
    unsigned scc_count = si.scc_count();

    // Build SCC → member-states mapping via scc_of().
    // (Avoids reliance on scc_info_options::TRACK_STATES which may
    //  not be default in all SPOT versions.)
    std::vector<std::vector<unsigned>> scc_members(scc_count);
    for (unsigned s = 0; s <= n; ++s) {
        unsigned scc_id = si.scc_of(s);
        if (scc_id < scc_count) {
            scc_members[scc_id].push_back(s);
        }
    }

    // ── 3. Mark directly divergent SCCs ─────────────────────────────────
    // An SCC is divergent if:
    //   (a) It contains more than one state, OR
    //   (b) It is a single original state with a tau self-loop.
    //
    // Note: the synthetic super-initial (state n) has no incoming edges,
    // so it is always in its own trivial SCC and never pollutes the
    // divergence analysis.
    for (unsigned scc = 0; scc < scc_count; ++scc) {
        const auto& members = scc_members[scc];
        bool is_div = false;

        if (members.size() > 1) {
            // Multi-state SCC ⇒ tau cycle ⇒ divergent
            is_div = true;
        } else if (members.size() == 1 && members[0] < n) {
            // Single original state — check for tau self-loop
            unsigned s = members[0];
            for (auto& e : silent->out(s)) {
                if (e.dst == s) { is_div = true; break; }
            }
        }

        if (is_div) {
            for (unsigned s : members) {
                if (s < n) divergent[s] = true;
            }
        }
    }

    // ── 4. Backward BFS: propagate divergence along tau edges ───────────
    // Any state that can reach a divergent state via a tau-only path
    // can itself engage in an infinite tau-sequence (by reaching the
    // divergent SCC and looping). Mark it divergent.
    std::vector<std::vector<unsigned>> tau_rev(n);
    for (unsigned s = 0; s < n; ++s) {
        for (auto& e : graph->out(s)) {
            if (is_tau(e.cond) && e.dst < n) {
                tau_rev[e.dst].push_back(s);
            }
        }
    }

    std::queue<unsigned> bfs_q;
    for (unsigned s = 0; s < n; ++s) {
        if (divergent[s]) bfs_q.push(s);
    }

    while (!bfs_q.empty()) {
        unsigned u = bfs_q.front();
        bfs_q.pop();
        for (unsigned pred : tau_rev[u]) {
            if (!divergent[pred]) {
                divergent[pred] = true;
                bfs_q.push(pred);
            }
        }
    }

    return divergent;
}

// ═══════════════════════════════════════════════════════════════════════════
// Phase B — Step 2: Groote–Vaandrager Partition Refinement
// ═══════════════════════════════════════════════════════════════════════════

std::vector<unsigned> AdvancedLifter::partition_refinement(
    const spot::twa_graph_ptr& graph,
    const std::vector<bool>& divergent) {

    unsigned n = graph->num_states();
    if (n == 0) return {};

    std::vector<unsigned> block(n);
    unsigned num_blocks;

    // ── Initial partition: strictly separate divergent from non-divergent ─
    {
        bool has_div = false, has_nondiv = false;
        for (unsigned s = 0; s < n; ++s) {
            if (divergent[s]) has_div = true;
            else has_nondiv = true;
        }

        if (has_nondiv && has_div) {
            num_blocks = 2;
            for (unsigned s = 0; s < n; ++s) {
                block[s] = divergent[s] ? 1 : 0;
            }
        } else {
            num_blocks = 1;
            for (unsigned s = 0; s < n; ++s) block[s] = 0;
        }
    }

    // ── Precompute reverse adjacency for backward BFS ────────────────────
    struct RevEdge { unsigned src; bdd cond; };
    std::vector<std::vector<RevEdge>> rev_adj(n);
    for (unsigned s = 0; s < n; ++s) {
        for (auto& e : graph->out(s)) {
            rev_adj[e.dst].push_back({s, e.cond});
        }
    }

    // ── Iterative refinement ─────────────────────────────────────────────
    //
    // For each splitter (label, target_block):
    //   For each block B:
    //     1. Find "direct" states in B that have the required transition.
    //     2. Backward BFS within B via INERT tau-transitions (tau
    //        transitions whose source and destination share block B)
    //        to find all "stable" states.
    //     3. If B is not uniformly stable, split it.
    //
    // A transition is a "splitter match" if:
    //   - For observable action a:   edge.cond matches a AND
    //                                 block[edge.dst] == target_block.
    //   - For non-inert tau:         is_tau(edge.cond) AND
    //                                 block[edge.dst] == target_block AND
    //                                 block[edge.src] ≠ block[edge.dst].

    bool changed = true;
    while (changed) {
        changed = false;

        // Collect current splitters
        std::set<std::pair<int, unsigned>> splitters;
        for (unsigned s = 0; s < n; ++s) {
            for (auto& e : graph->out(s)) {
                if (!is_tau(e.cond)) {
                    // Observable action → (bdd_id, target_block)
                    splitters.emplace(e.cond.id(), block[e.dst]);
                } else if (block[s] != block[e.dst]) {
                    // Non-inert tau → sentinel -1
                    splitters.emplace(-1, block[e.dst]);
                }
            }
        }

        for (const auto& [label_id, target_blk] : splitters) {
            // Rebuild block membership (safe against mid-loop splits)
            std::unordered_map<unsigned, std::vector<unsigned>> blk_members;
            for (unsigned s = 0; s < n; ++s) {
                blk_members[block[s]].push_back(s);
            }

            for (auto& [b, members] : blk_members) {
                if (members.size() <= 1) continue;

                // ── Find direct states ──
                std::unordered_set<unsigned> direct;
                for (unsigned s : members) {
                    for (auto& e : graph->out(s)) {
                        bool matches = false;
                        if (label_id == -1) {
                            // Non-inert tau splitter
                            matches = is_tau(e.cond) &&
                                      block[e.dst] == target_blk &&
                                      block[s] != block[e.dst];
                        } else {
                            // Observable action splitter
                            matches = (e.cond.id() == label_id) &&
                                      block[e.dst] == target_blk;
                        }
                        if (matches) { direct.insert(s); break; }
                    }
                }

                if (direct.empty() || direct.size() == members.size()) continue;

                // ── Backward BFS within block via inert tau ──
                std::unordered_set<unsigned> stable(direct);
                std::queue<unsigned> q;
                for (unsigned s : direct) q.push(s);

                while (!q.empty()) {
                    unsigned u = q.front();
                    q.pop();
                    for (const auto& re : rev_adj[u]) {
                        if (block[re.src] == b &&
                            is_tau(re.cond) &&
                            !stable.count(re.src)) {
                            stable.insert(re.src);
                            q.push(re.src);
                        }
                    }
                }

                // ── Split ──
                if (stable.size() < members.size()) {
                    unsigned new_blk = num_blocks++;
                    for (unsigned s : members) {
                        if (!stable.count(s)) {
                            block[s] = new_blk;
                        }
                    }
                    changed = true;
                }
            }
        }
    }

    // ── Renumber blocks contiguously 0..k-1 ──────────────────────────────
    std::map<unsigned, unsigned> remap;
    for (unsigned s = 0; s < n; ++s) {
        if (remap.find(block[s]) == remap.end()) {
            unsigned next = static_cast<unsigned>(remap.size());
            remap[block[s]] = next;
        }
        block[s] = remap[block[s]];
    }

    return block;
}

// ═══════════════════════════════════════════════════════════════════════════
// Phase B — Quotient Automaton Construction
// ═══════════════════════════════════════════════════════════════════════════

spot::twa_graph_ptr AdvancedLifter::build_quotient(
    const spot::twa_graph_ptr& graph,
    const std::vector<unsigned>& partition,
    unsigned num_blocks) {

    auto quotient = spot::make_twa_graph(graph->get_dict());
    quotient->copy_ap_of(graph);

    for (unsigned i = 0; i < num_blocks; ++i) quotient->new_state();

    unsigned n = graph->num_states();
    if (n == 0) return quotient;

    quotient->set_init_state(partition[graph->get_init_state_number()]);

    // Add edges, skipping inert tau (within same block) and deduplicating
    std::set<std::tuple<unsigned, unsigned, int>> seen;
    for (unsigned s = 0; s < n; ++s) {
        unsigned src_blk = partition[s];
        for (auto& e : graph->out(s)) {
            unsigned dst_blk = partition[e.dst];

            // Inert tau transitions are absorbed — they are invisible
            if (is_tau(e.cond) && src_blk == dst_blk) continue;

            auto key = std::make_tuple(src_blk, dst_blk, e.cond.id());
            if (seen.insert(key).second) {
                quotient->new_edge(src_blk, dst_blk, e.cond);
            }
        }
    }

    quotient->merge_edges();
    return quotient;
}

// ═══════════════════════════════════════════════════════════════════════════
// Phase B — Public API: minimize_stuttering / compute_bisimulation_full
// ═══════════════════════════════════════════════════════════════════════════

spot::twa_graph_ptr AdvancedLifter::minimize_stuttering(const spot::twa_graph_ptr& graph) {
    auto div = detect_divergent_states(graph);
    auto partition = partition_refinement(graph, div);

    unsigned num_blocks = 0;
    for (unsigned b : partition) {
        num_blocks = std::max(num_blocks, b + 1);
    }

    return build_quotient(graph, partition, num_blocks);
}

BisimulationResult AdvancedLifter::compute_bisimulation_full(const spot::twa_graph_ptr& graph) {
    BisimulationResult result;
    result.original_states = graph->num_states();

    result.divergent = detect_divergent_states(graph);
    result.num_divergent = static_cast<unsigned>(
        std::count(result.divergent.begin(), result.divergent.end(), true));

    result.partition = partition_refinement(graph, result.divergent);

    unsigned num_blocks = 0;
    for (unsigned b : result.partition) {
        num_blocks = std::max(num_blocks, b + 1);
    }

    result.num_partition_blocks = num_blocks;
    result.quotient_states = num_blocks;
    result.quotient = build_quotient(graph, result.partition, num_blocks);

    return result;
}

// ═══════════════════════════════════════════════════════════════════════════
// Phase B — Public API: check_stuttering_bisimulation
// ═══════════════════════════════════════════════════════════════════════════

bool AdvancedLifter::check_stuttering_bisimulation(
    const spot::twa_graph_ptr& aut1,
    const spot::twa_graph_ptr& aut2) {

    // Build the disjoint union of both automata.
    // States [0..n1-1] come from aut1, [n1..n1+n2-1] from aut2.
    auto combined = spot::make_twa_graph(dict_);
    combined->copy_ap_of(aut1);
    combined->copy_ap_of(aut2);

    unsigned n1 = aut1->num_states();
    unsigned n2 = aut2->num_states();

    for (unsigned i = 0; i < n1 + n2; ++i) combined->new_state();
    if (n1 + n2 > 0) combined->set_init_state(0);

    for (unsigned s = 0; s < n1; ++s) {
        for (auto& e : aut1->out(s)) {
            combined->new_edge(s, e.dst, e.cond);
        }
    }

    for (unsigned s = 0; s < n2; ++s) {
        for (auto& e : aut2->out(s)) {
            combined->new_edge(n1 + s, n1 + e.dst, e.cond);
        }
    }

    // Run full Phase B on the combined graph
    auto divergent = detect_divergent_states(combined);
    auto partition = partition_refinement(combined, divergent);

    // Bisimilar iff initial states land in the same partition block
    unsigned init1 = aut1->get_init_state_number();
    unsigned init2 = n1 + aut2->get_init_state_number();

    return partition[init1] == partition[init2];
}

// ═══════════════════════════════════════════════════════════════════════════
// Phase B — Tau-SCC Collapse (rewritten with spot::scc_info)
// ═══════════════════════════════════════════════════════════════════════════

spot::twa_graph_ptr AdvancedLifter::tarjan_tau_collapse(const spot::twa_graph_ptr& graph) {
    unsigned n = graph->num_states();
    if (n == 0) return spot::make_twa_graph(graph->get_dict());

    // Run spot::scc_info on the silent subgraph
    auto silent = build_silent_subgraph(graph);
    spot::scc_info si(silent);

    // Identify which SCCs contain original states (exclude super-initial)
    std::set<unsigned> original_sccs;
    std::vector<unsigned> state_scc(n);
    for (unsigned s = 0; s < n; ++s) {
        unsigned scc_id = si.scc_of(s);
        state_scc[s] = scc_id;
        original_sccs.insert(scc_id);
    }

    // Map SCCs → collapsed graph state IDs (contiguous)
    std::unordered_map<unsigned, unsigned> scc_to_cstate;
    unsigned cstate_count = 0;
    for (unsigned scc : original_sccs) {
        scc_to_cstate[scc] = cstate_count++;
    }

    auto collapsed = spot::make_twa_graph(graph->get_dict());
    collapsed->copy_ap_of(graph);
    for (unsigned i = 0; i < cstate_count; ++i) collapsed->new_state();

    collapsed->set_init_state(scc_to_cstate[state_scc[graph->get_init_state_number()]]);

    // Add inter-SCC edges
    for (unsigned s = 0; s < n; ++s) {
        unsigned src_cs = scc_to_cstate[state_scc[s]];
        for (auto& e : graph->out(s)) {
            unsigned dst_cs = scc_to_cstate[state_scc[e.dst]];
            if (is_tau(e.cond)) {
                if (src_cs != dst_cs) {
                    collapsed->new_edge(src_cs, dst_cs, bddtrue);
                }
            } else {
                collapsed->new_edge(src_cs, dst_cs, e.cond);
            }
        }
    }

    collapsed->merge_edges();
    return collapsed;
}

// ═══════════════════════════════════════════════════════════════════════════
// Deterministic Hashing
// ═══════════════════════════════════════════════════════════════════════════

} // namespace vibecheck

// ═══════════════════════════════════════════════════════════════════════════
// Pybind11 Module Definition
// ═══════════════════════════════════════════════════════════════════════════

PYBIND11_MODULE(vibecheck_lifter, m) {
    m.doc() = "VibeCheck C++ Engine — Phase A (Lifter) + Phase B (Stuttering Bisimulation)";

    // -- LifterDiagnostics (Phase A) --------------------------------------
    py::class_<vibecheck::LifterDiagnostics>(m, "LifterDiagnostics")
        .def(py::init<>())
        .def_readonly("total_states",       &vibecheck::LifterDiagnostics::total_states)
        .def_readonly("total_edges",        &vibecheck::LifterDiagnostics::total_edges)
        .def_readonly("observable_edges",   &vibecheck::LifterDiagnostics::observable_edges)
        .def_readonly("tau_edges",          &vibecheck::LifterDiagnostics::tau_edges)
        .def_readonly("deadlock_states",    &vibecheck::LifterDiagnostics::deadlock_states)
        .def_readonly("unreachable_states", &vibecheck::LifterDiagnostics::unreachable_states)
        .def_readonly("matched_aps",        &vibecheck::LifterDiagnostics::matched_aps)
        .def_readonly("unmatched_actions",  &vibecheck::LifterDiagnostics::unmatched_actions)
        .def("__repr__", [](const vibecheck::LifterDiagnostics& d) {
            return "<LifterDiagnostics states=" + std::to_string(d.total_states)
                 + " edges=" + std::to_string(d.total_edges)
                 + " observable=" + std::to_string(d.observable_edges)
                 + " tau=" + std::to_string(d.tau_edges)
                 + " deadlocks=" + std::to_string(d.deadlock_states)
                 + " unreachable=" + std::to_string(d.unreachable_states) + ">";
        });

    // -- BisimulationResult (Phase B) -------------------------------------
    py::class_<vibecheck::BisimulationResult>(m, "BisimulationResult")
        .def(py::init<>())
        .def_readonly("quotient",             &vibecheck::BisimulationResult::quotient)
        .def_readonly("original_states",      &vibecheck::BisimulationResult::original_states)
        .def_readonly("quotient_states",      &vibecheck::BisimulationResult::quotient_states)
        .def_readonly("num_divergent",        &vibecheck::BisimulationResult::num_divergent)
        .def_readonly("num_partition_blocks", &vibecheck::BisimulationResult::num_partition_blocks)
        .def_readonly("partition",            &vibecheck::BisimulationResult::partition)
        .def_readonly("divergent",            &vibecheck::BisimulationResult::divergent)
        .def("__repr__", [](const vibecheck::BisimulationResult& r) {
            return "<BisimulationResult original=" + std::to_string(r.original_states)
                 + " quotient=" + std::to_string(r.quotient_states)
                 + " divergent=" + std::to_string(r.num_divergent)
                 + " blocks=" + std::to_string(r.num_partition_blocks) + ">";
        });

    // -- TwaGraph binding -------------------------------------------------
    py::class_<spot::twa_graph, std::shared_ptr<spot::twa_graph>>(m, "TwaGraph")
        .def("num_states", &spot::twa_graph::num_states, "Returns the number of states.")
        .def("num_edges", &spot::twa_graph::num_edges, "Returns the number of edges.")
        .def("get_init_state_number", &spot::twa_graph::get_init_state_number,
             "Returns the initial state number.");

    // -- AdvancedLifter class ---------------------------------------------
    py::class_<vibecheck::AdvancedLifter, std::shared_ptr<vibecheck::AdvancedLifter>>(m, "AdvancedLifter")
        .def(py::init<>())
        // Phase A
        .def("parse_wir_types", &vibecheck::AdvancedLifter::parse_wir_types, 
             py::arg("wir_json_str"))
        .def("lift_to_lts", &vibecheck::AdvancedLifter::lift_to_lts,
             py::arg("wir_json_str"))
        .def("build_spot_automaton", &vibecheck::AdvancedLifter::build_spot_automaton,
             py::arg("wir_json_str"),
             "Single-call Phase A entry point.")
        .def("get_last_diagnostics", &vibecheck::AdvancedLifter::get_last_diagnostics)
        // Phase B
        .def("detect_divergent_states", &vibecheck::AdvancedLifter::detect_divergent_states,
             py::arg("graph"),
             "Detect divergent states using spot::scc_info on the silent subgraph.")
        .def("minimize_stuttering", &vibecheck::AdvancedLifter::minimize_stuttering,
             py::arg("graph"),
             "Minimize via divergence-sensitive stuttering bisimulation → quotient automaton.")
        .def("compute_bisimulation_full", &vibecheck::AdvancedLifter::compute_bisimulation_full,
             py::arg("graph"),
             "Full bisimulation analysis with partition and divergence diagnostics.")
        .def("check_stuttering_bisimulation", &vibecheck::AdvancedLifter::check_stuttering_bisimulation,
             py::arg("aut1"), py::arg("aut2"),
             "Check two automata for stuttering bisimilarity.")
        .def("tarjan_tau_collapse", &vibecheck::AdvancedLifter::tarjan_tau_collapse,
             py::arg("graph"),
             "Collapse tau-SCCs into macro-states (uses spot::scc_info).")
        // Matching
        .def("set_bpmn_tasks", &vibecheck::AdvancedLifter::set_bpmn_tasks,
             py::arg("tasks"))
        .def("semantic_match", &vibecheck::AdvancedLifter::semantic_match,
             py::arg("action_name"))
        .def("get_variable_map", &vibecheck::AdvancedLifter::get_variable_map);

}
