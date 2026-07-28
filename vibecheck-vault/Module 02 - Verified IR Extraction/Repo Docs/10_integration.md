> [!info] Imported from repo docs
> Source: `docs/module02/10_integration.md` @ main `7089711` (2026-07-28). `docs/` was removed from the repo (develop @ `05fae60`, 2026-07-28) after this import — **this vault copy is now the surviving snapshot** (git history retains the originals).

# Phase 6: Integration & Documentation

> **Historical document** (written during Module 02's original 6-phase planning, predating the implementation sessions): describes the design/plan as of that point, including a `POST /verify` request/response shape (`workflow_code`/`specification` fields) that was never adopted — the actual endpoint uses `source_code`/`CodePayload`. Superseded by `docs/module02/12_wir_and_certificate_contract.md`, the current, source-generated Module 03 API contract. Kept as the project's finding trail.

> **Phase**: 6 of 6  
> **Scope**: Module 03 API contract, thesis documentation, final integration checklist  
> **Prerequisite**: All Phases 1–5 complete  
> **Estimated Effort**: 1 day  
> **Status**: Pending

---

## 1. Module 03 API Contract

Module 02 must expose a stable, documented API for Module 03 (Bisimulation Checker) to consume. This section defines the contract.

### 1.1 Endpoint: `POST /verify` (Single Implementation)

**Maintained unchanged from existing implementation.** This is the core primitive.

**Request**:
```json
{
  "workflow_code": "def handle_incident() -> str:\n    incident = ServiceNow_incident__4_0_0__retrievewithwhere_incident()\n    if incident.impact == 'high':\n        issue = Jira_Issue__2_0_0__create_Issue()\n        message = Slack_message__3_0_0__create_message()\n        return 'high_impact'\n    else:\n        issue = GitHub_Issue__3_0_0__create_Issue()\n        return 'low_impact'",
  "specification": "Optional: BPMN XML or natural language"
}
```

**Response**:
```json
{
  "wir": {
    "entry": "node_0",
    "nodes": [
      {
        "id": "node_0",
        "type": "entry",
        "function": "handle_incident",
        "line": 1
      },
      {
        "id": "node_1",
        "type": "block",
        "statements": ["incident = ServiceNow_incident__4_0_0__retrievewithwhere_incident()"],
        "line": 2
      },
      {
        "id": "node_2",
        "type": "gateway",
        "guard_cnf": [{"op": "Eq", "left": "incident.impact", "right": "'high'"}],
        "line": 3
      },
      {
        "id": "node_3",
        "type": "block",
        "statements": ["issue = Jira_Issue__2_0_0__create_Issue()", "message = Slack_message__3_0_0__create_message()"],
        "line": 4
      },
      {
        "id": "node_4",
        "type": "block",
        "statements": ["return 'high_impact'"],
        "line": 6
      },
      {
        "id": "node_5",
        "type": "block",
        "statements": ["issue = GitHub_Issue__3_0_0__create_Issue()"],
        "line": 8
      },
      {
        "id": "node_6",
        "type": "block",
        "statements": ["return 'low_impact'"],
        "line": 9
      },
      {
        "id": "node_7",
        "type": "exit",
        "line": 9
      }
    ],
    "edges": [
      {"source": "node_0", "target": "node_1"},
      {"source": "node_1", "target": "node_2"},
      {"source": "node_2", "target": "node_3", "guard": true},
      {"source": "node_3", "target": "node_4"},
      {"source": "node_4", "target": "node_7"},
      {"source": "node_2", "target": "node_5", "guard": false},
      {"source": "node_5", "target": "node_6"},
      {"source": "node_6", "target": "node_7"}
    ],
    "control_variables": ["incident.impact"],
    "data_variables": ["incident", "issue", "message"]
  },
  "certificate": {
    "v1": {
      "score": 0.92,
      "tests_run": 50,
      "mismatches": 0,
      "input_entropy": 3.42
    },
    "v2": {
      "score": 0.85,
      "paths_explored": 12,
      "solver_queries": 87,
      "solver_time": 2.3,
      "loop_depth_reached": 2
    },
    "v3": {
      "score": 0.98,
      "nodes": 8,
      "edges": 10,
      "guards_cnf": 4,
      "branch_coverage": 1.0,
      "dominator_verified": true
    },
    "combined": 0.9997,
    "passed": true
  },
  "ai_refinement": {
    "counterexample_explanation": null,
    "narrative": "This workflow passed all three validation modes. V3 structural validation achieved a score of 0.98 with full branch coverage. V2 symbolic execution explored 12 paths in 2.3 seconds. V1 dynamic testing ran 50 inputs with zero mismatches. The combined certificate of 0.9997 significantly exceeds the 0.95 threshold.",
    "llm_used": true
  },
  "metadata": {
    "verification_time_ms": 4520,
    "module_version": "2.1.0",
    "timestamp": "2026-05-17T12:00:00Z"
  }
}
```

### 1.2 Endpoint: `POST /verify-batch` (Multi-Implementation)

**New endpoint for Module 03 consumption.** Accepts a specification, generates N variants, validates each.

**Request**:
```json
{
  "specification": "Retrieve all Jira issues. For each issue with urgent priority, create an Asana task and send a Slack notification. For low priority, just send a Slack message.",
  "n_variants": 5,
  "adapter": "self_consistency"
}
```

**Response**:
```json
{
  "implementations": [
    {
      "variant_id": 0,
      "source_code": "def route_issues(context: dict) -> str:\n    ...",
      "wir": { "entry": "node_0", "nodes": [...], "edges": [...] },
      "certificate": {
        "v1": { "score": 0.94, "tests_run": 25, "mismatches": 1 },
        "v2": { "score": 0.82, "paths_explored": 8, "solver_time": 1.8 },
        "v3": { "score": 0.97, "nodes": 12, "edges": 15, "guards_cnf": 6 },
        "combined": 0.9989,
        "passed": true
      },
      "passed": true
    },
    {
      "variant_id": 1,
      "source_code": "def handle_issues(ctx: dict) -> str:\n    ...",
      "wir": { "entry": "node_0", "nodes": [...], "edges": [...] },
      "certificate": {
        "v1": { "score": 0.96, "tests_run": 25, "mismatches": 0 },
        "v2": { "score": 0.88, "paths_explored": 10, "solver_time": 2.1 },
        "v3": { "score": 0.99, "nodes": 10, "edges": 12, "guards_cnf": 5 },
        "combined": 0.9999,
        "passed": true
      },
      "passed": true
    },
    {
      "variant_id": 2,
      "source_code": "def process_tickets(tickets: list) -> str:\n    ...",
      "wir": { "entry": "node_0", "nodes": [...], "edges": [...] },
      "certificate": {
        "v1": { "score": 0.45, "tests_run": 25, "mismatches": 12 },
        "v2": { "score": 0.30, "paths_explored": 3, "solver_time": 0.5 },
        "v3": { "score": 0.62, "nodes": 6, "edges": 8, "guards_cnf": 2 },
        "combined": 0.7135,
        "passed": false
      },
      "passed": false,
      "ai_refinement": {
        "counterexample_explanation": "The implementation incorrectly uses the ticket list parameter directly instead of retrieving issues from Jira, causing the V1 trace to diverge at the first API call."
      }
    }
  ],
  "summary": {
    "n_requested": 5,
    "n_generated": 5,
    "n_passed": 4,
    "pass_rate": 0.80,
    "consensus_variant_id": 1,
    "consensus_cluster_size": 4,
    "wall_time_seconds": 45.2,
    "budget_per_variant": { "z3_queries": 100, "test_runs": 25, "timeout": 60 }
  },
  "metadata": {
    "module_version": "2.1.0",
    "timestamp": "2026-05-17T12:00:00Z"
  }
}
```

### 1.3 Endpoint: `GET /health`

**For monitoring and dependency checks.**

**Response**:
```json
{
  "status": "healthy",
  "version": "2.1.0",
  "components": {
    "ast_extractor": "ok",
    "z3_solver": "ok",
    "dynamic_tracer": "ok",
    "ai_refinement": "ok",
    "generation_adapter": "ok"
  },
  "timestamp": "2026-05-17T12:00:00Z"
}
```

---

## 2. Error Handling Contract

All endpoints return structured error responses:

### Validation Error (4xx)

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Python code contains syntax errors",
    "details": {
      "line": 5,
      "column": 12,
      "suggestion": "Check indentation of the else clause"
    }
  }
}
```

### Verification Failure (200 with passed=false)

```json
{
  "wir": null,
  "certificate": {
    "v1": { "score": 0.30, "tests_run": 50, "mismatches": 15 },
    "v2": { "score": 0.20, "paths_explored": 2, "solver_time": 0.3 },
    "v3": { "score": 0.55, "nodes": 3, "edges": 4, "guards_cnf": 0 },
    "combined": 0.472,
    "passed": false
  },
  "ai_refinement": {
    "counterexample_explanation": "V1 detected 15 trace mismatches. The code appears to be missing conditional branches that the WIR expects.",
    "narrative": "Verification FAILED. Combined score 0.472 is below the 0.95 threshold. V3 structural extraction found only 3 nodes (expected 8+), suggesting the code may not be a valid workflow function."
  },
  "metadata": { "verification_time_ms": 1200 }
}
```

### System Error (5xx)

```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "Z3 solver encountered unexpected SMT error",
    "details": {
      "component": "z3_sym_engine",
      "retryable": true
    }
  }
}
```

---

## 3. Module 03 Consumption Guide

Module 03 (Bisimulation Checker) should consume Module 02 outputs as follows:

### 3.1 Single-Implementation Mode

```python
import httpx

