# VibeCheck — Using Claude Science

> Companion to [[Next Steps]]. Where that doc is the roadmap, this note is *how a Claude Science
> project (persistent Agent Context + long-running research agents) applies to executing it*.
> Snapshot: **2026-07-28** (main @ `7089711`).

## Why a Science project here specifically

VibeCheck already has a working discipline worth encoding once instead of re-deriving every
session: Module 02's thesis chapter is built on a *correction-trail methodology* — every
measured figure states what could invalidate it, three early figures were caught and corrected
this way, and superseded numbers are named explicitly so they never leak back in. A Science
project's Agent Context is the right place to make that a standing habit across the whole
project, not a Module-02-only practice.

## Mapped to the roadmap

- **[[Next Steps#P1 — Close the end-to-end loop (the research-critical path)|P1.4 — the LTLf→LTL bridge]]**
  is the one open research question on the critical path, and the right shape for a dedicated
  research agent *before* any code lands in `module_03_equiv`: which of SPOT 2.11.6's `from_ltlf`
  vs. a manual end-marker encoding integrates more cleanly with the existing
  `translator → product → emptiness` pipeline in `check_compliance`, and how `loop_bound_documented`
  and finite-trace liveness properties interact. Ready-to-use prompt below.
- **P2.7 — e2e evaluation harness.** Module 02's calibration method (Youden's J, stratified
  CALIB/EVAL split, Clopper-Pearson CIs) is the template. Put "always calibrate and report this
  way, following M02's method" directly into Agent Context so every future eval session — not
  just the one that writes it first — inherits the same statistical conventions.
- **Standing correction-trail habit.** Add to Agent Context: *before any measured figure is
  reported, state what could invalidate it and check that specifically.* This is the exact
  practice that saved Module 02's chapter from three bad numbers, generalized into a project-wide
  instruction rather than a one-module artifact.
- **P3.14 — thesis parity (M01/M03 chapters).** Once P1 lands, drafting the missing chapters in
  the same register as the existing Chapter 5 (measured vs. designed always labeled, limitations
  costed not hand-waved) is well suited to a long-running project — Agent Context keeps voice and
  citation discipline consistent across separate drafting sessions months apart.
- **A standing skeptical-reviewer agent.** Mirrors what Module 02 did informally: before a new
  number goes into the thesis, run it past an agent whose only brief is "what would invalidate
  this claim, and did anyone check?"

## Ready-to-use prompt — P1.4 (LTLf→LTL bridge design)

Paste this into a fresh Claude Science agent in the project (Agent Context already carries the
VibeCheck background, so the prompt below only needs to add the task-specific brief):

```
Investigate and design the LTLf→LTL bridge between Module 01 and Module 03 of VibeCheck.
This is a design/research task — produce a memo, do not write implementation code yet.

BACKGROUND YOU NEED
- Module 01 (module_01_spec) exports a property suite via export_for_module_03() as
  module_03_input.json = {semantic_graph, ltlf_property_suite, loop_bound_documented}.
  The properties are LTLf strings across three tiers: P0 safety, P1 liveness, P2 fairness.
  loop_bound_documented is a regex-parsed bound on loop unrolling (from P2_Quality_Limits).
- Module 03's C++ engine exposes check_compliance(code_aut, ltl_string) -> ComplianceResult.
  It is implemented as textbook infinite-trace SPOT model checking: parse_infix_psl on the
  LTL string -> negate -> Buchi automaton via spot::translator (sharing the code automaton's
  bdd_dict) -> spot::product with the code automaton -> is_empty() -> accepting_run() for a
  counterexample (prefix + cycle). This is wired into process_wir_batch() and used in
  practice today, but the only current caller passes a hardcoded placeholder property
  'G("approved")' — never a real LTLf property from Module 01.
- Verified directly against the repo (not just docs): module_03_input.json has zero
  consumers anywhere under module_03_equiv/ — no ingestion code exists at all.
- SPOT 2.11.6 is the vendored version (pinned in both module_01_spec/Dockerfile and
  module_03_equiv/Dockerfile). Any proposed solution must be checked against what 2.11.6
  actually ships, not a newer/older SPOT release.

THE CORE PROBLEM
LTLf (finite-trace linear temporal logic, as used by Module 01) and LTL (infinite-trace,
as consumed by check_compliance) are different semantics over the same syntax — the same
formula can mean different things under each. Feeding an LTLf string into an LTL model
checker without a deliberate translation is not just a type mismatch, it can silently
produce wrong verdicts (e.g. a liveness obligation that's fine to leave unresolved at the
end of a finite trace is not fine to leave unresolved on an infinite one).

WHAT TO PRODUCE
1. Evaluate two candidate approaches and recommend one, with rationale:
   a. SPOT's native from_ltlf() support (confirm it exists and what it does at 2.11.6 —
      typically: translate the LTLf formula into an LTL formula over an alphabet extended
      with an "alive"/tail proposition, encoding finite-trace semantics as a specific
      infinite-trace pattern), then feed the resulting LTL formula through the EXISTING
      check_compliance pipeline unmodified.
   b. A manual end-marker encoding: introduce an explicit "end" atomic proposition and
      rewrite each formula by hand (e.g. constraining what must hold once "end" becomes
      true), verified against the same three P0/P1/P2 tiers Module 01 actually generates.
   Judge primarily on: which is less invasive to the current check_compliance pipeline
   (idiomatic use of spot::translator / spot::product / bdd_dict sharing), and which is
   easier to test and reason about independently.
2. Work out how loop_bound_documented interacts with whichever translation is chosen —
   Module 01's traces are bounded; make explicit whether/how that bound needs to inform
   the alphabet extension or the property translation itself, or whether it's orthogonal.
3. Enumerate and resolve edge cases: empty traces; P1 liveness properties given a bounded/
   finite trace; P2 fairness properties under finite-trace closure; what happens if a
   property is trivially true/false once end-of-trace is reached.
4. Propose a concrete test plan: specific LTLf property + trace pairs (including at least
   one from each of P0/P1/P2) that would catch a wrong translation, before any
   implementation is trusted.
5. State explicitly what this memo is NOT solving (e.g. performance, multi-property
   batching, how process_wir_batch's call site should change) — scope it tightly to the
   semantic bridge decision.

CONSTRAINTS
- Ground every SPOT-specific claim in what 2.11.6 actually provides — if you cannot
  confirm a function/behavior exists at that version, say so explicitly rather than
  asserting it.
- Follow the project's correction-trail discipline: label every claim as verified-against-
  source vs. reasoned-from-general-knowledge, and flag anything uncertain rather than
  presenting it as settled.
- Deliverable is a design memo (markdown), not code.
```

## Links

- [[Home]]
- [[Next Steps]]
- [[Project Status.canvas|Project Status]]
