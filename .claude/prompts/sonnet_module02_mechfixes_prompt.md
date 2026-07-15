# SESSION MANDATE — Module 02: mechanical fixes (extractor bookkeeping cleanup + collector branch-decision)

You are closing the two measured gaps left after the eval arc on VibeCheck (`C:\Research\FYP\Vibe-Check`). Both gaps have file:line diagnoses and — unusually — **existing measurement instruments that produce before/after evidence**: E2 (`eval/e2_structural.py`) for fix F1, the differential calibration (`eval/calibrate.py`) for fix F2. This session touches `src/`, so full discipline applies.

**Branch**: PRs #25/#26 are merged; branch `fix/mod2/bookkeeping-and-branch-decision` off `develop`. Baseline: **179 tests passing**. First commit of the session: add the uncommitted `eval/results/e2_manual_check/VERDICT.md` (human-validation verdict, already written — commit as-is, `docs(mod2): record E2 manual-validation verdict`).

## Verified context (re-read cited lines first — they may have drifted)

**Gap F1 — bookkeeping nodes pollute the WIR.** The extractor emits blank merge/exit nodes: `visit_If` and the loop visitors create join/exit blocks, `visit_Try` (`src/ast_extractor/cfg_extractor.py:407`), `visit_TryStar` (`:457`), `visit_Match` (`:503`) each create a `merge = self._make_block(node)` with no code and no guard. Human-validated evidence (`eval/results/e2_manual_check/VERDICT.md`): 10/10 sampled programs show the *entire* E2 precision gap (node P 0.8255, edge F1 0.6827) is these synthetic nodes — zero genuine extraction errors. They also ship in the WIR Module 03's equivalence clustering will consume.

**Gap F2 — value-only mutations are invisible.** Corrected calibration (`eval/results/calibration_report_differential.md`): constant-perturb 0/9 detected, negate-guard 8/14. Cause: the actual-side collector records `branch_point` events with `observables` but **no decision** (`src/dynamic_tracer/collector.py:186-192` settrace, `:316-322` monitoring), while the reference interpreter records `taken_branch` (`src/dynamic_tracer/interpreter.py`). The comparator's decision-aware matching (added in D3, `src/dynamic_tracer/comparator.py::_normalise`) only activates when both sides carry a decision — currently a documented no-op. A mutated guard that routes to the *same* stubs either way produces identical task sequences and is undetectable.

## Ground rules

- `CLAUDE.md` GitNexus workflow: `npx gitnexus analyze` first; `gitnexus_impact` on every symbol you modify (expect HIGH on extractor/collector — proceed with the instrument-verified evidence this prompt provides); `gitnexus_detect_changes()` per commit.
- Suite green after every task (`python -m pytest -q` from `module_02_extract/`), **including `tests/test_dynamic_tracer_parity.py`** — F2 touches both tracer backends.
- `/verify` wire-format keys unchanged; adding fields is fine.
- Re-run the instruments after each fix and report measured numbers as-is. If a number moves the wrong way, investigate — do not rationalize.

---

## F1 — Contract bookkeeping nodes out of the WIR (post-construction pass)

**Design**: do NOT rewrite the visitors — their merge nodes are load-bearing during construction (e.g. the finally-rerouting in `visit_Try:424-438`). Instead add a **graph-contraction post-pass** in `CFGExtractor.extract()` (or as step P1.1b in `run_v3_pipeline`, `src/ast_extractor/pipeline.py:19-37` — before dominators, guards, and data-layer run, so downstream stages see the clean graph):

- A node is contractible iff: `type == "block"`, empty `code` (or only whitespace), no `guard`, and it is not the entry or exit node.
- Contract by rewiring every predecessor to every successor, preserving edge labels: if pred→node carries a label (e.g. `exception_type`, a guard label) and node→succ is unlabeled, the new pred→succ edge carries the pred-side label; **if both edges carry different labels, do not contract that node** (report it — likely rare).
- Loop-back and merge cycles: plain rewiring preserves cycles; add a test with `for`+`if` nesting asserting the loop back-edge survives contraction.
- Update `nodes`, `edges`, `predecessors`/`successors` consistently; run on the module CFG and every function sub-CFG.

**Known blast radius to check explicitly (in this order):**
1. **V3 abort gate**: `node_coverage = wir_count / ast_stmt_count` (`src/ast_extractor/certificate.py:63-89`). Removing nodes lowers `wir_count`; if any corpus program drops below the 0.95 gate, the composer now fails it outright (V3 gate from T1). After implementing, run all 101 corpus programs through `run_v3_pipeline` and assert zero new aborts — bookkeeping nodes were *inflating* coverage, so semantic statements should still map ≈1:1, but verify, don't assume.
2. **V1 params**: `_derive_v1_params` (`src/main.py`) reads gateway/loop nodes — untouched by contraction of blank blocks, but confirm branch_lines are stable on a conditional corpus program.
3. **Reference interpreter and V2 tracer** walk `successors` — contraction only shortens paths through no-op nodes; parity + dynamic-tracer tests are the net.
4. **Schema** (`src/ast_extractor/schema.py`) — contraction removes nodes, adds no fields; should validate unchanged.