async def verify_and_lift(module02_endpoint: str, workflow_code: str, bpmn_spec: str):
    """
    Module 03 calls Module 02, then performs bisimulation checking.
    """
    # Step 1: Get verified WIR from Module 02
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{module02_endpoint}/verify",
            json={"workflow_code": workflow_code}
        )
        result = resp.json()
    
    # Step 2: Check if verification passed
    if not result["certificate"]["passed"]:
        # Option A: Reject immediately
        return {"status": "rejected", "reason": "Module 02 verification failed"}
        
        # Option B: Use AI explanation for repair guidance
        explanation = result.get("ai_refinement", {}).get("counterexample_explanation")
        return {"status": "needs_repair", "guidance": explanation}
    
    # Step 3: Lift WIR to automaton for bisimulation checking
    wir = result["wir"]
    automaton = lift_wir_to_automaton(wir)
    
    # Step 4: Parse BPMN spec to automaton
    bpmn_automaton = parse_bpmn_to_automaton(bpmn_spec)
    
    # Step 5: Bisimulation check
    equivalent, witness = check_bisimulation(automaton, bpmn_automaton)
    
    return {
        "status": "verified" if equivalent else "divergent",
        "witness": witness,
        "module02_certificate": result["certificate"]
    }
```

### 3.2 Multi-Implementation Mode

```python
async def verify_batch_and_cluster(module02_endpoint: str, spec: str, n: int = 5):
    """
    Module 03 calls Module 02 in batch mode, then clusters by equivalence.
    """
    # Step 1: Get N validated WIRs
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{module02_endpoint}/verify-batch",
            json={"specification": spec, "n_variants": n}
        )
        batch = resp.json()
    
    # Step 2: Filter passed implementations
    passed = [impl for impl in batch["implementations"] if impl["passed"]]
    
    if len(passed) == 0:
        return {"status": "all_failed", "implementations": batch["implementations"]}
    
    # Step 3: Cluster by bisimulation equivalence
    clusters = []
    for impl in passed:
        automaton = lift_wir_to_automaton(impl["wir"])
        
        # Check if equivalent to existing cluster
        assigned = False
        for cluster in clusters:
            equiv, _ = check_bisimulation(automaton, cluster["representative"])
            if equiv:
                cluster["members"].append(impl["variant_id"])
                assigned = True
                break
        
        if not assigned:
            clusters.append({
                "representative": automaton,
                "members": [impl["variant_id"]]
            })
    
    # Step 4: Select consensus (largest cluster)
    consensus = max(clusters, key=lambda c: len(c["members"]))
    
    return {
        "status": "clustered",
        "n_clusters": len(clusters),
        "cluster_sizes": [len(c["members"]) for c in clusters],
        "consensus_cluster": consensus["members"],
        "selected_variant": consensus["members"][0],
        "implementations": batch["implementations"]
    }
