# 00 — Session Findings & Plan Impact

> [!info] Archival note
> Source: Claude Science, "E2E Session" (2026-07-29), commissioned via
> `e2e-integration-plan-prompt.md` to design the M01+M02+M03 integration and FLOW-BENCH evaluation
> plan. All six design docs (D1–D6) plus this findings summary were independently re-verified
> against the repo — see [[E2E Integration Verification Findings|E2E Integration Verification
> Findings]] for the results, including one additional finding (a second, still-open vacuity
> channel) that this session's Python-only emulation could not have surfaced. Treat this note as
> historically accurate for what it claims to have measured; treat the verification note as the
> current understanding of what those measurements mean for the plan.

> **Scope.** Design session, no implementation. Repo examined at `main @ 0daf57e`
> (`git log --oneline -8`, VERIFIED-SOURCE). All experiments run against the working tree
> at that commit. Raw measurements: `e2e_verification_log.json`.
>
> **Evidence tiers** used throughout, per the design prompt: VERIFIED-SOURCE (exact lines read),
> VERIFIED-EXPERIMENT (ran it, observed output), REASONED (inference, chain shown),
> BUILD-DEPENDENT (contingent on a named build step), NOT-ESTABLISHED (flagged guess).

This document exists because **five measurements taken this session change the shape of the plan**
the prompt asked for. They do not contradict the two vault documents
(`P1.4 Bridge Findings.md`, `AP Vocabulary and Lifting Scope Findings.md`) — every established
fact I re-derived held. They sit *upstream* of what those documents examined: the vault
investigated Module 03's lifter, and these findings are about what Module 01 actually emits and
what fraction of it is checkable at all.

Read this document before the other five. Two of them (D1, D3) are structured around these
findings; one (D2) reaches a conclusion opposite to the prompt's framing.

---

## F1 — Module 01 hard-fails on every gateway-bearing spec, so no branching workflow can reach Module 03 today

**VERIFIED-EXPERIMENT.** I ran `run_module_01_pipeline()`
(`module_01_spec/src/api.py:13`) over all 48 BPMN files in `flow-bench/data/context/`:

| Outcome | n |
|---|---|
| `FAIL` (Phase 3 gate, pipeline aborts) | **19** |
| `FAIL_ALIGNMENT_UNPROVEN` (completes, exports) | **29** |
| `PASS` | **0** |

`export_for_module_03()` (`module_01_spec/src/api.py:220` calls it; definition in the same
module) **succeeds on 29/48 and raises on 19/48** — the 19 that hard-`FAIL`.

The 19 failures all carry the same Phase-3 message, e.g. for uid 12:
`XOR Gateway 'exclusiveGateway_4' has 2 unconditioned branch(es) without a default flow.`

**The failing set is exactly the set of specs containing `<exclusiveGateway>`** — set equality
tested and true (`hardfail_equals_gateway_set: true` in the log; 19 specs contain the element,
namespace-aware parse via `ElementTree`). Zero specs in FLOW-BENCH contain `parallelGateway`.

### Why this reorders the plan

The vault's largest open issue (prompt fact 4) is that gateway nodes and task nodes never
coexist in a lifted WIR graph — a structural partition on the **code** side. That is real
(re-confirmed below, F5). But it is **not on the critical path for the walking skeleton**,
because no gateway-bearing *spec* can currently produce a property suite at all. The e2e-eligible
corpus is 29 sequential, gateway-free workflows.

**REASONED** (chain: export raises on all 19 → no `module_03_input.json` exists for them → M03
has nothing to check): any e2e conformance measurement built this month is measured on
straight-line workflows only. That is a stated scope limit of the thesis result, not a bug to fix
first. It also means the gateway half of the lifting-scope fix has **no test corpus** until the
Phase-3 gate is addressed separately.

