# Module 01 Thesis Chapter — Outline, Narrative Decisions, and Master Numbers Table

> Working scaffold for the Module 01 chapter, drafted as **Chapter 4** with section numbers 4.x
> (Module 02's own scaffold notes that "Module 01's docs map to Chapter 4" and drafts itself as
> Chapter 5; renumber trivially at assembly time). Draft prose lives in
> `module01_chapter_draft.md`.
>
> **Provenance of this scaffold.** Every figure below is traced to a file in this repository or its
> vault. No number in this document was computed, estimated, or reconstructed from memory while
> writing it. Where a figure exists in two versions, both appear and the superseded one is labeled.
> Where a claim I wanted to make has no artifact, it is listed in §"Claims flagged as
> unsupported" at the end rather than written into the chapter.

---

## The four narrative decisions (made deliberately, before drafting)

**Decision 1 — This is a corpus-admissibility chapter, not a detection chapter, and it says so in
its first paragraph.**
Module 01 never sees code. "Detection rate" is not a property it can have: there is no code-side
signal for it to be right or wrong about. Its evaluable capability is *admissibility and
checkability* — what fraction of a benchmark it can produce a property suite for at all, and what
fraction of what it produces can ever be evaluated against an implementation. Both are fully
measured (F1, F3, F2 below). The chapter opens by refusing the detection framing explicitly, so a
reader arriving from Chapter 5 (Module 02's 0.9952 detection figure) does not read the absence of a
comparable headline number as a gap in the work.

**Decision 2 — Lead with the negative result: the bottleneck is upstream of synthesis.**
The intuitive story is "the synthesizer emits properties; some are good, some are not." The measured
story is stronger and inverted: **synthesis is not where the corpus is lost.** 19 of 48 FLOW-BENCH
specs never reach synthesis at all (Phase-3 gate, exactly the `<exclusiveGateway>`-bearing set), 0
of 48 ever reach `PASS`, and of the 412 properties the 29 survivors do synthesize, 45 — 17.6% of the
P1 tier — are checkable against code. The chapter's spine is that funnel, costed at each stage, with
the argument that the largest single loss (the gateway gate) is a **corpus** limitation rather than a
gate defect — a claim that is not asserted but *measured*: 0 of 20 splitting exclusive gateways in
FLOW-BENCH declare a default flow or any condition expression.

**Decision 3 — Separate "the gate rejected it" from "the checker could not decide."**
This distinction is load-bearing in three places and the chapter maintains it in prose everywhere:
a spec that hard-fails Phase 3 (19/48), a property excluded by an ingestion policy decision
(P0/P2/P3, and the 211 `node()`-bearing P1 properties), and a property that reached the model
checker and returned `INCONCLUSIVE` are three different outcomes with three different meanings. The
design doc that specified the ingestion gate makes the same point in the same terms and is cited for
it (D1 §5: "out-of-scope must be a distinct outcome from INCONCLUSIVE").

**Decision 4 — Measured vs. designed is labeled inline, every time.**
Module 01's own history makes this non-optional: parts of the module were implemented, deleted, and
replaced within a day, and a doc tree describing a *planned* SPOT integration outlived the
integration itself. The chapter therefore labels each claim at the point of use — a measurement
taken over the corpus, a fact read from source, or a design proposed in a cited design doc and
**not** implemented (the task-coverage tier of D1 §6 is the main instance).

---

## Chapter structure (with per-section content notes)

### 4.1 Introduction: the spec track's burden of proof — and why this is not a detection chapter
Module 01's position in the dual-track architecture and the *reason* for the separation (Chapter 5's
negative result: a certificate whose oracle derives from the code under test cannot detect semantic
error, measured 0/220). Module 01 exists to supply the independently-derived reference that result
demands. Immediately: what this chapter therefore does and does not measure — admissibility and
checkability, not detection — and why a detection number for Module 01 would be a category error.
Chapter roadmap; forward reference to the contributions list in 4.10.

### 4.2 Background and related work
Keep short; the shared formal background (LTL/LTLf, Büchi automata, translation validation) belongs
to the Module 03 chapter, which needs it in depth. Here: BPMN 2.0 as a specification language and
its formalization literature; LTLf and finite-trace semantics (De Giacomo & Vardi) as the choice of
logic and *why* finite-trace is the right choice for a terminating business process — this sets up
Chapter 6's bridge problem rather than duplicating it; declarative process mining and
trace-alignment as the lineage of the Phase-4 alignment metric; mutation-based self-validation of
specifications as the lineage of Phase 3. Note the architecture pivot honestly here rather than in a
footnote: an earlier design placed SPOT/HOA automata lifting and process-mining alignment in
Phases 4–5; both were deleted and replaced by a pure-Python progression-based synthesis (cite
`Module 01 Knowledge.md`).

