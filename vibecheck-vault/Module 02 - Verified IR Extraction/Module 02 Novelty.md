# Module 02 — Novelty Analysis

> **Scope:** what in `module_02_extract/` is genuinely novel, what is a novel *combination*, and what is standard machinery — checked against the published literature (searched 2026-07-30). State analyzed: `main-demo` @ `5c65046` (FINAL). This module also has the strongest *measured* evidence base in the project (see [[Module 02 Knowledge]]), which matters: novelty claims below can point at committed numbers, not intentions.

## What the module does (one line)

Takes untrusted LLM-generated Python workflow code and produces (a) a schema-validated **Workflow Intermediate Representation** (WIR — a JSON CFG) in two views, and (b) a **three-layer, calibrated confidence certificate** (V3 structural gate, V2 Z3 concolic, V1 differential dynamic tracing) — the code track of a post-hoc translation-validation pipeline.

---

## Claim 1 — Post-hoc translation validation of LLM codegen with a *quantified* certificate, no annotations required

**The claim.** VibeCheck treats each generated program as untrusted input and validates it after the fact — no proof annotations, no cooperation from the generator, no natural-language re-reading of the prompt. The output is not a boolean but a **calibrated confidence certificate**: `combined = 1 − (1−v1)(1−v2)` in self-mode, `combined = v1` in differential mode, acceptance ≥ 0.95, with typed per-layer statuses so a failed layer degrades honestly rather than silently.

**Prior art.** Translation validation (validate each compilation run rather than the compiler) is Pnueli's line, recently revived for LLMs: [Towards Formal Verification of LLM-Generated Code from Natural Language Prompts (arXiv 2507.13290)](https://arxiv.org/abs/2507.13290) (Astrogator: verifies LLM-generated Ansible against a formal query language — 83%/92% verify/reject rates); VERT (Rust transpilation validated against WebAssembly oracles); the "vericoding" wave — [VeCoGen](https://arxiv.org/pdf/2602.13851)-style systems that *co-generate* formally verified code; and surveys like [the dual-perspective review on LLMs and code verification (2025)](https://www.frontiersin.org/journals/computer-science/articles/10.3389/fcomp.2025.1655469/full).

**The delta.** Three distinctions hold up against that literature: (1) the **spec source is a BPMN business process**, not NL prompts or hand-written contracts — the checkable truth is the diagram, via a dual-track design where the code track never sees it; (2) the verdict is a **graded, threshold-calibrated certificate** with per-layer evidence rather than verified/not (Astrogator, VERT, vericoding are boolean-by-construction); (3) the composition itself was **empirically corrected** — when evaluation showed V2's self-referential score padded every verdict in differential mode, the formula was changed to `combined = v1` and the old 3-term V3 formula was removed as vacuous, both documented with the failure that motivated them. We found no published LLM-codegen validator that ships a calibrated probabilistic verdict with this kind of composition audit trail.

**Not claimed.** "Multi-modal certificate" as a headline: V2 contributes ≈ nothing on the current corpus (container-shaped inputs force V1 fallback) — this caveat is now in the module's prominent docs (PR #83) and any novelty statement must carry it.

---

## Claim 2 — The WIR: a schema-first workflow IR extracted *from* code, with a conformance-oriented call-order view

**The claim.** `shared_schemas/wir_schema.json` defines a JSON CFG (12 node types, guarded edges, dominators, control/data variable classification, nested per-function sub-WIRs) that is the *contract* between producer (this module) and consumer (Module 03). `/verify` returns **two views**: definition-order `wir`, and `call_order_wir` (D2, `call_order_view.py`) — the driver function's own CFG with sibling call sites lifted to task boundaries, i.e., business actions in execution order, which is what conformance lifting actually needs (the definition-order view disagreed with call order in ~46% of real corpus variants — measured, and the motivating defect for D2).

