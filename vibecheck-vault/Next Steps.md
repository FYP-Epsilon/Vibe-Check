# VibeCheck — Next Steps (Research Roadmap)

> Synthesized from the vault snapshot **2026-07-28** (main @ `7089711`): [[Project Status.canvas|Project Status]], [[Module 01 - Specification Analysis/Module 01 Knowledge|M01]], [[Module 02 - Verified IR Extraction/Module 02 Knowledge|M02]], [[Module 03 - Equivalence Engine/Module 03 Knowledge|M03]], [[Module 04 - Verification Portal/Module 04 Knowledge|M04]].
> Ordered by *research leverage first*: the project's headline claim — end-to-end spec↔code verified translation validation — is mechanically possible for the first time, but not wired. Everything below serves getting that claim demonstrated, measured, and defensible.

## Reprioritization flag (2026-07-29, pending your sign-off)

The bridge investigation (three Claude Science sessions, see
[[Module 03 - Equivalence Engine/Bridge Investigation/AP Vocabulary and Lifting Scope Findings|full findings]])
surfaced something bigger than P1.4 was scoped to find: Module 03's C++ Phase A currently lifts a
chain of **function definitions**, in **definition order**, and never reads inside function
bodies at all — so its action atoms are function names, not business actions, and their order
disagrees with real execution order in ~46% of a real 184-variant corpus (measured, then
independently reproduced with a different method). This is arguably foundational to whether the
C++ track models real program behavior *at all*, independent of whether Module 01 is ever wired
in. Whether that should reorder P0–P3 below, or become its own P0/P1-adjacent item, is your call
to make, not something restructured here unilaterally — flagging it prominently so it doesn't get
lost inside P1.4's entry.

## Update 2026-07-29 (E2E session + independent verification)

A follow-up Claude Science round designed the full M01+M02+M03 integration, a FLOW-BENCH e2e
evaluation harness, and a real-world demo — see
[[Module 03 - Equivalence Engine/Bridge Investigation/E2E Integration Verification Findings|full
findings]]. Independently re-verified against the repo, including **the first working local
compiled build of `vibecheck_lifter` on this machine**. Three things change the picture above:

- **Item 4's vacuity guard (4.d) is not optional or a future risk — it is confirmed, live, and now
  the actual blocker above everything else in P1.** `check_compliance()` still returns vacuous
  `COMPLIANT` on every non-looping automaton regardless of atom matching, confirmed on the compiled
  engine, and **0 of 43 eligible-corpus variants have any top-level cycle** — so real detection is
  currently zero, for any lifting scheme, until the `alive`/stutter-extension bridge from 4.a/4.b
  actually lands. Item 6 ("first e2e demo") and P2.7 ("e2e eval") are both blocked on this, not just
  on ingestion (P1.3).