### 4.3 Design: BPMN → semantic graph → tiered LTLf → certificate
- **4.3.1 Phase 1, semantic extraction.** BPMN XML → semantic graph; Kripke labeling in three atom
  families, `start(X)` / `done(X)` / `node(X)`; dynamic node set (every element with an `id` minus a
  ~26-tag exclusion list) and the `_recovery_pass()` re-scan; gate: node coverage ≥ 1.0. The three
  atom families are introduced *here* because the `node(...)` family is what §4.5.2 later measures
  as unusable — the reader needs to have met it as a design choice before seeing it costed.
- **4.3.2 Phase 2, LTLf synthesis and the tier structure.** Template instantiation per construct;
  the five tiers actually emitted (`P0_Critical_Sentinels`, `P1_Structural_Control_Flow`,
  `P2_Quality_Limits`, `P3_Adversarial_Defenses`, `synthesized_mutant_killers`) against the three
  the export's own `tier_semantics` describes; implicit-else resolution; gate: guard-resolution
  coverage ≥ 1.0, else `VerificationException`. The P1 precedence shape `!start(B) W done(A)` is
  introduced here as the tier's flagship, since §4.6 measures what it cannot see.
- **4.3.3 Phase 3, mutation self-validation.** Five mutation operators; bounded iterative DFS trace
  generation (cap 100); multi-round self-healing (`max_rounds=3`) with killer enrichment;
  adversarial red-teaming in round 0 (simulated heuristics, not an LLM — label this as designed
  behavior with a known limitation). Gates: C_struct ≥ 1.0 **and** kill ratio δ ≥ 1.0. This is the
  gate that rejects 19 of 48 specs, so the section ends by naming it as the subject of §4.4.1.
- **4.3.4 Phase 4, PBCTS and bidirectional alignment.** Progression-Based Constructive Trace
  Synthesis: pure-Python LTLf progression replacing automata construction; conjoined suite,
  obligation pruning, memoized branching, `bound_k`, max 200 traces; SCov scoring
  (0.4·node + 0.4·branch + 0.2·depth); bidirectional alignment to EAS_BDA; gate: IDCD convergence
  (|ΔEAS| < 0.001 for some k ≤ 20); SCSL over-specification corrections. State plainly that the
  documented targets EAS ≥ 0.90 / SCov ≥ 0.85 are **not enforced in code** — IDCD convergence is
  the only Phase-4 gate — because §4.4.2's "never PASS" result is a direct consequence of that gate
  and of nothing else.
- **4.3.5 The export contract.** `export_for_module_03()` → `module_03_input.json`:
  `ltlf_property_suite`, `tier_semantics`, `semantic_graph`, `loop_bound_documented`. LTLf as
  *strings*, not automata — the deliberate choice that hands the finite-vs-infinite semantic problem
  to Module 03 and becomes Chapter 6 §6.4. The dual-track constraint that shapes this interface:
  Module 03 consumes this JSON and never Module 01's source (it deploys as its own container that
  does not contain it).

### 4.4 The central result: the corpus is lost upstream of synthesis
- **4.4.1 The gateway gate.** The 48/19/29/0 admission table; set equality between the hard-failing
  set and the `<exclusiveGateway>`-bearing set (tested true, then independently re-derived with
  identical tallies and identical uid list); the representative failure message (uid 12: two
  unconditioned branches without a default flow); zero `parallelGateway` anywhere in the corpus.
  Include the phase-attribution correction as a correction-trail entry, not a silent fix: the
  original finding attributed the raise to "Phase 3"; tracing the exception handling shows it is
  raised inside the synthesizer's own certification step and reported by the API as `"phase": 2`.
  Counts, message text and set equality were unaffected.
