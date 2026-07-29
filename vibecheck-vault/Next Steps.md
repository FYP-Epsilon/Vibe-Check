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
5. ✅ **Canonical Phase D declared — done 2026-07-30.** `process_wir_batch` (SPOT/C++) is canonical —
   every real caller already used it (module_03_equiv's `/check` endpoint, `demo/e2e_demo.py`, every
   corpus run). `run_pipeline` (legacy Python reachability-BFS) is now marked LEGACY in its own
   docstring, `pipeline.py`'s module docstring, and its CLI banner; `test_pipeline.py`'s 37 direct
   component tests are untouched (deprecated ≠ untested — they validate real bisimulation/clustering
   logic). Also fixed an adjacent false comment (`# gracefully degrade to pure-Python if not
   compiled` on the `vibecheck_lifter` import) — `process_wir_batch` actually raises `RuntimeError`
   when the C++ engine is missing; there is no fallback relationship between the two pipelines.
   **Named, not silently dropped: loop-bound safety checking has no home in the canonical path.**
   `run_pipeline`'s Phase D checks two things — forbidden-label reachability (subsumed by
   `check_compliance`, expressible as an LTL safety property) and loop-bound safety
   (`PropertyMonitor.from_loop_bound_check()`, which is NOT expressible via the current property
   suite — `property_ingest.py` excludes P2_Quality_Limits from conformance checking). Declaring
   `run_pipeline` legacy therefore leaves loop-bound checking unimplemented anywhere in the real
   pipeline; that's an open gap, tracked here rather than papered over. See [[Module 03 -
   Equivalence Engine/Module 03 Knowledge|Module 03 Knowledge]] for the doc-level decision record.
