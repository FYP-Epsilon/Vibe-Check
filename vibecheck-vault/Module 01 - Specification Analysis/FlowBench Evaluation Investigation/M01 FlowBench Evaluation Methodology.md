# Design memo — a FlowBench-driven evaluation methodology for Module 01 (Specification Engine)

**Status:** design proposal. No implementation code written; no file under
`module_01_spec/`, `module_02_extract/`, `module_03_equiv/`, `module_04_ui/`, or `demo/`
was modified. Pilot measurements below were produced by throwaway scripts run from a
scratch workspace against a clean checkout.

**Repo state at time of writing:** `main @ 9165513`, working tree clean apart from an
untracked `.claude/settings.local.json`.

**Evidence classes used throughout.** Every claim carries one:

| Tag | Meaning |
|---|---|
| `[SRC]` | Source-verified — read directly in the repo at 9165513, path and line cited. |
| `[EXP]` | Experiment-verified — measured in this session, procedure stated, reproducible. |
| `[REAS]` | Reasoned — follows from `[SRC]`/`[EXP]` facts but not itself measured. |
| `[OPEN]` | Not established — stated as an open question, not a finding. |

---

## 0. Executive summary

The assignment was to design an evaluation methodology and choose between three
candidate ground-truth mechanisms. In the course of grounding the design against the
actual repo I ran a small pilot, and the pilot changed the recommendation.

Three findings dominate everything else in this memo:

1. **Phase 4 is dead on all 148 FlowBench diagrams.** `[EXP]` Every diagram in both
   FlowBench corpora returns `phase_4_certificate.status = "FAIL_WITH_ERRORS"` with the
   same parse error. The cause is a single hardcoded property containing a C-style
   comment that M01's own LTLf parser cannot tokenize `[SRC]`. The pipeline still
   reports overall `status = "PASS_PBCTS_UNCONVERGED"`, so this failure is invisible to
   anyone reading the top-level status.

2. **Roughly half of all property suites reject the very diagram they were derived
   from.** `[EXP]` 79/148 suites accept their own source diagram (0.534, 95% CI
   [0.450, 0.616]). The split is not random: **0/50** diagrams containing a branch
   produce a sound suite (95% CI [0.000, 0.071]), versus 79/98 non-branching ones
   (0.806, [0.714, 0.879]).

3. **The existing mutation kill ratio measures nothing about the property suite.**
   `[EXP]` On the 79 diagrams where a kill is even interpretable, **0 of 1580 mutants**
   were killed by an LTLf property violation (95% CI [0.0000, 0.0023]). All 1580 were
   killed because the mutation disconnected the graph, which `LTLfAuditor.is_killed`
   scores as a kill before consulting any property at all `[SRC]`.

Consequence for the assignment: **candidate (b), mutation testing on the BPMN spec, must
not be the headline metric** — in its current form its headline number is `1.0000` and
that number is produced entirely by a code path that never evaluates a property. And
candidate (c), cross-oracle consistency against `ltlf_eval`, is self-referential in
exactly the way Module 02 already documented and rejected `[SRC]`.

**Recommendation: a two-tier design.** A *soundness* gate (does the suite admit its own
source diagram?) as the primary published metric, with *discriminative* mutation kill
ratio — kills restricted to connected mutants killed by an actual property — as the
secondary metric, reportable only once the soundness gate passes. Section 5 gives the
reasoning, including the recursive check applied to this recommendation rather than only
to the rejected ones.

---

## 1. Corpus: resolving the open question in the brief

The brief flagged as unverified which FlowBench directory is the right corpus, noting a
100-file set and a 48-file set and asking whether the larger one should be preferred.

**The two directories are not alternative corpora.** `[EXP]` `flow-bench/data/output/`
and `flow-bench/data/context/` are the two halves of each benchmark case. Comparing
filename stems: 47 uids appear in both, 53 appear only in `output/`, 1 (`uid_90`) appears
only in `context/`. `[SRC]` The FlowBench README describes the task as translating natural
language into an intermediate representation that converts into BPMN; `context` is the
prior-state diagram supplied to the model and `output` is the expected result diagram.

Structural census `[EXP]` (parsed with ElementTree over the `bpmn:process` subtree; note
that a naive regex census undercounts because 37/100 and 21/48 files use the `bpmn:`
namespace prefix while the rest do not):

| | files | tasks | userTasks | exclusiveGateways | subProcesses | sequenceFlows |
|---|---|---|---|---|---|---|
| `output/` | 100 | 277 | 17 | 68 | 40 | 576 |
| `context/` | 48 | 141 | 2 | 40 | 21 | 293 |