- **4.4.2 Module 01 never reports PASS on FLOW-BENCH.** All 29 survivors export under
  `FAIL_ALIGNMENT_UNPROVEN` (the name at the time of measurement; the status has since been renamed
  — see the correction-trail note in 4.4.4), which derives from PBCTS non-convergence and not from
  property validity. Whether a non-converged suite is legitimate input to a conformance check was
  explicitly left as an owner decision by the design round (D1 §5), and the recommendation was
  accept-and-record-on-every-row. Report what was decided in implementation: the downstream
  evaluation *does* consume these suites, so every conformance number in Chapter 6 rests on suites
  whose own producer could not prove alignment. That sentence belongs in Chapter 6 too, and appears
  in both.
- **4.4.3 The gate is correct and the corpus is underspecified.** The strongest single
  admissibility result: all 20 splitting exclusive gateways across the 19 gateway-bearing specs
  lack both a `default` attribute and any `conditionExpression` on any outgoing flow. The BPMN files
  contain no decision logic for these gateways at all. This converts "fix the gate vs. scope
  branching out" from an open question into an evidence-backed choice, and it is the difference
  between reporting a 40% admission rate as a tool limitation and reporting it as a benchmark
  limitation.
- **4.4.4 Correction trail for this section.** Two entries: the phase attribution above, and the
  status-code rename (the unconverged status was reported inconsistently between the library and the
  service layer; both now report a single unified code, pinned by a dedicated test). Both are
  cosmetic to the *counts* and load-bearing to *citations* — a reader grepping for the old status
  name in current source will not find it.

### 4.5 Checkability: what fraction of a synthesized suite can ever be checked
- **4.5.1 The tier census.** 412 properties over the 29 exporting specs: P0 79, P1 256, P2 29,
  P3 48, `synthesized_mutant_killers` 0. Two structural defects visible in the census itself:
  `tier_semantics` describes three of the five tiers shipped, and 34 of the 412 properties are exact
  duplicates within their own tier. Both matter downstream — the first hard-errored the ingestion
  layer on real specs until fixed (cite the regression test by name), the second inflates any
  per-property denominator and is de-duplicated before metrics.
- **4.5.2 The `node()` family is unusable against code.** 211 of 256 P1 properties (82.4%)
  reference `node(Start)`, `node(End)` or `node(Decision:…)` — BPMN control-flow structure with no
  code-side counterpart. 45 remain: pure task-precedence formulas, present in 22 of 29 specs,
  median 2 per spec. **45/256 = 17.6% is the chapter's headline checkability figure** and it is a
  property of the synthesizer's own output, measured before any code is involved.
- **4.5.3 P0, P2, P3 and the empty tier.** P0 excluded by construction and *provably* so: the
  self-sentinel shape is unfalsifiable under any faithful lifting, not merely under one candidate
  lifting — the proof, and its confirmation by two independent evaluators with different trace
  semantics, is Module 03's to present in detail (Chapter 6 §6.6), but the *consequence* for this
  chapter is that 79 of 412 properties are a lifting self-test rather than evidence about code, and
  reporting them as passed safety properties would reproduce Chapter 5's self-referential-validation
  failure at this seam. P2: all 29 instances are the single template
  `G(iteration_count <= 10 -> F(process_complete))`, whose `<=` is not parseable as a propositional
  atom and whose two identifiers have no code-side counterpart. P3: all 48 use `X`, precisely where
  finite- and infinite-trace semantics diverge. `synthesized_mutant_killers`: 0 properties across
  all 29 specs.
- **4.5.4 The atom vocabularies are disjoint by construction.** 0 of 116 spec-side P1 atoms can
  match a code-side atomic proposition; 0 of 29 pairs overlap at all. This is a lifecycle-prefix
  mismatch (`done_T` vs. `T`), not a naming-quality problem — and the evidence for that reading is
  that the *identifier* matching is good: spec task name to Python function name is 86.0% exact on
  mean across 43 pairs, with 26 of 43 at 100%. Report the reproduction status honestly: the prefix
  mismatch is source-verified from both code paths; the specific 0/116 count was measured against a
  Python emulation of the lifter's atom construction (the compiled engine did not exist in that
  environment), and was later confirmed on a real compiled build as 58 of 58 checks returning
  `INCONCLUSIVE` when unstripped atoms reach the checker.
- **4.5.5 The funnel.** One figure, one table: 48 specs → 29 export → 22 carry ≥1 checkable
  property → (Chapter 6) 6 usable as gold for end-to-end evaluation. Each arrow labeled with its
  cause and its source file. This figure is the chapter.

