# D2 — Lifting-Scope Fix Design (Option 2: call-site lifting via sub-CFG inlining)

> Repo at `main @ 0daf57e`. Depends on findings F4, F5, F6 in
> `00 - Session Findings and Plan Impact.md`.
>
> **Headline that the prompt's framing does not anticipate:** this fix *reduces* measured
> detection rate on the current corpus, from 53.2% to 40.4%, and I recommend doing it anyway,
> because the detection the current lifter achieves is traceably spurious. §5 and §6 give the
> measurement and the trace.

## 1. Verifying prompt fact 5 against the real WIR (required before relying on it)

**VERIFIED-SOURCE.** `shared_schemas/wir_schema.json` defines `functions` as a recursively-typed
mapping of function name → a full CFG object (same `nodes`/`edges`/`entry_node`/`exit_node` shape
as the top level). It is a first-class part of the format, so consuming it is not a schema change.

**VERIFIED-SOURCE.** `module_02_extract/src/ast_extractor/cfg_extractor.py`: `visit_FunctionDef`
records a function as a single opaque `task`-typed boundary node whose `code` is a synthesized
signature line; its docstring states the body is not inlined but stored as a separate sub-CFG.
`extract()` then builds each top-level function's sub-CFG by walking its body in source order, and
runs `contract_bookkeeping_nodes()` over both the top-level graph and each sub-CFG.

**VERIFIED-EXPERIMENT.** Extracting `100__llama-3.1-8b.py`: `WIR["functions"]["workflow"]`
contains the business calls as ordinary `block` nodes in source order, chained by edges, with
`entry_node`/`exit_node` set. **Fact 5 confirmed: the correct execution order already exists in
Module 02's output.**

**VERIFIED-SOURCE.** `lifter.cpp` contains **zero references to `functions`** (grep returns
nothing). The order is not wrong — it is never read.

**One caveat the vault does not record, and it matters for the design.**
VERIFIED-EXPERIMENT: across all 184 normalized variants, **every variant has at least one sub-CFG
whose declared `exit_node` has no outgoing edge.** That is expected for a function body (the exit
is a terminal), but an inlining algorithm that splices a sub-CFG into a caller must therefore
*synthesize* the return edge from the sub-CFG exit back to the call-site successor rather than
assume one exists. Getting this wrong produces a lifted automaton that dead-ends at the first
inlined call — which would look like a lifting bug and read as a conformance violation.

## 2. What the fix changes

The lifter currently walks the top-level graph, treats each `task` node as an action, and derives
its label from the node's code via `extract_actions_from_code()` (`lifter.cpp:185`) and
`semantic_match()` (`lifter.cpp:135`). Since `task` nodes are function *definitions*, the resulting
action sequence is definition order.

Target behavior: the automaton's action sequence is the sequence of **call sites** encountered by
walking the orchestrator's sub-CFG, with each call to a known business function contributing one
action labelled by `semantic_match()` on the callee name.

Three sub-problems, in dependency order:

**(a) Entry-point selection.** Which sub-CFG is the orchestrator? The current top-level walk has no
notion of one. Options: the function that calls the most sibling top-level functions (what I used
for measurement — VERIFIED-EXPERIMENT, it picks `workflow` in every corpus variant I inspected);
or the conventional name `workflow` (present in the corpus, but corpus-specific and would not
generalize to real-world demo code — see D5); or a WIR-level `entry_function` field that Module 02
would need to add. **Recommendation: max-sibling-calls heuristic, with the selected name recorded
in the lifter diagnostics** so a wrong pick is visible in the report rather than silent. Flagged
NOT-ESTABLISHED that this heuristic is correct on real-world code outside FLOW-BENCH; it is
measured only on this corpus.

**(b) Call-site detection inside sub-CFG `block` nodes.** The existing regex at `lifter.cpp:188`
already extracts call names from code lines, and the `structural_builtins` set at `lifter.cpp:190`
already filters Python builtins and common method names (VERIFIED-SOURCE). Reusing it is right;
the change is *where* it is applied (sub-CFG block nodes rather than top-level task nodes), not
*how*.

**(c) Inlining depth.** Nested business calls (orchestrator → helper → business call) would need
recursive descent. **VERIFIED-EXPERIMENT:** in this corpus the orchestrator calls business
functions directly and those functions have trivial bodies (`return {}`) — e.g. `82__llama-3.1-8b.py`
and `77__llama-3.1-8b.py`, read directly. So **depth-1 inlining is sufficient for FLOW-BENCH**,
and recursive descent is a real-world-demo concern (D5), not a Milestone-2 concern. Design the
recursion boundary as a configurable depth with a recorded value, so the limitation is visible.

