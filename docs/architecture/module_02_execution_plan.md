# Module 02: Verified IR Extraction — E2E Execution Plan & Deep Technical Reference

**Prepared for:** Fernando WKD (Group 18 — Epsilon), Module 02 Lead Developer, VibeCheck Framework
**Classification:** Technical Deep-Dive / Implementation Roadmap
**Target:** Python 3.10+, Linux/WSL Environment

---

## 1. The E2E Master Execution Plan (Step-by-Step)

The remainder of Module 02's workload is organized into three chronological phases, each delivering a production-grade validation mode (V3 → V2 → V1). The progression is deliberate: V3 (Static AST Extraction) provides the structural foundation upon which V2 (Symbolic Refinement) reasons, and V2's path-feasibility results determine where V1 (Dynamic Tracing) must statistically compensate. This ordering ensures that each phase's correctness certificate strengthens the overall confidence calculation.

### Phase 1: Hardening Static AST Extraction (V3) — Weeks 1–2

**Objective:** Transform the current AST parser into a hardened, CFG-aware structural extractor that emits a WIR with complete branch-condition metadata and syntactic correctness guarantees.

The Phase 1 architecture proceeds through five concrete milestones. **Milestone P1.1** expands the `ast.NodeVisitor` traversal to handle the full Python 3.10+ syntax surface that LLMs actually generate. Your current extractor targets `If`, `For`, `While`, and `Call` nodes. You must add explicit handlers for `ast.NamedExpr` (walrus operator `:=`, PEP 572), `ast.Match` (structural pattern matching, PEP 634), and `ast.TryStar` (exception groups, PEP 654). The walrus operator is particularly insidious because it introduces assignment expressions inside branch conditions — your CFG builder must treat `NamedExpr` as both a data-flow assignment and a control-flow predicate simultaneously. For pattern matching, map each `match_case` to a conditional block where the pattern is the guard and the case body is the branch. Extract the `ast.MatchValue` or `ast.MatchClass` pattern into a Z3-friendly equality constraint.

**Milestone P1.2** implements a dominator-tree analysis over the extracted CFG using NetworkX's `immediate_dominators`. This is non-negotiable for V3 validation: the dominator tree enables you to verify that every path from the entry node to a task node passes through required gateway checks. If a BPMN specification requires that "Task ApproveLoan" must always be preceded by "Gateway CreditCheckPassed," the dominator relationship between the corresponding CFG nodes provides a structural proof (or counterexample) of this ordering constraint. Use this to implement the fast syntactic pre-check that the report describes as V3's primary function.

**Milestone P1.3** hardens the guard-condition extraction pipeline. LLM-generated conditions are frequently compound expressions involving `and`, `or`, `not`, and method calls. Your extractor must flatten these into Conjunctive Normal Form (CNF) using De Morgan's laws, producing a list of atomic predicates that V2's Z3 engine can independently evaluate. For each atomic predicate, record the source AST node, the string representation (for diagnostics), and a typed variable inventory. Implement a `GuardExtractor` class that traverses `ast.BoolOp` nodes recursively, handling Python's short-circuit semantics by introducing explicit `ITE` (if-then-else) encodings where necessary.

**Milestone P1.4** implements the WIR-Data layer, distinguishing control variables (those appearing in branch conditions) from data variables (those only used in computations). This distinction is critical for V2's symbolic abstraction: control variables must be symbolized with full precision, while data variables can be abstracted to their type signatures or even concrete values. Perform a reaching-definitions analysis on the CFG to determine which variables are live at each branch point and classify them accordingly.

**Milestone P1.5** integrates the V3 certificate generator. After CFG extraction, emit a JSON certificate containing: node coverage (fraction of AST nodes mapped to WIR nodes), edge coverage (fraction of control-flow edges preserved), guard extraction success rate (fraction of branch conditions successfully decomposed into atomic predicates), and a list of unsupported constructs (if any). If node coverage falls below **0.95**, abort and flag the implementation for manual review — this is your first quality gate.

### Phase 2: Perfecting Symbolic Refinement with Z3 (V2) — Weeks 2–3

