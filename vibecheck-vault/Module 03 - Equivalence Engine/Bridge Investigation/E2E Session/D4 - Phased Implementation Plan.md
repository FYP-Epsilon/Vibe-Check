# D4 — Phased Implementation Plan

> Repo at `main @ 0daf57e`. Depends on D1, D2, D3 and the findings in
> `00 - Session Findings and Plan Impact.md`.
>
> The reframe this plan is designed against: walking skeleton before the big rock, thesis-readiness
> not gated on good numbers, evaluation designed to produce a defensible measurement whatever it
> shows.

## Milestone map

| # | Milestone | Gate to exit | Thesis output |
|---|---|---|---|
| M0 | Toolchain + startup repair | 116/116 M03 tests runnable; M01 service starts | none (infrastructure) |
| M1 | Walking skeleton: real property suite reaches `check_compliance()` | one FLOW-BENCH spec produces per-property verdicts | architecture chapter |
| **CP1** | **Checkpoint: reassess with real failure data** | decision recorded on D2 and on the coverage tier | — |
| M2 | Minimal harness + first full FLOW-BENCH run (29 specs) | Table 1 + Table 3 populated, definition-order lifting | first e2e results |
| M3 | Lifting-scope fix (D2) | paired comparison, 28 geometry assertions re-derived | methodology chapter |
| M4 | Coverage tier + gateway gate (scope decision) | either implemented or documented as scoped-out | results/limitations |
| M5 | Full evaluation + real-world demo | all three tables, demo runs e2e | evaluation chapter |

M0 through M2 are the walking skeleton. **CP1 is the checkpoint the reframe asks for**, and it is
placed *before* M2's full run rather than after, for a reason given in §CP1.

---

## M0 — Toolchain and startup repair (prerequisite, blocks everything)

This milestone exists because two things are broken in ways that make every downstream measurement
impossible, and neither is on the current plan.

**M0.1 — Build the C++ track.** `import vibecheck_lifter` fails with `ModuleNotFoundError`
(VERIFIED-EXPERIMENT). **79 of 116 Module 03 tests are `skipif`-gated on that import**
(VERIFIED-SOURCE: `pytestmark` at `tests/test_cpp_engine.py:31`, `tests/test_phase_b.py:31`,
`tests/test_phase_c.py:29`); only `tests/test_pipeline.py`'s 37 run without it. Until SPOT +
pybind11 build, no claim about lifter behavior can be validated and D2 cannot be implemented at
all. **This is the single highest-risk item in the plan** because it is the only one that can
invalidate the schedule rather than just delay it, and it is a toolchain problem, not a design
problem.

**M0.2 — Repair Module 01's service startup.** `module_01_spec/src/main.py` imports
`automata_lifter` in both branches of its try/except fallback (lines 11 and 16) and the module is
absent from `src/` (VERIFIED-SOURCE). The FastAPI app therefore cannot start. The *library* works —
I ran the full pipeline over 48 specs in-process (VERIFIED-EXPERIMENT) — so this is a stale import
from the SPOT→PBCTS pivot, not a functional gap. It blocks the demo (D5) and any UI path.

**M0.3 — First tests for Module 01.** It has zero. The minimum is the oracle self-consistency check
from D3 §3.2(d), which I measured at 45/45 (VERIFIED-EXPERIMENT) — a cheap regression guard on a
module that just pivoted architecture twice.

Exit gate: `pytest` collects and runs all 116 Module 03 tests; `uvicorn` starts the Module 01 app;
Module 01 has a passing test file.

---

## M1 — Walking skeleton

Deliver the minimum path from Module 01's exported JSON to a per-property verdict, per D1.

**M1.1** `module_03_equiv/src/property_ingest.py` — load, validate, normalize (via the currently
uncalled `FormulaNormalizer`, `module_01_spec/src/formula_normalizer.py:4`), de-duplicate,
tier-gate. Pure Python, so it is testable without M0.1 — this is the one piece of M1 that can
proceed in parallel with the build work.

**M1.2** `process_wir_batch()` signature change (`module_03_equiv/src/pipeline.py`) — accept a
`PropertySuite`, iterate per property, record `verdict` / `unmatched_atoms` /
`counter_example_trace` / `tier` / `spec_uid`. Preserve the single-string path so the 37 ungated
tests keep passing.

**M1.3** The atom-vocabulary fix — D1 §3 Option B (collapse spec-side lifecycle prefixes). **This
must be in M1, not deferred.** Finding F2 measured that 0 of 116 spec atoms can match the code AP
set, so without it the skeleton's first run returns `INCONCLUSIVE` for 100% of properties and
teaches nothing. Option B requires no C++ change, which is why it is the M1-appropriate choice.

