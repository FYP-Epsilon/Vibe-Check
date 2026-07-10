# Module 02 Thesis Chapter — Outline, Narrative Decisions, and Master Numbers Table

> Working scaffold for the Module 02 chapter (chapter number TBD — Module 01's docs map to "Chapter 4",
> so this is drafted as **Chapter 5** with section numbers 5.x; renumber trivially at assembly time).
> Draft prose lives in `module02_chapter_draft.md`, section by section.

---

## The three narrative decisions (made deliberately, before drafting)

**Decision 1 — Lead with the negative result, don't bury it.**
The chapter's intellectual spine is the finding that *self-referential validation cannot detect logic
bugs*: a certificate whose oracle is derived from the code under test structurally cannot see semantic
deviation (measured: 0/220 on the first properly-measured corpus). Everything that follows — the
differential mode, the base-WIR-as-spec oracle, the comparison-mode rule — is presented as the
*consequence* of taking that result seriously, not as the plan all along. This is honest (it wasn't the
plan) and it is stronger rhetorically: the chapter demonstrates the empirical loop working, not a
straight line that never existed.

**Decision 2 — The correction trail is methodology, not embarrassment.**
Three headline measurements were invalidated and corrected during the project (function-selection bug →
self-mode calibration re-run; early-return no-op operator + corpus-wide line-shift artifact → corrected
three-figure calibration; V2-masking → composition fix). Each correction is reported as a
finding-with-evidence, each superseded report is archived in-repo (`eval/results/archive/`), and the
chapter cites the trail explicitly as its answer to "how do you know your *measurements* are right?".
One dedicated subsection (§5.6.5 "Measurement validity and the correction trail") carries this.

**Decision 3 — Scope every claim to what was measured; never use the old numbers.**
- The certificate certifies **code↔WIR extraction fidelity** (self-mode); **bug detection** is a
  property of **differential mode** (base-WIR-as-spec) and, in the full system, of Module 03.
- "≥95% detection" appears nowhere as a target; measured values with exact binomial CIs appear instead.
- Superseded figures that must NOT appear as current: 429 mutants (now 427), E3 r=0.62 (now r=0.41/0.56),
  any pre-correction per-operator detection number, the three-term certificate formula, EQI, WIR-Type
  layers, QCE as a live defense.

---

## Chapter structure (with per-section content notes)

### 5.1 Introduction: the code track's burden of proof  [DRAFTED — see draft file]
Role in VibeCheck's dual track; why M03's verdict is only as good as the WIR it consumes; the two
questions the module answers (fidelity, and — in differential mode — behavioral conformance); chapter
roadmap; contributions list (forward references).

### 5.2 Background and related work
Reuse/adapt the still-valid literature sections from `docs/module_summery/Module_02_Verified_IR_Extraction.md`
(post-rewrite) — translation validation (CompCert, Pnueli), concolic testing (k-bounding), differential
testing, trace equivalence abstractions, mutation testing for evaluation, FLOW-BENCH. Add: PEP 669
(sys.monitoring) as enabling instrumentation. Keep short — M01/M03 chapters cover shared background.

### 5.3 Design: the WIR and the three-layer certificate
- 5.3.1 WIR: statement-level CFG (nodes/edges/guards/functions/dominators), schema-validated; the
  bookkeeping-node contraction (F1) as a design refinement with its measured effect (E2 precision
  0.8255→1.0 with recall constant — evidence the gap was representational, not extractive).
- 5.3.2 V3 structural extraction & the fidelity gate; CNF guard flattening; dominators.
- 5.3.3 V2 bounded concolic (Z3): k-bounding, branch-negation exploration, incremental solving (O(n)
  blocking clauses), container seeding + concrete len(), coverage-credit; *what was removed*: QCE state
  merging deleted as never-wired dead code (honesty note, §5.7 backs it).
- 5.3.4 V1 dynamic differential: monitoring-first tracer (PEP 669 BRANCH events; settrace fallback,
  parity-tested), WIR reference interpreter with exec environment, task-observable trace abstraction
  (task events + branch decisions + exceptions + return values), guard-literal input pooling
  (round-robin), LCS alignment with stutter elimination.
