# Chapter 6 — Module 03: The Equivalence Engine, and Two Ways a Model Checker Can Prove Nothing

> Draft. Chapter number provisional (Module 01 → Chapter 4, Module 02 → Chapter 5). Outline,
> narrative decisions and the master numbers table live in `module03_chapter_outline.md`. Every
> figure is cited; the master table maps each to its source file. Superseded figures appear only in
> the correction trail (§6.12), labeled, never as system behavior.

---

## 6.1 Introduction: the convergence point

Chapters 4 and 5 describe two pipelines that are, by design, forbidden to look at each other. Module
01 reads a BPMN specification and never sees the generated code. Module 02 reads the generated code
and never sees the BPMN diagram. That separation is the architectural commitment on which the whole
system's claim to non-circularity rests, and Chapter 5 measures what happens when it is violated:
a certificate derived from the code it checks detects 0 of 220 injected logic bugs, because oracle
and artifact move together.

Module 03 is where the two tracks meet — the only place in the system where a verdict about
*specification-versus-code* exists at all. It receives a property suite from Module 01 as JSON and a
Workflow Intermediate Representation from Module 02 as JSON, lifts the latter into an automaton,
model-checks the former against it, and returns conformance, violation with a counterexample, or an
explicit refusal to decide. The separation is maintained here structurally rather than by convention:
the module deploys as its own container with access to neither upstream module's source, which is why
— as §6.3.5 records — it reimplements normalization logic that exists, unused, upstream.

This chapter has two questions.

The first is about the model checker's `COMPLIANT` verdict, and it is the chapter's principal
intellectual content. Phase D implements the automata-theoretic approach to model checking exactly as
the textbook prescribes: parse the property, negate it, build a Büchi automaton of the negation, take
the product with the system automaton, test the product for emptiness, and extract an accepting run
as a counterexample. That pipeline was complete, tested, and *structurally incapable of returning a
meaningful `COMPLIANT`* on any ordinary input — for two entirely unrelated reasons, neither of which
its passing test suite revealed. The first is a missing acceptance condition, which makes the system
automaton's ω-language empty, which makes every product empty, which makes every property vacuously
true. The second is that the propositions the specification talks about and the propositions the code
automaton registers are disjoint sets, so a specification atom is permanently false in the code's
automaton. Each channel is presented here with its mechanism, the reason its tests were silent, its
fix, and the evidence the fix works.

The second question is empirical: what does the assembled pipeline detect, end to end, on real BPMN
specifications and real LLM-generated implementations. That evaluation exists and is small — 6 gold
specifications — and §6.8 reports it with its intervals, its manufactured-ground-truth provenance, and
an explicit statement of what it does and does not license.

There is a third question this chapter does not answer, and saying so up front is preferable to
letting a reader infer an evaluation that does not exist. Phases A, B and C — lifting, bisimulation
reduction, and behavioral clustering — constitute the module's code-versus-code behavioral-equivalence
capability. It is implemented and unit-tested. It is **not evaluated**: no artifact in this project
measures its agreement with behavioral ground truth on the corpus. §6.10 names this as the largest
single evaluation gap in the module, and no number anywhere in this chapter should be read as
speaking to it.

A note on how the vacuity findings are argued, because the order is deliberate. In each case the
mechanism is established from source and from standard theory *first*, and the confirming observation
on a real build comes second. A vacuity defect is precisely the kind of defect an experiment can
easily fail to reveal — the system returns a plausible answer — so an argument that depends on having
run it is weaker than one that does not. The runs are reported as confirmations of predictions, and
they are labeled as such.

---

## 6.2 Background and related work

**Linear temporal logic and Büchi automata.** LTL extends propositional logic with temporal
operators — `X` (next), `F` (eventually), `G` (always), `U` (until), `W` (weak until) — interpreted
over infinite sequences of propositional valuations. A Büchi automaton accepts infinite words that
visit an accepting state infinitely often. Every LTL formula has an equivalent Büchi automaton, and
this equivalence is the foundation of the verification method below.

**The automata-theoretic approach to model checking.** Vardi and Wolper's formulation: to check
whether system automaton *A* satisfies property φ, build the Büchi automaton *B* of ¬φ, form the
product *A* × *B*, and test the product's language for emptiness. A non-empty product yields an
accepting run — a concrete behavior of the system violating the property, i.e. a counterexample.
Phase D is this construction, and it is worth stating that the construction as implemented is
faithful: the defects §6.5 and §6.6 describe are not errors in the algorithm but errors in what was
handed to it.

**Finite-trace LTL and its reduction.** LTLf interprets the same syntax over finite traces (De
Giacomo & Vardi). Finite and infinite semantics differ substantively — `G φ` over a finite trace
constrains only the trace's own positions; `X φ` at the last position is false under a strong reading
and true under a weak one. The standard reduction to infinite-trace machinery introduces an auxiliary
proposition, conventionally `alive`, that holds exactly on the finite prefix and is false forever
after, and rewrites the formula so its temporal operators are relativized to the alive segment. §6.4
uses this reduction, with the well-formedness obligation it imposes on the automaton.

**Stuttering bisimulation, and why divergence sensitivity is not a detail.** Bisimulation equates
states that can match each other's transitions indefinitely. Stuttering variants tolerate finite
sequences of internal (τ) steps, allowing abstraction from implementation-level bookkeeping — the
Groote–Vaandrager partition-refinement algorithm is the standard efficient decision procedure.
*Divergence-sensitive* stuttering equivalence additionally distinguishes states that can perform
infinitely many consecutive τ steps from those that cannot. For this application the distinction is
the whole point: plain stuttering equivalence collapses a τ-cycle into a τ-path, so a hallucinated
`while True: pass` becomes equivalent to a workflow that briefly waits. Phase B is deliberately the
divergence-sensitive variant, and describing it as ordinary bisimulation would misstate the design.

**Bisimulation minimization and isomorphism-based clustering.** Reducing an automaton to its
bisimulation quotient before verification is standard practice, and canonical quotients make
structural comparison meaningful — the basis for Phase C's grouping of behaviorally identical
implementations by automaton isomorphism.

**Translation validation.** The general problem — checking that a translation preserved the source's
semantics, rather than verifying the translator once — descends from Pnueli's translation validation
and the validated-compiler line of work. This system is translation validation where the source is a
BPMN diagram, the target is generated Python, and the translator is a language model. That framing is
shared with Chapter 5 and is what makes the counterexample requirement of §6.7.4 non-negotiable: a
translation-validation tool that reports a mismatch without localizing it is of limited practical
use.

