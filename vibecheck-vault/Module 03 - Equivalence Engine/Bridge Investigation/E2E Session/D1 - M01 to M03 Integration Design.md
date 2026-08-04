# D1 — M01 → M03 Integration Design

> Repo at `main @ 0daf57e`. Read `00 - Session Findings and Plan Impact.md` first — findings F1,
> F2, F3 and F4 are load-bearing here. No implementation code below by design; signatures are
> given as contracts to implement against.

## 1. What exists at each end

**Producer side (VERIFIED-SOURCE).** `export_for_module_03()` in `module_01_spec/src/api.py`
(called at `api.py:220`) writes a JSON payload. Its keys, observed by running it on all 48
FLOW-BENCH specs (VERIFIED-EXPERIMENT): `ltlf_property_suite`, `tier_semantics`,
`semantic_graph`, `loop_bound_documented`.

`ltlf_property_suite` has **five** keys, not three: `P0_Critical_Sentinels`,
`P1_Structural_Control_Flow`, `P2_Quality_Limits`, `P3_Adversarial_Defenses`,
`synthesized_mutant_killers`. `tier_semantics` describes only the first three
(VERIFIED-EXPERIMENT). Any consumer that gates on `tier_semantics` will encounter tiers it has
no policy for — this must be an explicit error, not a silent skip, or P3 properties would
disappear without trace.

**Consumer side (VERIFIED-SOURCE).** The only call site is in `process_wir_batch()`,
`module_03_equiv/src/pipeline.py`, which calls `_cpp.check_compliance(rep, ltl_property)` per
cluster representative and stores `verdict`, `counter_example_trace`, `unmatched_atoms`.
`ltl_property` is a single string parameter defaulting to the placeholder. `check_compliance()`
is declared in `module_03_equiv/src/lifter.hpp:~276` and defined at `lifter.cpp:1066`.

So the shape mismatch is: **producer emits a tiered dict of many formulas; consumer accepts one
string.** That, plus format/semantics, is the whole of the integration.

## 2. Proposed data flow

Keep the dual-track separation intact: the ingestion layer must read *only* Module 01's exported
JSON and *only* Module 02's WIR, never the BPMN XML or the Python source. Placing the adapter in
Module 03 satisfies this — it is the designated convergence point.

```
module_01_spec/  ──(module_03_input.json)──┐
                                           ├──> [NEW] property_ingest.py ──> PropertySuite
module_02_extract/ ──(WIR json)────────────┘                                     │
                                                                                  v
                              pipeline.process_wir_batch(wir_strings, suite: PropertySuite)
                                                                                  │
                                                             per cluster rep, per property
                                                                                  v
                                                        _cpp.check_compliance(rep, formula)
```

### New module: `module_03_equiv/src/property_ingest.py`

Pure Python, no C++ dependency, so it is testable without the toolchain (relevant given F6).
Contract:

- `load_property_suite(path: str) -> PropertySuite` — parse and validate the exported JSON.
- `PropertySuite.conformance_properties() -> list[Property]` — the tier-gated, normalized,
  de-duplicated list actually handed to Phase D.
- `Property` carries at minimum: `formula` (the string passed to `check_compliance`), `tier`,
  `source_tier_role`, `atoms` (parsed set), `spec_uid`, and `origin_formula` (the pre-normalized
  LTLf string, so a counterexample can be reported against what Module 01 actually said).

### Changed function signature

`process_wir_batch()` gains a suite parameter and returns per-property verdicts. Contract:
it must accept a `PropertySuite` (not a bare string), iterate properties per cluster
representative, and record for each: `verdict`, `unmatched_atoms`, `counter_example_trace`,
plus the `tier` and `spec_uid`. Keeping the old single-string path as a deprecated default is
worth doing only if `tests/test_pipeline.py` depends on it — it has 37 ungated tests
(VERIFIED-SOURCE) and is the one suite that runs without the C++ build, so preserving it is cheap
insurance.