**Objective:** Resolve the dynamic variable injection problem and implement bounded concolic execution with path-explosion mitigation.

**Milestone P2.1** builds the **Z3 Variable Registry**, a Python class that bridges the dynamic typing of LLM-generated code to Z3's static sort system. This is the core architectural component that solves your biggest interim challenge. The registry maintains a mapping from Python variable names to Z3 constants, with automatic sort inference based on runtime value observation. When a variable is first encountered during concolic execution, inspect its concrete value using Python's `type()` builtin: map `int` → `z3.IntSort()`, `float` → `z3.RealSort()`, `bool` → `z3.BoolSort()`, `str` → `z3.StringSort()` (or `z3.IntSort()` if you encode strings as integer tokens). For `list` values, declare a `z3.Array('name', z3.IntSort(), infer_element_sort(value[0]))`. For `dict` values, use either nested `z3.Array` declarations or a flattened naming scheme (`dict_key_field` → `z3.Int('dict_key_field')`). For heterogeneous or `None` values, default to `z3.Const(name, z3.DeclareSort('PyObject'))` and refine the sort on first concrete assignment. The registry must handle variable reassignment: when a variable's type changes (e.g., `x = 1` then `x = "string"`), create a new Z3 constant with a versioned name (`x_0`, `x_1`) and record the type-transition constraint.

**Milestone P2.2** implements the **Concolic Execution Engine**. This engine maintains two parallel states: the **concrete state** (actual Python values, executed natively) and the **symbolic state** (Z3 expressions, tracked for variables classified as control-relevant). At each branch point, the engine records the path condition: the concrete execution takes one branch, while the symbolic state records the condition for that branch as a Z3 assertion. After the concrete execution completes, the engine queries the Z3 solver for alternative satisfiable branch conditions, generating new concrete inputs that would drive execution down unexplored paths. This is the classic concolic loop: concrete execution → path condition collection → solver query → new input generation → repeat.

**Milestone P2.3** implements **k-Bounded Loop Unrolling with State Merging**. For each loop encountered, unroll it a maximum of **k** iterations (start with **k = 3**, tune based on solver timeout). After k unrollings, merge the loop states: at the loop exit point, combine all states that differ only in loop-carried variables that are dead after the loop. Use the Query Count Estimation (QCE) heuristic to decide whether merging is profitable: merge if the total number of expected future solver queries with merged state is less than the sum of queries without merging. Specifically, merge when the differing variables are not used in subsequent branch conditions. This is your primary defense against path explosion.

**Milestone P2.4** implements **Incremental Confidence Accumulation**. After each concolic iteration, update a running confidence score: `confidence = (feasible_paths_verified / total_paths_explored) * (1 - timeout_rate) * (solver_success_rate)`. If confidence reaches **0.95**, emit the V2 certificate and proceed. If confidence stalls below **0.80** after a budget of solver queries (recommend 500 queries per function), trigger V1 (dynamic tracing) as a compensating modality.

### Phase 3: Implementing Dynamic Tracing & Differential Execution (V1) — Weeks 3–4

**Objective:** Build a low-overhead `sys.settrace` pipeline that captures execution observables and performs differential comparison between the LLM code and a WIR reference interpreter.

**Milestone P3.1** builds the **Observable Trace Capture** module. This is a `sys.settrace` callback function designed for minimal overhead. The function signature is `trace_observable(frame, event, arg)`, and it selectively captures only events relevant to the WIR abstraction: function calls matching task-entry patterns, function returns matching task-exit patterns, and line events at branch points (lines containing `if`, `while`, `for`). For each captured event, serialize a trace record containing: `(timestamp, event_type, function_name, line_number, observable_variables)`. The observable variables are filtered: only include variables identified as "control variables" by the V3 analysis, and only capture their types and equality classes (not full values), to reduce trace size. The trace function returns `None` (disabling tracing) for all library frames and non-target functions, ensuring that tracing overhead is proportional only to the target workflow code.

**Milestone P3.2** implements the **WIR Reference Interpreter**. This is a deterministic Python interpreter for the WIR JSON schema. Given a WIR and a set of concrete inputs, it executes the workflow logic step-by-step, producing a "theoretical trace" of task entry/exit events and branch decisions. The interpreter must handle: sequential block execution, conditional branching based on concrete guard evaluation, bounded loop execution, and function call simulation. This reference trace represents the "expected" behavior of the workflow.

