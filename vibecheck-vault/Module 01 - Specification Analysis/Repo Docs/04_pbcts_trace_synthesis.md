> [!info] Imported from repo docs
> Source: `docs/module01/04_pbcts_trace_synthesis.md` @ main `7089711` (2026-07-28). `docs/` was removed from the repo (develop @ `05fae60`, 2026-07-28) after this import — **this vault copy is now the surviving snapshot** (git history retains the originals).

# PBCTS: Progression-Based Constructive Trace Synthesis — Implementation Plan

**Status:** Planned
**Depends On:** Phase 2/3 (LTLf Property Suite)
**New Files:** `src/ltlf_progression.py`, `src/trace_synthesizer.py`, `src/bidirectional_alignment.py`

---

## 1. Problem Statement

### What PBCTS Replaces

PBCTS **supersedes Phase 4 (Automata Lifting) and Phase 5 (Native Replay)** from the critical pipeline path. Both existing phases have fundamental limitations that PBCTS resolves:

| Existing Phase | Limitation | PBCTS Resolution |
|---|---|---|
| **Phase 4** (Automata Lifting) | Depends on SPOT (C++ library). Fails on Windows. Language inclusion check is trace-based but still uses graph-derived traces. | PBCTS is pure Python. No external libraries needed. |
| **Phase 5** (Native Replay) | Generates traces from the Semantic Graph and replays them on the same graph — **circular**. Precision was hardcoded to 1.0 (now fixed to escaping edges, but still model-vs-model). | PBCTS generates traces from the **LTLf formulas** and cross-compares against model traces — **non-circular**. |

### What Happens to Phase 4 and Phase 5

| Phase | Action | Rationale |
|---|---|---|
| **Phase 4** (`automata_lifter.py`) | **Removed from critical path.** Retained in codebase as an optional diagnostic tool. | SPOT compilation is unnecessary — Module 03 has its own SPOT in C++. Language inclusion is superseded by BDA. GED can remain as an optional structural sanity check. |
| **Phase 5** (`process_mining_alignment.py`) | **Removed from critical path.** Retained in codebase as a lightweight fallback only if PBCTS encounters an error. | Fully superseded by PBCTS + BDA. Every function (trace generation, replay, EAS) is done better by PBCTS. |

### New Pipeline Architecture

**Before (5-phase):**
```
Phase 1 (Extraction) → Phase 2 (LTLf Synthesis) → Phase 3 (Mutation/Red-Team)
    → Phase 4 (Automata Lifting / SPOT) → Phase 5 (Native Replay) → Output
```

**After (4-phase with PBCTS):**
```
Phase 1 (Extraction) → Phase 2 (LTLf Synthesis) → Phase 3 (Mutation/Red-Team)
    → PBCTS (Trace Synthesis + BDA + FRC) → Output
```

### The Research Gap
No existing lightweight method generates execution traces purely from LTLf formulas without heavyweight C++ automata libraries (SPOT, Mona, CUDD). PBCTS fills this gap using a pure Python algorithm that inverts LTLf formula progression — traditionally used only for runtime monitoring — into a constructive trace enumeration mechanism.

---

## 2. Architecture Overview

PBCTS is the **sole verification phase** after Phase 3. It replaces both Phase 4 and Phase 5:

```
Input:   LTLf Property Suite (from Phase 3) + Semantic Graph (from Phase 1)

Step A:  LTLf Suite → PBCTS Progression Engine → T_spec (Specification Traces)
Step B:  Semantic Graph → Graph Traversal (LTLfAuditor) → T_model (Model Traces)
Step C:  T_spec × T_model → Bidirectional Differential Alignment → EAS_BDA
Step D:  Adaptive bound selection via IDCD (Iterative Deepening with Convergence)
Step E:  SCov (Specification Coverage) measurement
Step F:  Formal Reliability Certificate (FRC) output

Output:  FRC certificate (replaces Phase 4 + Phase 5 certificates)
```

---

## 3. Implementation Milestones

### Milestone P5B.1: LTLf Progression Engine (`src/ltlf_progression.py`)

