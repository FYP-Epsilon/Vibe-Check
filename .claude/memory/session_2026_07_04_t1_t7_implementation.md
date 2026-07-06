---
name: session-2026-07-04-t1-t7-implementation
description: T1-T7 + D1-D5 + E1-E4 + X1-X4 + C1-C5 + F1-F2 + Session A Module 02 sessions — genuine-bug detection 0.929→0.957→0.995, negate-guard 8/14→14/14 after F2's collector branch-decision field, constant-perturb 0/9→8/9 after Session A's A2 literal-coverage fix; E2 node/edge F1 both →1.0000 after F1's bookkeeping-node contraction; A1 removed V2's OR-composition masking in differential mode without raising false-alarm rate (0.0588 unchanged)
metadata:
  type: project
---

Implementation session executing the sonnet_module02_impl_prompt.md mandate (see [[round3_verified_findings_2026_07_04]]) on branch `fix/mod2/verdict-and-eval-corpus` (off `develop`). All T1-T7 landed, 127 tests passing (started at 105), one commit per task.

**Why:** Round-3 R&D had verified the vacuous-verdict bug and several smaller bugs with file:line evidence; this session implemented fixes plus built the FLOW-BENCH-derived evaluation harness (adapter, mutation generator, calibration runner) the user asked for as the actual measurement instrument.

## What landed (commits on the branch, in order)

- **T2** `789455a` — `guards.py:88/116` UnaryOp `value=` → `operand=` kwarg fix (+ the paired `_make_literal` reader at line ~163, which the mandate didn't call out but had to change in lockstep or the fix would regress the fallback path to a hard failure).
- **T3** `d070462` — widened V2's concrete-exec catch tuple in `concolic.py:147` to add `NameError, ValueError, RecursionError`.
- **T1** `d88c00b` — removed V3 from the OR-composition (`composer.py`: `combined = 1-(1-v1)(1-v2)`), V3 now gates on `abort` instead. `certificate.py`'s `confidence` is now `node_coverage` itself, never saturates to 1.0.
- **T4** `ff0b1d4` — ported `e4ba019`'s container-seeding + concrete-`len()` by hand onto the modularized `z3_sym_engine` package (the commit patched the pre-split monolith and was never merged). Added a coverage-credit term to `_emit_certificate` since container-only functions had no scalar inputs for solver_rate to key off.
- **T5** `2a35449` — `eval/flowbench_adapter.py`: turns all 101 FLOW-BENCH sequences into executable workflows (guard-attribute promotion to typed params, stub synthesis, `obj.attr`→`obj["attr"]` rewrite). 101/101 round-trip through `_run_verification` with zero outer-catch-all hits.
- **T6** `af5c321` — `eval/mutate.py`: all 10 mutation operators, 429 applicable mutants across 9/10 operators (off-by-one-loop has zero applicable sites — no `range()`/slice usage anywhere in this corpus).
- **T7** `32eac90` — `eval/calibrate.py`: stratified CALIB/EVAL split, Youden's J threshold selection, Clopper-Pearson CIs (hand-rolled via `math.comb` bisection, no scipy dependency — verified against the x=5,n=10 textbook value).

## Key findings (verified empirically, not just from source reading)

1. **T1's fix is necessary but not sufficient — v1 saturates too.** Under the new 2-term formula, whenever v1=1.0 the product collapses to 0 so `combined=1.0` regardless of v2. v1=1.0 is *structural*: V1's oracle (`WIRReferenceInterpreter`) re-derives the "expected" trace from the same (possibly mutated) source, and the comparator discards branch *decisions* when matching (`comparator.py:113-115`). Verified on `loan_approval.py`: guard-negation, boundary-shift, and constant-perturb mutations all left v1=1.0, v2 unchanged from baseline. Only a crash-inducing mutation moved the verdict. See `test_integration.py::test_crash_mutation_fails` for the honest (non-rigged) acceptance test and its documented limitation.

2. **Major new finding from actually running T7 (not in round-3 findings): `src/dynamic_tracer/randomized.py:86-87` never randomizes string-typed parameters** — `elif ann is str: inputs[param_name] = ""` assigns the same empty string on every one of the `n_runs` trials. Since most FLOW-BENCH guard-promoted params are `str`-typed (string-literal comparisons like `"high"`/`"urgent"`), V1 exercises exactly one distinct input across all runs, capping `input_coverage_score` (and thus V1 confidence) at `1/n_runs` regardless of program correctness. This explains why `combined_confidence` clustered near 0.1 across nearly the entire 101-program corpus in the T7 run, and why Youden's J found **zero discriminative power at every candidate threshold** (`tau=0.0, J=0.0`) between correct and mutated programs in this corpus.

**How to apply:** Before any future calibration run is trusted, `randomized.py:86-87` needs a real string generator (e.g. sample from a small pool of plausible/adversarial string literals, or draw from constants seen in the source's own guard comparisons). Until fixed, T7's calibration numbers should be read as "no signal was measurable with the current input generator," not "the pipeline has no bug-detection power" — those are different claims. This is next-session scope; not touched in this session per the mandate's explicit deferral list (though it wasn't explicitly named, it falls under "adaptive n_runs"-adjacent input-generation work that the mandate said to defer).

3. GitNexus flagged HIGH risk on T2, T4 individually and CRITICAL on the whole-branch `compare` diff against `develop` — expected given the surface area (composer/certificate/concolic/evaluator/tracer all touched), not a signal of an actual problem; verified via full test suite + targeted empirical scripts at every step.

## Not done in the T1-T7 session (deferred, per mandate's "what not to do")

`visit_Attribute`, wall-clock timeouts, typed per-layer `/verify` statuses, adaptive `n_runs`, and (at the time) the string-randomization fix from finding #2.

---

## Follow-up session (same day): D1-D5 differential-mode work, commits `d15466c..f8cfdc0`

Mandate: fix the string-randomization + self-referential-oracle causes of T7's `J=0`, then build differential mode (verify a mutant against its *base* program's WIR instead of one re-derived from the mutant). All D1-D5 landed; 137 tests passing.

