# SESSION MANDATE — Module 02 Implementation (post round-3 R&D)

You are running an **implementation session** on the VibeCheck FYP repo (`C:\Research\FYP\Vibe-Check`). A completed R&D pass has already verified every claim below against source with file:line evidence — do not re-litigate the findings, but DO re-read each cited location before editing it (line numbers may have drifted). Work on **Module 02 only** (`module_02_extract/`). Modules 01/03/04 belong to teammates — read-only, never edit.

## Ground rules (non-negotiable)

1. **Follow the repo's GitNexus workflow** (see `CLAUDE.md` at repo root): run `gitnexus_impact({target: "<symbol>", direction: "upstream"})` before modifying any function/class; run `gitnexus_detect_changes()` before every commit; never rename via find-replace (use `gitnexus_rename`). If GitNexus warns the index is stale, run `npx gitnexus analyze` first.
2. Create a feature branch off `develop` (e.g. `fix/mod2/verdict-and-eval-corpus`). Do not commit to `develop` directly.
3. The full test suite (`cd module_02_extract && python -m pytest -q`) currently passes **105 tests in <1s**. It must pass (plus your new tests) after every task. Run it after each task, not just at the end.
4. Commit per task (T1, T2, …), conventional-commit style like the existing history (`fix(mod2): ...`, `feat(mod2): ...`).
5. Context docs if you need background: `.claude/memory/round3_verified_findings_2026_07_04.md` (verified current state), `.claude/module02_rd_deliverable.md` (prior R&D), `docs/module02/*.md` (design docs).

## Architecture recap (verified current state)

`POST /verify` in `module_02_extract/src/main.py` runs V3 (static AST → WIR, `src/ast_extractor/`) → V2 (Z3 bounded concolic, `src/z3_sym_engine/`) → V1 (dynamic differential tracing, `src/dynamic_tracer/`), then composes certificates in `src/dynamic_tracer/composer.py` via `combined = 1-(1-v1)(1-v2)(1-v3)`, threshold 0.95.

**The critical bug motivating this session**: `V3Certificate.generate` (`src/ast_extractor/certificate.py:53`) emits `confidence = 1.0` whenever `node_coverage >= 0.95` — i.e. for ANY structurally extractable program, regardless of correctness. With v3=1.0 the product term `(1-v3)` is 0, so `combined = 1.0` and **every parseable program passes**. The verdict is currently vacuous; no evaluation is meaningful until T1 lands.

---

## TASKS (in this exact order)

### T1 — Fix the vacuous verdict (composer recomposition)

**Files**: `src/ast_extractor/certificate.py` (~line 53), `src/dynamic_tracer/composer.py` (lines 17-46), `src/main.py` (lines 193-211).

V3 measures *extraction fidelity*, not correctness, so it must not enter the OR-composition as a correctness signal. Change to:
- `composer.py`: compose the behavioral layers only: `combined = 1 - (1-v1)(1-v2)`. Accept the V3 cert and use it as a **gate**: if `v3_cert["abort"]` is true (or `node_coverage < 0.95`), the result is `passed: False` with message "V3 extraction fidelity below threshold — manual review" regardless of V1/V2. Keep `v3_confidence` in the output dict for transparency but document that it is a fidelity score.
- `certificate.py`: keep computing node/edge coverage; the `confidence` field should be the fidelity value itself (e.g. `node_coverage`), not a saturated 1.0. Grep for downstream readers of `v3_cert["confidence"]` before changing semantics.
- `main.py:197-211`: pass the abort flag through; ensure the wire format still contains `v3_coverage`, `v2_confidence`, `v1_confidence`, `combined_confidence`, `passed`, `message` (Module 04 UI reads these).

**Tests**: update `tests/test_dynamic_tracer.py::TestMultiModalComposer` (`test_combined_formula` at ~line 482, `test_all_high_confidence_passes`, `test_low_confidence_fails`) for the new formula. **Add** `tests/test_integration.py::test_buggy_program_fails`: take the loan-approval program from `test_loan_approval_pipeline` (~line 24), negate one guard (e.g. `>=` → `<`), run the full pipeline, assert `passed is False`. This is the acceptance test for the whole task — a mutated program must be able to fail.

### T2 — One-line bug: `guards.py:88`

