# VibeCheck — Research Vault

> Post-hoc **verified translation validation**: formally checks whether LLM-generated Python workflow code conforms to its originating **BPMN 2.0** specification, producing a quantified, evidence-backed certificate rather than a proof.
> FYP Group Epsilon, Faculty of IT, University of Moratuwa. Snapshot: **2026-07-28** (main @ `7089711`).

## Canvases

- [[Project Architecture.canvas|Project Architecture]] — full dual-track pipeline, all four modules
- [[Project Status.canvas|Project Status]] — whole-project status snapshot, strengths, gaps, priorities
- [[Module 01 - Specification Analysis/Module 01 Architecture.canvas|Module 01 Architecture]] · [[Module 01 - Specification Analysis/Module 01 Status.canvas|Module 01 Status]]
- [[Module 02 - Verified IR Extraction/Module 02 Architecture.canvas|Module 02 Architecture]] · [[Module 02 - Verified IR Extraction/Module 02 Status.canvas|Module 02 Status]]
- [[Module 03 - Equivalence Engine/Module 03 Architecture.canvas|Module 03 Architecture]] · [[Module 03 - Equivalence Engine/Module 03 Status.canvas|Module 03 Status]]
- [[Module 04 - Verification Portal/Module 04 Architecture.canvas|Module 04 Architecture]] · [[Module 04 - Verification Portal/Module 04 Status.canvas|Module 04 Status]]

## Module notes

- [[Module 01 - Specification Analysis/Module 01 Knowledge|Module 01 — Specification Analysis]] 🟡 (pivoted: SPOT Phase 4/5 replaced by pure-Python **PBCTS** trace synthesis; still zero tests; **startup bug in `main.py`**)
- [[Module 02 - Verified IR Extraction/Module 02 Knowledge|Module 02 — Verified IR Extraction]] 🟢 (most mature, measured; unchanged — thesis Ch. 5 draft added)
- [[Module 03 - Equivalence Engine/Module 03 Knowledge|Module 03 — Equivalence Engine]] 🟡 (C++/SPOT engine now covers **all four phases A–D** incl. real LTL model checking, 113 tests; Module 01 ingestion still missing)
- [[Module 04 - Verification Portal/Module 04 Knowledge|Module 04 — Verification Portal]] 🟡 (unchanged; works for M01/M02, equiv page broken under compose)

## Repo docs (vault copy)

The repo's entire `docs/` tree, imported @ `7089711`. **`docs/` has since been removed from the repo** (develop @ `05fae60`) — these vault copies are now the surviving snapshot (git history retains the originals).

- [[Project Repo Docs Index]] — architecture plans, thesis Ch. 5 draft + figures, WIR schema docs
- [[Module 01 Repo Docs Index]] · [[Module 02 Repo Docs Index]] · [[Module 03 Repo Docs Index]]

## Key concepts

- **WIR (Workflow Intermediate Representation)** — JSON CFG, the schema-validated contract between Module 02 (producer) and Module 03 (consumer): `shared_schemas/wir_schema.json`.
- **Dual-track independence** — spec track and code track never see each other's input; they meet only in Module 03 as independent mathematical objects, avoiding circular verification.
- **V1/V2/V3 certificate** — V3 structural hard gate, V2 Z3 symbolic, V1 dynamic differential tracing; `combined = 1 − (1−v1)(1−v2)`, acceptance ≥ 0.95.
- **Divergence-sensitive stuttering bisimulation** — refuses to merge a silently-infinite loop (e.g. hallucinated `while True: pass`) with a normal wait state. Implemented in both Python (`stuttering_engine.py`) and C++ (`spot::scc_info` + Groote–Vaandrager).
- **PBCTS (Progression-Based Constructive Trace Synthesis)** — Module 01's new Phase 4 (replacing the abandoned SPOT/HOA approach): LTLf formulas are *progressed* step-by-step in pure Python to construct satisfying traces `T_spec`, then bidirectionally aligned with model traces (`EAS_BDA`, `IDCD` convergence gate, `SCSL` self-correction loop ≤ 3 rounds) → Formal Reliability Certificate v2.0.
- **LTLf→LTL handoff gap** — Module 01 exports LTLf **strings** (`module_03_input.json`); Module 03's new C++ `check_compliance` model-checks any SPOT infix **LTL** string with counterexample extraction. The mechanism exists on both sides; the missing links are ingestion code and an LTLf(finite)→LTL(infinite) semantic bridge.
- **`flow-bench/`** — vendored upstream copy of IBM FLOW-BENCH (arXiv 2505.11646) at repo root; Module 02's eval harness uses its own derived copy under `module_02_extract/inputs/`.

## Headline numbers (Module 02 eval)

| Metric | Value |
|---|---|
| Genuine-bug detection | 0.9952 (n=210) |
| False-alarm rate | 0.0588 (n=51) |
| WIR structural F1 | 1.0000 |
| Natural-bug detection | 1.0 strict / 0.9329 task_only |
| Calibration corpus | 427 mutants, 10 operators |
| Natural-bug corpus | 3 LLM families, 20 admitted / 164 rejected |

## Current gap

End-to-end spec↔code equivalence is **closer than ever, but still not wired**. Both mechanisms now exist: Module 01 exports its LTLf property suite (`module_03_input.json`) and Module 03's C++ `check_compliance` runs textbook SPOT model checking (¬φ → Büchi → product → emptiness + counterexample) on any LTL string. Missing: code that feeds Module 01's suite into Module 03 (the only caller passes a hardcoded `'G("approved")'` placeholder) and an LTLf→LTL semantic bridge. What runs today: certificate generation (M02), code-vs-code behavioral equivalence + LTL compliance checking (M03, Python and C++, 113 tests), and Module 01's 4-phase PBCTS pipeline. Red flags: Module 01 still has **zero tests**, and its `main.py` imports the deleted `automata_lifter` — **the spec-engine crashes on startup** (Docker `uvicorn` CMD included).