## 3. Blast radius in `lifter.cpp`

**VERIFIED-SOURCE** unless noted.

| Area | Location | Impact |
|---|---|---|
| `lift_to_lts` / `build_spot_automaton` | `lifter.cpp` (Phase A) | **rewritten walk** — the core change |
| `extract_actions_from_code` | `lifter.cpp:185` | reused unchanged |
| `semantic_match` 3-tier cascade | `lifter.cpp:135` | reused unchanged; note tier 3 calls into Python `nlp_utils` under `gil_scoped_acquire`, so the C++ walk must not hold the GIL wrongly during the new loop |
| `normalize` | `lifter.cpp:106` | unchanged |
| `ensure_ap` / AP registration | `lifter.cpp:92` | touched if D1's Option A lifecycle APs land here |
| Phase B stuttering minimization | `src/stuttering_engine.py` + C++ | **behavior changes because input geometry changes**, not because the algorithm changes |
| Phase C clustering | `src/clustering.py`, `cluster_implementations` | **cluster memberships will change** — variants that were clustered together by definition-order accident may separate, and vice versa. This is a *result* change to be reported, not a regression |

**Test impact (VERIFIED-SOURCE counts):**

| file | test defs | hardcoded `num_states()`/`num_edges()` asserts | gated on C++ import |
|---|---|---|---|
| `tests/test_cpp_engine.py` | 32 | 7 | yes (`pytestmark`, line 31) |
| `tests/test_phase_b.py` | 28 | 15 | yes (line 31) |
| `tests/test_phase_c.py` | 19 | 3 | yes (line 29) |
| `tests/test_pipeline.py` | 37 | 3 | no |
| **total** | **116** | **28** | 79 gated |

Also: `tests/test_cpp_engine.py` has 9 assertions referencing AP names (VERIFIED-SOURCE,
`grep -cE 'matched_aps|ap_name|\.ap\(\)'`), which are affected if lifecycle APs land.

**Concrete effort estimate: 1 core file rewritten in part (`lifter.cpp` Phase A), 28 geometry
assertions to re-derive, 9 AP-name assertions to review, 2 Python phase modules to re-baseline,
plus new tests for sub-CFG walk / entry-point selection / return-edge synthesis.** The 28 geometry
assertions are the bulk of the mechanical work and cannot be mass-updated safely — each encodes an
expected automaton shape for a specific fixture, so each needs re-derivation by hand from the new
semantics. Budget this as the dominant cost, not the walk rewrite.

**BUILD-DEPENDENT and I want to be blunt about it:** `import vibecheck_lifter` fails in this
environment (VERIFIED-EXPERIMENT, `ModuleNotFoundError`), so 79 of the 116 tests cannot run and
none of this can be validated until a SPOT + pybind11 build works. Every behavioral claim in this
document about the *current* lifter is read from source or emulated in Python. **A working build is
a prerequisite for Milestone 2 and should be sequenced before it** (D4 §M0).

## 4. Interaction with the ordering findings

Two facts constrain what this fix can be expected to buy.

**The structural partition (F5, VERIFIED-EXPERIMENT):** across 184 variants, 0 have top-level
gateways, 184 have top-level tasks, 0 have task-typed nodes inside sub-CFGs, gateways appear only
inside sub-CFGs. **REASONED** (chain: sub-CFG inlining brings gateway nodes into the same walk as
call-site actions → the partition dissolves as a side effect): this fix is *also* the fix for the
gateway/task partition, which is a stronger argument for it than the ordering argument. But it has
no FLOW-BENCH payoff, because **no gateway-bearing spec can produce a property suite at all**
(F1 — Module 01 hard-fails on all 19). The branching capability becomes real and untested
simultaneously.

**The omission-dominance finding (F4, VERIFIED-EXPERIMENT):** 23 of 43 corpus pairs diverge by
omission, 2 by reordering only, 3 by both. This fix targets *ordering* fidelity. **REASONED**: on
this corpus, ordering fidelity is the minority failure mode, so the fix's measurable effect on
detection is bounded by ~5 of 43 pairs regardless of how correct it is.

