# Chapter 4 — Module 01: Specification Analysis and the Checkability of Synthesized Properties

> Draft. Chapter number provisional (Module 02 is drafted as Chapter 5, so this is 4.x; renumber at
> assembly). Outline, narrative decisions and the master numbers table live in
> `module01_chapter_outline.md`. Every figure in this chapter is cited to a file; the master table
> maps each to its source. Where a claim is *designed* rather than *measured*, the prose says so at
> the point of use.

---

## 4.1 Introduction: the spec track's burden of proof

Chapter 5 establishes, by measurement rather than by argument, that a certificate derived from the
code it is checking cannot detect that code's logic bugs. The oracle and the artifact under test
diverge together, so the certificate remains confident while the behavior is wrong: 0 detections
across 220 mutants, every operator, on the first properly measured corpus. That result is the reason
this chapter exists. If a code-derived oracle cannot supply the reference against which conformance
is judged, the reference must come from somewhere the code cannot reach — and in VibeCheck it comes
from the specification the code was supposedly generated from, processed by a module that never sees
the code at all.

This chapter describes that module: how it converts a BPMN 2.0 process model into a formal object a
downstream checker can use, what quality gates it enforces on its own output, and — the part that
occupies most of the chapter — what fraction of what it produces is *usable*.

It is worth being explicit at the outset about what this chapter does not contain, because a reader
arriving from Chapter 5 will be looking for it. There is no detection rate for Module 01. There
cannot be one. Detection is a relation between a specification and an implementation, and Module 01
is one half of that relation; asking how often it detects a bug is asking how often a ruler notices
that a plank is too short. The measurable properties of a specification-analysis module are of a
different kind:

- **Admissibility.** Given a corpus of real specifications, for what fraction can the module produce
  a property suite at all, and where exactly does it refuse?
- **Checkability.** Of the properties it does produce, what fraction can *in principle* be evaluated
  against an implementation — independent of whether any particular implementation passes?
- **Self-consistency.** Does the module's own output agree with the specification it came from, so
  that a downstream disagreement can be attributed to the code rather than to a defective property?

All three are measured in this chapter. The headline results are that admissibility on FLOW-BENCH is
29 of 48 specifications, that no specification in the corpus reaches an unqualified `PASS`, and that
of the 412 properties the 29 survivors synthesize, 45 can be checked against code — 17.6% of the
tier that carries the module's conformance-checking intent. Each of those numbers is a limitation.
Presented together with their causes they are also, I will argue, the chapter's contribution: a
specification synthesizer that is evaluated on how much it emits is not being evaluated at all, and
the checkability metric introduced here is what makes the difference visible.

One further framing decision runs through the chapter. Module 01's implementation history includes a
pivot in which an entire pair of phases — a SPOT/HOA automata-lifting stage and a process-mining
alignment stage — was written, and then deleted the following day and replaced with a pure-Python
construction. Documentation describing the deleted design outlived it. In a project whose central
methodological claim is that measurements must be traceable to artifacts, that history cannot be
quietly tidied; it is reported where relevant, and every claim in this chapter is labeled as a
measurement over the corpus, a fact read from current source, or a design proposed in a cited
document and not implemented.

The chapter proceeds as follows. §4.2 places the work in its literature. §4.3 describes the
four-phase pipeline and its export contract. §4.4 presents the admissibility result and the evidence
that its dominant cause is a property of the benchmark rather than of the gate. §4.5 presents the
checkability census. §4.6 presents a structural blindness that no amount of admissibility would fix:
the corpus's dominant divergence mode is invisible to the shape of property the module emits. §4.7
describes what does serve as this module's validation, §4.8 covers implementation, §4.9 states the
limitations with their measured costs, and §4.10 lists the contributions.

---

## 4.2 Background and related work

The formal machinery this chapter shares with Chapter 6 — linear temporal logic, Büchi automata, the
automata-theoretic approach to model checking — is developed there, where it is load-bearing. This
section covers what is specific to the specification side.

**BPMN 2.0 as a specification language.** BPMN is a graphical notation with an XML serialization,
designed for human communication of business processes rather than for formal analysis. Its
executable subset is well defined; its *semantics* in the sense a model checker needs are not
uniformly determined by the notation, and a large literature exists on formalizing BPMN into Petri
nets, process algebras, or temporal logic. The practical consequence for this work is that
translating BPMN to properties requires committing to a semantics for constructs the notation leaves
underdetermined, and — as §4.4.3 shows in detail — real BPMN files in the wild frequently omit the
information that any such commitment would need.

**Finite-trace temporal logic.** The properties this module synthesizes are LTLf — linear temporal
logic interpreted over finite traces (De Giacomo & Vardi). This is a deliberate choice and the right
one for the domain: a business process terminates, and a property asserting that something
*eventually* happens means something different over a trace that ends than over one that runs
forever. The choice has a cost, paid in Chapter 6: the downstream model checker interprets LTL over
infinite traces, so the interface between the two modules carries a genuine semantic conversion
rather than a formatting difference. The conversion is presented in Chapter 6 §6.4; it is mentioned
here because the choice of logic is made in this module and the bill arrives in that one.