**Prior art.** Control-flow automata as verification IRs are standard in software model checking ([IC3 on control flow automata](https://www.cs.utexas.edu/~hunt/FMCAD/FMCAD15/papers/paper12.pdf), [Ultimate LTL Automizer](https://ultimate.informatik.uni-freiburg.de/downloads/ltlautomizer/document.pdf)). On the workflow side, [FLOW-BENCH/FLOW-GEN (arXiv 2505.11646)](https://arxiv.org/abs/2505.11646) uses Python as an intermediate representation — but in the *generation* direction (NL → Python → BPMN).

**The delta.** The extraction direction plus purpose: recovering a **workflow-level** IR from untrusted generated Python whose atoms are meant to meet BPMN-derived properties halfway, schema-validated as a cross-container contract, with the call-order view added *additively* (existing consumers unbroken) after a measured defect. It is IR engineering rather than deep theory — but it is the load-bearing artifact of the whole pipeline, and we found no direct equivalent for LLM workflow code.

---

## Claim 3 — Differential dynamic validation: PEP 669 tracing vs a WIR reference interpreter

**The claim.** V1 executes the real code under a PEP 669 `sys.monitoring` tracer (settrace fallback + parity tests) and compares against an *interpretation of the WIR itself* (reference interpreter), with LCS trace alignment, strict vs `task_only` modes, and **return values as first-class trace events** (a fix that measurably moved logic-bug detection from 91.18% → 100% same-lineage / 77.94% → 88.24% cross-implementation). The oracle is the extracted model — so V1 simultaneously validates the code *and* the extraction: a trace mismatch means the WIR does not faithfully represent the code.

**Prior art.** Differential testing and runtime conformance are old ideas; process-mining conformance checking compares logs to models ([conformance checking overview](https://en.wikipedia.org/wiki/Conformance_checking)). Concolic execution with Z3 (V2) is textbook.

**The delta.** Using the extracted IR's own reference interpretation as the differential oracle to certify *extraction fidelity* (rather than code correctness against an external spec) is a clean, narrow contribution — it is what makes the WIR trustworthy enough for Module 03 to model-check. The PEP 669/parity-test engineering is quality work but not research novelty.

---

## Claim 4 — Verdict calibration as methodology: Youden's J, frozen thresholds, CIs, anti-circularity

**The claim.** The acceptance threshold is not hand-picked: stratified CALIB/EVAL split over a 427-mutant corpus (10 operators, FLOW-BENCH-derived), τ chosen by **Youden's J** (frozen at τ=0.1, J=0.96, differential-corrected), every reported rate carrying a **Clopper-Pearson CI**, a multi-LLM natural-bug corpus with behavioral admission (20/164), archived pre-fix reports as an audit trail, and explicit anti-circularity rules in the thesis chapter.

**Prior art.** Youden's J for threshold selection is standard classification methodology, lately fashionable in LLM-evaluation work ([Balanced Accuracy via Youden's J, 2025](https://arxiv.org/pdf/2512.08121); [VERDI's Youden-threshold review gating](https://arxiv.org/html/2605.11334v1)). Mutation testing for detector evaluation is standard.

**The delta.** Treating a *formal-ish verification tool's verdict* as a classifier to be calibrated — with frozen thresholds, held-out evaluation, and a published correction trail (three early figures caught and corrected, superseded numbers named) — is rare in the verification literature, which mostly reports soundness arguments rather than operating points. This is a **methodological** novelty claim: modest but well-evidenced, and it's the template the E2E harness (`demo/eval_e2e/`) reuses.

---

## Honest accounting

- **Standard machinery, no novelty claimed:** Python `ast` CFG construction, dominator computation, Z3 bounded concolic execution, LCS alignment, mutation operators as a genre, Docker/FastAPI plumbing.
- **Known soft spots a reviewer will probe:** V2 ≈ 0 contribution (certificate is V1-driven); equivalent-mutant specificity 0.1111; numeric-boundary blind spot (uniform −100..100 sampling); GIL-monopolizing hangs not preemptible (B3's own docstring says so); `pyyaml` missing from requirements for eval.
- **Numbers to quote (with their n):** genuine-bug detection 0.9952 (n=210); false-alarm 0.0588 (n=51); WIR structural F1 1.0 (101 programs); natural-bug 1.0 strict / 0.9329 task_only (n=164).

## Sources

- [Towards Formal Verification of LLM-Generated Code from Natural Language Prompts (Astrogator, arXiv 2507.13290)](https://arxiv.org/abs/2507.13290)
- [A dual-perspective review on LLMs and code verification (Frontiers in CS, 2025)](https://www.frontiersin.org/journals/computer-science/articles/10.3389/fcomp.2025.1655469/full) · [Evaluating LLM-generated ACSL annotations](https://arxiv.org/pdf/2602.13851) · [VeriBench](https://openreview.net/pdf?id=rWkGFmnSNl)
- [FLOW-BENCH: Towards Conversational Generation of Enterprise Workflows (arXiv 2505.11646)](https://arxiv.org/abs/2505.11646) · [IBM/flow-bench on GitHub](https://github.com/IBM/flow-bench)
- [IC3 Software Model Checking on Control Flow Automata](https://www.cs.utexas.edu/~hunt/FMCAD/FMCAD15/papers/paper12.pdf) · [Ultimate LTL Automizer](https://ultimate.informatik.uni-freiburg.de/downloads/ltlautomizer/document.pdf)
- [Conformance checking (process mining)](https://en.wikipedia.org/wiki/Conformance_checking)
- [Balanced Accuracy / Youden's J in evaluation (2025)](https://arxiv.org/pdf/2512.08121) · [VERDI: confidence estimation with Youden-threshold gating](https://arxiv.org/html/2605.11334v1)

## Links

- [[Module 02 Knowledge]] · [[Module 02 Architecture.canvas|Architecture]] · [[Module 02 Status.canvas|Status]] · [[module02_chapter_draft|Thesis Ch. 5 draft]] · [[../Project Overview|Project Overview]]