**File**: `src/ast_extractor/guards.py:88`: `ast.UnaryOp(op=ast.Not(), value=node)` — the keyword must be `operand=node`. Today this silently produces a malformed node (downstream CNF falls back to "Failed to parse guard into CNF" via the broad except at `src/ast_extractor/pipeline.py:57`); on Python 3.15 it becomes a hard error. Fix the kwarg, then add a regression test in `tests/test_ast_extractor.py` (near the `TestGuardExtractor` cases at ~lines 226-308) asserting that a guard like `not some_call()` produces a non-None CNF and emits no DeprecationWarning (`pytest.warns(None)` pattern or `-W error::DeprecationWarning`). The two DeprecationWarnings currently visible in the pytest summary must disappear.

### T3 — Widen V2 concrete-exec exception handling

**File**: `src/z3_sym_engine/concolic.py:147`. The catch tuple `(TypeError, KeyError, IndexError, AttributeError, ZeroDivisionError)` misses `NameError`, `ValueError`, `RecursionError` — any of those in user code currently propagates to `main.py`'s catch-all (`main.py:220-234`) and zeroes the entire response instead of degrading V2 alone. Add the three types. You will hit `NameError` constantly in T5 (undefined task-API calls), so this must land before the adapter. Add a unit test in `tests/test_z3_sym_engine.py` (near `test_unparseable_guard`, ~line 374): a function whose body calls an undefined name must yield a V2 certificate (confidence 0, no exception), not a crash.

### T4 — Port commit `e4ba019` (container seeding + concrete len)

The commit `e4ba019` ("feat(mod2): seed non-empty containers + concrete len() so V2 explores container paths") lives **only on branch `fix/mod2/phase1-symbolic-hardening` and was never merged**. It patches the *old monolith* `module_02_extract/src/z3_sym_engine.py`, which has since been split into a package — so it cannot be merged; **port it by hand**. View it with `git show e4ba019`.

Port targets:
- `_seed_containers` logic → `src/z3_sym_engine/concolic.py`, `BoundedConcolicEngine.run()` (lines 94-135): synthesize small non-empty values for empty list/dict inputs before the concolic loop — lists get 2 typed scalars; dicts get the string keys the function actually subscripts (discover from the source AST), else generic keys.
- Concrete `len()` → `src/z3_sym_engine/evaluator.py`, `SymbolicEvaluator.visit_Call` (lines 155-164): when the argument container is concrete on the current path, return `z3.IntVal(len(...))` instead of an uninterpreted const. This requires threading concrete state into the evaluator — follow the commit's approach (`concrete_state` threaded through `_eval_symbolic` in `src/z3_sym_engine/tracer.py:233-243`).
- Then the follow-on the commit itself flags: in `_emit_certificate` (`src/z3_sym_engine/concolic.py:454-506`) add a coverage-credit term so pure-container functions with real branch coverage don't stay at confidence 0. Current formula (line ~461): `(feasible/total)*(1-timeout_rate)*solver_rate` — solver_rate is 0 when there are no scalar inputs to re-solve. Suggested: blend in `branch_diversity_score` (already computed, lines 463-477) when `solver_rate == 0` but `covered_edges >= 2`, e.g. `confidence = max(confidence, 0.5 * branch_diversity_score + 0.3 * min(covered_edges/4, 1.0))` — calibrate so the existing caps at lines 479-490 still apply. Document the formula change in the docstring.

**Tests**: the commit message reports list loop+branch coverage going 1→4 covered edges and diversity 0→1.0 — encode that as a test (container-input function, assert `covered_edges >= 4` and confidence > 0). Keep all existing `tests/test_z3_sym_engine.py` cases green.

### T5 — FLOW-BENCH adapter → executable corpus

**New file**: `module_02_extract/eval/flowbench_adapter.py` (create the `eval/` package). **Input**: `module_02_extract/inputs/conditional_ootb.yaml` — the IBM FLOW-BENCH conditional/OOTB split, 101 tests, structure: `tests[i].expected_output.sequence[0]` is a valid-Python statement list (verified: all 101 parse). Facts you must handle:
- Sequences are **bare statement lists** — no `def`, no imports; `main.py:114-116` rejects function-less source.
- **141 distinct undefined task-API call names** (e.g. `Jira_Issue__2_0_0__create_Issue()`) plus `user_task("...")`.
- **30 of 32 if-guards are `obj.attr <cmp> literal`** (e.g. `incident.impact == "high"`), and `SymbolicEvaluator` has **no `visit_Attribute`** — attribute guards abstain-to-False in V2.