- 5.3.5 Certificate composition: v3 as abort gate; combined = 1−(1−v1)(1−v2) in self-mode; the
  vacuous-verdict episode as the motivating design evolution (formula originally included (1−v3);
  saturated to 1.0 for any extractable program; removed). This is the first beat of Decision 1's arc.

### 5.4 The central result: self-referential validation and the differential architecture
- 5.4.1 The negative result: mutant-vs-own-WIR cannot detect logic bugs — mechanism (oracle re-derived
  from mutated source diverges identically) + measurement (0/220 across all operators).
- 5.4.2 Differential mode: base-WIR-as-spec; the observation-layer/oracle separation principle
  (WHERE to watch may come from the code under test; WHAT to expect must not) — the anti-circularity
  line, stated as a design rule.
- 5.4.3 What it took to make it work (each an ablation-style before/after): exec-env for the reference
  interpreter; task-event alignment on stub calls; branch decisions (F2); string-literal pooling +
  V1-only verdict (Session A); return-value observable (B1). Table: detection climbing
  0.00 → 0.43 (artifact-inflated) → 0.9286 → 0.9571 → 0.9952 with each cause explained.
- 5.4.4 The comparison-mode rule: strict (shared lineage) vs task_only (independent implementations);
  the D3 control table as the data-driven defense (negate-guard 14/14→4/14, constant-perturb 8/9→2/9
  under task_only) and C5b's 0.25→0.10 as the payoff.

### 5.5 Implementation notes (short, selective)
FastAPI /verify with typed per-layer statuses; sandboxing model and its stated trust boundary; the
wall-clock timeout and the measured GIL boundary (thread timeouts bound GIL-releasing hangs only —
verified empirically; process isolation named as future work); CPython ≥3.12 scope.

### 5.6 Evaluation
- 5.6.1 Corpus construction: FLOW-BENCH conditional-OOTB (101 reference sequences; provenance and the
  no-labels finding) → executable corpus via the adapter (attribute→subscript rewrite, typed guard
  params, dict-echo stubs); 427 single-site mutants across 9 applicable operators (10 implemented);
  the multi-implementation corpus (3 NIM model families × 101 uids → 294 raw → 184 screened →
  20 admitted + 164 natural-bug via N=100 behavioral admission).
- 5.6.2 Anti-circularity rules (stated as methodology): independent gold labeler for E2 (import-ban
  enforced by test, human-validated on 10 sampled programs); code-vs-code ground truth for E3 and
  admission (WIR never touches the ground-truth side).
- 5.6.3 Calibration protocol: CALIB/EVAL split stratified by tag; Youden's J; τ=0.10 frozen before
  evaluation; three-figure reporting (genuine-bug detection / equivalent-mutant specificity /
  false-alarm on untouched bases) and why the split matters (equivalent mutants are label noise, not
  misses).
