# VibeCheck — System-Level Evaluation Plan (FLOW-BENCH, End-to-End)
**Session**: Fable 5 planning session, 2026-07-11. Companion to `.claude/module01_e2e_plan.md` and `.claude/module03_e2e_plan.md`; reuses Module 02's shipped eval machinery (`module_02_extract/eval/`).
**Premise**: all three module plans are implemented — M01 T1–T7 (sound Phases 1–3, Phase 4 automata/property suite, FLOW-BENCH adapter), M02 as it already exists on `develop` (V3/V2/V1 + certificate + 427-mutant corpus + multi-impl corpus + frozen `threshold.json`), M03 T1–T8 (observability + stuttering fixes, batch entrypoint, `from_property_suite`, ported semantic matcher). Where a number below was measured this session or in a prior session, it is cited; everything else is the plan's target, not a claim.

**What this plan produces**: one frozen, reproducible, non-circular evaluation of the full claim — *"VibeCheck formally verifies LLM-generated Python against BPMN-derived temporal specifications"* — on the public IBM FLOW-BENCH dataset, plus the refinement protocol that gets the system there and the presentation artifacts (thesis chapter, figures, demo, reproduction package) that carry it.

---

## 1. Research claims → evaluation questions

The thesis's system-level claim decomposes into five falsifiable questions. Each maps to one experiment family (§5) and one headline figure (§8).

| RQ | Question | Falsified if | Experiment |
|---|---|---|---|
| RQ1 | **Soundness on correct code**: does a correct implementation of uid *u*'s BPMN pass end-to-end? | E2E false-alarm rate materially above the pre-registered bound (target: ≤10%, matching M02's measured task_only FA 0.10) | SYS-1 |
| RQ2 | **Sensitivity to real defect classes**: does an implementation with a seeded, behaviorally-real defect fail? | Detection below the pre-registered floor (register **≥90%**, never 95% — the M02/M01 power lesson, third time) | SYS-2 |
| RQ3 | **Implementation freedom**: do *stylistically different but behaviorally admitted* implementations pass, and cluster with their base? | Admitted variants fail or singleton at a rate ≫ base FA rate | SYS-3 |
| RQ4 | **Spec-side sensitivity**: if the *diagram* is wrong for the code (mutated BPMN vs correct implementation), does the system fail it? | Spec-mutation detection below floor — would mean the verdict ignores the spec track | SYS-4 |
| RQ5 | **Clustering pays for itself**: does representative-only verification give the same verdicts as verify-everything, at measurably lower cost? | Any verdict flip between propagated and direct verification, or no cost reduction | SYS-5 |

Plus two supporting analyses that examiners will demand: **ablations** (which module/feature earns its place — SYS-6) and **baselines** (compared to what — SYS-7).

---

## 2. Corpus and ground truth (all label sources external to the system)

One identity spine: the FLOW-BENCH `uid` (1–101). Per-uid asset inventory, with the non-circularity pedigree of every label:

| Asset | Source / path | Count | Ground-truth role |
|---|---|---|---|
| BPMN diagram | `github.com/IBM/flow-bench` `data/output/uid_N_output.bpmn`, vendored at pinned SHA (M01 plan T2) | 100 (uid 90 absent) | System *input*, spec track |
| Utterance + expected sequence | `conditional_ootb.yaml` `expected_output.sequence` (IBM-authored constrained-Python IR) | 101 | **Independent gold**: defines correct call structure per uid; never produced by any module |
| Base program | `module_02_extract/eval/corpus/uid_N.py` | 101 | Correct-implementation exemplar (RQ1) |
| Code mutants | `module_02_extract/eval/mutants/` (seeded operators, labeled by construction) | **427** | Defect-seeded negatives (RQ2), with per-mutant operator class |
| Multi-impl variants + admission verdicts | `eval/variants/manifest.json` — verdicts from the WIR-free execution-diff (N=100 inputs), contract `docs/module02/11_multi_impl_corpus_contract.md` | 20 admitted / 164 rejected_behavioral today | Implementation-freedom positives (RQ3) + cluster ground truth (SYS-5); **expansion to ≥100 admitted is a Phase-E1 task** (Session-C machinery exists) |
| BPMN mutants | `module_01_spec/eval/mutate_bpmn.py` output (M01 plan §4.3 operators, labeled by construction) | target ≥280 EVAL (70 diagrams × 4) | Spec-side negatives (RQ4) |
| Equivalent-mutant controls | both mutators' semantics-preserving sets | ≥50 each side | Specificity controls (the third figure in every report) |

