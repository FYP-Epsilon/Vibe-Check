# Module 03 — Novelty Analysis

> **Scope:** what in `module_03_equiv/` is genuinely novel, what is a novel *combination*, and what is standard machinery — checked against the published literature (searched 2026-07-30). State analyzed: `main-demo` @ `5c65046` (FINAL): C++/SPOT engine through all phases A–D, M01 property suite ingested, both vacuity channels closed, canonical path `process_wir_batch()`.

## What the module does (one line)

Lifts Module 02's call-order WIR into automata, quotients them by divergence-sensitive stuttering bisimulation, clusters behaviorally equivalent LLM implementations, and model-checks each cluster representative against Module 01's ingested LTLf property suite — returning COMPLIANT / VIOLATION + readable counterexample / honest INCONCLUSIVE.

---

## Claim 1 — Divergence-sensitive equivalence chosen *because of* an LLM failure mode

**The claim.** Phase B compresses lifted automata with **divergence-sensitive** stuttering bisimulation: a silently-infinite τ-loop (the classic hallucination `while True: pass`) is *not* merged with a normal wait state, so the equivalence verdict can never certify code that stops making progress. Implemented twice — Python (Groote–Vaandrager refinement + Tarjan SCC, `stuttering_engine.py`) and C++ (G–V `partition_refinement` + `spot::scc_info` τ-cycle collapse, `lifter.cpp`).