## 3. The atom-vocabulary decision — must be resolved in this milestone (F2)

This is the blocking design decision, and it is **the owner's to make**. Finding F2 measured that
0 of 116 spec P1 atoms can match the code automaton's AP set, because Module 01 emits
`start_T`/`done_T` and `semantic_match()` (`lifter.cpp:135`) returns the bare task name `T`
(VERIFIED-SOURCE: `return task;`). Every property will return `INCONCLUSIVE` until this is fixed.

**Option A — code side gains lifecycle events.** The lifter emits two transitions per action:
one labelled `start_T`, one labelled `done_T`.

- Preserves the meaning of Module 01's formulas exactly as synthesized; no spec-side change.
- **Doubles the transition count of every lifted automaton.** This invalidates the hardcoded
  geometry assertions: 7 in `test_cpp_engine.py`, 15 in `test_phase_b.py`, 3 in `test_phase_c.py`,
  3 in `test_pipeline.py` (VERIFIED-SOURCE, counts of `num_states()`/`num_edges()` occurrences).
- It also **permanently neuters the P0 tier**, but P0 is already excluded from conformance
  (prompt fact 2), and the vault's Session-3 finding proved P0's self-sentinel is unfalsifiable
  under *any* faithful lifting — so this costs nothing that was not already lost.

**Option B — spec side strips lifecycle prefixes.** Ingestion rewrites `start_T` and `done_T` to
a single atom `T`.

- Zero change to `lifter.cpp`, zero geometry churn.
- **Semantically lossy in a way that matters.** `!start(B) W done(A)` becomes `!B W A`, which no
  longer distinguishes "B may not begin before A finishes" from "B may not begin before A begins".
  For sequential workflows those coincide; for any future overlap/parallel semantics they do not.
- **REASONED** (chain: collapsing both lifecycle atoms to one identifier makes `done_A` and
  `start_A` indistinguishable → a formula relating A's completion to B's start becomes a formula
  relating A's occurrence to B's occurrence): this is a correct-today, wrong-later choice. It is
  the right pick *if and only if* parallel gateways stay out of scope — and FLOW-BENCH contains
  zero `parallelGateway` elements (VERIFIED-EXPERIMENT), so "today" covers the whole thesis
  corpus.

**Recommendation, with the trade stated:** take **Option B for Milestone 1** (it unblocks a real
first run with no C++ change, which is the walking-skeleton principle), and treat Option A as
part of the lifting-scope work in D2 where the geometry assertions are being touched anyway. This
sequencing means the geometry churn is paid once, not twice.

**Counterexample check on my own recommendation, as required.** Claim: Option B lets a real
ordering violation be detected. Trace, on `44__llama-3.1-8b.py` (VERIFIED-EXPERIMENT): spec order
is SalesOrder → PriceLevel → Invoice → Slack; the code's call order is Invoice → Slack →
PriceLevel → SalesOrder. Property `!start(PriceLevel) W done(SalesOrder)` under Option B becomes
`!PriceLevel W SalesOrder`; on the collapsed call-order trace `[Invoice, Slack, PriceLevel,
SalesOrder]`, `PriceLevel` occurs at index 2 before `SalesOrder` at index 3, so the formula is
violated and a counterexample trace exists. Detection is reachable from the actual construction,
not just the mental model. **However** — the same check on an *omission* case fails: see F4 and
§6 below. Option B does not rescue omission blindness and I am not claiming it does.

## 4. LTLf → LTL: what actually needs bridging, and what does not

The prompt asks whether this design needs an LTLf→LTL bridge. Answering from the observed formula
shapes (VERIFIED-EXPERIMENT, all 412 exported properties):

| Tier | Operators used | Bridge needed? |
|---|---|---|
| P1 (45 node()-free) | `!`, `W` only — **no `X`, no `F`, no `G`** | **No** |
| P0 | `!`, `W` | excluded by design |
| P2 | `G`, `F`, `->`, and `<=` over `iteration_count` | **not bridgeable — see below** |
| P3 | `!`, `F`, `&`, `X` (all 48 use `X`) | **Yes — `X` is where the semantics diverge** |

