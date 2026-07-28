> [!info] Imported from repo docs
> Source: `docs/thesis/module02_chapter_draft.md` @ main `7089711` (2026-07-28). `docs/` was removed from the repo (develop @ `05fae60`, 2026-07-28) after this import — **this vault copy is now the surviving snapshot** (git history retains the originals).

# Chapter 5 — Module 02: Verified Intermediate-Representation Extraction

> Draft complete: 5.1–5.8 DRAFTED · figures in `figures/` · citation keys [Aa] to be resolved
> against the shared bibliography at assembly time.
> All numbers come from the master table in `module02_chapter_outline.md`; do not introduce figures
> from memory or superseded reports.

## 5.1 Introduction: the code track's burden of proof

The VibeCheck architecture rests on a deliberately asymmetric division of trust. The specification
track (Module 01, Chapter 4) begins from an artifact a human authored and reviewed — a BPMN 2.0
process model — and its task is to translate that trusted artifact into formal temporal properties
without loss. The code track begins from the opposite pole: a Python program emitted by a large
language model, which must be treated as untrusted in every respect. Before the equivalence engine
(Module 03, Chapter 6) can compare the two tracks, the code track must convert its untrusted input
into a formal object — the Workflow Intermediate Representation (WIR), a statement-level control-flow
graph — and it must do so in a way that transfers *evidence* along with the artifact. This chapter
describes Module 02, the component that carries that burden of proof.

The need for evidence, rather than mere extraction, follows from a simple observation about the
pipeline's failure modes. Module 03's verdict is a statement about the WIR it receives; if the WIR
does not faithfully represent the behavior of the code it was extracted from, then any downstream
verdict — however mathematically rigorous — is a statement about a program that does not exist. A
static extractor alone cannot rule this out: extraction bugs, unsupported language constructs, and
abstraction mismatches all produce structurally plausible graphs that quietly diverge from the code's
real behavior. Module 02 therefore treats *extraction fidelity* as a claim requiring verification in
its own right, and attaches to every WIR a quantified, multi-layer certificate of how strongly that
claim is supported.

The module answers two distinct questions, and much of this chapter's argument turns on keeping them
distinct. The first question is one of **fidelity**: does this WIR faithfully model this code? Module
02 answers it with three verification layers that fail in different ways — structural extraction
with a coverage gate (V3), bounded concolic execution over the extracted graph using an SMT solver
(V2), and dynamic differential testing in which the real code and a reference interpreter walking the
WIR are executed on the same inputs and their observable traces compared (V1). The second question is
one of **behavioral conformance**: does this code behave as a *reference* implementation's WIR says
it should? This differential question — asked by substituting a trusted reference's WIR for the
code's own as the oracle — is the module's bridge toward the specification track, and, as Section 5.4
shows, it is the only form of the question the module can answer for logic errors at all.

That last claim is this chapter's central finding, and it is a negative one. In the module's original
conception, the fidelity certificate was implicitly expected to double as a correctness signal: a
buggy program, the intuition went, would somehow fail its own verification. Measurement refuted the
intuition completely. When the certificate's oracle is derived from the code under test, a mutated
program and its mutated WIR diverge *identically* — the first correctly measured evaluation recorded
zero detections across two hundred and twenty seeded faults of every class. Rather than treating this
as a defect to be patched, the project treated it as a structural property to be characterized: the
result is reported in full (Section 5.4.1), and the module's detection capability was rebuilt on an
architecture that takes it seriously — a differential mode in which the oracle comes from a reference
implementation while the *observation layer* (where in the code to watch) may still be derived from
the code under test, a separation principle that preserves the anti-circularity of the comparison.
Successive, individually-measured refinements to what the dynamic layer can observe — task events,
branch decisions, guarded string inputs, and finally return values — carried differential detection
from that initial zero to 99.5% on seeded faults (95% CI [97.4, 100]) at a 5.9% false-alarm rate, and
to 68 of 68 genuine logic bugs harvested from real LLM generations, at an operating threshold frozen
before evaluation.

A second theme runs through the chapter alongside the negative result: the treatment of measurement
itself as an artifact requiring verification. Three of the module's headline measurements were
invalidated during the project — by an entry-point selection bug that silently evaluated trivial stub
functions, by a mutation operator that produced only semantically equivalent "bugs," and by a
line-numbering artifact that inflated apparent detection corpus-wide. Each was caught by
cross-checking instruments against one another, each correction is documented with direct evidence,
and every superseded report is preserved in the repository's archive rather than overwritten. Section
5.6.5 presents this correction trail not as an admission but as the chapter's answer to the question
every empirical claim must face: *how do you know your measurement is right?*

The chapter makes five contributions. First, the negative result itself: self-referential validation
— certifying code against a model derived from that same code — is structurally blind to semantic
error, a property demonstrated by construction and by measurement (§5.4.1). Second, a differential
verification architecture built on an explicit observation/oracle separation rule, with each
observability increment validated by a before/after measurement (§5.4.2–5.4.3). Third, a dual
comparison-mode design — strict for same-lineage comparison, task-only for independently written
implementations — selected by what the compared artifacts can assume shared rather than by outcome,
and defended with a control experiment quantifying exactly what each mode trades (§5.4.4). Fourth, an
evaluation package designed for a domain with no labeled benchmark: an adapter that turns FLOW-BENCH's
reference workflows into an executable corpus, a ten-operator mutation generator, a behavioral
admission oracle that labels LLM-generated variants without human annotation while yielding a
natural-bug corpus as a by-product, and a calibration protocol with pre-registered thresholds,
three-figure reporting, and enforced anti-circularity rules (§5.6). Fifth, the correction-trail
methodology: an auditable, in-repository record of every invalidated measurement and its fix (§5.6.5).