**Declarative process mining and trace alignment.** The pipeline's fourth phase scores its
synthesized property suite by generating traces that satisfy it and aligning them against traces of
the source model, producing a bidirectional alignment score. The lineage is the conformance-checking
and trace-alignment literature from process mining, where aligning an observed log against a model is
the standard instrument. An earlier implementation used a process-mining alignment library directly;
the version described here replaces it with a construction over LTLf progression (§4.3.4).

**Mutation-based validation of specifications.** The pipeline's third phase validates its own
property suite by mutating the source model and requiring the suite to reject the mutants — mutation
testing applied not to code but to a specification, using the property suite as the test set and the
mutants as the faults it must kill. This is the same instrument Chapter 5 uses to evaluate detection,
turned around: there, mutants measure a checker; here, mutants measure a specification's
discriminating power.

**FLOW-BENCH.** The corpus throughout this thesis is IBM's FLOW-BENCH, a benchmark of enterprise
workflow specifications with LLM-generated implementations. Chapter 5 §5.6.1 documents its
provenance and the finding that governs both chapters' evaluation design: the public release carries
no correctness labels for its implementations, so ground truth for any detection measurement must be
manufactured. This chapter uses the BPMN specifications; Chapter 6 uses both halves.

---

## 4.3 Design: BPMN to semantic graph to tiered LTLf to certificate

The module is a four-phase pipeline with a quality gate at each phase boundary. The gates are the
architecturally interesting part: each phase refuses to hand its output downstream unless a stated
condition holds, so a specification that emerges at the far end has passed four separate
admissibility tests, and a specification that does not emerge can be attributed to exactly one of
them. §4.4 is entirely an analysis of which gate stops what.
*(Rendered as Figure 4.2, `figures/fig_m01_pipeline.pdf`, with the measured pass count from §4.4
annotated at each boundary.)*

### 4.3.1 Phase 1 — semantic extraction

Phase 1 parses BPMN XML into a semantic graph and labels it in the style of a Kripke structure, with
three families of atomic proposition:

- `start(X)` — task X has begun,
- `done(X)` — task X has completed,
- `node(X)` — the process is at structural element X.

The three families are introduced here rather than in passing because the third one is the subject of
the chapter's central checkability measurement. `start` and `done` describe *task lifecycle*, which
an implementation can in principle exhibit; `node(...)` describes *diagram structure* — `node(Start)`,
`node(End)`, `node(Decision:…)` — which an implementation cannot exhibit at all, because a Python
program does not visit BPMN diagram elements. That asymmetry is invisible at design time and becomes,
in §4.5.2, the single largest reason synthesized properties are unusable.

The node set is derived dynamically: every XML element carrying an `id` counts toward coverage, minus
an exclusion list of roughly 26 tags that are structural rather than behavioral. A `_recovery_pass()`
re-scans from the XML root for elements the first pass failed to map and re-certifies once, so a
single unmapped element does not fail an otherwise complete extraction. The gate is node coverage
≥ 1.0: every element in the dynamic node set must be accounted for in the semantic graph.

### 4.3.2 Phase 2 — LTLf synthesis and the tier structure

Phase 2 instantiates property templates against the semantic graph, resolves implicit-else branches,
and emits a tiered property suite. The gate is guard-resolution coverage ≥ 1.0 — every guard in the
model must resolve to a condition the synthesizer can express — enforced by raising rather than by
degrading.

The tier structure as *exported* has five keys, and the discrepancy between that and the three
documented tiers is a real defect discussed in §4.5.1. The five are:

| Tier | Intent |
|---|---|
| `P0_Critical_Sentinels` | Safety properties over the specification's own structure |
| `P1_Structural_Control_Flow` | Ordering and precedence between tasks |
| `P2_Quality_Limits` | Bounded-iteration / fairness-style obligations |
| `P3_Adversarial_Defenses` | Properties enriched by Phase 3's adversarial round |
| `synthesized_mutant_killers` | Properties added by Phase 3 to kill surviving mutants |

P1 is the tier that carries the module's conformance-checking intent, and its flagship shape is a
precedence property:

```
!start(B) W done(A)
```

read as "B does not start until A has completed" — a weak-until formulation that does not itself
require A to happen. That formulation is standard and it is also, as §4.6 shows by exhaustive case
analysis, the reason the module's principal tier is blind to the corpus's principal failure mode.
The shape is introduced here so the reader meets it as a design decision before meeting its cost.

### 4.3.3 Phase 3 — mutation self-validation