- **P1 needs no bridge.** `W` (weak until) has the same meaning on finite and infinite traces for
  the safety patterns Module 01 emits, and SPOT's infix parser accepts `W`. **REASONED**: the
  finite/infinite divergence in LTLf vs LTL is concentrated in `X` at the trace end (LTLf's
  `X φ` is false at the last position — VERIFIED-SOURCE, `ltlf_eval.py:167-169`:
  `if i + 1 < N: ... return False`) and in the interaction of `G`/`F` with trace termination.
  A formula built only from `!` and `W` over a stutter-extended trace has no end-of-trace
  sensitivity to disagree about. **Since P1 is the only conformance tier in Milestone 1, the
  bridge is genuinely out of scope for the walking skeleton** — which is the answer the prompt
  was fishing for, and it holds for a checkable reason rather than by fiat.
- **P2 cannot be bridged, it must be redesigned or dropped.** All 29 P2 properties are the single
  template `G(iteration_count <= 10 -> F(process_complete))` (VERIFIED-EXPERIMENT). `<=` is a
  numeric comparison; SPOT's LTL parser expects propositional atoms. And `iteration_count` /
  `process_complete` have no code-side counterpart, so even if parsed they would be unmatched
  atoms → `INCONCLUSIVE` forever. Recommendation: **exclude P2 from the conformance gate and say
  so explicitly in the results table** rather than reporting 29 INCONCLUSIVEs as if they were
  measurements. Re-designing P2 into a checkable loop-bound property is a separate work item
  (it needs a code-side loop-iteration atom, which the WIR does support via `loop` nodes —
  69 sub-CFG loop nodes exist corpus-wide, VERIFIED-EXPERIMENT).
- **P3 does need the bridge, and is undescribed.** All 48 P3 formulas use `X`, which is precisely
  where LTLf and LTL differ, and P3 is absent from `tier_semantics` so no role/gating policy
  exists for it. Recommendation: **exclude P3 from Milestone 1** and file the bridge as its own
  design task. Including it silently would be the one place this integration could produce a
  confidently wrong verdict.

**Normalization.** `FormulaNormalizer` (`module_01_spec/src/formula_normalizer.py:4`) already
converts `start(T)`/`done(T)`/`node(N)` into flat identifiers, and **has zero callers**
(VERIFIED-SOURCE). The ingestion layer should call it rather than reimplement it — but note it
does *not* validate: on P2 input it returns the string unchanged including `<=`
(VERIFIED-EXPERIMENT). So ingestion needs a validation step *after* normalization that rejects any
formula containing characters outside the atom/operator grammar, and records the rejection in the
report rather than dropping it.

## 5. Tier gating policy

Given the above, the gate for Milestone 1:

| Tier | Feeds conformance check? | Reason |
|---|---|---|
| P0 | No | `role = "lifting_self_test"`, `conformance_check = False` (prompt fact 2); route to a separate self-test report |
| P1, `node()`-free | **Yes** | the 45 checkable precedence properties (F3) |
| P1, `node()`-bearing | No | 211 properties over `node(Start)`/`node(End)`/`node(Decision…)` with no code counterpart (F3); report as *out-of-scope*, not as INCONCLUSIVE |
| P2 | No | unparseable + unmatchable (§4) |
| P3 | No | needs the LTLf→LTL `X` bridge (§4) |
| `synthesized_mutant_killers` | No (empty) | 0 properties across all 29 specs (VERIFIED-EXPERIMENT) |

Two design rules follow. First, **the gate keys on `tier_semantics.conformance_check` where the
field exists, and hard-errors on a tier absent from `tier_semantics`** — otherwise P3 and
`synthesized_mutant_killers` vanish silently. Second, **out-of-scope must be a distinct outcome
from INCONCLUSIVE** in the report. Conflating "we chose not to check this" with "the checker
could not decide" would make the results table uninterpretable, and 211 + 29 + 48 = 288 of 412
properties are in that category.