**Acceptance (the instrument)**: re-run `eval/e2_structural.py`. Expect node precision ≈1.0 (from 0.8255) and edge F1 substantially up (from 0.6827) with recall staying 1.0. Archive the old E2 report to `eval/results/archive/` (README line), regenerate, include a before/after table. E2 gold and manual-check files are untouched. Then re-run the differential calibration once to confirm detection/false-alarm are not degraded by the cleaner WIR (they shouldn't be — task events don't ride on blank nodes — but measure it).

## F2 — Give the actual-side collector a branch decision

**Preferred mechanism**: the monitoring backend runs on CPython 3.12+ where PEP 669 exposes `sys.monitoring.events.BRANCH` (callback receives the branch's instruction offset and destination — taken vs not-taken is derivable, and 3.13 refines this; check the running interpreter's exact API, the venv is 3.13). Wire BRANCH events for code in the target file so each `branch_point` trace event gains a `"taken": bool` field. For the **settrace fallback**, infer the decision from the next `line` event after a branch line: taken = next executed line falls inside the branch's true-arm line range, derived from the WIR node's successors — use the **code-under-test's own WIR** for those line ranges (same observation-layer/oracle distinction as the C2 fix, `eval/calibrate.py:225-239`: WHERE to watch comes from the code under test; WHAT to expect comes from the oracle).

- **Parity**: `tests/test_dynamic_tracer_parity.py` must keep passing — both backends must emit the same `taken` values on the same runs. If the settrace inference cannot match the BRANCH-event fidelity in some corner (e.g. one-armed `if` falling through), normalize both to the weaker-but-consistent encoding and document it; parity beats precision here.
- The comparator's D3 pathway (`comparator.py::_normalise` — includes `taken` only when both sides carry it) should light up with no changes; verify with a unit test where only the decision differs (existing D3 test may already cover the shape — extend it to run through the real collector rather than hand-built traces).
- Reference side already emits `taken_branch`; confirm the field names align end-to-end.

**Acceptance (the instrument)**: re-run the differential calibration (archive old report + README line, regenerate with the same three-figure structure and per-operator table). Expected movement: constant-perturb up from 0/9, negate-guard up from 8/14, genuine-bug detection headline up from 0.929; **false-alarm on untouched bases (0.059) and equivalent-mutant behavior must not degrade** — a decision field that misfires would show up exactly there, so treat any FA increase as a bug in the inference, not noise. Re-freeze `threshold.json`. E3: ground truth is unchanged; rescore the certificate side (cache-invalidate) and regenerate the correlation report if r moves.

## Wrap-up

- Append before/after numbers (E2 and calibration) to `.claude/memory/session_2026_07_04_t1_t7_implementation.md`.
- `gitnexus_detect_changes()`, push, open PR to `develop` titled `fix(mod2): contract WIR bookkeeping nodes + collector branch decisions` — body: one paragraph per fix with its instrument's before/after table, plus a note for the M03 owner that WIRs are now free of blank structural nodes (relevant to their equivalence clustering input).

## WHAT NOT TO DO

- Do not rewrite the extractor visitors — the contraction is a post-pass by design.
- Do not touch E2 gold, manual-check files, or `eval/gold_wir.py` — the gold is human-validated; if extracted-vs-gold still mismatches after F1, the remaining delta is real extractor behavior to report, not gold to adjust.
- Do not regenerate any mutants — nothing in this session changes what the corpus should contain.
- Do not let F2's settrace inference read arm line ranges from the *oracle* WIR — observation layer comes from the code under test (C2 precedent).
- Out of scope, still: `visit_Attribute`, typed per-layer `/verify` statuses, wall-clock timeout, `merge_states` wire-or-excise, adaptive n_runs, multi-implementation corpus (separate track pending the M03 conversation).

## DEFINITION OF DONE

- Suite + parity green (179 + new tests).
- Zero new V3 aborts across the 101-program corpus after F1 (measured, reported).
- New E2 report: node precision ≈1.0, edge F1 improved, recall still 1.0, before/after table; old report archived.
- New calibration report: value-only operators improved, false-alarm not degraded, before/after table; `threshold.json` re-frozen; old report archived.
- VERDICT.md committed; PR open with the M03 note; memory appended.
