# Module 03 Thesis Chapter — Outline, Narrative Decisions, and Master Numbers Table

> Working scaffold for the Module 03 chapter, drafted as **Chapter 6** with section numbers 6.x
> (Module 01 → Chapter 4, Module 02 → Chapter 5; renumber at assembly). Draft prose lives in
> `module03_chapter_draft.md`.
>
> **Provenance of this scaffold.** Every figure is traced to a file in this repository or its vault.
> Nothing here was computed or estimated while writing. Where a figure was superseded, both versions
> appear and the superseded one is labeled with what replaced it and why. Claims I wanted to make
> and could not source are listed in the final section rather than smoothed into the prose.

---

## The four narrative decisions (made deliberately, before drafting)

**Decision 1 — The chapter's spine is vacuity: two independent channels by which a model checker
returns `COMPLIANT` while proving nothing.**
Not "we built a model checker and it works." The intellectual content is that a textbook-correct
SPOT model-checking pipeline — `parse_infix_psl` → negate → Büchi → product → emptiness →
`accepting_run()` counterexample — was *complete, tested, and structurally incapable of returning a
meaningful `COMPLIANT`* on any ordinary input, for two unrelated reasons, and that neither was
visible from its passing test suite because the suite documented one of them as intended semantics
(`test_finite_automaton_passes_all_properties`, pre-fix at `test_cpp_engine.py:407`,
`assert result.verdict == "COMPLIANT"  # vacuously true`; rewritten by the fix to
`test_finite_automaton_no_longer_vacuously_passes`, now asserting `VIOLATION`). Channel 1: no
acceptance condition plus permitted dead-end exit states ⟹ empty ω-language ⟹ vacuous `COMPLIANT`
for every property on every terminating workflow. Channel 2: the spec-side and code-side atomic
propositions are disjoint by construction, so a spec atom is permanently false in the code
automaton. The chapter presents them as *two* findings with two different fixes, and is explicit
that both had to close before any verdict from this module was worth reading.

**Decision 2 — A vacuous `COMPLIANT` is the exact failure mode Chapter 5's negative result predicts,
arriving from the other direction.**
Chapter 5 measured that a certificate derived from the code under test cannot detect logic bugs
(0/220). This chapter's channels are the same pathology in a different guise: a verification
apparatus returning "conformant" for a structural reason having nothing to do with the code's
behavior. Naming that connection is what makes this a thesis chapter rather than a bug report, and
it motivates the discipline the rest of the chapter applies — that a `COMPLIANT` verdict is
worthless without an argument that the check could have failed.

**Decision 3 — Report the detection-rate *decrease* as the chapter's methodological result, and cite
the right measurement for it.**
The call-order lifting change lowered definitive verdicts and raised abstentions. The naive reading
is regression. The chapter argues, with per-check tracing, that the pre-fix verdicts were mostly
untrustworthy — spurious, contradicted, or riding on omission blindness — and that the increase in
`INCONCLUSIVE` is the atom-matching gate working correctly on an automaton that no longer contains
functions that are never called. **Citation discipline here is load-bearing and easy to get wrong:**
the design-stage 53.2% → 40.4% pair was measured on a *Python emulation* of the compiled engine and
is explicitly superseded; the load-bearing evidence is the real compiled engine's corpus re-run
(`{VIOLATION: 18, COMPLIANT: 17, INCONCLUSIVE: 23}` → `{VIOLATION: 5, COMPLIANT: 10,
INCONCLUSIVE: 43}`) plus the 35-verdict cross-tabulation. The emulated pair appears **only** in the
correction-trail table, labeled superseded, never as system behavior.

**Decision 4 — Small-n numbers get intervals, provenance, and the honest denominator, every time.**
The end-to-end evaluation rests on 6 gold specs. Every rate is quoted with its Clopper–Pearson 95%
interval — never the point estimate alone — and with the ground-truth caveat attached: FLOW-BENCH
has no native correctness labels, so ground truth is manufactured by injecting mutations of known
effect into implementations independently confirmed conformant, and every rate is therefore a rate
*for injected defect classes*, not a measurement of real LLM implementations' conformance.
Abstention is reported as its own rate and excluded from the detection denominator, with the reason
stated; the false-alarm denominator excludes the unmutated gold variants on anti-circularity
grounds, also with the reason stated.

---

## Chapter structure (with per-section content notes)

### 6.1 Introduction: the convergence point
Module 03's role — where two independently-derived objects meet, and the only place in the system
where a spec-versus-code verdict exists at all. Restate the dual-track rule and why it must hold at
this seam specifically: the module deploys as its own container with no access to Module 01's
source, which is why it ports rather than imports the normalization it needs. The four phases in one
paragraph each, then the chapter's two questions: (a) does the model checker's `COMPLIANT` mean
anything, and (b) what does the pipeline detect end-to-end. Note up front which questions this
chapter does **not** answer — the behavioral-equivalence capability of Phases A–C is unmeasured
(§6.10) — so the reader is not left inferring an evaluation that does not exist.