6. ✅ **First end-to-end demo — done 2026-07-30.** `demo/e2e_demo.py`: BPMN spec → Module 01's real
   `export_for_module_03()` → Module 02's `derive_call_order_wir()` (the D2 fix) → Module 03's
   `process_wir_batch`/`check_compliance` → PASS/FAIL + a readable counterexample, run against the
   real FLOW-BENCH corpus and the real compiled `vibecheck_lifter` engine (no mocks, no scratchpad
   hardcoding). Verified end-to-end, output reproduced below. Regression tests:
   `demo/test_e2e_demo.py` (3 tests, skipped like `test_cpp_engine.py` if the C++ engine isn't
   compiled).
   - **`demo/e2e_demo.py` itself is in-process, by design**: it imports all three modules' Python
     packages directly in one process, honestly documented in its own docstring as crossing the
     module boundary *for demo convenience*. Production still deploys each module as its own
     container with no access to the others' source (`docker-compose.yml`), unchanged by this.
   - **The real HTTP chain (spec-engine → extract-engine → equiv-engine, docker-compose) is now
     also verified — done 2026-07-30.** `docker compose build && docker compose up -d` (all 4
     images build and run; Docker Desktop turned out to be available in this environment after
     all — the earlier "too slow to build here" note was based on a non-Docker local SPOT build,
     not an actual attempt). Ran the exact same uid 44 / uid 77 chain over real HTTP calls between
     the real containers (`spec-engine:8000/verify` → `extract-engine:8000/verify` →
     `equiv-engine:8000/check`) and got **identical results** to the in-process demo:
     `{2 VIOLATION, 1 COMPLIANT} / FAIL` for uid 44, `{1 COMPLIANT, 1 INCONCLUSIVE} / PASS` for
     uid 77. Two more real, previously-undiscovered production bugs found and fixed in the process
     — **`extract-engine`'s container had never successfully started until now**:
     1. `z3_sym_engine/__init__.py`, `z3_sym_engine/{tracer,evaluator,concolic}.py`, and
        `dynamic_tracer/__init__.py` all had `from .ast_extractor import ...` (single dot) where
        `ast_extractor` is a *sibling* of `z3_sym_engine`/`dynamic_tracer`, not a child — needed
        `from ..ast_extractor import ...` (two dots). The relative import raised `ImportError`,
        silently caught by each file's own `except ImportError: from ast_extractor import ...`
        fallback, which *also* failed in the container (only `/app` is on `sys.path`, not
        `/app/src`) with a misleading `ModuleNotFoundError: No module named 'ast_extractor'` that
        masked the real bug. Pre-existing since the `54cc3a2` z3_sym_engine-package-split refactor;
        unrelated to anything this session touched in those files. Fixed all 5 occurrences.
     2. `_run_verification`'s unconditional `source.replace('\\n', '\n').replace('\\t', '\t')`
        corrupted any source whose *own* string literals contain a genuine `\n`/`\t` escape (an
        f-string like `f"a\nb"` is valid Python; the replace turned its literal backslash-n into a
        real newline character in the source *text*, breaking the literal and failing
        `ast.parse`) — confirmed against **13/184 real FLOW-BENCH corpus variants**, all 13 now
        parse correctly after removing the line entirely (no legitimate reason for a JSON API to
        need it — `requests`/any proper JSON client already decodes `source_code` to the exact
        literal text the client's file contains; M04's own `app.py` already sends it correctly).
        Regression tests added (`TestLiteralEscapesInStringLiteralsNotCorrupted`).
   - **"Conforming vs non-conforming" is two specs, not one, stated plainly**: cross-tabbing the
     real corpus (`second_real_run_results.json`) found no single spec where different real LLM
     implementations produce different verdicts — every spec's variants behave identically. The
     demo shows uid 44 (real ordering violations, both real LLM variants) and uid 77 (a real
     compliant case) rather than hand-mutating a variant to force one spec to show both.
   - **Two real bugs found and fixed while building this, not just wiring**:
     1. `export_for_module_03()`'s `tier_semantics` only ever covered 3 of the 5 tiers
        `refined_ltlf_property_suite` can contain (`mutation_refiner.py`'s `_certify()` always emits
        all 5) — so the **real** M01 export function, unlike every prior scratchpad script's
        hardcoded complete dict, made `load_property_suite` hard-error on any real spec whose suite
        included a `P3_Adversarial_Defenses` or `synthesized_mutant_killers` property. Fixed in
        `module_01_spec/src/api.py`; regression test added
        (`test_real_export_is_ingestible_by_module_03`).
     2. `check_compliance`'s raw `counter_example_trace` is a full BDD state dump (every registered
        atom, positive or negated, including the `alive` bridging atom and unrelated gateway
        guards) — not remotely what "readable counterexample" means. New
        `module_03_equiv/src/counterexample.py` (`format_counterexample`) is a presentation layer
        that filters the raw trace down to just the violated property's own atoms and renders a
        plain task sequence (e.g. `PriceLevel → SalesOrder`). Does not change what
        `check_compliance` itself returns — the raw trace is still the ground truth underneath.
   - **Real output** (uid 44, `44__llama-3.1-8b.py`): 2 `VIOLATION` (readable counterexamples:
     `PriceLevel → SalesOrder`; `Invoice` alone, since `PriceLevel` never occurs at all in this
     run — a real, correctly-detected omission-as-violation case), 1 `COMPLIANT` → **OVERALL: FAIL**.
     uid 77 (`77__llama-3.1-8b.py`): 1 `COMPLIANT`, 1 `INCONCLUSIVE` (the never-called
     `COPY_OBJECT` task, correctly not claimed as a verdict) → **OVERALL: PASS**.

## P2 — Make it measurable and defensible