Phase 3 asks whether the synthesized suite is *discriminating*: it mutates the source model with
five operators, generates traces of the mutants by bounded iterative depth-first search (loops
permitted, cap 100 traces), and requires the property suite to reject them. A round-zero adversarial
step attempts to construct model variants the current suite would miss and enriches the suite with
properties that kill them; up to three self-healing rounds run, each re-auditing with the enriched
suite. A specification that fails leaves a certificate listing its `unresolved_vulnerabilities` with
`human_action_required`.

The gates are structural coverage C_struct ≥ 1.0 **and** kill ratio δ ≥ 1.0 — that is, the suite must
kill every mutant, not most of them.

Two honesty notes. First, the adversarial generator is simulated heuristics, not a language model,
notwithstanding the framing the name invites. Second, this is the gate that rejects 19 of the 48
FLOW-BENCH specifications, and its interaction with the corpus is the subject of §4.4.1 — including a
correction to which phase number the failure is reported under.

### 4.3.4 Phase 4 — PBCTS and bidirectional alignment

Phase 4 produces the module's certificate. Its mechanism is Progression-Based Constructive Trace
Synthesis (PBCTS): rather than compiling the property suite to an automaton and extracting accepted
words, it conjoins the suite into a single formula and enumerates satisfying traces by *progressing*
the formula symbolically one step at a time, pruning branches whose obligations become unsatisfiable
and memoizing repeated obligation sets. Progression is implemented in pure Python
(`progress`, `simplify`, `extract_obligations`), bounded by `bound_k` and capped at 200 traces.

Each synthesized trace is scored for structural coverage:

```
SCov = 0.4 · node_coverage + 0.4 · branch_coverage + 0.2 · depth_coverage
```

The synthesized traces are then aligned bidirectionally against traces of the source model, giving
precision, recall and a harmonic-mean alignment score (EAS_BDA). The gate is convergence:
|ΔEAS| < 0.001 for some k ≤ 20. A self-correcting loop converts detected over-specification into
corrective properties of the form `!(F(a & X(b)))` (at most ten, in a `P4_SCSL_Corrections` tier) and
re-runs up to three rounds. The output is a Formal Reliability Certificate carrying the alignment
analysis and, where relevant, spec-only and model-only traces as semantic-gap examples.

Two facts about this phase must be stated plainly because §4.4.2's result depends on them. First,
the documented targets EAS ≥ 0.90 and SCov ≥ 0.85 are **not enforced in code**: convergence is the
only Phase 4 gate. Second, the whole construction is the *replacement* for a deleted SPOT/HOA
automata-lifting phase; the pivot removed SPOT from this module's executable code entirely, and
subsequently from its container image.

### 4.3.5 The export contract

The module hands Module 03 a JSON payload with four keys: `ltlf_property_suite`, `tier_semantics`,
`semantic_graph`, and `loop_bound_documented`. The properties travel as **LTLf strings**, not as
automata.

This is the interface decision that shapes Chapter 6. Exporting strings keeps this module free of an
automata toolchain — which, after the pivot, it no longer has — and it keeps the dual-track boundary
clean: Module 03 consumes this JSON and nothing else from this module, deploying as its own container
with no access to this module's source. The cost is that the finite-trace semantics of the exported
formulas are carried by convention rather than by construction, and reconciling them with an
infinite-trace checker becomes the consumer's problem. Chapter 6 §6.4 shows what that costs. The
decision is defensible and it is not free, and this chapter says so rather than presenting the string
interface as obviously correct.

---

## 4.4 The central result: the corpus is lost upstream of synthesis

The intuitive account of a specification synthesizer's evaluation is that it emits properties of
varying quality. The measured account for this module is stronger and differently shaped: on
FLOW-BENCH, most of what is lost is lost *before synthesis runs*, and none of what survives passes
the module's own final gate.

### 4.4.1 The gateway gate

Running the pipeline over all 48 FLOW-BENCH specifications produces 19 hard failures and 29
specifications that export a property suite. The hard-failing set is not a scattered collection of
awkward models. It is exactly the set of specifications containing an `<exclusiveGateway>` element —
set equality, tested true rather than eyeballed, and subsequently re-derived by an independent
verification pass that obtained identical tallies and an identical list of failing uids. The corpus
contains no `<parallelGateway>` at all, so branching in FLOW-BENCH means exclusive branching, and
exclusive branching means rejection.

The failure message is specific. For uid 12:

```
XOR Gateway 'exclusiveGateway_4' has 2 unconditioned branch(es) without a default flow.
```

The synthesizer cannot instantiate a property for a decision whose branches carry no conditions and
whose gateway declares no default, because there is no proposition to write down: it does not know
what distinguishes the branches. Its refusal is the guard-resolution gate of §4.3.2 doing exactly
what it was specified to do.