Both have identical median tasks/diagram (3) and identical gateway range (0–4). 31/100
`output` and 19/48 `context` diagrams contain at least one branch point.

**Recommendation:** use **`data/output/`, n = 100**, as the primary M01 corpus. `[REAS]`
Three reasons. It is the larger set; it is the *expected result* half, so it is the
diagram a spec engine would legitimately be asked to formalise; and — decisively — the
existing end-to-end harness already consumes `data/context/` `[SRC]`
(`demo/eval_e2e/harness.py:62`), so using `output/` gives M01's standalone evaluation a
corpus that is not already entangled with the E2E numbers. Report `context/` as a held-out
replication set (n = 48) rather than pooling: pooling would double-count the 47 shared
uids, which are related diagrams, violating the independence assumption behind any
binomial interval.

**One caveat that must be stated in any writeup.** `[REAS]` FlowBench diagrams are small
and shallow — median 3 tasks, 69% of `output` has no branch at all, no
parallel/inclusive/event-based gateways occur anywhere in either corpus `[EXP]`. A
methodology validated only here establishes behaviour on simple sequential workflows.
It does not license claims about BPMN 2.0 coverage generally.

---

## 2. Baseline: what M01 actually does today

The brief asked me not to inherit a previously-recorded pass count and to re-derive a
baseline. Doing so:

**Unit tests.** `[EXP]` `pytest module_01_spec/tests/` → **35 passed**, 1.92 s. (The brief
carried 28; `git log 59a8bd8..HEAD -- module_01_spec/` is empty, so M01 has not changed
since that commit and 35 is the count at that snapshot too.) Note this required
`fastapi` to be installed — it is in `module_01_spec/requirements.txt` but absent from
the default interpreter, and without it collection aborts on `test_main_api.py`. So M01
does have tests, contrary to the "ZERO tests" note in the project brief; what it lacks is
a corpus-scale evaluation harness. `module_01_spec/eval/` does not exist `[EXP]`.

**Corpus run.** `[EXP]` `run_module_01_pipeline` over all 148 diagrams: 148/148 return
`status = "PASS_PBCTS_UNCONVERGED"`, 0 exceptions, total wall time 0.8 s for the full
148 (max 0.01 s per diagram). Phase 1 `PASS` 148/148; Phase 3 `PASS` 148/148.

**Phase 4 is uniformly broken.** `[EXP]` All 148 diagrams:

```
phase_4_certificate = {"status": "FAIL_WITH_ERRORS",
  "message": "Unexpected character '/' in formula
              '/* loop_bound=10 */ G(start -> F(done))'"}
```

`[SRC]` The offending property is appended unconditionally in
`module_01_spec/src/ltlf_synthesizer.py:225`:

```python
# Bounded Loop: Extractable and parseable template
self.ltlf_suite["P2_Quality_Limits"].append(
    "/* loop_bound=10 */ G(start -> F(done))"
)
```

`[EXP]` `evaluate_ltlf` accepts `G(start -> F(done))` and raises `ValueError` on the
commented form — the comment syntax is simply not in the tokenizer's `TOKEN_SPEC`. So
the P2 tier contributes exactly one property, to every suite, and that property is
unparseable by the module's own evaluator.

`[REAS]` This has a second-order effect that matters more than the dead phase. In
`mutation_refiner.LTLfAuditor._evaluate`, a parse exception is caught and treated as
"property did not hold" — i.e. as a kill. So the malformed P2 property kills *every*
mutant *and* the unmutated original. Measured: with the P2 property included, 148/148
suites reject their own source diagram and the kill ratio is 2960/2960 = 1.0000 `[EXP]`.
**Any kill-ratio or `C_struct` figure computed with the P2 property in the suite is
vacuous.** Every pilot number in this memo therefore excludes it, and any harness built
from this design must exclude it (or the bug must be fixed first).

---

## 3. The three candidate ground-truth mechanisms

### (a) Structural fidelity of the extractor against XML-derived expected counts

**What it measures.** Whether `SemanticExtractionEngine` loses or invents nodes and edges
relative to the BPMN XML.

**Pilot.** `[EXP]` I built an independent gold labeler that walks the XML and never
imports `semantic_extractor`, then scored micro precision/recall/F1 on
`(node_id, node_type)` and on `(flow_id, source, target)`:

| corpus | node P/R/F1 | edge P/R/F1 | tp / fp / fn (node) |
|---|---|---|---|
| `output` (100) | 1.0000 / 1.0000 / **1.0000** | 1.0000 / 1.0000 / **1.0000** | 682 / 0 / 0 |
| `context` (48) | 1.0000 / 1.0000 / **1.0000** | 1.0000 / 1.0000 / **1.0000** | 342 / 0 / 0 |

**What could invalidate this number, and the check.** A saturated F1 usually means the
gold labeler shares the system's own assumptions. My first labeler derived its node set
by *excluding* a `NON_NODE_TAGS`-shaped list — which is the extractor's own vocabulary,
so agreement would be partly definitional. `[EXP]` I re-derived gold from the BPMN 2.0
flow-node taxonomy as an explicit allowlist written from the standard (22 element types:
the event, activity, and gateway families), scored again, and got byte-identical
counts — 682/0/0 and 342/0/0, F1 = 1.0000 under both definitions. So the result survives
the circularity check.

**What it does not measure.** Everything downstream. `[REAS]` A perfect node/edge lift
says nothing about whether the LTLf properties synthesised from that graph are correct,
and Section 2 shows the graph is fine while the property suite is not. As a headline
number this would be actively misleading: a reader sees `1.0000` and infers the
Specification Engine works.

**Verdict: keep as a regression guard, reject as headline.** `[REAS]` It is already
saturated, so it has no discriminative power left on this corpus — it can only detect
future regressions. It is also structurally identical to what Module 02's E2 already
reports for the code track (also 1.0000 `[SRC]`,
`module_02_extract/eval/results/e2_structural_report.md`), so publishing it as M01's
evaluation would be the "borrowed framing" problem the brief warns about: importing M02's
metric shape rather than asking what M01's own failure modes are.

### (b) Mutation testing applied to the BPMN spec

**What it measures, in intent.** Whether the synthesised property suite is strong enough
to reject perturbed versions of the diagram it came from.

**Pilot, and why the headline number is an artifact.** `[SRC]`
`mutation_refiner.LTLfAuditor.is_killed` opens with:

```python
traces = self._generate_traces(mutant, depth=10)
# If no traces are generated, it means the mutant cannot reach any end event
# (disconnected) and is therefore killed.
if not traces:
    return True, "No complete execution traces generated (graph disconnected)"
```

So a "kill" conflates two very different events: a property caught the mutant, or the
mutation severed the graph and no property was ever consulted.

`[EXP]` Decomposing all 2960 mutants (148 diagrams × 20, seed 42) by which of those
happened, and cross-tabulating against whether the suite is sound in the first place:

| suite sound? | mechanism | mutants |
|---|---|---|
| yes (79 diagrams) | disconnected → killed without consulting a property | **1580** |
| yes | connected → killed by a property violation | **0** |
| yes | connected → survived | 0 |
| no (69 diagrams) | connected → killed by a property violation | 1235 |
| no | disconnected → killed by fiat | 132 |
| no | connected → survived | 13 |

The top block is the whole story: **on every diagram where a kill would be
interpretable, zero mutants are caught by a property** (0/1580, 95% CI [0.0000, 0.0023]).
The 1235 property-driven kills all occur on diagrams whose suite is already unsound —
i.e. the suite rejects everything, including the original, so "killing" a mutant there
carries no information.

`[EXP]` The reason is visible in the mutation operator distribution: all 2960 surviving
mutants come from **sequence-flow deletion** — no gateway substitution, condition
inversion, or retyping survives the engine's equivalence filter on this corpus. And
1712/2960 of those deletions disconnect the graph outright. A mutant population that is
100% one operator, over half of which are killed structurally, cannot exercise a temporal
property suite.

**Verdict: reject as headline in current form; salvageable as a secondary metric.**
`[REAS]` The fix is not conceptual — it is (i) restrict scoring to *connected* mutants,
(ii) require the kill to come from a named property, and (iii) diversify the operator
set. That yields a meaningful "discriminative kill ratio". But it is a secondary metric,
because it is only interpretable on diagrams that pass the soundness gate, and today
only 53% do.

### (c) Internal cross-oracle consistency against M01's reference LTLf interpreter

**What it measures.** Whether the synthesised properties agree with `ltlf_eval` on traces
derived from the semantic graph.

**Verdict: reject, on grounds this project has already established.** `[SRC]`
`mutation_refiner.py` imports `evaluate_ltlf` from `ltlf_eval` and uses it as the auditor's
decision procedure. So `ltlf_eval` is not an independent oracle — it is *the* oracle M01
already uses internally. Grading M01's output with it is the self-referential validation
pattern Module 02 measured and documented as structurally unable to detect logic bugs.
`[REAS]` The Phase 4 bug is a concrete demonstration: the property suite, the auditor, and
the interpreter all agree with each other, and the agreement is what hides the fact that
one property has been unparseable across all 148 diagrams.