**Approximate action matching.** Formal methods presume a fixed alphabet; here the alphabet must be
recovered by matching BPMN task names against Python identifiers. Phase A therefore ends in a
pragmatic cascade — exact match, then string edit distance, then sentence-embedding similarity — which
is where formal verification meets natural-language identifiers, and which §6.10 flags as the least
formally grounded component in the module.

---

## 6.3 Design: four phases from WIR to verdict

The module exists in two tracks. A pure-Python implementation (~1,470 lines, 37 tests) covers all four
phases without external dependencies. A C++ implementation built on SPOT covers all four phases and
is the canonical path. Both are maintained; the two-track situation is discussed in §6.3.4, since it
has a live consequence.
*(Rendered as Figure 6.1, `figures/fig_m03_pipeline.pdf`.)*

### 6.3.1 Phase A — lifting the WIR to a labeled transition system

Phase A walks the WIR's control-flow graph and emits a labeled transition system: nodes become states,
edges become transitions, and each transition is labeled with the atomic propositions that hold when
it is taken. Action names are extracted from each node's code text and resolved against the
specification's task vocabulary by a three-tier cascade:

1. exact string match;
2. string edit distance, for minor naming divergence;
3. sentence-embedding similarity (`all-MiniLM-L6-v2`), reached from C++ through embedded pybind11, for
   semantic divergence such as `submit_form` against `Submit Application`.

An action that resolves at no tier is labeled `unlabeled_task` rather than dropped, so an unmatched
action cannot silently pass as a match. Loops are handled by bounded unrolling.

One environmental fact bounds how the matching results in this chapter should be read. In the
environment where the corpus verification runs were performed, the embedding model was not installed:
tiers 1 and 2 ran for real and tier 3 degraded to the `unlabeled_task` fallback with a diagnostic on
stderr. This does not affect the §6.6 finding, which fires identically regardless of which tier
resolved a label, but it means no measurement in this chapter reflects tier-3 matching in operation.

### 6.3.2 Phase B — divergence-sensitive stuttering bisimulation

Phase B reduces the lifted LTS to its divergence-sensitive stuttering bisimulation quotient, using
Groote–Vaandrager partition refinement with Tarjan strongly-connected-component detection to identify
τ-cycles (`spot::scc_info` on the C++ side). Three equivalence tiers are exposed — functional, trace,
and process — differing in how much internal structure they abstract.

The design commitment is the divergence sensitivity. Reduction must not merge a state that can τ-step
forever with one that cannot, because in this domain the two are the difference between a hallucinated
non-terminating loop and a normal wait. §6.9 records the cost of that commitment: it collides directly
with the finite-trace bridge of §6.4, and the collision is unresolved.

### 6.3.3 Phase C — behavioral clustering

Phase C groups reduced automata by isomorphism (`spot::isomorphism_checker::are_isomorphic`),
selecting as each cluster's representative the automaton with fewest states, breaking ties on fewest
edges, over a shared BDD dictionary. The design rationale is cost: given N candidate implementations
of one specification, verification effort scales with the number of *distinct behaviors* rather than
with N, because behaviorally identical implementations need be model-checked once.

That is the designed rationale and it is reported as such. No artifact in this project measures the
realized saving on the corpus, and §6.10 lists it among the unmeasured capabilities.

### 6.3.4 Phase D — model checking

Phase D takes a reduced automaton and an LTL property string and returns a verdict. The C++ path
implements the Vardi–Wolper construction directly with SPOT primitives: `parse_infix_psl` for the
property, negation, `translate` to a Büchi automaton, `otf_product`, `is_empty`, and `accepting_run()`
to extract a counterexample. The result object carries the verdict, the counterexample trace, and the
set of atoms the property mentioned that the automaton did not register (`unmatched_atoms`).

That last field implements an important discipline. When a property references a task the automaton
does not contain, the checker does not answer; it returns `INCONCLUSIVE` and reports which atoms were
missing. An `INCONCLUSIVE` is a refusal to decide, and it is a different thing from both a `COMPLIANT`
and a `VIOLATION`. Most of the numbers in this chapter only make sense with that three-valued outcome
space in view, and §6.7.6 and §6.8.3 both turn on it.

The two-track situation has one concrete consequence worth recording rather than dismissing. The
canonical batch entry point routes through the C++ engine; the pure-Python reachability-BFS path is
legacy. But the Python path uniquely implements a loop-bound safety check — a property monitor
constructed from the specification's documented iteration bound — and that capability has no home in
the canonical path, because the property tier that carries loop bounds is excluded at ingestion
(§6.3.5, and Chapter 4 §4.5.3). A capability that exists only on the path the system does not use is
effectively absent, and §6.10 lists it as such.

### 6.3.5 The ingestion layer

Between Module 01's export and Phase D sits a small pure-Python ingestion layer (~205 lines) whose job
is to decide which exported properties are checkable and to put them in a form SPOT will parse. Its
own module docstring documents its scope, which is deliberately narrow.

**Tier gating**, with a stated reason per exclusion: `P1_Structural_Control_Flow` properties whose
atoms are all task-lifecycle atoms are admitted; `P0_Critical_Sentinels` are excluded as
specification self-tests unfalsifiable under any faithful lifting (§6.6); `P2_Quality_Limits` are
excluded for containing arithmetic comparisons no parser accepts as propositions;
`P3_Adversarial_Defenses` are excluded pending correct handling of the `X` operator's finite-trace
strength mismatch; P1 properties referencing `node(...)` atoms are excluded as having no code-side
counterpart. Exact intra-tier duplicate formulas are de-duplicated — measured at 34 of 412 properties
on the real corpus. The result on FLOW-BENCH is the 45 checkable properties Chapter 4 §4.5.2 derives
independently from the same corpus.

**Atom normalization**, and both halves of the choice are load-bearing. `start(T)` and `done(T)`
collapse to a single flat atom for task T. The *collapse* discards lifecycle distinction, which is
lossless only for strictly sequential workflows — true of this corpus, which contains no parallel
gateways, and false in general; §6.6 discusses the alternative that was not taken and what it would
have cost. The *quoting* of the resulting atom is not cosmetic: SPOT's infix parser reads an unquoted
identifier beginning with a reserved operator letter as that operator applied to the remaining
suffix, so an atom named `GitHub_thing` parses as `G(itHub_thing)` — a formula about a different,
nonexistent proposition, silently accepted. Quoting is the difference between checking the property
you wrote and checking one you did not.

