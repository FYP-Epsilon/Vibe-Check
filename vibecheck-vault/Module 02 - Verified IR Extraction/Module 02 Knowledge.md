# Module 02 — Verified IR Extraction

Module 02 is the **code track** of VibeCheck: it takes LLM-generated Python workflow code and produces a **WIR** (Workflow Intermediate Representation — a JSON control-flow graph defined by `shared_schemas/wir_schema.json`) plus a **3-layer confidence certificate**. Both are consumed by Module 03 (equivalence checking). Roughly 3,000 LOC. Contract doc: [[12_wir_and_certificate_contract]] (vault copy — `docs/` was removed from the repo @ develop `05fae60`).

## Three validator layers + certificate

- **V3 — STRUCTURAL** (`module_02_extract/src/ast_extractor/`, `CFGExtractor` in `cfg_extractor.py`): AST / dominator validation. Hard gate (`abort=True`) — it gates the certificate.
- **V2 — SYMBOLIC** (`module_02_extract/src/z3_sym_engine/`): Z3 bounded concolic execution.
- **V1 — DYNAMIC** (`module_02_extract/src/dynamic_tracer/`): PEP 669 `sys.monitoring` differential tracing against a WIR reference interpreter, with a `settrace` fallback + parity test, LCS trace alignment, and strict vs `task_only` comparison modes.

**Certificate fusion:** `combined = 1 − (1−v1)(1−v2)`, V3 gates, acceptance ≥ 0.95. The older 3-term formula with a V3 term was removed because it made the verdict vacuous. Robustness: wall-clock timeouts on `/verify`, typed per-layer statuses.

## WIR summary

Node types: entry / exit / block / gateway / loop / task / break / continue / return / except / finally / match. Guarded edges, dominators, control/data variable classification, nested per-function sub-WIRs.

**Integration note:** Module 01's `export_for_module_02()` writes `module_02_input.json` (`semantic_graph` + `task_patterns`); Module 02's `randomized.py` already consumes `task_patterns` — currently the only actually-wired cross-module handoff in the project.

## Eval harness (`module_02_extract/eval/`)

- IBM FLOW-BENCH adapter (101 workflows); 10 mutation operators → 427 applicable mutants.
- Stratified CALIB/EVAL calibration via Youden's J + Clopper-Pearson CIs.
- Multi-LLM natural-bug corpus (llama-3.1-8b, mixtral-8x7b, qwen3-next-80b) with behavioral admission: 20 admitted / 164 rejected.
- The upstream benchmark is now **vendored at repo root**: `flow-bench/` (IBM FLOW-BENCH, arXiv 2505.11646 — 101 cases, BPMN context/output pairs, arXiv PDF, 3 demo videos). Pristine copy, **not referenced by code** — the adapter keeps using its derived `module_02_extract/inputs/conditional_ootb.yaml`.

**Measured results** (committed in `eval/results/*.md`, archived pre-fix reports kept as an audit trail):

- Genuine-bug detection: **0.9952** (n=210)
- False-alarm rate: **0.0588** (n=51)
- WIR structural F1: **1.0000**
- Natural-bug detection: **1.0** strict / **0.9329** `task_only`
- Return-value observability fix: logic-bug detection 91.18% → 100% (same-lineage), 77.94% → 88.24% (cross-implementation); cross-implementation false alarms 25% → 10% under `task_only` (sensitivity cost stated openly).

## Thesis chapter

Full **Chapter 5 draft** (§5.1–5.8, 713 lines): [[module02_chapter_draft]], plus [[module02_chapter_outline]] and figures ([[fig_detection_climb.png]], [[fig_e3_scatter.png]]) — vault copies in `Repo Docs/Thesis/` (repo `docs/` removed @ develop `05fae60`). Covers the WIR, the three-layer certificate, the removed 3-term fusion (§5.3.5), the "self-referential validation" central result with differential mode/oracle separation (§5.4), and evaluation with anti-circularity rules and correction trail (§5.6). No code changed this cycle — the module is unchanged since the last snapshot.

## Limitations

- V2 symbolic contributes ≈ nothing on the current corpus (container-shaped inputs force V1 fallback) — the 'multi-modal' certificate is effectively V1-driven.
- Equivalent-mutant specificity is only 0.1111.
- Numeric-boundary bugs (`<` vs `<=` at a threshold like `credit_score=600`) are a known blind spot: V1 samples ints uniformly from −100..100 and V2 is not a per-input oracle.
- CPython timeout cannot preempt a C-level statement holding the GIL.
- Dead QCE symbolic-state-merging code was excised rather than overclaimed (documented with rationale).

## Links

- [[Home]]
- [[Module 02 Architecture]]
- [[Module 02 Status]]
- [[Module 02 Repo Docs Index]]