One correction belongs here rather than in a footnote, because it affects citation rather than
substance. The failure was first reported as a Phase 3 rejection. Tracing the exception path shows it
is raised inside the synthesizer's own certification step and reported by the API under `"phase": 2`.
The counts, the message text and the set-equality result are unaffected; the phase attribution was
wrong and is corrected here. A reader auditing this chapter against the source should expect
`"phase": 2`.

### 4.4.2 Module 01 never reports PASS on FLOW-BENCH

Of the 48 specifications, **zero** reach an unqualified `PASS`. All 29 survivors export under a
status indicating that PBCTS did not converge — that is, the Phase 4 gate of §4.3.4 was not met
within k ≤ 20.

This deserves precision, because the status name is easy to misread and has itself changed. The
status does not mean the properties are invalid, and it does not mean the specification was rejected;
it means the module could not demonstrate that its synthesized trace set had stabilized against the
source model's own traces. The suite is exported regardless. At the time this measurement was taken
the status was named for the unproven alignment; it has since been renamed to name the actual
condition — PBCTS non-convergence — and a dedicated test pins the library and service layers to
report the same code, because they previously did not. A reader grepping current source for the old
name will not find it; the master numbers table records both.

The consequence for the rest of the thesis is direct and belongs in both chapters. The design round
that specified the ingestion layer raised the question explicitly — whether a non-converged suite is
legitimate input to a conformance check — and left it as an owner decision, recommending that the
suite be accepted with its status recorded on every reported row. What was implemented is the
acceptance half: the downstream evaluation consumes these suites. **Every conformance number in
Chapter 6 therefore rests on property suites whose own producer could not prove alignment.** That
sentence appears in Chapter 6 as well. It is not a reason to discard those numbers, but it is a
condition on reading them, and burying it in one chapter would let it be missed.

Why 0 of 48 converge is not diagnosed by any artifact. The gate outcome is measured; which of
`bound_k`, the size of the conjoined suite, or the |ΔEAS| threshold is binding has not been
established, and §4.9 lists it as open rather than guessing.

### 4.4.3 The gate is correct and the corpus is underspecified

A 40% admission rate invites the reading that the gate is too strict. The measurement that settles
this is, I think, the strongest single admissibility result in the chapter.

Across the 19 gateway-bearing specifications there are **20 splitting exclusive gateways**. Of those
20:

- **0 declare a `default` attribute**, and
- **0 have any `conditionExpression` on any outgoing sequence flow.**

Not a minority. None. The BPMN files contain no decision logic whatsoever for these gateways: no
guard, no default, nothing that distinguishes taking one branch from taking another. There is no
version of a synthesizer that could produce a conformance property for such a gateway, because the
specification does not say what the branch condition is. Any tool that emitted a property here would
be inventing the specification's content.

This converts the open question — fix the gate, or scope branching out of the thesis — from a
judgement call into an evidence-backed one, and it changes what the 19/48 figure means. It is not a
40% admission rate for a tool that ought to admit more. It is a 40% admission rate against a corpus
whose entire branching subset is not specified to the level that branching conformance requires. The limitation is jointly owned by the tool and the benchmark,
and reporting it as the tool's alone would be a misattribution the evidence does not support.

What remains genuinely the tool's limitation is scope: branching workflows are out of scope, and with
them the whole branching-conformance story, which §4.9 states without mitigation.

### 4.4.4 Correction trail for this section

Two corrections have been folded into the text above rather than presented as errata, and both are
recorded here so the trail is auditable:

| What was stated | How it was caught | Correction |
|---|---|---|
| Gateway rejection occurs in Phase 3 | Independent verification traced the exception path | Raised in the synthesizer's certification step, reported as `"phase": 2`. Counts, message and set equality unaffected |
| The export status was named for unproven alignment | Library and service layers were found reporting different codes | Renamed to name PBCTS non-convergence; both layers unified and pinned by a dedicated test |

Neither changes a number. Both change what a verifier should expect to find in current source, which
is exactly the kind of drift that makes a cited figure unauditable a year later.

---

## 4.5 Checkability: what fraction of a synthesized suite can ever be checked

Admissibility asks whether a specification produces a suite. Checkability asks whether the suite is
of any use — and it is a property of the synthesizer's output alone, measurable before any
implementation is involved. To my knowledge no metric of this kind is standard in the
specification-synthesis literature, which tends to report properties emitted, coverage of the source
model, or downstream verification outcomes. The measurements in this section are the argument for
adding it: a synthesizer can score well on all three of those while emitting output that is
overwhelmingly unusable.

### 4.5.1 The tier census

The 29 exporting specifications synthesize **412 properties**, distributed as:

| Tier | Properties |
|---|---|
| `P0_Critical_Sentinels` | 79 |
| `P1_Structural_Control_Flow` | 256 |
| `P2_Quality_Limits` | 29 |
| `P3_Adversarial_Defenses` | 48 |
| `synthesized_mutant_killers` | 0 |