This layer reimplements normalization that already exists in Module 01, unused (Chapter 4 §4.8). The
duplication is deliberate: this module has no access to that module's source, and importing across the
boundary would create exactly the coupling the dual-track architecture exists to prevent. It is a real
cost of the architecture, paid knowingly.

---

## 6.4 The semantic gap: LTLf strings meeting an infinite-trace checker

Module 01 exports LTLf — finite-trace semantics. Phase D's parser reads SPOT infix LTL — infinite-trace
semantics. These are different logics that share a syntax, and reformatting a string does not convert
between them. Before any conformance verdict from this system can be believed, that gap has to be
closed by construction.

The reduction that closes it is the standard one: introduce a proposition `alive` that holds on the
finite prefix and is false thereafter, and rewrite the formula so each temporal operator is
relativized to the alive segment. SPOT provides it as `from_ltlf`, and the vendored version (2.11.6)
already incorporates two published errata to that function — a detail worth recording because it
means the reduction is not a hand-rolled rewriting whose corner cases are this project's
responsibility.

The implementation has two halves. On the formula side, the negated property becomes
`Not(from_ltlf(φ, "alive"))`. On the automaton side, `instrument_alive_extension()` builds an
alive-extended copy of the code automaton: every existing edge condition is conjoined with `alive`,
and every state that has no outgoing edge — the terminating states — receives a `!alive` self-loop.
The extended automaton therefore has infinite runs (a finite prefix of real behavior followed by
forever-dead), which is what the infinite-trace machinery requires, and its finite prefixes are
exactly the original automaton's traces.

The reduction is applied conditionally, and the guard is empirically justified rather than
conservative by taste. `from_ltlf`'s well-formedness obligation presumes the trace it is bridging
terminates. Applying it to an automaton with a genuine (non-τ-trivial) cycle manufactures a violation
that has nothing to do with the property, because the bridging formula's own requirement that the
trace eventually stop being alive cannot be met. This was caught concretely: a regression test
asserting the literal tautology `"1"` flipped to `VIOLATION` once the bridge was applied
unconditionally. The shipped code therefore tests the automaton's SCC structure and applies the
bridge only when every SCC is trivial, treating cyclic automata under the pre-existing path.

One corpus fact makes this guard nearly always inactive and is needed to interpret §6.5.6: of the 43
eligible top-level WIR graphs, **0 contain a genuine cycle**. The workflows in this benchmark are
straight-line orchestration sequences. That is convenient for the bridge and it is also a real
scope limit, since the interesting case for divergence sensitivity is precisely the case the bridge
declines to handle. §6.9 takes this up.

---

## 6.5 Channel 1: a complete model checker that could not fail

### 6.5.1 The mechanism

Two facts read from the lifter's source, and one standard result, are sufficient to establish the
defect without running anything.

**Fact one: no acceptance condition is ever set.** The lifter constructs its automaton and never calls
`set_buchi`, `set_acceptance`, or `set_generalized_buchi`. Searched across the whole implementation:
absent.

**Fact two: terminating states are explicitly permitted to have no outgoing edge.** The lifter's
handling of exit nodes leaves them as dead ends by design — reasonable, since a workflow ends.

**The consequence.** A Büchi automaton with no accepting states accepts no infinite word: its
ω-language is empty. Emptiness of the language is preserved by product — an empty language intersected
with anything is empty. Phase D's verdict is derived from the emptiness of the product of the system
automaton with the Büchi automaton of the negated property. Therefore the product is empty for
*every* property, therefore the emptiness check succeeds for every property, therefore every property
returns `COMPLIANT`.

Not "sometimes wrong." Not "wrong on edge cases." Every property, on every terminating workflow,
regardless of what the code does. The one class of input on which the checker could return a genuine
`VIOLATION` was an automaton containing a cycle, since a cycle can carry an infinite run.

### 6.5.2 Why the test suite did not catch it

The Phase D tests passed. They passed because they asserted the behavior the implementation exhibited,
and one of them said so, in `test_finite_automaton_passes_all_properties`
(`test_cpp_engine.py:407`, prior to the fix landed in commit `37a3d81`):

```
assert result.verdict == "COMPLIANT"  # vacuously true
```

The comment is accurate. The property in question *was* vacuously true. And a test asserting the
observed behavior of a vacuous check is syntactically indistinguishable from a test asserting the
correct behavior of a working check. Meanwhile the tests that did obtain real `FAIL` verdicts used a
deliberately looping fixture — the one input class on which the checker functioned — so the suite
contained both a green vacuous case and a green working case, and no test asked the question that
distinguishes them.

The fix itself makes this concrete: that same test was rewritten to
`test_finite_automaton_no_longer_vacuously_passes`, now asserting `result.verdict == "VIOLATION"`
on the branch the old version could never have reached a verdict on. A test that flips from passing
for the wrong reason to passing for the right one is stronger evidence of the defect than a test
that merely continues to pass — the rewrite is itself part of the record, not just a note about it.

That question is: *could this check have failed?* It is not answered by any assertion about the
verdict. It requires either a negative control — a property the input provably violates, expected to
`FAIL` — or reasoning about the machinery independent of its output. This is the chapter's sharpest
methodological point, and it generalizes past this bug: for verification tooling, a passing test
suite is evidence about agreement between implementation and expectation, and a vacuity defect
corrupts both sides at once.

### 6.5.3 Why it stayed dormant

The defect had been present through a period in which Phase D was described as complete and
functioning, and it did not manifest, for a reason that is itself instructive: the only caller of the
compliance check passed a hardcoded placeholder property, `G("approved")`, over an atom no real
automaton registers. Every invocation was already meaningless for a different reason.

So the defect was latent precisely until the module became useful. The moment a real property suite
was wired to a real automaton — the integration this chapter's evaluation performs — it would have
begun returning confident `COMPLIANT` verdicts on every non-looping implementation, including
implementations that ignore most of their specification. The mechanism would have been a silent
false-`PASS`, the worst failure mode available to a verification tool, and it would have appeared at
the exact moment the tool started being trusted.

The general lesson is about integration seams. Both sides of this seam were tested. The property
producer had tests; the property consumer had tests; nothing tested the seam, because nothing crossed
it — the placeholder stood in for the crossing. A module that has never received real input from its
upstream has not been verified against it, however green its own suite is.

### 6.5.4 Confirmation on a real build, and the fix