**Objective:** Implement the core LTLf formula progression function that advances a formula by one time step given a set of true propositions.

**Deliverables:**
* `progress(formula, proposition_set)` → returns the residual formula after one step.
* `simplify(formula)` → reduces the formula (e.g., `TRUE ∧ φ → φ`, `FALSE ∨ φ → φ`).
* `extract_obligations(formula)` → returns `(must_true, must_false, free)` proposition sets.
* `is_satisfied_at_end(formula)` → checks if the formula is satisfied under LTLf finite-trace semantics (important: `G(φ)` is trivially true at the end of a finite trace if no steps remain, `F(φ)` is false if φ was never seen).

**Progression Rules to Implement:**

| Formula | `progress(φ, P)` |
|---------|-------------------|
| Atomic `p` | `TRUE` if `p ∈ P`, `FALSE` if `p ∉ P` |
| `¬φ` | `¬progress(φ, P)` |
| `φ ∧ ψ` | `progress(φ, P) ∧ progress(ψ, P)` |
| `φ ∨ ψ` | `progress(φ, P) ∨ progress(ψ, P)` |
| `X(φ)` | `φ` (next obligation becomes current) |
| `F(φ)` | `progress(φ, P) ∨ F(φ)` |
| `G(φ)` | `progress(φ, P) ∧ G(φ)` |
| `φ U ψ` | `progress(ψ, P) ∨ (progress(φ, P) ∧ (φ U ψ))` |
| `φ W ψ` | `progress(ψ, P) ∨ (progress(φ, P) ∧ (φ W ψ))` |
| `φ → ψ` | Rewrite as `¬φ ∨ ψ`, then progress |

**Internal Representation:** Formulas should be represented as a recursive Python dataclass tree (not raw strings) for efficient manipulation:

```python
@dataclass
class LTLfFormula:
    op: str           # "atom", "not", "and", "or", "X", "F", "G", "U", "W", "TRUE", "FALSE"
    atom: str = None  # Only for op="atom"
    left: 'LTLfFormula' = None
    right: 'LTLfFormula' = None
```

**Parser:** A `parse(formula_string) → LTLfFormula` function that converts the existing string-based LTLf properties (e.g., `"!start(Payment) W done(Check_Stock)"`) into the internal tree representation. Must handle the operators used by `ltlf_synthesizer.py`: `!`, `G()`, `F()`, `X()`, `U`, `W`, `->`, `&`, `|`.

**Quality Gate:** Unit test each progression rule independently. Verify `progress("!start(B) W done(A)", {done(A)})` simplifies to `TRUE`, and `progress("!start(B) W done(A)", {start(B)})` simplifies to `FALSE`.

---

### Milestone P5B.2: Constructive Trace Synthesizer (`src/trace_synthesizer.py`)

**Objective:** Use the progression engine to enumerate all valid traces of length ≤ k that satisfy the entire LTLf property suite.

**Core Algorithm — `PBCTS(property_suite, bound_k)`:**

1. Collect all atomic propositions from the property suite (`AP`).
2. Conjoin all formulas into a single formula `Φ = φ₁ ∧ φ₂ ∧ ... ∧ φₙ`.
3. Call `ENUMERATE(Φ, AP, k, [], results)`.

**`ENUMERATE(φ_current, AP, steps_remaining, trace_so_far, results)`:**

1. If `simplify(φ_current) == TRUE` → add `trace_so_far` to `results`, return.
2. If `simplify(φ_current) == FALSE` → prune, return.
3. If `steps_remaining == 0` → check `is_satisfied_at_end(φ_current)`, add if satisfied, return.
4. Extract `(must_true, must_false, free)` from `φ_current`.
5. For each subset `F ⊆ free` (2^|free| combinations):
   - Construct `P = must_true ∪ F` (ensuring `must_false ∩ P = ∅`).
   - Compute `φ_next = simplify(progress(φ_current, P))`.
   - Recurse: `ENUMERATE(φ_next, AP, steps_remaining - 1, trace_so_far + [P], results)`.