The remainder of the chapter proceeds as follows. Section 5.2 situates the module against translation
validation, concolic and differential testing, and mutation-based evaluation. Section 5.3 presents
the WIR and the three-layer certificate, including the design evolution that removed the structural
layer from the confidence composition after it was found to make the verdict vacuous. Section 5.4
develops the central negative result and the differential architecture that answers it. Section 5.5
records implementation decisions with externally visible consequences, including an empirically
mapped boundary of what a thread-based timeout can and cannot bound in CPython. Section 5.6 presents
the evaluation methodology and results, and Section 5.7 the limitations — each of which is measured
or empirically bounded rather than merely acknowledged. Section 5.8 concludes.

## 5.2 Background and related work

This section situates the module against five bodies of work, confining itself to what the chapter's
argument actually uses; the framework-level literature review is shared with Chapters 4 and 6.

**Translation validation.** The module's closest ancestor is translation validation as introduced for
verified compilation [Pnueli et al.; Leroy]: rather than proving a translator correct once, each
individual translation is checked for semantic equivalence with its source. Module 02 inverts the
trust assumptions of that tradition. Classical translation validation assumes a *trusted source* and
asks whether the translator preserved it; here the source (LLM-generated code) is the untrusted
artifact, the "translation" is the module's own extraction of a formal model from it, and the
validation question splits in two accordingly — is the extracted model faithful to the code
(fidelity, answerable self-referentially), and is the code faithful to a reference (conformance,
answerable only against an independent artifact). Section 5.4 shows that collapsing these two
questions into one, which a naive adaptation of translation validation invites, produces a vacuous
verifier; keeping them separate is the module's structural response to the untrusted-source setting,
and quantified confidence replaces the full proof that setting makes unattainable.

**Concolic and symbolic testing.** The symbolic layer descends from the directed/concolic testing
tradition [Godefroid et al.; Sen et al.]: concrete execution paired with symbolic path tracking,
branch negation, and constraint solving to steer inputs into unexplored paths, with k-bounded loop
treatment inherited from bounded model checking. The module's variation is one of *role* rather than
technique: concolic execution here does not hunt for crashes in the program but for infeasibility in
the extracted model — its output is evidence about the WIR, folded into a certificate, and its
characteristic failure mode (abstention on opaque or container-heavy code) is compensated by an
independent dynamic layer rather than treated as the end of the analysis.

**Differential testing and trace equivalence.** The dynamic layer is differential testing [McKeeman]
with a twist on what the two "implementations" are: not two versions of a program, but a program and
a *reference interpreter walking a formal model*, compared over an observable-event vocabulary. The
choice of vocabulary is where the design engages the trace-equivalence literature: the task-observable
abstraction — task events, decisions, exceptions, return values, with silent internal steps eliminated
before alignment — is a pragmatic cousin of stuttering equivalence [Lamport; Groote & Vaandrager],
chosen so that the comparison tolerates unobservable implementation detail while remaining sensitive
to every business-visible action. The chapter's mode-selection result (§5.4.4) is, in these terms, an
empirical demonstration that the right equivalence relation depends on the provenance of the compared
artifacts — a granularity question the differential-testing literature usually fixes globally.
Module 03 (Chapter 6) pursues the fully formal version of this comparison; the runtime
instrumentation that feeds ours is CPython's recent monitoring interface [PEP 669], whose native
branch events this module exploits.

**Mutation analysis.** Mutation testing [DeMillo, Lipton & Sayward] supplies the evaluation's fault
model — small semantic edits as proxies for real defects — but with the direction of assessment
reversed: mutants here grade a *detector*, not a test suite. The evaluation inherits mutation
analysis's classical nuisance, the equivalent-mutant problem, and resolves it behaviorally rather
than by inspection: every mutant is executed against its base on shared inputs, equivalence is a
measured (bounded) property, and equivalents form a separate reporting category (§5.6.3) instead of
contaminating the detection denominator. The same behavioral-labeling machinery, pointed at LLM
generations instead of mutants, yields the admission oracle and the natural-bug corpus — to our
knowledge an unusual reuse, and the reason the evaluation can report detection on *real* generation
faults alongside synthetic ones.

**Evaluating LLM-generated code.** Mainstream code-generation benchmarks [HumanEval; MBPP] test
stateless functions against assertion suites and say nothing about workflow semantics; FLOW-BENCH
[Duesterwald et al.] supplies enterprise-workflow tasks with reference implementations but no
correctness labels and no executable LLM outputs — a gap this evaluation fills by construction
(§5.6.1). Recent work at the intersection of LLM generation and verification — formal query languages
for intent [Astrogator], LLM-assisted property generation over bounded model checking [SpecVerify],
property-based validation of code translation [Eniser et al.], and symbolic-execution equivalence
checking [ARDiff] — shares this chapter's goal but not its position in the pipeline: none certifies
the *extraction* of the formal artifact it reasons over, which is precisely the step whose
trustworthiness this module exists to establish, and none reports the self-referential blindness
result that motivates requiring an independent reference at all.

## 5.3 Design: the WIR and the three-layer certificate

### 5.3.1 The Workflow Intermediate Representation

The WIR is a statement-level control-flow graph serialized as JSON: one node per source statement,
typed as *block* (assignments and calls), *gateway* (conditional tests), *loop* (iteration headers),
*task* (function definitions), or *return*, with directed edges carrying guard labels on branch arms
and exception-type labels on handler paths. Each function in the source receives its own sub-graph;
the top-level graph carries module structure. Alongside the graph itself, the WIR records the
products of two static analyses that downstream consumers need: an immediate-dominator tree with
dominance frontiers (which statements *must* precede others), and every branch guard flattened into
conjunctive normal form, so that the equivalence engine receives decision logic in a uniform algebra
rather than as opaque expression strings. The whole artifact is validated against a published JSON
schema at emission — the schema is the inter-module contract, and Module 03's lifter consumes exactly
this shape.

