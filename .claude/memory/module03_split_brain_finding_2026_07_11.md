---
name: module03-split-brain-finding-2026-07-11
description: Module 03 has two non-interoperating implementations (tested pure-Python pipeline vs C++/SPOT engine actually run by Docker) that disagree on clustering algorithm and semantic matching; M01 input is entirely unconsumed — grounds fable_module03_e2e_plan_prompt.md
metadata:
  type: project
---

On 2026-07-11, before drafting a Fable E2E-plan prompt for Module 03 (mirroring [[module01_wiki_novelty_gap_2026_07_11]]'s approach), verified Module 03 source on `develop` directly. Findings:

**Split-brain implementation** — `module_03_equiv/src/` has two parallel, non-interoperating paths for the same claimed capabilities:
- **Pure Python** (`lifter.py`, `stuttering_engine.py`, `clustering.py`, `model_checker.py`, orchestrated by `pipeline.py`) — has real test coverage (`tests/test_pipeline.py`, all 4 phases + integration).
- **C++/Pybind11** (`lifter.cpp`/`.hpp` → compiled `vibecheck_lifter.*.so`, driven by `main.py`) — this is what the **Dockerfile actually runs** (`CMD python3 -m src.main`), and `main.py` is a one-shot demo (parses mock WIR, runs semantic matching on 3 hardcoded strings, `time.sleep(2)`, exits) — **no FastAPI app, no persistent server**, unlike M01/M02 which both run `uvicorn` as their CMD. `module_04_ui/src/app.py` already treats Module 03 as a CLI binary (import-check only), not an HTTP service — this may be intentional, unconfirmed.

The two paths **disagree behaviorally**:
- Semantic BPMN-task-name matching (`nlp_utils.py`'s Sentence-BERT `compute_max_similarity`) is called **only** from `lifter.cpp:132-139` — never from the tested pure-Python `lifter.py`, despite `sentence-transformers`/`torch` being installed deps. Wiring gap, not missing capability.
- `clustering.py`'s `BehavioralClusterer` builds clusters via a **pairwise O(n²) equivalence matrix** (`_build_equivalence_matrix`) + Union-Find — contradicts the wiki's "hash-based clustering, no pairwise comparison needed" claim. `compute_deterministic_hash` exists only in the C++ path, never called by `clustering.py`.
- `test_cpp_engine.py` gracefully `sys.exit(0)`s if the `.so` isn't importable — so CI could report this suite "passing" without ever exercising the C++ engine.

**M01→M03 interface does not exist**: `model_checker.py`'s `PropertyMonitor` has exactly 2 factory methods (`from_reachability`, `from_loop_bound_check`) — no LTLf/spec-automaton ingestion anywhere. Matches the finding already in `.claude/module01_e2e_plan.md` Agent 5 point 8 (M03 consumes nothing from M01).

**M02→M03 interface is real and tested**: `lifter.py`'s certificate-gating (`abort`/`guard_success_rate` vs `confidence_threshold`) is exercised by `test_pass_high_confidence`/`test_reject_low_confidence`/`test_reject_abort_flag`.

**Alignment asset already exists**: `module_02_extract/eval/variants/` (contract: `docs/module02/11_multi_impl_corpus_contract.md`) is a real multi-LLM-implementation corpus, **explicitly documented as Module 03's clustering ground truth** — one cluster per uid = base + admitted variants, rejected_behavioral = singletons, anti-circular (admission computed independently of any WIR/M03 machinery), same FLOW-BENCH uid space as M01's plan. `comparison_mode="task_only"` is the documented correct mode for any M03-adjacent cross-impl comparison (§7 of the contract).

**Why**: Third distinct shape of the same project-wide pattern — [[z3_double_reset_misdiagnosis]] (fabricated bug), [[module01_wiki_novelty_gap_2026_07_11]] (wiki overclaiming unbuilt code), and now Module 03 (two source-code implementations silently disagreeing with each other, with the untested/unwired one being the one the docs/wiki actually describe).

**How to apply**: [[fable_module03_e2e_plan_prompt]] hands this to a Fable session as a verify-first, five-agent plan explicitly required to (a) determine which implementation is canonical, (b) design an evaluation plan built on the already-existing M02 multi-impl corpus, (c) define the M01→M03 integration contract M01's Phase 4 will need to satisfy, referencing [[module01_wiki_novelty_gap_2026_07_11]] and `.claude/module01_e2e_plan.md` directly rather than re-deriving M01 findings. [[module01_ownership_boundary]]-equivalent applies to M03 too — planning only, no code edits.