**Prior art.** The theory is settled: De Nicola & Vaandrager established the [correspondence between stuttering equivalence and divergence-sensitive branching bisimulation](https://arxiv.org/pdf/1011.0136); [Groote–Vaandrager gave the efficient algorithm](https://link.springer.com/chapter/10.1007/BFb0032063), improved to [O(m log n) by Groote et al.](https://jfg.win.tue.nl/articles/mlogn_branching_algorithm.pdf); divergence-sensitive bisimulation has been used to [verify concurrent stacks](https://arxiv.org/pdf/1701.06104).

**The delta.** No algorithmic novelty is claimed — the novelty is the **application argument**: selecting divergence-sensitivity as a *requirement driven by LLM hallucination patterns* in generated workflow code, and wiring it into a code-conformance pipeline where plain stuttering equivalence would silently bless deadlocked output. We found no published use of divergence-sensitive stuttering bisimulation for validating LLM-generated code. Thesis framing: "the right known equivalence for a new threat model," not "a new equivalence."

---

## Claim 2 — Behavioral clustering to amortize model checking across N LLM implementations

**The claim.** Phase C groups bisimulation-quotiented automata by **automata isomorphism** (`spot::isomorphism_checker::are_isomorphic`; representative = min states, then min edges), so verifying N sampled LLM implementations costs ≈ #distinct behaviors model-checking runs, and one counterexample indicts an entire behavior class.

**Prior art.** Clustering LLM candidate programs is an active 2025–26 line — but by *sampled execution fingerprints*: CodeT-style exact-output clustering, [Semantic Voting: execution-grounded consensus](https://arxiv.org/pdf/2605.08680), [semantic triangulation vs plurality voting](https://arxiv.org/pdf/2511.12288). These cluster on finite I/O samples to pick a *likely-correct* candidate.

**The delta.** Clustering on a **formal, whole-language equivalence** (isomorphism after divergence-sensitive quotient) rather than sampled I/O equality, and for a different purpose: not candidate selection, but **amortizing formal verification cost** while preserving verdict validity for every member of a class. That combination — bisimulation quotient → isomorphism clustering → per-representative model checking of LLM output — appears original as a pipeline. Caveat to state: equivalence is up to the lifter's atom vocabulary; two programs differing below the WIR's abstraction cluster together by construction.

---

## Claim 3 — The engineered LTLf→LTL bridge: alive-extension with cycle-gating and mutual-exclusion closure

**The claim.** Phase D (`check_compliance`) is textbook SPOT (¬φ → Büchi → product → emptiness → `accepting_run()` counterexample). The novelty sits at the finite/infinite seam, where three engineering findings were discovered, fixed, and validated (PRs #67/#70; [[Bridge Investigation/E2E Integration Verification Findings|full findings]]):

1. **Cycle-gated alive-extension.** A lifted, terminating code automaton has an empty ω-language — every property is vacuously COMPLIANT. Fix: when the automaton has no genuine cycle (`spot::scc_info` all-trivial), check `spot::from_ltlf(φ, "alive")` against an *alive-extended* copy (edges ANDed with `alive`, dead-ends given `!alive` self-loops) — De Giacomo & Vardi's encoding, operationalized; a genuinely looping automaton **skips** the bridge, because bridging a real infinite loop manufactures violations (caught empirically by a regression test).
2. **Mutual-exclusion edge closure.** Edge labels only asserted the positive literal that fired; the emptiness search could pick convenient values for unasserted atoms (e.g. `B=true` on the entry edge) and fabricate violations. Fix: force every registered atom not required true by an edge's own condition to false before alive-extending.
3. **Atom-matching gate → INCONCLUSIVE.** A property referencing an atom absent from the code automaton yields an honest abstention, never a fabricated verdict (plus the quoted-atom grammar hazard: SPOT parses unquoted `GitHub_thing` as `G(itHub_thing)`).

Validated end-to-end against Module 01's independent `evaluate_ltlf` oracle: **100% agreement on all 35 decisive verdicts** over 29 specs / 58 checks; the 23 INCONCLUSIVEs were legitimate abstentions.

**Prior art.** The alive-proposition encoding is [De Giacomo & Vardi (IJCAI 2013)](https://www.ijcai.org/Abstract/13/132), available as SPOT's `from_ltlf`; the LTLf/LTL semantic gap is well studied ([LTLf+/PPLTL+ 2024](https://www.researchgate.net/publication/385822983_LTLf_and_PPLTL_Extending_LTLf_and_PPLTL_to_Infinite_Traces)). LTL model checking of programs via CFA lifting is standard ([Ultimate LTL Automizer](https://ultimate.informatik.uni-freiburg.de/downloads/ltlautomizer/document.pdf), [LTL over C programs](https://ssvlab.github.io/lucasccordeiro/papers/sosym2013.pdf)).

**The delta.** The literature defines the encoding; it does not tell you what happens when the *model side* (a lifted, possibly-terminating, possibly-looping code automaton with partial atom vocabulary) meets it. The cycle-gating decision rule, the mutual-exclusion closure, and the abstention semantics are original, empirically-forced contributions at a seam the theory treats abstractly — plus the honest deferral (what a genuinely non-terminating trace should report against a termination-requiring property is *explicitly undecided*, on record).

---

## Claim 4 — Spec-vs-code conformance as model checking, not process mining, with abstention semantics

**The claim.** The end-to-end loop checks generated *code* against *auto-generated* BPMN properties with **no event logs and no human-written properties**: `property_ingest.py` tier-gates M01's suite (exclusions carry reasons), the EQI gate degrades verification by Module 02's extraction confidence (full / conservative / refuse), and every verdict path can abstain rather than guess. Measured honestly at small n in `demo/eval_e2e/` (abstention 0.462 reported separately from detection 0.357 — not averaged away).

**Prior art.** [Conformance checking](https://en.wikipedia.org/wiki/Conformance_checking) (van der Aalst's line, incl. [declarative/data-aware variants](https://link.springer.com/chapter/10.1007/978-3-319-07215-9_22)) compares *event logs* to models — it needs executions to have happened. BPMN model checkers (BProVe et al.) verify the *model*, not an implementation. LTL software model checking verifies code against *hand-written* properties.

**The delta.** The three-way combination — properties auto-derived from BPMN, model auto-lifted from untrusted LLM code, verdict gated by upstream extraction confidence with first-class INCONCLUSIVE — is, to our search, not published as a working system. This is the project's headline claim, and it is now demonstrated (`demo/e2e_demo.py`) and measured, not just architected.

---

## Honest accounting

- **Standard machinery, no novelty claimed:** SPOT translation/product/emptiness, G–V partition refinement, Tarjan SCC, pybind11 embedding, Sentence-BERT name matching (a convenience tier, not a contribution).
- **Known soft spots a reviewer will probe:** only the node()-free P1 slice is checkable (17.6% of the tier); loop-bound checking currently homeless in the canonical path; the checkable-property scope means the 100%-oracle-agreement figure covers ordering-style properties, not the full suite; clustering validity is relative to the lifter's abstraction; `compute_deterministic_hash` referenced by 2 tests but unimplemented.
- **Provenance discipline:** the two ⛔ findings that forced this design (vacuity channels; definition-order lifting) and their fixes (PRs #67/#70/#73) are fully documented in [[Module 03 Knowledge]] and the Bridge Investigation notes — the novelty story is also a debugging story, which is a strength in a thesis, not a weakness.

## Sources

- [De Nicola & Vaandrager correspondence (state/event, stuttering ↔ divergence-sensitive branching)](https://arxiv.org/pdf/1011.0136) · [Groote–Vaandrager efficient algorithm](https://link.springer.com/chapter/10.1007/BFb0032063) · [O(m log n) branching/stuttering algorithm](https://jfg.win.tue.nl/articles/mlogn_branching_algorithm.pdf) · [Divergence-sensitive bisimulation for concurrent stacks](https://arxiv.org/pdf/1701.06104)
- [De Giacomo & Vardi — LTL over finite traces (IJCAI 2013)](https://www.ijcai.org/Abstract/13/132) · [LTLf+/PPLTL+: extending to infinite traces](https://www.researchgate.net/publication/385822983_LTLf_and_PPLTL_Extending_LTLf_and_PPLTL_to_Infinite_Traces)
- [Semantic Voting: execution-grounded consensus for LLM code](https://arxiv.org/pdf/2605.08680) · [Reducing hallucinations via semantic triangulation](https://arxiv.org/pdf/2511.12288)
- [Ultimate LTL Automizer (LTL software model checking)](https://ultimate.informatik.uni-freiburg.de/downloads/ltlautomizer/document.pdf) · [Model checking LTL properties over C programs](https://ssvlab.github.io/lucasccordeiro/papers/sosym2013.pdf) · [IC3 on control flow automata](https://www.cs.utexas.edu/~hunt/FMCAD/FMCAD15/papers/paper12.pdf)
- [Conformance checking (process mining)](https://en.wikipedia.org/wiki/Conformance_checking) · [Data-aware conformance checking for declarative models](https://link.springer.com/chapter/10.1007/978-3-319-07215-9_22)

## Links

- [[Module 03 Knowledge]] · [[Module 03 Architecture.canvas|Architecture]] · [[Module 03 Status.canvas|Status]] · [[Bridge Investigation/E2E Integration Verification Findings|E2E Integration Verification Findings]] · [[../Project Overview|Project Overview]]