The prediction was tested at the first opportunity a compiled build existed (Homebrew SPOT 2.15.1 with
pybind11; the vendored container build is 2.11.6). On a two-action non-looping automaton in which
action `B` provably executes, the property `G(!B)` — "B never happens" — returned **`COMPLIANT`**, with
`unmatched_atoms` empty, confirming that both atoms had matched and that the verdict was not an
artifact of the atom gate. The predicted behavior, observed directly, on the real engine.
*(Worked in full as Figure 6.6, `figures/fig_m03_alive_extension_example.pdf`; independently
re-confirmed on uid 44's real extracted WIR, a genuine total task-order reversal, in
`E2E Integration Verification Findings.md`.)*

The fix is the alive extension of §6.4. Extending the automaton gives it infinite runs, so its
ω-language is non-empty, so the product is no longer trivially empty, so emptiness of the product
again means what the Vardi–Wolper construction says it means.

### 6.5.5 The third defect, exposed by fixing the second

Closing a vacuity defect removes a mask, and what was behind this one is worth reporting in its own
right.

Edge labels in the lifted automaton asserted only the positive literal for whatever action fired on
that edge, leaving every *other* registered proposition unconstrained on that edge — including the
entry transition, on which nothing happens at all. While the automaton was vacuous this was harmless:
no run existed for a free variable to matter on. Once terminating automata became genuinely
checkable, the emptiness search could exploit it. Given code that genuinely calls `A` and then `B`, and
the property `!B W A`, the search could satisfy the negation by choosing `B = true` on the entry edge
— an edge that asserts nothing about `B` — and report a violation the code never exhibits.

The fix closes every edge under mutual exclusion: every registered atom not required true by the
edge's own condition is forced false, before the alive extension is applied. Two things make this
worth a subsection rather than a footnote. First, it is the same failure class the atom gate exists to
prevent — a confident verdict about something the code does not do — reached by a completely different
route, which suggests the class rather than the instance is the thing to design against. Second, it
demonstrates that fixing a vacuity defect *creates* exposure: the defects a vacuous checker hides are
not fixed by it, merely unobservable, and they arrive together the moment it starts working.

### 6.5.6 Validating the composite fix

With all three defects closed, the engine's verdicts were cross-validated against an independent
implementation of the same logic under different semantics: Module 01's own finite-trace LTLf
evaluator, applied directly to the code's action sequence. Across all 29 eligible specifications and
58 real property checks, the two agreed on **every check that produced a real verdict — 35 of 35**.
The remaining 23 were `INCONCLUSIVE`: the property referenced a task genuinely never called in that
variant, and the atom gate correctly refused rather than answering.

The significance and the limit belong in the same breath. Two independent implementations — a
compiled Büchi-product model checker over infinite traces with an `alive` bridge, and a direct
recursive evaluator over finite traces — agreeing on 35 of 35 real verdicts is meaningful evidence
that the bridge of §6.4 preserves semantics. It is **not** a detection measurement. Both sides consume
the same property suite, so their agreement says nothing about whether that suite catches bugs;
Chapter 4 §4.6 shows there are bug classes it structurally cannot catch. Agreement of two
implementations of a check is not evidence that the check is the right check.

---

## 6.6 Channel 2: disjoint atom vocabularies

The second channel is independent of the first, was diagnosed separately, and needed a different fix.
It is simply that the two sides of the verification are not talking about the same propositions.

Module 01 emits lifecycle-prefixed atoms: `start_Approve`, `done_Approve`. Phase A's label resolution
takes the matched BPMN task name and registers *that* as the proposition, producing a bare `Approve`;
no lifecycle-prefix construction exists anywhere in the lifter. Both halves are read from source on
both sides.

The consequence measured on the corpus: **0 of 116 spec-side P1 atoms** can match a code-side
proposition, and **0 of 29** specification/variant pairs overlap at all. A model checker whose
property atoms are absent from the automaton it is checking either abstains — the correct behavior
the atom gate now enforces — or, in the presence of channel 1, returns vacuous `COMPLIANT`.

The measurement that identifies this as a *lifecycle-layer omission* rather than a matching-quality
problem is the name-match quality itself: BPMN task name to Python function name matches exactly at
**86.0% on mean across 43 pairs, with 26 of 43 at 100%**. The vocabularies name the same tasks with
the same words. They fail to meet only because one side decorates each name with a lifecycle phase and
the other does not. Had the matcher been poor, the same 0/116 would have arisen from a much less
tractable cause, and the fix would have been a research problem rather than a naming convention.

**Reproduction status,** stated precisely because the two halves differ in strength. The mechanism is
source-verified on both sides. The 0/116 count was measured against a Python emulation of the C++
proposition construction, the compiled engine not being importable in that environment. It was
subsequently confirmed on a real build in the equivalent form: **58 of 58** property checks returned
`INCONCLUSIVE` when unstripped lifecycle atoms reached the checker. The emulated count and the
real-build confirmation agree, and the prose keeps them distinguishable rather than merging them into
a single unqualified claim.

*(Figure 6.2, `figures/fig_m03_two_vacuity_channels.pdf`, sets Channel 1 (§6.5) and Channel 2 (this
section) side by side: mechanism, why the passing test suite missed it, the fix, and the evidence
that the fix works.)*

**Two ways to close it, both costed.** Option A adds lifecycle propositions on the code side: a task
node contributes `start_T` on entry and `done_T` on exit, making the code automaton semantically
richer and preserving the distinction between a task starting and finishing. It requires modifying the
C++ Phase A walk and roughly nine proposition-name assertions in the test suite. Option B collapses
the specification side to flat atoms at ingestion, discarding the lifecycle distinction; it is
confined to the pure-Python ingestion layer and touches no C++.

**Option B shipped.** The justification is a corpus fact rather than convenience: with strictly
sequential workflows the lifecycle distinction carries no information the flat atom lacks, since a
task's start and completion are adjacent in every trace, and the corpus contains no parallel gateways.
The cost is that this is *not* true in general — a specification with genuine concurrency, where task
A starts before task B and finishes after it, has orderings that flat atoms cannot express — so Option
B is a corpus-scoped simplification and §6.10 records it as one.

**The P0 reclassification** belongs here, because it is the same vocabulary reasoning taken to its
conclusion. Module 01's `P0_Critical_Sentinels` tier — 79 of 412 properties — asserts properties of
the specification's own structure. An earlier analysis treated their unfalsifiability as an artifact of
one candidate lifting; the correct statement is stronger. Any *faithful* lifting of an implementation
satisfies these sentinels by construction, because they assert what the lifting itself guarantees. They
are therefore a self-test of the lifting, not evidence about the code. Reporting 79 passed safety
properties would reproduce Chapter 5's central failure — a check that cannot fail, reported as a check
that passed — at this seam, with the specification's authority borrowed to lend it credibility. They
are excluded at ingestion, and the exclusion is a result rather than a policy choice.