`[REAS]` There is a narrow legitimate use — a *differential* variant, where the same
formula is evaluated by `ltlf_eval` and by Module 03's SPOT-backed checker and
disagreements are flagged. That is genuinely independent. But it requires the LTLf↔LTL
semantic bridge that the project brief lists as the headline unresolved gap, so it is
future work, not a methodology available now.

---

## 4. Recommendation

**Primary metric — Suite Soundness.** For each diagram: synthesise the property suite,
generate traces of the *unmutated* semantic graph, and check that every property holds.
The suite is sound iff it admits the diagram it was derived from.

**Pilot value** `[EXP]` (P2 malformed property excluded, else it is 0/148 by
construction):

| corpus | sound | rate | 95% CI (Clopper–Pearson) |
|---|---|---|---|
| `output` | 55/100 | 0.5500 | [0.4473, 0.6497] |
| `context` | 24/48 | 0.5000 | [0.3523, 0.6477] |
| pooled (reported for completeness only — see §1 on independence) | 79/148 | 0.5338 | [0.4501, 0.6161] |

Stratified by whether the BPMN contains a branch `[EXP]`:

| | suite sound | suite rejects its own diagram |
|---|---|---|
| has ≥1 branch point | **0** | 50 |
| no branch | 79 | 19 |

Fisher exact, `output` p = 2.5e-15; `context` p = 7.4e-09.

**Secondary metric — Discriminative Kill Ratio.** Among mutants that are (i) connected
(at least one complete trace exists) and (ii) evaluated against a sound suite, the
fraction killed by a *named property violation*. Reported only for diagrams passing the
soundness gate. Pilot value: **0/1580 = 0.0000**, 95% CI [0.0000, 0.0023].

**How a poster or thesis reader would have to read the headline number.** This is the
part the brief asked to be explicit about, so: the sentence a reader must be able to form
is *"On 100 FlowBench workflow diagrams, Module 01's synthesised LTLf suite admitted its
own source diagram in 55% of cases (95% CI 45–65%), and admitted 0% of diagrams
containing a branch."* That is a diagnostic result, not a success metric. It is honest,
it is falsifiable, and it localises the defect. What it is emphatically *not* is the
shape of number M02 publishes (a calibrated detection rate against labelled bugs), and
the writeup must not present it as though it were — M01's evaluation problem is
spec-fidelity, and at this stage the fidelity is failing on a specific, identified
construct.

**Why the diagnosis points at branching specifically** `[EXP]`: of the 69 self-rejecting
suites, 63 are rejected by a `P4_Task_Coverage` property of the form `F(done(X))`. On a
branching diagram, `_generate_traces` enumerates each path separately, and a task on the
untaken branch never completes on that trace — so a property asserting every task
eventually completes is false on every branch-local trace. `[REAS]` This is a genuine
tier-semantics error, not a corpus artifact: `F(done(X))` is only valid for tasks on
every path, and the synthesiser emits it unconditionally for all tasks. A secondary
cause accounts for the 19 non-branching self-rejections: 14 involve `subProcess` elements
and 3 diagrams have two distinct task node-ids that collapse to the same atomic
proposition `[EXP]` (`output/uid_67`, `output/uid_8`, `context/uid_92`), which makes a
`P1` ordering property self-contradictory.

### The recursive check, applied to the recommendation

The brief asks that the recursive check be applied to the *recommended* option, not just
the rejected ones. So: **is the soundness metric itself self-referential?**

Partly, and this must be stated in any writeup rather than discovered by a reviewer.
`[REAS]` Soundness is computed using M01's own trace generator and M01's own LTLf
evaluator. It therefore cannot detect a defect that is *shared* between the synthesiser
and the evaluator — if both encode the same wrong reading of a BPMN construct, the suite
will look sound and be wrong.

What rescues it from vacuity is that it is not a *fixed-point* check. The synthesiser and
the trace generator derive from the semantic graph by different routes — one instantiates
templates over node types, the other enumerates paths — so agreement between them is a
real constraint rather than a tautology. `[EXP]` The empirical evidence that it is not
vacuous is that it *fails*, on 69/148 diagrams, and the failures localise to an
identifiable construct class. A vacuous check would have returned 1.0.