### 4.6 Structural blindness: omission dominance and the coverage tier that does not exist
The corpus's dominant divergence mode and the property shape's blindness to it. Divergence
classification over all 43 (spec, variant) pairs: omission-only 23, exact conformant 15,
omission + reordering 3, reordering-only 2. The five-row vacuous-truth table for
`!start(B) W done(A)`: correct order `True`, reversed `False` (detected), **A only with B omitted
`True` (not detected)**, B only `False`, neither `False`. Omitting the *later* task of a precedence
pair satisfies the property vacuously, so the tier the design calls "the real conformance checks"
cannot see the majority failure mode in this corpus — confirmed directly: 7 divergent pairs produce
no failing `node()`-free P1 property at all, with two named examples. Report the reproduction
spread honestly (the independent re-derivation used cruder substring name-matching and got
24 omission-only / 3 reordering-only over the same N=43 — same dominance pattern, different exact
split, and the two specific files cited as blind reappear independently). Then the gap: no tier
fills it, because the only `F`-bearing tiers are P2 (unusable) and P3 (excluded). A task-coverage
property family — one "task T eventually completes" obligation per spec task — was **designed**
(D1 §6, with its own reachability trace on a named variant and its own honest caveat that the
obligation is `F`-bearing and therefore needs the very bridge that design scoped out) and is
**not implemented**. Label it as designed-not-built, name it as future work, and do not estimate
what it would recover.

### 4.7 What serves as Module 01's own validation
Three things, none of them a detection rate, each cited:
(i) **Oracle self-consistency** — evaluating each spec's own task order against its own property
suite gives 45/45 satisfied. This is the guard that catches a synthesizer emitting
self-contradictory properties, and it is what makes any downstream `False` verdict attributable to
the code rather than to the property.
(ii) **Phase 3's own mutation self-validation** — the module's internal kill-ratio gate, which is a
*designed* mechanism whose corpus-scale behavior is reported only through its pass/fail outcome
(the 19/48 hard-fail); there is no artifact measuring kill-ratio distributions across the corpus,
and the chapter says so rather than implying one.
(iii) **The test suite** — 28 tests across 6 files, covering the Phase-1 and Phase-3 gates, PBCTS
convergence, SCSL, status-code consistency, the Module 03 export, and the HTTP API, all passing.
State the history plainly: this module had zero tests at the time the design round measured it, and
`main.py` could not start because it imported a module that had been deleted. Both are fixed, and
the fix is protected by a startup check in CI. A chapter that omitted the "zero tests" starting
point would be describing a different project.

### 4.8 Implementation notes (short, selective)
~2,260 LOC across 11 source files, FastAPI service; SPOT dropped from the Dockerfile entirely once
the pure-Python Phase 4 landed (the image is a 19-line slim build, dependencies fastapi / uvicorn /
networkx). The dead `FormulaNormalizer` — a normalizer for exactly the atom syntax Module 03 needs,
with zero callers — and why Module 03 ported its own instead of importing it (container boundary,
dual-track independence). One cross-module bug found and fixed at the export seam while building the
end-to-end demo: `tier_semantics` covering three of five tiers hard-errored the consumer on real
specs; fixed with a regression test that ingests a real export.

### 4.9 Limitations
Each costed with its measured value in the same sentence. (1) *Branching workflows are entirely
out of scope*: 19/48 specs, and with them the whole branching-conformance story — with the
mitigating measurement that the corpus supplies no decision logic for those gateways (0/20), so the
scope limit is jointly owned by the tool and the benchmark. (2) *No spec reaches PASS*: 0/48, and
every downstream number rests on non-converged suites. (3) *Checkability*: 17.6% of the P1 tier,
0% of P2, 0% of P3, P0 excluded by construction — i.e. 45 of 412 synthesized properties are
conformance-bearing. (4) *Omission blindness*: 23/43 pairs, structurally invisible to the shipped
property shapes; the coverage tier that would address it is designed and unbuilt. (5) *Atom
vocabulary*: disjoint by construction, reconciled downstream by a lossy prefix collapse whose
losslessness holds only for sequential workflows — true for this corpus (zero parallel gateways),
false in general. (6) *Adversarial generation is simulated heuristics, not a model.* (7) *Documented
Phase-4 targets are unenforced*: EAS ≥ 0.90 / SCov ≥ 0.85 appear in documentation and not in the
gate. (8) *Corpus scope*: one benchmark, 48 specs, enterprise-workflow shape; generalization
untested and not claimed.