---

## 6.7 Supporting architecture: what the automaton is an automaton *of*

Fixing both vacuity channels makes Phase D's verdicts meaningful *about the automaton it is given*. It
says nothing about whether that automaton represents the program's behavior. It did not.

### 6.7.1 The finding

A WIR `task` node, as produced by Module 02's extractor, is a function **definition**, not a business
action. The extractor's own docstring is explicit that a function body is not inlined into the
top-level graph but stored as a separate sub-CFG. And the C++ lifter contains **zero references** to
the WIR field holding those sub-graphs: it never reads them. So the action sequence Phase A lifted was
the order in which functions were *defined in the file*, not the order in which they were *called*.

Measured consequence: definition order disagrees with call order in **47.5% of 184 normalized
variants** (an independent re-derivation by a different method obtained 45.5%; both are reported,
since the spread is the honest precision of a name-matching-based comparison and presenting one as
definitive would overstate it). Nearly half the corpus was model-checked against a sequence the
program does not perform.

A second structural fact, measured over the same 184 variants, closes off the obvious cheap fix.
Top-level graphs contain **0** gateway nodes and **184** task nodes; sub-CFGs contain gateways and
**0** task-typed nodes. Gateways and tasks never appear in the same graph. So the branching structure
of these programs is invisible to a lifter that reads only top-level graphs, and no renaming or
atom-vocabulary change reaches it — only reading the sub-graphs does. Relatedly, every one of the 184
variants has at least one sub-CFG exit with no outgoing edge, which is why the dead-end handling of
§6.4 is a general property of this corpus rather than an incidental one.

### 6.7.2 Why this had to be fixed before the vacuity fixes could be trusted

Fixing vacuity and vocabulary while the lifter model-checks definition order produces a system that
reliably model-checks the wrong automaton. The `COMPLIANT` and `VIOLATION` verdicts would be sound
statements about an object that is not the program. The ordering of the work is itself a result: a
verification pipeline's fidelity to its target dominates the correctness of its verification
machinery, because the machinery's correctness is conditional on the target being right.

### 6.7.3 The decision, made on measured evidence

Whether to switch the lifter from definition order to call order was initially proposed on the basis
of a Python emulation of the compiled engine. That evidence was superseded before the decision was
made, in favor of a measurement against the real engine's first genuine run — 58 checks over 29
variants, verdicts `{VIOLATION: 18, COMPLIANT: 17, INCONCLUSIVE: 23}`, produced after the vacuity fix.

The method: for every non-`INCONCLUSIVE` verdict, reconstruct the ground truth independently from the
orchestrator's actual call sequence, extracted from source, and cross-tabulate against the verdict the
engine produced under definition-order lifting.

**Of 18 `VIOLATION` verdicts:** 12 name at least one task that is **never called at runtime** — the
atom "matched" only because definition-order lifting includes every function defined in the file,
called or not. Spurious by construction. Of the remaining 6, where both atoms are genuinely called,
checking real call order directly confirms 5 as genuine precedence violations and **contradicts 1**
(`77__llama-3.1-8b.py`), where the real call order satisfies the precedence that definition order
reported violated. Net: 5 of 18 confirmed real; 13 of 18 spurious or wrong.

**Of 17 `COMPLIANT` verdicts:** 12 occur on variants independently classified as omission-divergent.
A precedence property of the form `!start(X) W done(Y)` is vacuously satisfied when X never starts
(Chapter 4 §4.6), so these are false-`COMPLIANT`s concealing a real omission defect rather than
genuine order conformance. Net: at most 5 of 17 not already suspect.

**Combined: of the 35 definitive verdicts in the pipeline's first real run, roughly 10 (29%) are
trustworthy as-is; the remaining ~25 (71%) are provably spurious, contradicted by real call order, or
riding on omission blindness.**

That figure decides the question. Definition-order lifting is not a minor precision loss; it inverts
the majority verdict on both sides simultaneously. Any thesis number or demonstration produced against
it would be reporting noise as signal.

One scope warning was recorded with the decision and matters for reading §6.7.6: the omission-driven
false-`COMPLIANT`s are a *different* defect from the ordering-driven false-`VIOLATION`s. Call-order
lifting addresses the ordering side. A task never called remains absent from the automaton under any
ordering scheme, so a precedence property over it stays vacuously satisfiable unless omission is
checked by a separate property class. The 71% needs two fixes; only one was built.

### 6.7.4 The witness argument

Underneath the cross-tabulation is a criterion I want to state explicitly, because it is what makes the
decision defensible even though it lowered the headline detection number.

The value of a conformance tool's `FAIL` is not the verdict. It is the counterexample: a concrete
behavior the developer can inspect, reproduce, and fix. A verdict without an actionable witness moves
work from the tool back to the human.

Now consider one of the 12 spurious `VIOLATION`s. The code *is* divergent — it omits specified tasks.
The verdict `VIOLATION` is, as a bare label, correct. But the witness says "you call B before A" about
two functions that are never called at all. A developer following that witness would inspect two
definitions, find nothing wrong with their relative order, and conclude the tool is broken. The
verdict is right for a demonstrably wrong reason, and the witness is a false explanation of a real
defect.

By that criterion the 12 are not detections. They are coincidences with misleading explanations, and a
metric counting them as successes is measuring the wrong thing. This is why the correct fix *lowers*
the detection rate: it removes accidental agreement, leaving fewer verdicts that mean what they say.
§6.8.6 makes witness quality a measured quantity for exactly this reason.

### 6.7.5 What shipped, and its own bug

`derive_call_order_wir()` is a new entry point alongside the existing extractor rather than a
modification of it. Nothing in the existing extraction path changes, so every existing consumer —
the V3 structural pipeline, the Z3 concolic engine, the test suite — is untouched, which was confirmed
by impact analysis before the change was written.

The mechanism identifies the program's "driver": the top-level function whose body calls the most
sibling top-level functions, resolved through the AST against the exact set of top-level definition
names rather than by regular expression, excluding self-recursion. If no function qualifies, the
module's own trailing top-level statements serve. The driver's control-flow graph is then built with
the extractor's existing, tested body builder — reusing its full branch, loop and guard handling —
and each call site invoking a sibling top-level function is relabeled as a task node with its code
text unchanged, so the C++ action extraction and label matching resolve it exactly as before. No C++
change was required.

