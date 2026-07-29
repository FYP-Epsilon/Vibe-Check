# Module 03 — Equivalence Engine

Module 03 is the **convergence point of VibeCheck**. It compares the spec automaton (**M_spec**, produced by Module 01) against the code's **WIR** (produced by Module 02) and returns **PASS**, or **FAIL plus a counterexample trace** showing where the code's behavior diverges from the BPMN 2.0 specification.

## The Four Phases

- **Phase A — Lifter**: lifts the WIR into a Labeled Transition System (LTS). Action names are matched with a cascade — **exact → edit-distance → Sentence-BERT** — and an `unlabeled_task` fallback guarantees unmatched actions cannot silently slip through. Loops are handled by bounded unrolling. *(Python ✅ / C++ ✅)*
- **Phase B — Divergence-sensitive stuttering bisimulation**: compresses the LTS while preserving divergence. It refuses to merge a silently-infinite loop (e.g. a hallucinated `while True: pass`) with a normal wait state — plain stuttering equivalence would treat them as identical. Three equivalence tiers: **functional / trace / process**. *(Python ✅ Groote–Vaandrager + Tarjan SCC / C++ ✅ G–V `partition_refinement` + `spot::scc_info` τ-cycle collapse)*
- **Phase C — Behavioral clustering**: groups bisimulation-reduced automata so that verifying N LLM implementations costs roughly **#distinct behaviors**, not N full model-checking runs. *(Python ✅ hashing / C++ ✅ `cluster_implementations` via `spot::isomorphism_checker::are_isomorphic`, representative = min states then min edges, shared-`bdd_dict` precondition)*
- **Phase D — Model checking**: synchronous product of the behavior automaton with a violation automaton → emptiness check → **PASS**, or **FAIL + counterexample**. *(C++ ✅ textbook SPOT: `parse_infix_psl` → ¬φ → Büchi via `spot::translator` on the code automaton's own `bdd_dict` → `spot::product` → `is_empty()` + `accepting_run()` counterexample, prefix+cycle formatted — exposed as `check_compliance(code_aut, ltl_string)` returning `ComplianceResult`. Python legacy: `model_checker.py` finite-trace reachability-BFS survives only in `run_pipeline`.)*

## Two Tracks

**Track 1 — Pure-Python pipeline (core ~1,470 LOC, 37 tests)** — intact, `module_03_equiv/src/`:
- `lifter.py` (461) — Phase A (`WIRLifter`, `LifterConfig`, `QualityGateError`)
- `stuttering_engine.py` (414) — Phase B (Groote–Vaandrager + Tarjan SCC)
- `clustering.py` (241) — Phase C (`BehavioralClusterer`)
- `model_checker.py` (352) — Phase D legacy (BFS product + `PropertyMonitor`)

**Track 2 — C++/SPOT engine (ALL four phases A–D implemented)**:
- `lifter.cpp` **1,262 LOC**, `lifter.hpp` 294 LOC; real SPOT throughout (`scc_info`, `simulation`, `postproc`, `are_isomorphic`, `translator`, `product`, `emptiness`).
- Pybind11 module `vibecheck_lifter` exposes `AdvancedLifter`: **Phase A** (`parse_wir_types`, `lift_to_lts`, `build_spot_automaton`, diagnostics), **Phase B** (`detect_divergent_states`, `compute_bisimulation_full`, `check_stuttering_bisimulation`, `tarjan_tau_collapse`), plus free functions **`cluster_implementations`** (Phase C) and **`check_compliance`** (Phase D, added in 12be72c).
- `pipeline.py` (432 LOC): `process_wir_batch()` now runs the **full A→D chain** — Step 5 model-checks each cluster representative against an `ltl_property` parameter and attaches `{is_compliant, verdict, counter_example_trace}`. ⚠ The default property is a **hardcoded placeholder** `'G("approved")'`.
- `nlp_utils.py` (31 lines, `all-MiniLM-L6-v2`) is a live dependency: C++ `semantic_match()` tier 3 imports it via embedded pybind11.

## Why Divergence-Sensitivity Matters

Standard stuttering bisimulation collapses τ-loops, so a generated workflow that deadlocks in a silent infinite loop (`while True: pass` — a classic LLM hallucination) would be judged equivalent to a workflow that simply waits. Divergence-sensitivity keeps those τ-cycles visible, so the equivalence verdict does not certify code that never makes progress.

## EQI Gate

Verification behavior degrades according to Module 02's extraction confidence (EQI): **full** verification, **conservative** verification, or **refuse and flag for manual review**. Low-confidence extractions never get an unqualified PASS.

## Tests

**118 test functions total** (2026-07-29 count): `test_pipeline.py` 37 (pure Python, Phases A–D + e2e), `test_cpp_engine.py` 34 (Phase A C++ + `TestPhaseD` — tautologies, looping-WIR failures, counterexample content, quotient compliance, segfault guards, the atom-matching gate, and the vacuity/mutual-exclusion regression guards), `test_phase_b.py` 28, `test_phase_c.py` 19. 115 pass; 2 fail on a pre-existing, unrelated gap (`compute_deterministic_hash` doesn't exist yet); 1 skip. All C++-side tests `skipif` the `.so` isn't compiled.

## Status & Issues (2026-07-28, main @ `7089711`)

- ✅ **C++/SPOT engine is now complete through Phase D** — real LTL model checking with counterexample extraction, wired into `process_wir_batch`; 118 tests total (115 passing, 2 pre-existing unrelated failures, 1 skip). The documented method is finally executable, and (2026-07-29) the non-looping vacuity channel is fixed and empirically validated (see below) — the remaining caveat is Phase A's action atoms still being function definitions, not business actions.
- ✅ Resolved earlier: committed Linux `.so` removed from git; `module_summery` M03 doc rewritten.
- ✅ **Module 01 ingestion now wired (2026-07-29).** New `property_ingest.py`: loads the exported suite, tier-gates (P0 excluded, only `node()`-free P1 checkable — 17.6% of the tier — P2/P3 excluded), de-duplicates, normalizes to SPOT-ready syntax (`start(T)`/`done(T)` → a single flat, **quoted** atom — quoting matters, SPOT misparses an atom starting with a reserved operator letter like `GitHub_thing` → `G(itHub_thing)`). Ported rather than cross-imported from Module 01's own `FormulaNormalizer`, since `module_03_equiv` deploys as its own container with no access to `module_01_spec`'s source. `process_wir_batch()` gained an optional `property_suite` parameter (`cluster_info["compliance_results"]`, a list); the original single-string path is untouched. **First real end-to-end FLOW-BENCH run** (M01 → ingestion → the real compiled `check_compliance`) over all 29 eligible specs: 22/29 have ≥1 checkable property, 29 variants, 58 checks, `{VIOLATION: 18, COMPLIANT: 17, INCONCLUSIVE: 23}` — matches an independent oracle-validation tally exactly. **This is definition-order lifting** (D2's lifting-scope fix is separate, unimplemented) — a walking-skeleton proof, not yet a conformance-detection measurement. That's the next real decision (CP1): whether the lifting-scope fix is worth doing, from real failures now available.
- ⛔ **Latent vacuity bug in `check_compliance`, found via the P1.4 bridge investigation
  (2026-07-29):** the lifter never sets an acceptance condition and exit states may have no
  outgoing edge, so any non-looping (terminating) code automaton has an **empty ω-language** —
  `check_compliance` returns `COMPLIANT` for *every* property, correct or not. Confirmed against
  source (no `set_buchi`/`set_acceptance`/`set_generalized_buchi` anywhere in `lifter.cpp`;
  `test_cpp_engine.py:404` documents it as intended semantics, `# vacuously true`). Dormant only
  because the sole caller passes a hardcoded placeholder — becomes a silent false-PASS the
  moment real properties are wired in. Also confirmed independently: code-side APs (bare BPMN
  task names, e.g. `Approve`) and Module 01's spec-side atoms (`start_Approve`/`done_Approve`)
  **do not intersect** — a second vacuity channel needing an event-lifecycle mapping layer.
  Full findings: [[Bridge Investigation/P1.4 Bridge Findings|P1.4 Bridge Findings]].
- ⛔ **Larger finding, found via the same investigation (2026-07-29), likely more foundational
  than the M01 bridge itself:** a WIR `task` node is a **function definition**, not a business
  action (`cfg_extractor.py:474`, its own docstring: *"a function definition is an opaque task
  boundary... the body is not inlined"*). Business calls (`approve_loan(score)`) become `block`
  nodes inside per-function sub-CFGs, which the C++ lifter **never reads at all** (confirmed —
  zero references to `functions` anywhere in `lifter.cpp`). So the C++ track's action atoms are
  function *names*, and the automaton is a chain of definitions **in definition order, not
  execution order** — measured on all 184 normalized FLOW-BENCH variants: definition order
  disagrees with call order in 47.5% of variants (independently reproduced in the vault,
  different methodology: 45.5%, same order of magnitude). Also measured on the same corpus:
  gateway nodes and task nodes **never share a single graph** (0/184, independently reproduced:
  0/184 exact match) — a structural partition that no atom-renaming can fix. Consequence: fixing
  the vacuity and vocabulary defects while this stands would produce a bridge that reliably
  model-checks the wrong automaton. Full findings, including which near-term fixes are safe
  regardless (reclassifying P0 as a lifting self-test; gating unmatched atoms to `INCONCLUSIVE`
  instead of `VIOLATION`): [[Bridge Investigation/AP Vocabulary and Lifting Scope Findings|AP Vocabulary and Lifting Scope Findings]].
- ✅ **Canonical Phase D declared (2026-07-30).** `process_wir_batch` (SPOT/C++) is canonical — it's the only path any real caller uses (module_03_equiv's own `/check` HTTP endpoint, `demo/e2e_demo.py`, every corpus-scale run this project has done). `run_pipeline` (legacy pure-Python reachability-BFS) is now explicitly marked LEGACY in its own docstring and in `pipeline.py`'s module docstring; kept only because `test_pipeline.py`'s 37 tests exercise its components directly and because it's the only place loop-bound safety checking (`PropertyMonitor.from_loop_bound_check()`) currently lives — that check has **no equivalent in `process_wir_batch`** today (`property_ingest.py` excludes P2_Quality_Limits from conformance checking), so deprecating `run_pipeline` leaves loop-bound checking with no home anywhere; that gap is real and open, not silently dropped. `main.py` is **no longer** the stale P1.1 milestone demo — it was rewritten (PR #74) into module_03_equiv's real FastAPI service (`/lift`, `/check`, `/health`); `pipeline.py`'s own `main()` CLI (which calls the legacy `run_pipeline`) is a separate, unrelated entry point that predates and is untouched by that rewrite.
- ✅ **The non-looping vacuity channel is now fixed (2026-07-29).** Confirmed live on a real
  compiled build first (Homebrew SPOT 2.15.1 + pybind11): `check_compliance()` returned
  `COMPLIANT` for `G(!B)` on a 2-action, non-looping automaton where `B` provably executes and
  both atoms matched (`unmatched_atoms: []`) — the atom-gate fix (PR #67) closed a different
  channel and was never meant to close this one. Fixed via `instrument_alive_extension()` in
  `lifter.cpp`: when `code_aut` has no genuine cycle (`spot::scc_info`, all-trivial check — true
  for 0/43 of the eligible FLOW-BENCH corpus's top-level WIR graphs), `check_compliance` now
  negates `spot::from_ltlf(phi, "alive")` (De Giacomo & Vardi, IJCAI'13) against an "alive-extended"
  copy of the automaton (every edge ANDed with `alive=true`, every dead-end state given a
  `!alive` self-loop) instead of negating `phi` against the raw, dead-ending automaton. A genuine
  cycle (e.g. `LOOPING_WIR`) skips the bridge and uses the original unbridged check — `from_ltlf`'s
  own well-formedness obligation assumes the trace it bridges eventually terminates, and a real
  infinite loop doesn't, so bridging it manufactures a violation unrelated to the property (caught
  empirically: `test_looping_wir_passes_tautology` — literal `"1"` — regressed to `VIOLATION` before
  this branch was added).
  **A second, closely-related bug surfaced and was fixed in the same pass:** Phase A's edge labels
  only ever assert the positive literal for whatever fired on that edge (`resolve_task_label` /
  `resolve_edge_label`) — every *other* registered atom is left completely unconstrained on that
  edge, including the entry transition where nothing happens at all. Once terminating automata
  became checkable, this let the emptiness search pick a convenient value for an unrelated atom on
  an edge where nothing asserts it — e.g. `B=true` on the entry edge — to manufacture a violation
  of `!B W A` on code that genuinely calls `A` then `B` in the correct order. Same failure class as
  the atom-matching gate targets (a confident violation the code never exhibits), reached through
  an atom that *is* on the automaton somewhere, just not asserted false where it should be.
  `instrument_alive_extension()` now closes every edge under mutual exclusion first (forces every
  registered atom not already required true by an edge's own condition to false on that edge)
  before adding the alive-extension. Verified end-to-end against Module 01's own `evaluate_ltlf`
  oracle across all 29 eligible specs (58 real property checks): **100% agreement on every check
  that produced a real verdict (35/35); the remaining 23 were legitimate `INCONCLUSIVE`s** (the
  property references a task genuinely never called in that variant — the atom-gate correctly
  refusing, not a bug).
  **Also found, not fixed here (a caller/ingestion concern, not a `check_compliance` engine
  concern):** SPOT's infix parser reads an unquoted atom starting with a reserved LTL operator
  letter (`G`, `F`, `X`, `U`, `W`, `R`, `M`) as that operator applied to the remaining suffix —
  e.g. `GitHub_thing` parses as `G(itHub_thing)`. Any future ingestion code building LTL strings
  from task names must double-quote atoms (`"GitHub_thing"`) to avoid this.
  **Still explicitly deferred, not decided:** what a genuinely non-terminating trace (a real retry
  loop, or a hallucinated `while True`) should report against a property that itself requires
  termination — this is the vacuity-vs-divergence risk already on record. This fix only changes
  behavior for the *finite/dead-ending* case; looping automata are untouched.
  Full findings, cross-verification of a fresh Claude Science design round (M01→M03 integration,
  FLOW-BENCH eval harness, real-world demo), and one resolved owner-decision (the gateway
  default-flow question): [[Bridge Investigation/E2E Integration Verification Findings|E2E
  Integration Verification Findings]].

## Links

- [[Home]]
- [[Module 03 Architecture.canvas|Module 03 Architecture]]
- [[Module 03 Status.canvas|Module 03 Status]]
- [[Module 03 Repo Docs Index]]
- [[Bridge Investigation/P1.4 Bridge Findings|P1.4 Bridge Findings]] — LTLf→LTL bridge investigation: vacuity bug, AP vocabulary gap
- [[Bridge Investigation/AP Vocabulary and Lifting Scope Findings|AP Vocabulary and Lifting Scope Findings]] — the deeper finding: task nodes are function definitions, sub-CFGs unread, order wrong ~46% of the time
- [[Bridge Investigation/E2E Integration Verification Findings|E2E Integration Verification Findings]] — first real compiled build; the non-looping vacuity channel confirmed live; gateway default-flow question resolved
