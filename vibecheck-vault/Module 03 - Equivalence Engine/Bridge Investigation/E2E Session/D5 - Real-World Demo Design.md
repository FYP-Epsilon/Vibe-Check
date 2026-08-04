# D5 — Real-World Demo Design

> Repo at `main @ 0daf57e`. Depends on D1–D4. The demo is the artifact that makes the thesis
> defensible in a viva: a live spec→code check that produces a real counterexample.

## 1. What the demo must show

Three things, in order, and nothing more:

1. A BPMN spec goes in; a real LTLf property suite comes out (Module 01).
2. Python code goes in; a WIR comes out (Module 02).
3. The two meet and produce a **per-property verdict with a counterexample trace** on a
   deliberately-divergent pair (Module 03).

The third is the only novel claim. Points 1 and 2 already have working UI pages
(`module_04_ui/src/app.py`, spec-engine and extract-engine tabs both POST to `/verify`,
VERIFIED-SOURCE at lines 274-275 and 385-386).

## 2. Selection criteria for demo pairs

Constrained hard by the findings. A demo pair must:

- **Be gateway-free.** Module 01 hard-fails on every spec containing `<exclusiveGateway>`
  (VERIFIED-EXPERIMENT, 19/19, set equality tested). A branching demo is impossible until D4 §M4.2
  is resolved. This is the most restrictive criterion and it eliminates the most visually
  compelling demo (a decision that goes the wrong way).
- **Have ≥3 sequential tasks**, so a reordering or omission is visible rather than trivial.
- **Yield ≥2 node()-free P1 properties**, since only 17.6% of P1 is checkable and the median per
  spec is 2 (VERIFIED-EXPERIMENT). 22 of 29 eligible specs qualify.
- **Have task names that the matching cascade can resolve.** Spec-task→function-name exact match
  averages 86.0% across 43 pairs with 26/43 at 100% (VERIFIED-EXPERIMENT), so this usually holds,
  but a hand-written demo could easily break it and would then show `INCONCLUSIVE` rather than a
  verdict — an unimpressive outcome that looks like a tool failure.

### The divergent pair: construct it, do not hunt for it

The deliberately-divergent pair should be a **reordering**, not an omission, and this is a
non-obvious point that the findings force.

**VERIFIED-EXPERIMENT** (truth table over `evaluate_ltlf()`, `module_01_spec/src/ltlf_eval.py:202`):
the P1 precedence shape `!start(B) W done(A)` evaluates `True` when B is simply omitted. Omission
satisfies precedence vacuously. So an omission demo would show a green COMPLIANT verdict on
obviously-wrong code — the worst possible live demonstration.

A reordering demo does work. **Counterexample trace, as required — reachable from the real
construction:** on uid 44 (VERIFIED-EXPERIMENT), spec order is SalesOrder → PriceLevel → Invoice →
Slack. `44__llama-3.1-8b.py`'s orchestrator calls Invoice → Slack → PriceLevel → SalesOrder. The
property `!start(PriceLevel) W done(SalesOrder)`, under D1 §3 Option B, becomes
`!PriceLevel W SalesOrder`; on the call-order trace `PriceLevel` (index 2) precedes `SalesOrder`
(index 3), so the formula is violated and `check_compliance()` produces a counterexample trace.
This is a real FLOW-BENCH pair, already in the corpus, already measured as divergent — **no
construction needed for the divergent case.**

**Important caveat:** that trace depends on **call-order lifting** (D2 / M3). Under the current
definition-order lifter the same pair's verdict comes from definition positions, and D2 §6 measured
that 10 of 11 such extra detections name functions that are never called. **A demo run before M3
risks showing a FAIL whose witness is not executable** — which a viva examiner could reasonably
challenge. Recommendation: **the divergent demo should be gated on M3**, or the witness must be
manually confirmed executable before showing it.

### Three-pair demo set

| pair | source | expected verdict | purpose |
|---|---|---|---|
| **conformant** | one of the 15 measured-conformant (spec, variant) pairs | COMPLIANT on all checkable P1 | shows no false alarm |
| **divergent (reorder)** | uid 44 + `44__llama-3.1-8b.py` | VIOLATION + executable counterexample | the headline |
| **inconclusive** | a spec whose code uses unmatched action names | INCONCLUSIVE + `unmatched_atoms` | shows the tool refuses to guess — this is the vacuity fix (fact 1) working, and is worth demonstrating deliberately rather than hiding |