One bug surfaced during validation, and it is worth reporting because it is a genuine interaction
between two modules' invariants rather than a typo. A task label attaches only to an edge *leaving*
its node. The body builder — unlike the module-level visitor — leaves its final node with no outgoing
edge. So the driver's last call registered no proposition at all: the automaton silently omitted the
final action of every workflow. Fixed by mirroring the module visitor's entry/exit sentinel pattern.
Neither module's invariant was wrong on its own terms; the defect lived in the composition.

### 6.7.6 The measured shift, traced check by check

Re-running the same 58 checks with call-order lifting:

| | VIOLATION | COMPLIANT | INCONCLUSIVE |
|---|---|---|---|
| Definition order (pre-fix) | 18 | 17 | 23 |
| Call order (post-fix) | **5** | **10** | **43** |

Taken as an aggregate this looks like a regression: definitive verdicts fall from 35 to 15. Traced
check by check, it is the predicted behavior:

- **Old `VIOLATION` (18):** 5 stayed `VIOLATION` — exactly the 5 the cross-tabulation confirmed as
  genuine. 12 became `INCONCLUSIVE`: their atoms genuinely are not in the driver's call sequence, so
  they are now *absent* rather than spuriously present. 1 became `COMPLIANT` — the contradicted case,
  `77__llama-3.1-8b.py`, now agreeing with real call order.
- **Old `COMPLIANT` (17):** 9 stayed. 8 became `INCONCLUSIVE`, reflecting omission on that specific
  property's own atoms — a tighter and more accurate signal than the per-variant proxy used in the
  cross-tabulation.
- **Old `INCONCLUSIVE` (23):** all 23 unchanged. No regressions.

*(Rendered as Figure 6.3, `figures/fig_m03_verdict_shift.pdf`: the flows above as an alluvial
diagram, each band traced from its pre-fix bucket to its post-fix one.)*

Two acceptance cases were named and predicted *before* the change was implemented, and both behaved
as predicted: uid 44, where both atoms are genuinely called and real order does violate the
precedence, stays `VIOLATION`; uid 77 flips to `COMPLIANT`.

The rise in abstentions is correct behavior rather than a shortfall. Once a never-called function is
genuinely absent from the automaton, the atom gate reports `INCONCLUSIVE` instead of a confident wrong
answer — which is the gate doing its job on an input that is now honest about what the program does.
What the change does not do, per §6.7.3's scope warning, is turn omission into `VIOLATION`; that
requires the coverage property class Chapter 4 §4.6 describes as designed and unbuilt.

The change is covered by 7 tests: call-order-not-definition-order, driver identification, the
trailing-edge invariant, never-called-function exclusion, branching and guard preservation,
module-level-call fallback, and self-recursion not being mistaken for the driver.

---

## 6.8 Evaluation: end-to-end conformance detection on FLOW-BENCH

With both channels closed and the lifting target corrected, the pipeline can be measured end to end:
BPMN specification in, Python implementation in, verdict out.

### 6.8.1 Why ground truth had to be manufactured

FLOW-BENCH ships no correctness labels for its LLM-generated implementations. There is no source of
"this real implementation is, or is not, specification-conformant" to measure against. Every rate below
therefore rests on ground truth constructed the same way Chapter 5's evaluation constructs it: take a
real implementation independently confirmed end-to-end conformant ("gold"), inject a mutation whose
effect on conformance is known and verifiable, and check whether the pipeline's verdict flips as the
mutation class predicts.

The consequence must precede the numbers rather than follow them. **All rates below are rates for
injected defect classes.** None is a measurement of how often real LLM-generated implementations
conform to their specifications, and none can be converted into one.

Every rate is reported with a Clopper–Pearson exact-binomial 95% confidence interval, chosen
specifically so the sample sizes are visible in the result rather than hidden behind a point
estimate.

### 6.8.2 The corpus and the funnel

**6 gold specifications** (uids 45, 72, 76, 77, 84, 85): those with both at least one
conformance-checkable property *and* at least one real implementation confirmable end-to-end
conformant for use as gold. That 6 is the end of a funnel — 48 specifications, of which 29 export a
suite, of which 22 have a checkable property (Chapter 4 §4.5.5), of which 6 also have a confirmable
gold implementation. The 48 is itself a project-specific count, not the public benchmark's headline
101.

From those 6: **26 order-mutation trials** (drop-step and swap-adjacent) and **2 verified
order-preserving perturbation trials**. Four constant-perturbation candidates (uids 72, 76, 84, 85)
were discarded for containing no eligible literal to perturb — recorded rather than dropped, since a
discarded candidate is a fact about the corpus.

### 6.8.3 Task-drop defects are frequently unobservable, not merely undetected

The first result reshaped the metric, and was checked empirically rather than assumed.

Dropping a task's own call often removes that task's proposition from what the code-side matcher can
observe at all. When that happens the pipeline reports `INCONCLUSIVE`: it declines to claim an
ordering result about a task it can no longer see happening. That is honest behavior, not a detection
failure — the alternative would be a confident wrong `COMPLIANT`.

Averaging those trials into a single detection rate would therefore produce a misleading number, so
abstention is reported as its own rate and **excluded from the detection denominator**:

> **Abstention rate: 0.462, 95% CI [0.27, 0.67], n = 26.**

It does not happen for every drop. When the dropped task is not the one an applicable property
references, the property remains resolvable, so drop-step splits across all three outcomes.

### 6.8.4 Detection

> **Detection rate: 0.357, 95% CI [0.13, 0.65], n = 14** — of the order-mutation trials where the
> pipeline committed to a verdict, the fraction correctly flagged `VIOLATION` on the same property
> gold satisfied with fully matched atoms.

The aggregate is less informative than the split:

| Mutation kind | n | detected | missed as compliant | abstained |
|---|---|---|---|---|
| `drop_step` | 16 | **0** | 4 | 12 |
| `swap_adjacent` | 10 | **5** | 5 | 0 |

*(Rendered as Figure 6.5, `figures/fig_m03_detection_by_kind.pdf`.)*

Read this way the result is not "the pipeline detects about a third of defects." It is that the
pipeline detects *reordering* half the time it commits, and detects *task omission* **never — 0 of
16**. That is the structural blindness Chapter 4 §4.6 derives from the property shape, arriving here
as an end-to-end measurement: weak-until precedence formulas are vacuously satisfied by omitting the
later task, so the defect class that dominates this corpus (23 of the 43 spec/variant pairs) is
invisible to the tier that carries the conformance checks. Two independent measurements, one on the specification
side and one end-to-end, of the same gap.

The interval is wide — [0.13, 0.65] on n = 14 — and nothing in this chapter treats 0.357 as a
characterization of the pipeline's detection capability. The stable finding here is the *split*, not
the aggregate.