**Optimizations:**
* **Obligation pruning** reduces branching from 2^|AP| to 2^|free| per step. For typical BPMN (|AP| ≈ 15, |free| ≈ 3), this is 8 vs 32768 — a 4000x speedup.
* **Memoization:** Cache `(φ_string, steps_remaining) → results` to avoid re-exploring identical sub-problems.
* **Trace cap:** Stop enumeration after collecting 200 traces (configurable). Sufficient for alignment scoring while preventing combinatorial explosion on highly branching specifications.

**Quality Gate:** For the simple BPMN `Start → Check_Stock → XOR → (Payment | Cancel) → End`, the synthesizer must produce exactly the two expected traces purely from the LTLf rules, without any knowledge of the Semantic Graph.

---

### Milestone P5B.3: Bidirectional Differential Alignment (`src/bidirectional_alignment.py`)

**Objective:** Cross-compare specification-derived traces (T_spec from PBCTS) against model-derived traces (T_model from the existing `LTLfAuditor`) to compute a non-circular alignment score.

**Trace Normalization:**
Before comparison, both trace sets must be normalized to a canonical form:
* Each trace step `Set[str]` → `frozenset` (hashable).
* Each trace → `tuple(frozenset, frozenset, ...)` (hashable).
* Both sets → `Set[tuple]` for O(1) membership testing.

**BDA Metrics:**

```python
T_agreed   = T_spec & T_model         # Traces present in BOTH sets
T_spec_only = T_spec - T_model         # Over-specification: LTLf allows, BPMN forbids
T_model_only = T_model - T_spec        # Under-specification: BPMN allows, LTLf misses

fitness_bda   = len(T_agreed) / len(T_model)  if T_model else 1.0
precision_bda = len(T_agreed) / len(T_spec)   if T_spec  else 1.0
recall_bda    = len(T_agreed) / len(T_model)  if T_model else 1.0

eas_bda = 2 * (precision_bda * recall_bda) / (precision_bda + recall_bda)
```

**Semantic Gap Report:**
For every trace in `T_spec_only` (over-specification), log the trace and identify which LTLf property permitted it. For every trace in `T_model_only` (under-specification), log the trace and identify which graph edge was missed by the LTLf suite.

**Quality Gate:** On the simple BPMN example, `T_spec_only` and `T_model_only` must both be empty, yielding `EAS_BDA = 1.0`.

---

### Milestone P5B.4: Specification Coverage Metric (SCov)

**Objective:** Track how thoroughly the synthesized traces exercise the obligation tree.

**Implementation:** During PBCTS enumeration, maintain counters:
* `nodes_visited`: Number of distinct obligation states explored.
* `nodes_total`: Total obligation states in the tree (including pruned branches).
* `branches_exercised`: Number of distinct valid proposition assignments taken.
* `branches_total`: Total valid proposition assignments possible.
* `depth_reached`: Maximum trace length generated.

```python
SCov_node   = nodes_visited / nodes_total
SCov_branch = branches_exercised / branches_total
SCov_depth  = depth_reached / bound_k

SCov = (0.4 * SCov_node + 0.4 * SCov_branch + 0.2 * SCov_depth)
```

**Quality Gate:** For the simple BPMN example with a small enough bound, SCov should be 1.0 (full exploration). For complex BPMNs where the trace cap is hit, SCov must be > 0.80.

---

### Milestone P5B.5: Iterative Deepening with Convergence Detection (IDCD)

**Objective:** Automatically determine the optimal trace bound k without manual configuration.

**Implementation:**

```python
def run_idcd(property_suite, semantic_graph, k_max=20, epsilon=0.001):
    eas_prev = 0.0
    eas_history = []

    for k in range(1, k_max + 1):
        t_spec  = pbcts(property_suite, bound_k=k)
        t_model = generate_graph_traces(semantic_graph, cutoff=k)
        eas_k   = compute_bda(t_spec, t_model)
        eas_history.append(eas_k)

        if abs(eas_k - eas_prev) < epsilon:
            return eas_k, k, 1.0 - epsilon, eas_history  # converged

        eas_prev = eas_k

    scov = compute_scov(k_max)
    return eas_k, k_max, scov, eas_history  # did not converge, report SCov as confidence
```

