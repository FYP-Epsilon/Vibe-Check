# Module 01 — Novelty Analysis

> **Scope:** what in `module_01_spec/` is genuinely novel, what is a novel *combination* of known techniques, and what is standard machinery — checked against the published literature (searched 2026-07-30). Written in the project's own register: claims are labeled, prior art is named, and the deltas are stated narrowly enough to defend in a viva.
>
> State analyzed: `main-demo` @ `5c65046` (FINAL). The module's earlier churn (SPOT/HOA Phase 4 built and deleted in a day; SFI/ΔH/PWBE removed) is on record in [[Module 01 Knowledge]] — none of the deleted machinery is claimed below.

## What the module does (one line)

BPMN 2.0 XML → semantic graph → tiered LTLf property suite → mutation-validated suite → PBCTS trace-synthesis certificate — four phases, each behind a hard quality gate, producing a formal specification the rest of VibeCheck verifies code against.

---

## Claim 1 — PBCTS: progression-based *constructive* trace synthesis as a spec-reliability instrument

**The claim.** Phase 4 (`ltlf_progression.py`, `trace_synthesizer.py`, `bidirectional_alignment.py`) uses pure-Python LTLf **formula progression** to *constructively enumerate* satisfying traces `T_spec` of the auto-generated property suite (obligation pruning, memoized branching, `bound_k`, ≤ 200 traces), scores structural coverage (**SCov** = 0.4·node + 0.4·branch + 0.2·depth), bidirectionally aligns `T_spec` against model traces (**EAS_BDA**, an F1-style harmonic mean of precision/recall), gates on **IDCD convergence** (|ΔEAS| < 0.001 for some k ≤ 20), and runs an **SCSL** self-correction loop (≤ 3 rounds) that converts over-specification gaps into `!(F(a & X(b)))` corrections — emitting a Formal Reliability Certificate v2.0 *about the specification itself*.