**Milestone P3.3** implements the **Differential Comparator**. This module compares the trace captured from the LLM code (the "actual trace") against the reference interpreter's trace (the "expected trace"). The comparison is performed under the **task-observable abstraction**: two traces are equivalent if they produce the same sequence of task entry/exit events, regardless of intermediate data variable values or silent steps. The comparator computes a **trace alignment** using a variant of the Needleman-Wunsch sequence alignment algorithm, producing a divergence score and a list of mismatch points. If the alignment score is above **0.95**, the traces are statistically equivalent.

**Milestone P3.4** integrates **Randomized Differential Testing**. Generate random concrete inputs (constrained by the BPMN specification's data types), execute both the LLM code and the reference interpreter, and compare traces. Repeat this process for **n = 100** iterations. The V1 confidence score is: `confidence = (matching_traces / total_runs) * input_coverage_score`, where `input_coverage_score` measures the diversity of generated inputs (using a entropy-based metric). If confidence reaches **0.95**, emit the V1 certificate.

**Milestone P3.5** implements the **Multi-Modal Certificate Composer**. This module combines the V1, V2, and V3 certificates into a single correctness certificate for downstream consumption by Module 03. The combined confidence is: `combined = 1 - (1 - v1_confidence) * (1 - v2_confidence) * (1 - v3_confidence)`, assuming independence of failure modes. If `combined >= 0.95`, the WIR is validated and passed to S4 (Code-Derived Model Construction). Otherwise, flag for manual review.

---

## 2. Deep Dive: Hardening Z3 Integration

Your interim report identifies the core challenge: *"passing dynamically generated, unpredictable Python variables into the Z3"*. This section provides the advanced Python architecture to solve this definitively.

### 2.1 The Z3 Variable Registry: Automatic Sort Inference

Z3 requires explicit sort declarations — there is no `z3.AutoSort()`. When an LLM generates a variable like `inventory_count = 42` in one implementation and `inventory_count = 42.5` in another, your system must detect the type difference and select the appropriate Z3 sort automatically. The solution is a two-phase inference system.

**Phase A: Static Type Inference from AST.** During V3 AST traversal, collect all `ast.Assign` and `ast.AnnAssign` (annotated assignment) nodes. If a type annotation exists (e.g., `x: int = 5`), use it directly. For unannotated assignments, perform a lightweight type inference: constants like `ast.Constant(value=5)` map to `IntSort()`; `ast.Constant(value=5.5)` map to `RealSort()`; `ast.Constant(value=True)` map to `BoolSort()`. For binary operations, apply type promotion rules matching Python semantics (int + float → RealSort()). Record these inferred types in a `VariableTypeMap` keyed by `(function_name, variable_name)`.

**Phase B: Runtime Type Confirmation during Concolic Execution.** Even with static inference, LLM code may contain dynamic type changes. The Variable Registry intercepts every variable assignment during concolic execution and confirms the type:

```python
class Z3VariableRegistry:
    """Maps Python variables to Z3 constants with automatic sort inference."""

    def __init__(self):
        self._registry: dict[str, z3.ExprRef] = {}
        self._version_counter: dict[str, int] = {}
        self._type_history: dict[str, list[type]] = {}

    def _infer_sort(self, value: Any) -> z3.SortRef:
        """Map a Python runtime value to its Z3 sort."""
        match value:
            case bool():
                return z3.BoolSort()
            case int():
                return z3.IntSort()
            case float():
                return z3.RealSort()
            case str():
                # Encode strings as integers for arithmetic constraints
                return z3.IntSort()
            case list() if len(value) > 0:
                elem_sort = self._infer_sort(value[0])
                return z3.ArraySort(z3.IntSort(), elem_sort)
            case dict() if len(value) > 0:
                # Flatten: dict_d_key maps to value sort
                first_val = next(iter(value.values()))
                return self._infer_sort(first_val)
            case _:
                # Fallback: create an uninterpreted sort
                sort_name = f"PyObject_{type(value).__name__}"
                return z3.DeclareSort(sort_name)

    def declare(self, name: str, value: Any) -> z3.ExprRef:
        """Declare or retrieve a Z3 constant for a Python variable."""
        py_type = type(value)
        if name in self._registry:
            if self._type_history[name][-1] == py_type:
                return self._registry[name]
            # Type change: version the variable
            self._version_counter[name] = self._version_counter.get(name, 0) + 1
            versioned_name = f"{name}_{self._version_counter[name]}"
            sort = self._infer_sort(value)
            const = z3.Const(versioned_name, sort)
            self._registry[name] = const
            self._type_history[name].append(py_type)
            return const
        # First declaration
        sort = self._infer_sort(value)
        const = z3.Const(name, sort)
        self._registry[name] = const
        self._type_history[name] = [py_type]
        return const
```

The registry maintains a **version counter** for each variable. If `inventory_count` starts as `int` (version `inventory_count_0`) and is later reassigned as `float`, a new constant `inventory_count_1` is created with `RealSort()`. The type-transition constraint `z3.And(inventory_count_0 >= 0, inventory_count_1 >= 0.0)` connects the two versions where type-appropriate.

### 2.2 Encoding Complex Data Structures: Nested Dicts and Arrays

LLM-generated workflow code frequently uses nested data structures to represent business objects — for example, `order = {"items": [{"price": 10, "qty": 2}], "total": 20}`. Encoding this directly in Z3 is intractable for arbitrary nested structures. Instead, apply **selective flattening** combined with **array theory**.

**Strategy: Field Flattening with Path Naming.** For nested dictionaries, flatten the structure into scalar variables using dot-path notation:

| Python Access | Z3 Variable Name | Z3 Sort |
|---|---|---|
| `order["total"]` | `order_total` | Int |
| `order["items"][0]["price"]` | `order_items_0_price` | Int |
| `order["items"][0]["qty"]` | `order_items_0_qty` | Int |

During AST traversal, build a **Field Access Map** that records every field access pattern (e.g., `order["items"][i]["price"]`). For array indices that are symbolic (like the variable `i`), use Z3's Array theory:

```python
# For list accesses with symbolic index
items_array = z3.Array('order_items', z3.IntSort(), z3.IntSort())
# Access: order_items[i] → z3.Select(items_array, i)
# Update: order_items[i] = v → z3.Store(items_array, i, v)
```

For **bounded arrays** (lists of known maximum length, which FLOW-BENCH workflows typically have), use the **finite modeling** approach: pre-allocate Z3 scalar variables for each possible index and use ITE chains for reads:

```python
# Finite modeling for list of max length 5
item_0, item_1, item_2, item_3, item_4 = z3.Ints('item_0 item_1 item_2 item_3 item_4')
# Symbolic read: items[i] where i is symbolic
value = z3.If(i == 0, item_0, z3.If(i == 1, item_1, z3.If(i == 2, item_2, ...)))
```

This ITE approach avoids the overhead of Z3's array theory solver for small, bounded collections and yields significantly faster solving times for workflows with fixed-size data structures (e.g., vending machine items, approval chain stages).

### 2.3 Path Explosion Mitigation: The Three-Layer Defense

Path explosion is the single greatest scalability threat to your concolic execution. Your WIR validation pipeline must implement three complementary defenses:

**Layer 1: Static Bounding via k-Induction.** Before any solver query is issued, statically transform the WIR by unrolling each loop **exactly k times** (recommend k = 3 for FLOW-BENCH workflows, which have bounded iteration semantics). After k unrollings, replace the remaining loop iterations with a **Havoc** assignment: all loop-modified variables are assigned non-deterministic values consistent with the loop invariant. If you cannot infer the invariant automatically, use the **weakest liberal precondition** of the loop body as an approximation. This transforms an unbounded loop into a bounded acyclic CFG suitable for BMC-style analysis.

**Layer 2: Dynamic State Merging with QCE Heuristic.** During concolic exploration, maintain a **state pool** indexed by program location (CFG node). When a new state arrives at a location, check whether it can be merged with an existing state at that location. Two states are mergeable if, for all variables that differ between them, the differing variables are **cold** — meaning they do not appear in any branch condition after that program location. This is the Query Count Estimation (QCE) criterion. Merging creates a disjunctive path condition: `ITE(guard, state1_value, state2_value)`. The QCE heuristic predicts whether the solver cost of the disjunctive condition is less than the cost of exploring two separate paths — merge only when QCE predicts net savings.

**Layer 3: Coverage-Guided Path Pruning.** Track which CFG edges have been covered by previous concolic iterations. Prioritize unexplored edges using a BFS-like strategy. When the solver budget (500 queries) is exhausted, halt concolic execution and rely on V1 (dynamic tracing) for statistical coverage of the remaining paths. This bounded approach is sound: you prove correctness for explored paths, and you statistically validate the rest.

**Architecture for Bounded Concolic Loop:**

```python
class BoundedConcolicEngine:
    def __init__(self, wir: dict, max_k: int = 3, query_budget: int = 500):
        self.wir = wir
        self.max_k = max_k
        self.query_budget = query_budget
        self.solver = z3.Solver()
        self.path_conditions: list[z3.BoolRef] = []
        self.registry = Z3VariableRegistry()
        self.covered_edges: set[tuple[int, int]] = set()

    def execute_loop(self, loop_node: dict, concrete_state: dict, symbolic_state: dict, iteration: int) -> list[tuple[dict, dict, z3.BoolRef]]:
        """Execute a loop with k-bounding and state merging."""
        if iteration >= self.max_k:
            # Havoc: assign non-deterministic values to loop-modified variables
            modified_vars = loop_node['modified_variables']
            for var in modified_vars:
                sort = self.registry._infer_sort(concrete_state.get(var, 0))
                havoc = z3.Const(f"{var}_havoc_{iteration}", sort)
                symbolic_state[var] = havoc
            return [(concrete_state, symbolic_state, z3.BoolVal(True))]

        # Normal loop body execution
        body_states = self.execute_block(loop_node['body'], concrete_state, symbolic_state)

        # Check for state merging opportunities at loop header
        merged = []
        for state in body_states:
            merge_candidate = self.find_merge_candidate(loop_node['id'], state)
            if merge_candidate and self.qce_predicts_savings(state, merge_candidate):
                merged_state = self.merge_states(state, merge_candidate)
                merged.append(merged_state)
            else:
                merged.append(state)

        return merged
```

---

## 3. Deep Dive: Building the sys.settrace Pipeline

The `sys.settrace` mechanism is deceptively simple but requires careful architectural design to avoid computational collapse. A naïve trace function that captures every line, every variable, and every event will slow execution by 100x or more. Your pipeline must be **selective**, **abstract**, and **efficient**.

### 3.1 Trace Function Architecture: The Selective Observable Pattern

The key insight is that you do not need to trace everything. Your WIR abstraction cares only about **task boundaries** (function entry/exit corresponding to BPMN tasks) and **control-flow decisions** (branch conditions). Data computations between these points are irrelevant to process-level equivalence. Design your trace function as a **two-tier filter**:

```python
from types import FrameType
from typing import Any, Callable, Optional
import sys
import copy

class WIRTraceCollector:
    """Low-overhead trace collector for WIR-relevant execution events."""

    def __init__(self, target_file: str, task_patterns: list[str], branch_lines: set[int]):
        self.target_file = target_file  # Only trace the LLM-generated file
        self.task_patterns = task_patterns  # Function names matching BPMN tasks
        self.branch_lines = branch_lines  # Line numbers with if/while/for
        self.trace_log: list[dict] = []
        self._active = False

    def _is_target_frame(self, frame: FrameType) -> bool:
        """Filter: only trace frames from the target module."""
        return frame.f_code.co_filename == self.target_file

    def _is_task_function(self, frame: FrameType) -> bool:
        """Check if the current function matches a BPMN task pattern."""
        return any(pattern in frame.f_code.co_name for pattern in self.task_patterns)

    def trace_callback(self, frame: FrameType, event: str, arg: Any) -> Optional[Callable]:
        """Main trace function — selective capture for minimal overhead."""
        # Tier 1: File filter — ignore library/stdlib frames immediately
        if not self._is_target_frame(frame):
            return None  # Stop tracing this frame and all sub-frames

        func_name = frame.f_code.co_name
        line_no = frame.f_lineno

        if event == 'call' and self._is_task_function(frame):
            # Capture task entry: record function name and control-variable snapshot
            observables = self._extract_observables(frame.f_locals)
            self.trace_log.append({
                'event': 'task_entry',
                'function': func_name,
                'line': line_no,
                'observables': observables,
            })
            return self.trace_callback  # Continue tracing inside the function

        elif event == 'return' and self._is_task_function(frame):
            observables = self._extract_observables(frame.f_locals)
            self.trace_log.append({
                'event': 'task_exit',
                'function': func_name,
                'line': line_no,
                'return_value': self._serialize_value(arg),
                'observables': observables,
            })
            return None  # Stop tracing after return

        elif event == 'line' and line_no in self.branch_lines:
            # Capture branch-point state: record which branch was taken
            observables = self._extract_observables(frame.f_locals)
            self.trace_log.append({
                'event': 'branch_point',
                'line': line_no,
                'observables': observables,
            })
            return self.trace_callback

        # For all other events: continue tracing but don't record
        return self.trace_callback

    def _extract_observables(self, locals_dict: dict) -> dict:
        """Extract only control-relevant variables — shallow copy, not deepcopy."""
        # Filter: only variables that appear in branch conditions (from V3 analysis)
        result = {}
        for var_name in self.control_variables:
            if var_name in locals_dict:
                val = locals_dict[var_name]
                # Serialize as type + equality class, not full value
                result[var_name] = {
                    'type': type(val).__name__,
                    'hash': hash(val) & 0xFFFFFFFF,  # 32-bit hash for comparison
                }
        return result

    def start_tracing(self):
        self._original_trace = sys.gettrace()
        sys.settrace(self.trace_callback)

    def stop_tracing(self):
        sys.settrace(self._original_trace)
```

**Critical Performance Decisions:**

1. **Return `None` aggressively.** When `trace_callback` returns `None`, Python stops tracing that frame and all its descendants. This is your primary overhead control: library calls, standard library internals, and framework code are never traced.

2. **Never use `deepcopy`.** `frame.f_locals` is a mutable dictionary that may contain large objects. Your `_extract_observables` method should only shallow-copy the references to control variables and serialize their types and hashes — never the full values. A `deepcopy` of a 10,000-item list would kill performance.

3. **Pre-compute `branch_lines`.** The set of line numbers containing branch instructions should be computed statically during V3 AST analysis (look for `ast.If`, `ast.While`, `ast.For` nodes). This avoids runtime string parsing of source lines.

4. **Use `sys.monitoring` on Python 3.12+.** If your deployment environment supports Python 3.12 or later, replace `sys.settrace` with the `sys.monitoring` API, which provides C-level event delivery with dramatically lower overhead. The API uses numeric event codes (`PY_START`, `PY_RESUME`, `BRANCH`) and avoids the Python-level callback indirection.

### 3.2 Differential Execution: Comparing Actual vs. Expected Traces

Differential execution compares the trace collected from the LLM code against a reference trace produced by executing the same inputs through a **WIR Reference Interpreter**. The comparison is performed at the level of **task-observable sequences**.

**Step 1: Build the WIR Reference Interpreter.** This is a deterministic Python class that executes a WIR JSON object against concrete inputs:

```python
class WIRReferenceInterpreter:
    """Deterministic interpreter for WIR that produces theoretical execution traces."""

    def __init__(self, wir: dict):
        self.wir = wir
        self.nodes = {n['id']: n for n in wir['nodes']}
        self.trace_log: list[dict] = []

    def execute(self, inputs: dict) -> list[dict]:
        """Execute WIR with concrete inputs, return trace."""
        state = dict(inputs)  # Copy inputs as initial state
        current = self.wir['entry_node']

        while current != self.wir['exit_node']:
            node = self.nodes[current]

            if node['type'] == 'task':
                self.trace_log.append({
                    'event': 'task_entry',
                    'task': node['name'],
                })
                # Simulate task execution: update state per WIR semantics
                state = self._apply_task_effects(node, state)
                self.trace_log.append({
                    'event': 'task_exit',
                    'task': node['name'],
                })
                current = node['successors'][0]

            elif node['type'] == 'gateway':
                # Evaluate guard condition with concrete values
                guard_value = self._eval_guard(node['guard'], state)
                self.trace_log.append({
                    'event': 'branch_point',
                    'gateway': node['name'],
                    'taken_branch': guard_value,
                })
                # Select successor based on guard evaluation
                current = node['successors'][0] if guard_value else node['successors'][1]

            elif node['type'] == 'loop':
                # Bounded execution: iterate up to bound
                for _ in range(node['bound']):
                    if not self._eval_guard(node['condition'], state):
                        break
                    # Execute loop body
                    state = self._execute_block(node['body'], state)
                current = node['successors'][0]

        return self.trace_log

    def _eval_guard(self, guard_expr: str, state: dict) -> bool:
        """Safely evaluate a guard expression with the current state."""
        # Use eval with restricted globals/locals
        allowed_names = {"__builtins__": {}}
        allowed_names.update(state)
        return eval(guard_expr, allowed_names)
```

**Step 2: Normalize and Compare Traces.** Both the actual trace (from `sys.settrace`) and the expected trace (from the reference interpreter) are normalized to sequences of **task-observable events** — tuples of `(event_type, task_name, branch_decision)`. The comparison uses a **Longest Common Subsequence (LCS)** algorithm to find the optimal alignment:

```python
def compare_traces(actual: list[dict], expected: list[dict]) -> dict:
    """Compare actual and expected traces under task-observable abstraction."""
    # Normalize to comparable tuples
    actual_seq = [(e['event'], e.get('function', e.get('task')), e.get('taken_branch'))
                  for e in actual if e['event'] in ('task_entry', 'task_exit', 'branch_point')]
    expected_seq = [(e['event'], e.get('task'), e.get('taken_branch'))
                    for e in expected]

    # LCS alignment
    lcs_length = _lcs(actual_seq, expected_seq)
    max_len = max(len(actual_seq), len(expected_seq))
    similarity = lcs_length / max_len if max_len > 0 else 1.0

    # Find divergence points
    divergences = _find_divergence_points(actual_seq, expected_seq)

    return {
        'similarity_score': similarity,
        'lcs_length': lcs_length,
        'actual_length': len(actual_seq),
        'expected_length': len(expected_seq),
        'divergence_points': divergences,
        'passed': similarity >= 0.95,
    }
```

**Step 3: Randomized Differential Testing.** Generate random inputs consistent with the BPMN specification's data types, execute both implementations, and accumulate statistical confidence. Use a **feedback-directed input generator**: when a divergence is found, use Z3 to generate a **near-miss input** that is similar to the diverging input but should (according to the specification) produce matching traces. This maximizes the information content of each test iteration.

---

## 4. Critical Edge Cases & "Gotchas"

Testing against the FLOW-BENCH dataset will expose four categories of severe technical roadblocks. Architect your code now to avoid them.

### Gotcha 1: The "Silent Step" Explosion in LLM-Generated Code

**The Problem:** LLMs frequently generate "helper" code — variable initializations, format conversions, logging statements, type checks — that has no corresponding BPMN task. Your V3 CFG extractor will produce nodes for these silent steps, and your V1 trace collector will capture them as task entries/exits if their function names happen to match task patterns. This creates **false divergence** when comparing against the reference trace, which has no silent steps.

**The Architecture Fix:** Implement a **Stutter Elimination Pass** before differential comparison. After V3 extraction, run a dominance analysis to identify CFG nodes that: (a) do not modify any control variable, (b) are not branch points, and (c) have a single predecessor and single successor. Collapse these nodes into their successor, recording the stutter in the WIR metadata. During trace comparison, use a **stuttering-insensitive LCS** that permits insertion of silent steps without penalizing similarity. This is the trace-level equivalent of the stuttering bisimulation that Module 03 computes on automata.

### Gotcha 2: Non-Deterministic Dictionary Iteration Order

**The Problem:** Python 3.7+ preserves insertion order for dictionaries, but LLM-generated code may iterate over dictionaries constructed from external data (database queries, API responses) where insertion order is non-deterministic. Two executions of the same code with the same logical inputs may produce different iteration orders, causing your V1 trace comparator to flag false divergences.

**The Architecture Fix:** During V1 trace capture, **hash the iteration state** of every `for` loop that iterates over a dictionary or set. In the trace record, store `(iteration_index, key_hash)` instead of `key_value`. During comparison, match traces by iteration index rather than key value. Additionally, for V2 symbolic analysis, add a **determinism constraint** to the Z3 model: `ForAll(i, j, i < j => dict_key_i < dict_key_j)` to enforce sorted iteration, or simply abstract dictionary iterations as non-deterministic choice over keys.

### Gotcha 3: Exception Handling as Hidden Control Flow

**The Problem:** FLOW-BENCH workflows include boundary events (error handling, timeouts). LLMs implement these using `try/except` blocks. Your V3 AST extractor may treat `try/except` as a simple branch, but exceptions create **non-local control flow** that your V2 concolic engine cannot fully explore (raising an exception depends on the runtime environment, not just input values). A path through the `except` block may be feasible in the LLM code but infeasible in the WIR, or vice versa.

**The Architecture Fix:** Separate exception edges from normal control flow in the WIR. When extracting the CFG from AST, create **dedicated exception edges** from every statement in the `try` block to each `except` handler. Annotate these edges with `exception_type` guards. During V2 concolic execution, do not attempt to symbolically trigger exceptions — instead, perform a **separate exception analysis**: for each `except` block, verify that it is reachable from at least one statement in the `try` block via the dominator tree (structural reachability). During V1 dynamic tracing, use `sys.settrace`'s `'exception'` event to capture actual exception occurrences and compare them against the WIR's exception-edge annotations.

### Gotcha 4: The State-Mutation-Outside-Task-Boundary Hallucination

**The Problem:** Your report (Chapter 2) identifies that LLMs hallucinate "state transitions that violate strict business constraints." A particularly insidious variant occurs when an LLM modifies a workflow state variable (e.g., `loan_status`) inside a utility function or helper method that is not mapped to any BPMN task. This violates the BPMN semantics that state changes should only occur at task boundaries.

**The Architecture Fix:** Implement a **State-Mutation Audit** pass in V3. After CFG extraction, perform a reaching-definitions analysis to identify every assignment to a variable that appears in a BPMN data object reference. Check whether the assignment occurs inside a CFG node that corresponds to a BPMN task. If a state variable is mutated outside a task boundary, flag the mutation in the WIR certificate and emit a **warning-level discrepancy**. During V1 tracing, capture all mutations to state variables and verify they occur only within traced task-entry/task-exit intervals. This is your primary defense against the "inventory never negative" class of safety violations.

---

## References

| # | Source | Citation |
|---|--------|----------|
| 1 | Programming Z3 (Stanford) | Stanford theory group Z3 tutorial |
| 2 | Efficient State Merging in Symbolic Execution (PLDI 2012) | PLDI '12 — Query Count Estimation (QCE) and Dynamic State Merging (DSM) |
| 3 | Accelerating Array Constraints in Symbolic Execution | KLEE array paper — finite modeling vs. SMT-LIB arrays |
| 4 | Handling Loops in Bounded Model Checking (STTT 2015) | Cordeiro et al. — k-induction, forward condition, ESBMC |
| 5 | Differential Symbolic Execution | UCK-LEE automatic grading paper — trace deviation detection |
| 6 | Python sys.settrace documentation | docs.python.org/3/library/sys.html |
| 7 | Coverage.py internals — sys.settrace and sys.monitoring | coverage.readthedocs.io — C trace function implementation |
| 8 | FLOW-BENCH dataset paper (EMNLP 2024) | Duesterwald et al. — 101 incremental build tests |
| 9 | Python AST documentation — Node classes | docs.python.org/3/library/ast.html — Try, TryStar, NamedExpr, Match |
| 10 | The unreasonable effectiveness of sys.settrace | expLog.in — frame modification, event types, state inspection |