- **The gateway question (item 4.c's scope decision, and the corpus-scope question generally) is
  resolved, not just deferred:** Module 01 hard-fails on all 19 `<exclusiveGateway>`-bearing specs,
  and every one of those gateways' BPMN source genuinely lacks a default flow or any condition
  expression — confirmed by direct XML inspection, not just by reading the gate's error message.
  The eligible e2e corpus is 29 sequential specs; scoping branching out of the thesis is the
  evidence-backed choice, not a workaround.
- **Only 45 of 412 exported properties (17.6% of P1, 0% of P2/P3) are checkable against code at
  all**, and the dominant real-corpus divergence mode is task *omission* (23/43 pairs), which the
  existing P1 property shape is structurally blind to — a task-coverage tier is a prerequisite for
  a defensible e2e number, not a nice-to-have. See the findings note for the full property-tier
  breakdown and the design (D1 §6) for what that tier would look like.

## The one thing that matters most

**Wire Module 01 → Module 03.** Both mechanisms exist today: M01 exports an LTLf property suite (`module_03_input.json`) and M03's C++ `check_compliance` model-checks any SPOT LTL string with counterexample extraction. The only caller passes a hardcoded `'G("approved")'` placeholder. Until this is connected, the thesis's central claim is two halves, not a system.

## P0 — Unblock what's broken (hours, not days)

1. ✅ **Fix M01 startup crash — done 2026-07-29.** `main.py:11,16` imported the deleted `automata_lifter`; deleted, the app now imports and constructs cleanly, all 4 existing tests pass.
2. ✅ **Fix M04 equivalence page — done 2026-07-29.** `module_03_equiv/src/main.py` rewritten as a
   FastAPI service (`uvicorn src.main:app`, mirroring M01's pattern; no host port needed — same as
   spec-engine/extract-engine, reachable over the docker network by container name). Two endpoints,
   deliberately not conflated: `POST /lift` (the literal fix — WIR type-lifting + semantic action
   matching, the old P1.1/P1.2 demo, now over HTTP instead of an in-process `import vibecheck_lifter`
   that could never succeed in the `ui-engine` container) and `POST /check` (the real Phase A-D
   conformance check, wrapping `property_ingest`/`process_wir_batch` — this is the start of item #6,
   not part of #2's fix, and is explicitly documented as requiring an already call-order-lifted WIR:
   this container only has `module_03_equiv`'s own source, so it cannot itself run
   `derive_call_order_wir` — no committed caller produces one over HTTP yet). `module_04_ui/src/app.py`'s
   `_check_equiv_engine()` and the equivalence page's demo button now call `/lift` over HTTP, matching
   the existing spec-engine/extract-engine pattern. Verified locally: started the service with the
   scratchpad-built `.so` + `DYLD_LIBRARY_PATH`, hit `/health`, `/lift` (same output as the old demo),
   and `/check` with the uid 77 call-order WIR — returned the same `COMPLIANT`/`INCONCLUSIVE` verdicts
   already validated in-process. **Not verified**: the actual `docker-compose` build (SPOT-from-source
   is too slow to build in this environment) and the Streamlit page in a browser — flagged explicitly,
   not claimed.

## P1 — Close the end-to-end loop (the research-critical path)

3. ✅ **M03 ingestion of `module_03_input.json` — done 2026-07-29.** New `property_ingest.py` (tier-gated, normalized, deduplicated, quoted for SPOT's parser) wired into `process_wir_batch()` via a new optional `property_suite` parameter; the legacy single-string path is untouched. First real end-to-end FLOW-BENCH run completed (definition-order lifting, 58 checks, provisional — see [[Module 03 - Equivalence Engine/Module 03 Knowledge|Module 03 Knowledge]]).
4. ✅ **LTLf→LTL semantic bridge — all five sub-parts (a–e) done 2026-07-29.** Two residual,
   explicitly-flagged gaps remain inside it (not separate roadmap items): the `NON_TERMINATING`
   verdict design decision (d) and untested edge cases — empty traces, the loop-bound/
   `loop_bound_documented` interaction (e).
   ([[Module 03 - Equivalence Engine/Bridge Investigation/P1.4 Bridge Findings|full findings]]).
   Confirmed: SPOT 2.11.6 (the exact vendored version) ships `spot::from_ltlf()`, so formula
   translation itself is close to solved. But translation alone is **worse than useless** —
   `check_compliance` is vacuously `COMPLIANT` on any non-looping automaton today, because the
   lifter never sets an acceptance condition (confirmed against source); shipping only the
   formula bridge would produce a confident, uniformly-passing verdict on arbitrary code. This
   item is four sub-parts, not one:
   a. ✅ **Done.** Sanitize + translate LTLf → LTL via `spot::from_ltlf`, applied to individual
      properties inside `check_compliance` (not a bulk pre-translation pass) and, for the atom
      side, in `property_ingest.py` (Option B — collapse and quote lifecycle atoms). The strong-`X`
      rewrite noted here didn't end up needed: today's checkable P1 tier uses only `!`/`W`, and
      only P3 (out of scope, see (c)'s sibling exclusion) uses `X` at all.
   b. ✅ **Done, but check-local, not lifted-automaton-wide.** Rather than instrumenting every
      lifted automaton with `alive` at Phase A (perturbing Phase B/C, exactly the risk this bullet
      flagged), `check_compliance` builds a fresh `alive`-extended *copy* of `code_aut` internally
      (`instrument_alive_extension()`) only when needed, and only when the automaton has no genuine
      cycle. Phases A/B/C are untouched. See [[Module 03 - Equivalence Engine/Module 03 Knowledge|Module 03 Knowledge]] for the full mechanism and the mutual-exclusion bug this surfaced and fixed in the same pass.
   c. ✅ **CP1 decided and D2 implemented 2026-07-29 — call-order lifting is required, not optional, and is now live.**
      Follow-up investigation found the actual obstruction is graph *scope*, not atom naming: a
      WIR `task` node is a function definition, and the C++ lifter never reads inside function
      bodies at all, so task atoms (function names) and gateway atoms (guard text) **never share
      a single automaton** (confirmed 0/184 on the real corpus, independently reproduced).
      No renaming scheme fixes two atoms living in different graphs. Closing this for real means
      changing what Phase A lifts (call-sites instead of definitions) and connecting orchestrator
      to callee sub-CFGs. Cross-tabbing the first real 58-check run against independently-derived
      ground truth (actual call order, not definition order) settled CP1: **13/18 `VIOLATION`
      verdicts (72%) are spurious or contradicted by real call order; 12/17 `COMPLIANT` verdicts
      (71%) ride on omission-blindness. Only ~10/35 (29%) definitive verdicts are trustworthy
      as-is.** See [[Module 03 - Equivalence Engine/Bridge Investigation/CP1 Lifting-Scope Decision|CP1 Lifting-Scope Decision]]
      for the full cross-tab and script. Note the scope split this finding surfaced: call-order
      lifting fixes the ordering side (the 13/18) but **not** the omission side (the 12/17) — that
      needs the separate coverage-tier property class (item 4a's `F`-bearing family, M4.1 in the
      Claude Science D4 plan), not D2 itself. **Implemented**: new `derive_call_order_wir()`
      (`module_02_extract/src/ast_extractor/call_order_view.py`), additive alongside
      `CFGExtractor.extract()` — lifts the driver function's own CFG (reusing existing branch/guard
      machinery) instead of module-level definition order, and marks call-sites to sibling
      top-level functions as task boundaries. Validated against the discriminating uid 44/uid 77
      pair and the full 29-variant corpus: verdicts moved exactly as CP1 predicted (`{VIOLATION: 5,
      COMPLIANT: 10, INCONCLUSIVE: 43}`, down from `{18, 17, 23}`), with no regressions in either
      module's test suite. Full detail: [[Module 03 - Equivalence Engine/Bridge Investigation/CP1 Lifting-Scope Decision|CP1 Lifting-Scope Decision]].
      **Not yet done**: no committed caller wires this into a real end-to-end run yet — the
      corpus re-run used a scratchpad script, same gap item 7 (E2E evaluation harness) already
      names.
   d. ✅ **Done.** Vacuity guard: `check_compliance` no longer trusts a `COMPLIANT` verdict on a
      non-empty-but-dead-ending automaton without genuinely checking it (the acceptance-condition
      fix). `NON_TERMINATING` reporting (a real loop vs. an ordinary violation) is **still an open,
      explicit design decision** — the fix only bridges the finite/dead-ending case; a genuine
      cycle skips the bridge and uses the original unbridged check, deliberately not deciding what
      it should report against a property that itself requires termination.
   e. ✅ **Done.** P0 reclassified as a lifting self-test (`tier_semantics`); atom-matching gate
      reports `INCONCLUSIVE`, never `VIOLATION`, on an atom absent from the code automaton (PR #67).
   Still applies: test edge cases (empty traces, loop-bound interaction with M01's
   `loop_bound_documented` field — note the investigation found this field currently defaults
   to `0` in practice, not the documented `3`, a separate bug worth filing).
   **Caution from the investigation, and how it was actually resolved:** the investigation said do
   not treat "wire the P1 tier" as a safe step while (c)'s ordering defect stands. It has now been
   wired anyway (2026-07-29, item 3) — deliberately, as the walking-skeleton's proof-of-wiring step,
   with results reported explicitly as **definition-order, provisional** rather than a conformance
   claim. The first real run (58 checks, `{VIOLATION: 18, COMPLIANT: 17, INCONCLUSIVE: 23}`) is the
   real-failure data (c)'s "wait and see" was for — CP1 (below) is now decidable from it, not from
   the earlier emulated projection.
5. **Declare the canonical Phase D.** Two flavors now coexist: legacy Python reachability-BFS in `run_pipeline` and SPOT LTL in `process_wir_batch`. Pick one, mark the other deprecated, and say so in the docs — ambiguity here will be challenged at defense.
6. **First end-to-end demo.** One BPMN spec → M01 suite → M03 check against a conforming and a non-conforming LLM implementation → PASS, and FAIL + readable counterexample. This is the money shot for the thesis and the demo.

## P2 — Make it measurable and defensible

7. **E2E evaluation harness.** Extend M02's eval methodology (the strongest part of the project) to the full pipeline: FLOW-BENCH's 101 BPMN workflows give spec↔code pairs for free. Measure spec-conformance detection rate, false-alarm rate, and counterexample quality/usefulness. Report with CIs, as M02 already does.
8. **Module 01 tests — third cycle with zero.** Gates, PBCTS convergence (IDCD), SCSL rounds, and the status codes are entirely unexercised. Minimum: gate boundary tests, a converging and a non-converging PBCTS fixture, and a regression test for the startup bug. No more Phase rewrites without tests landing in the same commit.
9. **CI.** `.github/` holds only CODEOWNERS. Add a workflow: per-module tests + a docker-compose build check. M01's startup crash would have been caught by a one-line `uvicorn` smoke test.
10. **Fix M01 status-code inconsistency** — `FAIL_ALIGNMENT_UNPROVEN` (api.py) vs `PASS_PBCTS_UNCONVERGED` (main.py) for the same outcome. Downstream consumers need one vocabulary.

## P3 — Hygiene and honest accounting

11. **Drop SPOT from M01's Dockerfile** (dead weight since the PBCTS pivot; nothing imports it) and fix `formula_normalizer.py` docstrings that still promise "SPOT-compatible grammar."
12. **M02 certificate honesty items:** V2 contributes ≈ nothing on the current corpus (certificate is V1-driven), equivalent-mutant specificity is 0.1111, numeric-boundary bugs are a known blind spot. Either expand the corpus to exercise V2 or reframe the "multi-modal" claim in the thesis. The eval already states these openly — keep it that way.
13. **Cleanup:** unused `networkx` in M04 requirements; M03 `main.py` is a stale P1.1 milestone demo — replace with the real pipeline entrypoint or remove.
13a. **M02 test suite hang, found 2026-07-29, not yet diagnosed.** `pytest module_02_extract/tests/test_ast_extractor.py::TestWIRDataLayer` (and, apparently, `TestV3Certificate`/`TestEndToEnd` — all three call `run_v3_pipeline`) hangs indefinitely under Python 3.9 rather than failing or passing. Confirmed pre-existing and unrelated to the D2 lifting-scope change via `git stash` (reproduces identically on HEAD without it). Not diagnosed further — worth a real look, since a hang (vs. a clean failure) is exactly the kind of thing that silently breaks CI.
14. **Thesis parity:** only M02 has a Chapter 5 draft. Once P1 lands, M01/M03 need equivalent write-ups (PBCTS/EAS_BDA/IDCD/SCSL on one side, divergence-sensitive bisimulation + SPOT compliance on the other).

## Risks to manage

- **Vacuity-vs-divergence tension (new, 2026-07-29).** The `alive` reduction needed for P1.4 is
  unsatisfiable on a trace that never terminates, so a hallucinated `while True: pass` would
  report VIOLATION on every property — technically defensible, but it flattens exactly the
  distinction Phase B's divergence-sensitivity was built to preserve (diverged vs. reached-a-
  bad-state). Needs an explicit `NON_TERMINATING` verdict decision before P1.4 ships — see
  [[Module 03 - Equivalence Engine/Bridge Investigation/P1.4 Bridge Findings|P1.4 Bridge Findings]].
- **Pivot churn.** Two architectural pivots in two days (SPOT→HOA→PBCTS), each deleting the prior day's work including tests. Freeze the architecture after the LTLf→LTL bridge decision; further changes need a written rationale first.
- **Docs drift.** `docs/` was removed from the repo and survives only in this vault + git history. Decide where living documentation lives, or the vault becomes write-only archaeology.
- **Demo dependency chain.** P0 items block any live demo; P1 blocks the e2e claim. Sequence accordingly before any evaluation freeze or demo date.

## Suggested order of attack

```
P0.1  →  P0.2  →  P1.3 (ingestion)  →  P1.4 (LTLf→LTL bridge)  →  P1.6 (e2e demo)
       →  P2.8 (M01 tests) + P2.9 (CI) in parallel
       →  P2.7 (e2e eval) once the demo runs
       →  P3 hygiene + thesis write-ups
```

## Links

- [[Home]]
- [[Claude Science Plan]] — how a Claude Science project applies to executing this roadmap, incl. a ready-to-use P1.4 bridge-design prompt
- [[Module 03 - Equivalence Engine/Bridge Investigation/P1.4 Bridge Findings|P1.4 Bridge Findings]] — the bridge investigation's output: vacuity bug, AP vocabulary gap, revised scope
- [[Module 03 - Equivalence Engine/Bridge Investigation/AP Vocabulary and Lifting Scope Findings|AP Vocabulary and Lifting Scope Findings]] — the deeper finding: task=function-definition, sub-CFGs unread, ~46% ordering mismatch
- [[Project Status.canvas|Project Status]]
- [[Module 01 - Specification Analysis/Module 01 Knowledge]] · [[Module 02 - Verified IR Extraction/Module 02 Knowledge]] · [[Module 03 - Equivalence Engine/Module 03 Knowledge]] · [[Module 04 - Verification Portal/Module 04 Knowledge]]