### 4.10 Summary of contributions
(1) A tiered, finite-trace property synthesis pipeline from BPMN with per-phase quality gates and a
constructive trace certificate produced without an automata toolchain. (2) **A checkability metric
and its measurement** — the observation that a specification synthesizer must be evaluated on what
fraction of its output is *evaluable against an implementation*, not on how much it emits, together
with the corpus measurement that makes the metric bite (45/256). (3) **An admissibility result that
localizes a benchmark limitation**: the entire branching gap traced to one gate, and the gate
vindicated by showing the corpus contains no decision logic for it. (4) The negative structural
result that a specification's own self-sentinel tier cannot serve as evidence about code under any
faithful lifting — the same failure mode as Chapter 5's central result, arrived at from the spec
side. (5) An honest interface contract: LTLf strings plus tier semantics, with the finite-trace
obligation handed to the consumer explicitly rather than silently.

---

## Master numbers table (every figure with its source; use ONLY these)

Sources are repo-relative. `00` = `vibecheck-vault/Module 03 - Equivalence Engine/Bridge
Investigation/E2E Session/00 - Session Findings and Plan Impact.md`; `VER` =
`vibecheck-vault/Module 03 - Equivalence Engine/Bridge Investigation/E2E Integration Verification
Findings.md`; `M01K` = `vibecheck-vault/Module 01 - Specification Analysis/Module 01 Knowledge.md`.

| Figure | Value | Source |
|---|---|---|
| Corpus size | 48 BPMN specs | `flow-bench/data/context/`; `00` §F1 |
| Pipeline admission | 19 `FAIL`, 29 export, **0 `PASS`** | `00` §F1 (VERIFIED-EXPERIMENT) |
| Hard-fail set identity | == the `<exclusiveGateway>`-bearing set (set equality tested true) | `00` §F1; independently re-derived, identical tallies + uid list, `VER` reproduction table row F1 |
| Representative failure message | uid 12: `XOR Gateway 'exclusiveGateway_4' has 2 unconditioned branch(es) without a default flow.` | `00` §F1 |
| Parallel gateways in corpus | 0 | `00` §F1 |
| Phase attributed to the raise | reported as `"phase": 2` (not Phase 3, as first stated) | `VER` §"What reproduced cleanly", correction paragraph |
| Splitting exclusive gateways | 20, across the 19 gateway-bearing specs | `VER` §"Gateway default-flow question — resolved" |
| Gateways with a `default` attribute | **0 / 20** | same |
| Gateways with any `conditionExpression` on an outgoing flow | **0 / 20** | same |
| Export status on all survivors | non-converged (`FAIL_ALIGNMENT_UNPROVEN` at measurement time; renamed to `PASS_PBCTS_UNCONVERGED`) | `00` §F1; rename per `M01K` status list + `module_01_spec/tests/test_status_code_consistency.py` |
| Total properties synthesized | 412 over 29 specs | `00` §F3 |
| Tier census | P0 79 · P1 256 · P2 29 · P3 48 · killers 0 | `00` §F3 |
| P1 referencing `node(...)` | 211 / 256 = **82.4%** | `00` §F3 |
| P1 checkable against code | **45 / 256 = 17.6%**, in 22/29 specs, median 2 per spec | `00` §F3; restated in `module_03_equiv/src/property_ingest.py` module docstring |
| P2 template | all 29 = `G(iteration_count <= 10 -> F(process_complete))` | `00` §F3 |
| P3 operator use | all 48 use `X` | `D1 - M01 to M03 Integration Design.md` §4 table |
| Intra-tier exact duplicates | 34 / 412 | `00` §F3; `property_ingest.py` docstring |
| `tier_semantics` coverage | describes 3 of the 5 tiers shipped | `D1` §1 |
| Spec-atom / code-atom overlap | **0 of 116** spec P1 atoms; 0/29 pairs overlap | `00` §F2 (emulated lifter AP set; prefix mismatch itself VERIFIED-SOURCE) |
| Real-build confirmation of the above | 58/58 checks `INCONCLUSIVE` with unstripped atoms | `VER` reproduction table row F2 |
| Task-name identifier match | 86.0% mean over 43 pairs; 26/43 at 100% | `00` §F2 |
| Divergence-mode census | omission-only 23 · conformant 15 · omission+reorder 3 · reorder-only 2 (N=43) | `00` §F4 |
| Independent re-derivation of the above | 24 omission-only / 3 reorder-only, same N=43 (cruder name matching) | `VER` reproduction table row F4 |
| Vacuous-truth table for `!start(B) W done(A)` | 5 rows; A-only-B-omitted = `True` (undetected) | `00` §F4; reproduced identically in `VER` |
| Divergent pairs with no failing checkable P1 property | 7 | `00` §F4 |
| Named P1-blind examples | `82__llama-3.1-8b.py` (1 of 5 spec tasks called), `77__llama-3.1-8b.py` (2 of 3) | `00` §F4; both independently reappear in `VER`'s own list |
| Oracle self-consistency | **45 / 45** spec-order traces satisfy their own suite | `D3 - FLOW-BENCH E2E Evaluation Harness Design.md` §3.2(d); same figure in `D2` §5 |
| Finite-trace cross-check scale | 1,979 real traces | `vibecheck-vault/Module 03 - Equivalence Engine/Bridge Investigation/AP Vocabulary and Lifting Scope Findings.md` |
| Module 01 tests | 28 across 6 files, all passing | `M01K`; `module_01_spec/tests/` |
| Module size | ~2,260 LOC across 11 source files | `M01K` |
| Export-seam bug | `tier_semantics` 3-of-5 hard-errored ingestion on real specs; fixed + regression test `test_real_export_is_ingestible_by_module_03` | `M01K` |

