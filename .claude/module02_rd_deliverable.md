# Module 02 — R&D Session Deliverable

**Produced**: 2026-05-30 · **Mode**: Research & design only (no code written, no source edited)
**Session type**: 5-role pass (Literature Scout, Dataset Scout, Evaluation Methodologist, Architecture Critic) → Synthesis
**Inputs**: `.claude/prompts/opus_multiagent_rd_session.md`, `.claude/module02_rd_plan.md`
**Status of evidence**: Literature & dataset claims grounded in real, fetched sources (URLs inline). Statistical figures computed exactly (exact binomial + Fisher-z), not approximated.

> ⚠️ **One load-bearing finding to verify with the team first (see Agent 2 / DELIVERABLE 2):** the *public* IBM FLOW-BENCH does **not** contain executable LLM Python implementations or correct/buggy correctness labels. Each record is `{utterance, prior_sequence, prior_context, bpmn-ref, expected_output}`, where the "Python" is a **constrained Python-syntax IR** (assignments, if, for/while, function calls). The brief's "101 triplets with Python *implementation*, 80 dev / 21 eval, LLM codegen external" is therefore the group's **own derived/augmented artifact**, not the published dataset. This changes where E1's ground truth comes from. Confirm before implementation.

> 🛠️ **Implementation status (2026-05-30, branch `fix/mod2/phase1-symbolic-hardening`):**
> - **CORRECTION — the "P0 Z3 double-reset" bug does not exist as described.** On inspection, `_solve_for_inputs` (real location `module_02_extract/src/z3_sym_engine.py:947`, **not** L4360–4397) creates a *fresh* local `z3.Solver()` per call; the two `solver.reset()` calls were vestigial no-ops added later in a "solver hygiene" commit (`ee8a3be`). Path-constraint accumulation lives in `self.explored_path_conditions` (re-added as `Not(pc)` each solve), which `reset()` cannot touch. The original audit (R&D plan §3) misdiagnosed this. **DONE:** removed the dead resets + misleading comment and refactored to incremental `push()/pop()` solving with monotonic blocking clauses (real O(n) vs O(n²) fix). 97 tests pass.
> - **DONE (partial Phase-1 settrace migration):** the concrete-execution step-counter guard in `_execute_concrete` migrated from `sys.settrace` → `sys.monitoring` (PEP 669) with a settrace fallback; verified guard still fires + no tool-id leak.
> - **DONE — V1 `WIRTraceCollector` given a `sys.monitoring` runtime path (commit `869499c`), behaviour-preserving.** `start_tracing`/`stop_tracing` now prefer `sys.monitoring` (PEP 669) with a `sys.settrace` fallback (the `trace_callback` unit-test path is left intact). Event mapping reconciled with settrace: `PY_START`→task_entry, `PY_RETURN`→task_exit(normal), `PY_UNWIND`→task_exit(exception exit) + propagation `exception` for ancestor frames, `RAISE`→`exception` at the origin frame, `LINE`→branch_point/mutation audit; locals recovered via `sys._getframe(1)`. Gated by a new differential parity test (8 cases incl. uncaught/locally-caught/multi-frame exception corners) asserting byte-identical output vs the settrace path.
>   - **Caveat preserved for the thesis:** this fixes NEITHER Critic-Q5 concern — (a) *overhead* gain is ~nil/unmeasured because V1 reads `f_locals` every line (PEP 669's `DISABLE` low-overhead model does not apply), and (b) `sys.monitoring` is **also CPython-only**, so the CPython dependency remains. Keep V1's CPython-only scope as a stated limitation. The far higher-ROI item — `Module01Adapter` (WIR-independent oracle, vulnerability #1) — remains **not started**.

---

## AGENT 1 — Literature Scout

### Area 1 — Formal verification of LLM-generated code
The closest peer system is **Astrogator** ("Towards Formal Verification of LLM-Generated Code from Natural Language Prompts", arXiv:2507.13290): it formally verifies LLM code (for Ansible) using a formal query language, a behavior calculus, and a symbolic interpreter + unification. On **21 code-generation tasks it verified correct code in 83% and flagged incorrect code in 92%** — directly comparable scale and metric to VibeCheck's E1, and useful as a baseline/related-work anchor. The broader pattern in the 2024–2025 literature (Frontiers dual-perspective review, 2025; Berkeley EECS-2025-174 on compositional reasoning for code translation) is that **LLM output is treated as untrusted and checked by an independent formal/symbolic oracle** — which validates VibeCheck's post-hoc, oracle-style premise. **Supports** the overall design. **Implication**: cite Astrogator as the comparable baseline and explicitly position VibeCheck's contribution as *multi-layer* certification rather than single-oracle verification.

### Area 2 — Python symbolic execution & container types
**CrossHair** (pschanely; crosshair.readthedocs.io) is the decisive find: it does symbolic execution of *real Python* by substituting symbolic objects (`SymbolicInt` backed by Z3 `IntSort`, etc.) and **natively supports symbolic `list`, `dict`, `set`, and custom classes**, deciding branches via `__bool__` and accumulating Z3 path constraints. This is *exactly* the capability V2 lacks today (the 30% container fallback). Abstract-interpretation alternatives exist (Lyra, the ETH SRI Python static analyzer; IKOS for C/C++) but are either research-grade or not Python-workflow-targeted. **Challenges** the current "scalars-only Z3" V2. **Implication**: either (a) adopt CrossHair's symbolic-container modelling pattern inside `z3_sym_engine.py`, or (b) integrate CrossHair as the V2 backend for container-bearing workflows. (a) is more publishable; (b) is faster and lower-risk.

### Area 3 — IR extraction from Python
The dominant academic pattern is **CFG + dominator tree + guard/branch conditions**, which is precisely what V3 (`CFGExtractor → DominatorAnalyzer → GuardExtractor → WIRDataLayer`) already builds — so V3 is well-aligned with standard practice. What comparable systems additionally capture and V3 appears to under-model: **explicit data-flow / def-use edges** and **exception/abnormal-exit edges**. FLOW-BENCH's own IR is deliberately a *constrained* subset (assignments, conditionals, for/while, calls), which means VibeCheck's WIR only has to be faithful over that subset — a scoping advantage worth stating. **Mostly supports** V3. **Implication**: add def-use edges to the WIR schema and treat exception edges explicitly, because both feed the E2 "structural accuracy" metric.

### Area 4 — Multi-layer certificate combination
The formula `combined = 1 − (1−v1)(1−v2)(1−v3)` is the **noisy-OR / independent-evidence** combination — standard, but its independence premise is the single most-attacked assumption. The literature offers principled alternatives: **Dempster–Shafer evidence theory** (used for software defect prediction — "Information fusion with Dempster-Shafer evidence theory for software defect prediction", ResearchGate 220307939) and, critically, **Murphy's averaging rule and correlation-aware extensions of Dempster's rule** developed specifically because *"the major limitation of Dempster's rule is the inability to handle information coming from correlated sources"* (WVU thesis on software reliability fusion). **Challenges** the formula. **Implication**: do **not** swap to full Dempster–Shafer (heavy, hard to defend in a viva); instead **down-weight for correlation** — keep noisy-OR as the headline but introduce a correlation discount (Area 5) and report both.

### Area 5 — Correlated failure across layers sharing an upstream artifact
This is the formal name for VibeCheck's deepest vulnerability: V1/V2/V3 all consume the **same WIR from the same AST extractor**, so a systematic extractor bug is a **common-mode failure** that the independent-product formula cannot see. The reliability literature (common-cause failure modelling; correlation-aware evidence fusion, above) is unanimous that **independent combination over-states confidence when sources share an upstream cause**. **Challenges** the formula hard. **Implication**: (i) make at least one layer *not* depend on the WIR — e.g. let V1 dynamic tracing compare the LLM program's behaviour directly against the FLOW-BENCH `expected_output` reference, bypassing the WIR; (ii) add a measured correlation term to the certificate; (iii) at minimum, document the common-mode limitation explicitly.

### Area 6 — Bounded symbolic execution & choice of k
Fixed small-k loop unrolling is standard in bounded model checking (CBMC-style), but k is normally **justified by the program/loop-bound structure**, not asserted as a universal constant. A pre-declared `k=3` invites the same "where did this number come from?" attack as the 0.95 threshold. **Neutral-to-challenging.** **Implication**: derive k empirically from the FLOW-BENCH corpus — measure the distribution of static loop trip-counts across the 80 dev workflows and set k to a high percentile (e.g. p95), then report "k=N covers X% of workflow loops exactly; the remainder are over-approximated."

### Top 3 design changes implied by the literature
1. **Fix the container gap via CrossHair-style symbolic containers** (Area 2) — converts the 30% V2 fallback from a blind spot into coverage, and is the most publishable single change.
2. **Replace pure independence with a correlation-discounted combination + at least one WIR-independent layer** (Areas 4–5) — neutralises the single hardest examiner attack.
3. **Empirically derive both k and the 0.95 threshold from dev data** (Areas 5/6 + Agent 3) — removes two "magic constant" attacks at once.

**Sources:** [FLOW-BENCH arXiv:2505.11646](https://arxiv.org/abs/2505.11646) · [IBM/flow-bench](https://github.com/IBM/flow-bench) · [Astrogator arXiv:2507.13290](https://arxiv.org/abs/2507.13290) · [SymEx+LLM specs arXiv:2506.09550](https://arxiv.org/pdf/2506.09550) · [AutoBug / LLM-powered symbolic execution (OOPSLA'25)](https://www.comp.nus.edu.sg/~gregory/papers/llm_sym_exe.pdf) · [Frontiers dual-perspective review](https://www.frontiersin.org/journals/computer-science/articles/10.3389/fcomp.2025.1655469/full) · [CrossHair docs](https://crosshair.readthedocs.io/en/latest/how_does_it_work.html) · [D-S defect prediction](https://www.researchgate.net/publication/220307939) · [D-S correlated-sources / Murphy's rule (WVU)](https://researchrepository.wvu.edu/cgi/viewcontent.cgi?article=3116&context=etd)

---

## AGENT 2 — Dataset Scout

### What the public FLOW-BENCH actually is (verified)
Fetched from `github.com/IBM/flow-bench` README and arXiv:2505.11646 (Duesterwald et al., EMNLP 2025 Industry). Each record:

```
input:  utterance (NL), prior_sequence (constrained-Python-syntax IR of prior BPMN),
        prior_context, bpmn ($ref to context/uid_N_context.bpmn)
expected_output: sequence (ground-truth constrained-Python-syntax IR), bpmn ($ref to output/uid_N_output.bpmn)
_metadata.tags: linear|conditional, create|update|delete
```

**It does NOT contain:** (a) full executable LLM Python implementations — only a constrained subset (assignment, if, for/while, calls); (b) any correct-vs-buggy correctness label. The "ground truth" is the *expected workflow IR/BPMN*, for an NL→workflow generation task — **not** a verification-with-bug-labels task. ⇒ **VibeCheck's E1 ("≥95% bug detection") has no native data source here. Buggy programs must be manufactured.**

### Dataset table

| Dataset | N samples | Has BPMN? | Has Python? | Correctness labels? | Source |
|---|---|---|---|---|---|
| **FLOW-BENCH (public)** | ~100s of utterance/BPMN records | ✅ BPMN 2.0 XML | ⚠️ constrained-syntax IR only, not executable impls | ❌ (only ground-truth IR + type tags) | [IBM/flow-bench](https://github.com/IBM/flow-bench) |
| FLOW-BENCH "triplet" split (brief) | 101 (80 dev / 21 eval) | ✅ | claims executable Python | claims correctness | **group-derived — verify provenance** |
| BPI Challenge logs | large, annual | event logs (→BPMN) | ❌ | ❌ | process-mining community |
| PMo Dataset | ~750 diagrams → ~400 validated GT | ✅ | ❌ (BPMN only) | GT via SpiffWorkflow validation | [Zenodo 15857589](https://zenodo.org/records/15857589) |
| HumanEval | 164 | ❌ | ✅ executable | ✅ via test suites | OpenAI |
| MBPP | 974 (374 core) | ❌ | ✅ executable | ✅ via test suites | Google |
| REval (used by AutoBug) | 85 Python LeetCode | ❌ | ✅ | ✅ | [AutoBug paper](https://www.comp.nus.edu.sg/~gregory/papers/llm_sym_exe.pdf) |
| SWE-Bench | 2,294 | ❌ | ✅ (repo-scale) | ✅ (PASS/FAIL tests) | Princeton |

### Recommended dataset strategy (with statistical justification)
The eval claim that matters (E1) needs **labeled correct/buggy program pairs with workflow structure**. None of the public corpora supply that directly. Recommended layered strategy:

1. **Base reference set — FLOW-BENCH dev (80):** use the *ground-truth IR/BPMN* as the **gold reference** for E2 (structural accuracy of WIR extraction). This is exactly what FLOW-BENCH provides and needs no augmentation.
2. **Generate the verification corpus by mutation, not by hoping FLOW-BENCH has bugs.** Take each correct FLOW-BENCH workflow, generate an executable Python realisation, then apply **semantic mutation operators** (swap branch guards, off-by-one loop bounds, swap create↔update calls, drop a step, negate a condition) to produce a labeled buggy/correct population. This is a *controlled* E1: VibeCheck must detect *injected* defects, and the corpus size is something **you control**, which is what fixes the power problem.
3. **Cross-domain robustness — HumanEval + MBPP subset:** select the subset with workflow-like control structure (sequential steps + branching + bounded loops) for an external-validity check that VibeCheck generalises beyond FLOW-BENCH's narrow IR. Use their existing test suites as correctness oracle.

**Target N (from Agent 3's power analysis):** the headline E1 claim ("≥95%, reject true rate ≤80%, α=0.05, power=0.80") requires **N ≈ 30 trials minimum, ~40 for comfortable power (0.86), ~80 for power ≈ 0.99**. The 21-sample eval split is below the floor (power 0.34). **Recommendation: build a mutation corpus of ≥40 labeled buggy + ≥40 correct programs, held strictly separate from any calibration data.**

**Train/dev/eval split recommendation:**
- **Calibration set** (set the threshold and k): FLOW-BENCH dev workflows + their mutants — *never reused for the final claim*.
- **Eval set**: a disjoint mutation corpus (target ≥40 buggy / ≥40 correct) + the 21 native FLOW-BENCH eval workflows for the *structural* (E2) claim.
- **External set**: HumanEval/MBPP workflow-like subset, reported separately as generalisation evidence.

---

## AGENT 3 — Evaluation Methodologist

> All sample sizes below were computed exactly (exact binomial test; Fisher-z for correlation), not from rules of thumb.

### 1. Threshold calibration protocol (fixes the circular 0.95)
1. **Split first.** Partition all labeled data into **CALIB** and **EVAL** with no overlap. Freeze EVAL — do not look at it until step 6.
2. **Score CALIB.** Run the full V1+V2+V3 pipeline on every CALIB program; record the continuous combined certificate score and the binary ground-truth label (correct / buggy).
3. **Choose threshold by an operating-point rule, not by fiat.** On CALIB only, sweep the threshold τ over [0,1] and pick τ\* by a *pre-registered objective* — recommended: the τ maximising Youden's J (sensitivity + specificity − 1), or the smallest τ achieving a target *specificity* (so PASS rarely lets a bug through). Report the full ROC and the chosen operating point.
4. **Lock τ\*.** Write it down; it is now a fixed constant derived from CALIB.
5. **Pre-register** the EVAL hypotheses and the test (below) *before* unfreezing EVAL.
6. **Evaluate once** on EVAL with τ\* fixed. No tuning after this point.

This converts "we chose 0.95 then measured against it" into "we *derived* τ\* on calibration data and *confirmed* it once on held-out data" — the standard ML protocol and not circular.

### 2. Power analysis for E1 (≥95% bug detection) — exact binomial
- **Test**: one-sided **exact binomial test**, H₀: p ≤ 0.80 vs H₁: p = 0.95, α = 0.05.
- **Minimum N for power 0.80: N = 30** (reject if ≥ 28/30 successes; achieved power 0.812).
- **Power at the current eval split is fatal:** at **N = 21, power = 0.341**, and the rejection region requires a **perfect 21/21** — you cannot tolerate a single miss.
- **Even a perfect run can't clear 0.95 at N=21:** observing 21/21 gives a one-sided 95% **lower confidence bound of only 0.867**; 20/21 → 0.793; 19/21 → 0.729. **So 21 samples cannot support a "≥95%" claim under any outcome.**
- **Comfortable N:** N = 40 → power 0.862 (tolerates 3 misses); N = 80 → power 0.993 (tolerates 9 misses).
- **Denominator caveat:** if "bug detection rate" is **sensitivity over buggy programs only**, the effective N is the *buggy* subset — so the corpus must contain ≥40 *buggy* programs, not 40 total.

### 3. Framework for E2 (≥98% structural accuracy)
- **Operationalise** as **micro-F1 over WIR elements** (nodes + edges) against the FLOW-BENCH gold IR — precision/recall on extracted-vs-gold nodes and edges (including the def-use and exception edges recommended in Agent 1).
- **Why per-element:** accuracy is measured over *elements*, not programs, so N is the total element count across the corpus. With ~40–80 workflows at tens of elements each, the population is comfortably in the **hundreds–thousands**, which trivially exceeds the few-hundred elements needed to distinguish 0.98 from 0.95 at α=0.05/power 0.80. **E2 is not sample-starved**; report micro-F1 with a Wilson/Clopper-Pearson CI and per-element-type breakdown.

### 4. Framework for E3 (Pearson r ≥ 0.85)
- **Pearson r is the wrong primitive** if "actual correctness" is **binary** — you'd be computing point-biserial correlation, and "r ≥ 0.85" is barely achievable for a binary outcome regardless of model quality. **Fix the ground truth to be continuous**: define correctness as the **mutation-kill fraction** (fraction of behavioural checks / reference-trace positions the program matches) or **1 − normalised behavioural distance** to the reference. Then Pearson r is meaningful.
- **Sample size (Fisher-z, α=0.05 two-sided, power 0.80):** detecting r=0.85 vs r=0 needs only **N≈8** — a *misleadingly easy* null. The honest framing is **CI width**: at N=21 the 95% CI for r=0.85 is **[0.66, 0.94]** (cannot assert ≥0.85); N=30 → [0.71,0.93]; N=50 → [0.75,0.91]; N=80 → [0.78,0.90]. To claim "r ≥ 0.85" with a lower bound that actually clears a meaningful threshold (e.g. ≥0.70), target **N ≈ 50–80**.
- **Report Spearman ρ as well** (rank correlation is robust if the relationship is monotone-but-not-linear) and show the scatter.

### 5. Exact thesis wording recommendation (non-circular threshold)
> "The decision threshold τ\* was **not** chosen a priori. We partitioned the labeled corpus into disjoint calibration and evaluation sets. On the calibration set we computed the certificate's ROC curve and selected τ\* as the operating point maximising Youden's J [alt: achieving ≥0.95 specificity]. τ\* was then **fixed** and the system evaluated exactly once on the held-out evaluation set, on which all reported figures are computed. We report τ\* together with the calibration ROC so the choice is auditable. We do **not** claim 0.95 as a universal threshold; we report the empirically derived τ\* and its sensitivity to the calibration split (Appendix)."

Caveats to include verbatim: (i) τ\* is corpus-specific; (ii) the buggy population is synthetic (mutation-generated) and detection rates are for *injected* defect classes, not a claim about all real LLM bugs; (iii) confidence intervals, not point estimates, are the headline.

---

## AGENT 4 — Architecture Critic (the 10 hardest viva questions)

**1. Independence assumption.**
**Q:** "V1, V2, V3 all read the same WIR from one AST extractor. The product rule `1−∏(1−vᵢ)` assumes independent evidence — but a single extractor bug fails all three identically. Your combined score is not a confidence; it's three correlated copies of one number." **CURRENT:** Not answered — the formula assumes independence with no correlation term. **FIX:** (a) Add a measured correlation/common-mode discount; (b) make ≥1 layer WIR-independent (V1 compares program behaviour directly to the FLOW-BENCH reference); (c) report the empirical correlation between layer scores on CALIB and present a correlation-adjusted combined score alongside the naive one.

**2. Container-type V2 gap.**
**Q:** "≈30% of workflows hit `list`/`dict` and silently fall back to V1-only. Your 'symbolic coverage' is overstated by exactly that fraction." **CURRENT:** Documented as a known gap; V2 skips containers. **FIX:** Adopt CrossHair-style symbolic containers (symbolic `list`/`dict` over Z3) in `z3_sym_engine.py`, or integrate CrossHair as the V2 backend for container workflows. If neither lands in time: **report V2 coverage as a denominator** ("V2 applies to X% of workflows; certificate degrades gracefully to V1+V3 elsewhere") rather than implying full coverage.

**3. QCE "three defenses" vs reality.**
**Q:** "You claim three defenses against path explosion — k-bounding, state merging, concolic refinement — but `merge_states()` is never called and refinement is a stub. You have one defense." **CURRENT:** Overclaimed; only k-bounding is live. **FIX:** Either wire `merge_states()` into the QCE loop and measure its effect, or **rewrite the claim**: "We implement k-bounded unrolling; state-merging is designed and stubbed but disabled pending evaluation (Limitations §X)." Do not claim three.

**4. Pre-declared 0.95 threshold.**
**Q:** "You picked 0.95, then measured against 0.95. That's a tautology." **CURRENT:** Circular. **FIX:** The calibration protocol in Agent 3 §1 + thesis wording §5 — derive τ\* on CALIB, confirm once on EVAL.

**5. `sys.settrace` for V1.**
**Q:** "`sys.settrace` is CPython-only, ~20× overhead, and per-line tracing can perturb or miss behaviour. Why trust 50 traced runs?" **CURRENT:** Functional but heavy and CPython-bound. **FIX:** Migrate V1 to **`sys.monitoring` (PEP 669, Python 3.12+)** — ~5% overhead vs ~2000% for settrace, works across threads, and supports per-event DISABLE. State the CPython-only scope as an explicit limitation.

**6. WIR as shared upstream artifact.**
**Q:** "Every layer trusts the WIR. What validates the WIR itself? If it's wrong, all certification is built on sand." **CURRENT:** Not directly validated; E2 measures structural accuracy but doesn't feed the runtime certificate. **FIX:** Make **E2's WIR-vs-reference check a gating precondition**: if WIR structural accuracy on a sanity check is low, the certificate is voided/RED before V1–V3 even run. Surfaces the common-mode risk instead of hiding it.

**7. Z3 over abstract interpretation.**
**Q:** "For workflow-scale Python with containers, why an SMT solver and not abstract interpretation (which handles unbounded/heap data more gracefully)?" **CURRENT:** Z3 chosen; container weakness is a direct consequence. **FIX:** Justify Z3 by the *constrained* FLOW-BENCH IR (finite branching, bounded loops, decidable guards) where SMT is precise; cite CrossHair as evidence Z3-backed symbolic execution *can* handle Python containers; document abstract interpretation as future work for unbounded data.

**8. M01→M02 coupling.**
**Q:** "M02 ingests the BPMN spec but only uses it for GPT narrative. Why accept an input you don't verify against?" **CURRENT:** Under-exploited; spec feeds narrative only. **FIX:** Decide explicitly. Recommended: **use the BPMN/M01 reference as the WIR-independent oracle for V1** (behavioural equivalence to spec), which simultaneously fixes Q1 and Q6. If not implemented, **drop the input from the contract** rather than accept-and-ignore it.

**9. n=50 runs for V1.**
**Q:** "Why 50? What's the probability a behavioural divergence escapes 50 random inputs over your input distribution?" **CURRENT:** Fixed magic number, unjustified. **FIX:** Make it **adaptive** — sample until the certificate estimate's CI half-width is below a target ε, or until a divergence is found; report the achieved CI. Failing that, derive 50 from a coverage argument on CALIB and report the residual escape probability.

**10. FastAPI `/verify` partial-output contract.**
**Q:** "If V3 throws, what does `/verify` return? Is a missing layer scored 0, or omitted? A crash that silently scores 0 inflates apparent rigor." **CURRENT:** Underspecified partial-failure contract. **FIX:** Define a typed response: per-layer status ∈ {OK, SKIPPED(reason), ERROR(reason)}; the combined score is computed **only over OK layers** with coverage reported; a hard V3 failure ⇒ certificate = RED/ABORT (not PASS), matching the M03 contract (RED <0.70 ⇒ M03 refuses to lift).

---

## AGENT 5 — SYNTHESIS

### Reconciled conflicts
- **Combination method (Agent 1 D-S vs keep noisy-OR):** Resolved → **keep noisy-OR as headline, add a correlation discount + one WIR-independent layer.** Full Dempster–Shafer is heavier than the thesis needs and harder to defend; the correlation term addresses the actual attack (common-mode) more transparently.
- **Container fix (rebuild in Z3 vs integrate CrossHair):** Resolved → **integrate CrossHair as the V2 container backend for Phase 1** (low risk, fast, fixes coverage), and note in-house symbolic containers as optional future work. Publishability is preserved by the *measurement* (coverage before/after), not by re-implementing CrossHair.
- **Dataset → E1 dependency:** The single most important reconciliation — **the power analysis (Agent 3) is moot for E1 unless the mutation corpus (Agent 2) is built.** E1 measures detection of *injected* defects on a corpus whose size the team controls; this is what makes "N≈40–80" achievable. Stated as a hard dependency in DELIVERABLE 5.

---

### Text component diagram (revised)

```
                         ┌──────────────────────────────────────────────┐
   BPMN / M01 ref ──────►│  Module01Adapter (NEW)                        │
   (was narrative-only)  │  → behavioural reference for V1 (WIR-indep.)  │
                         └───────────────┬──────────────────────────────┘
                                         │ reference
 LLM Python code ──► V3: AST Extraction  │
                     CFG→Dom→Guard→WIR ──┼─────────────┬───────────────┐
                     (+ def-use, exc edges) (KEEP+CHANGE)               │
                                         │             │                │
                          ┌──────────────▼──┐   ┌──────▼───────┐  ┌─────▼─────────┐
                          │ V2: Z3 symbolic │   │ V1: dynamic  │  │ E2 WIR-vs-ref │
                          │ + CrossHair      │   │ sys.monitoring│ │ gate (NEW):   │
                          │ containers (CHG) │   │ adaptive runs │ │ bad WIR⇒RED   │
                          │ fix double-reset │   │ ref-based cmp │ └──────┬────────┘
                          └────────┬─────────┘   └──────┬───────┘        │
                                   │ v2 (coverage-aware) │ v1            │
                                   └──────────┬──────────┘               │
                                              ▼                          │
                          MultiModalCertificateComposer (CHANGE)         │
                          combined = 1−∏(1−vᵢ) over OK layers            │
                          × correlation discount  ──────────────────────┘
                                              │  EQI: GREEN≥0.90 / YELLOW / RED<0.70
                                              ▼
                          FastAPI /verify (CHANGE: typed partial-failure contract) → Module 03
```

---

### DELIVERABLE 1 — Revised Module 02 Architecture

| Component | Verdict | Justification (1 sentence) |
|---|---|---|
| **V3 — AST extraction** | **KEEP + CHANGE** | CFG/dominator/guard pipeline matches standard practice; add **def-use and exception edges** to the WIR schema (needed for E2). |
| **V3 — WIR as shared artifact** | **CHANGE** | Add an **E2 WIR-vs-reference gate** so a bad WIR yields RED before V1–V3 run, surfacing common-mode risk. |
| **V2 — Z3 symbolic** | **CHANGE** | Fix the `solver.reset()` double-reset bug; **integrate CrossHair-style symbolic containers** to close the 30% `list`/`dict` gap; report coverage as a denominator. |
| **V2 — QCE state merging** | **CHANGE (de-scope claim)** | Either wire `merge_states()` and measure it, or **document it as a designed-but-disabled limitation**; stop claiming three path-explosion defenses. |
| **V1 — dynamic tracing** | **CHANGE** | Migrate `sys.settrace`→**`sys.monitoring` (PEP 669)** (~5% vs ~2000% overhead); make run count **adaptive** (sample to CI target) instead of fixed n=50. |
| **V1 — reference oracle** | **ADD** | Compare program behaviour **directly to the BPMN/M01 reference**, making V1 WIR-independent (breaks the common-mode chain). |
| **Certificate composition** | **CHANGE** | Keep `1−∏(1−vᵢ)` over **OK layers only**, multiplied by a **measured correlation discount**; report naive vs adjusted. |
| **M01→M02 alignment (Module01Adapter)** | **ADD** | Implement to feed the V1 reference oracle — turns the under-used BPMN input into the independence fix. |
| **SelfConsistencyAdapter** | **KEEP (defer)** | Useful but not on the critical path for the thesis claims; Phase 3. |
| **ai_refinement/ (GPT-4o-mini)** | **KEEP (defer)** | Narrative/explainer value only; must not enter the certificate score; Phase 2. |
| **eval/ (golden + mutants + adversarial)** | **ADD (critical)** | Without the mutation corpus, E1 has no ground truth at any N. |
| **FastAPI /verify** | **CHANGE** | Typed per-layer status {OK/SKIPPED/ERROR}; combined over OK layers; hard V3 failure ⇒ RED. |

**Revised certificate formula verdict:** `1−(1−v1)(1−v2)(1−v3)` is **defensible only with caveats**. Recommended form:
> **combined = [1 − ∏₍ᵢ∈OK₎(1 − vᵢ)] · (1 − ρ̂·δ)**, computed over layers with status OK, where **ρ̂** is the empirically measured inter-layer score correlation on calibration data and **δ** a discount factor; the naive (ρ̂=0) value is reported alongside for transparency. At least V1 is made WIR-independent so the independence premise is partially *true*, not merely assumed.

---

### DELIVERABLE 2 — Dataset Recommendation
- **Recommended eval data:** **mutation corpus** built from FLOW-BENCH dev workflows — target **≥40 buggy + ≥40 correct** labeled programs — held disjoint from calibration; plus the **21 native FLOW-BENCH eval** workflows for E2 (structural) only; plus a **HumanEval/MBPP workflow-like subset** as external-validity evidence.
- **Power assessment:** E1 needs N≈30 (floor) to 80 (power 0.99); **21 is insufficient (power 0.34, and 95% lower bound ≤0.867 even at 21/21).** E2 is **not** sample-starved (per-element population in the hundreds–thousands). E3 needs **N≈50–80** for a useful CI on r≥0.85 *and* requires a **continuous** correctness ground truth (mutation-kill fraction), not binary.
- **Augmentation defensibility:** mutation testing is a **standard, citable** methodology; defensible provided the thesis states clearly that detection rates are for *injected* defect classes (enumerate the operators) and not a universal claim over all LLM bugs.
- **Split:** CALIB (dev workflows + mutants, threshold/k tuning) ⟂ EVAL (disjoint mutant corpus + 21 native for E2) ⟂ EXTERNAL (HumanEval/MBPP subset, reported separately).
- ⚠️ **Verification item for the team:** confirm the provenance of the brief's "101 triplets / executable Python / 80-21 split." If it is a real internal augmentation of FLOW-BENCH with correctness labels, much of the corpus concern is resolved — **but it must be documented as group-produced, because the public dataset does not contain it.**

---

### DELIVERABLE 3 — Empirical Calibration Protocol
Use Agent 3 §1 verbatim: (1) split CALIB⟂EVAL and freeze EVAL; (2) score CALIB with full V1+V2+V3; (3) on CALIB sweep τ and pick τ\* by a **pre-registered** rule (Youden's J, or smallest τ with ≥0.95 specificity), reporting the ROC; (4) lock τ\*; (5) pre-register EVAL hypotheses + the exact binomial test; (6) evaluate **once** on EVAL, no post-hoc tuning. Use the **thesis wording in Agent 3 §5** and include the three caveats (corpus-specific τ\*, synthetic buggy population, CIs as headline). Test of record for E1: **one-sided exact binomial, H₀:p≤0.80, α=0.05**.

---

### DELIVERABLE 4 — Top 5 Thesis Vulnerability Mitigations (ranked by attack severity)

| # | Vulnerability (1 sentence) | Mitigation | Code or wording? | Risk if unaddressed |
|---|---|---|---|---|
| 1 | **Independence/common-mode**: all layers trust one WIR, so the product formula over-states confidence. | Make V1 WIR-independent (BPMN reference oracle) + correlation discount + report naive vs adjusted. | **Code + wording** | HIGH — invalidates the central certificate claim. |
| 2 | **21 eval samples** cannot support "≥95%" (power 0.34; lower bound ≤0.867 even at 21/21). | Build ≥40 buggy/≥40 correct mutation corpus; report exact-binomial CIs. | **Code (eval) + wording** | HIGH — headline E1 claim is statistically unsupportable. |
| 3 | **Pre-declared 0.95 threshold** is circular. | Calibrate τ\* on CALIB, confirm once on EVAL (Deliverable 3). | **Wording + small code** | HIGH — examiner dismisses all PASS/FAIL results. |
| 4 | **QCE overclaim** — three defenses claimed, one implemented. | Wire+measure `merge_states()` or restate as designed-but-disabled limitation. | **Code or wording** | MEDIUM — credibility hit on rigor. |
| 5 | **Container blind spot** — 30% of workflows skip V2. | CrossHair symbolic containers, or report V2 coverage as an explicit denominator. | **Code (preferred) or wording** | MEDIUM — symbolic-coverage claim overstated. |

---

### DELIVERABLE 5 — Revised Phase Plan

| Phase | Scope change | Priority change | Dropped | Added |
|---|---|---|---|---|
| **1 — Core hardening** | **EXPANDED** | **unchanged (first)** | — | Z3 double-reset fix; **`sys.settrace`→`sys.monitoring`**; **adaptive V1 run count**; `ValidationConfig`; **typed `/verify` partial-failure contract**. |
| **2 — AI refinement** | **REDUCED** | **moved DOWN** | counterexample features that touch the score | GPT-4o-mini stays **narrative/explainer only, excluded from certificate**. |
| **3 — Multi-impl adapters** | **CHANGED** | **Module01Adapter moved UP into Phase 1.5** | — | **Module01Adapter** promoted (it *is* the independence fix); SelfConsistencyAdapter + `/verify-batch` stay here. |
| **4 — Eval data** | **EXPANDED + CRITICAL** | **moved UP (blocks Phase 5)** | — | **Mutation corpus (≥40/≥40)**; enumerate mutation operators; CALIB⟂EVAL split; continuous correctness label (mutation-kill fraction) for E3. |
| **5 — Experiments** | **CHANGED** | unchanged | the "≥95% on 21 samples" framing | E1 exact-binomial on mutation corpus; E2 micro-F1 w/ CI (not sample-starved); E3 on **continuous** ground truth, N≈50–80, report Pearson **and** Spearman + scatter. |
| **6 — Integration** | **EXPANDED** | unchanged | — | E2 **WIR-vs-reference gate** wired to certificate (RED on bad WIR); M03 EQI contract test; thesis chapter incl. calibration ROC + caveats. |

**New critical path:** Phase 1 (hardening + sys.monitoring + Module01Adapter) → Phase 4 (mutation corpus) → Phase 5 (experiments). Phases 2 and the rest of 3 are parallelisable and off the thesis-claim critical path.

---

## NEXT SESSION — first 5 actions (priority order)
1. **Verify FLOW-BENCH provenance with the team**: does the internal "101 triplets / executable Python / labels" exist, or must the corpus be built by mutation? This gates everything in Phase 4.
2. **Phase 1 hardening, start with the two cheapest high-impact fixes**: the Z3 `solver.reset()` double-reset (`z3_sym_engine.py` ~L4360–4397) and migrating V1 from `sys.settrace` to `sys.monitoring` (PEP 669). Run `gitnexus_impact` on each target before editing (per CLAUDE.md).
3. **Stand up `eval/`**: write the mutation operator set and generate the ≥40 buggy / ≥40 correct labeled corpus from FLOW-BENCH dev, with a frozen CALIB⟂EVAL split.
4. **Implement `Module01Adapter` as the V1 reference oracle** so at least one layer is WIR-independent — the highest-leverage architectural change for the independence attack.
5. **Implement the calibration script** (ROC on CALIB → τ\*; one-shot EVAL with exact-binomial CI) so E1/E3 can be run reproducibly and the threshold is never circular.
```