`FAIL_ALIGNMENT_UNPROVEN` on all 29 survivors is worth flagging to the owner: Module 01 never
reports `PASS` on FLOW-BENCH. The status derives from PBCTS convergence
(`api.py:88-92`, VERIFIED-SOURCE: `overall_status = "FAIL_ALIGNMENT_UNPROVEN"` when
`phase_4_certificate.convergence.converged` is falsy). Whether an unconverged suite is
*legitimate input* to a conformance check is **an owner decision** — see D1 §5.

---

## F2 — The atom vocabularies of the two sides are disjoint by construction: 0 of 116 spec atoms can ever match

**VERIFIED-EXPERIMENT + VERIFIED-SOURCE.** This is the finding that determines what the
walking skeleton's first run will print.

Spec side, after `FormulaNormalizer.normalize()` (`module_01_spec/src/formula_normalizer.py:4`;
note it has **zero callers in the repo** — VERIFIED-SOURCE, grep returns only the class
definition), a P1 atom looks like:

```
done_Microsoft_Dynamics_365_for_Sales_Invoice__7_0_0__retrievewithwhere_Invoice
```

Code side, the lifter's AP set is built from `semantic_match()`
(`module_03_equiv/src/lifter.cpp:135`), which returns **the matched BPMN task name verbatim**
(`return task;` at the exact-lexical and Levenshtein tiers, `return best_task;` at the NLP tier)
or the literal `"unlabeled_task"`. No lifecycle prefix is added anywhere. So the code-side AP is:

```
Microsoft_Dynamics_365_for_Sales_Invoice__7_0_0__retrievewithwhere_Invoice
```

Across the 29 e2e-eligible (spec, variant) pairs: **0/29 pairs have any overlap; 0 of 116 spec
P1 atoms appear in the emulated code AP set.** (I emulated the lifter's AP construction in Python
— `normalize()` = lowercase alphanumerics only, `lifter.cpp:106`; call-name regex from
`lifter.cpp:188` — because the compiled module is unavailable, see F6. Flagged
NOT-ESTABLISHED that the compiled lifter's AP set is byte-identical to my emulation; the
*prefix mismatch* is VERIFIED-SOURCE from the two code paths above and does not depend on the
emulation.)

The name matching itself is largely fine: spec task name → Python function name exact match is
**86.0% mean across 43 pairs, with 26/43 at 100%** (VERIFIED-EXPERIMENT). The problem is the
lifecycle prefix, not the identifier.

### Consequence

**REASONED** (chain: atom gate returns `INCONCLUSIVE` when formula atoms are absent from the
automaton AP set — prompt fact 1, VERIFIED-SOURCE at `lifter.cpp:1066` region → every P1 formula
atom carries a `start_`/`done_` prefix absent from every AP → gate fires on every property):
**the walking skeleton's first FLOW-BENCH run will return `INCONCLUSIVE` for 100% of properties**
unless an AP-lifecycle decision is made in the same milestone as ingestion.

This is a *good* outcome for the atom gate — it is doing exactly its job, and a first run that
reports honest INCONCLUSIVE rather than vacuous COMPLIANT is the fix from prompt fact 1 working.
But it means "wire ingestion, then look at failures" cannot be the whole of Milestone 1: you
would learn only that the gate fires. D1 §3 makes the lifecycle-AP choice part of Milestone 1.

---

## F3 — Only 17.6% of P1 properties are checkable against code at all; 82.4% reference spec-only structure

**VERIFIED-EXPERIMENT.** Over the 29 exported suites, 412 properties total:

| Tier | n | Notes |
|---|---|---|
| `P0_Critical_Sentinels` | 79 | excluded by design (prompt fact 2) |
| `P1_Structural_Control_Flow` | 256 | **211 (82.4%) reference `node(...)`** |
| `P2_Quality_Limits` | 29 | all 29 contain bare non-atom identifiers |
| `P3_Adversarial_Defenses` | 48 | **absent from `tier_semantics`** |
| `synthesized_mutant_killers` | 0 | **absent from `tier_semantics`** |

The `node(...)` atoms are `node(Start)`, `node(End)`, and `node(Decision:_...)` — BPMN control
nodes with no code counterpart. Stripping them leaves **45/256 = 17.6%** node()-free P1
properties, present in 22/29 specs, **median 2 per spec** (VERIFIED-EXPERIMENT).