**Designed-but-not-implemented (cite as design, never as capability)**

| Item | Where designed | Status |
|---|---|---|
| Task-coverage (`F done_T`) property family | `D1` §6, with reachability trace on `82__llama-3.1-8b.py` | **Not implemented.** Named as future work in §4.6 |
| Lifecycle-event atoms on the code side ("Option A") | `D1` §3 | Not implemented; the lossy prefix collapse ("Option B") shipped instead |
| P2 redesign into a checkable loop-bound property | `D1` §4 | Not implemented; loop-bound checking currently has no home in the canonical Phase-D path |

**Figures/tables to produce**

- **F4.1** The admissibility/checkability funnel: 48 specs → 29 export → 22 with ≥1 checkable
  property → 45 checkable properties → 6 gold specs (the last arrow forward-referencing Chapter 6).
  Each arrow annotated with cause and source file. This is the chapter's centerpiece figure.
- **F4.2** Four-phase pipeline diagram with the gate condition on each phase boundary and the
  measured pass count at each gate.
- **F4.3** Tier census stacked bar (412 properties), segmented by disposition: checkable (45),
  `node()`-bearing (211), P0 self-test (79), P2 unparseable (29), P3 unbridged (48), duplicates
  overlaid (34).
- **T4.1** Admission table: outcome × construct present (the 19/29/0 cross-tabulation, with the
  set-equality result stated).
- **T4.2** The vacuous-truth table for the P1 precedence shape (5 rows, verbatim).
- **T4.3** Correction trail: what was stated / how it was caught / corrected value / where the
  superseded version lives. Entries: phase attribution (3→2), status-code rename, and the
  supersession of the emulated 0/116 by the real-build 58/58 confirmation.

---

## Claims flagged as unsupported (no citable artifact — do not write these into the chapter)

1. **Kill-ratio and C_struct distributions across the corpus.** Phase 3's gate outcome is measured
   (19 hard-fail), but no artifact reports the distribution of kill ratios or structural-coverage
   scores over the 48 specs. §4.7(ii) says this explicitly instead of implying a measurement.
2. **What the designed task-coverage tier would recover.** D1 §6 argues it "converts 23/43 corpus
   pairs from invisible to detectable" as a *design* claim with a reachability trace on one named
   variant. No implementation exists, so no measured recovery figure exists. The chapter reports the
   design argument as a design argument and does not carry the 23/43 figure across into a
   capability claim.
3. **Per-spec synthesis latency / runtime.** No timing artifact for Module 01 exists.
4. **Whether the checkability rate generalizes beyond FLOW-BENCH.** Untested; the corpus-scope
   limitation (§4.9(8)) states it as untested rather than estimating.
5. **PBCTS convergence behavior itself** — why 0/48 converge. The gate outcome is measured; a
   diagnosis of the non-convergence (which of `bound_k`, suite conjunction size, or the |ΔEAS|
   threshold is binding) has no artifact. §4.4.2 reports the outcome and names the diagnosis as
   open.