*(Rendered as Figure 4.3, `figures/fig_m01_tier_census.pdf`; the rendered version shows five
disjoint segments summing to 412, not the duplicate count as a separate overlay — see the outline's
note on this simplification.)*

Two defects are visible in the census itself, before any property is examined.

First, the export's own `tier_semantics` field describes **three** of the five tiers it ships. A
consumer that gates on `tier_semantics` — the natural implementation — meets tiers it has no policy
for. This is not hypothetical: it hard-errored the downstream ingestion layer on real specifications
during end-to-end integration, and was fixed at the export with a regression test that ingests a real
export rather than a fixture. It is a small bug with a general lesson about self-describing
interfaces: a schema description that is not generated from the schema drifts from it silently, and
the drift surfaces at the consumer.

Second, **34 of the 412 properties are exact duplicates within their own tier**. Duplicates inflate
any per-property denominator, so they are de-duplicated before metrics are computed downstream. As a
signal about the synthesizer, a duplicate rate of 8% suggests template instantiation is firing more
than once on the same structural feature.

The `synthesized_mutant_killers` tier is empty across all 29 specifications. Since Phase 3 gates on
kill ratio δ ≥ 1.0, an empty killer tier is consistent with suites that killed every mutant without
enrichment — but no artifact reports the kill-ratio distribution, so this reading is inference and is
flagged as such in §4.7.

### 4.5.2 The `node()` family is unusable against code

Of the 256 P1 properties, **211 — 82.4% — reference at least one `node(...)` atom**: `node(Start)`,
`node(End)`, or `node(Decision:…)`. These describe positions in a BPMN diagram. A Python
implementation has no counterpart: it does not enter `node(Start)` and it does not visit a decision
element. However good the matcher between BPMN task names and Python function names is — and §4.5.4
shows it is good — there is nothing on the code side for a `node(...)` atom to match.

**45 properties remain**: pure task-precedence formulas over `start`/`done` atoms, present in 22 of
the 29 exporting specifications, median 2 per specification.

**45 of 256 — 17.6% of the P1 tier — is this chapter's headline checkability figure.** It is
measured on the synthesizer's own output, with no implementation involved and no downstream
verification attempted. Every conformance verdict anywhere in this thesis is drawn from those 45
properties.

The figure is not an indictment of the `node(...)` family in itself; structural properties are
meaningful *about the specification*, and Phase 3 uses them productively to discriminate mutated
models. It is an indictment of not distinguishing the two purposes. A tier named "structural control
flow" that mixes code-checkable precedence with diagram-structural assertions cannot be gated
usefully downstream, and its size cannot be read as a measure of conformance-checking power.

### 4.5.3 P0, P2, P3, and the empty tier

The remaining tiers are excluded from conformance checking, each for a distinct reason, and the
distinctions matter because "excluded" is not one thing.

**P0 — 79 properties — is excluded by construction, and provably so.** The sentinel shape asserts a
property of the specification's own structure. Any faithful lifting of an implementation satisfies it
by construction, so it cannot be falsified — not merely under one candidate code-side lifting, but
under any. Chapter 6 §6.6 develops this argument where the lifting is defined; the consequence for
this chapter is that 79 of 412 properties constitute a *lifting self-test* rather than evidence about
code. Reporting them as passed safety properties would be reproducing Chapter 5's central failure at
this seam: a check that cannot fail, reported as a check that passed. This connection is why the P0
reclassification is treated as a result rather than a bookkeeping decision.

**P2 — 29 properties — is a single template instantiated 29 times:**

```
G(iteration_count <= 10 -> F(process_complete))
```

Two independent obstacles. Syntactically, `iteration_count <= 10` is an arithmetic comparison, not a
propositional atom, and no downstream parser accepts it as one. Semantically, neither
`iteration_count` nor `process_complete` has a code-side counterpart to match against. The property
expresses something real and desirable — bounded iteration implies eventual completion — and
expresses it in a form no consumer in this system can evaluate. Chapter 6 notes the further
consequence: loop-bound checking has no home in the canonical verification path precisely because
this tier is excluded.

**P3 — 48 properties — all use the `X` (next) operator.** This lands exactly where finite- and
infinite-trace semantics diverge most sharply, and where a documented strength mismatch exists
between this module's evaluator (strong `X`, false past the end of a trace) and the downstream
reduction's bare `X` (weak). The tier is excluded pending a bridge that handles the operator
correctly rather than silently.

**`synthesized_mutant_killers` — 0 properties.** Nothing to exclude.

The arithmetic is worth stating in one line, because it is the chapter's summary in miniature: of 412
synthesized properties, 45 are conformance-bearing.

### 4.5.4 The atom vocabularies are disjoint by construction

A property is only checkable if its atoms can be *matched* to something observable in the code, and
this turns out to fail for a reason unrelated to matching quality.

The measurement: **0 of 116 spec-side P1 atoms** can match a code-side atomic proposition, and **0 of
29** spec/variant pairs overlap at all. Complete disjointness.

