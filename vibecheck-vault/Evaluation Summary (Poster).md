> [!info] Purpose
> Poster-ready evaluation summary for Module 01, Module 02, Module 03, and the full project, all against the IBM FLOW-BENCH dataset. This page is the single source of truth for the numbers — link to it rather than re-typing figures on slides/posters, so a future correction only has to happen in one place. Figures below are dated **pre-PR #88** (2026-08-02) where noted; PR #88 (`feat/mod1/improve-reliability`) had not yet merged when this was written.

## Why FlowBench has no "accuracy" number to just look up

[FLOW-BENCH](https://github.com/IBM/flow-bench) (Isahagian et al. 2025, arXiv:2505.11646) gives 101 natural-language→BPMN generation samples plus ~48 real BPMN diagrams — but it ships **no correctness labels** (buggy vs. correct implementation). It's a generation benchmark, not a bug-detection benchmark.

So every module in this project builds its own ground truth **by mutation**: take a real FlowBench-derived program or spec, inject a defect with a known effect (or use a real, independently-confirmed-correct/incorrect implementation), and check whether the module's verdict flips the way the defect predicts. This is the one idea to put on the poster before any number — it's what makes "94% detection rate" a meaningful claim against an unlabeled dataset rather than a made-up figure.

One consequence: **the three modules are not evaluated the same way**, because they sit at different points in the pipeline and have different amounts of mutation-eval infrastructure built out. A single "accuracy" row across all three would misstate what each number actually means. Treat each module's box below as its own claim, with its own caveat.

---

## Module 01 — Specification Engine (BPMN → LTLf property suite)

**Method**: unit/regression tests + quality-gate pass criteria, not yet a standalone FlowBench detection-rate figure.

| What | Result |
|---|---|
| Unit tests | **28/28 passing** (~0.3s), 6 test files — phase-1/phase-3 gates, PBCTS convergence, SCSL, status-code consistency, M03 export, main API (2026-07-29 snapshot) |
| Quality-gate criteria (per spec, must all hold to certify) | Node coverage ≥ 1.0, guard-resolution coverage ≥ 1.0, mutation kill-ratio ≥ 1.0, IDCD (bidirectional alignment) convergence |
| Standalone FlowBench corpus run | **Gap — no current number.** An earlier run over all 100 real FlowBench BPMN diagrams found only 3/100 passing end-to-end, but that predates several fixes (including PR #88's `G(A -> !F(B))` LTLf template correction). Not re-measured since. |

**Honest caveat for the poster**: present M01 as tests-passing + quality-gate criteria + its contribution to the M01→M03 numbers below — don't claim a standalone FlowBench detection percentage for M01 alone, because that number doesn't currently exist post-fix. (Re-running the 100-diagram corpus to get a fresh number is possible future work, not done here.)

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
| M01 | Unit tests + quality-gate criteria | 28/28 tests passing | Internal correctness, not FlowBench detection rate (gap, see above) |
| M02 | Mutation testing, 101-program corpus + real multi-LLM bug corpus | 100% (164/164) real-bug detection | Detects behaviorally-divergent code vs. reference IR |
| M03 | Oracle-agreement on real FlowBench property checks | 100% (35/35) agreement | Agrees with M01's own oracle — plumbing correctness, not bug-catch rate |
| Full pipeline | Order-mutation E2E, 6 gold pairs | 35.7% [13–65%] detection, 46% abstention, 0% false alarms | Honest-abstention design; small n, wide CIs |

## Source files (canonical — this page summarizes, does not replace)

- M02: `module_02_extract/eval/results/calibration_report_differential.md`, `session_b_report.md`, `e2_structural_report.md`, `e3_correlation_report.md`
- M03: [[Module 03 - Equivalence Engine/Module 03 Knowledge|Module 03 Knowledge]]
- Full project: `demo/eval_e2e/results/e2e_eval_report.md`, `demo/eval_e2e/harness.py` (module docstring has full ground-truth-provenance caveats)
- FlowBench ground-truth methodology: `.claude/memory/flowbench_groundtruth_finding.md`
