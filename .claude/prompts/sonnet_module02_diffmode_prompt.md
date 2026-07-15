# SESSION MANDATE — Module 02: differential-mode evaluation (follow-up to T1–T7)

You are continuing implementation on the VibeCheck FYP repo (`C:\Research\FYP\Vibe-Check`), branch **`fix/mod2/verdict-and-eval-corpus`** (do NOT branch off `develop` — this session extends the existing branch; all T1–T7 commits `789455a..32eac90` are already on it, 127 tests passing). Work on **Module 02 only** (`module_02_extract/`); `module_01_spec/`, `module_03_equiv/`, `module_04_ui/` are teammates' — read-only.

## Why this session exists (verified context — do not re-derive, but re-read cited lines before editing)

The T7 calibration run measured **0/220 detection across every mutation operator** (`eval/results/calibration_report.md`), Youden's J = 0. A verification pass established the cause is **two stacked defects**, and fixing only the first will NOT restore detection:

1. **Flattening**: `src/dynamic_tracer/randomized.py:86-87` assigns `""` to every str-typed parameter on every run, so every program yields one distinct input → `coverage_score = 1/n_runs` (`randomized.py:171`) → all V1 scores collapse to the same constant → degenerate ROC.
2. **Self-referential oracle (the fundamental one)**: V1's expected trace comes from a WIR reference interpreter re-derived **from the mutated source itself**, so mutant code and mutant-derived WIR diverge identically — drop-step scored 0/51 and early-return 0/51, which no input generator could rescue. This is documented in `tests/test_integration.py:85-104` and `.claude/memory/round3_verified_findings_2026_07_04.md` (section "Round-3b").

The resolution: Module 02's self-mode certificate certifies code↔WIR **extraction fidelity**; bug *detection* requires verifying mutant code against the **base program's WIR** (WIR-as-spec differential mode). The seam already exists: `run_v1_pipeline(source, function_name, wir, ...)` takes `wir` as an injectable parameter (`src/dynamic_tracer/pipeline.py:12-23`).

## Ground rules (same as last session)

1. Follow `CLAUDE.md` GitNexus workflow: `gitnexus_impact` before modifying any symbol, `gitnexus_detect_changes()` before each commit, no find-replace renames. **First action of the session**: run `npx gitnexus analyze` — the index predates the eval/ subsystem.
2. `cd module_02_extract && python -m pytest -q` must pass (currently 127) after every task, plus your new tests. Pay special attention to `tests/test_dynamic_tracer_parity.py` when touching collector/comparator behavior.
3. One commit per task, conventional style (`fix(mod2): ...` / `feat(mod2): ...`).
4. Do not change existing `/verify` wire-format keys (Module 04 reads them). Adding keys is fine.

---

## TASKS (in order)

### D1 — Pool-based string input generation

**File**: `src/dynamic_tracer/randomized.py` (`_generate_random_inputs`, lines 67-100).

Replace the constant `""` for str params with sampling from a **literal pool**: in `RandomizedDifferentialTester.__init__`, walk `self.source` with `ast` and collect every `str` constant that appears inside an `ast.Compare` node (these are the guard-compared literals like `"high"`, `"urgent"`, `"customer"` — 30 of 32 FLOW-BENCH guards have this shape). For each str param, sample uniformly from `pool + ["", "<random junk string>"]` so both sides of every string guard get exercised. Keep determinism under the existing `seed` parameter (use the module-level `random` already seeded at lines 46-47).

Do NOT sample uniform random strings alone — a random string never satisfies `status == "high"`, which would reproduce the one-path problem in the other direction.

**Tests** (in `tests/test_dynamic_tracer.py`, near `test_input_coverage_score` ~line 440):
- A function with a `param == "high"` guard, n_runs=20, seed fixed: assert the collected inputs contain both `"high"` and non-`"high"` values, and `input_coverage_score` > 1/20.
- Existing tests must stay green; if any asserted the old constant-`""` behavior, update them with justification in the commit message.

Also mirror the pool idea in `src/main.py:148-149` only if trivial (initial V2 input for str params: first pool literal instead of `""`); skip if it ripples.

### D2 — V2 string round-trip via reverse token map

**Files**: `src/z3_sym_engine/registry.py`, `src/z3_sym_engine/evaluator.py:54-56` (`visit_Constant` str → `z3.IntVal(hash(v) & 0x7FFFFFFF)`), `src/z3_sym_engine/concolic.py:355-375` (`_z3_to_python`).

Today V2 encodes string literals as hash tokens but cannot decode a Z3 model value back into a string — `_z3_to_python(z3_val, str)` hits the `as_long` branch and returns a raw `int`, which then gets passed as a str-typed argument on the next concrete iteration (wrong-typed input; comparisons silently False). Fix:
- Add a `token → literal` reverse map to `Z3VariableRegistry`; populate it in `visit_Constant` whenever a str constant is tokenized (the registry instance is already shared across iterations — `concolic.py:67-69`).
- In `_z3_to_python`, when `py_type is str` and the value is an int token, look it up in the reverse map; if found return the literal, else return a sentinel string (e.g. `f"__tok_{v}"`), never a bare int.

**Test** (in `tests/test_z3_sym_engine.py`): a function `def f(status: str): if status == "high": return 1; return 0` — run the full concolic engine from `initial_inputs={"status": ""}` and assert both branches end up in `covered_edges` (the solver must produce `"high"` as a *string* on the negated path).