Those 45 are the real conformance surface today: pure task-precedence formulas of the shape
`!start(B) W done(A)`.

Two further shape facts (VERIFIED-EXPERIMENT):

- **All 29 P2 properties are `G(iteration_count <= 10 -> F(process_complete))`** — the identifiers
  `iteration_count` and `process_complete` are not in the `start`/`done`/`node` atom families and
  survive normalization unchanged. Under the atom gate they will be unmatched → `INCONCLUSIVE`,
  permanently. P2 is not a usable conformance tier without a code-side counterpart for these two
  symbols. It is also **not an LTL parse hazard only** — `<=` is a comparison operator SPOT's
  infix parser will not accept as part of an atom. See D1 §4.
- **34 of 412 properties are exact duplicates within their own tier** (e.g. uid 44's P1 list
  contains `!start(SalesOrder…) W node(Start)` twice). Harmless for correctness, but it inflates
  any per-property denominator; D3 §2 specifies de-duplication before metrics.

---

## F4 — The dominant divergence mode in the corpus is task *omission*, and the P1 property shape is structurally blind to it

**This is the most consequential finding for the evaluation design.**

**VERIFIED-EXPERIMENT.** Classifying all 43 (spec, variant) pairs by how the code's orchestrator
call sequence relates to the spec's task sequence:

| Divergence mode | pairs |
|---|---|
| omission only (a spec task is never called) | **23** |
| exact conformant | 15 |
| omission + reordering | 3 |
| reordering only | **2** |

Now the blindness. The P1 precedence shape is `!start(B) W done(A)` — "B does not start until A is
done". Evaluated with `evaluate_ltlf()` (`module_01_spec/src/ltlf_eval.py:202`) on
lifecycle traces (VERIFIED-EXPERIMENT):

| trace | verdict |
|---|---|
| A then B (correct) | `True` |
| B then A (reordered) | `False` ← detected |
| **A only, B omitted** | **`True`** ← *not* detected |
| B only, A omitted | `False` |
| neither runs | `False` |

Omitting the *later* task of a precedence pair satisfies the property vacuously. **REASONED**
(chain: 23/43 pairs are omission-only → omissions of trailing tasks satisfy every precedence
formula they appear in → those pairs produce no P1 violation): the tier that the prompt calls
"the real conformance checks" cannot see the majority failure mode in this corpus.

Confirmed directly: **7 divergent pairs have no node()-free P1 property that fails** under the
correct call-order lifting (VERIFIED-EXPERIMENT). Examples — `82__llama-3.1-8b.py`, whose
`workflow()` calls exactly one function while the spec has 5 tasks; `77__llama-3.1-8b.py`, 2 of 3
spec tasks called (both source files read directly, VERIFIED-SOURCE).

And there is no liveness tier to catch it: **the only `F`-bearing tiers are P2 (the unusable
`iteration_count` formula) and P3 (which `tier_semantics` does not describe)**
(VERIFIED-EXPERIMENT). Module 01 synthesizes no `F(done_T)` coverage obligation per task.

### Design consequence

A **task-coverage property family** — one `F(done_T)` obligation per spec task — is a
*prerequisite* for the e2e measurement to be meaningful, not a nice-to-have. It is a small,
well-understood addition on the Module 01 side (D1 §6), and it converts 23/43 corpus pairs from
invisible to detectable. Without it the headline e2e number is measured against 2 reordering-only
pairs and is not defensible.

---

## F5 — Prompt facts 4 and 5 both re-confirmed independently

Included so the Claude Code session can cross-check against the vault rather than take it on
trust.