Corpus caveats to carry into every results section (measured this session / M01 session): construct coverage is skewed — ~31 uids conditional, ~69 linear, **0** parallel gateways, 0 inclusive gateways, 0 lanes/boundary events; 37 diagrams use subProcess+loop markers; task names in FLOW-BENCH are near-aligned with code call names *by construction* (external-validity threat → SYS-6d obfuscation ablation). Scope every claim to this coverage; the synthetic construct supplements (M01 plan §4.2.5, M03 plan §4.3) are robustness evidence, not headline data.

**Anti-circularity rules (inherited, now system-wide)**: no label may come from any module's own output (no M03-verdict-as-truth, no M01-property-suite-as-spec-gold, no Phase-3 self-mutation numbers as evidence); admission verdicts come only from the execution-diff manifest; any reuse of M02's differential comparator across implementations runs `comparison_mode="task_only"` (contract §7 — strict inflates FA 0.25→0.10); CALIB and EVAL are disjoint **by uid** and the split is frozen before any EVAL run.

---

## 3. The E2E harness (the one new artifact this plan requires)

Neither module owns the system-level run, so it lives at repo root: **`eval_e2e/`**.

- **`eval_e2e/run_e2e.py`** — the single entrypoint everything else calls:
  `run_e2e(uid, program_path, config) -> verdict.json` implementing the real pipeline: BPMN (vendored corpus + M01 dialect adapter) → M01 `/verify`-equivalent (property suite + certificates) → program → M02 `run_v3_pipeline` (WIR + certificate) → M03 batch entrypoint (lift → cluster if multiple programs → `from_property_suite` Phase D) → structured verdict `{uid, program_id, verdict: PASS|FAIL|INCONCLUSIVE(reason), violated_properties[{id,tier}], counterexample, certificates: {m01, m02, m03}, timings}`.
  Non-negotiables baked into the schema: **INCONCLUSIVE is a first-class outcome** (gate refusals, bound-exceeded, unsupported constructs — never silently coerced to PASS or FAIL; M03 plan 0.7's lesson), every verdict carries the three certificates, and the run is **seeded end-to-end** (M01 Phase-3 RNG, any sampling) so a uid+program+config triple is bit-reproducible.
- **`eval_e2e/corpus_index.py`** — materializes the §2 table as `eval_e2e/corpus_index.json`: per uid, paths to every asset + labels + split assignment. This file *is* the three-way alignment table (M03 plan §4.5) made executable.
- **`eval_e2e/split.json`** — uid-hash split, ~30 CALIB / ~70 EVAL (`sha1(str(uid)) % 10 < 3`, same rule as the module plans so module-level and system-level CALIB sets coincide — a uid must never be CALIB for one module and EVAL for another, or module tuning leaks into system EVAL).
- **`eval_e2e/report.py`** — one reporting path for all experiments: three-figure tables (detection / equivalent-mutant specificity / clean false-alarm), per-defect-class and per-tag (linear/conditional) stratification, exact-binomial or bootstrap-over-uids CIs, INCONCLUSIVE rates reported separately (never folded into either PASS or FAIL).

Acceptance for the harness itself (Phase E0): 5 hand-picked uids (1 linear, 1 conditional, 1 loop-bearing, 1 with admitted variants, 1 previously gate-refused e.g. uid 4) run end-to-end reproducibly twice with identical verdict JSON.

---

## 4. Statistical protocol (pre-registered, computed this session)

Exact one-sided 95% binomial lower bounds (Clopper–Pearson, computed 2026-07-11): n=100 @ 0.95 observed → LB 0.898; n=150 @ 0.95 → **0.906**; n=200 @ 0.95 → 0.917; n=300 @ 0.95 → 0.924. Power to defend a pre-registered "≥90%" when the true rate is 95%: n=150 → 0.66, **n=200 → 0.80**, n=300 → 0.95.

Rules:
1. **Pre-register ≥90%** for every detection claim (RQ2, RQ4). n floors: no rate below **150** EVAL items; target **≥280** (both mutant corpora clear this: 427 code mutants ≈ 300 EVAL after split; 280 BPMN mutants planned).
2. RQ1/RQ3 (FA rates): report point estimate + exact CI; pre-register the acceptable bound (≤10%) on CALIB before EVAL.
3. RQ3/SYS-5 clustering figures: pairs are correlated within uid → **bootstrap over uids**, not binomial over pairs; if the admitted pool is still ~20 at run time, publish as *pilot* with per-uid table and no headline rate (M03 plan §4.2 verbatim).
4. Stratify everything by `linear`/`conditional` tag and by defect-operator class; a headline rate that hides a 0% class is worse than no headline (report the per-class minimum alongside the aggregate).
5. Multiple-comparisons hygiene: the five RQ figures are the *confirmatory* set, pre-registered; everything in SYS-6/7 is labeled exploratory.

---

## 5. The experiment suite

**SYS-1 — Correct-code specificity (RQ1).** EVAL-split base programs (~70, minus uid 90) + all EVAL admitted variants through `run_e2e`. Expect PASS. Figures: FA rate overall + by tag; INCONCLUSIVE rate separately with reasons histogram. *This is the first experiment to run and the system's smoke test — the M01 session measured base-FA ≈ 100% pre-fix; this figure is the proof the Phase-0 work landed.*

**SYS-2 — Code-defect detection (RQ2).** EVAL-split code mutants (~300) vs their uid's spec. Expect FAIL, with `violated_properties` non-empty. Figures: detection by operator class (the M02 taxonomy: logic/branch/order/return classes) + tier attribution (which P0/P1/P2 property fired — ties the verdict back to M01's hierarchy claim, novelty 5). Controls: the equivalent-mutant set must PASS (specificity figure).

