# CP1 — Is the lifting-scope fix (D2) actually required? Decided: YES

> Follows on from [[E2E Integration Verification Findings]] (the vacuity-channel fix + real
> ingestion wiring, PRs #70–#72) and [[AP Vocabulary and Lifting Scope Findings]] (the original
> definition-order-vs-call-order framing). D2 (in the Claude Science Session-e2e docs) proposed
> switching the lifter from **definition order** (functions ordered as written in the file) to
> **call order** (functions ordered as actually invoked by the orchestrator). That proposal was
> based on a Python emulation of the compiled engine. This note answers CP1 — whether that fix is
> worth building — using the **real compiled engine's first genuine run** (58 checks, 29 variants,
> `{VIOLATION: 18, COMPLIANT: 17, INCONCLUSIVE: 23}`, produced after the vacuity-channel fix).

## Method

For every non-`INCONCLUSIVE` verdict, independently reconstruct the ground truth from the
orchestrator's actual call sequence (regex-extracted from source, same method as
[[E2E Integration Verification Findings|F4]]'s divergence classification — directional, not the
compiled engine) and cross-tab against the verdict the engine produced under definition-order
lifting. Script: `cp1_crosstab.py`, raw per-check data: `cp1_crosstab_raw.json`.

## Result

**Of 18 `VIOLATION` verdicts:**
- 12 name at least one task that is **never called at runtime** — the atom only "matched" because
  definition-order lifting includes every function defined in the file, called or not. Spurious by
  construction.
- Of the remaining 6 (both atoms genuinely called), checking real call order directly: **5 confirm
  a genuine precedence violation; 1 (`77__llama-3.1-8b.py`) is contradicted** — real call order
  shows the precedence was actually satisfied (bucket retrieved before object created), but
  definition order told the engine otherwise.
- **Net: 5/18 (28%) confirmed real. 13/18 (72%) spurious or wrong.**

**Of 17 `COMPLIANT` verdicts:**
- 12 occur on variants independently classified (F4) as omission-divergent — i.e. the code omits a
  spec task entirely. `P1` precedence properties (`!start(X) W done(Y)`) are vacuously satisfied
  when a task never starts, so these are false-`COMPLIANT`s hiding a real omission defect, not
  genuine order conformance.
- **Net: at most 5/17 (29%) not already flagged as suspect.**

**Combined: of the 35 definitive verdicts from the pipeline's first real run, roughly 10 (29%) are
trustworthy as-is; the remaining ~25 (71%) are either provably spurious, contradicted by real call
order, or riding on omission-blindness.** This is measured directly against the compiled engine's
real output, not projected from Claude Science's Python emulation — the emulation's 53.2%→40.4%
detection-rate framing pointed the same direction but couldn't see the vacuity bug, so this number
supersedes it as the load-bearing evidence.

## Decision

**D2 (call-order lifting) is required**, not optional polish. Definition-order lifting isn't a
minor precision loss — it inverts the majority verdict on both sides (false-VIOLATION and
false-COMPLIANT) for the corpus this project is evaluated against. Any thesis numbers or demo
generated against the current definition-order lifter would be reporting noise as signal.

**Scope note for implementation:** the omission-driven false-`COMPLIANT`s are a *different* defect
than the ordering-driven false-`VIOLATION`s. Call-order lifting fixes the ordering side (13/18).
It does **not** by itself fix the omission side (12/17) — a task that's never called still won't
appear in the lifted automaton's call sequence regardless of ordering scheme, so a precedence
property will still be vacuously `COMPLIANT` unless omission is checked separately (e.g. a
distinct "was every spec task actually reached" property class, already conceptually adjacent to
the P0 sentinel tier). Flagging this so D2's implementation isn't scoped as fixing more than it
does — the ~71% "untrustworthy" figure needs two fixes, not one.

## Implemented and validated, 2026-07-29