The cause is a lifecycle-prefix mismatch. This module emits lifecycle atoms — `start_Approve`,
`done_Approve` — while the code-side lifter registers the matched BPMN task name directly as the
proposition, giving a bare `Approve`, with no lifecycle-prefix construction anywhere in it. Both
halves of that are read from source, on both sides.

What identifies this as a lifecycle-layer omission rather than a naming-quality problem is that the
identifier matching is *good*: spec task name to Python function name matches exactly at **86.0% on
mean across 43 spec/variant pairs, with 26 of 43 at 100%**. The two vocabularies are talking about
the same tasks with the same names and failing to meet only because one side decorates the name with
a lifecycle phase and the other does not. A weaker matcher would have produced the same 0/116 for a
completely different and much less tractable reason.

Reproduction status, stated precisely because the two halves have different strength. The mechanism —
prefix on one side, no prefix on the other — is verified from source on both sides. The specific
0/116 count was measured against a Python emulation of the code-side proposition construction,
because the compiled engine was not available in that environment. It was later confirmed on a real
compiled build in the equivalent form: 58 of 58 property checks returned `INCONCLUSIVE` when
unstripped atoms reached the checker. The emulated count and the real-build confirmation agree; the
prose above keeps them distinguishable.

Chapter 6 §6.6 presents the two ways to close the gap and which one shipped. The relevant note for
this chapter is that the shipped fix collapses this module's lifecycle atoms to flat ones on the
consumer's side, which is lossless only for sequential workflows — true of this corpus, which
contains no parallel gateways, and false in general.

### 4.5.5 The funnel

Collecting §4.4 and §4.5 into one shape:

```
48 BPMN specifications
 └─ 19 hard-fail at guard resolution (exactly the exclusiveGateway set)
 └─ 29 export a property suite  ── all under PBCTS-non-convergence, 0 PASS
     └─ 412 properties synthesized
         ├─  79  P0   lifting self-test, unfalsifiable by construction
         ├─ 211  P1   node()-bearing, no code-side counterpart
         ├─  29  P2   unparseable atoms, no code-side counterpart
         ├─  48  P3   X-operator, unbridged
         ├─   0       synthesized_mutant_killers
         └─  45  P1   conformance-checkable  ── in 22 of 29 specs, median 2
             └─ (Chapter 6) 6 specs usable as end-to-end gold
```

This figure is the chapter. Every arrow has a cause, every cause has a source file, and the shape of
the loss is the finding: the two largest cuts are a benchmark underspecification and a property-family
choice, and neither is a matter of synthesis quality in the sense the phrase usually implies.
*(Rendered as Figure 4.1, `figures/fig_m01_checkability_funnel.pdf`.)*

---

## 4.6 Structural blindness: omission dominance and the coverage tier that does not exist

The 45 checkable properties are the tier the design calls the real conformance checks. This section
measures what they cannot see, and the answer is: the corpus's dominant failure mode.

**How the implementations actually diverge.** Classifying all 43 (specification, variant) pairs for
which both sides are available:

| Divergence mode | Pairs |
|---|---|
| Omission only — the implementation omits a specified task | **23** |
| Exactly conformant | 15 |
| Omission and reordering | 3 |
| Reordering only | 2 |

Omission dominates. LLM-generated implementations of these workflows mostly go wrong by leaving a
step out, not by getting the order wrong.

**What the P1 shape does with an omission.** Take the precedence property `!start(B) W done(A)` — B
does not start until A completes — and enumerate the cases:

| Trace | Verdict | Interpretation |
|---|---|---|
| A then B (correct) | `True` | correct pass |
| B then A (reversed) | `False` | **detected** |
| A only, B omitted | `True` | **not detected** |
| B only, A omitted | `False` | detected (incidentally) |
| Neither | `False` | detected (incidentally) |

Row three is the problem. Weak until does not require its right-hand side to occur, so omitting the
*later* task of a precedence pair satisfies the property **vacuously**. The implementation has
dropped a specified step and the property is content.

This is not a theoretical worry. Checked directly on the corpus: **7 divergent pairs produce no
failing checkable P1 property at all.** Two named cases make the mechanism concrete —
`82__llama-3.1-8b.py` calls 1 of its specification's 5 tasks, and `77__llama-3.1-8b.py` calls 2 of 3.
These are not marginal divergences that a reasonable checker might forgive; they are implementations
that skip most of the workflow, and the property suite reports nothing.

**Reproduction spread, reported rather than smoothed.** An independent re-derivation using cruder
substring name matching classified the same 43 pairs as 24 omission-only and 3 reordering-only. The
dominance pattern is identical and the exact split differs by one pair in each direction; the two
named blind cases reappear independently. Both classifications are given here because the difference
is the honest precision of a name-matching-based classification, and quietly presenting one as
definitive would overstate it.