**Commits, in order:** D3 `d15466c` (comparator: compare branch decisions when both sides support it — see below, this stays a no-op for real traces by design) → D1 `f5d29c4` (string-literal-pool input generation) → D2 `1795970` (V2 string-token reverse map) → **`be47afe` (unplanned, critical): `_select_entry_function` fix** → D4 `f1a5b91` (differential-mode harness) → `f8cfdc0` (full differential calibration run + report).

### The critical unplanned fix: wrong function was being verified all along

While building D4, a base program and its own mutants scored *identically* under the new differential harness, which made no sense. Root cause: `main.py`'s `_run_verification` (and `calibrate.py`'s WIR-selection) used `function_name = next(iter(functions))` — whichever function the source **defines first**. `eval/flowbench_adapter.py` emits task-API stub defs *before* the `workflow` def they support, so for every one of the 101 FLOW-BENCH corpus programs and their mutants, this picked a trivial stub (e.g. `def Jira_Issue__2_0_0__retrievewithwhere_Issue(...): return {...}`, zero branches) — **never `workflow`, never the actual orchestration logic**. Fixed with `_select_entry_function(functions)`: prefers a function literally named `workflow`, falls back to `next(iter(...))` for single-function fixtures (unaffected).

**This means the T1-T7 session's finding #2 above (string-randomization) was measured on the wrong function the whole time.** It's still a real, independently-fixed bug (D1), but it was not the primary or sole cause of T7's `J=0` — it was one contributing factor on top of "verifying a no-op stub." `eval/results/calibration_report.md` (self-mode) predates this fix and should be treated as **invalid / needs a re-run**, not as ground truth. Per the mandate, it was not auto-regenerated this session (self-mode report is explicitly preserved, not overwritten by a differential run).

### D1-D3: three real, independent fixes (each verified, each necessary but each insufficient alone)

- **D1** (`randomized.py:86-87`): str-typed V1 inputs were a constant `""` every run. Now sampled from a pool of guard-compared string literals (extracted via `ast.Compare`) plus `""` and a random junk string, so both sides of every string guard actually get exercised.
- **D2** (`evaluator.py` / `registry.py` / `concolic.py`): V2 tokenized strings as `z3.IntVal(hash(v))` but had no way to decode a solved token back to a string — `_z3_to_python` returned a raw int, silently breaking the next concrete iteration. Added a token→literal reverse map on the registry; verified V2 now solves `status == "high"` and covers both branches from a non-matching start.
- **D3** (`comparator.py`): branch **decisions** were discarded (`("branch_point",)` bare tuple) regardless of `taken_branch`. Made comparison decision-aware **only when every branch_point event on both sides carries `taken_branch`** — checked once per comparison, not per-event, specifically to avoid an asymmetric regression (expected always has it, the real collector never does, so mixing them would make every branch mismatch on any program, correct or not). Verified: real traces are unaffected (collector.py never emits decisions), synthetic traces that do carry it now discriminate correctly. **By design, this is a no-op for real executions until collector.py is separately enhanced** — that enhancement was explicitly out of scope this session.

### D4: differential mode built, does NOT restore detection — two deeper, independently verified causes

Building differential mode (`eval/calibrate.py --mode differential`, `run_v1_pipeline(source=mutant, wir=base_func_wir)`) surfaced two blockers that persist even with a correct oracle:

1. **The reference interpreter cannot execute task-API calls.** `WIRReferenceInterpreter._exec_stmt` runs `exec(stmt, {"__builtins__": {}}, state)` — no access to the compiled stub defs in the source. Any assignment that calls a user-defined function (`incident = ServiceNow_..._incident()`) silently fails (`except Exception: pass`) and never populates `state`; every guard reading that variable then falls to its permissive-False default, and any for-loop over its result gets `[]`. **Confirmed directly**: base program uid_4, differential mode against its own WIR, scores `combined_confidence = 0.0` — the *correct* program fails its own differential check. This affects self-mode and differential-mode identically (both use the same interpreter); switching the oracle to the base program's WIR does not help, because the base's own reference execution is equally broken. This is deeper than, and supersedes, Round-3b's "self-referential oracle" diagnosis — the oracle isn't just self-referential, it structurally cannot execute this class of program at all.
2. **Value-only mutations produce identical trace shape.** Confirmed on a hand-crafted zero-function-call base/mutant pair (`status == 'high'` vs `not (status == 'high'`)`): identical `combined_confidence` on both, because D3's decision-comparison can't activate for real traces (see D3 above) — this is the SAME root cause as before, now reconfirmed as a genuine floor rather than an artifact of the wrong-function bug.

**Full differential calibration** (101 corpus + 429 mutants, 50/50 CALIB/EVAL, seed 1234): Youden's J = 0.0506 at τ=0.0999 (nonzero, unlike self-mode's exact 0.0, but weak). EVAL: detection 0.432 (95% CI [0.365, 0.500]), false-alarm 0.392 (95% CI [0.258, 0.539]) — **these are close to each other, i.e. a near-coin-flip signal, not a working detector**. Per-operator numbers (in `eval/results/calibration_report_differential.md`) should be read as noise from cause (1), not as genuine per-operator difficulty. `eval/threshold.json` is frozen from this run but annotated as not a usable operating point given cause (1).

**How to apply next session, in priority order:**
1. Give `WIRReferenceInterpreter` (or its `_exec_stmt`) access to a real compiled namespace (the same `compiled_ns` already threaded everywhere else) so it can actually call task-API stubs. This is a core-semantics change to the oracle used by 137 existing tests including the parity suite — needs its own focused validation pass, not a tack-on. Advisor's assessment: do this *before* trusting any future calibration number.
2. Only after (1): re-run self-mode calibration (the existing `calibration_report.md` is invalid, measuring the wrong function) and differential-mode calibration, and see whether cause (2) (value-only mutations) is the only remaining floor.
3. Enhancing `collector.py` to emit real branch decisions (unblocking D3's fallback) is the natural follow-on to close cause (2), but only worth doing after (1) makes the numbers otherwise trustworthy.

## Not done in the D1-D5 session (deferred)

Fixing the interpreter's exec environment (finding D4-1 above), `visit_Attribute`, wall-clock timeouts, typed per-layer `/verify` statuses, adaptive `n_runs`, collector.py decision emission.

---

## Follow-up session (next day): E1-E4 task-observability alignment, commits `2fc1af7..c5dafa5`, PR #25

Mandate: fix D4's two root causes (interpreter can't execute task-API calls; stub calls invisible in traces) and re-measure. **Result: differential mode went from a near-coin-flip (J=0.05) to a genuinely working detector (J=0.81).** 141 tests passing.

**Commits, in order:** E1 `2fc1af7` (interpreter exec_env) → E2 `b28d245` (task-event alignment) → E3 `c5dafa5` (archive old reports, re-run both calibrations).

### E1 — reference interpreter given a real execution environment

`WIRReferenceInterpreter.__init__` now takes `exec_env` (stub defs + `SAFE_BUILTINS`); `_exec_stmt` execs against it instead of `{"__builtins__": {}}`. `exec_env=None` preserves the old behavior exactly (regression-tested). `RandomizedDifferentialTester._run_expected` passes its own `_compiled_ns`. Also added `exec_errors` counting (`_exec_stmt`/`_eval_guard` failures) surfaced as a `"_exec_errors"` trace event — diagnostic only, comparator ignores unknown event types. Verified: uid_4's interpreter trace went from one degenerate "loop exits immediately" event to the full 2-iteration loop with 6 branch_point events and `exec_errors=0`.

### E2 — stub calls made observable as task events on both sides

Stub-call assignments are WIR **block** statements, not "task"-type nodes, so even with E1's fix, neither side emitted a `task_entry`/`task_exit` for them. Added:
- `main.py:_derive_task_patterns(tree, entry_function)`: task_patterns is now `[entry_function] + every other module-level function name` (was just `[entry_function]`). Mirrored in `calibrate.py`. Verified zero substring collisions across the real corpus's function names before relying on this — and deliberately did **not** switch the collector's substring matcher to exact matching, because `tests/test_dynamic_tracer_parity.py` relies on substring matching (`task_patterns=["task"]` matching `task_process`/`task_loop`/etc.) — switching would have broken that suite.
- `interpreter.py`: `WIRReferenceInterpreter` takes a `task_names` set; `_exec_stmt_observed` (used for block/entry/exit/break/continue/return, not "task"-type nodes which keep their own existing whole-node wrapping) parses each statement once (cached) to detect a call to a known task name and emits synthetic `task_entry`/`task_exit` around it — never traces into the stub's body.
- `randomized.py`: derives `_stub_task_names = task_patterns - {function_name}`, passes to the interpreter.

**E2 acceptance test** (`tests/test_integration.py::TestTaskObservabilityAlignment`, a hand-built 4-stub workflow): base-vs-itself gets 20/20 matching runs; a drop-step mutant (middle stub deleted) gets 0/20; a negate-guard mutant whose branches call different stubs gets 0/20.

### E3 — both calibrations re-run; differential mode now works

Archived (not deleted) the two invalid/superseded reports into `eval/results/archive/` with a README. Re-ran:

- **Self-mode** (first valid measurement of `workflow`, not a stub): J=0.30, detection 0.373, false-alarm 0.059. Still architecturally self-referential (WIR re-derived from the mutant), but a genuine narrow channel exists: mutations that make the *actual* code raise an exception (`corrupt-container-op`'s KeyError, `wrong-variable`'s NameError) show up as an actual-side `exception` trace event with no reference-side counterpart (the interpreter swallows the equivalent failure silently) — hence those two operators sit at 1.000 while purely-logical mutations stay low.
- **Differential mode**: Youden's J **0.0506 → 0.8069**, detection **0.4318 → 0.8636** (95% CI [0.811, 0.906]), false-alarm **0.3922 → 0.0588** (95% CI [0.012, 0.162]) — CIs no longer overlap. Per-operator: `negate-guard`/`boundary-shift`/`constant-perturb` (D4's predicted-hard "value-only" class) are now at or near **1.000** — in the real FLOW-BENCH corpus, a mutated guard's two branches typically call *different* stubs, so E2's task-sequence divergence catches them without needing collector.py's still-missing branch-decision field. `drop-step`/`wrong-variable`/`corrupt-container-op`/`swap-branches` all at 1.000. `early-return` is the one real remaining floor at 0.431 — only removes trailing steps, so only detectable when a random run reaches the cut-off point; a genuine, explained limitation, not a bug. `boundary-shift` (n=1) and `swap-branches` (n=5) have too few applicable sites in this corpus for a precise rate estimate.

`eval/threshold.json` re-frozen from the new differential CALIB run (τ=0.0999, J=0.8069) — this is now a *usable* operating point, unlike the prior session's frozen threshold.

### What this means for the thesis

The vacuous-verdict fix (T1) plus task-observability alignment (E1+E2) together produce a Module 02 pipeline whose differential-mode verdict is empirically a working bug detector on a real, published benchmark corpus (FLOW-BENCH) across 9 mutation operators — not just a plausible design, a measured one with pre-registered CIs. Self-mode's architectural limitation (can't detect logic-only bugs without an exception) remains a valid, separate, still-true finding and a legitimate thesis paragraph in its own right — it motivated *why* differential mode was necessary in the first place.

## Not done in the E1-E4 session (deferred)

Collector.py branch-decision emission (D3's cause 3) — explicitly gated on data: with E2 in place, value-only mutations are mostly caught via task-sequence divergence instead, so this is no longer the clear next priority it looked like after D4. `visit_Attribute`, wall-clock timeouts, typed per-layer `/verify` statuses, adaptive `n_runs`, `merge_states` wiring — still out of scope. `early-return`'s lower detection rate is a measured, explained floor, not flagged as a bug to fix. **(Revised below — X1-X4 found `early-return`'s low rate is actually a mutate.py bug, not a floor.)**

---

## Follow-up session (next day): X1-X4 research experiments (E2 structural accuracy / E3 certificate-correlation, using the thesis's own numbering — distinct from the previous session's "E1/E2" task-observability work above), branch `feat/mod2/e2-e3-experiments` off `fix/mod2/verdict-and-eval-corpus` (PR #25 still open at the time, so this is stacked on it), commits `4b2e431..<wrap-up>`, PR opened separately.

Mandate: produce the two remaining thesis research measurements with hard anti-circularity guarantees. **No `src/` changes — pure measurement session.** 171 tests passing (added 30 new: 6 gold-labeler + 12 matching-logic + 12 stats/recorder).

### X1 — independent gold-WIR labeler (`eval/gold_wir.py`)

Derives a statement-level gold CFG straight from `ast`, with a hard rule enforced by an import-scan unit test: **never imports `src/ast_extractor/`** — otherwise E2 grades the extractor against a copy of itself. Schema: one node per statement (`if`/`elif`→gateway, `for`/`while`→loop, `return`→return, else→block), **deliberately no synthetic merge/exit bookkeeping nodes** (unlike the real extractor, which emits a merge-point node per `if` and an exit-block node per loop) — this was a load-bearing design choice, not an oversight: it's what makes the extractor's bookkeeping-node overhead measurable as a precision gap instead of invisible. Generated gold for all 101 corpus programs.

### X2 — E2: WIR structural accuracy (`eval/e2_structural.py`)

Greedy 1:1 node matching on (type, normalized text), falling back to (type, order-within-type) for near-misses (0 weak matches needed across the whole corpus — the normalization held up); edges matched only when both endpoints matched and direction agrees.

**Result: node P/R/F1 = 0.826/1.000/0.904; edge P/R/F1 = 0.620/0.759/0.683.** 100% node recall — the extractor never misses a gold-recoverable statement. The precision gap is fully explained and *predicted in advance* by X1's design choice: `linear`/`linear_update` programs (no `if`, so no merge-node bookkeeping) score a perfect 1.000/1.000; `conditional`/`conditional_update` programs (which do have `if`) sit at 0.55-0.68 edge F1. The worst-10 list's diagnosis is uniformly "N extra extracted nodes, 0 missing" across every low-F1 program — confirms the merge/exit-node hypothesis directly rather than leaving it as speculation. 10 gold-vs-extracted pairs (seed 42, uids 4/14/15/18/29/32/36/82/87/95) rendered side-by-side in `eval/results/e2_manual_check/` for human eyeballing (~15 min, not yet done by a human as of this writing).

### X3 — E3: certificate score vs code-vs-code correctness (`eval/e3_correlation.py`)

Ground truth (`semantic_diff_rate`) is pure code-vs-code: base and mutant `workflow` executed directly on the same 25 seeded random inputs (locally reimplemented generator, not imported from `RandomizedDifferentialTester`), diffing stub-call sequence + return value. **The WIR never touches this side.** Certificate side reuses `eval/calibrate.py`'s `run_differential_verification` (which does use the WIR — that's the thing being validated).

**Result** (all 429 applicable mutants, 0 execution failures): Pearson r = 0.6238 (95% CI [0.562, 0.678]) between `semantic_diff_rate` and `1 - combined_confidence`; restricted to mutants that aren't behaviorally equivalent to their base (n=318), r = 0.3164 (95% CI [0.214, 0.412]) — weaker once the trivial cases are excluded, but still real and significant. 111/429 mutants (26%) are behaviorally indistinguishable from their base at N=25 (an upper-bound count per the documented N=25 caveat).

**Major finding, verified by reading generated mutant files directly (not just inferred from the rate): `early-return` is 101/101 "equivalent," and it's a `mutate.py` bug, not a hard-to-detect operator.** `op_early_return` inserts its new `return None` at `len(body) - 1` — immediately before the function's existing final statement. Every `eval/flowbench_adapter.py`-generated workflow already ends with a bare `return None` as that final statement, so the mutation fires at the exact point the original already returned: it never cuts off any real logic, just duplicates the terminal no-op as dead code. **This reframes the E1-E4 session's differential-mode calibration finding above** ("early-return sits at 0.431, a genuine measured floor because it's only detectable when a random run reaches the cutoff point") — that explanation was incomplete. The real story: `early-return` mutants are almost all semantically equivalent to their base, so the certificate flagging ~43% of them as `combined_confidence < tau` is largely **false positives on non-buggy code**, not genuine detection of hard-to-reach bugs. Not fixed this session (`eval/mutate.py` explicitly out of scope — this was a pure measurement session); `early-return`'s numbers should not be cited as evidence of detection quality until the operator itself is fixed to actually insert mid-body rather than at the trailing position.

### X4 — wrap-up

This memory update; PR opened stacked on #25 (see PR description for exact number/link).

## Not done in the X1-X4 session (deferred)

Fixing `eval/mutate.py`'s `op_early_return` (the finding above) — **done below, C1-C5**. Getting a human to actually eyeball the 10 `eval/results/e2_manual_check/` files (the report requests this but doesn't self-certify it — still not done as of this writing). Edge-label agreement scoring for E2 (compared only where both sides have a label; not required for the edge match, and not separately reported this session — would need label-normalization work). Everything from prior sessions' "not done" lists remains not done (`visit_Attribute`, collector.py branch-decision emission, wall-clock timeouts, adaptive `n_runs`, `merge_states`).

---

## Correction session (next day): C1-C5, PR #26 same branch, commits `5ed2e98..c3e7bd0`

Mandate: the X1-X4 session's "early-return is a mutate.py no-op bug" finding needed both a fix AND a companion hypothesis test (an inferred root cause for *why* differential mode's numbers looked the way they did, explicitly flagged as unverified in the mandate and gated behind empirical confirmation before touching anything). 179 tests passing.

### C1 — line-shift hypothesis, tested BEFORE fixing anything (gate, not skipped)

`run_differential_verification` derives `branch_lines` from the **base** program's WIR (`_derive_v1_params(base_func_wir)`). `branch_lines` are raw source line numbers; any single-statement insertion/deletion mutation (which is what most operators are) shifts every subsequent mutant line by ±1 relative to the base, so the collector -- which matches on `line_no in self.branch_lines` -- watches the wrong lines in the mutant.

A/B test on 3 real early-return mutants that the pre-correction calibration had flagged (branch_lines from base [status quo] vs. from the mutant's own WIR, oracle WIR and control/state vars unchanged): uid_3 went 0.000 (false flag) → 0.300 (exactly the base's own score); uid_4 went 0.000 → 0.800 (exactly the base's own score); uid_1 was already correct at 0.100 in both. **Confirmed, not refuted** — this is the rare case where the inferred-and-flagged-as-unverified explanation in the mandate held up cleanly on the first test.

### C2 — fix: branch_lines from the mutant's own WIR

`run_differential_verification` now derives `branch_lines` from `functions[function_name]` (the mutant's own extraction, already computed for V3) while keeping the base WIR as the V1 oracle and base-derived `control_variables`/`state_variables` (name-based, so shift-insensitive — changing those *would* reintroduce a real oracle leak). Documented in a code comment as a load-bearing anti-circularity distinction: **where to watch is a property of the code under test's own syntax** (no oracle knowledge needed), **what to expect there must come from the base**. Regression test: a hand-built semantically-equivalent line-shifted mutant (inserted no-op pad statement) now scores within epsilon of its base's own score.

### C3 — fix: op_early_return actually cuts logic

Inserts at a seeded-deterministic random index in `[1, len(body)-2]` (seed = the function's own unparsed source text — deterministic regardless of `PYTHONHASHSEED`), a range that always excludes the trailing position. Inapplicable when body has < 3 statements. `eval/mutate.py` gained `regenerate_operator(operator)` to fix a single operator's mutants without invalidating the other 9's cross-report comparability -- ran it for early-return only: 99/101 applicable (2 short bodies now correctly inapplicable), every other operator's 1010 manifest entries and files byte-identical. Sanity gate (E3's own `semantic_diff_rate`, reused not copied): equivalent mutants dropped from 101/101 to 1/99.

### C4 — corrected three-figure report

Archived the pre-correction differential report, self-mode report, E3 report, and `e3_pairs.csv` (never delete, per the established convention — `eval/results/archive/README.md` explains each). Re-ran E3 fully (C2+C3 applied to every mutant): equivalent-mutant count 111/429 → **11/427**; restricted-to-non-equivalent correlation r improved 0.316 → **0.649** (the old large equivalent cluster near the origin was diluting the real signal, not strengthening it -- worth remembering next time a "the more data the better" instinct says otherwise). Re-ran self-mode: early-return now correctly 0/50 detected (was 0.059 by noise before the fix) — consistent with, not contradicting, the self-referential-oracle limitation.

New `eval/calibrate_corrected.py` replaces the single conflated "detection rate" with three figures, joining E3's per-mutant `semantic_diff_rate` (ground truth) against the certificate score:

1. **Genuine-bug detection** (semantic_diff_rate > 0): **0.9286** (95% CI [0.885, 0.959], n=210) — was 0.8636 conflated.
2. **Equivalent-mutant specificity** (semantic_diff_rate == 0): **0.1111** (95% CI [0.003, 0.482], n=9) — investigated directly rather than left as a scary bare number: 8/9 score *exactly* identical to their own base's score (proving no residual line-shift artifact — an equivalent mutant correctly inherits its base's own false-alarm status when n is this small and clustered on ~5 distinct bases), and the 1 exception is a documented false negative in E3's *ground truth* (a `None`-comparison guard the local string-pool input generator can never trigger — E3's own N=25 caveat, not a certificate bug).
3. **False-alarm rate on untouched bases**: **0.0588** (unchanged from before either fix — expected, since bases were never mutated).

tau (0.0999, J=0.8532) selected on CALIB using only genuinely-buggy mutants as positives and bases as negatives — equivalent mutants excluded from *selection*, not just from the headline figure. Per-operator (genuine class only): 7/8 operators at 0.57-1.0; `constant-perturb`'s 0/9 matches D3's prior "value-only mutation" finding (still needs a branch-decision field on the real collector, still out of scope), not a new surprise.

### C5 — wrap-up

This memory update. `eval/results/e3_correlation_report.md`'s early-return section auto-updates to a RESOLVED status now that the underlying condition (99/99 equivalent) no longer holds (the report generator checks the live count, not a hardcoded flag).

## What this means for the thesis, final state

The corrected numbers are the ones to cite: **genuine-bug detection 0.929, false-alarm 0.059**, both with pre-registered 95% CIs, on differential-mode verification against a real published benchmark (FLOW-BENCH) across 8 mutation operator classes with actual applicable mutants. E2's structural accuracy (node F1 0.904) is unaffected by any of this (base programs never changed) and stands independently. The correction trail itself (T1→D-session→E-session→X-session→C-session, each finding sharper than the last, each verified before being acted on) is worth keeping as thesis methodology narrative, not just as a memory artifact — it's a live demonstration of iterative empirical verification catching its own earlier mistakes.

## Not done in the C1-C5 session (deferred)

Getting a human to eyeball the E2 manual-check files (still outstanding). Fixing `constant-perturb`'s low genuine-bug detection (needs collector.py branch-decision emission — explicitly out of scope, gated on data same as before, and the data still says this isn't urgent since only 1/8 operators is affected). Everything else from every prior session's "not done" list remains not done.

---

## Mechanical-fixes session (2026-07-06): F1 (WIR bookkeeping-node contraction) + F2 (collector branch decisions), branch `fix/mod2/bookkeeping-and-branch-decision` off `develop` (PRs #25/#26 already merged)

Mandate: the human finally did the E2 manual-check eyeball (`eval/results/e2_manual_check/VERDICT.md`, 10/10 PASS — confirmed every precision-gap node is bookkeeping, zero genuine extraction errors) and gave two mechanical fixes to implement, each gated on its own measurement instrument.

### F1 — WIR bookkeeping-node contraction (`src/ast_extractor/cfg_extractor.py`)

Post-construction graph-contraction pass (`contract_bookkeeping_nodes`), **not** a visitor rewrite — the merge/exit-block creation sites in `visit_If`/loop visitors/`visit_Try`/`visit_TryStar`/`visit_Match` are untouched (load-bearing during construction, e.g. `visit_Try`'s finally-clause rerouting). Removes any post-construction node that is a plain "block" with no code and no guard and isn't the graph's entry/exit, rewiring predecessors directly to successors and merging edge labels (conflict → node left uncontracted, tracked in `_bookkeeping_contraction_skipped`).

**E2 instrument (before → after):** node P/R/F1 0.8255/1.0000/0.9044 → **1.0000/1.0000/1.0000**; edge P/R/F1 0.6204/0.7589/0.6827 → **1.0000/1.0000/1.0000**, across all 101 corpus programs, zero new V3 abort-gate failures, differential calibration numbers unchanged (task events don't ride on blank nodes — proves F1 doesn't touch V1/V2 behavior). Pre-F1 report archived at `eval/results/archive/e2_structural_report_pre_bookkeeping_contraction.md` / `e2_per_program_pre_bookkeeping_contraction.csv`.

### F2 — actual-side collector gains a branch decision (`src/dynamic_tracer/collector.py`)

D3 (prior session) made the comparator decision-aware **only when every branch_point event on both sides carries `taken_branch`** — but the real collector never emitted it, so this pathway was a permanent no-op for real traces (see the note at the C1-C5 section above and D3's own commit). F2 closes that gap:

- **Observation-layer derivation** (`main.py:_derive_branch_arms`): for each gateway/loop node in the code-under-test's own WIR, walks `successors[0]`/`successors[1]` (recursing through any node with no code of its own) to the first real source line each arm reaches — `{branch_line: (true_line, false_line)}`. Threaded through `_derive_v1_params` → `run_v1_pipeline` → `RandomizedDifferentialTester` → `WIRTraceCollector` as a new optional `branch_arms` param (default `None`/`{}`, fully backward-compatible — every existing call site and test needed zero changes). In differential mode (`calibrate.py`), sourced from the **mutant's own WIR**, mirroring C2's `branch_lines` precedent exactly (WHERE to watch is a property of the code under test; only WHAT to expect must come from the base).
- **Monitoring backend**: wires `sys.monitoring.events.BRANCH`. On each BRANCH event, maps `instr_offset`/`destination_offset` to source lines via `code.co_lines()` (cached per code object) and compares the destination line against `branch_arms`. Only acts when it lands exactly on one arm's line — a compound condition (`a and b`) or a for-loop's own "continue iterating" case can produce a BRANCH event whose destination is still on the branch's *own* line (ambiguous), and those are deliberately left pending.
- **Both backends** share one fallback (`_resolve_pending_branch`, keyed by `id(frame)`): whatever line that frame executes *next* resolves any pending branch. This is the *only* mechanism settrace has (no BRANCH event exists there), and it's what makes the two backends converge by construction rather than by coincidence — BRANCH is a same-frame optimization on top of a fallback both paths share, not a separate code path that could drift out of parity with the other.
- Field name is `taken_branch` (not `taken`, as the mandate's prose loosely said) — matches the comparator's `_both_sides_have_taken`/`_normalise` exactly, which already expects that name from the reference interpreter's side.

**Parity verification** (advisor flagged this as the one gap after initial self-review: the corpus-wide calibration only ever exercises the monitoring backend on Python 3.13, so "parity preserved" was resting on reasoning, not measurement, for real corpus bytecode shapes — compound conditions, elif chains, for-loops, one-armed ifs): wrote a one-off script (not committed — scratchpad) that runs both backends over all 101 base programs plus every negate-guard/constant-perturb mutant plus a random 30-mutant sample (184 programs × 6 random-input runs each), diffing `taken_branch` sequences. **Zero mismatches.** Also confirmed directly that a real base-program trace carries non-None `taken_branch` on every branch_point (not just synthetic test cases). `tests/test_dynamic_tracer_parity.py` gained a `branch_arms`-populated case (`branch_decision_if_else_in_loop`) plus a dedicated `test_branch_decision_populated_on_both_backends` asserting the field is actually present (not just equal-because-both-empty) and matches the exact expected True/False sequence for a known input. `tests/test_dynamic_tracer.py`'s `TestDifferentialComparator` gained `test_branch_decision_via_real_collector`, running the real collector (not hand-built traces) through the comparator end-to-end.

**Acceptance instrument (differential calibration, before → after — archived at `eval/results/archive/calibration_report_differential_pre_branch_decision.md`, `e3_pairs_pre_branch_decision.csv`, `e3_correlation_report_pre_branch_decision.md`):**

- Youden's J: 0.8532 → **0.9017**
- Genuine-bug detection: 0.9286 → **0.9571** (n=210)
- `negate-guard` detection: 8/14 → **14/14** — exactly the mandate's predicted win (a negated guard flips the branch decision on nearly every run; D3's pathway now catches it directly instead of needing the mutation to also perturb the task-call sequence).
- `constant-perturb`: stayed **0/9 in this EVAL split** despite `combined_confidence` measurably moving (0.8 ceiling → 0.32 floor for affected mutants, checked directly in `e3_pairs.csv`, not inferred) — it just doesn't cross tau=0.1000, since the mutated literal only diverges the branch decision on a fraction of `n_runs`, not all of them (unlike guard-negation's near-100% divergence). Reported as a genuine partial improvement, not force-fit into "now detected."
- False-alarm rate (untouched bases) and equivalent-mutant specificity: unchanged (0.0588, 0.1111/n=9) — required by the mandate, confirmed.
- **E3 side effect, investigated not rationalized:** Pearson r dropped 0.4359 → 0.3653 (full corpus), 0.6493 → 0.5326 (restricted); Spearman rho dropped 0.6774 → 0.5212, 0.7632 → 0.5784. Root cause confirmed by diffing `e3_pairs.csv` pre/post: F2 makes `combined_confidence` saturate (many negate-guard mutants collapse to exactly 0.0 regardless of `semantic_diff_rate` magnitude, previously graded 0.1-0.32) — a sharper pass/fail detector trades away gradedness, which is exactly what this correlation measures. The ground-truth side is untouched (E3's equivalent-mutant table is byte-identical, 11/427, same per-operator breakdown pre/post), confirming the shift is entirely on the certificate side F2 touched, not a code-vs-code ground-truth regression.
- `eval/threshold.json` re-frozen: `tau=0.09999999999999998, youdens_j=0.901747572815534`.

**How to apply:** if `constant-perturb` detection needs to actually cross tau, the lever is the input generator (more `n_runs`, or inputs biased to reliably hit the mutated literal), not the collector — F2 already gives the signal a measurable amount of lift, it's just not enough at the current `n_runs=10` operating point. If the correlation-vs-detection tradeoff ever needs discussing in the thesis, cite the three-figure calibration numbers as the ones that matter for "does this catch bugs," and the r/rho drop as a separately-explained, expected side effect of the detector becoming sharper — not evidence the certificate regressed.

## Not done in the F1/F2 session (deferred)

`visit_Attribute`, typed per-layer `/verify` statuses, wall-clock timeout, `merge_states` wire-or-excise, adaptive `n_runs`, multi-implementation corpus — none of these were in scope per the mandate. Raising `constant-perturb`'s detection past tau (needs input-generator work, not collector work, per the note above) is now the most clearly-scoped remaining gap in the mutation-detection numbers.

**V2-masking caveat (known open item, not an F2 defect):** on a stub-free scalar workflow, V2 stays self-referentially active (`v2=0.5`, no oracle) and the OR-composition (`combined = 1-(1-v1)(1-v2)`) floors `combined_confidence` at V2's own confidence even when V1 detects with total certainty. The corpus's negate-guard mutants only reach the clean 0.0 floor demonstrated above because their container-typed inputs make V2 bail (`v2=0` → `combined=v1`) — see `eval/test_calibrate.py::test_value_only_guard_mutation_now_detected`'s explanatory comment, added this session as the regression test for F2. Discounting V2's contribution to the composition in differential mode (where V1 already has a real oracle and doesn't need V2's self-referential backstop) is backlog, not done here.

## Wrap-up session (2026-07-06): verification + PR only, no code changes

Re-ran the full mandate as a closing check on the F1/F2 branch (`fix/mod2/bookkeeping-and-branch-decision`, commits `7c6e21e`→`191eb2c`, then `8e6dd69` GitNexus count sync 7659→7706 symbols/12631→12703 relationships from this session). `npm gitnexus analyze` was stale after `191eb2c`'s own doc edit; re-ran once more post-commit and it settled with no further tracked-file changes (index metadata isn't git-tracked). 188/188 tests passed including `tests/test_dynamic_tracer_parity.py` (10/10). Confirmed both eval reports byte-match the mandate's cited numbers exactly (`eval/results/calibration_report_differential.md`: detection 0.9571 [0.920,0.980], J=0.9017, false-alarm 0.0588, negate-guard 14/14, constant-perturb 0/9; `eval/results/e2_structural_report.md`: node/edge P/R/F1 all 1.0000, pre-contraction 0.8255/1.0000/0.9044 node and 0.6827 edge F1). No regeneration was needed or performed — these are the already-committed artifacts. PR opened to `develop` with both before/after tables, the M03 note on blank-node removal, and this V2-masking paragraph plus the two-session-collision reconciliation note.

## Session A (2026-07-07): A1 (differential composition) + A2 (deterministic literal coverage), branch `fix/mod2/differential-compose-and-perturb` off `develop`

Mandate: fix the two instrument-facing backlog items named at the end of the F1/F2 session (V2-masking caveat above, and constant-perturb's undetected-for-a-sampling-reason status) before the next session's multi-implementation corpus measures anything with this instrument. Both fixes landed; 190 tests passing (was 188, +2 new).

### A1 — differential verdict = V1 only (`eval/calibrate.py::run_differential_verification`)

`combined_confidence` is now set directly to `v1_confidence` in differential mode (composer's OR-formula result is computed first for `passed`/`message`/`v3_abort` bookkeeping, then `combined_confidence` and, when V3 hasn't aborted, `passed`/`message` are overridden). `v2_confidence` stays in the returned cert as telemetry. Self-mode (`main.py::_run_verification`, `composer.py`) is untouched — verified by direct comparison against a clean pre-session worktree on three corpus programs (uids 4, 14, 98, all with `str` guards): v1/combined identical pre/post, confirming self-mode's oracle (re-derived from the mutant itself, so matching≈always-1) doesn't depend on input order at all. `eval/test_calibrate.py::test_value_only_guard_mutation_now_detected` (the F2-era regression test whose docstring explicitly deferred this) now asserts `combined_confidence < 0.10` directly instead of only `v1_confidence < 0.10`.

### A2 — round-robin string pool + base-guard-literal seeding (`src/dynamic_tracer/randomized.py`)

Added `extract_guard_string_literals(source)` (module-level, the same `ast.Compare` walk D1's `_extract_string_pool` already did) and an `extra_str_literals` constructor param on `RandomizedDifferentialTester`, threaded through `run_v1_pipeline`/`run_v2_pipeline`'s sibling `pipeline.py`. `calibrate.py::run_differential_verification` gained an optional `base_source` param and passes `extract_guard_string_literals(base_source)` as `extra_str_literals` — the base's own guard literals (e.g. `"high"` for a mutant whose pool is only `"high_MUTATED"`) get unioned in. Sampling changed from pure `random.choice` to a shared `self._pool_queue` that's drained (each distinct pool literal returned once, in sorted order) before falling back to the original uniform-random-plus-junk behavior — deterministic under the existing seed, applies unconditionally (not just when `extra_str_literals` is passed), including self-mode (confirmed a no-op there per A1's note above).

### Acceptance instrument (differential calibration, before → after — archived at `eval/results/archive/calibration_report_differential_pre_a1a2.md`, `e3_pairs_pre_a1a2.csv`, `e3_correlation_report_pre_a1a2.md`):

- Youden's J: 0.9017 → **0.9600**
- Genuine-bug detection: 0.9571 → **0.9952** (n=210)
- `constant-perturb` detection: 0/9 → **8/9**. The 1 remaining straggler (uid_4's `'urgent'`→`'urgent_MUTATED'`, checked directly) is *not* the numeric-literal case anticipated going in — the guarded value (`issue['priority']`) is a dict field fed by **two** independent `str` params sharing one pool-wide round-robin queue; with a 2-literal pool and 2 params the queue drains entirely on run 1 (guaranteeing exactly one divergent run), and the other 9 runs revert to uniform random per-param, rarely re-hitting either literal (`v1_confidence` lands at 0.36, well above tau). Real backlog item: per-guard-site literal coverage instead of one function-wide queue — not the numeric-literal gap the mandate pre-named.
- **Honest-risk clause outcome: false-alarm rate did NOT rise** — unchanged at 0.0588 (n=51), verified via clean pre-session worktree comparison (not just re-reading the aggregate number): `v2_confidence` is **0.0 for every one of the 101 base programs** in this container-heavy FLOW-BENCH corpus (same root cause as the negate-guard mutants' clean 0.0 floor noted in the F2 section above — container inputs make V2 bail). Since V2 already contributed zero OR-composition padding to this corpus's negative class before A1, removing it had nothing to take away. A1's masking risk is real (demonstrated directly by the regression test) but specific to stub-free/scalar-input programs, which this container-heavy corpus doesn't contain — so the risk named in the session mandate didn't manifest here. This is a property of *this corpus*, not evidence the risk was overstated; the multi-implementation corpus planned for Session C should include stub-free/scalar styles precisely so this gets tested for real.
- E3 correlation *recovered* rather than dropping further: Pearson r 0.3653→0.4085 (full), 0.5326→0.5580 (restricted); Spearman rho 0.5212→0.5400 (full), 0.5784→0.5988 (restricted). A1 removes a saturating term, A2 restores graded signal specifically for `constant-perturb` (previously flattened to F2's 0.32 floor) — ground truth (11/427 equivalent) is byte-identical, confirming the shift is entirely certificate-side.
- `eval/threshold.json` re-frozen: `mode=differential-corrected, tau=0.1, youdens_j=0.96, seed=1234`.

**How to apply:** the differential harness's composition and input-generation backlog items from the F1/F2 session are both closed. The next open item in this family is per-guard-site (not per-function) literal coverage, named above — low priority, affects exactly 1/427 mutants measured so far. Session C's multi-implementation corpus (stub-free/scalar styles specifically) is the right place to actually stress-test A1's honest-risk clause, since this session's corpus structurally couldn't trigger it.