**SYS-3 — Implementation freedom (RQ3).** All admitted variants: (a) E2E PASS rate (should match base FA), (b) cluster-with-base rate under M03 (the fixed pipeline's version of the 0.459/0.630 baseline — the before/after table across the whole program is this cell), (c) rejected_behavioral variants as the negative control (should FAIL or singleton). Gate: if A.3 corpus expansion happened, headline; else pilot-labeled.

**SYS-4 — Spec-side sensitivity (RQ4).** EVAL-split BPMN mutants (~280) paired with their uid's *correct base program*. Expect FAIL (the spec no longer matches the code). Figures: detection by BPMN operator (branch_drop, gateway_type_swap, condition_negate…); BPMN equivalent-mutant controls must PASS. This is the experiment that proves the *spec track* is load-bearing — without it, an examiner can claim the system only ever checks code against code.

**SYS-5 — Clustering utility (RQ5).** For every uid with ≥2 implementations: run Phase D (i) on every implementation directly, (ii) on cluster representatives with verdict propagation. Figures: verdict-agreement rate (must be 100% — any flip is a correctness bug, not a trade-off), wall-clock and model-checking-call reduction (the honest version of the wiki's "per-cluster cost" claim), cluster-quality P/R vs the manifest ground truth.

**SYS-6 — Ablations (exploratory; each isolates one claimed contribution).**
(a) divergence-sensitivity OFF → rerun SYS-2's livelock/loop mutants: detection drop = the feature's measured value (M03 novelty 2).
(b) P0 sentinel tier OFF → SYS-2 order-violation classes: drop = M01 novelty 4's value; also measures NC-3-style veto prevalence honestly.
(c) certificate gates OFF (accept all WIRs/specs) → FA change on SYS-1: the gates' value, and the cost of the M03 session's 38/101 miscalibration if it regressed.
(d) task-name obfuscation (rename code calls to synonyms/abbreviations) → SYS-1/SYS-2 deltas per matcher tier (lexical/Levenshtein/NLP): the semantic-matching cascade's value and the corpus's name-alignment threat, measured.
(e) `strict` vs `task_only` comparison mode on cross-impl steps: reproduce the 0.25→0.10 FA gap at system level.

**SYS-7 — Baselines (exploratory but committee-critical: "compared to what?").**
(a) **LLM-as-judge**: prompt a frozen model (pin id + temperature) with utterance + BPMN XML + code → correct/incorrect; same EVAL items as SYS-1/2/4. The expected story: competitive on gross defects, no counterexamples, no calibration, unstable across runs — VibeCheck's differentiators are the certificate trail and the trace.
(b) **Sequence-string diff**: naive baseline — extract call sequence by regex, string-compare to IBM's expected sequence. Cheap, surprisingly strong on this corpus (name alignment) — if VibeCheck can't beat it on conditional uids, the formal machinery isn't earning its complexity; that comparison is the honest one to publish.
(c) **Execution-diff oracle** (the admission protocol itself) as the *upper-bound reference*, not a competitor — it needs concrete inputs and the base program (which the real use case doesn't have); position it as the ceiling static verification is reaching for.

**Error-attribution protocol (runs continuously, feeds refinement)**: every wrong verdict in any SYS experiment gets bisected before it counts as "analyzed": M01 fault (property suite ≠ gold-from-sequence property set for that uid), M02 fault (WIR ≠ gold-WIR, via `e2_structural.py` micro-F1), M03 fault (correct inputs, wrong verdict), or corpus/label fault. Output: `eval_e2e/reports/error_ledger.csv` (uid, program, expected, got, attributed-module, one-line cause). The ledger is both the refinement worklist (§6) and a thesis artifact (the correction-trail-as-methodology narrative that worked for M02's chapter).

---

## 6. Refinement protocol (evaluate → refine → freeze → evaluate)

The loop that makes "refine" honest — same discipline that produced M02's defensible numbers, formalized:

1. **R0 — Instrument first**: build the harness (E0) and run the full suite on **CALIB only**. Commit the raw baseline report, however bad. (Precedent: the committed 0.459/0.630 M03 baseline and M01's 3/100 — before-numbers are evidence of methodology, not embarrassment.)
2. **R1 — Ledger-driven fixing**: iterate on the error ledger, worst class first, *on CALIB uids only*. Each fix lands with (a) the module-level regression test from the relevant module plan, (b) a CALIB re-run showing the ledger row cleared, (c) no other row regressed. Thresholds/operating points may move freely here.
3. **R2 — Freeze**: when CALIB meets the pre-registered targets (FA ≤10%, detection ≥90% per class or a documented waiver per class), write `eval_e2e/OPERATING_POINT.md` (all thresholds: M01 coverage gate, M02 τ from `threshold.json`, M03 gate + loop_max + matcher tiers + comparison_mode) and tag the repo. **After this point no parameter moves.**
4. **R3 — EVAL, once**: run the full suite on EVAL. These are the thesis numbers. If EVAL exposes a defect so severe it must be fixed: fix, re-freeze, re-run, and **report both runs** (pre-registered protocol-deviation clause — one honest sentence beats an undisclosed second attempt).
5. **R4 — Sensitivity appendix**: sweep the frozen thresholds ±(one notch) on EVAL and plot verdict stability — demonstrates the operating point isn't a cliff (cheap, disarms the "you tuned it" question).

---

## 7. Presentation plan

**7.1 Thesis evaluation chapter** (mirror the Module-02 chapter's proven skeleton — `docs/thesis/module02_chapter_draft.md`'s three narrative decisions reused):
1. Lead with the honest arc: what the baselines were (3/100 M01, 0.459/0.459 M03, the vacuity findings), what the correction trail fixed, and the frozen-run results — the correction trail *is* the methodology contribution.
2. Master numbers table (one page): every RQ figure + n + CI + stratification minima, sourced only from the frozen R3 run. Same table drives the viva slide deck.
3. Per-RQ sections: SYS-1..5 each get design → figure → threat discussion. SYS-6/7 as "analysis" (exploratory-labeled).
4. Threats to validity: corpus construct skew (0 parallel gateways — descoped features listed as future work, consistent with both module plans), name-alignment threat + SYS-6d measurement, single-vendor dataset, seeded-defect realism (mitigated by the multi-impl *natural* variants), small admitted pool if unexpanded.
5. Reproducibility statement: pinned FLOW-BENCH SHA, seeds, `OPERATING_POINT.md`, one-command rerun.

**7.2 Figures** (build with the repo's figure conventions from `docs/thesis/figures/`):
- E2E funnel: 100 uids → adapter → gates → verdicts (with INCONCLUSIVE visible — the honesty figure).
- Detection-by-defect-class grouped bars, code-side (SYS-2) and spec-side (SYS-4) side by side.
- Before/after fix-trail climb (ledger milestones on x-axis, CALIB detection/FA on y — the M02 "detection climb" figure generalized to the system).
- Clustering cost curve (SYS-5): verification calls vs implementation count, with/without clustering.
- Ablation tornado: per-feature delta on the two headline figures (SYS-6a-e).

**7.3 Demo (viva)**: M04 UI driving `run_e2e` on two scripted uids — one PASS with certificate trail, one seeded-defect FAIL showing the violated property + counterexample mapped to the code line. Scripted and pre-recorded as backup; never a live random uid (until SYS-1's FA figure says random is safe).

**7.4 Reproduction package**: `eval_e2e/README.md` — clone → `fetch_corpus` (pinned SHA) → `run_suite --split eval` → report regeneration; plus the frozen `corpus_index.json`, `split.json`, `OPERATING_POINT.md`, seeds, and the error ledger. Apache-2.0 attribution for FLOW-BENCH.

---

## 8. Phase-ordered task list

| Phase | Tasks | Depends on | Effort |
|---|---|---|---|
| **E0 — Harness** | `eval_e2e/{run_e2e.py, corpus_index.py, split.json, report.py}`; 5-uid smoke ×2 reproducible | all three module T-lists done | M |
| **E1 — Corpus freeze** | Vendored BPMN @ pinned SHA; BPMN-mutant generation to ≥280 EVAL + equivalents; **admitted-variant expansion to ≥100** (Session-C machinery, NIM budget); `corpus_index.json` committed | E0; M02 owner for variants | M (mostly API budget + review) |
| **E2 — CALIB baseline** | Full suite on CALIB; commit raw baseline report + error ledger v0 | E0, E1 | S–M |
| **E3 — Refinement loop** | R1 iterations, ledger-driven, CALIB-only, regression-gated | E2 | **L** (the real work; budget the majority of remaining term time here) |
| **E4 — Freeze + EVAL** | `OPERATING_POINT.md`, tag, single EVAL run (R3), sensitivity sweep (R4) | E3 targets met | S–M |
| **E5 — Ablations + baselines** | SYS-6a-e, SYS-7a-c on frozen system | E4 | M |
| **E6 — Presentation** | Chapter section, 5 figures, master table, demo script, repro package | E4 (E5 folds in) | M |

Sequencing notes: E1's variant expansion can start immediately (independent of module fixes); E5 can overlap E6; the joint M01↔M03 property-suite contract doc (both plans' shared task) is a *prerequisite of the premise*, not of this plan — verify it exists before E0.

---

## 9. Top risks to this plan

| # | Risk | Mitigation |
|---|---|---|
| 1 | Module fixes assumed done aren't (esp. M03 0.4 stuttering rewrite, M01 0.2 soundness) | E0's 5-uid smoke will expose it immediately; fall back to module T-lists — do not start E2 on a broken premise |
| 2 | Admitted-variant pool stays at 20 → RQ3/RQ5 stuck at pilot | Start E1 expansion first (it's slow-but-parallel); pre-write the pilot-framing paragraph as the fallback |
| 3 | Refinement overfits CALIB (30 uids is small) | Per-class targets not aggregate; R4 sensitivity sweep; the uid-hash split matches module-level splits so no leakage |
| 4 | INCONCLUSIVE becomes a dumping ground that flatters both headline figures | Report INCONCLUSIVE rate as a first-class figure with a pre-registered ceiling (≤10%); ledger every instance |
| 5 | Baseline (b) sequence-diff *beats* the system on linear uids | Plausible and fine — the claim to defend is on conditional/loop uids + counterexample quality + no-oracle-needed; write that framing before seeing the numbers |
| 6 | Term runs out mid-E3 | The committed CALIB baseline + partial ledger + module before/afters are already a defensible "evaluate → diagnose → fix" chapter; E4's frozen run is the stretch goal, not the only story |

---

## Next actions (first sitting)

1. Verify the premise: confirm M01 T1–T7 / M03 T1–T8 completion state against `develop` (the module plans' acceptance criteria are the checklist) — anything missing goes back to its module list before E0 starts.
2. Create `eval_e2e/` with `corpus_index.py` + `split.json` (uid-hash rule shared with module plans) and commit the index built from today's verified asset inventory (§2).
3. Kick off E1's variant expansion with M02's owner (`eval/gen_variants.py`, NIM key via env, raw-cache resumable) — it runs in the background of everything else.
4. Write `run_e2e.py` against the three module entrypoints (M01 `/verify`-equivalent, M02 `run_v3_pipeline`, M03 batch entrypoint) and pass the 5-uid smoke.
5. Run the CALIB baseline, commit the report and error ledger v0 — the before-numbers that anchor the whole refinement narrative.