## 5. Measured effect: detection goes *down*, and that is the honest result

I emulated both liftings in Python and evaluated Module 01's real node()-free P1 properties with
`evaluate_ltlf()` (`module_01_spec/src/ltlf_eval.py:202`) — the same evaluator Module 01 ships.
Model A = current lifter (definition order); Model B = this fix (call order).

**Oracle sanity check first (VERIFIED-EXPERIMENT):** evaluating each spec's own task order against
its own P1 properties gives **45/45 satisfied**. The oracle is self-consistent, so a `False` below
means genuine disagreement, not a broken property.

**Raw disagreement (VERIFIED-EXPERIMENT):** across 58 (variant, property) checks, A and B disagree
on **17 (29.3%)** — 12 where A says violated and B says satisfied, 5 the reverse. So the fix
materially changes verdicts; it is not cosmetic.

**On the subset where the spec-order oracle is complete** (24 of 29 specs, where a single-successor
walk reaches every task node — the other 5 have unreachable tasks and would bias the denominator;
VERIFIED-EXPERIMENT):

| | false-positive rate on conformant code | detection rate on divergent code |
|---|---|---|
| Model A (definition order) | 0.0% | **53.2%** (n=47 checks) |
| Model B (call order, this fix) | 0.0% | **40.4%** (n=47 checks) |

Both are sound on conformant code (0 false positives; n=3 conformant property-checks in this
subset — a small denominator I will not over-read). **Model A detects more.** A naive reading says
do not do the fix.

## 6. Why the extra detection is spurious — traced, as required

The design prompt requires that any "detects/prevents/preserves" claim be traced to a concrete,
reachable counterexample from the *real* construction. Applying that rule to the *opposing*
option is what settles this.

**VERIFIED-EXPERIMENT.** I isolated all 11 property-checks where Model A reports a violation and
Model B does not, and inspected whether the two tasks in each property are actually called at
runtime:

| Are the two tasks in the property actually called? | cases |
|---|---|
| **neither task is ever called** | **9** |
| only the earlier task is called | 1 |
| both called | 1 |

So **10 of 11 of Model A's extra detections rest on tasks that never execute.** Model A flags them
because both functions are *defined*, in a relative definition order that happens to contradict the
spec. Example (VERIFIED-EXPERIMENT): `73__llama-3.1-8b.py`, property relating
`Calendly_eventInvitee…` before `Box_File__3_0_0__create_File` — Model A reports a violation from
definition positions 0 and 1; neither function appears in the call sequence at all.

**The counterexample trace Model A would emit is not executable.** `check_compliance()` returns a
`counter_example_trace` (VERIFIED-SOURCE, `ComplianceResult` field), and the whole value
proposition of the tool is that a FAIL comes with a witness a developer can act on. A witness
saying "you call B before A" about two functions that are never called is a false explanation of a
real defect. The code *is* divergent — by omission (F4) — but Model A gets the right verdict for
demonstrably the wrong reason, and would mislead the developer reading the report.

The remaining case where both tasks *are* called and A flags while B does not is worse: there,
runtime order is correct and A's violation is simply false at the property level; it is masked in
the aggregate only because that variant is divergent for an unrelated reason.

**Therefore:** the 53.2% → 40.4% decrease is not a capability loss. It is the removal of
coincidental verdicts backed by non-executable witnesses. Model B's 40.4% is a *lower and more
defensible* number, and this is exactly the kind of result the reframe in the prompt says is
thesis-grade. The right way to report it is as a paired comparison with the spuriousness analysis
above — that is a genuinely interesting methodological finding about self-consistent-looking
verification, and it belongs in the thesis.

**Owner decision:** accepting a headline detection number that goes down in exchange for
correctness of witnesses is your call. My recommendation is to do the fix and report both numbers
with the trace. If the thesis timeline cannot absorb the 28-assertion re-derivation, the
alternative is to ship Model A *with the spuriousness analysis published as a known limitation* —
which is honest, but leaves the tool emitting witnesses it cannot justify.

## 7. What this fix does not fix

- **Omission blindness** (F4) — needs the coverage tier in D1 §6, not this.
- **Gateway conformance** — unblocked structurally, untestable until Module 01's Phase-3 gate
  admits gateway specs (F1).
- **P2 / P3 checkability** — separate concerns (D1 §4).
- **Nested-call depth** — depth-1 is enough for FLOW-BENCH, not for arbitrary real-world code (§2c).