### 6.8.5 False alarms

> **False-alarm rate: 0.000, 95% CI [0.00, 0.84], n = 2** — of verified order-preserving literal
> perturbations, the fraction the pipeline incorrectly flagged `VIOLATION`.

The interval deserves more attention than the point estimate: n = 2 supports an upper bound of 0.84,
which is to say almost nothing. Reporting "0% false alarms" without it would be indefensible.

The denominator is small for a deliberate reason. The unmutated gold variants are **excluded**: they
were selected *because* they already verified `COMPLIANT`, so counting them as false-alarm trials
would be circular — the tool would be scored on reproducing the verdict that qualified the input.
Only the perturbation mutants, novel relative to that selection, are counted. A larger, circular
denominator would have produced a much prettier interval and meant less.

### 6.8.6 Counterexample quality

> **Counterexample quality: 0.800, 95% CI [0.28, 0.99], n = 5** — of the mutations the pipeline
> correctly detected, the fraction whose rendered counterexample named every BPMN task the violated
> property's own formula references.

The rubric is deliberately narrow, and its narrowness is what makes it a measurement: a mechanical
yes/no over the atoms the violated formula itself mentions, not a subjective judgement of
helpfulness. It exists because §6.7.4 made witness validity the deciding criterion in a real design
tradeoff, and a criterion used to decide should be measured rather than asserted. The rendering
itself is the counterexample formatter's job: turn a raw product-automaton run into a readable task
sequence, filtered to the violated property's own atoms.

At n = 5 this is an existence result with a wide interval, not a characterization. What it
establishes is that witnesses generally name the right tasks; what it cannot establish is a rate.

### 6.8.7 What these numbers license

*(The four rates above — abstention, detection, false alarm, counterexample quality — are collected
as a forest plot in Figure 6.4, `figures/fig_m03_forest_ci.pdf`; interval width, not the point
estimate, is the figure's point.)*

**They license:** the assembled pipeline runs end to end on real BPMN specifications and real
LLM-generated implementations and returns verdicts; it detects injected reordering defects when its
propositions resolve; it abstains rather than guessing when they do not, at a measured rate; and its
counterexamples generally name the tasks the violated property is about.

**They do not license:** any statement about how often real LLM-generated implementations conform to
their specifications (§6.8.1); any detection claim for omission defects (0 of 16); any claim about the
behavioral-equivalence capability of Phases A–C, which is unmeasured (§6.10); or comparison with
Chapter 5's detection figures, which measure a different instrument against a different oracle on a
different corpus with different ground truth. Placing 0.357 beside Chapter 5's 0.9952 as though they
were commensurable would be the single most misleading thing this chapter could do.

---

## 6.9 The unresolved tension: vacuity versus divergence

The bridge of §6.4 and the design commitment of §6.3.2 are in direct conflict, and the conflict is
open.

The `alive` reduction requires that the trace it bridges eventually stop being alive. On a trace that
stays alive forever — a genuinely non-terminating program — that requirement cannot be met, so the
bridged formula is violated regardless of what the program does. A hallucinated `while True: pass`
would therefore report `VIOLATION` on *every* property, for a reason unrelated to any of them.

That is precisely the confusion Phase B's divergence sensitivity exists to prevent. Phase B refuses to
merge a divergent state with a terminating one specifically so that "this program diverges" remains
distinguishable from "this program reaches a bad state." The bridge, applied naively, erases the
distinction Phase B was built to preserve, and turns divergence into an indiscriminate violation of
everything.

The recommended resolution is a distinct verdict — a `NON_TERMINATING` outcome, reported separately
from both `VIOLATION` and `COMPLIANT`, so that divergence is diagnosed rather than converted into
false property violations. That is a reasoned design judgement in this chapter and **not** a project
decision, and it is **not implemented**. What ships is the guard: the bridge is applied only to
automata with no genuine cycle, so the collision is sidestepped rather than resolved. On this corpus
the guard is nearly always inactive — 0 of 43 eligible graphs contain a cycle — which is why the
tension has not yet cost anything measurable, and also why the shipped configuration cannot be said
to handle the case where it would.

I present this as an open problem rather than a limitations bullet because it sits at the intersection
of the chapter's two main design commitments, and because the corpus that makes the bridge safe is
exactly the corpus that makes divergence sensitivity untestable. A benchmark containing
non-terminating implementations would force the resolution; this one does not.

---

## 6.10 Limitations

Each limitation is stated with its measured cost in the same sentence.

1. **The behavioral-equivalence capability — Phases A, B and C — is unmeasured.** No artifact in this
   project reports clustering agreement with behavioral ground truth, bisimulation-reduction
   correctness on the corpus, or the realized verification-cost saving from clustering. The capability
   is implemented and unit-tested (142 test functions across 6 files) and not evaluated. This is the
   largest single evaluation gap in the module; it is named rather than estimated, and no Phase-D
   number in this chapter speaks to it.
2. **Witness validity has not been re-measured at corpus scale on the corrected engine.** The
   29%-trustworthy cross-tabulation is a *pre-fix* measurement. The post-fix evidence is the traced
   verdict shift and two named acceptance cases — strong evidence that the change did what was
   predicted, not a fresh witness audit. A corpus-scale re-measurement is future work.
3. **Small samples throughout §6.8.** 6 gold specifications; n = 14 for detection, n = 2 for false
   alarms, n = 5 for counterexample quality. Every interval is wide and every interval is reported.
4. **Injected defect classes only** (§6.8.1). No rate here describes real implementations'
   conformance.
5. **Omission blindness.** 0 of 16 drop-step detections; the coverage property class that would
   address it is designed (Chapter 4 §4.6) and unbuilt.
6. **Branching conformance is structurally unblocked and empirically untestable.** Inlining sub-CFGs
   would dissolve the gateway/task partition of §6.7.1, but no gateway-bearing specification produces
   a property suite at all (Chapter 4 §4.4.1) — 19 of 48 are rejected upstream. The capability and its
   untestability arrived together.
7. **Depth-1 inlining is corpus-scoped.** Sufficient here, where the driver calls business functions
   directly and their bodies are trivial; not sufficient for arbitrary real-world code with nested
   orchestration.
8. **Driver identification is a heuristic** validated on this corpus only. Whether "the top-level
   function calling the most siblings" identifies the orchestrator in general is untested.
9. **Tier-3 semantic matching was unavailable** in the verification environment (§6.3.1), so all
   reported matching behavior reflects tiers 1–2 with an `unlabeled_task` fallback. No measurement here
   reflects the embedding tier in operation.
10. **Loop-bound safety checking has no home in the canonical path** (§6.3.4). It survives only in the
    legacy pure-Python pipeline, because the property tier carrying loop bounds is excluded at
    ingestion.
11. **Two pre-existing test failures persist** in the Python track (a deterministic-hash helper
    absent), unrelated to this work and confirmed unchanged across it.
12. **The `alive` bridge applies only to acyclic automata** (§6.9), which on this corpus means it
    applies to all 43 eligible graphs and has never been exercised on the case that would break it.
13. **Property suites are non-converged by their producer's own gate.** Every conformance verdict in
    this chapter is checked against a suite Module 01 exported under PBCTS non-convergence (Chapter 4
    §4.4.2) — 0 of 48 specifications reach an unqualified `PASS`. This is a condition on reading every
    number above, and it is stated in both chapters deliberately.

---

## 6.11 Summary of contributions

**(1) A two-channel vacuity result for automata-theoretic conformance checking.** Two independent
mechanisms by which a faithfully implemented Vardi–Wolper pipeline returns `COMPLIANT` while proving
nothing: a missing acceptance condition emptying the system automaton's ω-language, and disjoint atom
vocabularies making specification propositions permanently false in the code automaton. Each was
established from source and standard theory before being confirmed on a real build. The accompanying
methodological observation is the transferable part: a passing test suite can *document* vacuity as
intended semantics — here, verbatim, `assert result.verdict == "COMPLIANT"  # vacuously true`
(`test_cpp_engine.py:407`, pre-fix) — because a test asserting the observed behavior of a vacuous
check is indistinguishable from one asserting a working check. The discipline that follows is that no `COMPLIANT` is trusted without an argument that
the check could have failed, and that argument requires a negative control or reasoning about the
machinery, not another assertion about the verdict.

**(2) An executable LTLf-to-LTL bridge at a real module boundary.** Not a semantics discussion: an
implemented `alive`-extension reduction with the termination guard its well-formedness obligation
requires, the guard's necessity demonstrated by a concrete regression (a literal tautology flipping to
`VIOLATION` under unconditional bridging), and the whole cross-validated 35 of 35 against an
independent finite-trace evaluator across 29 specifications and 58 real property checks.