**M1.4** Report schema — with `out-of-scope` as a distinct outcome from `INCONCLUSIVE` (D3 §2).
288 of 412 properties are gated out by design; conflating the two categories would make every
downstream table unreadable.

Exit gate: one eligible spec (e.g. uid 44, which has node()-free P1 properties and real variants)
produces a per-property verdict table with at least one non-INCONCLUSIVE verdict.

**Owner decision required before M1.2 lands:** whether ingestion accepts suites carrying
`FAIL_ALIGNMENT_UNPROVEN`. All 29 eligible specs carry it (VERIFIED-EXPERIMENT); rejecting it
makes the eligible corpus zero and promotes PBCTS convergence to blocking. D1 §5 recommends
accept-and-record.

---

## CP1 — Checkpoint: reassess the lifting-scope fix against real data

The reframe asks for this checkpoint after the first real run. I am placing it **after M1's
single-spec run and before M2's full run**, and I want to be explicit that this differs from the
prompt's sequencing, because a large part of what the checkpoint was meant to discover has already
been measured this session.

What the checkpoint was for: decide how much of D2 is worth doing, based on actual failures rather
than blind design. What is already known (all VERIFIED-EXPERIMENT, this session):

- Definition-order vs call-order lifting **disagree on 29.3% of property-checks** (17/58) — the
  fix materially changes verdicts.
- On the clean-oracle subset, definition-order detection is **53.2%** and call-order is **40.4%**,
  both with **0% false positives**.
- **10 of 11 of definition-order's extra detections rest on functions that are never called**
  (D2 §6) — the higher number is backed by non-executable witnesses.
- The dominant corpus divergence mode is **omission (23/43 pairs), not reordering (2/43)** — so the
  fix's ceiling on this corpus is small regardless of correctness.

So the checkpoint's job is narrower than originally framed: not "is the fix worth doing" but
**"confirm the emulated measurement reproduces against the compiled lifter, then accept or reject
the detection-rate trade."** Two decisions get recorded here:

1. **Accept 53.2% → 40.4% in exchange for witness validity?** (D2 §6). Owner decision. My
   recommendation: yes, and publish both numbers with the spuriousness trace, because the trace is
   itself a thesis finding about self-consistent-looking verification.
2. **Does the coverage tier (D1 §6) get built?** Owner decision. Without it, the e2e detection
   number rests on 2 reordering-only pairs and is not defensible; with it, 23 more pairs become
   detectable, but Module 01's synthesizer changes.

If (1) is rejected, M3 becomes documentation-only (ship definition-order lifting with the
limitation published) and M4 absorbs the freed time. If (2) is rejected, D3's headline metric must
be reported as *precedence-conformance only*, with the omission blindness stated as a scope limit.

---

## M2 — Minimal harness and first full FLOW-BENCH run

Per D3 §6, `eval_e2e/` at repo root. Reuse `clopper_pearson()` from
`module_02_extract/eval/c5_experiments.py` and the split/τ convention from `eval/calibrate.py`
(VERIFIED-SOURCE: 50/50 stratified split, fixed seed, Youden's J on CALIB, Clopper–Pearson on
EVAL). Do not regenerate any Module 02 report.

**M2.1** Corpus inventory table (D3 §1) — 48 specs, 29 exportable, 43 e2e pairs, construct
coverage. This table is a thesis deliverable in its own right and needs no verdicts to produce.

**M2.2** Spec-order extraction with a **proper graph traversal**, not a single-successor walk.
D3 §4.4: the naive walk reaches all task nodes in only 24 of 29 specs, and that incompleteness
alone produced an apparent 44.4% false-positive rate that vanished to 0.0% on the complete subset.
This is a harness self-test, not an optional refinement.

**M2.3** Natural-label derivation for the 43 (spec, variant) pairs — 15 conformant, 28 divergent as
measured this session.

**M2.4** First full run over 29 specs with definition-order lifting, producing Table 3 rows.

Exit gate: Tables 1 and 3 populated; INCONCLUSIVE rate reported as a first-class figure.

---

## M3 — Lifting-scope fix

Per D2. Sequenced after M2 so the paired comparison has a pre-fix baseline from the same harness.

**M3.1** Sub-CFG consumption in `lifter.cpp` Phase A — entry-point selection (max-sibling-calls,
recorded in diagnostics), call-site detection reusing the existing regex at `lifter.cpp:188` and
`structural_builtins` at `lifter.cpp:190`, **return-edge synthesis** (D2 §1: every variant has at
least one sub-CFG whose `exit_node` has no outgoing edge, so the splice must synthesize it —
getting this wrong dead-ends the automaton at the first call).