- 5.6.4 Results (the master table below, plus per-operator tables, E2, E3, C5a/b/c, D3).
- 5.6.5 Measurement validity and the correction trail (Decision 2's subsection): the three invalidated
  measurements, how each was caught (instrument cross-checks, advisor review, reading generated
  artifacts), and the archive as auditable evidence.

### 5.7 Limitations (each measured or empirically bounded, none hand-waved)
Per-guard-site literal coverage (the 1/210 constant-perturb straggler, diagnosed); numeric-literal
pooling absent (V2 covers numeric boundaries); GIL-monopolizing timeout gap; N-bounded behavioral
equivalence (admission + E3); V2 masking in *self-mode* composition (differential mode fixed; self-mode
retains the OR-composition by design since it measures fidelity); import allowlist and visit_Attribute
as documented boundaries (normalization covers the eval corpus); small-n caveats (C5b n=20, equivalent
specificity n=9); single sample per (uid, model) in the variant corpus.

### 5.8 Summary of contributions
(1) the self-referential-validation negative result; (2) WIR-as-spec differential verification with the
observation/oracle separation rule; (3) the data-defended dual comparison mode; (4) the evaluation
package (adapter, mutation corpus, behavioral admission oracle, natural-bug corpus, three-figure
calibration, independent-gold structural F1); (5) the auditable correction-trail methodology.

---

## Master numbers table (every figure with its in-repo source; use ONLY these)

| Figure | Value | Source |
|---|---|---|
| Test suite | 246 passing | `module_02_extract` pytest, post-Session-B |
| Base corpus | 101 programs (FLOW-BENCH conditional-OOTB) | `eval/corpus/`, `inputs/conditional_ootb.yaml` |
| Mutants | 427 single-site, 9 applicable operators (10 implemented) | `eval/manifest.json`, `eval/mutate.py` |
| Genuine-bug detection (strict, EVAL) | **0.9952** (95% CI [0.974, 1.000], n=210) | `eval/results/calibration_report_differential.md` |
| False-alarm, untouched bases | **0.0588** (95% CI [0.012, 0.162], n=51) | same |
| Youden's J / τ | 0.9600 / 0.10 (frozen on CALIB) | same + `eval/threshold.json` |
| Equivalent-mutant specificity | 0.111 (n=9; 8/9 score exactly = own base — inheritance, not misjudgment) | same, figure-2 section |
| Per-operator (strict) | all 1.000 except constant-perturb 8/9 (straggler diagnosed) | same, per-operator table |
| E2 structural accuracy | node & edge P/R/F1 all **1.0000** (pre-contraction: node 0.8255/1.0/0.9044, edge F1 0.6827) | `eval/results/e2_structural_report.md` (+archive) |
| E2 gold validation | 10/10 human-checked, zero gold errors | `eval/results/e2_manual_check/VERDICT.md` |
| E3 correlation | Pearson r=0.4085 full / 0.5580 restricted; Spearman ρ=0.5400 / 0.5988; 427 pairs, 11 equivalent | `eval/results/e3_correlation_report.md` |
| Variant funnel | 294/303 raw (qwen outage documented) → 184 screened → 20 admitted + 164 natural-bug | `eval/results/multi_impl_report.md` |
| Natural-bug detection (strict, post-B1) | **164/164 overall; logic-class 68/68 (from 62/68=0.9118)** | `eval/results/session_b_report.md` gate 1 |
| Natural-bug detection (task_only, post-B1) | 153/164 = 0.9329; logic-class 60/68 = 0.8824 (from 0.7794) | same, gate 2 |
| Implementation-freedom FA | strict 0.25 (5/20) → task_only **0.10** (2/20); both residual flags exception-driven | `eval/results/cross_impl_mode_report.md` |
| D3 control (task_only on mutants) | detection 0.8952; negate-guard 4/14; constant-perturb 2/9 | same, D3 table |
| Extraction robustness on variants | 0 aborts, 0 crashes, node_coverage 1.0 (n=20) | `eval/results/multi_impl_report.md` C5a |
| Return-value observable effect | logic 0.9118→**1.0000** (strict), 0.7794→**0.8824** (task_only); FA unchanged; E3 byte-identical (mechanism explained) | `eval/results/session_b_report.md` |
| Self-mode negative result | 0/220 detection across all operators (properly-measured run) | archived self-mode report + `tests/test_integration.py` docstring |
| GIL timeout boundary | GIL-releasing hang bounded ~0.22s @ 0.2s budget; GIL-monopolizing statement not bounded (measured) | `eval/results/session_b_report.md` B3 |

**Figures/tables to produce for the chapter** (from `eval/results/e3_pairs.csv` + reports):
F1: dual-track architecture diagram (adapt wiki Home ASCII → proper figure). F2: pipeline stages of
/verify. F3: detection-climb table/plot across sessions (the 5.4.3 arc). F4: three-figure calibration
bar chart with CIs. F5: E3 scatter (1−confidence vs semantic_diff_rate, 427 points, equivalents marked).
F6: per-operator strict-vs-task_only paired bars (D3). F7: variant funnel Sankey-style. T-series: master
table, per-operator table, mode-tradeoff table, correction-trail table (what was wrong / how caught /
corrected value / archive pointer).