```

---

## 4. Thesis Documentation

### 4.1 Chapter Structure for Module 02

```
Chapter X: Verified Translation Validation (Module 02)

X.1 Introduction
    - Motivation: Why verify the verifier?
    - Research Question 2 formulation
    - Overview of three-layer architecture

X.2 Background
    - Control-flow graphs and dominator analysis
    - Concolic execution (Godefroid et al., Cadar et al.)
    - Differential testing and stuttering equivalence
    - Multi-modal confidence composition

X.3 Architecture
    - V3: Structural AST extraction (Figure: pipeline diagram)
    - V2: Symbolic refinement with Z3 (Figure: concolic loop)
    - V1: Dynamic differential testing (Figure: trace comparison)
    - Certificate composition (Figure: independent modes)

X.4 AI Refinement (Phase 2)
    - Design principle: LLM as diagnostic aid
    - Counterexample explanation
    - Certificate narrative generation
    - Guard simplification suggestions

X.5 Multi-Implementation Generation (Phase 3)
    - Self-consistency sampling theory
    - Adapter pattern architecture
    - Adaptive budget allocation

X.6 Evaluation (Phases 4–5)
    - 4-layer dataset generation methodology
    - Experiment E1: Seeded bug detection (Table: per-operator results)
    - Experiment E2: Structural accuracy (Table: match rates)
    - Experiment E3: Confidence calibration (Figure: score distribution)
    - Metric target achievement summary (Table: all targets)

X.7 Results
    - Consolidated metrics table
    - Comparison with baseline (no validation)
    - Ablation study: V1-only, V2-only, V3-only vs combined

X.8 Limitations and Future Work
    - QCE state merging not fully integrated
    - Container type symbolic reasoning
    - Scaling to >100 LOC workflows

