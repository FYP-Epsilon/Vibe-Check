# Thesis Parity Note — Module 01 and Module 03 Chapters Against the Module 02 Baseline

> Companion to `module01_chapter_outline.md`, `module01_chapter_draft.md`,
> `module03_chapter_outline.md`, `module03_chapter_draft.md`. Written for the commissioning session
> to check before placing anything in the repo.

---

## 1. What "parity" was taken to mean

The Module 02 chapter (`vibecheck-vault/Repo Docs/Thesis/module02_chapter_draft.md`, with its outline
alongside) sets the register. Parity was read as matching it on five specific behaviors, not on length
or section count:

1. **The chapter's spine is a negative or structural result**, not a feature tour. Module 02's spine is
   that self-referential validation cannot detect logic bugs — 0/220, measured, stated in the
   introduction and returned to throughout.
2. **Every number is traceable to a named artifact**, and superseded numbers appear in an explicit
   correction trail rather than being silently dropped or silently preferred.
3. **Measured, designed, and inferred are distinguished at the point of use** — not collected in a
   caveats appendix.
4. **Limitations are costed**: each states its measured magnitude in the same sentence as the
   limitation.
5. **Contributions are paired with the evidence that carries them**, and claims without evidence are
   named as unsupported rather than hedged into the prose.

All five are matched in both new chapters. Where the new chapters deviate, the deviations are listed in
§4 with reasons.

---

## 2. Chapter-by-chapter parity summary

| Dimension | Module 02 (baseline) | Module 01 (new) | Module 03 (new) |
|---|---|---|---|
| Spine | Self-referential validation cannot detect logic bugs (0/220) | Checkability: 45 of 412 synthesized properties are conformance-bearing; the corpus is lost upstream of synthesis | Two independent channels by which a correct model checker returns `COMPLIANT` while proving nothing |
| Headline measured result | 0/220 genuine-bug detection; 0.9952 (n=210) on the mutant corpus | 29/48 admitted; 0/48 PASS; 45/256 P1 checkable (17.6%) | 35/35 bridge cross-validation; ~71% of pre-fix definitive verdicts untrustworthy; detection 0.357 [0.13, 0.65] n=14 |
| Evaluation design | FLOW-BENCH mutants, Youden's J calibration | No detection evaluation — admissibility / checkability / self-consistency instead, with the reason argued in §4.1 | 6 gold specs, injected mutations, Clopper–Pearson intervals on every rate |
| Correction trail | In-chapter, with what superseded what | §4.4.4 (2 entries) + T4.3 in the outline | §6.12 (6 entries + 1 excluded figure with its reason) |
| Unsupported claims named | Yes | 5, in the outline's final section | 7, in the outline's final section |
| Cross-chapter link | — | To Ch5's 0/220 (§4.1) and Ch6's blindness measurement (§4.6) | To Ch5's 0/220 (§6.1 and §6.6) and Ch4's checkability funnel (§6.8.4) |

---

## 3. The four cross-chapter dependencies, and where each is stated

These are the places where one chapter's correctness depends on another's. Each is stated in **both**
chapters deliberately — a reader who reads one chapter should not be able to miss it.

**(a) Non-converged property suites underlie every conformance number.** Module 01 exports all 29
surviving suites under PBCTS non-convergence; 0 of 48 specifications reach an unqualified `PASS`. Every
Module 03 verdict is checked against such a suite. Stated in Ch4 §4.4.2 and Ch6 §6.10(13), with
identical wording on the substantive claim. **This is the single most important thing for the
commissioning session to verify in current source**, since the status code was renamed after the
measurement was taken.

**(b) Omission blindness is measured twice, independently, from the two sides.** Ch4 §4.6 derives it
from the property shape (weak-until precedence is vacuously satisfied by omitting the later task) and
measures 23 of the 43 (spec, variant) pairs as omission-only (of the remainder, 15 are exactly
conformant, 3 combine omission with reordering, 2 are reordering-only), with 7 of the 23 producing
no failing checkable property.
Ch6 §6.8.4 measures it end-to-end as 0 of 16 drop-step detections. The two are presented as
corroborating measurements of one gap, not as one finding cited twice.

**(c) The P0 reclassification is argued in Ch6 and consumed in Ch4.** The strong claim — sentinels are
unfalsifiable under *any* faithful lifting, not merely under one candidate lifting — is developed in
Ch6 §6.6 where the lifting is defined, and Ch4 §4.5.3 cites it there rather than re-deriving it. Both
chapters draw the same conclusion: reporting 79 passed sentinels would reproduce Ch5's
self-referential failure at this seam.