### 6.2 Background and related work
This chapter carries the shared formal background. LTL and Büchi automata; the automata-theoretic
approach to model checking (Vardi–Wolper) as the exact shape of Phase D; LTLf and its
finite-to-infinite reduction (De Giacomo & Vardi, IJCAI'13) as the bridge Phase D needs; stuttering
bisimulation (Groote–Vaandrager) and *divergence-sensitive* stuttering equivalence, with the
distinction stated precisely because it is a design commitment and not a detail; bisimulation
minimization and isomorphism-based clustering; translation validation (CompCert, Pnueli) shared with
Chapter 5; approximate action matching (edit distance, sentence embeddings) as the pragmatic layer
where formal methods meet natural-language task names.

### 6.3 Design: four phases from WIR to verdict
- **6.3.1 Phase A — lifting the WIR to an LTS.** Node walk, action extraction from code text, and
  the three-tier label cascade: exact → edit-distance → Sentence-BERT (`all-MiniLM-L6-v2`, reached
  from C++ via embedded pybind11), with an `unlabeled_task` fallback so an unmatched action cannot
  silently pass as a match. Bounded loop unrolling. Note the tier-3 dependency honestly: in the
  environment where the corpus verification ran, the embedding model was absent, so tiers 1–2 ran
  for real and tier 3 degraded to `unlabeled_task` with a stderr message — this did not affect the
  channel-2 finding, which fires regardless of which tier resolved a label, but it bounds what the
  action-matching quality numbers can be read as.
- **6.3.2 Phase B — divergence-sensitive stuttering bisimulation.** Why plain stuttering equivalence
  is wrong here: it collapses a τ-cycle, so a hallucinated non-terminating loop becomes equivalent
  to a workflow that waits. Groote–Vaandrager partition refinement with Tarjan SCC τ-cycle
  detection (`spot::scc_info` on the C++ side); three equivalence tiers (functional / trace /
  process). This section states the design commitment; §6.9 states the cost — that the same
  divergence-sensitivity collides with the finite-trace bridge, and the collision is unresolved.
- **6.3.3 Phase C — behavioral clustering.** Isomorphism-based grouping
  (`spot::isomorphism_checker::are_isomorphic`) with the representative chosen as fewest states then
  fewest edges, on a shared `bdd_dict`; the cost argument (verifying N implementations costs
  #distinct behaviors, not N model-checking runs) presented as the *design* rationale it is, with
  the note that no artifact measures the realized speedup on the corpus.
- **6.3.4 Phase D — model checking.** The textbook chain and the concrete SPOT calls; the
  `ComplianceResult` shape including `counter_example_trace` and `unmatched_atoms`; the atom-matching
  gate that returns `INCONCLUSIVE` when a property's atoms are not present in the automaton, rather
  than a confident `VIOLATION`. Two-track situation stated plainly: the pure-Python
  reachability-BFS path is legacy, `process_wir_batch` is canonical, and the one capability the
  legacy path uniquely holds (loop-bound safety checking via `PropertyMonitor.from_loop_bound_check`)
  has no home in the canonical path — an open gap, recorded rather than dropped.
- **6.3.5 The ingestion layer.** `property_ingest.py` as the seam: tier gating with an explicit
  reason per excluded tier, intra-tier de-duplication, and "Option B" normalization — `start(T)` and
  `done(T)` collapsed to one flat quoted atom. Both halves of that choice are load-bearing and both
  get a sentence: the *collapse* is lossless only for sequential workflows (true for this corpus,
  zero parallel gateways; false in general), and the *quoting* is not cosmetic — SPOT's infix parser
  reads an unquoted atom beginning with a reserved operator letter as that operator applied to the
  suffix, so `GitHub_thing` parses as `G(itHub_thing)`.

### 6.4 The semantic gap: LTLf strings meet an infinite-trace checker
Module 01 exports LTLf (finite-trace); `check_compliance` parses SPOT infix LTL (infinite-trace).
These are not the same semantics and reformatting does not reconcile them. The reduction that does:
`spot::from_ltlf` with an `alive` proposition, vendored in SPOT 2.11.6 with two published errata
already corrected upstream. What the implementation actually does — `instrument_alive_extension()`
builds an alive-extended copy of the code automaton (every edge conjoined with `alive`, every
dead-end state given a `!alive` self-loop) and negates `from_ltlf(φ, "alive")` against it — and the
condition under which it does so: only when the automaton has no genuine cycle
(`spot::scc_info`, all-trivial). The branch matters and its justification is empirical, not
aesthetic: `from_ltlf`'s well-formedness obligation assumes the bridged trace terminates, so
bridging a genuinely looping automaton manufactures a violation unrelated to the property — caught
by a regression that flipped a literal-`"1"` tautology test to `VIOLATION` before the guard was
added. Report the corpus fact that makes this branch nearly always taken: 0 of 43 eligible
top-level WIR graphs contain a genuine cycle.

### 6.5 The central result, channel 1: a complete model checker that could not fail
- **6.5.1 The mechanism, from source and theory rather than from a run.** Two source facts — no
  acceptance condition is ever set anywhere in the lifter (`set_buchi` / `set_acceptance` /
  `set_generalized_buchi` absent), and exit states are explicitly permitted to have no outgoing edge
  — and one standard result: the automaton's ω-language is empty, so the product with any violation
  automaton is empty, so every property returns `COMPLIANT`. Presented in that order deliberately:
  the finding does not depend on trusting an experiment.
- **6.5.2 Why the test suite did not catch it.** The suite documented the behavior as intended
  (`# vacuously true`) and obtained real `FAIL` verdicts only from a deliberately looping fixture.
  This is the chapter's sharpest methodological point about verification tooling: a test asserting
  the observed behavior of a vacuous check is indistinguishable from a test asserting a correct
  check, unless someone asks whether the check *could* have failed.
- **6.5.3 Why it was dormant.** The only caller passed the hardcoded placeholder `G("approved")`.
  The defect was latent precisely until the module became useful — the moment a real property suite
  was wired in, it would have become a silent false-`PASS` on every non-looping implementation. This
  is the chapter's argument for measuring integration seams before trusting either side of them.
- **6.5.4 Confirmation on a real build, and the fix.** The first working compiled build (Homebrew
  SPOT 2.15.1 + pybind11) returned `COMPLIANT` for `G(!B)` on a 2-action non-looping automaton where
  `B` provably executes and both atoms matched (`unmatched_atoms: []`) — the prediction, observed.
  Fixed by the alive-extension of §6.4.
- **6.5.5 The third defect, found because the second fix exposed it.** Edge labels asserted only the
  positive literal for whatever fired on that edge, leaving every other registered atom
  unconstrained — including the entry transition, where nothing happens. Harmless while automata
  were vacuous; once terminating automata became checkable, the emptiness search could pick a
  convenient value for an unrelated atom on an edge that asserts nothing about it (`B=true` on the
  entry edge) and manufacture a violation of `!B W A` against code that genuinely calls `A` then
  `B`. Fixed by closing every edge under mutual exclusion — forcing every registered atom not
  required true by the edge's own condition to false — before adding the alive extension. Worth its
  own subsection because it is the same failure class as the atom gate targets (a confident
  violation the code never exhibits) reached by a different route, and because it illustrates that
  fixing a vacuity defect *creates* exposure that was previously masked.
- **6.5.6 Validation of the composite fix.** Cross-validated against Module 01's own `evaluate_ltlf`
  finite-trace oracle across all 29 eligible specs, 58 real property checks: **100% agreement on
  every check that produced a real verdict (35/35)**, with the remaining 23 legitimate
  `INCONCLUSIVE`s (the property references a task genuinely never called in that variant — the atom
  gate refusing, not failing). State the significance and the limit in the same breath: two
  independent implementations with different trace semantics agreeing on 35/35 is meaningful
  cross-validation of the bridge; it is not a detection measurement, because agreement with an
  oracle that shares the property suite says nothing about whether the property suite catches bugs.

### 6.6 The central result, channel 2: disjoint atom vocabularies
Spec-side atoms are lifecycle-prefixed (`start_Approve`, `done_Approve`); code-side APs are bare
matched task names (`Approve`), because `resolve_task_label` → `semantic_match` registers the matched
BPMN name directly as the AP and no lifecycle-prefix construction exists anywhere in the lifter.
Measured consequence: 0 of 116 spec-side P1 atoms can match; 0 of 29 spec/variant pairs overlap at
all. Crucially this is **not** a name-quality problem — spec task name to Python function name is
86.0% exact on mean across 43 pairs with 26/43 at 100% — which is what identifies the defect as a
lifecycle-layer omission rather than a matcher weakness. Report the reproduction status precisely:
the mechanism is source-verified from both sides; the 0/116 count was measured against a Python
emulation of AP construction, and the real-build confirmation is 58/58 checks returning
`INCONCLUSIVE` when unstripped atoms reach the checker. Then the two design options, both costed:
Option A (lifecycle APs on the code side — semantically richer, requires touching the C++ Phase A
walk and ~9 AP-name assertions) versus Option B (collapse the spec side to flat atoms — cheaper,
lossless only for sequential workflows). Option B shipped; say so, say why, and say what it costs.
Close with the P0 reclassification, which belongs to this section because it is the same
vocabulary reasoning taken to its conclusion: the P0 sentinel shape is unfalsifiable under *any*
faithful lifting rather than merely under one candidate lifting, so those 79 properties are a
lifting self-test rather than evidence about code — and reporting them as passed safety properties
would reproduce Chapter 5's self-referential failure at this seam.

### 6.7 Supporting architecture: what the automaton is an automaton *of*
- **6.7.1 The finding.** A WIR `task` node is a function *definition*, not a business action — the
  extractor's own docstring says the body is not inlined but stored as a separate sub-CFG — and the
  C++ lifter contains zero references to `functions`, so it never reads those sub-CFGs. The action
  sequence was therefore definition order, not execution order. Measured: definition order disagrees
  with call order in 47.5% of 184 normalized variants (independently reproduced at 45.5% by a
  different method — report both, and treat the disagreement as the honest precision of the
  estimate rather than picking one). Alongside it, the structural partition: across 184 variants, 0
  have top-level gateways, 184 have top-level tasks, 0 have task-typed nodes inside sub-CFGs, and
  gateways appear only inside sub-CFGs — so gateway nodes and task nodes never share a graph, which
  no atom renaming can fix.
- **6.7.2 Why this had to be fixed before the vacuity fixes could be trusted.** Fixing vacuity and
  vocabulary while the lifter model-checks definition order produces a bridge that reliably
  model-checks the wrong automaton. The ordering of the work is itself a result.
- **6.7.3 The decision, made on measured evidence.** Cross-tabulate the compiled engine's first real
  run (35 definitive verdicts) against ground truth reconstructed independently from the
  orchestrator's actual call sequence. Of 18 `VIOLATION`s: 12 name a task never called at runtime
  (spurious by construction — the atom "matched" only because definition-order lifting includes
  every function defined in the file), 5 of the remaining 6 confirm a genuine precedence violation,
  and 1 (`77__llama-3.1-8b.py`) is contradicted by real call order. Of 17 `COMPLIANT`s: 12 occur on
  variants independently classified as omission-divergent, where a precedence property is vacuously
  satisfied because a task never starts. **Net: roughly 10 of 35 definitive verdicts (29%)
  trustworthy as-is; the remaining ~25 (71%) provably spurious, contradicted, or riding on omission
  blindness.** This is the paragraph that converts "should we do the fix" into "any thesis number
  from the pre-fix lifter is noise reported as signal."
- **6.7.4 The witness argument.** The whole value proposition of a `FAIL` is a counterexample a
  developer can act on. A witness saying "you call B before A" about two functions that are never
  called is a false explanation of a real defect — the code *is* divergent, by omission, but the
  verdict is right for demonstrably the wrong reason. This is why the fix is justified even though
  it lowers the headline number.
- **6.7.5 What shipped, and its own bug.** `derive_call_order_wir()` as an additive entry point
  alongside the existing extractor — no shared visitor modified, so every existing consumer is
  untouched. Driver identification by AST-resolved sibling-call count (excluding self-recursion),
  falling back to the module's trailing top-level statements; the driver's own CFG built via the
  existing tested body builder; call-site nodes relabeled as tasks with code text unchanged, so no
  C++ change was needed. One bug found during validation and worth reporting because it is a real
  interaction between two modules' invariants: a task label attaches only to an edge *leaving* its
  node, and the body builder (unlike the module visitor) leaves its last node with no outgoing edge,
  so the driver's final call registered no AP at all until a trailing exit sentinel was added.
- **6.7.6 The measured shift, traced check by check.** `{VIOLATION: 18, COMPLIANT: 17,
  INCONCLUSIVE: 23}` → `{VIOLATION: 5, COMPLIANT: 10, INCONCLUSIVE: 43}` over the same 58 checks.
  Old `VIOLATION`s: 5 stayed (the confirmed-real ones), 12 became `INCONCLUSIVE` (the atoms
  genuinely are not in the driver's call sequence), 1 became `COMPLIANT` (the contradicted case).
  Old `COMPLIANT`s: 9 stayed, 8 became `INCONCLUSIVE` (omission on that specific property's own
  atoms — a tighter signal than the per-variant proxy used in the cross-tab). Old `INCONCLUSIVE`s:
  all 23 unchanged, no regressions. Two named acceptance cases behaved exactly as predicted before
  the change was written: uid 44 stays `VIOLATION`, uid 77 flips to `COMPLIANT`. The abstention
  increase is correct behavior: once a never-called function is genuinely absent from the automaton,
  the atom gate correctly refuses instead of answering confidently.

### 6.8 Evaluation: end-to-end conformance detection on FLOW-BENCH
- **6.8.1 Why ground truth had to be manufactured, and how.** FLOW-BENCH ships no correctness labels
  for its LLM implementations, so there is no direct source of "this implementation is/isn't
  conformant." Ground truth is built by the same method as Chapter 5's evaluation: inject mutations
  of known, verifiable effect into a real implementation already confirmed conformant end-to-end
  ("gold"), then check whether the pipeline's verdict flips as the mutation class predicts. Every
  rate is therefore a rate for *injected* defect classes. State this before the first number, not
  after.
- **6.8.2 The corpus and the funnel.** 6 gold specs (uids 45, 72, 76, 77, 84, 85) — those with both
  ≥1 conformance-checkable property and ≥1 real implementation independently confirmable as
  end-to-end conformant. Trace the funnel to that 6 and note that it is a cut of 48, itself not the
  public benchmark's 101. 26 order-mutation trials (drop-step and swap-adjacent), 2 verified
  order-preserving perturbation trials, 4 constant-perturbation candidates discarded for want of an
  eligible literal.
- **6.8.3 The finding that reshapes the metric: task-drop defects are frequently unobservable, not
  merely undetected.** Dropping a task's own call often removes that task's atom from what the
  matcher can observe; the pipeline then reports `INCONCLUSIVE` rather than a wrong `COMPLIANT` —
  it declines to claim an ordering result about a task it can no longer see. Reported as its own
  rate and excluded from the detection denominator rather than averaged into one misleading number.
  **Abstention rate 0.462 (95% CI [0.27, 0.67], n=26).** Note that it does not happen for every
  drop: when the dropped task is not the one an applicable property references, the property stays
  resolvable, so drop-step splits across all three outcomes.
- **6.8.4 Detection.** **0.357 (95% CI [0.13, 0.65], n=14)** — of trials where the pipeline
  committed to a verdict, the fraction correctly flagged `VIOLATION` on the same property gold
  satisfied with fully matched atoms. By kind (n / detected / missed-as-compliant / abstained):
  drop-step 16 / 0 / 4 / 12; swap-adjacent 10 / 5 / 5 / 0. Read the split rather than the aggregate:
  the pipeline detects reordering when it commits, and detects task omission never — 0 of 16 —
  which is the same structural blindness Chapter 4 §4.6 measures from the specification side, now
  observed end-to-end. The interval is wide and the chapter says so in the same sentence as the
  point estimate.
- **6.8.5 False alarms.** **0.000 (95% CI [0.00, 0.84], n=2)** on verified order-preserving literal
  perturbations. Give the interval prominence over the point estimate — n=2 supports almost nothing
  — and state why the denominator excludes the unmutated gold variants: they were selected
  *because* they verified conformant, so counting them would be circular.
- **6.8.6 Counterexample quality.** **0.800 (95% CI [0.28, 0.99], n=5)** — of correctly detected
  mutations, the fraction whose rendered counterexample named every BPMN task the violated
  property's own formula references. State the rubric's narrowness as a feature: a mechanical yes/no
  on formula-referenced atoms, not a subjective usefulness judgement. Connect to §6.7.4: this metric
  exists because the witness argument made witness quality a first-class concern, and to
  `counterexample.py`, whose job is turning a raw BDD trace into a readable task sequence filtered
  to the violated property's own atoms.
- **6.8.7 What these numbers do and do not license.** They license: the pipeline runs end-to-end on
  real specs and real LLM implementations; it detects injected reordering defects when its atoms
  resolve; it abstains rather than guessing when they do not; its witnesses mostly name the right
  tasks. They do not license: any statement about real implementations' conformance rate, any
  detection claim for omission defects, or any comparison with Chapter 5's detection figures, which
  measure a different instrument on a different corpus with a different ground truth.

### 6.9 The unresolved semantic tension: vacuity versus divergence
The `alive` reduction's `U(alive, G(!alive))` conjunct is unsatisfiable on a trace that stays alive
forever, so a hallucinated non-terminating loop would report `VIOLATION` on *every* property — not
because of what the code does but because it never terminates. That collides directly with Phase B's
deliberate divergence-sensitivity, which exists precisely to distinguish "diverged" from "reached a
bad state." A distinct `NON_TERMINATING` verdict is the recommended resolution and is a reasoned
design judgement, **not a project decision and not implemented**; the current guard sidesteps the
collision by skipping the bridge on cyclic automata rather than resolving it. Present this as a live
open problem at the heart of the design, which is more honest and more interesting than a
limitations bullet.

### 6.10 Limitations
Each costed with its measured value in the same sentence. (1) **The behavioral-equivalence
capability — Phases A, B, C — is unmeasured**: no artifact reports clustering agreement with
behavioral ground truth or bisimulation correctness on the corpus. The capability is implemented and
tested at unit level (142 test functions across 6 files) and *not* evaluated; the chapter names this
as the largest single evaluation gap and does not estimate it. (2) **Witness validity has not been
re-measured at corpus scale on the corrected engine**: the 29%-trustworthy cross-tabulation is a
pre-fix measurement, the post-fix evidence is the traced verdict shift plus two named acceptance
cases, and a fresh corpus-scale witness audit is future work. (3) **Small n throughout §6.8**: 6 gold
specs, n=14 detection, n=2 false alarm, n=5 counterexample quality; every interval is wide and every
one is reported. (4) **Injected defect classes only**, per §6.8.1. (5) **Omission blindness**: 0/16
drop-step detections; the coverage-tier property class that would address it is designed and
unbuilt. (6) **Branching conformance is structurally unblocked and empirically untestable**: sub-CFG
inlining dissolves the gateway/task partition, but no gateway-bearing spec produces a property suite
at all (Chapter 4 §4.4.1), so the branching capability became real and untested simultaneously.
(7) **Depth-1 inlining**: sufficient for this corpus, where the driver calls business functions
directly and those bodies are trivial; not sufficient for arbitrary real-world code. (8) **Driver
identification is a heuristic** validated on this corpus only, flagged as not established beyond it.
(9) **Tier-3 semantic matching was unavailable** in the verification environment, so reported
matching behavior reflects tiers 1–2 with an `unlabeled_task` fallback. (10) **Loop-bound safety
checking has no home in the canonical path** — it survives only in the legacy pure-Python pipeline,
because the ingestion layer excludes the tier that carries it. (11) **Two pre-existing test failures
persist** (`compute_deterministic_hash` absent from the Python lifter), unrelated to this work and
unchanged across it. (12) **The `alive` bridge applies only to acyclic automata** (§6.9).

### 6.11 Summary of contributions
(1) **A two-channel vacuity result for automata-theoretic conformance checking**: two independent
mechanisms by which a textbook-correct pipeline returns `COMPLIANT` while proving nothing, each
established from source and theory before being confirmed on a real build, plus the observation that
a passing test suite can *document* vacuity as intended semantics — with the resulting discipline
that no `COMPLIANT` is trusted without an argument that the check could have failed. (2) **An
executable LTLf-to-LTL bridge at a real module boundary**, with the termination guard its
well-formedness obligation requires, cross-validated 35/35 against an independent finite-trace
oracle. (3) **A measured demonstration that verification-target fidelity dominates verification
machinery**: an automaton built from function definitions rather than executed calls yielded ~71%
untrustworthy verdicts, and correcting it *lowered* the headline detection number while raising
witness validity — reported as a paired comparison with per-check tracing. (4) **The
witness-validity criterion**: that a conformance tool's `FAIL` must come with a counterexample a
developer can act on, made operational as a metric (0.800, 95% CI [0.28, 0.99], n=5) and used as
the deciding argument in a real design tradeoff. (5) **An end-to-end evaluation harness** over real
BPMN specs and real LLM implementations, with manufactured-ground-truth provenance stated,
abstention reported separately from detection, and exact-binomial intervals on every rate.

---

## Master numbers table (every figure with its source; use ONLY these)

Sources are repo-relative. `M03K` = `vibecheck-vault/Module 03 - Equivalence Engine/Module 03
Knowledge.md`; `P14` = `.../Bridge Investigation/P1.4 Bridge Findings.md`; `APVL` = `.../Bridge
Investigation/AP Vocabulary and Lifting Scope Findings.md`; `VER` = `.../Bridge Investigation/E2E
Integration Verification Findings.md`; `CP1` = `.../Bridge Investigation/CP1 Lifting-Scope
Decision.md`; `00` = `.../Bridge Investigation/E2E Session/00 - Session Findings and Plan
Impact.md`; `RPT` = `demo/eval_e2e/results/e2e_eval_report.md`; `JSON` =
`demo/eval_e2e/results/e2e_eval_results.json`; `HARN` = `demo/eval_e2e/harness.py` module docstring.

**Architecture and scale**

| Figure | Value | Source |
|---|---|---|
| C++ engine size | `lifter.cpp` 1,423 LOC, `lifter.hpp` 326 LOC | `M03K` |
| Pure-Python track | core ~1,470 LOC, 37 tests | `M03K` |
| Test functions | **142 across 6 files** (`test_pipeline.py` 37, `test_cpp_engine.py` 34, `test_phase_b.py` 28, `test_phase_c.py` 21, `test_property_ingest.py` 17, `test_counterexample.py` 5) | `M03K` (2026-07-30 count) |
| Test run status | 118 total / 115 passing / 2 pre-existing unrelated failures / 1 skip | `M03K` |
| Ingestion layer | `property_ingest.py` 205 LOC | `M03K` |
| SPOT version (vendored, pinned) | 2.11.6 in `module_03_equiv`'s Dockerfile (the only one that builds SPOT; `module_01_spec`'s no longer does, per item #11) | `P14` |
| SPOT version (verification build) | Homebrew 2.15.1 + pybind11 | `M03K`, `VER` |

**Channel 1 — the vacuity defect**

| Figure | Value | Source |
|---|---|---|
| Acceptance condition set anywhere in lifter | **none** (`set_buchi`/`set_acceptance`/`set_generalized_buchi` absent) | `P14` (VERIFIED-SOURCE) |
| Dead-end exit states permitted | yes, `lifter.cpp` ~499–512 | `P14` |
| Test documenting vacuity as intended | pre-fix `test_cpp_engine.py:407`, `assert result.verdict == "COMPLIANT"  # vacuously true` (rewritten by the fix to `test_finite_automaton_no_longer_vacuously_passes`, now asserting `VIOLATION`) | `P14` (quoted verbatim) |
| Placeholder property masking it | `pipeline.py:57`, `'G("approved")'` | `P14` |
| Live confirmation on real build | `COMPLIANT` for `G(!B)` on a 2-action non-looping automaton where `B` executes, `unmatched_atoms: []` | `M03K`, `VER` |
| Eligible corpus graphs with a genuine cycle | **0 / 43** | `M03K` |
| Post-fix cross-validation vs `evaluate_ltlf` | **35/35 agreement on real verdicts**; 23 legitimate `INCONCLUSIVE` (58 checks, 29 specs) | `M03K` |

**Channel 2 — the vocabulary defect**

| Figure | Value | Source |
|---|---|---|
| Spec P1 atoms matchable code-side | **0 of 116**; 0/29 pairs overlap | `00` §F2 (emulated AP construction; prefix mismatch VERIFIED-SOURCE) |
| Real-build confirmation | 58/58 `INCONCLUSIVE` with unstripped atoms | `VER` reproduction table row F2 |
| Task-name identifier match quality | 86.0% mean exact over 43 pairs; 26/43 at 100% | `00` §F2 |
| `FormulaNormalizer` callers | **zero** anywhere in repo | `P14`; docstring rewritten to say so (`M03K`) |
| P0 properties reclassified as lifting self-test | 79 | `00` §F3 (census); reclassification per `APVL` |
| Parallel gateways in corpus (Option B losslessness precondition) | 0 | `00` §F1 |
| SPOT quoting hazard | unquoted `GitHub_thing` parses as `G(itHub_thing)` | `M03K`; `VER` |

**Lifting scope**

| Figure | Value | Source |
|---|---|---|
| Definition order ≠ call order | **47.5% of 184 variants** (independently reproduced at 45.5%, different method) | `M03K`; `APVL` |
| `functions` references in `lifter.cpp` | **zero** | `D2 - Lifting Scope Fix Design.md` §1 (VERIFIED-SOURCE); `M03K` |
| Structural partition | 0/184 top-level gateways; 184/184 top-level tasks; 0/184 task nodes in sub-CFGs | `D2` §4 (VERIFIED-EXPERIMENT); independently reproduced 0/184 (`M03K`) |
| Sub-CFGs with a no-outgoing-edge exit | **every one of 184 variants has ≥1** | `D2` §1 |
| Pre-fix corpus run | `{VIOLATION: 18, COMPLIANT: 17, INCONCLUSIVE: 23}` (58 checks, 29 variants, 22/29 specs with ≥1 checkable property) | `M03K`; `CP1` |
| Verdict trustworthiness cross-tab | 12/18 `VIOLATION` name a never-called task; 5/6 remaining confirmed real; 1 contradicted (`77__llama-3.1-8b.py`); 12/17 `COMPLIANT` on omission-divergent variants | `CP1` (script `cp1_crosstab.py`, raw `cp1_crosstab_raw.json`) |
| Net trustworthy verdicts | **~10 of 35 (29%)**; ~25 (71%) spurious, contradicted, or omission-blind | `CP1` |
| Post-fix corpus re-run | `{VIOLATION: 5, COMPLIANT: 10, INCONCLUSIVE: 43}` | `CP1` |
| Traced shift | old VIOLATION 18 → 5 stay / 12 → INCONCLUSIVE / 1 → COMPLIANT; old COMPLIANT 17 → 9 stay / 8 → INCONCLUSIVE; old INCONCLUSIVE 23 → all unchanged | `CP1` |
| Acceptance pair | uid 44 stays `VIOLATION`; uid 77 flips to `COMPLIANT` | `CP1` |
| Call-order view tests | 7 (`module_02_extract/tests/test_call_order_view.py`) | `CP1` |

**End-to-end evaluation** — every rate quoted with its CI, never alone

| Figure | Value | Source |
|---|---|---|
| Gold specs | **6** (uids 45, 72, 76, 77, 84, 85) | `RPT`, `JSON` |
| Order-mutation trials | 26 (drop-step + swap-adjacent) | `RPT` |
| Perturbation trials | 2 (order-preserving, verified) | `RPT` |
| Discarded candidates | 4 uids (72, 76, 84, 85), no eligible literal for constant perturbation | `RPT`, `JSON` |
| Abstention rate | **0.462, 95% CI [0.27, 0.67], n=26** | `RPT` |
| Detection rate | **0.357, 95% CI [0.13, 0.65], n=14** (verdict-committing trials only) | `RPT` |
| By kind (n / detected / missed / abstained) | drop-step 16 / 0 / 4 / 12 · swap-adjacent 10 / 5 / 5 / 0 | `RPT`, per-trial records in `JSON` |
| False-alarm rate | **0.000, 95% CI [0.00, 0.84], n=2** | `RPT` |
| Counterexample quality | **0.800, 95% CI [0.28, 0.99], n=5** | `RPT` |
| Ground-truth provenance caveat | benchmark has no native correctness labels; ground truth is injected mutations into confirmed-conformant gold; all rates are for injected defect classes | `HARN`; `.claude/memory/flowbench_groundtruth_finding.md` |
| Interval method | Clopper–Pearson exact binomial | `HARN` |

**Correction trail (Table T6.3 — cite these as superseded, never as current)**

| What was stated | How it was caught | Correction / what supersedes it |
|---|---|---|
| Detection 53.2% (definition order) vs 40.4% (call order) | The figures were emulated in Python because the compiled engine could not be imported in that environment; the emulation could not see the vacuity defect | **Superseded** by the real compiled engine's pre/post corpus runs and the 35-verdict cross-tab (`CP1`). Direction of the finding held; the magnitudes are not system behavior and must not be quoted as such |
| Atom-gate fix (PR #67) closes the vacuity channel | A real compiled build still returned `COMPLIANT` for `G(!B)` with `unmatched_atoms: []` | Two distinct channels; the atom gate closes a different one. Vacuity closed separately by the alive extension |
| "Phase D complete, real model checking" | The vacuity mechanism was derived from source | Accurate for the mechanism, silently wrong on non-looping automata at the time; caveat recorded in `M03K` |
| Gateway hard-fail attributed to Phase 3 | Traced the exception path | Raised in the synthesizer's certification step, reported as `"phase": 2`; counts and set equality unaffected (`VER`) |
| Definition-order corpus run as a conformance-detection measurement | `CP1` cross-tab | It is a walking-skeleton proof, not a detection measurement; `M03K` labels it as such |

**Figures/tables to produce**

- **F6.1** Four-phase pipeline diagram (WIR → LTS → quotient → clusters → verdict), annotated with
  the SPOT primitive used at each step and which track implements it.
  Rendered as `figures/fig_m03_pipeline.pdf`.
- **F6.2** The two vacuity channels side by side: for each, the mechanism, why the test suite was
  silent, the fix, and the evidence that the fix works. This is the chapter's centerpiece.
  Rendered as `figures/fig_m03_two_vacuity_channels.pdf`.
- **F6.3** Verdict-shift Sankey: pre-fix `{18, 17, 23}` → post-fix `{5, 10, 43}` with the traced
  per-bucket flows from `CP1`. Rendered as `figures/fig_m03_verdict_shift.pdf`.
- **F6.4** The end-to-end rates as a forest plot — abstention, detection, false alarm,
  counterexample quality — each with its Clopper–Pearson interval, so interval width is the visual
  message rather than a footnote. Rendered as `figures/fig_m03_forest_ci.pdf`.
- **F6.5** Detection by mutation kind, stacked (detected / missed / abstained) for drop-step and
  swap-adjacent, making the 0/16 omission result immediately visible.
  Rendered as `figures/fig_m03_detection_by_kind.pdf`.
- **F6.6** Worked alive-extension example: raw dead-ending automaton beside its alive-extended copy,
  with the manufactured-violation edge annotated. Rendered as
  `figures/fig_m03_alive_extension_example.pdf`, using the exact entry->A()->B()->exit / G(!B)
  example from `E2E Integration Verification Findings.md`'s own VERIFIED-EXPERIMENT block (chosen
  over reconstructing `BRANCHING_WIR` from `lifter.cpp` directly, since the simpler example is the
  one already independently verified in the docs).
- **T6.1** Master numbers table (above). **T6.2** Tier gating decisions with the exclusion reason per
  tier. **T6.3** Correction trail (above). **T6.4** Verdict cross-tabulation from `CP1`.

---

## Claims flagged as unsupported (no citable artifact — do not write these into the chapter)

1. **Phase B / Phase C behavioral-equivalence evaluation.** No artifact measures clustering
   agreement with behavioral ground truth, bisimulation-reduction correctness on the corpus, or the
   realized verification-cost saving from clustering. A search of both results directories found
   nothing. §6.10(1) names this as the largest evaluation gap; the chapter must not imply a
   measurement, and must not reuse Phase-D numbers as if they spoke to Phases A–C.
2. **Corpus-scale witness validity on the corrected engine.** The 29%-trustworthy figure is
   pre-fix. Post-fix evidence is the traced verdict shift and two acceptance cases — not a fresh
   audit. §6.10(2) states this as future work; do not present the post-fix run as a witness-validity
   measurement.
3. **Clustering speedup.** The cost argument (#distinct behaviors rather than N runs) is a design
   rationale with no measured artifact. Present as designed, never as measured.
4. **Action-matching accuracy of the three-tier cascade.** No artifact isolates per-tier match
   accuracy, and tier 3 was unavailable in the verification environment. The 86.0% identifier-match
   figure is a spec-name-to-function-name property of the corpus, not a measurement of the cascade.
5. **Wall-clock performance of any phase.** No timing artifact.
6. **The 12,600/12,600 differential-agreement figure for the `alive` reduction.** It exists in the
   original bridge memo, but its own verification note lists it as credible-but-not-independently
   reconfirmed, resting on a local build never reproduced. If cited at all, cite it with that status
   attached; the load-bearing bridge validation is the 35/35 agreement instead.
7. **Whether the driver heuristic generalizes beyond FLOW-BENCH.** Flagged not-established at
   design time and never measured off-corpus. §6.10(8) states it as untested.