**M3.2** Re-derive the **28 hardcoded geometry assertions** — 7 in `test_cpp_engine.py`, 15 in
`test_phase_b.py`, 3 in `test_phase_c.py`, 3 in `test_pipeline.py` (VERIFIED-SOURCE). Each encodes
an expected automaton shape for a specific fixture and must be re-derived by hand; this is the
dominant cost of M3, not the walk rewrite. Also review the 9 AP-name assertions in
`test_cpp_engine.py`.

**M3.3** Re-baseline Phase B and Phase C. Their algorithms do not change but their input geometry
does, so stuttering quotients and cluster memberships will move. Cluster-membership changes are a
**result to report** (D3 §3.3a), not a regression to suppress.

**M3.4** Optional here, per CP1: D1 §3 Option A (lifecycle APs on the code side). If taken, it
belongs in M3 because the geometry assertions are already being re-derived — paying that cost once
rather than twice is the whole argument for this sequencing.

**M3.5** Re-run M2's harness; produce the paired comparison with the witness-validity metric.

Exit gate: paired table (definition-order vs call-order) × (detection, false-alarm, INCONCLUSIVE,
witness validity), all with CIs.

---

## M4 — Coverage tier and the gateway decision

**M4.1 — Coverage tier** (if CP1 approved it). Module 01's `FLTLSynthesizer`
(`module_01_spec/src/ltlf_synthesizer.py:8`) gains one completion obligation per task node. Note
from D1 §6 that this family is `F`-bearing and therefore either needs the LTLf→LTL bridge or must
be evaluated by the pure-Python `ModelChecker` (`module_03_equiv/src/model_checker.py:125`); the
second is cheaper and keeps the bridge out of scope, at the cost of two engines behind one results
table, which must be disclosed.

**M4.2 — The gateway decision. Owner call, and it is the largest single scope question in the
project.** VERIFIED-EXPERIMENT: Module 01 hard-fails on exactly the 19 specs containing
`<exclusiveGateway>` (set equality tested true), all with the same Phase-3 diagnostic shape —
*"XOR Gateway 'exclusiveGateway_4' has 2 unconditioned branch(es) without a default flow."*
Consequences either way:

- **Fix the gate:** unlocks 19 specs, **131 additional mutants**, and the entire branching-
  conformance story — which is also what makes D2's gateway/task partition fix testable. Cost is
  unknown until the gate's intent is understood: the diagnostic may be *correct* (FLOW-BENCH's
  BPMN genuinely lacks default flows), in which case the fix is a policy change — admit
  underspecified gateways with a recorded warning — not a bug fix.
- **Scope them out:** the thesis result covers sequential workflows only. Defensible, and D3 §1's
  construct-coverage table states it honestly, but it means the branching capability ships
  untested.

Note the asymmetry: the gate may not be wrong. Establishing whether these BPMN files are
underspecified is a small investigation that should precede the decision, and it is *not* a design
question I can settle from here — flagged NOT-ESTABLISHED whether the 19 specs are spec-invalid or
the gate is over-strict.

---

## M5 — Full evaluation and demo

**M5.1** All three D3 tables plus the detection-vs-witness-validity figure.
**M5.2** Real-world demo per D5, including its M03 HTTP-service prerequisite (D5 §3 — this is
larger than the vault's framing suggests; Module 03 has no HTTP service at all).
**M5.3** Limitations section, written from measurements: sequential-only scope, omission blindness
if M4.1 was declined, the 28 `early-return` out-of-scope mutants, depth-1 inlining, the
entry-point heuristic's unestablished generality.

---

## Critical path and parallelism

```
M0.1 (C++ build) ──────────────┬── M3 ── M3.5 ─┐
                               │               ├── M5
M1.1 (ingest, pure Python) ─┬──┴── M2 ── CP1 ──┘
M0.2/M0.3 (M01 repair) ─────┘                   │
                                        M4 ─────┘
```

Genuinely parallelizable: M1.1 (pure Python) does not wait on M0.1; D3's corpus-inventory table
(M2.1) needs no verdicts; the thesis chapters in D6 need no implementation at all.

**Sequencing risks, honestly stated.** M0.1 is the schedule's only true blocker and it is a
toolchain risk, not a design risk. M3.2's 28 assertions are the largest mechanical cost and are
easy to under-budget. M4.2 is the largest *scope* risk and should be decided before M3 starts, not
after, because a decision to fix the gateway gate changes what M3 needs to be tested against.
