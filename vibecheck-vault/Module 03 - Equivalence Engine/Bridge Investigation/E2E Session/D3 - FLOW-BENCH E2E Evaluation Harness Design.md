# D3 — FLOW-BENCH E2E Evaluation Harness Design

> Repo at `main @ 0daf57e`. Depends on all findings in
> `00 - Session Findings and Plan Impact.md`. Raw measurements: `e2e_verification_log.json`.

## 1. Corpus inventory — what is actually available (VERIFIED-EXPERIMENT)

Everything downstream depends on these denominators, so they are stated first.

| Quantity | n | Source |
|---|---|---|
| BPMN specs in `flow-bench/data/context/` | 48 | all `*.bpmn`, namespace-aware parse |
| Base programs in `module_02_extract/eval/corpus/` | 101 | |
| Normalized variants in `eval/variants/normalized/` | 184 | across 99 uids |
| Mutants in `eval/mutants/` | **427** | (the vault's corrected figure — confirmed) |
| **Specs Module 01 can export a suite for** | **29** | 19/48 hard-fail (F1) |
| Variant *files* whose uid has a spec | 82 | |
| **(spec, variant) pairs that are e2e-runnable** | **43** | 29 eligible uids ∩ variants |
| Mutants on e2e-eligible uids | **96** | of 427 |
| Mutants blocked by gateway specs | **131** | unusable until M01's Phase-3 gate admits them |

BPMN construct coverage, e2e-eligible subset vs full pool (VERIFIED-EXPERIMENT):

| construct | specs in pool | specs e2e-eligible |
|---|---|---|
| `task` | 48 | 29 |
| `subProcess` | 21 | 5 |
| `multiInstanceLoopCharacteristics` | 21 | 5 |
| `exclusiveGateway` | 19 | **0** |
| `userTask` | 2 | **0** |
| `parallelGateway` | 0 | 0 |

**This table is the single most important thing to put in the thesis' evaluation-scope section.**
The e2e result covers sequential workflows only, and that is a measured property of the toolchain's
current gates, not a corpus limitation.

## 2. Metric hygiene rules (apply to every metric below)

Three rules, each forced by a measurement:

1. **De-duplicate properties before counting.** 34 of 412 exported properties are exact duplicates
   within their own tier (VERIFIED-EXPERIMENT). Undeduplicated denominators silently weight some
   specs more heavily.
2. **Report `out-of-scope` separately from `INCONCLUSIVE`.** 288 of 412 properties are excluded by
   the D1 §5 tier gate (211 `node()`-bearing P1 + 29 P2 + 48 P3). Reporting them as INCONCLUSIVE
   would make the checker look 70% undecided when it was never asked.
3. **Report per-property and per-(spec,variant) rates separately.** A spec with 10 checkable
   properties would otherwise dominate one with 1. Median node()-free P1 per spec is 2
   (VERIFIED-EXPERIMENT), so per-property aggregation is dominated by a few large specs.

## 3. Module-wise evaluation

### 3.1 Module 02 — reuse as-is, no redesign

**VERIFIED-SOURCE.** `eval/calibrate.py`'s module docstring specifies the existing methodology:
50/50 CALIB/EVAL split stratified by semantic tag with fixed seed, threshold τ chosen on CALIB by
maximizing Youden's J on the `combined_confidence` ROC, then detection rate and false-alarm rate
reported on held-out EVAL with **exact Clopper–Pearson** binomial CIs (binomial CDF via
`math.comb`, inverted by bisection — no scipy). `eval/threshold.json` records the calibrated result:
`{"mode": "differential-corrected", "tau": 0.1, "youdens_j": 0.96, "seed": 1234}`.

The docstring also records the load-bearing negative finding — in `self` mode V1's oracle is a WIR
re-derived from the mutant itself, so it cannot distinguish a mutant from its base — with an
explicit instruction never to regenerate the calibration report from a differential run.
**Do not touch any of this.** The e2e harness reuses the *methodology* (stratified split, Youden's J
on CALIB, Clopper–Pearson on EVAL) and reuses `clopper_pearson()` (already implemented,
`eval/c5_experiments.py`), but writes its own runner so Module 02's reports stay reproducible.

When citing Module 02 numbers in the thesis, use the vault's master numbers table only
(e.g. genuine-bug detection 0.9952, n=210); 427 mutants, not 429.

### 3.2 Module 01 — designing evaluation that does not exist yet

Module 01 has zero tests and zero evaluation. Four measurable things, all runnable today (I ran
all four this session, so the harness is re-implementing a measured procedure, not a hypothesis):

**(a) Pipeline admission rate by BPMN construct.** Run `run_module_01_pipeline()` over all 48 specs,
cross-tabulate outcome against constructs present. Measured baseline (VERIFIED-EXPERIMENT):
19 `FAIL`, 29 `FAIL_ALIGNMENT_UNPROVEN`, 0 `PASS`; and **the hard-fail set is exactly the
`exclusiveGateway` set** (set equality tested true). This single table is the strongest Module 01
evaluation result available — it localizes the entire branching gap to one gate.

**(b) Synthesis coverage per construct.** Properties emitted per spec, per tier, normalized by
node count. Measured baseline: 412 properties over 29 specs — P0 79, P1 256, P2 29, P3 48,
`synthesized_mutant_killers` 0.

**(c) Checkability rate — the metric that matters most and does not exist anywhere yet.** Of the
properties synthesized, what fraction can *in principle* be evaluated against code?
Measured baseline: **45/256 = 17.6% of P1** (node()-free), 0/29 P2, 0/48 P3 (needs bridge),
P0 excluded by design. A synthesizer that emits many unusable properties is not a good
synthesizer, and no current metric would reveal that.

**(d) Oracle self-consistency.** Evaluate each spec's own task order against its own property
suite; it must be 100%. Measured baseline: **45/45 satisfied** (VERIFIED-EXPERIMENT, via
`evaluate_ltlf()` at `module_01_spec/src/ltlf_eval.py:202`). This is the guard that catches a
synthesizer regression producing self-contradictory properties, and it is cheap.

Also worth reporting: `tier_semantics` describes 3 tiers while the suite ships 5
(VERIFIED-EXPERIMENT) — a spec-completeness defect the harness should assert on.

Module 01 also needs actual unit tests; `module_01_spec/src/main.py` still imports the deleted
`automata_lifter` in both branches of its import fallback and the module is absent from `src/`
(VERIFIED-SOURCE), so the FastAPI app cannot start. That is a Milestone-0 fix, not an evaluation
metric, but it means "Module 01 works" is currently only true of the library, not the service.

### 3.3 Module 03 — two separately measurable capabilities

**(a) Behavioral equivalence (Phases A/B/C) — measurable without any spec.** This is the capability
the prompt correctly identifies as independently evaluable. Metrics:
- **Clustering agreement with behavioral ground truth.** Variants of the same uid that are
  semantically identical should cluster together. FLOW-BENCH gives a natural label: same uid,
  different model. Measure with adjusted Rand index or pair-counting precision/recall against
  "same uid" as the reference partition — with the caveat that two variants of one uid may
  legitimately differ (28 of 43 pairs diverge from spec, VERIFIED-EXPERIMENT), so *disagreement
  is not automatically error*. Report the confusion, not a single score.
- **Stuttering-reduction fidelity.** Phase B must not collapse a divergent loop (`while True: pass`)
  into a normal wait state. This is a property-based test with hand-built fixtures rather than a
  corpus metric, and the C++ track's 28 hardcoded geometry assertions already encode part of it
  (VERIFIED-SOURCE).
- **Determinism.** Same WIR in → same quotient out, across runs. Cheap, and the NLP tier
  (`lifter.cpp:135`, tier 3 via `nlp_utils`) is a plausible nondeterminism source worth pinning.

**(b) Spec-conformance model checking (Phase D)** — this is the full-project metric, §4.

## 4. Full-project evaluation: the labeled conformance corpus

FLOW-BENCH gives spec↔code pairs with **no conformance labels**. The prompt asks how to extend
Module 02's mutation machinery into the conformance setting. Here is what the existing machinery
actually yields, measured.

### 4.1 The mutation operators, and which are conformance-relevant

**VERIFIED-SOURCE**, `eval/mutate.py:199` — 10 operators: `negate-guard`, `boundary-shift`,
`swap-branches`, `off-by-one-loop`, `drop-step`, `reorder-steps`, `wrong-variable`,
`corrupt-container-op`, `early-return`, `constant-perturb`. Distribution over the 427 mutants
(VERIFIED-EXPERIMENT): `drop-step` 101, `reorder-steps` 99, `early-return` 99,
`wrong-variable` 36, `negate-guard` 32, `corrupt-container-op` 30, `constant-perturb` 21,
`swap-branches` 8, `boundary-shift` 1.

`drop-step` and `reorder-steps` map directly onto the two conformance divergence modes (omission,
reordering). That is a genuine piece of luck: **the existing mutation machinery already generates
the right kind of defect**, and the extension is labeling, not new generation.

### 4.2 What a conformance label can honestly be derived from

I derived candidate labels for the 96 eligible mutants by comparing each mutant's spec-observable
call sequence against its base program's (VERIFIED-EXPERIMENT):

| operator | spec-observable change | no static observable change |
|---|---|---|
| `drop-step` | **27** | 2 |
| `reorder-steps` | **16** | 12 |
| `early-return` | 0 | **28** |
| `wrong-variable` | 0 | 5 |
| `negate-guard` | 0 | 2 |
| `corrupt-container-op` | 0 | 2 |
| `constant-perturb` | 0 | 2 |
| **total** | **43** | **53** |

So the labeled divergent set is **43 mutants** across 29 uids, from `drop-step` and
`reorder-steps` only.

**The `early-return` result is the important one and must not be mislabeled.** All 28 eligible
`early-return` mutants show *no* change in the statically-extracted call sequence — an early return
removes calls at *runtime* while leaving them present in the source. These are genuine conformance
divergences that a static call-order lifting cannot see. **REASONED** (chain: the lifter derives
actions from WIR nodes, which are static CFG nodes → an early return changes reachability, not node
presence → an action atom still appears): labeling them "divergent" and counting the resulting
misses against the checker would be measuring an *architectural* limitation of static lifting, not a
lifter defect. They belong in the report as a **named, quantified out-of-scope class (28 mutants)**,
not in the recall denominator. Reachability-aware lifting would be required to catch them; that is
future work.

Likewise the 12 `reorder-steps` mutants with no observable change: the reorder happened inside a
function body or among non-spec calls. They are **conformant-equivalent** — a *good* addition to the
conformant class, since they test that the checker does not fire on irrelevant edits.

### 4.3 Corpus construction

| class | source | n |
|---|---|---|
| **divergent (labeled)** | `drop-step` + `reorder-steps` mutants with spec-observable change | **43** |
| **conformant (labeled)** | base programs on eligible uids | 29 |
| **conformant (labeled)** | mutants with no spec-observable change (`reorder-steps` 12, plus the non-observable others where the base was conformant) | up to 53, screen individually |
| **naturally divergent** | LLM variants measured divergent from spec | 28 of 43 pairs |
| **naturally conformant** | LLM variants measured exactly conformant | 15 of 43 pairs |
| **out-of-scope (reported, not scored)** | `early-return` | 28 |

Two label provenances, which must be kept separate in the results table: **synthetic** (mutation,
label by construction) and **natural** (LLM variants, label by measured call-order comparison).
The natural labels are only as good as the comparison oracle, and that oracle has a known
limitation — see §4.4.

### 4.4 A labeling-oracle caveat I have to disclose

My natural-divergence labels come from comparing the code's call order against the spec task
order derived by a single-successor walk of the semantic graph. **VERIFIED-EXPERIMENT: that walk
reaches every task node in only 24 of 29 specs**; in 5 specs some tasks are unreachable by
single-successor traversal, so the derived spec order is incomplete.

This is not cosmetic. Using the naive labels, the call-order lifting appears to have a **44.4%
false-positive rate**; restricting to the 24 specs where the walk is complete, the false-positive
rate is **0.0%** (VERIFIED-EXPERIMENT). **The entire apparent false-positive signal was a labeling
artifact.** The harness must therefore (a) use a proper graph traversal for spec order, not a
single-successor walk, and (b) report the walk-completeness check as a harness self-test. I flag
this prominently because it is exactly the kind of artifact that would otherwise be written up as
a finding about the tool.

### 4.5 Full-project metrics

Per (spec, code) pair, and separately per property:

- **Detection rate (recall on divergent)** with Clopper–Pearson 95% CI.
- **False-alarm rate (1 − specificity on conformant)** with CI.
- **INCONCLUSIVE rate** — first-class, not an error bucket. Given F2, the pre-fix baseline is
  expected to be 100%, and demonstrating it drop after the atom fix is itself a result.
- **Witness validity** — of the FAILs, what fraction have a counterexample trace naming actions
  that actually execute? D2 §6 measured that 10 of 11 of the current lifter's extra detections have
  non-executable witnesses. **This metric is novel and is arguably the paper's most interesting
  contribution**: it separates "right verdict" from "right reason", which no standard
  precision/recall table captures.
- **Youden's J** on the same convention as Module 02, for comparability across chapters.

Stratify every metric by: divergence mode (omission / reorder / both), label provenance
(synthetic / natural), and lifting model (definition-order / call-order) so D2's paired comparison
is reproducible from the harness output.

## 5. Results table shape

Three tables. Table 1 — corpus and scope (§1 inventory + construct coverage; establishes what was
*not* measured). Table 2 — module-wise: one block per module, with Module 01's four metrics
(§3.2), Module 02's existing calibrated figures cited from the vault master table, Module 03's
equivalence metrics (§3.3a). Table 3 — full-project: rows = lifting model × divergence mode,
columns = n, detection ± CI, false-alarm ± CI, INCONCLUSIVE rate, witness validity.

Plus one figure that earns its place: **detection rate vs witness validity for the two lifting
models**, which shows the D2 trade visually — definition-order lifting sits higher on detection
and far lower on witness validity.

## 6. Harness placement

New directory `eval_e2e/` at repo root, not inside any module — it necessarily touches all three
and putting it inside one would breach the module boundary that the architecture is built on. It
consumes Module 01's exported JSON and Module 02's WIR through their public interfaces only, which
preserves the dual-track independence: the harness reads two independently-derived artifacts and
never feeds one module's output back into the other's input.

Reuse `clopper_pearson()` from `eval/c5_experiments.py` and the split/τ convention from
`eval/calibrate.py` rather than reimplementing statistics.
