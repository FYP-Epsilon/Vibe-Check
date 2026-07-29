# E2E Integration — Verification Findings

> Source: independent re-verification (Claude Code, repo access) of the Claude Science "E2E
> Session" design round — [[E2E Session/00 - Session Findings and Plan Impact|00]] and design docs
> D1–D6, archived at [[E2E Session/00 - Session Findings and Plan Impact|E2E Session/]]. Repo at
> `main-demo @ 0daf57e`. Every claim below was independently re-derived — either by re-running the
> same measurement against the real repo, or, for the crown-jewel detection-rate figures, by
> **compiling `vibecheck_lifter` for the first time this project has had a working local build**
> and running the real compiled engine instead of a Python emulation.

## Headline

Sessions F1–F5 (the reframing findings in [[E2E Session/00 - Session Findings and Plan Impact|00]])
all reproduce closely enough to trust. The design docs built on them (D1–D4) are sound. But the
real build surfaced something none of the six design docs anticipated, because none of them had a
working compiled engine to test against:

**`check_compliance()` still returns a vacuous `COMPLIANT` for every property on every non-looping
automaton, independent of atom matching — confirmed live on the compiled artifact.** This is a
second, still-open channel of the vacuity bug this project already knows about (the first channel —
atom-vocabulary mismatch — was fixed in PR #67). It means the 53.2%/40.4% detection-rate figures in
D2, however carefully derived, describe what Module 01's own finite-trace evaluator (`evaluate_ltlf`)
would say — not what the real engine says today. On the non-looping majority of FLOW-BENCH (i.e.
effectively the whole eligible corpus — see below), **the real engine's current detection rate is
zero**, for any lifting scheme, until this is instrumented. See "The new finding" below before
reading D2's numbers as a real-system projection.

## What reproduced cleanly

| Finding | Session's claim | My result | Verdict |
|---|---|---|---|
| F1 — gateway hard-fail | 19/48 FAIL, 29/48 FAIL_ALIGNMENT_UNPROVEN, 0 PASS; failing set == `<exclusiveGateway>` set | Re-ran `run_module_01_pipeline` over all 48 specs: **identical tallies, identical uid list, set equality confirmed** | ✅ exact match |
| F2 — AP disjointness | 0/116 spec atoms match code APs; 100% INCONCLUSIVE once syntax reaches `check_compliance` unstripped | Confirmed both **logically** (from the atom-gate source I added in PR #67) and **empirically on the real compiled engine**: 58/58 real checks with raw `start_T`/`done_T` atoms → 100% INCONCLUSIVE | ✅ exact match, and now real-build-confirmed, not just emulated |
| F3 — P1 checkability | 45/256 (17.6%) P1 node-free; 22 specs; all 29 P2 = one `<=`-bearing template | Re-ran the extraction over all 29 eligible specs: **256, 45, 17.6%, 22 — identical**, same P2 template | ✅ exact match |
| F4 — omission dominance | 23/43 omission-only, 2/43 reordering-only; vacuous-truth table for `!start(B) W done(A)` | Vacuous-truth table: **identical, all 5 rows**, reproduced directly against Module 01's `evaluate_ltlf`. Divergence-mode classification (cruder substring name-matching, so not byte-identical): 24 omission-only / 3 reorder-only / same N=43 total — **same dominance pattern**, and the two *specific* files the session cited as P1-blind (`77__llama-3.1-8b.py`, `82__llama-3.1-8b.py`) independently reappear in my own P1-blind list | ✅ qualitative + point match; exact split differs, attributable to matching-heuristic looseness, not a refutation |
| F5 — sub-CFG order + partition | `WIR["functions"]["workflow"]` has business calls in source order; `lifter.cpp` has 0 refs to `functions`; every sub-CFG's `exit_node` has no outgoing edge | Extracted `100__llama-3.1-8b.py` directly: **confirmed exactly**, including the no-outgoing-edge exit node (`node_3`, 0 outgoing edges) | ✅ exact match |
| Gateway default-flow question (D4 §M4.2, flagged NOT-ESTABLISHED by the session) | "the gate may be correct... which I couldn't establish" | Parsed all 20 splitting `exclusiveGateway`s across all 19 gateway-bearing specs directly: **0/20 declare a `default` attribute, 0/20 have a `conditionExpression` on any outgoing flow.** The FLOW-BENCH BPMN files contain no decision logic at all for these gateways — not a Module 01 parsing gap | ✅ **resolved** — was an owner-decision blocker, now a verified fact |
| Cheap source/config claims (main.py, fastapi, compose ports, `functions` refs, `FormulaNormalizer` callers) | see D1–D2 | All confirmed by direct read/grep | ✅ exact match |

One small correction: F1 attributes the gateway hard-fail to "Phase 3." Tracing `api.py`'s
exception handling, the raise happens inside `FLTLSynthesizer.run_pipeline()`'s own certification
step (`ltlf_synthesizer.py:_layer_v1_certify`) and is caught by the `except VerificationException`
block at `api.py:105`, which attributes it to **`"phase": 2`** — confirmed by direct reproduction.
Message text, counts, and set-equality are all otherwise exactly right.

## The new finding: a second, still-open vacuity channel, confirmed on the real compiled engine

This project's Module 03 knowledge base has documented **two** vacuity channels since the P1.4
Bridge Findings (2026-07-29):

1. **AP-vocabulary mismatch** — formula atoms absent from the code automaton's AP set. **Fixed** in
   PR #67 (the atom-matching gate; returns `INCONCLUSIVE` with `unmatched_atoms` instead of a false
   verdict).
2. **Structural non-looping vacuity** — "the lifter never sets an acceptance condition ... any
   non-looping (terminating) code automaton has an empty ω-language." Documented as open
   ("vacuous on non-looping automata until instrumented") in [[Module 03 Knowledge]]. **Still open.**
   PR #67 did not touch this — it fixed channel 1 only, and was never claimed to fix channel 2.

This session compiled `vibecheck_lifter` for the first time on this machine (Homebrew SPOT 2.15.1 +
pkg-config + cmake + nlohmann-json + a scratchpad venv with pybind11 3.0.4 — an existing `build/`
directory from earlier this session reconfigured and rebuilt cleanly; 113/116 tests pass, the 2
known-unrelated `compute_deterministic_hash` failures unchanged, 1 skip). That build makes it
possible, for the first time, to check channel 2 empirically rather than by reading source.

**Direct test (VERIFIED-EXPERIMENT):**

```python
wir = {  # entry -> A() -> B() -> exit, no loop
    "entry_node": "n0", "exit_node": "n3",
    "nodes": [
        {"id": "n0", "type": "entry", "code": []},
        {"id": "n1", "type": "task", "code": ["A()"]},
        {"id": "n2", "type": "task", "code": ["B()"]},
        {"id": "n3", "type": "exit", "code": []},
    ],
    "edges": [{"source": "n0", "target": "n1"}, {"source": "n1", "target": "n2"},
              {"source": "n2", "target": "n3"}],
}
# lifter.set_bpmn_tasks(["A", "B"]); graph = lifter.build_spot_automaton(json.dumps(wir))
# vl.check_compliance(graph, "G(!B)")  ->  verdict = "COMPLIANT", unmatched_atoms = []
```

`G(!B)` — "B never happens" — is reported **`COMPLIANT`**, even though the automaton's only
execution literally calls `B`. Atoms are matched (`unmatched_atoms` empty), so channel 1's gate does
not fire; this is channel 2, live.

Confirmed this is not an artifact of that toy example: re-running the same check against uid 44's
real extracted WIR (`44__llama-3.1-8b.py`, spec order SalesOrder→PriceLevel→Invoice→Slack, code
definition order Invoice→Slack→PriceLevel→SalesOrder — an obvious, total reversal) gave
`matched_aps` containing all 4 real spec-task atoms, `unmatched_atoms: []`, and **`COMPLIANT`** on
`!PriceLevel W SalesOrder` — a property that is genuinely violated on this ordering. Running the
full corpus (Model-A-equivalent: current lifter + Option-B prefix stripping, 29 eligible specs, 43
variants, 58 property-checks): **0 violations across the entire corpus** — 3 conformant checks (0%
false positives, consistent with the session's finding) and **55 divergent checks, 0 detected**
(vs. the session's emulated 53.2%).

**Why, precisely (REASONED from VERIFIED-SOURCE):** `grep` for `set_buchi`, `set_acceptance`,
`set_generalized_buchi` across `lifter.cpp` returns nothing — no acceptance condition is ever set on
a built automaton. `test_cpp_engine.py`'s own pre-existing test,
`test_finite_automaton_passes_all_properties`, already asserts this as intended behavior
(`# vacuously true`). Checked whether the corpus dodges this by being loop-bearing anywhere: **0 of
43 top-level WIR graphs for the eligible corpus contain a cycle** (direct cycle-detection over
nodes/edges) — every eligible-corpus automaton is exactly the case this bug hits. One correction to
the vault's stated *mechanism*: the existing text also cites "exit states may have no outgoing edge"
as a cause; the diagnostics for uid 44 report `deadlock_states: 0`, which argues against dead-ends
being the active mechanism here. The safer claim is: effect = empty *accepting* ω-language (solid);
cause = no acceptance condition is ever set (grep-verified); the dead-end-exit explanation should be
treated as unconfirmed, not restated as established.

**What this does and doesn't mean:**

- This is **not** a failure of PR #67 — that fix targeted a different, narrower channel and the
  atom-gate's own real-build test (100% INCONCLUSIVE on raw lifecycle atoms) passed exactly as
  designed. It is the confirmation-and-elevation of an already-flagged open item, not a new bug.
- D2's 53.2%/40.4% numbers are **not disconnected garbage** — they come from Module 01's own
  finite-trace evaluator, which is the correct oracle for LTLf truth. They describe what detection
  *could* look like once the automaton is properly instrumented for infinite-trace acceptance (the
  standard LTLf→LTL bridge — SPOT's `from_ltlf()` "alive"-proposition/stutter-extension technique,
  already named in this project's own bridge investigation). Report them as a **post-instrumentation
  projection**, not as today's system behavior.
- **This is now the actual gate**, above the lifecycle-AP decision, above the gateway scope
  decision, above the entire Model-A-vs-Model-B lifting-scope debate (D2). Both lifting schemes are
  equally moot on the real engine until channel 2 is instrumented — neither can produce a real
  `VIOLATION` on the non-looping majority of FLOW-BENCH today.
- **Concrete consequence for D5 (the real-world demo):** a demo built today cannot show a single
  red `FAIL` on a non-looping example, no matter how obviously wrong the code is. D5's own design
  calls for "at least one deliberately-divergent pair to show a real counterexample-driven FAIL" —
  that scenario is currently unreachable, not just untested.
- Scope note, in keeping with this project's own convention: this finding is reported, not designed
  around. Instrumenting the acceptance condition is implementation work for a future round, not
  something to improvise inside a verification pass.

## D1–D6 design review (given the above)

- **D1** (M01→M03 wiring) is sound and unaffected in its own scope — ingestion, tier-gating, and the
  Option-B atom-vocabulary recommendation are all still the right Milestone-1 shape. Its own
  counterexample trace (uid 44, Option B) is a **property-level** analysis (does the string-level
  formula hold on the intended trace) and doesn't depend on `check_compliance`'s automaton
  machinery, so it stands independent of the new finding.
- **D2** stands as a **design and a methodology finding**, not as a live measurement. Its own
  discipline (tracing whether a detection claim is reachable from the real construction) is exactly
  the right instinct — it's the same discipline that surfaced channel 2 here, one level up. The
  10-of-11 spurious-detection argument and the "worse" 1-of-11 case are logically sound on their own
  terms and remain valid *once real detection exists to have an opinion about*.
- **D3, D4** need one new milestone that predates everything currently in M0–M5: instrumenting
  channel 2 (accept condition / LTLf→LTL bridge). Until then, M2's "first full FLOW-BENCH run" exit
  gate (Table 3 populated) would report a wall of `COMPLIANT`, indistinguishable in the table from
  "the code is correct" unless this finding travels with it.
- **D5** should not schedule the divergent-pair demo scenario until channel 2 lands — currently it
  cannot be satisfied.
- **D6**'s parallelization logic is unaffected; this finding is itself further thesis-grade material
  (a second, independently-discovered instance of the project's running theme: verification
  machinery that looks like it works until someone traces whether detection is reachable from the
  real construction).

## Gateway default-flow question — resolved

D4 §M4.2 flagged as NOT-ESTABLISHED whether the 19 gateway-bearing specs are genuinely
under-specified or whether Module 01's gate is over-strict. Resolved: **every one of the 20
splitting `exclusiveGateway`s in the corpus lacks both a `default` attribute and any
`conditionExpression` on any outgoing flow.** The BPMN source files contain no decision logic for
these gateways at all. The gate is doing exactly what a decision-logic-requiring synthesizer should
do with genuinely underspecified input. This makes "scope branching workflows out of the thesis, as
a documented FLOW-BENCH limitation" the evidence-backed choice, not "fix the gate" — there is
nothing in the input for a fixed gate to resolve.

## Owner decisions this pass could settle vs. could not

**Settled by this pass:**
- Gateway hard-fail is a genuine corpus limitation (FLOW-BENCH's BPMN lacks decision logic), not a
  gate bug — supports scoping branching out rather than "fixing" the gate.

**Still genuinely the owner's call, now with better evidence:**
- `FAIL_ALIGNMENT_UNPROVEN` as acceptable ingestion input (F1/D1 §5) — unaffected by this session.
- Lifecycle-AP representation, Option A vs B (D1 §3) — unaffected; Option B remains the
  Milestone-1-appropriate pick regardless of channel 2.
- Task-coverage tier (F4/D1 §6) — unaffected; still needed for the omission-blindness gap
  independent of channel 2.
- **New:** whether to prioritize instrumenting channel 2 before or alongside D2's lifting-scope
  work — given both are needed before any real detection number exists, and channel 2 is
  encountered first regardless of lifting scheme.

## Local build recipe (now twice-proven; worth writing up)

Homebrew SPOT 2.15.1 + pkg-config + cmake + nlohmann-json + a Python 3.9 venv with pybind11 3.0.4;
`libspot.pc` lives at `/opt/homebrew/lib/pkgconfig` (needs `PKG_CONFIG_PATH` set, it is not on the
default search path). `cmake -S . -B build -Dpybind11_DIR=<venv>/lib/python3.9/site-packages/pybind11/share/cmake/pybind11 -DPYTHON_EXECUTABLE=<venv>/bin/python3 -DCMAKE_CXX_FLAGS="-I/opt/homebrew/include"`,
then `cmake --build build`. Run with `DYLD_LIBRARY_PATH=/opt/homebrew/lib`. Tier-3 semantic
matching (`nlp_utils.py`, sentence-transformers/torch) is not installed in this environment — tier
1/2 (exact + Levenshtein) still run for real; tier-3 fallback silently degrades to `unlabeled_task`
and prints `NLP Matching Error` to stderr. This did not affect the channel-2 finding (which fires
identically regardless of which tier resolved the label), but would affect any future real-build
detection-rate measurement once channel 2 is fixed — worth installing before that measurement is
taken seriously. This recipe has now worked twice; still no `BUILDING.md`.
