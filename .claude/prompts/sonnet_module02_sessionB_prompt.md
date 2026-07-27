# SESSION MANDATE — Module 02, Session B: final engineering batch (return-value observable + robustness)

You are running the **last planned code session** for VibeCheck's Module 02 (`C:\Research\FYP\Vibe-Check`). Everything through Session D is merged to `develop` and `main`. This session has one measurement-improving headline (B1, promoted by Session D's 6-miss diagnosis) and four robustness/honesty items. After it, Module 02 is code-complete and the remaining work is thesis text.

**Branch**: `fix/mod2/robustness-batch` off `develop`. Baseline: **228 tests passing**.

## B0 — Housekeeping first (main repo tree)

1. Switch the main working tree from the stale `feat/mod2/multi-impl-corpus` branch to `develop`; pull.
2. `git worktree remove C:/Research/FYP/Vibe-Check-sessionD` (its PR #33 is merged) and remove its duplicate GitNexus index entry; also remove the stale `pr-21-review` worktree listed by `git worktree list` (temp-scratchpad path).
3. Delete merged local branches. Then `npx gitnexus analyze` and commit any AGENTS.md/CLAUDE.md count sync.

## Ground rules

- `CLAUDE.md` GitNexus workflow (impact analysis before every symbol edit — B1 and B4 touch heavily-connected code, expect HIGH); suite green after every task incl. `tests/test_dynamic_tracer_parity.py`; stdlib only.
- `/verify` wire-format: existing keys unchanged; **adding** keys is allowed (B2 adds one).
- Instrument-gated as always: B1 must be proven by the existing eval reports' numbers moving in the diagnosed direction, with archives + before/after tables (7th generation — keep the trail style).
- Report numbers as-is; τ=0.10 stays the primary operating point (re-report J, but re-freeze `threshold.json` only if the calibration procedure itself selects a different τ — flag it loudly if so).

---

## B1 — Return-value observable in V1 traces (the headline)

**Why (verified, Session D)**: all 6 remaining strict-mode logic-class misses on the natural-bug corpus are **return-value-only divergences** — identical stub-call sequence, base falls through returning `None`, variant returns a real value, every one sitting exactly at the τ floor (`eval/results/cross_impl_mode_report.md`, 6-miss table). V1 traces never observe return values, in either comparison mode.

**Design** (keep the collector out of it — no parity risk):
- **Actual side**: in `RandomizedDifferentialTester._run_actual` (`src/dynamic_tracer/randomized.py`), capture the function's return value (currently discarded) and append a synthetic `{"event": "return_value", "value": <canonical>}` as the trace's final event. Canonicalize with the same make-hashable approach already in the class (dicts → sorted tuples, lists → tuples); exceptions keep their existing event, no return event on crash.
- **Expected side**: in `WIRReferenceInterpreter` (`src/dynamic_tracer/interpreter.py`), return-node statements (`return <expr>`) currently go through `_exec_stmt`, where `exec("return x")` is a SyntaxError silently counted in `exec_errors` — handle them explicitly: parse the expression, `_safe_eval` it against state into `state["__return__"]`, and emit the matching `return_value` event when execution ends (falling off the graph without an explicit return ⇒ `None`, matching Python).
- **Comparator** (`src/dynamic_tracer/comparator.py::_normalise`): emit a `("return_value", <canonical>)` tuple in **both** modes — a return value is behavior, not branch structure.
- **Graceful degrade (FA guard)**: if the reference side cannot evaluate a return expression (eval error), emit **no** return event on the expected side and exclude the pair's return tuples from that run's comparison — never fabricate a `None` the reference didn't compute. A fabricated mismatch here is how this feature would create false alarms; count these skips and surface them in the certificate.

**Instrument gates (all three, with before/after tables)**:
1. Natural-bug corpus strict re-run: the 6 diagnosed variants (uids 33/35/38/42/49/68's listed misses) must now be detected; logic-class detection rises from 0.9118 — report the new figure with CI.
2. task_only C5c re-run: logic-class rises from 0.7794 (return values compare in both modes); C5b (20 admitted variants) must NOT regress — admitted variants are behaviorally equivalent *including return values* by admission, so any new C5b flag is a bug in your expected-side evaluation, not a finding.
3. Full strict mutation calibration re-run: FA must not exceed 0.0588; detection may rise (early-return mutants change return values) — report whatever moves.

**Tests**: unit tests for both trace sides emitting the event; comparator both modes; a hand-made return-value-only divergent pair detected end-to-end; graceful-degrade path (unevaluable return expression → no false flag).

## B2 — Typed per-layer `/verify` statuses

**File**: `src/main.py`. The oldest open item (round-3 #7): every failure still collapses into one all-zero response. Wrap each phase (V3 / compile / V2 / V1) in its own try; add a `layers` key to the response: `{"v3": {"status": "OK|ERROR|SKIPPED", "reason": str|null}, "v2": {...}, "v1": {...}}`. Later phases after a fatal earlier failure are `SKIPPED` with the upstream reason; the outer catch-all remains as last resort (everything `ERROR`). `passed` semantics unchanged; existing keys untouched. **Tests**: syntax error → v3 ERROR + v2/v1 SKIPPED; happy path → all OK; a V2-bail case carries its message in `layers.v2.reason`.

## B3 — Wall-clock timeout

**Files**: `src/main.py` (+ small helper). Step counters catch line-loops; a single long-running C-level line (`pow(10, 10**8)`) still hangs the worker. This is Windows (no `SIGALRM`): run `_run_verification` under a `concurrent.futures.ThreadPoolExecutor` with `future.result(timeout=...)`, env `VERIFY_TIMEOUT_S` default 30. On timeout return the typed shape (`layers.*.status="ERROR", reason="wall-clock timeout"`, `passed: false`). **Document the known limitation in a comment**: a truly hung thread cannot be killed and is orphaned — acceptable for a research prototype, stated honestly. **Test**: monkeypatch the timeout to ~0.2s and verify with a single-statement heavy computation (pick one that demonstrably evades the step counter); assert the typed timeout response and that the suite doesn't hang.

## B4 — `merge_states` excise (thesis honesty)

**File**: `src/z3_sym_engine/concolic.py`. `merge_states`, `qce_predicts_savings`, `_reachable_from`, and the never-appended `state_pool` are dead code exercised only by unit tests — presenting them as a live "QCE defense" would be an overclaim. Run `gitnexus_impact` to confirm no production caller (expected: tests only), then **delete** all four plus their tests (`tests/test_z3_sym_engine.py::test_merge_states`, `test_qce_*`), and update the `BoundedConcolicEngine` class docstring to claim exactly what is live: k-bounded unrolling + branch-negation concolic exploration + container seeding. Leave historical mentions in `docs/module02/*.md` alone (they're the finding trail). Commit message must say why (honesty, not cleanup).

## B5 — n_runs justification (note, not code)

Add a short comment block at `src/main.py`'s `V1_RUNS`/`dynamic_n_runs` derivation stating the defense: since F2, a behavioral divergence on ANY single run (branch decision, task sequence, exception, and now return value) drags V1 confidence below τ, so detection does not hinge on n; n controls input-space coverage granularity (`coverage_score`) and the round-robin literal drain (Session A). Cite the constant-perturb straggler as the known n-sensitivity case. One paragraph in the final report mirrors it. No behavior change.

## B6 — Only if everything above is green

Per-guard-site literal coverage (the uid_4 straggler, `src/dynamic_tracer/randomized.py` round-robin queue becoming per-guard-site) with a calibration re-run gate. If any earlier task ran long, skip — write it as the single named leftover instead.

## Re-runs & wrap-up

- One combined re-run at the end: strict calibration + both-mode C5b/C5c + E3 rescore; archive superseded reports with README lines; before/after tables everywhere a number moved.
- Final session report `eval/results/session_b_report.md`: B1 gates with numbers, B2/B3 behavior summary, B4 rationale, B5 paragraph, leftover list (import allowlist = documented boundary; `visit_Attribute` = documented V2 limitation; anything skipped).
- Suite green (228 + new); `gitnexus_detect_changes()`; PR to `develop`: `feat(mod2): return-value observable + robustness batch (final engineering session)` — body: B1 before/after tables, the layers-key addition note for Module 04, B4 honesty paragraph. Append final numbers to the session memory file.

## WHAT NOT TO DO

- Do not put the return event in the collector (parity risk for zero benefit) — tester/interpreter level only, per the design above.
- Do not let B1's expected-side evaluation fabricate return values it couldn't compute — the graceful-degrade rule is the FA guard.
- Do not re-freeze `threshold.json` silently; do not touch E2 artifacts/gold, the variants corpus, or admission verdicts.
- Do not implement the import allowlist or `visit_Attribute` — both are documented boundaries now; changing them post-measurement would desynchronize the published numbers.
- Do not soften B4 into "keep it but comment it" — dead code presented as a defense is the overclaim being removed.

## DEFINITION OF DONE

- B0 housekeeping done (worktrees gone, tree on develop, index fresh).
- The 6 diagnosed return-value misses are detected; logic-class detection > 0.9118 (strict) and > 0.7794 (task_only), C5b not regressed, FA ≤ 0.0588 — all with before/after tables.
- `/verify` returns `layers` statuses; wall-clock timeout works and is tested; `merge_states` family deleted with impact evidence; n_runs note in place.
- Suite green; reports archived + regenerated; PR open; memory appended.