`[REAS]` The honest scope statement: soundness detects *internal inconsistency* between
M01's property synthesis and M01's own execution semantics. It does not establish that
M01's LTLf suite is a faithful formalisation of the BPMN diagram's intended meaning —
that claim requires an external oracle, and the only credible one available to this
project is Module 03's independent model checker, which needs the LTLf↔LTL bridge first.
The metric should be named and captioned so that this limit is visible without reading
the methods section.

---

## 5. Proposed harness design (not built)

Location `module_01_spec/eval/`, mirroring M02's layout `[SRC]`:

| file | responsibility |
|---|---|
| `gold_bpmn.py` | Independent XML labeler. Must not import `module_01_spec/src/`, enforced by an import-scan test — same discipline as M02's `gold_wir.py` `[SRC]`. Node set defined by the BPMN 2.0 flow-node allowlist, not by the extractor's exclusion list. |
| `soundness.py` | Primary metric. Per-diagram: synthesise suite, drop unparseable properties (logging them as a separate defect count, never silently), evaluate against traces of the unmutated graph, record which property and which tier caused any rejection. |
| `mutate_eval.py` | Secondary metric. Wraps `BPMNMutationEngine`, records connectivity per mutant, and attributes each kill to a named property or to `disconnected`. Reports the two separately — never summed. |
| `report.py` | Emits `results/m01_eval_report.md` + per-diagram CSV, with counts, Clopper–Pearson intervals, and the branch/no-branch stratification. |

**Statistical conventions**, inherited from M02 `[SRC]` (`eval/calibrate.py`): α = 0.05,
Clopper–Pearson exact binomial intervals, fixed seed 42, per-diagram results persisted to
CSV so any aggregate can be recomputed without re-running. `[REAS]` Two additions specific
to M01: report `output` and `context` separately rather than pooling (the 47 shared uids
break independence), and stratify every rate by branch/no-branch, since Section 4 shows
that is the dominant explanatory variable and an unstratified rate would hide it.

**Pilot acceptance criteria — how to tell a working harness from a broken one.** `[REAS]`
A harness reproducing this design should, on `data/output/` at seed 42, reproduce:
structural node/edge F1 = 1.0000 (682 nodes, 576 edges, zero fp/fn); soundness 55/100;
zero property-driven kills among connected mutants on sound-suite diagrams; and 100% of
surviving mutants attributable to sequence-flow deletion. Divergence on the first
indicates the gold labeler drifted toward the extractor's vocabulary; divergence on the
second or third most likely means the malformed P2 property was not excluded (the
signature is soundness collapsing to 0/100 and kill ratio rising to exactly 1.0000).

**Relationship to the existing E2E harness.** `[SRC]` `demo/eval_e2e/harness.py` already
calls `run_module_01_pipeline` on `data/context/` and passes the resulting suite into
Module 02. `[REAS]` These should stay separate and be reported separately: the E2E harness
measures the joint pipeline and cannot attribute a failure to M01, whereas this design
measures M01 alone. The finding in Section 2 is the argument for the separation — an
E2E number cannot surface a uniformly dead Phase 4, because the E2E path does not read
the Phase 4 certificate.

---

## 6. What this memo does not solve

- **It does not fix any bug.** The malformed P2 property, the unconditional `F(done(X))`
  emission, and the disconnection-as-kill conflation are diagnosed, not repaired. No
  module source was touched.
- **It does not establish spec fidelity.** Soundness is an internal-consistency metric.
  Whether M01's LTLf suite faithfully formalises a BPMN diagram's intended meaning is not
  answered here and cannot be, without an external oracle.
- **It does not build the LTLf↔LTL bridge.** The genuinely independent oracle — Module
  03's model checker — remains unreachable for M01 properties, and this memo assumes that
  gap persists.
- **It does not generalise beyond simple workflows.** FlowBench diagrams have median 3
  tasks and contain no parallel, inclusive, or event-based gateways `[EXP]`. Every number
  here is scoped to that.
- **`[OPEN]`** Whether the 40 `subProcess` elements in `output/` should count as one node
  or be flattened is unresolved; I scored them as single nodes, matching the extractor.
  A different choice would change the structural denominator, though on this corpus it
  would not change F1 (which is saturated under both gold definitions tested).
- **`[OPEN]`** Whether `context/uid_90`, the one uid with no `output` counterpart, is a
  benchmark omission or intentional was not determined.

---

## Appendix — reproduction

Pilot scripts were written to a scratch workspace, not to the repo. Environment:
python 3.11 with `networkx`, `pytest`, `fastapi`, `scipy`. All measurements use seed 42
and `main @ 9165513`. `git status` after the session shows no modification to any module
or demo path.