**Quality Gate:** For the simple BPMN, IDCD must converge within k ≤ 5. For complex BPMNs (20+ nodes), convergence within k ≤ 15.

---

### Milestone P5B.6: Formal Reliability Certificate (FRC)

**Objective:** Replace the Phase 4 + Phase 5 certificates with a single structured certificate.

**Certificate Schema:**
```python
{
    "certificate_version": "2.0",
    "method": "PBCTS_BDA_IDCD",

    "alignment_scores": {
        "EAS_BDA": float,
        "fitness_BDA": float,
        "precision_BDA": float,
        "recall_BDA": float
    },

    "specification_coverage": {
        "SCov": float,
        "SCov_node": float,
        "SCov_branch": float,
        "SCov_depth": float
    },

    "convergence": {
        "converged": bool,
        "k_converged": int,
        "epsilon": float,
        "eas_history": [float]
    },

    "differential_analysis": {
        "traces_spec_count": int,
        "traces_model_count": int,
        "traces_agreed": int,
        "traces_spec_only": int,
        "traces_model_only": int,
        "semantic_gaps": [{"type": str, "trace": str, "explanation": str}]
    },

    "reliability": {
        "confidence": float,
        "completeness_statement": str
    }
}
```

**Integration with `api.py`:** The `run_module_01_pipeline()` function should invoke the PBCTS pipeline **directly after Phase 3**, replacing the Phase 4 and Phase 5 calls. The FRC is emitted under a `"phase_4"` key to maintain backward compatibility with downstream consumers.

**Fallback:** If PBCTS encounters a fatal error (e.g., unparseable formula), fall back to the existing Phase 5A (`process_mining_alignment.py`) and emit a warning in the certificate.

---

## 4. File Structure (Post-Implementation)

```
module_01_spec/src/
├── __init__.py
├── api.py                          # Updated: PBCTS replaces Phase 4 + 5 calls
├── semantic_extractor.py           # Phase 1 (unchanged)
├── ltlf_synthesizer.py             # Phase 2 (unchanged)
├── formula_normalizer.py           # Shared utility (unchanged)
├── ltlf_eval.py                    # Shared utility (unchanged)
├── adversarial_generator.py        # Phase 3 (unchanged)
├── mutation_refiner.py             # Phase 3 (unchanged)
├── automata_lifter.py              # DEPRECATED — optional diagnostic only
├── process_mining_alignment.py     # DEPRECATED — fallback only
├── ltlf_progression.py             # NEW — P5B.1: Formula progression engine
├── trace_synthesizer.py            # NEW — P5B.2: PBCTS trace enumeration
└── bidirectional_alignment.py      # NEW — P5B.3+4+5+6: BDA, SCov, IDCD, FRC
```

---

## 5. Implementation Order & Dependencies

```
P5B.1 (Progression Engine)
  │
  ▼
P5B.2 (Trace Synthesizer) ──── depends on P5B.1
  │
  ▼
P5B.3 (BDA Comparator) ─────── depends on P5B.2 + existing LTLfAuditor
  │
  ▼
P5B.4 (SCov Metric) ────────── depends on P5B.2 internals
  │
  ▼
P5B.5 (IDCD Controller) ────── depends on P5B.2 + P5B.3
  │
  ▼
P5B.6 (FRC Certificate) ────── depends on all above
  │
  ▼
API Integration ─────────────── update api.py + main.py (remove Phase 4/5 from critical path)
```

---

## 6. Changes to `api.py` and `main.py`

### Current Pipeline Flow (to be replaced):
```python
Phase 1 → Phase 2 → Phase 3 → Phase 4 (automata_lifter) → Phase 5 (process_mining_alignment)
```

### New Pipeline Flow:
```python
Phase 1 → Phase 2 → Phase 3 → PBCTS (bidirectional_alignment.run_pbcts_pipeline())
```

