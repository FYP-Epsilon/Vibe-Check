> [!info] Purpose
> Poster-ready evaluation summary for Module 01, Module 02, Module 03, and the full project, all against the IBM FLOW-BENCH dataset. This page is the single source of truth for the numbers — link to it rather than re-typing figures on slides/posters, so a future correction only has to happen in one place. M02/M03/full-pipeline figures are dated pre-PR #88 (2026-08-02); PR #88 (`feat/mod1/improve-reliability`, merged) does not change those. M01's section was rewritten 2026-08-02 after a dedicated FlowBench evaluation session found 3 real defects (see that section) — those are diagnosed but **not yet fixed**; re-check this page once the follow-up fix session lands before citing M01's numbers as final.

## Why FlowBench has no "accuracy" number to just look up

[FLOW-BENCH](https://github.com/IBM/flow-bench) (Isahagian et al. 2025, arXiv:2505.11646) gives 101 natural-language→BPMN generation samples plus ~48 real BPMN diagrams — but it ships **no correctness labels** (buggy vs. correct implementation). It's a generation benchmark, not a bug-detection benchmark.

So every module in this project builds its own ground truth **by mutation**: take a real FlowBench-derived program or spec, inject a defect with a known effect (or use a real, independently-confirmed-correct/incorrect implementation), and check whether the module's verdict flips the way the defect predicts. This is the one idea to put on the poster before any number — it's what makes "94% detection rate" a meaningful claim against an unlabeled dataset rather than a made-up figure.

One consequence: **the three modules are not evaluated the same way**, because they sit at different points in the pipeline and have different amounts of mutation-eval infrastructure built out. A single "accuracy" row across all three would misstate what each number actually means. Treat each module's box below as its own claim, with its own caveat.

---

## Module 01 — Specification Engine (BPMN → LTLf property suite)

**Method**: a dedicated FlowBench evaluation design session (2026-08-02) closed the "no standalone number" gap identified earlier — and in doing so, found and independently re-verified **3 real defects in mainline**, not a clean detection-rate figure. This is a methodology-found-defects result, not a success metric — treat it that way on the poster: it demonstrates the evaluation methodology works (it caught real problems), not that Module 01 is currently sound end-to-end.

**Why "detection rate" isn't the right shape of number here.** Unlike M02 (mutating code, checkable by execution) or M03 (agreement with an external oracle), M01 turns a *diagram* into a *property suite* — there is no "run it and compare" oracle. The chosen primary metric is **suite soundness**: does the synthesized property suite hold on traces of the very diagram it was derived from? A suite that rejects its own source diagram is definitely wrong; a suite that accepts it is necessary but not sufficient for correctness (see caveat below).

| What | Result |
|---|---|
| Unit tests | 35/35 passing (`module_01_spec/tests/`, re-derived baseline, 2026-08-02 — supersedes an earlier "28" figure from before 7 test files were added) |
| **Suite soundness** (does the suite accept its own source diagram?) | **55/100** (`output/` corpus), **24/48** (`context/` corpus), 95% CI [45–65%] / [35–65%] |
| Soundness, stratified by branching | **0/50** on diagrams containing a branch (95% CI [0–7%]) vs. **79/98** on non-branching diagrams (95% CI [71–88%]) — Fisher p = 2.5×10⁻¹⁵ |
| Structural extraction fidelity (node/edge P/R/F1, independent gold labeler) | 1.0000 / 1.0000 / 1.0000 on both corpora — saturated, kept as a regression guard, not a headline (identical in shape to M02's own structural metric — would be borrowed framing as a headline) |
| Discriminative mutation kill ratio (mutants killed by an actual property, not by graph disconnection) | **0/1580** (95% CI [0.00–0.23%]) on diagrams that pass the soundness gate — the existing kill-ratio gate currently measures graph connectivity, not property strength |

**The three defects found** (diagnosed, not yet fixed — see [[Module 01 - Specification Analysis/FlowBench Evaluation Investigation/M01 FlowBench Evaluation Methodology|full memo]]):
1. A hardcoded LTLf property contains a comment M01's own evaluator can't parse — Phase 4 fails on **100% of both FlowBench corpora (148/148 diagrams)**, invisible because the top-level status still reads `PASS_PBCTS_UNCONVERGED`.
2. The mutation auditor scores "disconnected, no traces" as a kill without ever checking a property — this is *why* the kill-ratio figure above is 0/1580: every kill in the sound-suite population is disconnection, never a caught property.
3. The `P4_Task_Coverage` tier asserts every task eventually completes, unconditionally — false by construction for any task on a branch's untaken path. This is the direct cause of the 0/50 branching-diagram figure above.

**Honest caveat for the poster**: present this as *"a rigorous evaluation methodology applied to Module 01 found that its property-suite self-soundness is 55% overall and 0% on branching diagrams, tracing to 3 identified defects"* — not as a pass/fail grade on the module. All three defects are being fixed in a follow-up phase before any harness or headline number is finalized; this snapshot is honestly a mid-investigation state, not a concluded evaluation.

---

## Module 02 — Verified IR Extraction (code ↔ IR equivalence checking)

**Method**: mutation testing on a 101-program FlowBench-derived corpus, plus a second independent corpus of real bugs from 3 different LLMs' code generations. This is the most mature evaluation in the project — verified directly against the source reports below, not just summarized.

| Metric | Result | n | Source |
|---|---|---|---|
| Genuine-bug detection (synthetic mutants, differential mode) | **99.52%** [95% CI 97.4–100%] | 210 | `calibration_report_differential.md` |
| False-alarm rate (correct code wrongly flagged) | **5.88%** [1.2–16.2%] | 51 | same |
| Natural-bug detection — real LLM-generated code, strict mode | **100.00%** (164/164) | 164 | `session_b_report.md` |
| Natural-bug detection — task_only (cross-implementation) mode | 93.29% (153/164) | 164 | same |
| WIR structural accuracy (node/edge precision, recall, F1) | 1.0000 / 1.0000 / 1.0000 | 101 programs | `e2_structural_report.md` |
| Certificate-score ↔ real-code-correctness correlation | Pearson r=0.41, Spearman ρ=0.54 | 427 mutants | `e3_correlation_report.md` |

**Corpus scale**: 101 FlowBench-derived base programs → 427 applicable mutants (8-9 operator types: drop-step, negate-guard, wrong-variable, early-return, etc.), 50/50 CALIB/EVAL split, seed 1234, frozen threshold τ=0.1. Separately, 3 LLMs (llama-3.1-8b, mixtral-8x7b, qwen3-next-80b) independently generated code against the same FlowBench tasks; 164 rejected (behaviorally divergent) generations became the natural-bug corpus.

**Headline poster claim**: *100% detection of real bugs in independently-generated LLM code* (164/164, strict mode) is the strongest single number in the project — it's not a synthetic-mutant artifact, it's real generation failures from 3 different models.

**Honest caveat**: equivalent-mutant specificity is weak and wide-CI (11.1%, 95% CI 0.3–48.2%, n=9 only) — the certificate doesn't reliably tell a behaviorally-equivalent mutant apart from a real one on this small a sample. Documented in the source report as investigated, not swept under the rug.

---

## Module 03 — Equivalence Engine (LTLf model checking against real code)

**Method**: two layers — component tests, and a real end-to-end FlowBench run scored as **oracle agreement**, not (yet) a bug-detection rate.

| What | Result |
|---|---|
| C++/SPOT engine tests | 115/118 passing, 2 pre-existing unrelated failures, 1 skip (2026-07-30 snapshot) |
| First real FlowBench run (M01 suite → ingestion → compiled `check_compliance`) | 22/29 eligible specs had ≥1 checkable property → **29 variants, 58 checks**: `{VIOLATION: 18, COMPLIANT: 17, INCONCLUSIVE: 23}` |
| Agreement with Module 01's own independent LTLf oracle, on checks that returned a real verdict | **100% (35/35)** |
| Remaining 23 checks | Legitimate abstentions (`INCONCLUSIVE`) — the property referenced a task genuinely never called in that variant; correctly refusing, not a miss |

**Precise caption — do not round this up**: "100%" here means *M03's compiled checker agrees with Module 01's independent reference interpreter on every check where either produced a real verdict*. It is a **plumbing-correctness proof for the M01→M03 bridge**, not a claim that M03 catches 100% of real bugs — that's a different, not-yet-measured number (see Full-Project section, which *is* a detection-rate measurement). This run also uses definition-order lifting (a documented, separate scoping decision, [[Module 03 - Equivalence Engine/Bridge Investigation/CP1 Lifting-Scope Decision|CP1]]) rather than the call-order fix already used elsewhere in the pipeline.

---

## Full Project — End-to-End (M01 → M02 → M03)

**Method**: `demo/eval_e2e/harness.py` runs the complete pipeline against a small gold set of FlowBench specs with confirmed-correct real implementations, then mutates the *order* of steps in the real implementation and checks whether the full pipeline catches the resulting violation.

- **Gold set**: 6 FlowBench (spec, real implementation) pairs, independently confirmed COMPLIANT end-to-end (uids 45, 72, 76, 77, 84, 85)
- **Abstention rate**: **46.2%** [95% CI 27–67%], n=26 — trials where the pipeline honestly returned `INCONCLUSIVE` rather than guessing
- **Detection rate**: **35.7%** [95% CI 13–65%], n=14 — of trials where the pipeline *did* commit to a verdict, the fraction correctly flagged `VIOLATION`
  - By mutation kind: `drop_step` 0/16 detected (12 abstained, 4 missed) — dropping a task often makes its own atom unobservable, so the pipeline correctly can't judge it, rather than silently guessing wrong; `swap_adjacent` 5/10 detected
- **False-alarm rate**: **0.0%** [95% CI 0–84%], n=2 (small n — most gold specs had no literal eligible to perturb)
- **Counterexample quality**: **80.0%** [95% CI 28–99%], n=5 — of correctly-detected violations, fraction whose counterexample named every task the violated property references

**Poster framing — show the CIs, not bare percentages.** These are small-n figures by the harness's own design (only 6 gold pairs exist), and it deliberately reports Clopper-Pearson 95% CIs rather than point estimates. "35.7%" alone reads as a failing grade; "35.7% [13–65%] detection, 46% honest abstention, 0% false alarms" reads as what it actually is — a pipeline that mostly declines to guess rather than guessing wrong, which is the intended, designed-for behavior, not a bug.

**Product-claim caveat**: this evaluation runs against `demo/eval_e2e/harness.py`'s own pipeline wiring, not the production `/check` API endpoint (which currently still defaults to a placeholder — see [[Module 03 - Equivalence Engine/Module 03 Knowledge|Module 03 Knowledge]]). Caption figures as "the evaluation pipeline," not "the deployed system."

---

## Quick reference for poster captions

| Module | One-line method | Headline number | What it actually measures |
|---|---|---|---|
| M01 | Suite-soundness (does the LTLf suite accept its own source diagram?), 148-diagram corpus | 55/100 sound, 0/50 on branching diagrams | Diagnostic — found 3 real defects; not a bug-detection rate, and not yet post-fix (see above) |
| M02 | Mutation testing, 101-program corpus + real multi-LLM bug corpus | 100% (164/164) real-bug detection | Detects behaviorally-divergent code vs. reference IR |
| M03 | Oracle-agreement on real FlowBench property checks | 100% (35/35) agreement | Agrees with M01's own oracle — plumbing correctness, not bug-catch rate |
| Full pipeline | Order-mutation E2E, 6 gold pairs | 35.7% [13–65%] detection, 46% abstention, 0% false alarms | Honest-abstention design; small n, wide CIs |

## Source files (canonical — this page summarizes, does not replace)

- M02: `module_02_extract/eval/results/calibration_report_differential.md`, `session_b_report.md`, `e2_structural_report.md`, `e3_correlation_report.md`
- M03: [[Module 03 - Equivalence Engine/Module 03 Knowledge|Module 03 Knowledge]]
- Full project: `demo/eval_e2e/results/e2e_eval_report.md`, `demo/eval_e2e/harness.py` (module docstring has full ground-truth-provenance caveats)
- FlowBench ground-truth methodology: `.claude/memory/flowbench_groundtruth_finding.md`