`derive_call_order_wir()` (`module_02_extract/src/ast_extractor/call_order_view.py`, exported from
the package `__init__.py`) is a new, separate entry point alongside `CFGExtractor.extract()` — it
does not modify `extract()` or any shared visitor method, so every existing consumer of
definition-order WIRs (tests, `run_v3_pipeline`, `concolic.py`) is untouched (confirmed: `impact()`
+ grep both show `extract()`'s only real callers are `run_v3_pipeline` and the z3 concolic engine,
neither of which this touches).

**Mechanism:** identify the "driver" — the top-level function whose body calls the most sibling
top-level functions (AST-based `ast.Call`/`ast.Name` resolution against the exact set of top-level
def names, not a fragile regex heuristic; excludes self-recursive calls) — or, if no function
qualifies, the module's own trailing top-level statements. Build that driver's own control-flow
graph via `CFGExtractor`'s existing, tested `_build_body()` (full branch/loop/guard support reused
as-is), then relabel each call-site node that invokes a sibling top-level function as `type="task"`
(code text unchanged — the C++ lifter's existing `extract_actions_from_code` + `semantic_match`
already resolves the call text to a BPMN task atom; no C++ changes needed). One bug found and
fixed during validation: `_build_body()` (unlike `visit_Module`) leaves its last node with no
outgoing edge, and a task label only ever attaches to an *edge leaving* its node
(`lifter.cpp`'s `resolve_task_label` call site) — without an explicit trailing exit-sentinel edge,
the driver's last call would never register an AP at all. Fixed by mirroring `visit_Module`'s own
entry/exit sentinel pattern.

**Acceptance pair, confirmed exactly as predicted:** uid 44 (both atoms genuinely called, real
order violation) stays `VIOLATION`; uid 77 (definition order said `VIOLATION`, real call order
shows the precedence was actually satisfied) flips to `COMPLIANT`.

**Full 58-check corpus re-run, call-order lifting:** `{VIOLATION: 5, COMPLIANT: 10,
INCONCLUSIVE: 43}` (previously `{VIOLATION: 18, COMPLIANT: 17, INCONCLUSIVE: 23}`). The shift maps
exactly onto this doc's predictions when traced check-by-check:
- Old `VIOLATION` (18): 5 stayed `VIOLATION` (the confirmed-real ones), 12 became `INCONCLUSIVE`
  (the atoms genuinely aren't in the driver's call sequence — never called, so absent, not
  spuriously matched), 1 became `COMPLIANT` (uid 77 itself).
- Old `COMPLIANT` (17): 9 stayed `COMPLIANT`, 8 became `INCONCLUSIVE` (omission on *that specific
  property's* atoms, a tighter and more accurate signal than the per-variant F4 proxy used above).
- Old `INCONCLUSIVE` (23): all 23 unchanged — no regressions.

This is the correct behavior, not a shortfall: call-order lifting fixes ordering, and as a direct
consequence a never-called atom is now genuinely absent from the automaton rather than spuriously
present, so the existing atom-matching gate (PR #67) correctly reports `INCONCLUSIVE` instead of a
confident wrong answer. It does not, by itself, turn omission into a `VIOLATION` — that is the
separate coverage-tier work noted above, still open.

Tests: `module_02_extract/tests/test_call_order_view.py` (7 tests: call-order-not-definition-order,
driver identification, trailing-edge invariant, never-called-function exclusion, branching/guard
preservation, module-level-calls fallback, self-recursion not mistaken for the driver). Full
module_02/module_03 suites re-run: no regressions (module_03's 2 pre-existing unrelated failures —
`compute_deterministic_hash` missing — unchanged; module_02's `test_ast_extractor.py` has 4
pre-existing Python-3.9-vs-3.10+ AST-feature failures and one pre-existing hang in
`TestWIRDataLayer`/`TestV3Certificate`/`TestEndToEnd` — all confirmed present identically on HEAD
*without* this change, via `git stash`, so unrelated to D2 and out of this scope).