The third pair is a design choice worth defending: showing an honest INCONCLUSIVE is stronger
evidence of soundness than two green checks.

### Real-world (non-FLOW-BENCH) pairs

For a genuinely real-world demo, the constraint that bites is **depth-1 inlining** (D2 §2c). In
FLOW-BENCH the orchestrator calls business functions directly with trivial bodies
(VERIFIED-EXPERIMENT on `82__llama-3.1-8b.py`, `77__llama-3.1-8b.py`). Real code nests. Criteria:
a flat orchestrator (one function calling named steps in sequence), no branching, ≤10 steps, and
step names that lexically resemble the BPMN task names. Realistically that means a
**purpose-written** demo workflow — e.g. an onboarding or invoice-approval flow authored as a clean
BPMN file plus an LLM-generated implementation. Flagged NOT-ESTABLISHED that the entry-point
heuristic (max-sibling-calls) picks correctly on arbitrary real-world code; it is measured only on
FLOW-BENCH.

## 3. UI prerequisite — larger than "the import is wrong"

The prompt notes M04's equivalence page uses in-process `import vibecheck_lifter` instead of an
HTTP call. That is true (VERIFIED-SOURCE: `module_04_ui/src/app.py:542-543`, and a guard at line 98,
with an error message at 561). **But the reason it cannot simply be converted to an HTTP call is
that there is no service to call.**

**VERIFIED-SOURCE.** `module_03_equiv/src/main.py` is a *demo script*, not a service: it imports the
compiled module, builds a hardcoded mock WIR (`control_variables`, `types` including a
`risk_profile: "Any"` over-approximation case), calls `parse_wir_types` and `semantic_match` on
three fixed test actions, prints results, `time.sleep(2)`, exits. Grep for `fastapi`/`FastAPI`/
`uvicorn` anywhere in `module_03_equiv/` returns **nothing**. The Dockerfile's `CMD` is
`["python3", "-m", "src.main"]` (line 50), and `docker-compose.yml`'s `equiv-engine` service
declares **no `ports`** — consistent with a script that runs once and exits.

Compare: `spec-engine` and `extract-engine` both expose `/verify` and the UI already POSTs to them
by service name (VERIFIED-SOURCE).

So the prerequisite is: **give Module 03 an HTTP service with a `/verify` (or `/check`) endpoint,
change its `CMD` to a uvicorn invocation, and add a `ports` entry.** Minimal contract — accepts
`{wir: <json>, property_suite: <M01 export>}`, returns per-property verdicts with
`counter_example_trace` and `unmatched_atoms`. This is new work, not a one-line fix, and it should
be stated as such in the plan (D4 §M5.2). It does not require redesigning M04's architecture — the
UI change is then the same `requests.post` pattern already used twice.

Second prerequisite: **Module 01's service must start at all.** `module_01_spec/src/main.py` imports
the deleted `automata_lifter` in both fallback branches (VERIFIED-SOURCE, lines 11 and 16; module
absent from `src/`), so the spec-engine page cannot work in a live demo even though the library
does. D4 §M0.2.

## 4. What the demo page must display

Beyond a verdict badge, three things the findings make necessary:

1. **The tier gate, visibly.** 288 of 412 properties are out-of-scope by design (D1 §5). If the
   page shows "3 of 41 properties checked" without explaining the other 38, it reads as a broken
   tool. Show counts by category: checked / out-of-scope (with reason) / inconclusive.
2. **The counterexample trace as an action sequence**, side by side with the spec's expected
   sequence. This is the artifact that makes the FAIL actionable and is the whole point of the
   demo.
3. **The lifting model in use** (definition-order vs call-order) and the entry-point function the
   lifter selected. Both are decisions the tool makes silently and both change verdicts (29.3%
   disagreement, VERIFIED-EXPERIMENT).

## 5. Demo failure modes to rehearse

- **All INCONCLUSIVE** — the F2 signature (atom vocabularies disjoint). If D1 §3 was not
  implemented, this is what the demo shows. Rehearse against the real pipeline, not a mock.
- **Green on obviously-wrong code** — the omission blindness (F4). Avoid by choosing a reordering
  demo, as above.
- **Non-executable witness** — the D2 §6 finding. Avoid by gating on M3 or hand-checking.
- **Wrong entry point selected** — the heuristic picks the max-sibling-call function; on demo code
  with a `main()` wrapper it could pick wrong. Display the selection so it is diagnosable live.