**(d) The LTLf/LTL semantic gap is created in Ch4 and paid for in Ch6.** Ch4 §4.3.5 states that
exporting LTLf strings hands the finite-trace obligation to the consumer, and says explicitly that the
decision is defensible and not free. Ch6 §6.4 implements the reduction and §6.9 records the unresolved
collision with divergence sensitivity. Neither chapter presents the string interface as obviously
correct.

---

## 4. Deliberate deviations from the Module 02 baseline

**(i) Module 01 has no detection rate, and §4.1 argues why rather than apologizing.** Detection is a
relation between a specification and an implementation; the module is one half of it. Three different
measurable properties are substituted (admissibility, checkability, self-consistency) and all three are
measured. A reader arriving from Ch5 looking for a comparable headline figure is told in the first
section that there is not one and why.

**(ii) Module 03's chapter contains two central results rather than one.** The two vacuity channels are
independent, were diagnosed separately, and needed different fixes; collapsing them into one narrative
would misrepresent the finding. §6.5 and §6.6 are parallel sections with the same internal structure
(mechanism → why tests were silent → fix → evidence).

**(iii) Module 03 §6.9 is an open problem, not a limitations bullet.** The vacuity/divergence collision
sits at the intersection of the chapter's two main design commitments. Demoting it to §6.10 would
understate it.

**(iv) Both new chapters name unsupported claims in their outlines rather than their drafts.** Ch5
handles this inline. Keeping the "do not write this" list out of the draft prose was a practical choice
for the commissioning session's benefit; if the repo convention is inline, those sections should be
folded into the drafts' limitations before placement.

**(v) Neither new chapter has a figure like Ch5's Youden's-J calibration curve,** because no
comparable calibration artifact exists for either module. The centerpiece figures proposed instead are
Ch4's checkability funnel (F4.1) and Ch6's two-channel comparison (F6.2) plus the verdict-shift Sankey
(F6.3).

---

## 5. Verification checklist for the commissioning session

Ordered by how much damage an error would do.

**Must verify before placement:**

1. **The export status code.** Ch4 §4.4.2 states 0/48 PASS with all 29 exports under PBCTS
   non-convergence, and notes the status was renamed after the measurement. Confirm the current name
   in `module_01_spec/src/` and that the test pinning library/service agreement exists. Both chapters
   depend on this.
2. **The 45 checkable properties and the 412 total.** Ch4 §4.5.1–§4.5.2 and Ch6 §6.3.5 must agree, and
   both derive from the same corpus run. Confirm the tier census (79 / 256 / 29 / 48 / 0) and the
   211 `node()`-bearing count.
3. **The pre/post verdict distributions** `{18, 17, 23}` → `{5, 10, 43}` and the per-bucket flows, from
   `CP1 Lifting-Scope Decision.md` and `cp1_crosstab_raw.json`. Ch6 §6.7.6 is traced check by check and
   any arithmetic error there is visible.
4. **Every rate in Ch6 §6.8 against `demo/eval_e2e/results/e2e_eval_report.md`,** including intervals:
   abstention 0.462 [0.27, 0.67] n=26; detection 0.357 [0.13, 0.65] n=14; false alarm 0.000 [0.00,
   0.84] n=2; counterexample 0.800 [0.28, 0.99] n=5; and the by-kind table 16/0/4/12 and 10/5/5/0.
5. ~~The verbatim test-suite quotation in Ch6 §6.5.2 and §6.11~~ — **checked and corrected during
   placement.** The originally-drafted quote (`assert result.is_compliant is True  # vacuously
   true`) misquoted the field name and the file has since changed further: the real pre-fix line
   was `assert result.verdict == "COMPLIANT"  # vacuously true` in
   `test_finite_automaton_passes_all_properties` (`test_cpp_engine.py:407`), and that same test was
   rewritten by the fix to `test_finite_automaton_no_longer_vacuously_passes`, now asserting
   `VIOLATION`. Both chapter files have been corrected to the verified quote and framed as a
   historical (pre-fix) citation.

**Should verify:**

6. Ch6's test-function count (142 across 6 files) and the 118/115/2/1 run status — these are snapshot
   figures and will drift.
7. The 47.5% / 45.5% definition-vs-call-order pair. Both are reported deliberately; confirm both
   sources exist and that neither has been superseded.