X.9 Conclusion
```

### 4.2 Required Tables and Figures

| Table/Figure | Content | Source |
|-------------|---------|--------|
| Table 1 | Three-layer validation comparison (modes, techniques, independence) | Phase 1 docs |
| Table 2 | Mutation detection results (per-operator breakdown) | E1 results JSON |
| Table 3 | Structural accuracy (node/edge/decision match rates) | E2 results JSON |
| Table 4 | Metric target achievement (all 9 metrics, targets, actuals) | Consolidated report |
| Table 5 | Ablation study (V1-only, V2-only, V3-only, combined) | E1 with mode masking |
| Figure 1 | Three-layer architecture diagram | `docs/diagrams/` |
| Figure 2 | Concolic execution loop (Z3 integration) | `docs/diagrams/` |
| Figure 3 | Confidence score distribution (correct vs incorrect) | E3 results |
| Figure 4 | Detection rate vs mutation operator | E1 results |

### 4.3 LaTeX Table Template

```latex
\begin{table}[h]
\centering
\caption{Module 02 Metric Achievement Summary}
\label{tab:module02_metrics}
\begin{tabular}{llrr}
\toprule
\textbf{Metric} & \textbf{Symbol} & \textbf{Target} & \textbf{Achieved} \\
\midrule
Trace coverage & $\tau_{cov}$ & $\geq 0.95$ & \{TODO: fill\} \\
Branch coverage & $\beta_{cov}$ & $\geq 0.80$ & \{TODO: fill\} \\
Mismatch rate & $\mu$ & $\leq 0.01$ & \{TODO: fill\} \\
Refinement success & $\rho$ & $\geq 0.70$ & \{TODO: fill\} \\
Mutation detection & $\delta$ & $\geq 0.95$ & \{TODO: fill\} \\
False positive rate & $\varphi$ & $\leq 0.05$ & \{TODO: fill\} \\
Validation time & $t_{val}$ & $< 300$s & \{TODO: fill\} \\
Combined-pass rate & $\pi_{pass}$ & $\geq 0.85$ & \{TODO: fill\} \\
Structural accuracy & $\alpha_{struct}$ & $\geq 0.98$ & \{TODO: fill\} \\
\bottomrule
\end{tabular}
\end{table}
```

---

## 5. Final Integration Checklist

Before declaring Module 02 complete, verify all items:

### 5.1 Code Checklist

- [ ] All 6 phase documents created and reviewed
- [ ] `docs/module02/05_core_hardening.md` — bugs fixed, tests passing
- [ ] `docs/module02/06_ai_refinement.md` — OpenAI client integrated, 3 tasks working
- [ ] `docs/module02/07_multi_impl.md` — adapter pattern, `/verify-batch` endpoint live
- [ ] `docs/module02/08_eval_data.md` — all 4 datasets generated and validated
- [ ] `docs/module02/09_experiments.md` — E1, E2, E3 run, results documented
- [ ] `docs/module02/10_integration.md` — API contract finalized
- [ ] `docs/module02/00_overview.md` — updated with final architecture

### 5.2 API Checklist

- [ ] `POST /verify` — single implementation, backward compatible
- [ ] `POST /verify-batch` — multi-implementation, returns N WIRs + cluster summary
- [ ] `GET /health` — component status, used by Module 03 for dependency check
- [ ] Error responses follow structured format (4xx, 5xx)
- [ ] API response times < 5s for 100 LOC workflows

### 5.3 Evaluation Checklist

- [ ] 50 golden workflows generated (Layer 1)
- [ ] 100 augmented variants generated (Layer 2)
- [ ] 500 seeded mutants generated (Layer 3)
- [ ] 10 adversarial cases defined (Layer 4)
- [ ] E1: Detection rate ≥ 95%, false positive ≤ 5%
- [ ] E2: Structural accuracy ≥ 98%
- [ ] E3: Threshold accuracy ≥ 90%
- [ ] All results saved to `eval_data/results/`

### 5.4 Documentation Checklist

- [ ] Thesis Chapter X outline finalized
- [ ] All required tables filled with actual numbers
- [ ] All required figures generated
- [ ] Supervisor sign-off obtained
- [ ] README updated with setup + run instructions

### 5.5 Budget Checklist

- [ ] OpenAI API usage tracked
- [ ] Total cost within $5 budget
- [ ] No API key committed to repository
- [ ] `.env.example` provided with required variables

---

## 6. Sign-off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Module 02 Developer | [Your Name] | ☐ | [Date] |
| Supervisor | [Supervisor Name] | ☐ | [Date] |
| Module 03 Lead | [M03 Name] | ☐ | [Date] |

---

*This completes the Module 02 documentation suite. All 6 phases documented, integrated, and ready for implementation.*
