"""
e2e_orchestrator.py -- chains the three live HTTP services (spec-engine,
extract-engine, equiv-engine) into one M01 -> M02 -> M03 conformance check.

This is the HTTP-service equivalent of demo/eval_e2e/harness.py's
in-process discover_gold_specs()/run_mutant(): same shape of data, but
driven entirely over the network against the real docker-compose
deployment, closing the gap tracked in the vault
(Home.md: "M04 has zero tests and no UI demo for /check").

tier_semantics below is NOT derived from any service response -- it is a
fixed policy dict, byte-identical to module_01_spec/src/api.py's own
export_for_module_03() (that function only exists on the M01 side, not
reachable over HTTP, so it is mirrored here rather than imported).
"""

from __future__ import annotations

import re
from typing import Any

import requests

TIER_SEMANTICS: dict[str, dict[str, Any]] = {
    "P0_Critical_Sentinels": {
        "role": "lifting_self_test",
        "conformance_check": False,
        "note": (
            "Unfalsifiable under any faithful lifting. Do not report as a "
            "passed/failed conformance verdict against generated code; use "
            "only to self-test the Module 03 lifter."
        ),
    },
    "P1_Structural_Control_Flow": {
        "role": "conformance_check",
        "conformance_check": True,
        "note": "Cross-task ordering/exclusivity properties, genuinely falsifiable against code.",
    },
    "P2_Quality_Limits": {
        "role": "conformance_check",
        "conformance_check": True,
        "note": "Quality/iteration-bound properties, genuinely falsifiable against code.",
    },
    "P4_Task_Coverage": {
        "role": "conformance_check",
        "conformance_check": True,
        "note": "Task omission checks, ensures every task specified actually occurs in the trace.",
    },
    "P3_Adversarial_Defenses": {
        "role": "adversarial_self_test",
        "conformance_check": False,
        "note": (
            "Killer properties synthesized from adversarially-generated "
            "deceptive traces (Phase 3's own red-teaming) -- validates the "
            "property suite's own robustness, not generated code. Also "
            "commonly needs the LTLf->LTL X-operator bridge Module 03's "
            "current ingestion does not yet implement."
        ),
    },
    "synthesized_mutant_killers": {
        "role": "audit_trail",
        "conformance_check": False,
        "note": (
            "Bookkeeping list of killer properties Phase 3's mutation "
            "self-healing synthesized during its own refinement loop -- "
            "each one is already duplicated into P1_Structural_Control_Flow "
            "when synthesized, so this tier is an audit trail, not an "
            "independent conformance check."
        ),
    },
}

_ATOM_RE = re.compile(r"(?:start|done)\(([^)]+)\)")


class E2EOrchestrationError(RuntimeError):
    """Raised with the failing stage name attached, so callers can show
    the user which of the three services broke the chain."""

    def __init__(self, stage: str, message: str):
        super().__init__(f"[{stage}] {message}")
        self.stage = stage


def _bpmn_task_names(semantic_graph: dict) -> list[str]:
    names: list[str] = []
    for state in semantic_graph["states"]:
        if state.get("node_type") in ("task", "userTask", "serviceTask"):
            for prop in state.get("atomic_propositions", []):
                m = _ATOM_RE.match(prop)
                if m:
                    names.append(m.group(1))
                    break
    seen: dict[str, None] = {}
    for n in names:
        seen.setdefault(n, None)
    return list(seen)


def run_e2e_check(
    bpmn_xml: str,
    source_code: str,
    *,
    spec_url: str = "http://spec-engine:8000",
    extract_url: str = "http://extract-engine:8000",
    equiv_url: str = "http://equiv-engine:8000",
    # spec-engine's /verify runs Module 01's Phase 3 mutation-based quality
    # gate, whose cost scales with diagram complexity, not just task count --
    # measured up to ~290s for a 6-task/2-gateway diagram (vs a few seconds
    # for the 3-4 task FLOW-BENCH specs). 60s silently misfires as a generic
    # "network error" on exactly these richer, legitimate cases -- not a
    # broken chain, just an under-sized client timeout.
    timeout: float = 600.0,
) -> dict[str, Any]:
    """
    Drives the real M01 -> M02 -> M03 HTTP chain for one (BPMN spec, source
    code) pair and returns M03's /check response, augmented with the
    intermediate artifacts (property suite, bpmn_tasks, wir) so a caller
    (e.g. a UI) can show its work instead of just a verdict.

    Raises E2EOrchestrationError, tagged with the stage name, on any
    non-2xx response or malformed intermediate artifact -- callers should
    not need to inspect requests.Response objects themselves.
    """
    spec_resp = requests.post(
        f"{spec_url}/verify", json={"bpmn_xml": bpmn_xml}, timeout=timeout
    )
    if spec_resp.status_code != 200:
        raise E2EOrchestrationError(
            "spec-engine", f"HTTP {spec_resp.status_code}: {spec_resp.text[:500]}"
        )
    spec_result = spec_resp.json()

    semantic_graph = spec_result["phase_1"]["semantic_graph"]
    ltlf_property_suite = spec_result["phase_3"]["refined_ltlf_property_suite"]
    bpmn_tasks = _bpmn_task_names(semantic_graph)

    extract_resp = requests.post(
        f"{extract_url}/verify", json={"source_code": source_code}, timeout=timeout
    )
    if extract_resp.status_code != 200:
        raise E2EOrchestrationError(
            "extract-engine", f"HTTP {extract_resp.status_code}: {extract_resp.text[:500]}"
        )
    extract_result = extract_resp.json()

    call_order_wir = extract_result.get("call_order_wir")
    if not call_order_wir:
        raise E2EOrchestrationError(
            "extract-engine",
            "response had no usable call_order_wir (v3 layer likely failed) -- "
            f"layers: {extract_result.get('layers')}",
        )

    check_resp = requests.post(
        f"{equiv_url}/check",
        json={
            "wir": call_order_wir,
            "bpmn_tasks": bpmn_tasks,
            "ltlf_property_suite": ltlf_property_suite,
            "tier_semantics": TIER_SEMANTICS,
        },
        timeout=timeout,
    )
    if check_resp.status_code != 200:
        raise E2EOrchestrationError(
            "equiv-engine", f"HTTP {check_resp.status_code}: {check_resp.text[:500]}"
        )

    return {
        "bpmn_tasks": bpmn_tasks,
        "ltlf_property_suite": ltlf_property_suite,
        "call_order_wir": call_order_wir,
        "check_result": check_resp.json(),
    }
