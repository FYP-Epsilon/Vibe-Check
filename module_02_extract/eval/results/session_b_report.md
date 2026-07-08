# Module 02, Session B: Final Engineering Batch (Return-Value Observable + Robustness)

Branch `fix/mod2/robustness-batch` off `develop`, worked in a separate
worktree (`Vibe-Check-sessionB`) per the session mandate. Baseline: 228
tests passing (`tests/` + `eval/`, pre-session). This report closes the
session: B1-B5 done and green; B6 explicitly skipped as the named
leftover, per the mandate's own escape hatch ("if any earlier task ran
long, skip and write as the single named leftover instead") -- B3's
wall-clock-timeout task ran long (a real CPython GIL/threading
investigation, detailed in its own section below).

## B1 -- Return-value observable in V1 traces (the headline)

**Why**: Session D's `eval/results/cross_impl_mode_report.md` diagnosed
all 6 remaining strict-mode logic-class misses on the natural-bug
corpus as return-value-only divergences -- an identical stub-call
sequence on both sides, differing only in the function's final return
value. V1 traces never observed return values in either comparison
mode before this session, so this class of bug was structurally
invisible regardless of comparison mode.

**Design**: actual side (`src/dynamic_tracer/randomized.py`'s
`_run_actual`) captures the real Python call's return value and
appends a synthetic `return_value` trace event, canonicalised the same
way as everywhere else (`_make_hashable`). Expected side
(`src/dynamic_tracer/interpreter.py`'s `WIRReferenceInterpreter`) now
actually executes `return`-type WIR nodes instead of silently
SyntaxError-ing on `exec("return x")` -- parses the statement, evaluates
the expression via `_safe_eval` into `state["__return__"]`, and emits a
matching `return_value` event on completion (fall-through emits `None`,
matching Python's own implicit-return semantics). The comparator
(`src/dynamic_tracer/comparator.py`) includes `("return_value", value)`
in the normalised sequence in **both** modes -- a return value is
behavior, not branch structure, so unlike `branch_point` it is not
dropped in `task_only` mode.

**Graceful-degrade false-alarm guard**: if the reference interpreter
can't evaluate a return expression, no `return_value` event is emitted
on that side, and `_both_sides_have_return` symmetrically excludes
return-value comparison for that run entirely -- the reference
interpreter never fabricates a value it didn't actually compute. Skips
are counted (`return_value_skips` in the V1 certificate) rather than
silently absorbed.

**Two latent bugs found and fixed as a prerequisite for B1's own
correctness** (not scope creep -- both were required for return values
to be observed at all):

1. `WIRReferenceInterpreter.execute()`'s loop stopped *before*
   processing a node once `current == exit_node`, but the CFG extractor
   makes a function's final bare `return` statement's node the graph's
   own `exit_node` in the common case -- so that terminal, most-common
   case's return value was never evaluated, always silently returning
   `None`. Fixed: only a non-`return`-type exit sentinel still stops
   before processing.
2. `_run_expected`'s task_entry/task_exit wrapping ran *after* the
   interpreter had already appended `return_value` as the trace's last
   event, placing it before `task_exit` on the expected side -- but the
   actual side always has it after `task_exit` (the real collector's
   `task_exit` fires synchronously during the call; `_run_actual`
   appends `return_value` only once the call returns). Since the LCS
   comparator is order-sensitive, this caused spurious `<1.0`
   similarity for behaviorally-identical traces. Fixed by extracting
   `return_value` events before wrapping and re-appending them last on
   both sides.

### Instrument gate 1 -- natural-bug corpus, strict mode

All 6 previously-diagnosed misses individually re-checked:
`33__qwen3-next-80b`, `35__qwen3-next-80b`, `38__qwen3-next-80b`,
`42__qwen3-next-80b`, `49__qwen3-next-80b`, `68__llama-3.1-8b` -- every
one now scores `combined_confidence = 0.0` (detected).

| | before (Session D, PR #31) | after (B1) |
|---|---|---|
| Detection rate (all) | 0.9634 (158/164) | **1.0000 (164/164)** |
| exception-class | 1.0000 (96/96) | 1.0000 (96/96) |
| logic-class | 0.9118 (62/68) | **1.0000 (68/68)** |

### Instrument gate 2 -- natural-bug corpus, task_only mode

| | before (Session D) | after (B1) |
|---|---|---|
| Detection rate (all) | 0.8841 (145/164) | **0.9329 (153/164)** |
| exception-class | 0.9583 (92/96) | 0.9688 (93/96) |
| logic-class | 0.7794 (53/68) | **0.8824 (60/68)** |

C5b (implementation-freedom specificity, regression check): task_only
false-alarm rate **unchanged** at 0.10 (2/20) -- identical flagged
variants (`1__mixtral-8x7b`, `42__llama-3.1-8b`) and identical
divergence breakdowns to pre-B1. No regression.

### Instrument gate 3 -- full strict mutation calibration

| | before (Session A, frozen) | after (B1) |
|---|---|---|
| tau | 0.1000 | 0.1000 |
| Youden's J | 0.9600 | 0.9600 |
| Genuine-bug detection | 0.9952 | 0.9952 |
| False-alarm rate | 0.0588 | 0.0588 |

Byte-identical to Session A's frozen numbers, including the
per-operator table (`constant-perturb` 8/9, all others unchanged).
`threshold.json` was **not** re-frozen -- the calibration procedure
itself re-selects the identical tau, so per the mandate there was
nothing to update.

C5b strict (regression check): false-alarm rate unchanged at 0.25
(5/20) -- identical flagged variants and divergence breakdowns to
pre-B1.

### E3 checked, not assumed: correlation is unchanged, and why

The combined re-run at the end of this session (see below) includes a
full E3 re-run (`eval/e3_correlation.py`, all 427 mutant/base pairs
recomputed from scratch). It came back **byte-identical** to the
pre-B1 archived copy: Pearson r = 0.4085 (0.5580 restricted), Spearman
rho = 0.5400 (0.5988 restricted), 11/427 equivalent mutants. This
corpus's mutation operators directly perturb control flow, so in
strict mode a genuine bug almost always already diverges on
task-sequence or branch-decision before return value would ever be the
deciding channel; an equivalent mutant's return value agrees along
with everything else. B1's leverage is specific to the natural-bug
cross-implementation corpus, where two independently-written
implementations can share identical branch structure and task
sequence while differing only in the returned value -- a divergence
class that essentially does not arise from mutating one program's own
control flow. See `eval/results/e3_correlation_report.md`'s "unchanged
after Session B" section and `eval/results/archive/README.md` for the
full write-up.

### Tests

14 new tests in `tests/test_dynamic_tracer.py`: interpreter-side return
evaluation (evaluated value, bare return, fall-through, unevaluable
expression graceful-degrade, exit-node-as-return-node, non-return exit
sentinel still not executed), comparator-side (matching/divergent
return values in both modes, task_only keeps return_value unlike
branch_point, symmetric exclusion when one side lacks the event),
tester-side (actual emits the event, end-to-end return-value-only
divergence detected, graceful-degrade produces no false alarm). One
pre-existing test (`test_linear_execution`) updated: it asserted an
empty trace for a function with no observable statements, which is no
longer true now that a `return_value` event is always emitted.

Commit: `c66b44f feat(mod2): return-value observable in V1 traces (B1)`.

## B2 -- Typed per-layer `/verify` statuses

`src/main.py`'s `_run_verification` restructured so each phase (V3,
compile, V2, V1) runs in its own try/except and contributes a `layers`
key: `{"v3": {"status": "OK"|"ERROR"|"SKIPPED", "reason": str|null},
"v2": {...}, "v1": {...}}`. A fatal earlier-phase failure marks later
phases `SKIPPED` with the upstream reason attached rather than leaving
them silently absent; the existing top-level `passed`/`message`/etc.
keys are unchanged, `layers` is purely additive to the `/verify` wire
format. The outer catch-all exception handler (last resort, should
rarely fire) mirrors the same shape with everything `ERROR`.

4 new tests in `tests/test_integration.py`
(`TestTypedLayerStatuses`): syntax error -> v3 ERROR, v2/v1 SKIPPED;
happy path -> all OK; a V2-bail case (a dynamic dict-key subscript that
defeats static container seeding) carries the real bail message in
`layers.v2.reason`; no functions in source -> v3 ERROR.

Commit: `b6c9924 feat(mod2): typed per-layer /verify statuses (B2)`.

## B3 -- Wall-clock timeout

`_run_verification` now runs under a `ThreadPoolExecutor(max_workers=1)`
+ `future.result(timeout=VERIFY_TIMEOUT_S)` (env override, default 30s,
read once at import time as a module attribute so tests can
monkeypatch it directly). On timeout, returns the same typed `layers`
shape with `status="ERROR", reason="wall-clock timeout"` on every
layer.

**This task ran long because of a genuine, empirically-verified CPython
nuance the mandate's own example did not anticipate**: the mandate
names `pow(10, 10**8)` -- a single long C-level statement -- as the
motivating hang case. Direct testing (an isolated debug script, then
the real test harness) showed this mechanism does **not** actually
bound that case. `future.result(timeout=)` only wakes promptly for a
**GIL-releasing** hang (an infinite Python bytecode loop, which yields
the GIL at periodic safepoints -- confirmed directly with `while True:
pass`, interrupted at ~0.22s for a 0.2s timeout). A **GIL-monopolizing**
single C-level statement with no such safepoint (confirmed directly: a
big-integer `**` of comparable size holds the GIL for its whole ~5s
runtime) blocks `future.result()`'s own timeout check for as long as
that statement runs -- once it completes and releases the GIL,
`future.result()` returns the call's real, late result **normally**,
not a `TimeoutError`, because the call did in fact finish; `timeout_s`
was never actually enforced against it. If such a statement ran
forever rather than merely a long time, this wrapper would hang
forever too, silently reproducing the exact failure mode it exists to
prevent.

Stated honestly in `_run_verification_with_timeout`'s docstring rather
than papered over: a thread-based timeout cannot preempt a
GIL-holding call in CPython; only process-based isolation
(`multiprocessing` + `Process.terminate()`) can, and that's out of
scope for this session -- named here as the honest leftover rather than
silently claimed as covered. Two limitations are now documented: (1)
the worker thread cannot be killed, only orphaned (existing, from the
original design); (2) the boundary above -- GIL-releasing hangs are
bounded close to `timeout_s`, GIL-monopolizing ones are not bounded at
all.

Tests exercise the case this design can actually bound: a
`threading.Event`-based hang (GIL-releasing, like the real
infinite-loop case), monkeypatched in place of `_run_verification` and
released immediately after assertions so the orphaned worker thread
doesn't leak into `concurrent.futures`' atexit join and hang the test
suite at shutdown (confirmed directly during development with a
`while True: pass` variant, which does exactly that). A
GIL-monopolizing hang was deliberately **not** used as a test input --
no assertion of "typed timeout response" can honestly be made against
it, since the implementation, as specified, doesn't produce one for
that case.

Commit: `659b5e3 feat(mod2): wall-clock timeout for /verify (B3)`.

## B4 -- `merge_states` excise (thesis honesty)

`merge_states`, `qce_predicts_savings`, `_reachable_from`, and the
never-appended `state_pool` field in
`src/z3_sym_engine/concolic.py`'s `BoundedConcolicEngine` were an
earlier design for QCE (Query Count Estimation) state merging that was
never wired into the actual exploration loop -- exercised only by their
own unit tests. Confirmed via `gitnexus_impact` (upstream, each
target): LOW risk, zero production callers, zero affected execution
flows for all three methods; `state_pool` isn't even an indexed symbol
(never read anywhere but its own initialization).

Deleted, not commented out or kept as an unused capability -- this is a
thesis-honesty fix, not a cleanup. The class docstring now states
exactly what the engine does: k-bounded unrolling + branch-negation
concolic exploration + container seeding, controlled by `max_k` and a
query budget, not by state merging. Historical mentions in
`docs/module02/*.md` are left alone per the mandate -- they document
what was tried, not what ships. The 3 tests for the removed methods
(`test_merge_states`, `test_qce_cold_variables`, `test_qce_hot_variables`)
were deleted alongside them.

Commit: `fff3155 fix(mod2): excise dead QCE state-merging code from BoundedConcolicEngine (B4)`.

## B5 -- n_runs justification

Comment-only change in `src/main.py`, no behavior modified. Explains
why `n_runs` controls input-space coverage, not detection confidence:
since F2 (branch decisions) and B1 (return values), a single V1 run's
comparator now observes every behavioral surface this design covers
(task/branch sequence, exception type, branch decision in strict mode,
return value), so a divergence on any one run already drags that run's
result to "not passed" regardless of how many other runs happened to
agree -- detection does not hinge on `n_runs` being large. What
`n_runs` actually buys is the chance a rare guard-controlling input
gets sampled; the known n-sensitive case is the constant-perturb
straggler (uid_4, documented in
`eval/results/calibration_report_differential.md`), whose two
independent `str`-parameter guards need more than one round-robin
drain to force-cover both.

Commit: `caa2911 docs(mod2): explain why n_runs controls coverage, not detection confidence (B5)`.

## B6 -- SKIPPED (named leftover)

Per-guard-site literal coverage (the uid_4 straggler from B5's note)
was the mandate's explicitly lowest-priority, explicitly skippable
item ("only if everything above is green" / "if any earlier task ran
long, skip and write as the single named leftover instead"). B3's
GIL/timeout investigation ran long. Not attempted this session --
`RandomizedDifferentialTester`'s round-robin literal queue
(`randomized.py`'s `_pool_queue`) is shared across a function's `str`
parameters rather than being per-guard-site, so a guard fed by two
independent string parameters can take more than one `n_runs` budget
to force-cover both sides. B5's comment names this as the known
n-sensitive case; fixing it (and re-running the mutation calibration
under the same FA-regression gate the rest of this session used) is
the concrete next-session starting point.

## Combined re-run

Run at the end of this session, after B1-B5, to confirm nothing in
B2-B5 moved a number on the eval path:

| check | before (B1's own gate, mid-session) | after (post-B2-B5, this re-run) |
|---|---|---|
| Full strict calibration: tau | 0.1000 | 0.1000 |
| Full strict calibration: J | 0.9600 | 0.9600 |
| Full strict calibration: detection | 0.9952 | 0.9952 |
| Full strict calibration: FA | 0.0588 | 0.0588 |
| C5c strict: detected | 164/164 | 164/164 |
| C5c task_only: detected | 153/164 | 153/164 |
| C5b strict: FA | 5/20 | 5/20 |
| C5b task_only: FA | 2/20 | 2/20 |
| E3: Pearson r (full) | (not yet run at B1's gate) | 0.4085 -- byte-identical to pre-B1 |
| E3: Spearman rho (full) | (not yet run at B1's gate) | 0.5400 -- byte-identical to pre-B1 |

All byte-identical to B1's own instrument-gate numbers. This is
expected, not just hoped for: B4 deleted code that was never in the
production pipeline; B5 is a comment; B3 wraps `verify()`, which none
of the eval scripts call (they call `run_v1_pipeline` /
`run_differential_verification` / the pipeline functions directly,
bypassing the FastAPI layer entirely). `threshold.json` was not
touched. `eval/variants/`, gold WIR, and admission verdicts were not
touched.

`eval/results/e3_pairs.csv` and `e3_correlation_report.md` were
regenerated in full (not resumed) to make sure this claim was checked,
not assumed -- see the E3 section under B1 above and
`eval/results/archive/README.md`'s new entry for the detail.

## Suite status

246/246 tests passing (`tests/` 162 + `eval/` 84 -- 3 fewer than the
249 at B3 due to B4's 3 deleted tests for deleted methods).
`gitnexus_detect_changes` run before every commit in this session;
every change registered LOW risk with zero affected execution flows.

## Known open items (carried forward, not fixed this session)

- **B6, per-guard-site literal coverage** (named leftover above).
- **B3's GIL-monopolizing-hang gap**: a thread-based timeout cannot
  bound a single uninterrupted C-level statement in CPython; closing
  this needs process-based isolation (`multiprocessing` +
  `Process.terminate()`), out of scope here.
- **V2-masking in self-mode** (carried from the F1/F2 wrap-up session,
  unaffected by this session): `/verify`'s self-mode composition is
  still the standard OR-composition `1-(1-v1)(1-v2)`; only differential
  mode uses the A1 fix (`combined_confidence = v1_confidence`).
- **Constant-perturb backlog is now precisely diagnosed** (B5/B6):
  root cause is the round-robin queue being function-wide, not
  per-guard-site.