**Prior art.** Formula progression is a classic technique (Bacchus & Kabanza's TLPlan lineage), and it is alive in the LTLf synthesis literature: [On-the-fly Synthesis for LTL over Finite Traces (AAAI 2021)](https://cdn.aaai.org/ojs/16809/16809-13-20303-1-2-20210518.pdf) expands transition systems directly from LTLf semantics, and [An On-the-Fly Synthesis Framework for LTLf (TOSEM)](https://dl.acm.org/doi/10.1145/3749101) / [Model-Guided Synthesis for LTLf](https://cris.technion.ac.il/en/publications/model-guided-synthesis-forltl-overfinite-traces/) (the MoGuS line) explicitly "compute a satisfying trace of the input formula, then use formula-progression to compute the states on the fly."

**The delta (narrow, defensible).** The literature uses progression to *synthesize strategies* or decide realizability. Module 01 uses it for a different job: **auditing a machine-generated specification** — the synthesized traces are not the product, they are *evidence about the spec*, aligned bidirectionally against independently derived model traces to measure whether the spec over- or under-constrains the process, with a convergence gate and a self-correction loop closing the feedback. We found no published system that (a) progresses an auto-generated BPMN-derived LTLf suite to synthesize witness traces, (b) scores spec quality via bidirectional trace alignment, and (c) auto-repairs over-specification from the alignment residue. The *components* are known; the **instrument** (a quantified reliability certificate for a generated spec) appears original.

**Not claimed.** LTLf semantics and the progression rule set are textbook ([De Giacomo & Vardi, IJCAI 2013](https://www.ijcai.org/Abstract/13/132)). "Pure Python, no SPOT" is an engineering property, not a research claim. Doc targets EAS ≥ 0.90 / SCov ≥ 0.85 are unenforced — only IDCD gates; any thesis claim must say so.

---

## Claim 2 — Mutation self-validation as a *hard gate on the spec generator*

**The claim.** Phase 3 (`mutation_refiner.py` + `adversarial_generator.py`) attacks the module's *own* freshly synthesized suite with 5 mutation operators over bounded-DFS traces, requires **kill ratio δ ≥ 1.0 and C_struct ≥ 1.0** to pass, runs ≤ 3 self-healing rounds that inject synthesized killer properties back into the suite, and adds a simulated adversarial tier (P3) — i.e., a specification does not leave the module until it has demonstrably killed every mutant of its own process model.

**Prior art.** Vacuity detection is mature ([Beer et al., vacuity detection in temporal model checking](https://link.springer.com/article/10.1007/s100090100062) — famously ~20% of IBM specs passed vacuously; [Vacuity in Testing](https://link.springer.com/chapter/10.1007/978-3-540-79124-9_2)). Mutation against specifications is established as a *quality assessment*: [Towards Strengthening Formal Specifications with Mutation Model Checking (2023)](https://www.researchgate.net/publication/376097131_Towards_Strengthening_Formal_Specifications_with_Mutation_Model_Checking), [Property-Based Mutation Testing (Bartocci et al.)](https://arxiv.org/pdf/2301.13615), and [Adaptive Testing for Specification Coverage](https://arxiv.org/pdf/2010.06674).

**The delta.** Prior work measures spec strength or strengthens specs offline, typically with a human in the loop. Here mutation adequacy is an **inline, blocking gate inside an automated spec-generation pipeline**, with the self-healing loop feeding killers back into the artifact it gates. The combination "generator + mutation adequacy gate + killer re-injection + adversarial tier, fully automated per request" is the defensible novelty; each ingredient separately is not.

**Not claimed.** The adversarial tier is *simulated heuristics*, not a real LLM red-teamer — stated in the module's own docs; don't let a thesis sentence imply otherwise.

---

## Claim 3 — BPMN→LTLf synthesis with enforced coverage gates

**The claim.** Phases 1–2 translate BPMN to a tiered LTLf suite (P0 safety / P1 liveness / P2 fairness) with a **dynamic coverage denominator** (every id-bearing XML element counts unless excluded), a `_recovery_pass()` retry, implicit-else guard inference, and *hard failure* (`VerificationException`) below coverage 1.0 — the spec track refuses to emit a partial spec silently.

**Prior art.** BPMN-to-formal-verification is a crowded field: [BPMN→Promela + LTL for SPIN](https://ieeexplore.ieee.org/document/11158756/), [pattern-based generation of temporal specifications](https://arxiv.org/pdf/1406.7000), [BProVe and operational-semantics approaches](https://www.sciencedirect.com/science/article/abs/pii/S0164121221001047), Declare's LTLf constraint templates, and — directly adjacent, 2026 — [LLaMA-PG: verification property generation from BPMN models with LLMs](https://www.sciencedirect.com/science/article/pii/S2666307426000124).

**The delta.** Not the translation itself (well-trodden), but its **accountability regime**: an enforced coverage-≥1.0 gate over a dynamically computed element universe, plus the downstream honesty machinery (tier semantics exported so Module 03 can exclude-with-reasons instead of silently dropping). This is a modest, engineering-flavored novelty; the thesis should frame it as such and lean on Claims 1–2 for research weight.

---

## Honest accounting

- **Standard machinery, no novelty claimed:** BPMN XML parsing, Kripke-style labeling, LTLf syntax/semantics, property templates, DFS trace enumeration.
- **Churn discount:** the novelty scoreboard churned twice (SPOT/HOA lifting, process-mining EAS, SFI/ΔH/PWBE all implemented then deleted). Only what survives at `5c65046` is claimed.
- **Known soft spots a reviewer will probe:** EAS/SCov doc targets unenforced; adversarial tier simulated; PBCTS trace cap (200) and `bound_k` mean the certificate is bounded evidence, not exhaustive; 28 tests exist but the eval evidence for Module 01 is far thinner than Module 02's.

## Sources

- [On-the-fly Synthesis for LTL over Finite Traces (AAAI 2021)](https://cdn.aaai.org/ojs/16809/16809-13-20303-1-2-20210518.pdf) · [TOSEM on-the-fly LTLf synthesis framework](https://dl.acm.org/doi/10.1145/3749101) · [Model-Guided Synthesis for LTLf (MoGuS)](https://cris.technion.ac.il/en/publications/model-guided-synthesis-forltl-overfinite-traces/)
- [De Giacomo & Vardi — LTL/LDL on finite traces (IJCAI 2013)](https://www.ijcai.org/Abstract/13/132) · [Synthesis for LTL and LDL on finite traces (IJCAI 2015)](https://www.cs.rice.edu/~vardi/papers/ijcai15b.pdf)
- [Vacuity detection in temporal model checking (Beer et al.)](https://link.springer.com/article/10.1007/s100090100062) · [Vacuity in Testing](https://link.springer.com/chapter/10.1007/978-3-540-79124-9_2)
- [Towards Strengthening Formal Specifications with Mutation Model Checking](https://www.researchgate.net/publication/376097131_Towards_Strengthening_Formal_Specifications_with_Mutation_Model_Checking) · [Property-Based Mutation Testing](https://arxiv.org/pdf/2301.13615) · [Adaptive Testing for Specification Coverage](https://arxiv.org/pdf/2010.06674)
- [Automated Verification of BPMN Workflows Through Promela and LTL](https://ieeexplore.ieee.org/document/11158756/) · [Pattern-based automatic generation of logical specifications](https://arxiv.org/pdf/1406.7000) · [A formal approach for the analysis of BPMN collaboration models](https://www.sciencedirect.com/science/article/abs/pii/S0164121221001047) · [LLaMA-PG (BPMN property generation via LLMs, 2026)](https://www.sciencedirect.com/science/article/pii/S2666307426000124)

## Links

- [[Module 01 Knowledge]] · [[Module 01 Architecture.canvas|Architecture]] · [[Module 01 Status.canvas|Status]] · [[../Project Overview|Project Overview]]
