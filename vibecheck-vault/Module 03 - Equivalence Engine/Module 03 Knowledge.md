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

**113 test functions total**: `test_pipeline.py` 37 (pure Python, Phases A–D + e2e), `test_cpp_engine.py` 29 (Phase A C++ + new `TestPhaseD` — tautologies, looping-WIR failures, counterexample content, quotient compliance, segfault guards), `test_phase_b.py` 28, `test_phase_c.py` 19. All C++-side tests `skipif` the `.so` isn't compiled.

## Status & Issues (2026-07-28, main @ `7089711`)

- ✅ **C++/SPOT engine is now complete through Phase D** — real LTL model checking with counterexample extraction, wired into `process_wir_batch`; 113 tests total. The documented method is finally executable (caveats below — vacuous on non-looping automata until instrumented, and Phase A's action atoms are function definitions, not business actions).
- ✅ Resolved earlier: committed Linux `.so` removed from git; `module_summery` M03 doc rewritten.
- ⛔ **Module 01 ingestion still missing:** zero references to `module_03_input.json` / property suites anywhere in `module_03_equiv`. `check_compliance` accepts SPOT infix **LTL** (infinite-trace semantics); Module 01 produces **LTLf** strings (finite-trace) — no LTLf→LTL bridge exists. The only caller passes the placeholder `'G("approved")'`, so spec↔code is mechanically possible but not integrated.
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
- ⚠ Phase D now exists in two flavors (legacy Python reachability in `run_pipeline`, SPOT LTL in `process_wir_batch`) — still no statement of which pipeline is canonical; `main.py` (80 LOC) remains the stale P1.1 milestone demo.
- ⛔ **The non-looping vacuity channel is still open, now confirmed live on a real compiled build
  (2026-07-29):** first successful local build of `vibecheck_lifter` on this machine (Homebrew
  SPOT 2.15.1 + pybind11), and `check_compliance()` still returns `COMPLIANT` for `G(!B)` on a
  2-action, non-looping automaton where `B` provably executes and both atoms are matched
  (`unmatched_atoms: []`) — the atom-gate fix (PR #67) closed a different channel and was never
  meant to close this one. Confirmed the whole eligible FLOW-BENCH corpus is exposed to it: 0 of 43
  top-level WIR graphs contain a cycle. Consequence: real detection on this corpus is currently
  **zero**, for any lifting scheme, until the automaton's acceptance condition is instrumented
  (the LTLf→LTL "alive"/stutter-extension bridge this project's own investigation already named).
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