**Owner decision (F1):** all 29 eligible specs carry `FAIL_ALIGNMENT_UNPROVEN`
(`api.py:88-92`). Should ingestion accept a suite whose own producer could not prove alignment?
Accepting it is defensible — the properties are individually well-formed and the flag concerns
PBCTS convergence, not property validity — but it must be *recorded on every result row*, because
a reviewer will ask. Rejecting it reduces the eligible corpus to zero and makes PBCTS convergence
the blocking task. I recommend accepting-and-recording; the decision is yours.

## 6. The task-coverage gap (F4) — a Module 01 change this integration depends on

Finding F4 measured that 23 of 43 corpus pairs diverge by *omitting* a spec task, and that the
P1 precedence shape `!start(B) W done(A)` is satisfied vacuously when B is omitted
(VERIFIED-EXPERIMENT, truth table in F4). 7 divergent pairs produce no P1 violation at all.

No tier fills this gap: the only `F`-bearing tiers are P2 (unusable) and P3 (excluded)
(VERIFIED-EXPERIMENT).

**Design ask:** Module 01's `FLTLSynthesizer` (`module_01_spec/src/ltlf_synthesizer.py:8`) gains a
coverage family — one obligation per task node in the semantic graph, of the shape "task T
eventually completes". On the spec's own task sequence this is trivially satisfied (control check:
the spec-order trace satisfies 45/45 existing P1 properties, VERIFIED-EXPERIMENT, so the oracle
is not self-inconsistent); on an omitting implementation it fails and yields a counterexample
naming the missing task.

**Counterexample check, as required.** Claim: a coverage obligation detects omission where P1
cannot. Trace on `82__llama-3.1-8b.py` (source read directly, VERIFIED-SOURCE): the spec has 5
tasks; `workflow()` calls exactly one, `Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages`,
which is *not* among the 5 spec tasks. Under call-order lifting the trace contains no spec task at
all. Every precedence property of the form `!B W A` over absent A and B — `False` when the
antecedent side is examined, but crucially the 4 node()-free P1 properties for uid 82 produce **no
failure** in the measured run (this pair is in the 7-pair miss list, VERIFIED-EXPERIMENT). A
coverage obligation on any one of the 5 tasks fails immediately, with the missing task name as the
witness. So the detection claim is reachable from the real construction.

Caveat I must state: this obligation is **`F`-bearing, so it does require the LTLf→LTL bridge**
that §4 scoped out — on an infinite-trace reading, `F done_T` over a stutter-extended terminal
state is satisfiable in ways it should not be. Either the bridge lands with this tier, or the
coverage check is evaluated by the pure-Python `ModelChecker`
(`module_03_equiv/src/model_checker.py:125`) rather than through SPOT. The second option is
cheaper and keeps Milestone 1 free of the bridge; it does mean the coverage metric and the
precedence metric come from two different engines, which must be disclosed in the results table.

**This is an owner decision** (item 3 in F1's list): it changes Module 01, which has zero tests
today, so it also implies writing the first Module 01 tests.

## 7. Effort

| Item | Files | Notes |
|---|---|---|
| `property_ingest.py` (new) | 1 new | pure Python; testable without C++ build |
| `pipeline.process_wir_batch` signature + per-property loop | 1 changed | keep string path for the 37 ungated tests |
| Wire `FormulaNormalizer` + add post-normalization validation | 1 changed (M01) or call from M03 | it has no callers today |
| Report schema (verdict, tier, out-of-scope vs INCONCLUSIVE) | 1 new | consumed by D3's harness |
| New tests for ingestion + gating | 1 new test file | ungated, runs without toolchain |
| Option B prefix collapse | inside ingestion | no C++ change |

Not included, deliberately: LTLf→LTL bridge, P2 redesign, coverage tier (§6), Option A lifecycle
APs (deferred into D2).