**The gap, and its status.** No tier fills it. Detecting omission needs a property that *requires*
something to happen — an `F`-bearing obligation — and the only `F`-bearing tiers are P2 (unparseable,
§4.5.3) and P3 (unbridged). The P1 tier is built from safety-shaped precedence formulas, which cannot
express "this must happen" by construction.

A task-coverage property family was **designed** to fill it: one obligation per specification task, of
the form "task T eventually completes," with a reachability trace worked through on
`82__llama-3.1-8b.py` and an explicit caveat from its author that the obligation is `F`-bearing and
therefore requires the very finite-trace bridge that design scoped out. It is **not implemented**. The
design document argues it would convert a large share of the corpus's invisible divergences into
detectable ones; that is a design argument with a worked example, not a measurement, and this chapter
does not carry the figure across into a capability claim. §4.9 lists it as future work, and Chapter 6
observes the same blindness from the other end: 0 of 16 injected task-drop mutations were detected
end-to-end.

There is an uncomfortable symmetry worth naming. Chapter 5's negative result is that a code-derived
oracle cannot see logic bugs. This section's result is that a specification-derived property suite of
the wrong *shape* cannot see the corpus's dominant bug class either. Independence of the oracle is
necessary and it is not sufficient; the property shape has to be able to fail in the way the defects
actually occur.

---

## 4.7 What serves as Module 01's own validation

If not detection, then what? Three things, each cited, none of them a detection rate.

**(i) Oracle self-consistency.** Evaluating each specification's own task order against its own
property suite yields **45/45 satisfied** — every checkable property is satisfied by the trace the
specification itself prescribes. This is a small measurement doing important work. It is the guard
against a synthesizer emitting self-contradictory properties, and it is what licenses attributing a
downstream `False` to the implementation rather than to a defective property. Without it, every
conformance violation in Chapter 6 would be ambiguous between "the code is wrong" and "the property
was never satisfiable." Chapter 6 §6.5.6 uses the same evaluator as an independent finite-trace
oracle to cross-validate its bridge, which is a second use of the same self-consistency guarantee.

**(ii) Phase 3's mutation self-validation.** The module carries its own internal discriminating-power
gate: it must kill every mutant of its source model. This is a genuine validation mechanism and it is
reported here only through its pass/fail outcome — the 19 hard failures of §4.4.1. No artifact
reports the distribution of kill ratios or structural-coverage scores across the corpus, so there is
no measurement of *how* discriminating the surviving suites are, only that they cleared a binary bar.
The chapter says this rather than letting the presence of a gate imply a measurement of what it
admitted.

**(iii) The test suite.** 28 tests across 6 files, all passing: the Phase 1 and Phase 3 gates, PBCTS
convergence, the self-correcting loop, status-code consistency, the Module 03 export, and the HTTP
API.

The history behind that sentence has to be stated, because omitting it would describe a different
project. At the time the design round measured this module's behavior, it had **zero tests**, and its
FastAPI service could not start at all: `main.py` imported a module that had been deleted in the
pivot, in both branches of its import fallback. Every measurement in §4.4 and §4.5 was taken against
the *library*, which worked, not the service, which did not. Both are now fixed, the startup path is
covered by a container startup check in CI, and the status-code inconsistency found along the way is
pinned by its own test. A module that acquired its first test after its evaluation numbers were taken
is a module whose evaluation numbers deserve the caveat, and this is it.

---

## 4.8 Implementation notes

The module is roughly 2,260 lines across 11 source files, served over FastAPI, with about 700 lines
of tests. Its dependency list is three packages — a web framework, a server, and a graph library.

The most notable implementation fact is a subtraction. After the pivot replaced automata-based trace
synthesis with pure-Python progression, SPOT remained in the container image, built from source, for
nothing. It has since been removed: the image is a 19-line slim build with a comment explaining the
removal. A model-checking toolchain vendored into a service that never calls it is exactly the kind
of residue an architecture pivot leaves, and it is worth reporting as such.

A second residue is more interesting because it interacts with the dual-track rule.
`FormulaNormalizer` is a class in this module that normalizes atoms into precisely the form the
downstream consumer needs — and it has **zero callers anywhere in the repository**. When Module 03
came to need that normalization, it did not import this class; it ported its own. That was the right
call for a structural reason: Module 03 deploys as its own container with no access to this module's
source, so cross-importing would have created a coupling the dual-track architecture forbids. The
dead class's docstrings have been rewritten to say plainly that it is unused and not to be
resurrected as-is. The episode is a small illustration of a real cost of the dual-track constraint —
duplicated normalization logic in two modules — accepted deliberately in exchange for independence.

One genuine cross-module bug was found and fixed at the export seam while building the end-to-end
demonstration: the `tier_semantics` field described three of the five tiers the suite can contain,
which hard-errored the consumer's ingestion on real specifications. The fix is at the export, and the
regression test ingests a real export rather than a hand-built fixture — the only form of the test
that would have caught the original defect.

