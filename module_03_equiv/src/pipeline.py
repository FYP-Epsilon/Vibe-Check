"""
Module 03 — Equivalence Checking Engine: Main Pipeline Orchestrator
=====================================================================
Executes the full 4-phase pipeline:

    Phase A → WIR Lifter (lifter.py / C++ vibecheck_lifter)
    Phase B → Stuttering Bisimulation Engine
    Phase C → Pairwise Behavioural Clustering
    Phase D → LTL Model Checking via Synchronous Product (C++)

Usage::

    python -m src.pipeline              # default demo WIR
    python -m src.pipeline input.json   # from file
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

from .lifter import LTS, LifterConfig, QualityGateError, WIRLifter
from .stuttering_engine import StutteringEngine, StutteringResult
from .clustering import BehavioralClusterer, ClusterResult
from .model_checker import ModelChecker, PropertyMonitor, VerificationVerdict

# Optional C++ engine — gracefully degrade to pure-Python if not compiled
try:
    import vibecheck_lifter as _cpp
    HAS_CPP_ENGINE = True
except ImportError:
    _cpp = None  # type: ignore[assignment]
    HAS_CPP_ENGINE = False

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-30s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("module_03_equiv.pipeline")


# ---------------------------------------------------------------------------
# Phase C: C++ Batch Orchestrator
# ---------------------------------------------------------------------------

def process_wir_batch(
    wir_json_strings: list[str],
    *,
    bpmn_tasks: list[str] | None = None,
    ltl_property: str = 'G("approved")',
) -> dict:
    """
    Process a batch of WIR JSON strings through the C++ engine.

    CRITICAL INVARIANT: Exactly ONE AdvancedLifter is instantiated so that
    all automata share the same ``bdd_dict``.  This is required for SPOT's
    ``are_isomorphic()`` (and therefore ``cluster_implementations()``) to
    work correctly.

    Steps:
        1. Instantiate a single ``AdvancedLifter``.
        2. For each WIR variant, call ``build_spot_automaton()`` then
           ``minimize_stuttering()`` — producing the quotient automaton.
        3. Collect all quotients into a list.
        4. Pass the list to ``cluster_implementations()`` (C++).

    Args:
        wir_json_strings: List of WIR JSON strings (one per LLM implementation).
        bpmn_tasks: Optional list of BPMN task names for semantic matching.

    Returns:
        A dict with keys:
            ``quotients``  — list of minimized TwaGraph objects.
            ``diagnostics`` — list of LifterDiagnostics (one per input).
            ``clusters``   — dict[cluster_id] → {indices, representative, compliance}.

        Raises:
            RuntimeError: If the C++ engine is not available.
        """
    if not HAS_CPP_ENGINE:
        raise RuntimeError(
            "vibecheck_lifter C++ module not available. "
            "Build it with CMake first (see module_03_equiv/CMakeLists.txt)."
        )

    # ── Step 1: Single lifter instance (shared bdd_dict) ──────────────
    lifter = _cpp.AdvancedLifter()

    if bpmn_tasks:
        lifter.set_bpmn_tasks(bpmn_tasks)

    # ── Steps 2–3: Build + minimize each variant ─────────────────────
    quotients: list = []
    diagnostics: list = []

    for idx, wir_json_str in enumerate(wir_json_strings):
        logger.info("Processing variant %d/%d", idx + 1, len(wir_json_strings))

        # Phase A: WIR → SPOT automaton
        graph = lifter.build_spot_automaton(wir_json_str)
        diag = lifter.get_last_diagnostics()
        diagnostics.append(diag)

        # Phase B: Stuttering bisimulation → quotient
        quotient = lifter.minimize_stuttering(graph)
        quotients.append(quotient)

        logger.info(
            "  Variant %d: %d states → %d quotient states, %d edges",
            idx,
            graph.num_states(),
            quotient.num_states(),
            quotient.num_edges(),
        )

    # ── Step 4: Cluster via C++ isomorphism engine ───────────────────
    raw_clusters = _cpp.cluster_implementations(quotients)

    # Convert to a plain dict for easy serialisation
    clusters: dict[int, dict] = {}
    for cid, entry in raw_clusters.items():
        clusters[int(cid)] = {
            "indices": list(entry.indices),
            "representative": entry.representative,
        }

    logger.info(
        "Clustering complete: %d variants → %d cluster(s)",
        len(wir_json_strings),
        len(clusters),
    )

    # ── Step 5: Phase D — Model check each representative ───────────────
    logger.info("Phase D: Model checking with LTL property: %s", ltl_property)

    for cid, cluster_info in clusters.items():
        rep = cluster_info["representative"]
        try:
            compliance = _cpp.check_compliance(rep, ltl_property)
            cluster_info["compliance"] = {
                "ltl_property": ltl_property,
                "is_compliant": compliance.is_compliant,
                "verdict": "PASS" if compliance.is_compliant else "FAIL",
                "counter_example_trace": compliance.counter_example_trace,
            }
            verdict_icon = "✅" if compliance.is_compliant else "❌"
            logger.info(
                "  Cluster %d: %s %s",
                cid,
                verdict_icon,
                "PASS" if compliance.is_compliant else "FAIL",
            )
        except Exception as exc:
            logger.warning(
                "  Cluster %d: Phase D error: %s", cid, exc
            )
            cluster_info["compliance"] = {
                "ltl_property": ltl_property,
                "is_compliant": None,
                "verdict": "ERROR",
                "counter_example_trace": "",
                "error": str(exc),
            }

    return {
        "quotients": quotients,
        "diagnostics": diagnostics,
        "clusters": clusters,
    }


# ---------------------------------------------------------------------------
# Demo / Integration WIR
# ---------------------------------------------------------------------------

DEMO_WIR: dict = {
    "entry_node": "node_1",
    "exit_node": "node_6",
    "nodes": [
        {"id": "node_1", "type": "entry",   "successors": ["node_2"], "predecessors": [],         "control_vars": [], "data_vars": []},
        {"id": "node_2", "type": "task",     "successors": ["node_3"], "predecessors": ["node_1"], "control_vars": [], "data_vars": [],   "guard": None},
        {"id": "node_3", "type": "gateway",  "successors": ["node_4", "node_5"], "predecessors": ["node_2"], "control_vars": ["approved"], "data_vars": [], "guard": "approved"},
        {"id": "node_4", "type": "task",     "successors": ["node_6"], "predecessors": ["node_3"], "control_vars": [], "data_vars": []},
        {"id": "node_5", "type": "task",     "successors": ["node_6"], "predecessors": ["node_3"], "control_vars": [], "data_vars": []},
        {"id": "node_6", "type": "exit",     "successors": [],          "predecessors": ["node_4", "node_5"], "control_vars": [], "data_vars": []},
    ],
    "edges": [
        {"source": "node_1", "target": "node_2", "guard": None, "exception_type": None},
        {"source": "node_2", "target": "node_3", "guard": None, "exception_type": None},
        {"source": "node_3", "target": "node_4", "guard": "approved",      "exception_type": None},
        {"source": "node_3", "target": "node_5", "guard": "not approved", "exception_type": None},
        {"source": "node_4", "target": "node_6", "guard": None, "exception_type": None},
        {"source": "node_5", "target": "node_6", "guard": None, "exception_type": None},
    ],
    "functions": {
        "process_batch_orders": {
            "entry_node": "fn_1",
            "exit_node": "fn_5",
            "nodes": [
                {"id": "fn_1", "type": "entry",   "successors": ["fn_2"], "predecessors": [],       "control_vars": [], "data_vars": []},
                {"id": "fn_2", "type": "loop",    "successors": ["fn_3"], "predecessors": ["fn_1"], "control_vars": [], "data_vars": [], "guard": "iter order_quantities", "ast_type": "For"},
                {"id": "fn_3", "type": "task",    "successors": ["fn_4"], "predecessors": ["fn_3"], "control_vars": [], "data_vars": []},
                {"id": "fn_4", "type": "gateway", "successors": ["fn_2", "fn_5"], "predecessors": ["fn_3"], "control_vars": ["inventory_level"], "data_vars": [], "guard": "inventory_level == 0"},
                {"id": "fn_5", "type": "exit",    "successors": [],        "predecessors": ["fn_4"], "control_vars": [], "data_vars": []},
            ],
            "edges": [
                {"source": "fn_1", "target": "fn_2", "guard": None,                     "exception_type": None},
                {"source": "fn_2", "target": "fn_3", "guard": "iter order_quantities", "exception_type": None},
                {"source": "fn_3", "target": "fn_4", "guard": None,                     "exception_type": None},
                {"source": "fn_4", "target": "fn_2", "guard": "inventory_level == 0",  "exception_type": None},
                {"source": "fn_4", "target": "fn_5", "guard": "not inventory_level == 0", "exception_type": None},
            ],
        }
    },
    "guard_extraction": {
        "total": 6,
        "success": 6,
        "conditions": ["approved", "not approved", "iter order_quantities", "inventory_level == 0", "not inventory_level == 0"]
    },
    "certificate": {
        "version": "V3",
        "node_coverage": 1.0,
        "edge_coverage": 1.0,
        "guard_success_rate": 1.0,
        "abort": False,
        "message": "V3 structural extraction passed quality gate."
    }
}


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

def run_pipeline(wir_json: dict) -> dict:
    """
    Execute the full 4-phase equivalence-checking pipeline.

    Returns a summary dict suitable for JSON serialisation.
    """
    summary: dict = {"phases": {}}
    t0 = time.perf_counter()

    # ── Phase A: Lifter ──────────────────────────────────────────────────
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  Phase A: Advanced Python Lifter                           ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    lifter = WIRLifter(LifterConfig(
        confidence_threshold=0.95,
        loop_max=3,
        abort_on_low_confidence=True,
    ))

    try:
        lts_list = lifter.lift(wir_json)
    except QualityGateError as exc:
        print(f"  ❌ QUALITY GATE ABORT: {exc}")
        summary["phases"]["A"] = {"status": "ABORT", "error": str(exc)}
        summary["overall"] = "ABORT"
        return summary

    for lts in lts_list:
        print(f"  ✅ {lts}")

    summary["phases"]["A"] = {
        "status": "OK",
        "lts_count": len(lts_list),
        "lts_models": [
            {
                "name": l.name,
                "states": l.num_states(),
                "transitions": l.num_transitions(),
                "cyclomatic_complexity": l.cyclomatic_complexity(),
            }
            for l in lts_list
        ],
    }

    # ── Phase B: Stuttering Engine ───────────────────────────────────────
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  Phase B: Divergence-Sensitive Stuttering Engine            ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    engine = StutteringEngine()
    
    # Cache compilation dict to optimize execution footprint
    results_cache: dict[str, StutteringResult] = {}
    per_lts_summary: list[dict] = []

    for lts in lts_list:
        # Compute EXACTLY once per structural variant
        result = engine.compute(lts)
        results_cache[lts.name] = result
        
        div_count = len(result.divergent_states)
        print(
            f"  {lts.name}: {result.num_blocks} equivalence classes, "
            f"{div_count} divergent states, "
            f"{len(result.scc_components)} SCCs"
        )
        
        per_lts_summary.append({
            "name": lts.name,
            "blocks": result.num_blocks,
            "divergent": div_count,
        })

    summary["phases"]["B"] = {
        "status": "OK",
        "per_lts": per_lts_summary,
    }

    # ── Phase C: Pairwise Clustering ─────────────────────────────────────
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  Phase C: Pairwise Behavioural Clustering                   ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    clusterer = BehavioralClusterer(engine)
    cluster_result: ClusterResult = clusterer.cluster(lts_list)

    print(f"  Clusters: {cluster_result.num_clusters}")
    for cid, members in cluster_result.clusters.items():
        rep = cluster_result.representatives.get(cid, "?")
        print(f"    Cluster {cid}: {members}  (representative: {rep})")
    if cluster_result.singleton_anomalies:
        print(f"  ⚠  Singleton anomalies: {cluster_result.singleton_anomalies}")

    summary["phases"]["C"] = {
        "status": "OK",
        "num_clusters": cluster_result.num_clusters,
        "clusters": {
            str(k): v for k, v in cluster_result.clusters.items()
        },
        "representatives": {
            str(k): v for k, v in cluster_result.representatives.items()
        },
        "singleton_anomalies": cluster_result.singleton_anomalies,
    }

    # ── Phase D: Model Checker ───────────────────────────────────────────
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  Phase D: Finite-Trace Reachability Model Checker           ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    checker = ModelChecker()
    lts_by_name = {l.name: l for l in lts_list}

    phase_d_results: list[dict] = []

    for cid, rep_name in cluster_result.representatives.items():
        rep_lts = lts_by_name[rep_name]
        print(f"\n  Checking representative: {rep_name}")

        # Property 1: Loop-bound safety
        loop_monitor = PropertyMonitor.from_loop_bound_check()
        verdict_loop = checker.check(rep_lts, loop_monitor)
        icon = "✅" if verdict_loop.result == "PASS" else "❌"
        print(f"    {icon} Loop-bound safety: {verdict_loop.result}")
        if verdict_loop.loop_bound_violations:
            print(f"       Trap states: {verdict_loop.loop_bound_violations}")
        print(f"       {verdict_loop.message}")

        phase_d_results.append({
            "representative": rep_name,
            "cluster_id": cid,
            "loop_bound_check": verdict_loop.result,
            "loop_bound_violations": verdict_loop.loop_bound_violations,
            "states_explored": verdict_loop.states_explored,
        })

        # Property 2: Check for reachability of any known forbidden labels
        for forbidden in ["error", "abort", "panic"]:
            if forbidden in rep_lts.atomic_propositions:
                mon = PropertyMonitor.from_reachability(forbidden)
                v = checker.check(rep_lts, mon)
                icon_f = "✅" if v.result == "PASS" else "❌"
                print(f"    {icon_f} Reachability({forbidden}): {v.result}")

    summary["phases"]["D"] = {
        "status": "OK",
        "checks": phase_d_results,
    }

    elapsed = time.perf_counter() - t0
    summary["elapsed_seconds"] = round(elapsed, 4)
    summary["overall"] = "COMPLETE"

    print(f"\n{'─' * 62}")
    print(f"  Pipeline completed in {elapsed:.3f}s")
    print(f"{'─' * 62}\n")

    return summary


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point."""
    print("═" * 62)
    print("  VibeCheck — Module 03: Equivalence Checking Engine")
    print("  Pure Python 4-Phase Pipeline")
    print("═" * 62)

    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if not path.exists():
            print(f"❌ File not found: {path}")
            sys.exit(1)
        wir_json = json.loads(path.read_text())
        print(f"  Input: {path}")
    else:
        wir_json = DEMO_WIR
        print("  Input: built-in demo WIR")

    summary = run_pipeline(wir_json)

    # Dump summary
    print("\n[Pipeline Summary JSON]")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()