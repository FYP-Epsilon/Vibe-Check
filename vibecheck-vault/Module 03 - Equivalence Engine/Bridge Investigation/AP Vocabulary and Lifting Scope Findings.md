# AP Vocabulary & Lifting Scope — Investigation Findings (Sessions 2–3)

> Source: Claude Science, Sessions 02 and 03 (2026-07-29), following on from [[P1.4 Bridge Findings|Session 01]].
> Raw artifacts archived alongside this note: [[ap_gap_memo]] / `ap_gap_verification_log.txt`
> (Session 2) and [[i3_memo]] / `i3_verification_log.txt` (Session 3). Session 3 corrects a factual
> error in Session 2 and reframes the whole question — read this note as the current understanding;
> treat Session 2's memo as superseded on the points below.
> This note adds one further layer: independent reproduction of the two most consequential
> Session-3 claims, run directly against the repo rather than trusted from the memo.

## Headline: the vocabulary framing was addressing the wrong layer

Session 2 found that Module 03's lifter emits one bare-task-name atom per action while Module 01
emits `start(T)`/`done(T)` lifecycle atoms, and evaluated four fixes to reconcile the naming.
Session 3 went further and found the real obstruction sits **one layer below naming**:

- **A WIR `task` node is a function *definition*, not a business action.** `node_type="task"` is
  set only in `visit_FunctionDef` (`cfg_extractor.py:474`), whose own docstring says it plainly:
  *"At module level a function definition is an opaque task boundary... the body is not inlined."*
  The recorded code is the literal string `def <name>(...)`. Business calls like
  `approve_loan(score)` become `type="block"` nodes (`visit_Expr`), and Module 03's
  `resolve_task_label` (`lifter.cpp:264-266`) returns `bddtrue` — i.e. ignores — anything that
  isn't typed `"task"`. **Independently confirmed against source, verbatim, including the
  docstring's own framing.**
- **The C++ lifter never reads function bodies at all.** `grep functions module_03_equiv/src/lifter.cpp`
  returns nothing — confirmed, zero hits. The pure-Python lifter *does* read them
  (`lifter.py:145-153`), but lifts each function as its own **separate, disconnected** LTS
  appended to a list — confirmed by reading the loop directly. So neither track can currently
  check a property that spans two business actions living in different functions.
- **Consequence, measured on all 184 normalized FLOW-BENCH variants (881 graphs):** gateway nodes
  and task nodes **never once share a single graph** — gateways only ever appear at the top level
  in 0 cases, task-type nodes only ever appear inside a sub-CFG in 0 cases.
  **Independently reproduced in this session** with a fresh script run directly against the same
  corpus (not the Claude Science session's own code): **0/184**, exact match.
  This is a structural partition, not a labelling gap — no amount of atom-renaming can make a
  property checkable when its two atoms live in two different automata.
- **Correction to Session 2:** Session 2 recorded gateway nodes as receiving `bddtrue` (no atom at
  all). That was wrong. Gateways *do* get an atom today — `resolve_edge_label`
  (`lifter.cpp:222-259`, confirmed) sanitises the guard text (e.g. `score > 50`) into an AP like
  `score_50`. The real gap was never "gateways have no atom"; it's that task and gateway atoms
  are structurally quarantined from each other.

## A second, independently significant defect: definition order ≠ execution order

Because the top-level automaton is a chain of function *definitions*, its order is definition
order, not the order those functions are actually called in. Measured on the real corpus: for
**86/181 = 47.5%** of variants with an orchestrating function, definition order disagrees with
call order (a concrete case: a variant defines a GitHub task then a Jira task, but its
`workflow()` calls Jira first).

**Independently reproduced in this session**, with a different AST-based heuristic for
identifying "the orchestrating function" than Session 3 used: **75/165 = 45.5%**. The denominator
differs (165 vs. 181 — a different detection rule for what counts as an orchestrator), but the
mismatch rate lands in the same range under an independently-written method — this corroborates
the effect is real, not an artifact of one script's specific logic.

**Consequence:** any ordering property checked against the current top-level automaton is checked
against the wrong sequence roughly half the time. Whether this produces *observed* wrong verdicts
today is a separate question — the only current caller of `check_compliance` passes a hardcoded
placeholder property, so this is a **latent defect**, not something that has produced a wrong
result in production. It would become active the moment real ordering properties are wired in.

## The P0 self-sentinel is now *proven* unfalsifiable for any design — not just option (b)

Session 2's reviewer caught that option (b) (splitting each task into `start_T`/`done_T` events)
makes `!done(T) W start(T)` vacuous. Session 3 proved this generalises to **every possible
lifting**, not just (b): any lifting *faithful* to task semantics necessarily enforces "every
`done_T` is preceded by that task's `start_T`" — and that invariant is logically identical to the
property itself. Intersecting the negated property with the space of invariant-respecting models
gives the empty language. **There is no lifting design that could make this property shape
falsifiable** — asking it to fail would require the lifting to be unfaithful. Confirmed by two
independent tools with different trace semantics: SPOT (infinite-trace, product-and-emptiness)
and Module 01's own `evaluate_ltlf` (finite-trace, 1,979 real traces) — same verdict from both.

**Recommendation carried forward:** reclassify Module 01's P0 tier as a **lifting self-test**, not
evidence about the generated code. If a real lifted automaton ever *did* violate `!done(T) W
start(T)`, that would indicate a bug in the lifter, not in the code under test. Certifying it as a
passed safety property would repeat, at this seam, exactly the self-referential-validation failure
mode that is Module 02's own central thesis finding.

## P1 is falsifiable in principle — but not correctly checked in practice, yet

Under the same faithful-lifting invariant, four of Module 01's five property shapes — everything
in the P1 tier (sequence-flow, XOR exclusivity, AND synchronization) — **are** genuinely
falsifiable. This is real discriminating power, and P1, not P0, is where it lives.

**Important correction, caught on review — do not read this as "P1 is safe to wire now."**
"P1 is falsifiable in principle" was proven against an *idealized* faithful-lifting invariant, not
against what the actual C++ lifter currently produces. P1's flagship shape is exactly an
**ordering property** (`!start(B) W done(A)`), and the current lifter's ordering is wrong for
~45–47% of real code, per the defect above. Wiring P1 alone right now would check real ordering
properties against a wrong-order, function-definition-atom automaton for roughly half the corpus.
Session 3's own §5 says as much explicitly ("fixing [the vacuity/vocabulary defects] while
[the ordering defect] stands produces a bridge that reliably model-checks the wrong automaton —
not obviously better than the current honest placeholder"), but its own recommendation list
doesn't carry that caveat through consistently. Treat "wire P1 only" as **not yet a safe
near-term step** — it is downstream of the lifting-scope decision below, not independent of it.

## Confirmed: unmatched atoms cause false VIOLATIONS on correct code

When an atom on the right-hand side of a weak-until is never matched, it's permanently false, and
the property collapses to require the negated left-hand atom to hold forever — i.e. that action
may **never** fire. Any correct code that fires it gets a false `VIOLATION`. This is worse than
vacuity (false green, merely uninformative) — it's false red, which actively misdirects debugging
effort toward a bug that doesn't exist. Confirmed by direct `evaluate_ltlf` experiment, and the
graph-partition finding above shows this is the *expected* outcome under the current lifter for
any property spanning a task atom and a gateway atom, not a rare edge case.

## Two safe near-term actions, independent of the bigger scope decision

1. **Reclassify P0 in the certificate/thesis as a lifting self-test**, never as evidence about
   code correctness.
2. **Gate on atom matching before reporting any violation.** Any property referencing an atom
   that isn't present in the code automaton should yield `INCONCLUSIVE`, never `VIOLATION` (and
   never a silent `COMPLIANT` either). This is cheap, requires no scope decision, and prevents the
   worst failure mode identified across all three sessions.

