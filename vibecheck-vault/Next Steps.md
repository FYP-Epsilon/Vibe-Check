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

1. **Fix M01 startup crash.** `main.py:11,16` imports the deleted `automata_lifter`; the FastAPI app and Docker `uvicorn` CMD raise `ModuleNotFoundError` on startup. The `/verify` route never uses the import — delete it. The spec-engine service is down until this lands.
2. **Fix M04 equivalence page.** It does an in-process `import vibecheck_lifter` inside the `ui-engine` container, which has no SPOT — broken by construction. Route it over HTTP to the equiv-engine container like the Spec/Extract pages, and make the health check symmetric (`GET /docs`, not a local import).

## P1 — Close the end-to-end loop (the research-critical path)

3. **M03 ingestion of `module_03_input.json`.** Zero references to it exist in `module_03_equiv`. Add the loader and feed the real property suite into `process_wir_batch()` in place of the placeholder. This is mostly plumbing.
4. **LTLf→LTL semantic bridge — scope revised 2026-07-29 after investigation**
   ([[Module 03 - Equivalence Engine/Bridge Investigation/P1.4 Bridge Findings|full findings]]).
   Confirmed: SPOT 2.11.6 (the exact vendored version) ships `spot::from_ltlf()`, so formula
   translation itself is close to solved. But translation alone is **worse than useless** —
   `check_compliance` is vacuously `COMPLIANT` on any non-looping automaton today, because the
   lifter never sets an acceptance condition (confirmed against source); shipping only the
   formula bridge would produce a confident, uniformly-passing verdict on arbitrary code. This
   item is now four sub-parts, not one:
   a. Sanitize + translate LTLf → LTL via `spot::from_ltlf`, after rewriting strong `X` to
      `X[!]` (Module 01's `X` is strong, SPOT's bare `X` is weak — silent mismatch otherwise).
      Replace the dead, incomplete `FormulaNormalizer` rather than extending it.
   b. Instrument lifted automata with the `alive` AP on the Phase D path only — leave Phases
      B/C untouched, since Phase B's divergence-sensitivity is a deliberate result that
      shouldn't be perturbed by a Phase D concern.
   c. **Superseded — the vocabulary gap turned out to be a symptom, not the root cause.**
      Follow-up investigation found the actual obstruction is graph *scope*, not atom naming: a
      WIR `task` node is a function definition, and the C++ lifter never reads inside function
      bodies at all, so task atoms (function names) and gateway atoms (guard text) **never share
      a single automaton** (confirmed 0/184 on the real corpus, independently reproduced).
      No renaming scheme fixes two atoms living in different graphs. Closing this for real means
      changing what Phase A lifts (call-sites instead of definitions) and connecting orchestrator
      to callee sub-CFGs — sized but explicitly **not recommended for implementation yet**, see
      the reprioritization flag above and the linked findings note.
   d. Add a vacuity guard before trusting any `COMPLIANT` verdict (non-empty language + every
      formula AP present on some edge), and decide how to report the `NON_TERMINATING` case
      (see risk below) separately from an ordinary property violation.
   e. **New, safe to do now, independent of (c)'s scope decision:** reclassify Module 01's P0
      tier as a lifting self-test rather than evidence about code correctness — it's now proven
      (not just observed) unfalsifiable under *any* lifting design, since the property and the
      faithful-lifting invariant are logically identical. And gate atom matching: any property
      referencing an atom absent from the code automaton should report `INCONCLUSIVE`, never
      `VIOLATION` — confirmed that unmatched atoms currently produce false violations on
      *correct* code, which is worse than the vacuity problem it sits alongside.
   Also still applies: test edge cases (empty traces, loop-bound interaction with M01's
   `loop_bound_documented` field — note the investigation found this field currently defaults
   to `0` in practice, not the documented `3`, a separate bug worth filing).
   **Caution carried over from the investigation itself:** do not treat "wire the P1 tier" as a
   safe near-term step on its own — P1's flagship shape is an ordering property, and the ordering
   defect in (c) makes any wiring unreliable while it stands. Only (d) and (e) above are safe to
   do independent of the scope decision.
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