One design refinement deserves record because it was driven by measurement. The graph *construction*
requires scaffolding — blank merge nodes at branch joins and loop exits, load-bearing while the
builder rewires exception and finally-clause paths — and the original design let that scaffolding
ship in the emitted WIR. Structural-accuracy measurement against independent ground truth (Section
5.6.4) showed this scaffolding to be the *entire* gap between the extractor and a perfect score, and
human validation confirmed the nodes carried no semantic content. A post-construction contraction
pass now removes them: every blank, guardless block is spliced out with its edges re-joined and their
labels preserved, leaving a WIR whose every node corresponds to a real statement. The pass was
accepted only after three checks — structural accuracy rising to 1.0 with recall unchanged, zero new
fidelity-gate failures across the corpus, and detection figures byte-identical — establishing that
the removed class was representational noise, not behavioral signal.

### 5.3.2 V3 — structural extraction and the fidelity gate

The structural layer walks the abstract syntax tree with dedicated handlers for Python's control
constructs — conditionals, both loop forms, `try`/`except`/`else`/`finally` (including exception-
group variants), `with`, structural pattern matching, and early exits — building the WIR and
measuring, as it does so, how much of the source it captured: the fraction of statement nodes
represented in the graph, an edge-coverage heuristic, and the fraction of guards successfully
flattened to CNF. Its certificate is a *fidelity* instrument in the narrow sense established in
Section 5.1: if statement coverage falls below 0.95, the layer sets an abort flag and the entire
verification fails to "manual review" regardless of what the behavioral layers would report, because
every downstream check would otherwise run against a model missing part of the program. What V3
never does — and this required a design correction recorded in Section 5.3.5 — is contribute a
*correctness* vote.

### 5.3.3 V2 — bounded concolic execution