7. ✅ **E2E evaluation harness — done 2026-07-30.** `demo/eval_e2e/` (`mutate.py` +
   `harness.py` + tests). Ground truth: FLOW-BENCH has no native correctness labels
   (`.claude/memory/flowbench_groundtruth_finding.md`), so this extends M02's own
   mutation-based methodology (Clopper-Pearson CIs, ported not imported — see
   harness.py's module docstring for the Python-3.9-vs-3.10+ reason) to the full
   M01→M02→M03 pipeline: 6 real (BPMN, LLM-implementation) pairs confirmed
   end-to-end `COMPLIANT` serve as "gold," mutated two ways — `drop_step`/
   `swap_adjacent` (order-changing, candidate detection-rate positives) and
   `perturb_constant` (verified order-preserving, false-alarm-rate negatives).
   First real run (26 order-mutation trials, 2 perturbation trials — n is small,
   reported with CIs throughout, not hidden):
   - **Real finding, checked not assumed:** dropping a task's call entirely often
     makes that task's own atom unobservable, so the pipeline correctly abstains
     (`INCONCLUSIVE`) rather than emitting a wrong `COMPLIANT` — **not** a
     detection failure. Abstention rate 0.462 (95% CI [0.27, 0.67], n=26),
     reported separately and excluded from the detection-rate denominator.
   - **Detection rate** (of decisive trials only): 0.357 (95% CI [0.13, 0.65],
     n=14). By kind: `drop_step` 0/16 detected (12 abstained, 4 genuine misses),
     `swap_adjacent` 5/10 detected.
   - **False-alarm rate**: 0/2 (95% CI [0.00, 0.84]) — small n, wide interval,
     stated plainly.
   - **Counterexample quality** (does the rendered counterexample name every task
     the violated property's own formula references — a narrow, mechanical
     yes/no, not a subjective rubric): 0.8 (95% CI [0.28, 0.99], n=5).
   Full report: `demo/eval_e2e/results/e2e_eval_report.md` /
   `e2e_eval_results.json`. Regression tests: `test_mutate.py` (pure AST logic,
   always runs) + `test_harness.py` (pins uid 77's exact mutation outcomes,
   skipped like `test_cpp_engine.py` if the C++ engine isn't compiled).
8. ✅ **Module 01 tests — done 2026-07-30.** 4 new files, 26 tests total
   (module_01_spec/tests/), covering exactly the roadmap's stated minimum:
   - `test_phase1_gate.py` (6 tests) — Phase 1's node-coverage gate boundary
     (`_layer_v1_certify`), both directly (white-box, hits the exact `>= 1.0`
     threshold) and via real BPMN XML, including the self-healing recovery
     pass and a genuine unrecoverable-FAIL case (a non-BPMN-namespaced element
     with an `id`, which V3's namespace-blind counting flags but neither V2
     nor the recovery pass — both BPMN-namespace-scoped — can ever map).
   - `test_phase3_gate.py` (5 tests) — Phase 3's mutation-kill gate boundary
     (`MutationValidator._certify`, `C_struct >= 1.0 AND killed_ratio >= 1.0`)
     plus one real end-to-end `execute_validation_pipeline()` run.
   - `test_pbcts_convergence.py` (4 tests) — IDCD convergence (a real
     converging fixture, and `k_max=1` as the cleanest deterministic way to
     pin the non-converging path, since the convergence check itself requires
     `k > 1`) and SCSL correction synthesis (`_compute_corrections`), both a
     genuine-gap case and a no-correction case.
   - `test_main_api.py` (6 tests) — the startup-bug regression (`main.py`
     must always import cleanly) plus the status-code vocabulary across all
     paths: 400 (empty XML), 500 `UNEXPECTED_ERROR` (malformed XML — no
     specific handler exists for this, noted as a gap item #10 should also
     cover), 422 `PHASE_1_GATE_FAIL`, and the happy path's `PASS` /
     `PASS_PBCTS_UNCONVERGED` vocabulary.
   Two real things found while writing these, not assumed:
   - An empty/degenerate diagram (0 executable nodes) **fails** Phase 1's
     gate rather than vacuously passing — the `> 0` guard only prevents
     division by zero, it doesn't special-case coverage to 1.0.
   - `module_01_spec/src/main.py` and `module_03_equiv/src/main.py` share the
     bare module name `main` — running both modules' test suites in one
     pytest session, a plain `import main` after
     `test_export_for_module_03.py`'s `test_real_export_is_ingestible_by_module_03`
     (which inserts `module_03_equiv/src` onto `sys.path` ahead of
     `module_01_spec/src`) silently resolves to the *wrong* file. Worked
     around in `test_main_api.py` via `importlib.util.spec_from_file_location`
     under a private module name; not fixed at the source level (renaming
     either `main.py` would be a larger, unrelated change) — flagged here in
     case a future CI run (item #9) hits the same collision.
   Full suite: 26/26 pass; cross-checked against module_02_extract/tests/ and
   demo/ in the same pytest session for further collisions — only the
   pre-existing, unrelated `sys.monitoring` gap (item #13a) shows up.
9. ✅ **CI — done 2026-07-30.** `.github/workflows/ci.yml`: 4 per-module test
   jobs (module_01, module_02, module_03, cross-module `demo/`) on Python 3.11
   matching each service's own Dockerfile, plus a 5th job that is the actual
   point of this item — `docker-compose-smoke` — which does not stop at
   `docker compose build`. Both real incidents this item exists to prevent
   (M01's deleted-`automata_lifter` import crash, item #6's discovery that
   `extract-engine` had never once started in this project's history) built
   their images cleanly and only crashed at `uvicorn` startup, so a
   build-only check would have caught neither. The smoke job instead: brings
   the real stack up (`docker compose up -d`), fails if `docker compose ps`
   shows any container outside the `running` state (the one check that
   would have caught both incidents directly, verified locally against a
   real `docker compose up` run before committing), then confirms each
   service actually answers a request — `spec-engine`'s `/`, `extract-engine`'s
   `/docs` (its only route is `POST /verify`, so this is the most
   business-logic-neutral proof `uvicorn` is routing), `equiv-engine`'s
   `/health`, all three reached via `docker compose exec` + Python `urllib`
   from inside the compose network since only `ui-engine`'s port is
   published to the host in `docker-compose.yml`; `ui-engine` itself is
   curled directly on `localhost:8501`. Every one of these commands was run
   for real against this repo's actual containers before being committed to
   the workflow, not just written and hoped to work.
   `module_02_extract/tests/test_dynamic_tracer_parity.py::test_monitoring_matches_settrace`
   is explicitly `--deselect`-ed with an inline comment citing item #13a
   (asserts `sys.monitoring`, Python 3.12+ only — CI runs 3.11 to match
   production) rather than either left permanently red or silently hidden;
   remove the deselect once #13a is resolved. All 4 test jobs pass cleanly
   in this configuration (module_01 26/26, module_02 161/161 after the
   deselect, module_03 59 passed + 83 skipped, demo 8 passed + 6 skipped —
   the skips are the existing, intentional `skipif(not HAS_MODULE)` convention
   for the uncompiled C++ engine, not new gaps).
10. ✅ **Fix M01 status-code inconsistency — done 2026-07-30.** `api.py`'s
    `run_module_01_pipeline()` said `FAIL_ALIGNMENT_UNPROVEN`, `main.py`'s
    `/verify` said `PASS_PBCTS_UNCONVERGED`, for the identical outcome
    (PBCTS completed, IDCD just didn't converge within budget). Unified on
    `PASS_PBCTS_UNCONVERGED` — confirmed correct, not just consistent:
    `export_for_module_03`'s own FAIL-blocklist (`["FAIL",
    "FAIL_WITH_ERRORS"]`) never included either variant, so an unconverged
    result has always been treated as valid, exportable output by this
    codebase's own actual behavior. The `FAIL_ALIGNMENT_UNPROVEN` name was
    the one disagreeing with reality, not `PASS_PBCTS_UNCONVERGED`.
    New test (`test_status_code_consistency.py`, 2 tests) runs one real
    BPMN fixture through both `run_module_01_pipeline()` and `verify_spec()`
    and confirms they now genuinely agree, plus confirms the unconverged
    result stays exportable. `impact()` on `run_module_01_pipeline` flagged
    HIGH risk (its usual callgraph-fanout position, not this change
    specifically) — cross-checked: none of the 3 real callers
    (`demo/e2e_demo.py`, `demo/eval_e2e/harness.py`) inspect the `status`
    string at all, so behavior is unchanged for all of them. Full
    `module_01_spec` suite: 28/28 pass.

## P3 — Hygiene and honest accounting

11. ✅ **Drop SPOT from M01's Dockerfile — done 2026-07-30.** Confirmed dead
    weight before removing anything: `formula_normalizer.py` is the only
    file mentioning SPOT, only in docstrings/comments, and is never
    imported by `api.py`/`main.py` (grep, zero hits) — `impact()` on
    `FormulaNormalizer` independently confirms 0 upstream callers, LOW risk.
    Removed the entire from-source SPOT 2.11.6 build (`wget`/`configure`/
    `make install`, several minutes per build) and the `apt-get` toolchain
    that existed only to support it (`build-essential`, `g++`, `cmake`,
    `pkg-config`, `wget`, `tar`, `python3-dev`) — none of `fastapi`/
    `uvicorn`/`networkx` need compilation, confirmed by the trimmed
    Dockerfile's build log installing pure wheels only. Rebuilt
    `spec-engine` for real (~8s vs. several minutes before), started it,
    and ran a full real `/verify` request through all 4 phases inside the
    container — `PASS_PBCTS_UNCONVERGED` end to end, not just a root-route
    ping. Also fixed `formula_normalizer.py`'s docstring: it now states
    plainly that the class is unused, and — a separate, more important
    fact than just being dead code — that its own normalization scheme
    (`start(X)` → `start_X`/`done(X)` → `done_X`, kept as separate atoms)
    doesn't even match what `property_ingest.py`'s real, ported normalizer
    does today (collapses `start`/`done` into one flat quoted atom per
    task) — so this class couldn't be resurrected as-is even if it were
    wired back in.
12. ✅ **M02 certificate honesty items — done 2026-07-30.** Checked before
    writing anything: the deep technical writeup
    (`Module_02_Verified_IR_Extraction.md` §10.6/§10.7) and the informal
    `Module 02 Knowledge.md` already stated the V2-near-zero-contribution
    finding and the 0.1111 equivalent-mutant specificity honestly — "the
    eval already states these openly" was already true there. The gap was
    in the *prominent, early* claims a reader hits first: `00_overview.md`
    (Module 02's architecture-overview doc, no limitations section at all)
    and the novelty section (§5.1) and novelty summary table (§5.5) of the
    comprehensive writeup both presented "multi-modal certificate" as an
    unqualified three-way combination, only pointing forward to §10.6/§10.7
    without stating the finding — a reader who stopped at the architecture
    or novelty sections would come away thinking all three modalities
    meaningfully combine. Added an inline caveat to `00_overview.md`
    (stated at the point the three-layer table itself is introduced, not
    buried afterward) and strengthened §5.1 and the §5.5 table in
    `Module_02_Verified_IR_Extraction.md` to state the V1-dominance finding
    directly rather than only cross-reference it. Chose "reframe the claim"
    over "expand the corpus" — expanding the corpus to genuinely exercise
    V2 is a real eval-design effort, out of scope for a documentation-
    honesty pass. No code changed; `Module 02 Knowledge.md` and the eval
    reports themselves were already correct and left untouched.
13. ✅ **Cleanup — done 2026-07-30.** Removed `networkx` from
    `module_04_ui/requirements.txt` — confirmed genuinely unused (grep,
    zero hits anywhere in `module_04_ui/src/`, the module's only Python
    file), then rebuilt and started `ui-engine` for real and confirmed it
    still serves `200` on `/` without it. The item's other half — "M03
    `main.py` is a stale P1.1 milestone demo" — is now stale wording, not
    a remaining task: `main.py` was rewritten into the real FastAPI
    service (`/lift`, `/check`, `/health`) back in PR #74, earlier this
    session, before this item was ever reached.
13a. ✅ **M02 test suite Python-version-sensitivity — diagnosed and fixed
     2026-07-30.** Both gaps traced to real, distinct root causes rather
     than left as "not yet diagnosed":
     - **The 3.9 hang (real bug, now fixed).** Root cause is
       **networkx-version-dependent, not Python-version-dependent per
       se** — the two only correlate in this project's two dev venvs.
       `nx.immediate_dominators`'s entry-node convention differs across
       networkx releases: confirmed `idom[entry] == entry` on networkx
       3.2.1 (this project's Python-3.9 venv, where the hang was
       reproduced and pinned via `SIGABRT` + `faulthandler`, landing the
       stuck frame inside `dominators.py`'s `_dominates`), and entry
       simply omitted from the dict on networkx 3.6.1 (the Python-3.11
       venv, where it doesn't hang). `compute_dominance_frontier()` built
       its own `idoms` dict raw from whichever networkx returns, unlike
       `compute_immediate_dominators()` next to it, which already
       normalized self-mapping to `None` — so on a self-mapping networkx
       version, the frontier walk's `idoms.get(cur)` climb never reaches
       `None` once it hits `entry`, looping forever. Fixed by applying
       the same normalization in both places
       (`module_02_extract/src/ast_extractor/dominators.py`).
       **A second, independent correctness bug was found while fixing
       the first**: the frontier loop's stopping condition compared
       `_dominates(node, runner)` instead of the textbook Cytron et al.
       `runner != idom(node)`. Domination only flows ancestor→descendant
       in the idom tree, so a node essentially never dominates its own
       idom-chain ancestors — the old condition almost never fired, so
       the walk over-ran all the way to the root. Confirmed wrong on a
       plain diamond CFG (produced `frontier[entry] = {merge}`, when
       entry — dominating the entire reachable graph — must have an
       empty frontier) and fixed to compare against the node's own
       immediate dominator directly. `compute_dominance_frontier()`'s
       output (`wir["dominance_frontier"]`) is currently inert in
       production — confirmed by grep, nothing downstream reads it, and
       it isn't in `shared_schemas/wir_schema.json` — but the infinite
       loop itself was a real, live risk: `run_v3_pipeline` (module_02's
       actual `/verify` entrypoint) calls straight into it, so any real
       request hitting a self-mapping networkx version could have hung
       the extract-engine process indefinitely. Zero prior test coverage
       for `dominators.py` — new `test_dominators.py` (8 tests) pins both
       fixes on diamond and nested-diamond CFGs, cross-version-safe
       (checks via `.get()`, not exact dict shape, since the
       entry-key-presence quirk itself differs across networkx
       versions).
     - **The 3.11/3.12 `sys.monitoring` mismatch (fixed).**
       `test_dynamic_tracer_parity.py`'s `test_monitoring_matches_settrace`
       hard-`assert`ed `sys.monitoring is not None`, which doesn't exist
       at all before Python 3.12 (PEP 669) — a hard fail, not a graceful
       skip, on the Dockerfile's pinned 3.11. The runtime tracer's own
       settrace fallback on <3.12 is real, intentional, documented
       behavior (see the module's own docstring), not a gap this test
       should fail on. Replaced the hard assert with
       `@pytest.mark.skipif(getattr(sys, "monitoring", None) is None,
       ...)`, so the 9 parametrized cases now skip cleanly instead of
       failing. This closes the loop item #9 opened: removed the
       `--deselect` workaround from `.github/workflows/ci.yml` now that
       the test handles its own version gate.
     Full `module_02_extract` suite after both fixes: 169 passed, 9
     skipped (the now-gracefully-skipped `sys.monitoring` cases), 0
     failures — under both the Python 3.9 and 3.11 dev venvs.
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