**(3) A measured demonstration that verification-target fidelity dominates verification machinery.**
An automaton lifted from function definitions rather than executed calls produced verdicts of which
~71% were spurious, contradicted, or riding on omission blindness — measured against ground truth
reconstructed independently from the orchestrator's own call sequence, on the real engine, not
emulated. Correcting the lifting target *lowered* the count of definitive verdicts from 35 to 15 while
raising their validity, and the shift was traced check by check against predictions made before the
change was written. The general claim: correctness of verification machinery is conditional on the
target being right, so fidelity must be established first, and a detection-rate decrease can be the
signature of a correct fix.

**(4) The witness-validity criterion, made operational.** That a conformance tool's `FAIL` must come
with a counterexample a developer can act on, applied as the deciding argument in a real design
tradeoff — 12 verdicts rejected as coincidences with false explanations despite carrying the correct
label — and then measured rather than asserted (0.800, 95% CI [0.28, 0.99], n = 5). Verdict-level
accuracy is not the right target for a translation-validation tool; explanation validity is.

**(5) An end-to-end conformance-evaluation harness over real BPMN specifications and real LLM
implementations,** with manufactured-ground-truth provenance stated before its results, honest
abstention reported as its own rate rather than averaged into detection, an anti-circular false-alarm
denominator that costs interval width to buy meaning, and Clopper–Pearson intervals on every rate.

The module's honest summary is this. Both vacuity channels are closed, and the model checker's
`COMPLIANT` now means something it demonstrably did not mean before. The bridge between finite-trace
specifications and an infinite-trace checker is implemented and cross-validated 35/35 against an
independent oracle. The automaton being checked is now an automaton of the program's executed calls
rather than its file layout, and correcting that lowered the headline number for reasons the chapter
traces individually. What remains open is substantial and named: the behavioral-equivalence capability
is unevaluated, omission defects are undetected 16 times out of 16, the divergence-versus-vacuity
tension is sidestepped rather than resolved, and every number rests on 6 gold specifications and on
property suites their own producer could not prove converged. The contribution is not a verified
system. It is a measured account of what it takes to make a verification verdict mean anything at
all, in which the most useful results are the ones where the apparatus was proving nothing and the
tests were green.

---

## 6.12 Correction trail

Every superseded figure and claim, with how it was caught and what replaced it. Nothing was
overwritten; the superseded artifacts remain in the vault with their status recorded.

| What was stated | How it was caught | Correction / what supersedes it |
|---|---|---|
| Detection 53.2% under definition order vs 40.4% under call order | Both figures were produced by a Python *emulation* of the compiled engine, which could not be imported in that environment; the emulation could not see the vacuity defect | **Superseded** by the real engine's pre/post corpus runs (`{18, 17, 23}` → `{5, 10, 43}`) and the 35-verdict cross-tabulation. The direction of the finding held; the magnitudes are not system behavior and are not quoted as such anywhere in this chapter |
| The atom-matching gate closes the vacuity channel | A real compiled build still returned `COMPLIANT` for `G(!B)` with `unmatched_atoms` empty | Two distinct channels. The atom gate closes the vocabulary channel; vacuity required the separate `alive` extension |
| "Phase D complete, real model checking" | The vacuity mechanism was derived from the lifter's source | Accurate for the mechanism, silently wrong for non-looping automata at the time. Caveat recorded in the module's knowledge note |
| P0 sentinels are unfalsifiable *under the candidate lifting* | Re-derivation of the sentinel shape | Stronger and simpler: unfalsifiable under *any* faithful lifting. They are a lifting self-test, excluded at ingestion (§6.6) |
| The definition-order corpus run read as a conformance-detection measurement | The 35-verdict cross-tabulation | It is a walking-skeleton proof that the pipeline runs end to end, not a detection measurement |
| Gateway hard-failure attributed to Phase 3 (Chapter 4 §4.4.1) | Traced the exception path | Raised in the synthesizer's certification step, reported under `"phase": 2`. Counts and set equality unaffected |

One figure is *not* used in this chapter and the reason belongs here. An earlier bridge investigation
reports 12,600 of 12,600 agreement between the `alive` reduction and a finite-trace oracle on
generated formula/trace pairs. Its own verification pass records it as credible but not independently
reconfirmed, resting on a local build that was never reproduced. The load-bearing bridge validation in
this chapter is the 35/35 corpus agreement of §6.5.6 instead, which was reproduced on a working build.
