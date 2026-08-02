# feat(mod1): FLOW-BENCH evaluation harness for the Specification Engine

`feat/mod1/flowbench-eval-harness` → `demo/evaluation-finale` (base `f55053a`)

Implements the corpus-scale evaluation the FlowBench design memo proposed in
its Section 5. The memo was explicitly a design proposal that wrote no code
into any module; its pilot scripts lived in a scratch workspace and are gone.
This branch makes that methodology a permanent, tested, re-runnable part of
the repo.

**Evidence classes** (same legend the memo and PR #89 use):

| Tag | Meaning |
|---|---|
| `[SRC]` | Source-verified — read directly in the repo at `f55053a`, path cited. |
| `[EXP]` | Experiment-verified — measured on this branch, procedure stated, reproducible. |
| `[REAS]` | Reasoned — follows from `[SRC]`/`[EXP]` facts but not itself measured. |
| `[OPEN]` | Not established — stated as an open question, not a finding. |

---

## Scope

Additive only. `[EXP]` `git status` after the work shows two new paths —
`module_01_spec/eval/` and this PR description — plus the pre-existing
untracked `.claude/settings.local.json`. No file under `module_01_spec/src/`,
`module_02_extract/`, `module_03_equiv/`, `module_04_ui/`,
`shared_schemas/`, or `demo/` is modified — `git diff --stat` over those
paths is empty. The 56 pre-existing Module 01 tests still pass unchanged.

```
module_01_spec/eval/
  gold_bpmn.py        220  independent XML labeler (never imports src/)
  soundness.py        247  primary metric
  mutate_eval.py      201  secondary metric (discriminative kills)
  report.py           814  report + per-diagram CSVs
  test_gold_bpmn.py   232  labeler + anti-circularity + non-vacuity tests
  test_harness.py     321  metric, statistics, and corpus regression tests
  conftest.py          15  registers the `slow` marker
  results/                 generated report + 3 CSVs (148 rows each)
```

`[EXP]` 42 tests, all passing (`pytest module_01_spec/eval/`, 2.0s).
29 of them need no corpus and run under `-m "not slow"`.

## What it measures

**Primary — suite soundness.** Does a synthesised LTLf suite accept the
unmutated diagram it was derived from? A suite that rejects its own source
cannot be a faithful formalisation of it, and any kill ratio computed against
such a suite is uninterpretable. `[EXP]`

| corpus | all | branch | no-branch |
|---|---|---|---|
| `output` | 98/100 = 0.9800 [0.9296, 0.9976] | 31/31 | 67/69 |
| `context` | 47/48 = 0.9792 [0.8893, 0.9995] | 18/19 | 29/29 |

**Secondary — discriminative mutation kills.** `[SRC]` `LTLfAuditor.is_killed`
(`module_01_spec/src/mutation_refiner.py`) returns `True` whenever a mutant
has no complete trace, so a mutation that severs the graph scores a kill an
*empty* property suite would also have scored. Only the property mechanism
measures suite strength. `[EXP]` On sound-suite diagrams, **0 of 2900**
mutants across both corpora were killed by a property; 1672 were
disconnection kills and 1228 survived.

**Structural fidelity.** `[EXP]` Node and edge F1 are both 1.0000 on all 148
diagrams, graded against a labeler that reads the BPMN XML directly.

## Reproduction of the known-good figures

`[EXP]` Every figure the memo and PR #89 established reproduces exactly, and
each is pinned as a regression test rather than merely observed:

| Figure | Expected | Harness | Test |
|---|---|---|---|
| suite soundness | 145/148 | 145/148 | `test_soundness_counts_match_pr89` |
| branch stratum | 49/50 | 49/50 | `test_branch_stratification_matches_pr89` |
| no-branch stratum | 96/98 | 96/98 | `test_branch_stratification_matches_pr89` |
| unsound uids | `uid_67`, `uid_8`, `uid_92` | identical | `test_the_three_unsound_diagrams_are_the_known_ones` |
| sound-suite mutants | 2900 | 2900 | `test_sound_suite_crosstab_matches_pr89` |
| property kills | 0 | 0 | `test_headline_finding_zero_property_kills_on_sound_suites` |
| disconnection kills | 1672 | 1672 | `test_sound_suite_crosstab_matches_pr89` |
| survived | 1228 | 1228 | `test_sound_suite_crosstab_matches_pr89` |
| unparseable properties | 0 | 0 | `test_no_unparseable_properties_remain` |
| corpus overlap | 47 shared, `uid_90` only | identical | `test_corpus_overlap_matches_the_memo` |

No mismatch was found, so no investigation of one was required.

## Anti-circularity

`[SRC]` The memo's own pilot labeler defined its node set as the *complement*
of the extractor's `NON_NODE_TAGS`, which makes agreement partly definitional.
This harness does not. `gold_bpmn.SPEC_FLOW_NODES` is an allowlist transcribed
from the BPMN 2.0 flow-node taxonomy, and `[EXP]` it contains three types the
extractor's `EXECUTABLE_NODES` omits — `transaction`, `adHocSubProcess`,
`complexGateway` — so the two vocabularies are provably not copies. Two tests
enforce this: an AST import scan (same discipline as
`module_02_extract/eval/test_gold_wir.py`) and a guard that those three types
stay in the gold vocabulary.

## Three things checked *before* reporting, because each could have invalidated a figure

**1. A perfect structural score might have meant a metric that cannot fail.**
`[EXP]` Node/edge F1 = 1.0000 across 148 diagrams is the kind of number that
usually indicates a vacuous metric. Injecting known defects into the XML the
extractor sees, while holding gold labels pinned to the pristine document:
deleting one task drops recall to 0.8889, retyping one task drops both
precision and recall to 0.8889. The metric moves. Those probes are now
permanent tests (`TestMetricIsNotVacuous`) rather than a one-off check.
`[REAS]` The score is still bounded by what the corpus exercises — the report
computes the construct census and names the gold-vocabulary types absent from
all 148 diagrams, about which the metric says nothing.

**2. The subProcess convention looked inert and is not.** `[EXP]` A first
draft of the report asserted the flatten-or-not question had no measurable
consequence. A census refuted this: 58 of 148 diagrams carry a `subProcess`
(61 wrappers). The report now computes node F1 under **both** conventions —
1.0000 adopted, 0.9693 flattened — instead of asserting inertness.
`[REAS]` The adopted convention is also the higher-scoring one, so the grounds
for it are argued from the standard rather than the outcome: in BPMN 2.0,
`SubProcess` is a subclass of `Activity`, itself a subclass of `FlowNode`.
Had the alternative been adopted, the 61 extra false positives would have been
an artifact of the labeling convention, not an extractor defect. The
counterfactual is disclosed in the report for exactly that reason.

**3. "Held-out replication set" overstates what `context` provides.**
`[EXP]` The memo describes `context` as a held-out replication set (n=48).
Its own overlap figures are exactly right — 47 shared uids, 53 output-only,
`uid_90` context-only — but they imply that only **1 of 48** `context` uids is
absent from `output`. `[REAS]` `context` is therefore a paired near-replicate,
the same workflows rendered differently, not an independently sampled held-out
set. Agreement between the two columns is evidence that a result is stable
across two renderings; it is not evidence of generalisation to unseen
workflows. The report states this, and a test fails if a future corpus swap
makes the wording understate the evidence. This refines the memo's framing; it
does not contradict its conclusion, which was that the corpora must not be
pooled — that remains correct and is the reason every rate is reported split.

## Decisions recorded rather than silently taken

`[EXP]` **Unparseable properties are counted, never filtered.** The memo's
pilots had to strip an unparseable `/* loop_bound=10 */` P2 property. PR #89
fixed that at source by moving the bound into typed `spec_metadata`, so
filtering would now conceal a regression rather than work around a limitation.
The count is 0 and a test asserts it stays 0.

`[EXP]` **Duplicate-atomic-proposition diagrams are labelled, never excluded.**
All 3 unsound diagrams carry the construct. Excluding them would raise the
headline soundness rate by redefining the denominator.

`[EXP]` **Unsound-suite kill rows are shown but marked not-a-detection.**
`uid_92` contributes 17 property kills; they come from the same P1 property
that already rejects its unmutated graph, so the mutation is incidental. The
report says so inline rather than leaving a row that looks like detection.

## Statistics

`[SRC]` Exact Clopper-Pearson binomial intervals at alpha = 0.05, matching
`module_02_extract/eval/calibrate.py`. Re-implemented by bisection on the
binomial CDF rather than cross-imported: `[EXP]` the project venv has no
scipy, and cross-module imports would make either eval harness unrunnable
without the other. A textbook value is pinned as a test
(CP(2,10) = [0.0252, 0.5561]). Seed 42, 20 mutants/diagram, matching the
shipped Phase 3 configuration. Every rate is stratified by branch/no-branch,
since branch-free diagrams admit a single trace and are far easier to satisfy.

## What this branch does *not* claim

`[REAS]` Soundness is computed with M01's own trace generator and own LTLf
evaluator. It detects internal inconsistency between property synthesis and
execution semantics; it does **not** establish that a suite faithfully
formalises the diagram's intended meaning. That needs an external oracle. The
structural-fidelity metric is the only one here graded against a genuinely
external reference.

`[REAS]` This branch changes no engine behaviour. It measures; it does not
improve. The 0/2900 discriminative kill figure is a finding about the property
suite's strength, and this harness makes it visible and regression-guarded —
it does not address it.

`[OPEN]` The LTLf↔LTL bridge to Module 03's independent model checker remains
unbuilt, so the genuinely independent oracle the memo identified is still
future work.

## Repo conventions

`[EXP]` GitNexus `detect-changes` after the work: 2 files, 0 affected
processes, risk **low**. `impact` on the three consumed classes
(`SemanticExtractionEngine`, `LTLfAuditor`, `BPMNMutationEngine`) reports
`processes_affected: 0` and `modules_affected: 0` for each — the harness is a
pure consumer and inverts no dependency.

One note for the reviewer: running `analyze` caused GitNexus to rewrite its
own symbol-count line in `CLAUDE.md` and `AGENTS.md` (8172 → 8578). That is
tool churn unrelated to this work, so both files were restored with
`git checkout` and are unmodified in this branch. A maintainer may want those
counts refreshed deliberately in a separate commit.

## Reproduction

```bash
venv/bin/python -m pytest module_01_spec/eval/ -q     # 42 passed
venv/bin/python module_01_spec/eval/report.py         # regenerates results/
```

Writes `results/m01_eval_report.md` and three 148-row CSVs
(`soundness_per_diagram.csv`, `mutation_per_diagram.csv`,
`structural_per_diagram.csv`), one row per diagram as the memo specified, so
any aggregate in the report can be recomputed or re-stratified independently.