## What's now a maintainer decision, not a next investigation

Whether and when to change Phase A's scope: lift call-sites (real business actions) instead of
function definitions, and connect the orchestrator's sub-CFG to its callees' so that ordering is
checkable at all (inlining is the simplest route and fixes the ordering defect as a side effect,
since the orchestrator's own body already has calls in execution order). Session 3 sized this
(not proposed it for implementation): it changes lifted geometry substantially, so every
hard-coded state/edge count in the 113 C++ tests is affected, and Phase C's isomorphism check is
state/edge-count sensitive (established in Session 2) — meaning any such change must be applied
uniformly, not selectively. This is a considerably larger change than the split Session 2
originally proposed, and no session has recommended undertaking it on the strength of a memo
alone.

## Corpus scope — stated honestly, not oversold

Every measurement above (both sessions' and this note's independent reproduction) is on the 184
normalized FLOW-BENCH variants in `module_02_extract/eval/variants/normalized/`. That's a real,
substantial corpus, but it reflects one benchmark's LLM-generated coding style (one function per
task, a single orchestrator function). Whether hand-written or differently-structured code shows
the same clean gateway/task partition or the same order-mismatch rate is untested — treat the
0/184 and ~46% figures as strong evidence for *this* corpus, not an assertion about the WIR format
or Python code in general.

## What this changes about the project's priorities

This reframes the AP-vocabulary gap from "a naming problem to fix" into a symptom of something
larger: Module 03's C++ Phase A currently lifts a chain of function definitions, in definition
order, never looking inside function bodies at all. That is arguably foundational to whether the
C++ track models real program behavior *at all* — a question bigger than, and prior to, wiring
Module 01 in. Whether to treat this as blocking ahead of other roadmap items is the maintainer's
call; this note documents the finding, not a reprioritization decision. See the corresponding
update in [[Next Steps]].

## Links

- [[Home]]
- [[Next Steps]]
- [[Module 03 - Equivalence Engine/Module 03 Knowledge|Module 03 Knowledge]]
- [[P1.4 Bridge Findings]] — Session 1 (vacuity + LTLf/LTL semantics)
- [[ap_gap_memo]] · `ap_gap_verification_log.txt` — Session 2 (superseded on the points above)
- [[i3_memo]] · `i3_verification_log.txt` — Session 3
- [[Claude Science Plan]] — investigation prompts and the evidence discipline used across all three sessions
