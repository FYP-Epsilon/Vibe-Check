# Phase 1: Core Module 02 Hardening

> **Phase**: 1 of 6  
> **Scope**: Bug fixes, test coverage improvements, and validation threshold calibration  
> **Prerequisite**: Existing `ast_extractor.py`, `z3_sym_engine.py`, `dynamic_tracer.py`, `main.py`  
> **Estimated Effort**: 2–3 days  
> **Status**: Pending

---

## 1. Objectives

1. **Eliminate known bugs** in the Z3 concolic engine that silently corrupt constraint solving
2. **Increase V1 test coverage** from default 20 runs to 50–100 runs with dynamic budget adjustment
3. **Validate all confidence gating thresholds** (0.50, 0.75, 0.80) against the current codebase
4. **Ensure end-to-end pipeline integrity** across all Python 3.10+ constructs before adding new features

---

## 2. Bug Inventory

### 2.1 P0 — Z3 Solver Double-Reset Bug

**Location**: `z3_sym_engine.py`, `BoundedConcolicEngine._concolic_iteration()` (~lines 4360–4397)

**Current Code (Buggy)**:
```python
# Line ~4360
solver.reset()                    # ← BUG #1: Loses all accumulated constraints
solver.add(path_condition)        # Re-added after reset

# ... constraint solving ...

# Line ~4364
for seen_condition in self.seen_path_conditions:
    solver.add(Not(seen_condition))  # "Not seen before" constraints

# ... solve, extract model ...

# Line ~4397
solver.reset()                    # ← BUG #2: Reset again before next iteration
```

**Problem**: `solver.reset()` on line 4360 clears the solver state *before* `path_condition` is re-added. On the first iteration, the solver is empty → `path_condition` is added → solving works. On subsequent iterations, the reset on line 4397 from the *previous* iteration already cleared the solver, then line 4360 resets again (redundant but harmless), then path constraints are added fresh. The "not seen before" constraints (4364) are added to a solver that starts empty each iteration — this actually *prevents* constraint accumulation but also means:

1. **No learned lemmas survive** between iterations (the solver forgets everything)
2. **No incremental solving benefit** — each call to `check()` starts from scratch
3. **Potential race**: If `seen_path_conditions` grows large, adding `Not(seen)` for each creates a massive formula that degrades performance

**Fix**: Use **fresh `Solver()` instances per iteration** (cleaner semantics) or `push()`/`pop()` (preserves learned structure):

```python
# Option A: Fresh solver per iteration (RECOMMENDED — simpler, no state leakage)
for iteration in range(k_bound):
    solver = Solver()  # Fresh solver
    solver.add(path_condition)
    for seen in self.seen_path_conditions:
        solver.add(Not(seen))
    
    if solver.check() == sat:
        model = solver.model()
        # ... extract inputs, concrete execution ...
    
    self.seen_path_conditions.append(path_condition)

# Option B: push/pop (preserves learned lemmas, slight performance gain)
for iteration in range(k_bound):
    solver.push()
    for seen in self.seen_path_conditions:
        solver.add(Not(seen))
    
    if solver.check() == sat:
        model = solver.model()
        # ... extract inputs ...
    
    solver.pop()  # Remove "not seen" constraints, keep learned structure
    self.seen_path_conditions.append(path_condition)
```

**Validation**: After fix, verify that:
- Iteration 2+ explores paths *different* from iteration 1 (not solving empty constraint set)
- Solver statistics (`solver.statistics()`) show `sat` or `unknown`, never trivial `sat` on empty

### 2.2 P1 — QCE State Merging Never Invoked

**Location**: `z3_sym_engine.py`, `BoundedConcolicEngine.state_pool`

**Problem**: The `qce_predicts_savings()` and `merge_states()` methods exist but are **never called** during the concolic execution loop. The `state_pool` list accumulates symbolic states but merging never occurs. Path explosion is mitigated only by k-bounding, not by the advertised QCE (Quality Cost Estimation) state merging.

**Decision**: **Leave unimplemented for now.** Document as known limitation. QCE merging is a research-level optimization; k-bounding provides sufficient mitigation for workflows ≤100 LOC. If FLOW-BENCH evaluation reveals path explosion beyond k=5, revisit.

**Action**: Add a `TODO` comment in code and document in this file:
```python
# TODO(Phase 1.P1): QCE state merging is implemented but not integrated.
# The state_pool accumulates states; merge_states() is never called.
# k-bounding alone provides sufficient mitigation for ≤100 LOC workflows.
# Revisit if evaluation shows path explosion beyond k=5.
```

### 2.3 P1 — Container Type Forces V1 Fallback

**Location**: `z3_sym_engine.py`, `BoundedConcolicEngine._concolic_iteration()`

**Problem**: When parameters have `list` or `dict` type annotations, the symbolic engine triggers immediate V1 fallback with message: *"Container types require dynamic validation"*. This is by design but means ~30% of FLOW-BENCH workflows (those with `for x in collection:` loops over retrieved data) skip V2 entirely.

**Mitigation** (Phase 1 — minimal fix): 
- Treat loop iterators as **uninterpreted scalars** for guard analysis
- Only model the *number of iterations* (k-bounded) not the container contents
- This preserves V2's ability to verify guards inside loops without full array theory