### What to Remove from Critical Path:
* `automata_lifter.py` invocation in `api.py` lines 46-66 → replace with PBCTS call.
* `process_mining_alignment.py` invocation in `api.py` lines 69-89 → remove entirely.
* Phase 4/5 status logic in `api.py` lines 91-102 → replace with FRC status logic.

### What to Keep:
* `automata_lifter.py` file → kept in codebase, importable as optional diagnostic.
* `process_mining_alignment.py` file → kept in codebase, used as fallback in PBCTS error handler.

### Module 03 Handoff (`export_for_module_03`):
* `loop_bound_documented` currently comes from Phase 4's certificate. PBCTS should extract this value directly from the `P2_Quality_Limits` property suite (it's already available in the LTLf data).
* `ltlf_property_suite` → unchanged, comes from Phase 3.
* `semantic_graph` → unchanged, comes from Phase 1.

---

## 7. External Dependencies

**None.** This is the critical engineering advantage. The entire PBCTS pipeline uses:
* Python standard library only (`dataclasses`, `typing`, `copy`, `itertools`).
* Internal project modules (`ltlf_eval.py`, `formula_normalizer.py`, `mutation_refiner.py` for `LTLfAuditor`).
* No SPOT, no Z3, no pm4py, no networkx for the core PBCTS algorithm.

---

## 8. Risk Assessment

| Risk | Mitigation |
|------|------------|
| Combinatorial explosion on complex BPMN (many atomic propositions) | Obligation pruning reduces branching to 2^|free|. Trace cap at 200. Memoization. |
| LTLf parser fails on edge-case formula syntax | Build parser against the exact output format of `ltlf_synthesizer.py`. Test with all P0/P1/P2/P3 formula patterns. |
| IDCD does not converge within k_max | Return partial result with SCov as confidence. Fallback to Phase 5A score. |
| BDA produces empty T_spec (formulas too restrictive) | Log diagnostic. Fall back to Phase 5A score and flag the property suite for review. |
| Removing Phase 4 breaks Module 03 handoff | Verified: Module 03 receives LTLf strings, not HOA. `loop_bound_documented` extractable from P2 properties. No breaking change. |

---

## 9. Success Criteria

1. **Simple BPMN (3-5 nodes):** PBCTS generates the expected traces purely from LTLf. BDA yields `EAS = 1.0`. IDCD converges at k ≤ 5. SCov = 1.0.
2. **Medium BPMN (10-15 nodes):** PBCTS generates ≥ 10 diverse traces. BDA yields `EAS ≥ 0.90`. IDCD converges at k ≤ 10. SCov ≥ 0.85.
3. **Complex BPMN (20+ nodes):** PBCTS generates traces within the cap. BDA produces a meaningful semantic gap report. FRC certificate is structurally complete.
4. **Zero external dependencies:** The entire PBCTS runs on a fresh Python 3.10+ install with no `pip install` required beyond the existing project requirements.
5. **Backward compatibility:** `export_for_module_03()` produces an identical payload structure. Module 03 does not need any changes.

---

## 10. Strict Discrete LTLf Guarantee

**Architectural Constraint:** Module 01 is the Formal Specification Authority. It must remain mathematically absolute.
1. **No Tensors/Gradients:** The introduction of Vector Symbolic Architectures (VSA), embeddings, PyTorch/TensorFlow, or differentiable formal verification into Module 01 is **strictly prohibited**.
2. **Discrete ASTs:** The progression engine must parse LTLf strings into strict, discrete `LTLfFormula` dataclass ASTs.
3. **Delegation of Fuzzy Matching:** Any NLP-based similarity matching (e.g., mapping LLM code names to BPMN task names) is explicitly delegated to Module 03 (which uses Tier-3 Sentence-BERT). Module 01 must only produce and consume exact boolean strings.
4. **Mathematical Trace Generation:** Traces will be synthesized using Python `frozenset` boolean evaluation, never through probabilistic sampling or vector manipulation.