### D3 — Comparator: stop discarding branch decisions

**File**: `src/dynamic_tracer/comparator.py:102-118` (`_normalise` currently maps every branch event to a bare `("branch_point",)`).

In differential mode, a negated guard whose two arms contain identical observable tasks is invisible unless the *decision* is compared. Change `_normalise` to emit `("branch_point", taken)` where `taken = e.get("taken_branch")`. **Before doing so, verify what the actual-side collector emits**: read `src/dynamic_tracer/collector.py` (settrace callback ~lines 141-215 and the sys.monitoring callbacks ~215-300) and check whether actual-trace `branch_point` events carry a comparable taken/decision field. If they don't, normalize both sides to a shared encoding you can justify (e.g. include `taken` only when present on both, else fall back to the bare tuple) — the requirement is: identical programs still match 1.0 (parity + existing comparator tests), and a decision divergence on aligned branch events lowers similarity.

**Tests**: existing `TestDifferentialComparator` cases (`tests/test_dynamic_tracer.py:341-410` — `test_identical_traces`, `test_stutter_elimination`, `test_divergent_traces`, `test_partial_match`, `test_lcs_correctness`) must pass, updated only if their fixtures baked in the old tuple shape. Add one new case: two traces identical except one `taken_branch` flag → similarity < 1.0. Run `tests/test_dynamic_tracer_parity.py` explicitly.

### D4 — Differential mode in the eval harness + re-run calibration

**Files**: `eval/calibrate.py` (main change), `src/z3_sym_engine/concolic.py:32-55` + `src/z3_sym_engine/pipeline.py:12-38` (small optional param).

1. Add `--mode {self, differential}` to `eval/calibrate.py` (default `differential`; keep self-mode runnable — its 0-detection result is a documented negative finding, not dead code).
2. Differential scoring of a mutant: extract WIR **once from the base program** (`run_v3_pipeline(base_source)`, take `functions["workflow"]`), derive V1 params from the **base** WIR (reuse `_derive_v1_params`, `src/main.py:51-80` — import it rather than duplicating), then run `run_v1_pipeline(source=mutant_source, function_name="workflow", wir=base_func_wir, ...)` with the mutant's compiled namespace. Correct (unmutated) corpus programs are scored the same way against their own WIR — which is identical to self-mode for them, keeping labels comparable. Use the existing `eval/manifest.json` (`base_uid` links mutants to bases).
3. V2 in differential mode: add an optional `wir: Optional[dict]` parameter to `BoundedConcolicEngine.__init__` (skip the internal `CFGExtractor().extract` at `concolic.py:55` when provided) and thread it through `run_v2_pipeline`. Be honest in the code docs: V2 has no actual/expected comparator, so in differential mode it contributes spec-path coverage stats, not detection — **V1 is the differential detector**. If wiring V2 cleanly takes more than ~an hour, run differential mode V1-only (`combined = v1`) and say so in the report.
4. Re-run the full calibration (both modes), regenerate `eval/results/calibration_report_differential.md` with the same structure as the existing report **plus** the per-operator detection table. Freeze `eval/threshold.json` from **differential-mode CALIB** only.

**Acceptance**: report whatever you measure — do not tune until J looks good. Expected (not required): drop-step / early-return / reorder-steps detected via task-sequence divergence; negate-guard / boundary-shift / constant-perturb detected via D1+D3; corrupt-container-op partially via exceptions. If an operator class stays at 0, state why in the report rather than adjusting the corpus.

### D5 — Wrap-up

- Update `tests/test_integration.py:85-104` docstring NOTE to reference differential mode as the measured answer (keep the self-mode explanation — it is thesis material).
- Append a short section to `.claude/memory/session_2026_07_04_t1_t7_implementation.md` with the differential-mode results (per-operator numbers, chosen τ, CIs).
- `gitnexus_detect_changes()` + `npx gitnexus analyze`, then push the branch and open a PR to `develop` (`gh pr create`) titled `fix(mod2): non-vacuous verdict + FLOW-BENCH mutation eval (differential mode)` — body: one paragraph on the vacuous-verdict fix, one on the self-referential-oracle finding and differential mode, the per-operator detection table, and the standard generated-with-Claude-Code footer.

---

## WHAT NOT TO DO

- Do not try to make **self-mode** detect logic mutations — it is architecturally impossible (oracle derived from the code under test) and the 0/220 result is a deliberate documented finding.
- Do not delete or overwrite `eval/results/calibration_report.md` (the self-mode negative result); the differential report is a sibling file.
- Do not implement `visit_Attribute`, wall-clock timeouts, typed per-layer `/verify` statuses, adaptive n_runs, or `merge_states` wiring — still out of scope.
- Do not weaken parity or comparator tests to force D3 through; if the collector genuinely lacks decision info, the fallback encoding described in D3 is the correct scope.

## DEFINITION OF DONE

- Full suite green (127 existing + new tests) including `test_dynamic_tracer_parity.py`.
- D2's both-branches string test passes (V2 solves a string guard end-to-end).
- `eval/results/calibration_report_differential.md` exists with per-operator detection, exact binomial CIs, and a frozen `threshold.json` from differential CALIB.
- Self-mode report untouched; memory file updated; PR opened against `develop`.