**Fact 5 (sub-CFGs already carry correct order) — VERIFIED-EXPERIMENT, confirmed.**
`CFGExtractor().extract()` (`module_02_extract/src/ast_extractor/cfg_extractor.py`) on
`100__llama-3.1-8b.py` produces `WIR["functions"]["workflow"]` whose nodes are the business calls
as ordinary `block` nodes in source order, chained by edges. The order is present and correct in
what Module 02 already emits; `lifter.cpp` contains **zero references to `functions`**
(VERIFIED-SOURCE, grep empty). The recursive `functions` mapping is a first-class part of
`shared_schemas/wir_schema.json` (VERIFIED-SOURCE), so consuming it is not a schema change.

**Fact 4 (definition order ≠ call order) — VERIFIED-EXPERIMENT, my measurement: 76/165 = 46.1%.**
Denominator is variants whose orchestrator makes ≥2 distinct calls to sibling top-level functions
(order is undefined below 2). This sits inside the vault's two prior figures (47.5%, 45.5%); the
spread is a denominator convention, not a disagreement.

**The structural partition — VERIFIED-EXPERIMENT, confirmed exactly.** Over all 184 normalized
variants: 0 have a top-level gateway node, 184 have top-level task nodes, 0 have a task-typed node
inside any sub-CFG, and gateways appear only inside sub-CFGs. Full node-type census in the log.

---

## F6 — The C++ track is unbuildable in this environment, which gates 79 of 116 Module 03 tests

**VERIFIED-EXPERIMENT / BUILD-DEPENDENT.** `import vibecheck_lifter` fails with
`ModuleNotFoundError` (Python 3.11.15, repo working tree). Test-function counts by file
(VERIFIED-SOURCE, `grep -cE '^\s*def test'`):

| file | test defs | gated on C++ import |
|---|---|---|
| `tests/test_cpp_engine.py` | 32 | yes (`pytestmark = pytest.mark.skipif`, line 31) |
| `tests/test_phase_b.py` | 28 | yes (line 31) |
| `tests/test_phase_c.py` | 19 | yes (line 29) |
| `tests/test_pipeline.py` | 37 | **no** |
| **total** | **116** | 79 gated |

So 37 tests run without the toolchain and 79 do not. (The vault cites 113 for the C++ track;
I count 79 `skipif`-gated defs plus 37 ungated. Test *defs* and pytest-*collected* tests differ
when fixtures parametrize — no `parametrize` markers exist in these files, VERIFIED-SOURCE — so
I report my count and flag the discrepancy rather than assert either is wrong.)

Every claim in D2 about lifter behavior is therefore VERIFIED-SOURCE (reading `lifter.cpp`) or
emulated in Python, never observed from the compiled artifact. **BUILD-DEPENDENT: a working
SPOT + pybind11 build is a prerequisite for Milestone 1 to produce any real verdict at all.**
This should be the very first task in the plan, ahead of ingestion, because it is the only
prerequisite that can invalidate the rest of the schedule.

---

## What the owner must decide

Flagged here and repeated in context in the relevant document. I have **not** silently picked any
of these.

1. **Is `FAIL_ALIGNMENT_UNPROVEN` an acceptable input status for conformance checking?** (F1)
   All 29 eligible specs carry it. If not, the eligible corpus is 0 and PBCTS convergence becomes
   the blocking task. → D1 §5
2. **Lifecycle AP representation on the code side** — add `start_`/`done_` events to the lifted
   automaton, or strip prefixes from spec atoms? These are not equivalent; one changes the
   automaton's state count and invalidates geometry assertions, the other weakens what P0 could
   ever mean. → D1 §3
3. **Does Module 01 gain a task-coverage (`F done_T`) tier?** (F4) Without it the e2e number rests
   on 2 corpus pairs. With it, Module 01's synthesizer changes, which touches its (currently
   nonexistent) test surface. → D1 §6
4. **Gateway specs: fix the Phase-3 gate, or scope them out of the thesis?** (F1) 19/48 specs and
   the entire branching-conformance story hang on this. → D4 §M4
5. **How much detection-rate regression is acceptable in exchange for a semantically correct
   lifter?** D2 measures the honest answer as a *decrease* from 53.2% to 40.4% on the current
   corpus, and argues the decrease is correct. That trade is the owner's to accept. → D2 §6