---

## 4.9 Limitations

Each limitation is stated with its measured cost in the same sentence, and each is drawn from the
master numbers table rather than from impression.

1. **Branching workflows are entirely out of scope.** 19 of 48 specifications are rejected, and with
   them the whole branching-conformance story. Mitigating measurement: the corpus supplies no
   decision logic for those gateways — 0 of 20 splitting exclusive gateways declare a default flow or
   any branch condition — so the scope limit is jointly owned by the tool and the benchmark rather
   than being a gate defect.
2. **No specification reaches an unqualified PASS.** 0 of 48. All 29 exports carry
   PBCTS-non-convergence, and every downstream conformance number in this thesis rests on
   non-converged suites. Why none converge is not diagnosed; the gate outcome is measured and the
   diagnosis is open.
3. **Checkability is low.** 17.6% of the P1 tier (45 of 256), 0% of P2, 0% of P3, and P0 excluded by
   construction — 45 of 412 synthesized properties are conformance-bearing.
4. **Omission blindness is structural.** 23 of the 43 (spec, variant) pairs diverge by omission alone
   (of the 43, 15 are exactly conformant, 3 combine omission with reordering, and 2 are
   reordering-only), and 7 of the 23 produce no failing checkable property at all. The property shape cannot express the obligation that would
   catch them. The coverage tier that would is designed and unbuilt.
5. **The atom vocabulary is disjoint from the code side by construction.** 0 of 116 atoms match; the
   downstream reconciliation is a prefix collapse that is lossless only for sequential workflows —
   true of this corpus (zero parallel gateways), false in general.
6. **Adversarial generation is simulated heuristics, not a language model**, notwithstanding the
   name.
7. **Documented Phase 4 targets are unenforced.** EAS ≥ 0.90 and SCov ≥ 0.85 appear in
   documentation; convergence is the only gate in code.
8. **Corpus scope.** One benchmark, 48 specifications, enterprise-workflow shape. Whether the
   checkability rate or the divergence-mode distribution generalizes is untested and not claimed.
9. **No per-specification timing is reported.** No timing artifact exists for this module.

---

## 4.10 Summary of contributions

**(1) A finite-trace property synthesis pipeline from BPMN with per-phase quality gates and a
constructive trace certificate produced without an automata toolchain.** PBCTS enumerates satisfying
traces by symbolic progression of the conjoined property suite, with obligation pruning and
memoization, in pure Python; the certificate carries a bidirectional alignment score and a
convergence gate. The architectural claim is not that progression is superior to automata
construction in general, but that it removes a heavyweight dependency from a module that needed only
a bounded trace set — a claim supported by the fact that the toolchain was subsequently removed from
the container entirely.

**(2) A checkability metric, and the measurement that makes it bite.** The observation that a
specification synthesizer must be evaluated on the fraction of its output that is *evaluable against
an implementation* — not on properties emitted, model coverage, or downstream pass rates — together
with the corpus measurement that gives it force: 45 of 256 P1 properties, 17.6%, with the loss
attributed to a specific property family (`node(...)`, 211) and a specific vocabulary mismatch
(0 of 116 atoms). A synthesizer scoring well on conventional metrics can emit output that is
overwhelmingly unusable, and no conventional metric would reveal it.

**(3) An admissibility result that localizes a benchmark limitation rather than a tool limitation.**
The entire branching gap traced to one gate by set equality, and the gate vindicated by the finding
that 0 of 20 splitting gateways in the corpus carry any decision logic. This converts a headline
limitation into a jointly-owned one and demonstrates a general point: an admission-rate figure is
uninterpretable without an audit of what was refused.

**(4) A negative structural result from the specification side.** A specification's own sentinel tier
cannot serve as evidence about code under any faithful lifting — 79 of 412 properties are a lifting
self-test — which is Chapter 5's self-referential-validation failure mode arrived at from the
opposite direction. Together with §4.6's omission blindness, this supports a claim neither chapter
makes alone: oracle independence is necessary but not sufficient, because a property shape that
cannot fail in the way defects actually occur is as uninformative as an oracle that moves with the
code.

**(5) An honest interface contract.** LTLf strings plus tier semantics, with the finite-trace
obligation handed to the consumer explicitly rather than silently, and the dual-track boundary
maintained at the cost of duplicated normalization logic. Chapter 6 pays this bill in full and in
public.

The module's honest summary is that it produces a small, self-consistent, independently-derived set
of checkable properties from a minority of a real benchmark, and that the measurements explaining why
the set is small are more useful to the thesis than a larger set with unaudited provenance would have
been. What it hands Module 03 is 45 properties in 22 specifications, every one of them satisfied by
its own specification's prescribed trace, none of them derived from any line of the code they will be
used to judge.