```python
# In Z3VariableRegistry._infer_sort()
if annotation == list:
    # NEW: Return IntSort representing loop bound, not full ArraySort
    return IntSort(), {"loop_bound": True, "container_type": "list"}
```

### 2.4 P2 — Default Test Runs Below Target

**Location**: `dynamic_tracer.py`, `RandomizedDifferentialTester.__init__()`

**Current**: `n_runs=20` (hardcoded default)
**Target**: `n_runs=50` with dynamic adjustment based on AST complexity

**Implementation**:
```python
def _adaptive_test_runs(self, ast_node_count: int) -> int:
    """Dynamically adjust test runs based on code complexity."""
    base = int(os.environ.get("V1_RUNS", 50))
    # More nodes → fewer runs (timeout protection)
    if ast_node_count > 200:
        return max(15, base // 3)
    elif ast_node_count > 100:
        return max(25, base // 2)
    elif ast_node_count > 50:
        return max(35, base * 2 // 3)
    return base
```

---

## 3. Confidence Threshold Validation

The `V3Certificate._emit_certificate()` and `V2Certificate._emit_certificate()` methods contain hardcoded gating thresholds. These need empirical validation during Phase 5, but Phase 1 must ensure they are **documented, configurable, and consistently applied**.

### 3.1 Current Gating Logic

```python
# V3 structural certificate
def _emit_certificate(self) -> dict:
    score = (node_coverage + edge_coverage + guard_success) / 3.0
    
    # Hardcoded gates
    if branch_diversity < 0.5:
        score = min(score, 0.75)  # Cap if low branch diversity
    if branches_explored < 2:
        score = min(score, 0.80)  # Cap if <2 branches
    
    return {"score": score, "passed": score >= 0.95}
```

### 3.2 Required Changes

1. **Extract thresholds to configuration**:
```python
@dataclass
class ValidationConfig:
    branch_diversity_cap_threshold: float = 0.50  # Gate fires below this
    branch_diversity_cap_value: float = 0.75      # Cap score to this
    min_branches_cap_threshold: int = 2           # Gate fires below this
    min_branches_cap_value: float = 0.80          # Cap score to this
    certification_threshold: float = 0.95         # Final pass/fail
```

2. **Add branch diversity metric calculation** (currently referenced but not defined):
```python
def _calculate_branch_diversity(self, traces: list) -> float:
    """Shannon entropy of branch outcome distribution."""
    outcomes = collections.Counter()
    for trace in traces:
        for event in trace:
            if event["type"] == "branch":
                outcomes[event["taken"]] += 1
    
    total = sum(outcomes.values())
    if total == 0:
        return 0.0
    
    entropy = -sum(
        (count / total) * math.log2(count / total)
        for count in outcomes.values()
    )
    # Normalize: max entropy for binary branches is 1.0
    return min(entropy, 1.0)
```

---

## 4. Test Validation Checklist

Run the following tests and confirm all pass before proceeding to Phase 2:

| Test Suite | File | Expected Result | Actual Result |
|-----------|------|-----------------|---------------|
| Basic block extraction | `test_ast_extractor.py::test_basic_block` | PASS | ☐ |
| Python 3.10+ constructs | `test_ast_extractor.py::test_py310_constructs` | PASS | ☐ |
| Dominator tree correctness | `test_ast_extractor.py::test_dominator_tree` | PASS | ☐ |
| Guard CNF flattening | `test_ast_extractor.py::test_guard_cnf` | PASS | ☐ |
| End-to-end pipeline | `test_ast_extractor.py::test_end_to_end` | PASS | ☐ |
| Z3 solver produces models | `test_z3_engine.py::test_solver_produces_model` | PASS | ☐ |
| Iteration 2+ explores new paths | `test_z3_engine.py::test_path_diversity` | PASS (NEW) | ☐ |
| Container type fallback | `test_z3_engine.py::test_container_fallback` | PASS | ☐ |
| Differential testing detects mismatch | `test_tracer.py::test_mismatch_detection` | PASS | ☐ |
| Randomized tester entropy scoring | `test_tracer.py::test_entropy_coverage` | PASS | ☐ |
| Combined certificate calculation | `test_certificate.py::test_combined_formula` | PASS | ☐ |
| 0.95 abort threshold triggers | `test_certificate.py::test_abort_threshold` | PASS | ☐ |

---

## 5. Deliverables

1. **Fixed `z3_sym_engine.py`** — Solver reset bug resolved (Option A or B)
2. **Updated `dynamic_tracer.py`** — Adaptive test run calculation integrated
3. **New `config.py`** — `ValidationConfig` dataclass with all thresholds
4. **Updated test suite** — `test_path_diversity` added; all 12 tests passing
5. **Phase 1 Sign-off** — This document updated with checkmarks

---

## 6. Known Limitations (Documented, Not Fixed)

| Limitation | Impact | Resolution Plan |
|-----------|--------|-----------------|
| QCE state merging not invoked | Path explosion for deep loops (>k=5) | Revisit if Phase 5 evaluation shows issue |
| Container types use V1 fallback only | ~30% of workflows skip V2 | Minimal fix in Phase 1; full array theory deferred |
| Reference interpreter `eval()` restricted | Workflow code calling stdlib helpers may fail | Whitelist expansion on demand |

---

*Next: Phase 2 — AI Refinement Integration (`06_ai_refinement.md`)*