The symbolic layer asks whether the WIR's paths are logically real. It executes the program
concretely from seed inputs while tracing the corresponding symbolic path condition along the WIR,
then negates the most recent branch decision and asks an SMT solver (Z3) for inputs reaching the
unexplored side, iterating under a query budget. Loops are k-bounded: after a fixed number of
unrollings the loop's modified variables are replaced with fresh symbols (havoc) and exploration
exits, trading completeness for termination. Three engineering decisions matter to its behavior on
this domain. Solver state is incremental — blocking clauses for explored paths are asserted once on a
persistent solver, with per-query conditions in transient scopes, keeping the run linear rather than
quadratic in explored paths. Container-typed inputs, which dominate workflow code, are seeded with
small non-empty values (and dictionary keys discovered from the program's own subscripts), with
concrete lengths propagated into symbolic guards, so container-bearing branches are explored rather
than abandoned. String comparisons are encoded by tokenizing literals, with a reverse map so that a
solver's answer converts back into an actual string for the next concrete iteration. The layer's
confidence combines path feasibility, solver success, and branch-coverage credit; where it cannot
make progress — opaque containers, unsupported constructs — it abstains toward zero rather than
guessing, and the dynamic layer compensates. One capability announced in the module's original
design, symbolic-state *merging* at join points, is deliberately absent: it was implemented but never
wired into the exploration loop, and rather than ship dead code implying an unexercised defense, it
was deleted, with the class documentation stating exactly which explosion-control mechanisms are
live (k-bounding and the query budget).

### 5.3.4 V1 — dynamic differential testing

The dynamic layer is the module's behavioral instrument, and its design is best read as the
construction of an *observability surface* (Section 5.4.3 gives the measured history). The program
under test runs inside a tracer built on CPython's low-overhead monitoring interface (PEP 669), which
reports line execution and — critically — native branch events carrying the taken/not-taken decision;
a legacy `settrace` backend provides a fallback for older interpreters, with next-line inference
substituting for branch events, and a dedicated parity suite holds the two backends to identical
trace output. Opposite the real execution, a reference interpreter walks the WIR on the same inputs:
it executes statement code in a provided environment (so task-stub calls really run and state really
flows), emits task-entry/exit events for every call matching a known task pattern, evaluates guards
and loop iterations against its own state, and evaluates return statements to a final value —
emitting, on both sides, the same event vocabulary: task events, branch decisions, exceptions, and
the return value. Inputs are generated per parameter type, with one domain-informed refinement:
string parameters draw from a pool of the very literals the program's guards compare against
(round-robin first, so every literal is exercised within the run budget), because uniform random
strings satisfy no equality guard and would leave every string-guarded branch unexplored. Traces are
aligned by longest-common-subsequence over normalized event tuples, with stutter elimination
discarding unobservable noise, and confidence reflects the fraction of matching runs weighted by
input diversity.

### 5.3.5 Composing the certificate — and the formula the project removed

The certificate originally composed all three layers as independent evidence:
`combined = 1 − (1−v1)(1−v2)(1−v3)`. Measurement destroyed this design in a single observation: V3's
score saturates near 1.0 for *any* structurally extractable program — extractability is cheap — so
the three-term product certified essentially everything, regardless of what the behavioral layers
found. The verdict was vacuous, and the flaw is instructive rather than incidental: it came from
composing a *fidelity* measure as though it were a *correctness* vote, the exact category confusion
Section 5.1 warned against. The corrected composition treats the layers according to what they
measure. V3 gates: abort fails everything. V1 and V2 compose as parallel behavioral evidence in
self-mode, `combined = 1 − (1−v1)(1−v2)`, certified at 0.95. In differential mode the verdict is V1
alone (Section 5.4.2), with V2 retained as telemetry. Alongside the scores, every response carries a
typed per-layer status — OK, ERROR with reason, or SKIPPED with the upstream cause — so that a caller
can always distinguish "the code failed verification" from "the verifier failed to run," a
distinction the original single-catch design collapsed.

## 5.4 The central result: self-referential validation, and the architecture that answers it

### 5.4.1 A certificate whose oracle is the code under test cannot detect logic errors

Consider what Module 02's dynamic layer actually compares. The real program is executed and its
observable trace recorded; a reference interpreter walks the WIR on the same inputs and produces the
trace the WIR *predicts*; the two are aligned and scored. In self-mode — the `/verify` endpoint's
configuration — the WIR is extracted from the very program being verified. Now let that program
contain a logic error: a negated guard, a dropped step, an inverted comparison. The extractor,
operating faithfully, extracts a WIR containing *the same* negated guard, *the same* missing step.
The reference interpreter, walking that WIR, predicts precisely the erroneous behavior the program
exhibits. The two traces agree, run after run, and the certificate reports high confidence — because
the certificate is answering the question it was built to answer, *"does this WIR faithfully model
this code?"*, and for a faithfully-extracted model of a buggy program the honest answer is yes.

The property follows by construction, but the project also measured it, twice over. At unit scale,
guard-negation, boundary-shift, and constant-perturbation mutations applied to a single-function
workflow left the dynamic layer's confidence saturated at 1.0 in every case — the mutated program
matched its mutated model perfectly. At corpus scale, the corrected self-mode calibration (Section
5.6.5 describes why the first attempt had to be discarded) recorded **zero detections across 220
seeded faults spanning every operator class**: deletion, reordering, guard logic, container
corruption. No threshold exists at which this configuration separates buggy programs from correct
ones, because the score distributions coincide.

Two conclusions were drawn, and they shaped everything that follows. First, the negative result does
not indict the fidelity certificate — extraction fidelity is a real property, it genuinely requires
verification (Section 5.3), and a certified-faithful WIR is exactly what the downstream equivalence
engine needs. The error would be to *also* read the certificate as evidence of correctness, and the
architecture now forbids that reading structurally: correctness judgments belong to comparisons
against an artifact the code under test did not produce. Second, if a reference artifact is
available — in the full pipeline, Module 01's specification; in this module's evaluation, a reference
implementation's WIR — then the same dynamic machinery *can* detect logic errors, provided the oracle
side of the comparison is swapped. That configuration is differential mode.

### 5.4.2 Differential mode and the observation/oracle separation rule

In differential mode, the program under test executes as before, but the reference interpreter walks
a WIR extracted from a *trusted reference implementation* of the same requirement. A logic error in
the program now produces a trace the reference's WIR does not predict, and the divergence is
measurable. The verdict in this mode is the dynamic layer's confidence alone: the symbolic layer
explores the program's own code and therefore has no oracle — its confidence means "internally
consistent with itself," which is not evidence of conformance, and composing it into the verdict was
measured to mask genuine detections (a mutant with dynamic confidence 0.0 — perfect detection — could
still score 0.5 combined). The structural layer's abort gate is retained unchanged.

Making differential comparison sound required drawing a line that recurs throughout the
implementation, stated here as a rule:

> **The observation layer — *where* in the program to watch — may be derived from the code under
> test. The oracle — *what to expect* at those observation points — must never be.**

Watching positions are properties of the program's own syntax, observable without any knowledge of
correct behavior; deriving them from the code under test is not circular. Expected behavior is
precisely what verification must not assume. The rule has three concrete instantiations in the
module. Branch-observation line numbers are derived from the WIR of the program under test, not the
reference's — a single inserted or deleted line shifts every subsequent line number, and
reference-derived positions were measured to misfire on *every* mutant in the corpus (the mutant
generator's unparsing re-formats the file), manufacturing spurious divergence unrelated to behavior
(Section 5.6.5). Branch *arm* ranges, used to convert an observed jump into a taken/not-taken
decision, likewise come from the code under test. Test inputs, by contrast, may come from anywhere —
including the reference side: sampling the guard literals that both programs compare against is
ordinary specification-based input selection, since inputs are not the oracle; only the expected
trace is.

### 5.4.3 What the dynamic layer must observe: an incremental, measured construction

Differential mode's detection power was not obtained in one step. It was built as a sequence of
observability increments, each motivated by a diagnosed failure of the previous state and each
validated — or, twice, *invalidated* — by re-running the same calibration instrument. Table 5.1
summarizes the sequence; the distinction in its final column matters, because two of the movements
are corrections of the measurement rather than improvements of the detector, and conflating the two
would overstate the engineering and understate the methodology.

**Table 5.1 — Differential-mode genuine-bug detection across the construction sequence.**
*(Rendered as Figure 5.1, `figures/fig_detection_climb.pdf`: the same sequence as a staged
progression, marker-coded by the nature of each movement, with the constant false-alarm rate as the
reference line — the caption should state that stage 1 is an invalid measurement, plotted for the
correction-trail narrative, not as a baseline capability.)*

| Stage | Change | Detection | False alarm | Nature of movement |
|---|---|---|---|---|
| Initial differential harness | oracle swapped to reference WIR | 0.432 | 0.392 | invalid measurement (see below) |
| Reference execution + task observability | interpreter given an execution environment; stub calls emitted as task events on both trace sides | 0.864 | 0.059 | capability |
| Corpus corrections | no-op mutation operator fixed; observation lines re-derived per the separation rule; three-figure reporting adopted | 0.929 | 0.059 | measurement correction |
| Branch decisions | PEP 669 BRANCH events (settrace fallback, parity-tested) give the real trace taken/not-taken values | 0.957 | 0.059 | capability |
| Verdict composition + input coverage | symbolic layer removed from differential verdict; guard-literal pool with guaranteed coverage | **0.995** | **0.059** | capability |
| Return values | final return value emitted and compared on both trace sides | 0.995 (unchanged) | 0.059 | capability (see text) |

The initial 0.43 deserves its label. The first harness's reference interpreter executed WIR
statements in an empty environment: every call to a workflow's task functions failed silently, no
state was ever populated, and a *correct* program scored zero against its own reference — there was
no working baseline to separate mutants from. Detection at that stage was noise given meaning only by
a line-numbering artifact. The first genuine capability step was making the reference execution real
(an execution environment containing the task stubs) and making task calls first-class observable
events on both trace sides — dropped, reordered, and rerouted steps then became directly visible as
task-sequence divergence, which is the alignment's native currency. Branch decisions closed the class
of mutations that flip which arm executes without changing which tasks run (guard negation went from
8/14 to 14/14 detected). Removing the oracle-less symbolic layer from the verdict, together with
deterministic coverage of compared string literals, closed value-perturbation cases (0/9 to 8/9) and
brought seeded-fault detection to 0.995 (95% CI [0.974, 1.000], n = 210) at a false-alarm rate of
0.059 on untouched correct programs — with the operating threshold selected on a calibration split
and frozen before evaluation throughout.

The final increment — return values — moved the seeded-fault number not at all, and the chapter
reports that fact deliberately. Synthetic mutations perturb control flow, so their effects surface in
task sequences and branch decisions before the return value could ever be the deciding channel; a
full re-computation of the certificate-correctness correlation confirmed byte-identical results on
the mutation corpus. The increment's value appears on a different corpus entirely: among genuine LLM-
generated implementations (Section 5.6.1), every one of the six remaining undetected logic bugs was a
*return-value-only* divergence — identical task sequence, identical branching, different answer —
invisible to a trace that never observes what the function returns. With the return-value observable,
logic-class detection on that natural-bug corpus rose from 0.912 to **1.000** (68/68), and from 0.779
to 0.882 in the cross-implementation mode described next, while the false-alarm rate was unchanged.
The general lesson the sequence teaches is that differential verification is exactly as strong as its
observability surface, and that each addition to that surface should be priced by measurement — the
same instrument, re-run, with archives keeping every prior state comparable.

### 5.4.4 Two comparison modes, selected by lineage, defended by a control experiment

The trace alignment described so far treats branch decisions as signal. That is correct precisely
when the two sides of the comparison share source lineage — a mutant against its own base program —
because branch structure is then shared by construction and any decision divergence is caused by the
fault. It is wrong when the two sides are *independently written* implementations of the same
requirement: two correct programs may legitimately differ in guard nesting, defensive checks, and
control-flow shape, and an alignment that counts branch events punishes style as though it were
error. Measured on twenty independently-generated implementations verified against the reference's
WIR — each behaviorally equivalent to the reference by construction (Section 5.6.1's admission
oracle) — the strict alignment falsely flagged 25%, with the divergence breakdown dominated by
branch-structure events rather than task or exception events.

The module therefore provides two comparison modes. **Strict** mode (the default) compares task
events, branch decisions, exceptions, and return values. **Task-only** mode drops branch events
entirely — not merely their decision values, since a branch-*count* mismatch is itself style noise —
and compares task events, exceptions, and return values. The selection rule is categorical, decided
before any score is computed: *strict when the compared artifacts share source lineage; task-only
when they are independent implementations.* The rule is a property of what the comparison can assume
shared, not a tuning knob; choosing a mode by which produces the preferred number would reintroduce
through the back door the circularity the architecture exists to exclude.

Both directions of the trade were measured, because a rule defended only by its benefit is not
defended at all. Under task-only alignment, the implementation-freedom false-alarm rate fell from
0.25 to **0.10** — and the two residual flags are exception-driven divergences, which task-only mode
correctly retains, not style penalties. The cost was measured by a control experiment: re-running the
full seeded-fault calibration under task-only alignment collapses exactly the operator classes whose
detection rides on branch decisions — guard negation from 14/14 to 4/14, value perturbation from 8/9
to 2/9, overall detection from 0.995 to 0.895 — while the operators that alter task sequences
(dropped, reordered, corrupted-call mutations) remain at 1.000, unaffected. The control run also
served as a regression proof in the opposite direction: under strict mode the calibration reproduced
its frozen figures exactly, demonstrating the mode mechanism itself to be behaviorally inert when
disabled. The two measurements together are the answer to the natural objection — *why not always
use the forgiving mode?* — and they quantify, rather than assert, why the mode must be chosen by
lineage: each alignment is the correct instrument for a different question, and the price of using
either for the other's question is now a number, not an opinion.

## 5.5 Implementation notes

The module is a FastAPI service exposing a single verification endpoint; this section records only
the implementation decisions with externally visible consequences, each stated with its boundary.

**Sandboxing and its trust boundary.** Submitted code executes under a whitelist of side-effect-free
builtins, with no import machinery exposed — file, network, and process access are absent by
construction, and any program requiring an import is rejected rather than partially trusted. The
boundary is stated honestly: whitelist sandboxing in CPython does not stop a determined adversary
(attribute-chain escapes through the object graph remain possible), so the sandbox is a guard against
accident, not attack; the module verifies untrusted-as-in-unreliable code, and hostile-code isolation
would require the process-level separation named as future work below.

**Resource bounds, with a measured limit.** Runaway execution is bounded at two levels. Step-count
guards in every execution layer — the tracer, the reference interpreter, and the concolic engine's
concrete runs — terminate any program exceeding a fixed number of executed statements, which bounds
all Python-level loops. Above them sits a wall-clock timeout on the whole verification (thread-based,
as the deployment platform lacks POSIX signals), and its limit was mapped empirically rather than
assumed: a timeout thread wakes only when the worker yields the interpreter's global lock, so a
GIL-*releasing* hang (any Python-bytecode loop) is bounded within milliseconds of the deadline —
measured at 0.22 s against a 0.2 s budget — while a GIL-*monopolizing* single native operation (a
large-integer exponentiation was measured holding the lock for its full multi-second runtime) is not
preempted at all: the call simply completes late. The test suite deliberately asserts only the
bounded case, because asserting the unbounded one would document a guarantee the mechanism does not
provide; closing the gap requires process isolation, which would also subsume the sandboxing caveat
above.

**Interpreter scope.** The monitoring-first tracer requires CPython 3.12+; the `settrace` fallback
extends coverage to older CPython versions at higher overhead, with a parity suite pinning both
backends to identical trace semantics. Alternative Python implementations are out of scope, and the
claim is scoped accordingly.

**Verification of the verifier.** The module carries 246 automated tests, including the backend-
parity suite, regression tests that encode each correction from Section 5.6.5 (several written to
*fail* on the previously-buggy behavior), and end-to-end tests asserting that a seeded fault actually
fails verification — the test the original design, with its vacuous verdict, could never have passed.

## 5.6 Evaluation

The evaluation faced a constraint that shaped its entire design: no labeled benchmark exists for this
task. The public FLOW-BENCH dataset provides reference workflow programs but no buggy/correct labels
and no executable LLM implementations; standard code-generation benchmarks provide neither workflow
semantics nor the paired specification the module targets. Every labeled artifact the evaluation uses
therefore had to be constructed — and construction is exactly where an evaluation can quietly become
circular, grading an instrument against its own assumptions. The methodology below is organized
around preventing that: Section 5.6.1 describes the three corpora, Section 5.6.2 the anti-circularity
rules that keep ground truth independent of the system under evaluation, Section 5.6.3 the
calibration protocol, Section 5.6.4 the results, and Section 5.6.5 the measurement-validity record.

### 5.6.1 Three corpora from one dataset

**Base corpus (101 programs).** The starting material is FLOW-BENCH's conditional-OOTB split: 101
enterprise-workflow requirements, each pairing a natural-language utterance with a reference
implementation in a constrained Python subset (task-API calls, conditionals, loops over retrieved
collections). Inspection established two properties that drove the design. First, all 101 reference
sequences parse as ordinary Python — they are usable as executable ground truth. Second, they are
bare statement lists calling 141 distinct undefined task-API functions, with 30 of their 32 branch
guards taking the form *object-attribute compared to string literal*. An adapter therefore converts
each into a self-contained program: attribute accesses are rewritten to subscripts, the guard-
controlling values are promoted to typed function parameters, and each task-API call is synthesized
as a deterministic stub that echoes its parameters — fixing the *environment* while leaving the
*workflow logic* as the object under test.

**Mutation corpus (427 programs).** Known-buggy variants are generated by applying exactly one
semantic mutation at one site: guard negation, comparison-boundary shift, branch swap, step deletion,
step reordering, wrong-variable substitution, container-operation corruption, early return, and
constant perturbation (nine operator classes with applicable sites in this corpus, of ten
implemented). Stub definitions are never mutated, so every mutant represents a workflow-logic fault
rather than a simulated-environment fault. Each mutant is labeled by *behavior*, not by construction:
Section 5.6.2's code-versus-code check classifies eleven of the 427 as semantically equivalent to
their base at the sampled input budget — mutations that changed the text but not the behavior — and
the calibration treats them as a separate category rather than as detection targets.

**Multi-implementation corpus (184 programs).** To test the module against genuine stylistic
diversity rather than single-edit mutations, three LLM families (via a hosted model pool) were each
asked to implement all 101 requirements from the utterance and the stub signatures alone — 294 raw
generations (an outage at the provider truncated one model's run at 49 of 101; the shortfall is
reported, not backfilled), of which 184 survived mechanical screening (parses, correct signature,
no imports, known calls only). A **behavioral admission oracle** then executed each surviving variant
and its reference on 100 shared, seeded inputs, comparing stub-call sequences and return values
directly — code against code, with no intermediate representation involved. Twenty variants proved
behaviorally indistinguishable from their reference and were admitted as *correct-by-behavior*
implementations; the remaining 164 diverged and became the **natural-bug corpus**: real LLM-generated
faults, each with recorded divergence evidence. The admission rate (20 of 184) is itself a finding
with a known cause — the models saw stub *signatures* but not bodies, so many rejections are wrong
guesses about a stub's return shape rather than misread requirements — and the results below
therefore separate crash-shaped divergences from logic-shaped ones and rest their claims on the
harder class.

### 5.6.2 Anti-circularity rules

Two rules were enforced as tested invariants rather than intentions. First, **structural ground truth
is produced by an independent labeler**: the gold control-flow structures used to score extraction
accuracy are built by a separate, deliberately minimal program that walks the Python syntax tree
directly and is forbidden — by an automated test that scans its imports — from touching the
extractor's own code. The gold itself was then human-validated: ten randomly sampled programs
(fixed seed) were rendered gold-versus-extracted side by side and manually reviewed, with all ten
passing and zero gold errors found. Second, **behavioral ground truth is code-versus-code**: the
admission oracle and the correctness labels for the correlation study execute the actual programs and
compare observable behavior; the WIR — the artifact whose trustworthiness is being evaluated — never
appears on the ground-truth side of any experiment. Both rules are stated in the corresponding
reports' methods sections, and both closed off the specific failure mode of an extractor graded
against a copy of itself.

### 5.6.3 Calibration protocol and the three-figure report

All detection results follow one protocol. Base programs are split 50/50 into calibration and
evaluation sets, stratified by workflow type, with every mutant inheriting its base program's side —
so no program's variants straddle the split. The operating threshold is selected on the calibration
set only, by Youden's J statistic over the differential score, using only *behaviorally genuine*
faults as positives (equivalent mutants are excluded from threshold selection); the selected
threshold, τ = 0.10, is frozen in a committed configuration file before the evaluation set is
touched, and every subsequent re-measurement in this chapter re-derives it identically. Confidence
intervals are exact binomial (Clopper–Pearson), computed from first principles.

Results are reported as **three separated figures** rather than one accuracy number: (i) detection on
genuinely-buggy programs, (ii) specificity on semantically-*equivalent* mutants, and (iii) the
false-alarm rate on untouched correct programs. The separation exists because a single conflated
"detection rate" cannot distinguish a missed bug from a correctly-unflagged equivalent mutant — the
two look identical in the numerator and mean opposite things. This lesson was learned empirically
(Section 5.6.5) rather than anticipated.

### 5.6.4 Results

**Seeded-fault detection.** On the held-out evaluation set, the differential verifier detects
**99.5%** of genuinely-buggy mutants (209/210; 95% CI [0.974, 1.000]) at a false-alarm rate of
**5.9%** on untouched correct programs (3/51; 95% CI [0.012, 0.162]), with Youden's J = 0.960 at the
pre-registered threshold. Table 5.2 gives the per-operator breakdown: every operator class is
detected at 100% except constant perturbation (8/9), whose single miss is individually diagnosed — a
program with two guards fed by two independent string parameters, where the shared literal-coverage
queue drains across parameters slowly enough that only two of ten runs are guaranteed to exercise the
mutated comparison. The equivalent-mutant specificity figure is 1/9 with a necessarily wide interval
(n = 9), and its investigation matters more than its value: eight of the nine equivalents score
*exactly* their base program's own score — they inherit the base's status, as a semantically
identical program should — and the ninth is a labeling artifact of the ground-truth input budget, not
a misjudgment by the verifier.

**Table 5.2 — Per-operator detection, genuinely-buggy mutants, evaluation split (strict mode).**

| Operator | n | Detected | Rate |
|---|---|---|---|
| constant-perturb | 9 | 8 | 0.889 |
| corrupt-container-op | 16 | 16 | 1.000 |
| drop-step | 51 | 51 | 1.000 |
| early-return | 49 | 49 | 1.000 |
| negate-guard | 14 | 14 | 1.000 |
| reorder-steps | 49 | 49 | 1.000 |
| swap-branches | 4 | 4 | 1.000 |
| wrong-variable | 18 | 18 | 1.000 |

**Structural extraction accuracy.** Against the independent, human-validated gold, the extractor
achieves node and edge precision, recall, and F1 of **1.000** across all 101 programs. This figure
has a history worth one sentence: the first measurement scored node precision 0.826 and edge F1
0.683 with recall already perfect, the manual validation confirmed that *every* precision error was
a blank bookkeeping node the extractor emitted at branch merges and loop exits — zero genuine
extraction errors — and a post-construction graph-contraction pass removed that entire class, with
the calibration re-run confirming byte-identical detection figures (the bookkeeping nodes carried no
behavioral signal) and zero new abort-gate failures.

**Certificate–correctness correlation.** Across all 427 mutant/base pairs, the inverse certificate
score correlates with a continuous, code-versus-code correctness measure (the fraction of 25 shared
inputs on which mutant and base observably diverge) at Pearson r = 0.41 (Spearman ρ = 0.54); restricted
to behaviorally non-equivalent pairs, r = 0.56 (ρ = 0.60). The interpretation is deliberately modest:
the certificate *separates* broken from equivalent programs well (that is the detection result), and
*grades* degree of brokenness only weakly — most genuine faults in this corpus drive the differential
score to its floor regardless of how many inputs they corrupt, so the score behaves more like a
detector than a severity meter. The chapter claims the former and not the latter. Figure 5.2
(`figures/fig_e3_scatter.pdf`) shows the full distribution: divergent mutants collapse to the score
floor regardless of divergence rate, equivalents (triangles) sit at zero divergence with scores
inherited from their bases, and the threshold line separates the populations — the caption should
note the small positional jitter added for legibility of overlapping points.

**Real LLM-generated code.** On the multi-implementation corpus, three results. *Extraction
robustness:* the pipeline processed every admitted variant — independently written, stylistically
diverse code — with zero extraction aborts, zero crashes, and full statement coverage. *Natural-bug
detection:* of the 164 behaviorally-divergent variants, the strict-mode verifier detects **164/164**,
and — the figure this chapter rests its realism claim on — **68 of 68** whose divergence is
logic-shaped (both programs run to completion but do different things), the class closest to a
genuine reasoning error; crash-shaped divergences (96/96 detected) are reported separately because
they are partly harness-induced and trivially detectable. In the cross-implementation comparison mode
the corresponding figures are 153/164 overall and 60/68 logic-class — the measured cost of the mode's
style tolerance, whose benefit (implementation-freedom false alarms 25% → 10%) and control experiment
were presented in Section 5.4.4. *Instructability:* the per-model screening funnel (how many raw
generations survive to admission) varies markedly across model families and is reported in the
corpus documentation as an observation about the generators, not the verifier.

### 5.6.5 Measurement validity: the correction trail

Three of this chapter's headline measurements were, in their first published form, wrong — and the
project's claim to measurement validity rests not on never having erred but on the mechanism by which
each error was caught, diagnosed with direct evidence, corrected, and preserved. Table 5.3 records
the three invalidations. Every superseded report remains in the repository's evaluation archive with
a note explaining its supersession; nothing was overwritten.

**Table 5.3 — Invalidated measurements and their corrections.**

| What was wrong | How it was caught | Correction and consequence |
|---|---|---|
| The first self-mode calibration silently verified trivial *stub* functions, not the workflows: the pipeline selected the first-defined function in each file, and the generated corpus defines its stubs first. Every number from that run was about the wrong code. | Discovered while building the differential harness, by reading the code path rather than the aggregate numbers. | Entry-point selection fixed (prefer the workflow function); self-mode re-measured — producing the *valid* 0/220 negative result of §5.4.1. The invalid run's numbers were never reused. |
| One mutation operator (early return) was a no-op: it inserted a return immediately before an existing terminal return, so all 101 of its "bugs" were semantically equivalent to their bases — and the ~43% of them then being "detected" were in fact false positives on correct code. | The behavioral ground-truth check (code-versus-code equivalence, §5.6.2) reported a 100% equivalence rate for the operator; reading the generated mutant files confirmed the mechanism. | Operator fixed to cut real logic; its mutants regenerated; reporting split into the three-figure form (§5.6.3) so equivalent mutants can never again masquerade as detection targets. |
| A corpus-wide line-numbering artifact inflated detection: mutant files are re-serialized on generation, shifting every line, so reference-derived branch-observation positions misfired on *all* mutants — manufacturing divergence that read as detection, most visibly for value-only mutations that genuinely had none. | Hypothesis formulated from an anomalous operator-level flip between consecutive reports, then tested by a controlled A/B on individual mutants *before* any fix (two of three false flags recovered exactly their base's score when only the observation lines changed). | Observation positions re-derived from the code under test (the separation rule of §5.4.2); calibration re-run; all pre-correction per-operator figures marked unusable. |
| *(Smaller entries follow the same pattern: an initial straggler diagnosis corrected after review found a miscounted guard; an early overclaim about a false-alarm breakdown refined to a per-variant analysis before publication.)* | | |

Two properties of this record are worth stating. First, each error was caught by an *instrument*, not
by luck: cross-checking the calibration against independently-derived behavioral ground truth, and
against its own prior generation, is what surfaced all three. Second, the corrections moved numbers
in both directions — the operator fix *lowered* an apparent detection rate before later capability
work raised the real one — which is the observable difference between correcting measurements and
tuning them.

## 5.7 Limitations

Every limitation below is measured or empirically bounded; none is a conjecture. They divide into
limits of the *instrument*, limits of the *evaluation*, and limits of *scope*.

**Instrument limits.** (1) *Input coverage for multi-parameter guards.* The guard-literal pool that
guarantees string-guard coverage is maintained per function, not per guard site; a program whose
guards draw on several independent string parameters can exhaust its guaranteed draws before every
mutated comparison is exercised. This is the mechanism behind the evaluation's single missed seeded
fault (1 of 210), diagnosed to the exact run schedule; a per-guard-site queue is the identified
remedy. (2) *Numeric guard boundaries.* The pool covers string literals only; numeric boundary
values are reached through the symbolic layer's solved inputs rather than the dynamic layer's
generator, so a numeric-guarded divergence that the symbolic layer cannot reach may be under-
exercised dynamically. (3) *The timeout boundary.* As measured in Section 5.5, the wall-clock guard
bounds any Python-bytecode hang but cannot preempt a single GIL-monopolizing native operation;
process-level isolation is the known fix. (4) *Self-mode composition.* The self-mode certificate
retains the two-term behavioral composition by design — it answers the fidelity question, for which
both layers carry evidence — but Section 5.4's masking analysis applies to any attempt to reuse that
composition for conformance judgments; differential mode exists precisely because of it.

**Evaluation limits.** (5) *Bounded behavioral equivalence.* The admission oracle and the correctness
labels are N-bounded (100 and 25 shared inputs respectively): a variant differing only on inputs
outside the sample is labeled equivalent. The bound is not hypothetical — one "equivalent" mutant in
the evaluation split is flagged by the verifier and, on inspection, diverges on an input class the
label's budget never sampled; in that instance the instrument was arguably more correct than its
ground truth. (6) *Small strata.* The implementation-freedom false-alarm figures rest on twenty
admitted variants and the equivalent-mutant specificity on nine; both carry the wide intervals
honesty requires, and both are reported as directional rather than precise. (7) *Generator sampling.*
The variant corpus holds one sample per requirement per model family — enough to test the verifier
against style diversity, not enough to characterize any model's output distribution; the per-model
funnel is reported as observation, not inference.

**Scope limits.** (8) *Language subset.* Submitted code must be import-free and attribute access is
normalized away before symbolic analysis; both are documented boundaries of the evaluation harness,
appropriate to FLOW-BENCH-style workflow code but a real restriction on arbitrary LLM output.
(9) *Domain.* All measured claims concern enterprise-workflow programs of FLOW-BENCH's shape —
sequential task calls, string-guarded conditionals, bounded iteration over retrieved collections.
Generalization beyond that shape is untested and is not claimed. (10) *Runtime.* CPython 3.12+ as
described in Section 5.5.

## 5.8 Summary of contributions

This chapter's contributions are five, each stated with the evidence that carries it.

**1. A structural negative result for self-referential validation.** A verification certificate whose
oracle derives from the code under test cannot detect semantic error: shown by construction, and
confirmed at unit scale and across a 220-fault corpus with zero detections (§5.4.1). The result
generalizes beyond this module — it is an argument that applies to any self-checking arrangement in
which the model being validated and the behavior being validated share a source — and within
VibeCheck it is the architectural justification for the dual-track design: correctness judgments
require an independently-produced reference, which is exactly what Module 01 supplies and Module 03
consumes.

**2. Differential verification under an observation/oracle separation rule.** A workable middle
ground between self-checking (circular) and full specification-based verification (unavailable at
this stage of the pipeline): the expected behavior comes strictly from a reference artifact, while
observation positions may come from the code under test — a rule with three load-bearing
instantiations and a measured failure for each violation of it (§5.4.2). Built incrementally and
priced by measurement at every step, the resulting instrument detects 99.5% of seeded faults
(CI [97.4, 100]) and 68/68 real LLM logic bugs at a 5.9% false-alarm rate (§5.4.3, §5.6.4).

**3. Comparison modes selected by lineage, defended by control experiment.** The distinction between
same-lineage and independent-implementation comparison, made categorical and chosen before any score
is computed, with both directions of the trade quantified: style false alarms 25% → 10% under the
appropriate mode, at a measured cost to decision-sensitive fault classes that the control experiment
makes explicit (§5.4.4). The principle — that trace-comparison granularity must be justified by what
the compared artifacts share — transfers to any differential-testing setting.

**4. An evaluation package for a benchmark-less domain.** A reproducible construction that turns a
label-free public dataset into three labeled corpora: an adapter producing 101 executable base
programs, a mutation generator producing behaviorally-labeled fault corpora, and a behavioral
admission oracle that both certifies LLM-generated variants as correct-by-behavior and yields a
natural-bug corpus as a by-product — governed throughout by tested anti-circularity rules,
pre-registered thresholds, exact intervals, and three-figure reporting (§5.6.1–5.6.3). Nothing in the
package is specific to this verifier; it is a recipe for evaluating any tool that judges workflow
implementations.

**5. The correction trail as method.** Three invalidated headline measurements, each caught by
cross-instrument checking, corrected with direct evidence, and preserved in an in-repository archive
alongside every superseded report (§5.6.5). The claim this record supports is deliberately narrow and
deliberately unusual: not that the measurements were always right, but that the process that produced
them detects its own errors — which is, in the end, the only property that makes any of the numbers
above worth citing.

Taken together, the module delivers what the pipeline position demanded: a certified intermediate
representation whose certificate means precisely what it claims — fidelity in self-mode, conformance
in differential mode, never one dressed as the other — handed to the equivalence engine with its
evidence attached. The differential instrument built here is also, in miniature, a preview of the
full system's verdict: what Module 03 does with a specification automaton, this module already does
with a reference implementation's WIR, and the measured behavior of the smaller instrument is the
best available forecast of the larger one's.
