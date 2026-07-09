# WIR & Certificate Contract — Module 02 → Module 03

> **Scope**: the actual interface Module 03 consumes from Module 02 today — generated from current source (`src/ast_extractor/`, `src/dynamic_tracer/composer.py`, `shared_schemas/wir_schema.json`), not from the original design docs.
> **Consumer**: Module 03 (equivalence engine). Treat field renames or removals here as a breaking change to Module 03's lifter.
> **Status**: current as of this docs-refresh session. Supersedes `docs/module02/10_integration.md`'s original API contract sketch.

## 1. `POST /verify` — request and response

**Request**: `{"source_code": "<python function source>"}`.

**Response** (flat object, `main.py`'s `_run_verification`):

| Key | Type | Meaning |
|---|---|---|
| `wir` | object | The WIR (§2 below) |
| `v3_coverage` | float | V3's node-coverage score |
| `v3_abort` | bool | See §3 |
| `v2_confidence`, `v1_confidence` | float | Per-layer confidence (telemetry) |
| `combined_confidence` | float | `1 - (1-v1)(1-v2)` — V3 is excluded (§3) |
| `passed` | bool | `combined_confidence >= 0.95 AND NOT v3_abort` |
| `message` | str | Human-readable status |
| `layers` | object | `{"v3"/"v2"/"v1": {"status": "OK"\|"ERROR"\|"SKIPPED", "reason": str\|null}}` — per-phase status; a fatal earlier failure marks later phases `SKIPPED` with the upstream reason |
| `v3_details`, `v2_details`, `v1_details` | object | Full per-layer certificates (§3) |

There is no `POST /verify-batch` and no `specification` input field — both remain planned, not implemented (see `docs/module02/00_overview.md` §4, §7).

## 2. WIR schema

Full JSON Schema (draft-07): `shared_schemas/wir_schema.json` — the authoritative, machine-checkable definition. Structure:

```json
{
  "entry_node": "node_id", "exit_node": "node_id",
  "nodes": [{
    "id": "node_id",
    "type": "entry|exit|block|gateway|loop|task|break|continue|return|except|finally|match",
    "ast_type": "If|While|For|Try|...", "line": 42, "code": ["stmt_text"],
    "successors": ["node_id"], "predecessors": ["node_id"],
    "guard": "cond_or_null", "exception_type": "Name_or_null",
    "control_vars": ["..."], "data_vars": ["..."]
  }],
  "edges": [{"source": "node_id", "target": "node_id", "guard": "...", "exception_type": "..."}],
  "unsupported_constructs": [],
  "dominators": {"node_id": "idom_node_id"},
  "dominance_frontier": {"node_id": ["node_id", "..."]},
  "guard_extraction": {"total": 1, "success": 1, "conditions": [{"node_id": "...", "guard": "...", "cnf": [[{"negated": false, "text": "...", "vars": ["..."]}]]}]},
  "control_variables": ["..."], "data_variables": ["..."],
  "certificate": { "...": "V3 certificate, see §3" },
  "functions": { "function_name": { "...": "nested WIR, same shape" } }
}
```

**Fact 1 for the M03 owner: no blank structural nodes.** A post-construction contraction pass (`contract_bookkeeping_nodes`, applied after F1) removes blank merge/exit bookkeeping nodes the extractor's visitors create during construction. Every node in the output WIR corresponds to real source code — Module 03's lifter does not need to filter or skip empty nodes.

**Fact 2 for the M03 owner: there is no `WIR-Core`/`WIR-Data`/`WIR-Proc`/`WIR-Type` layered structure.** `docs/module_summery/Module_03_Equivalence_Engine.md` describes consuming a WIR with these four named layers; they do not exist. The real WIR is the single flat structure above. The closest real equivalents:
- "WIR-Core" (control flow) ≈ `nodes` + `edges` + `entry_node`/`exit_node`.
- "WIR-Data" (data/control variable classification) ≈ each node's `control_vars`/`data_vars`, plus the top-level `control_variables`/`data_variables`.
- "WIR-Proc" (process/task semantics) — no discrete layer; task boundaries are `type: "task"` nodes inline in `nodes`.
- "WIR-Type" (type information) — no discrete layer in the WIR itself; Python type annotations are read directly from the AST by `Z3VariableRegistry` at V2 time, not persisted as a separate WIR structure. If Module 03 needs per-variable types, they are not currently exposed in the WIR JSON — this is a real gap, not a naming difference, and is worth raising if needed (see the companion cross-module drift issue).

## 3. Certificate semantics

**V3 is a gate, not a vote.** `v3_details["abort"]` (mirrored at the top level as `v3_abort`) is `True` when node coverage falls below 0.95 — extraction fidelity too low to trust anything built on top of this WIR. When `True`, `passed` is `False` regardless of V1/V2. V3's `node_coverage`/`edge_coverage`/`guard_success_rate` are diagnostic detail, not inputs to `combined_confidence`.

**`combined_confidence` is V1 and V2 only**: `1 - (1 - v1_confidence)(1 - v2_confidence)`. Certification threshold (self-mode, one program verified against its own re-derived WIR): `combined_confidence >= 0.95`. A **separate**, differential-mode operating point exists for verifying one program against a *different* program's WIR (mutant vs. base, or independent implementation vs. reference) — currently `tau = 0.10` (a run is flagged if `combined_confidence < tau`), selected via Youden's J on a held-out calibration split. Do not conflate the two thresholds; they apply to different verification modes.

**Comparison mode** (V1 only, does not affect V3/V2): `strict` (default) keeps branch-decision divergence as signal — correct when the two compared programs share source lineage (e.g. a mutant vs. its own base). `task_only` drops branch-decision events from the comparison entirely — correct when comparing independently-written implementations, where branch structure is legitimate style variation, not a correctness signal. See `docs/module02/11_multi_impl_corpus_contract.md` for the full rationale and measured trade-off.

## 4. Suggested EQI-policy translation (M02's suggestion — for the M03 owner to adopt or adapt)

`docs/module_summery/Module_03_Equivalence_Engine.md` describes a 3-tier Extraction Quality Indicator (EQI) policy gating Module 03's verification strictness (GREEN ≥0.90 standard checking, YELLOW 0.70–0.90 conservative abstraction, RED <0.70 refuse). **There is no `EQI` field** — it was never implemented on the Module 02 side. The two real fields that carry the information EQI was meant to summarize are `v3_abort` (a hard boolean gate on extraction fidelity) and `combined_confidence` (a continuous behavioral-confidence score). A suggested, non-binding translation:

| Original EQI tier | Suggested real-field equivalent |
|---|---|
| **RED** (<0.70, refuse automaton lifting) | `v3_abort == True` — extraction fidelity itself is untrustworthy; do not lift this WIR at all |
| **GREEN** (≥0.90, standard model checking) | `v3_abort == False AND combined_confidence >= 0.95` — the WIR passed full certification |
| **YELLOW** (0.70–0.90, conservative abstraction) | `v3_abort == False AND combined_confidence < 0.95` — extraction is structurally trustworthy, but behavioral confidence didn't reach certification; treat guards/branches this didn't confirm conservatively, same spirit as the original YELLOW policy |

This is Module 02's suggestion for how to adapt the existing EQI-gated design to the fields that actually exist, not a unilateral decision on Module 03's behalf — flagged for the module owner's review alongside the broader doc-drift issue (see the linked GitHub issue).

## 5. What Module 03 should NOT assume

- No `/verify-batch` endpoint — multi-implementation comparison is currently only available via the `eval/` evaluation harness, not a production API (§1).
- No `specification` field on the request — Module 01's output is not currently threaded through Module 02 in a single combined call.
- No per-variable type layer in the WIR (§2, Fact 2) beyond what `control_vars`/`data_vars` implies.
- `combined_confidence`'s 0.95 threshold is self-mode only; differential-mode comparisons use `tau = 0.10` against the same field name (§3) — check which mode produced a given certificate before comparing it to a threshold.