Adapter spec (per test uid):
1. Parse the sequence with `ast`.
2. Rewrite every `obj.attr` load into `obj["attr"]` (ast.NodeTransformer) — V2's `visit_Subscript` + registry flattening (`src/z3_sym_engine/evaluator.py:166-180`, `src/z3_sym_engine/registry.py`) already handle subscripts.
3. Collect the guard-controlling attributes (attributes compared in if/elif tests) and promote them to **typed function parameters** (str/int/bool inferred from the compared literal) so V1's random generator (`src/dynamic_tracer/randomized.py:67-100`) and V2's solver can vary them.
4. Synthesize a stub `def` for each task-API call used, returning a dict that echoes the relevant parameters (e.g. `def ServiceNow_incident__4_0_0__retrievewithwhere_incident(impact): return {"impact": impact}` — thread the parameter through the workflow body). `user_task(label)` stubs return `{"label": label}`. No imports allowed anywhere — the runtime `SAFE_BUILTINS` (`src/main.py:38-44`) has no `__import__`.
5. Wrap the rewritten body in `def workflow(<params>):` and emit one self-contained `.py` per uid into `module_02_extract/eval/corpus/`, plus `manifest.json` entries `{uid, tags, params, source_file}` (tags from `tests[i]._metadata.tags`).
6. Smoke-run: every generated file must round-trip `_run_verification` (`src/main.py:83`) without hitting the outer exception handler. Write `eval/test_corpus_smoke.py` (pytest) that runs a sample (e.g. 10 uids spanning linear/conditional/loop tags) through the pipeline and asserts a well-formed certificate.

For-loops iterate over stubbed retrieve-calls; make those stubs return small non-empty lists of dicts (2 items) parameterized the same way — this is what T4's container work will exercise.

### T6 — Mutation generator

**New file**: `module_02_extract/eval/mutate.py`. AST-transform based; each mutant = exactly one operator applied at one site; output `eval/mutants/<uid>__<operator>__<site>.py` + extend `manifest.json` with `{base_uid, operator, site, label: "buggy"}`. Operators (implement all 10):
1. `negate-guard` — `if c:` → `if not (c):`
2. `boundary-shift` — `<` ↔ `<=`, `>` ↔ `>=`
3. `swap-branches` — exchange if/else bodies
4. `off-by-one-loop` — perturb a loop bound/slice by ±1 (where applicable)
5. `drop-step` — delete one state-update/task-call statement
6. `reorder-steps` — swap two adjacent data-dependent statements
7. `wrong-variable` — replace a variable read with another in-scope same-type name
8. `corrupt-container-op` — `append` ↔ `remove`, or wrong dict key
9. `early-return` — insert `return` before the last workflow step
10. `constant-perturb` — replace a compared literal (e.g. `"high"` → `"low"`, `100` → `1000`)

Skip operators that don't apply to a given base (e.g. no `swap-branches` on linear programs); record applicability in the manifest. Unit-test at least 3 operators on a fixed base program (assert the mutant differs, still parses, and differs semantically on at least one input).

### T7 — (if time remains) Calibration runner skeleton

`module_02_extract/eval/calibrate.py`: split base uids 50/50 CALIB/EVAL stratified by tag (fixed seed), run all corpus+mutant programs through `_run_verification`, collect `combined_confidence` + label, compute ROC on CALIB, pick τ by Youden's J, freeze to `eval/threshold.json`, report EVAL detection/false-alarm with exact (Clopper–Pearson) binomial CIs. Output a markdown report to `eval/results/`.

---

## WHAT NOT TO DO

- Do not touch `module_01_spec/`, `module_03_equiv/`, `module_04_ui/`.
- Do not merge or cherry-pick `e4ba019` mechanically — the file it patches no longer exists; port per T4.
- Do not change the `/verify` wire-format keys (Module 04 UI depends on them); adding keys is fine.
- Do not weaken existing tests to make them pass — if a test conflicts with a fix, update it only with a comment-free, behavior-justified change and mention it in the commit message.
- Do not implement `visit_Attribute`, wall-clock timeouts, typed per-layer `/verify` statuses, or adaptive n_runs in this session unless T1–T6 are done and green — they're the next session's scope.

## DEFINITION OF DONE

- All original 105 tests + new tests pass (`python -m pytest -q` from `module_02_extract/`).
- `test_buggy_program_fails` proves a mutated program can fail the pipeline.
- `eval/corpus/` contains 101 generated programs; smoke test green.
- `eval/mutants/` generated with manifest; ≥5 operators exercised across the corpus.
- `gitnexus_detect_changes()` run before each commit; one branch, one commit per task, pushed.