8. The 86.0% mean name-match figure and 26/43 at 100%.
9. That the 0/20 splitting-gateway result (no default flow, no condition expression) is stated as
   measured in its source, since Ch4 §4.4.3 leans on it heavily to argue the gate is correct.
10. SPOT versions: 2.11.6 vendored/pinned in the `module_03_equiv` Dockerfile (the only one that
    builds SPOT — `module_01_spec`'s Dockerfile no longer touches it, per item #11) versus 2.15.1 in
    the verification environment. Ch6 distinguishes them in three places.

**Known drift risks:**

- Line-number references (`pipeline.py:57`, `test_cpp_engine.py:404`, `lifter.cpp` ~499–512) will
  drift; prefer symbol names at final assembly.
- Chapter numbers are provisional (4 / 5 / 6).
- Ch6 §6.10(11) claims two pre-existing test failures persist unchanged; re-run before asserting.

---

## 6. Figures and tables proposed across both chapters

| ID | Chapter | Content |
|---|---|---|
| F4.1 | 4 | Checkability funnel, 48 → 29 → 22 → 45 → 6, each arrow annotated with cause and source (**centerpiece**) |
| F4.2 | 4 | Four-phase pipeline with gate condition and measured pass count per boundary |
| F4.3 | 4 | Tier census stacked bar (412), segmented by disposition, duplicates overlaid |
| T4.1 | 4 | Admission table: outcome × construct present, with the set-equality result |
| T4.2 | 4 | Vacuous-truth case analysis for the P1 precedence shape (5 rows) |
| T4.3 | 4 | Correction trail |
| F6.1 | 6 | Four-phase pipeline, annotated with the SPOT primitive per step and which track implements it |
| F6.2 | 6 | The two vacuity channels side by side: mechanism / test silence / fix / evidence (**centerpiece**) |
| F6.3 | 6 | Verdict-shift Sankey, `{18,17,23}` → `{5,10,43}` with traced per-bucket flows |
| F6.4 | 6 | Forest plot of the four end-to-end rates with Clopper–Pearson intervals, so interval width is the visual message |
| F6.5 | 6 | Detection by mutation kind, stacked, making 0/16 immediately visible |
| F6.6 | 6 | Worked alive-extension example with the manufactured-violation edge annotated |
| T6.1–T6.4 | 6 | Master numbers · tier gating with reasons · correction trail · verdict cross-tabulation |

Both centerpiece figures require only data already in the cited artifacts; no new computation.

---

## 7. Aggregate unsupported-claim list

Consolidated from both outlines, since a reader assembling the thesis needs one list. None of these
appears as a claim in either draft.

**Module 01:** kill-ratio and structural-coverage distributions across the corpus (only the binary gate
outcome is measured); what the designed task-coverage tier would recover (design argument with a worked
example, not a measurement); per-specification synthesis latency; whether the checkability rate
generalizes beyond FLOW-BENCH; why 0/48 converge (outcome measured, diagnosis open).

**Module 03:** any Phase A/B/C behavioral-equivalence evaluation (the largest gap); corpus-scale
witness validity on the corrected engine; clustering speedup (designed, unmeasured); per-tier
action-matching accuracy (and tier 3 was unavailable during verification); wall-clock performance of
any phase; the 12,600/12,600 differential-agreement figure (credible but unreproduced — Ch6 §6.12
explains why 35/35 is used instead); whether the driver heuristic generalizes off-corpus.

---

## 8. One-paragraph summary of what the three module chapters say together

Chapter 5 measures that a validation certificate derived from the code it checks cannot detect that
code's logic bugs. Chapter 4 supplies an independent oracle and measures how little of it is usable —
45 of 412 synthesized properties are conformance-bearing, most of the corpus is refused upstream for
underspecification the benchmark itself carries, and the surviving property shape is structurally blind
to the corpus's dominant defect class. Chapter 6 assembles the two tracks and finds that the checker
joining them was returning `COMPLIANT` for two independent reasons unrelated to any code, that its
passing test suite documented one of them as intended semantics, and that after fixing both — plus the
discovery that the automaton being checked represented file layout rather than execution — the
end-to-end detection number went *down* while becoming meaningful for the first time. The three
chapters share one thesis: oracle independence is necessary and nowhere near sufficient, and most of
the work in making a conformance verdict mean anything lies in establishing that the check could have
failed.
