# Module 02 — Verified IR Extraction

> Snapshot: 2026-07-29 — branch `main-demo` @ `5c65046` (declared FINAL implementation). Previous snapshot: 2026-07-28 (main @ `7089711`).

Module 02 is the **code track** of VibeCheck: it takes LLM-generated Python workflow code and produces a **WIR** (Workflow Intermediate Representation — a JSON control-flow graph defined by `shared_schemas/wir_schema.json`) plus a **3-layer confidence certificate**. Both are consumed by Module 03 (equivalence checking). ~5,200 lines in `module_02_extract/src/` (grew from the ~3,000 at the last snapshot: robustness batch, call-order view, FastAPI hardening). Served as a FastAPI **extract-engine** (`src/main.py`, 545 LOC) with a single `POST /verify` endpoint that returns the certificate, the WIR, a call-order WIR view, and typed per-layer statuses. Contract doc: [[12_wir_and_certificate_contract]] (vault copy — `docs/` was removed from the repo @ develop `05fae60`).

## Three validator layers + certificate

- **V3 — STRUCTURAL** (`module_02_extract/src/ast_extractor/`, `CFGExtractor` in `cfg_extractor.py`, 707 LOC): AST / dominator validation. Hard gate (`abort=True`) — it gates the certificate. Also hosts `call_order_view.py` (123 LOC), the D2 call-order lifting that produces `call_order_wir`.
- **V2 — SYMBOLIC** (`module_02_extract/src/z3_sym_engine/`): Z3 bounded concolic execution (`concolic.py` 534, `tracer.py` 361, `evaluator.py` 199 LOC).
- **V1 — DYNAMIC** (`module_02_extract/src/dynamic_tracer/`): PEP 669 `sys.monitoring` differential tracing against a WIR reference interpreter, with a `settrace` fallback + parity test, LCS trace alignment, strict vs `task_only` comparison modes, and return values as first-class trace events (`collector.py` 532, `interpreter.py` 332, `randomized.py` 291, `comparator.py` 259 LOC).

**Certificate fusion:** `combined = 1 − (1−v1)(1−v2)`, V3 gates, acceptance ≥ 0.95. The older 3-term formula with a V3 term was removed because it made the verdict vacuous. Robustness: 30s wall-clock timeout on `/verify` (`VERIFY_TIMEOUT_S`), typed per-layer statuses (`layers` key: OK / ERROR / SKIPPED + reason), source guards (50k chars / 5k AST nodes), SAFE_BUILTINS exec sandbox.

## WIR summary

Node types: entry / exit / block / gateway / loop / task / break / continue / return / except / finally / match. Guarded edges, dominators, control/data variable classification, nested per-function sub-WIRs. `/verify` returns **two views**: `wir` (definition-order, unchanged for all existing consumers) and `call_order_wir` (driver-function lifting, sibling calls as task boundaries — what M03's lifter actually needs).

**Integration note:** Module 01's `export_for_module_02()` writes `module_02_input.json` (`semantic_graph` + `task_patterns`); Module 02's `randomized.py` consumes `task_patterns` — the wired M01→M02 handoff. Output handoff: WIR + call-order WIR + certificate → Module 03.

## Eval harness (`module_02_extract/eval/`)

- IBM FLOW-BENCH adapter (101 workflows); 10 mutation operators → 427 applicable mutants (all verified on disk).
- Stratified CALIB/EVAL calibration via Youden's J + Clopper-Pearson CIs; frozen `threshold.json`: tau=0.1, J=0.96, mode `differential-corrected`.
- Multi-LLM natural-bug corpus (llama-3.1-8b, mixtral-8x7b, qwen3-next-80b): 294/303 generations (documented qwen NIM outage), 184 clean, behavioral admission 20 admitted / 164 rejected.
- The upstream benchmark is **vendored at repo root**: `flow-bench/` (IBM FLOW-BENCH, arXiv 2505.11646 — 101 cases, BPMN context/output pairs, arXiv PDF, 3 demo videos). Pristine copy, **not referenced by code** — the adapter keeps using its derived `module_02_extract/inputs/conditional_ootb.yaml`.

**Measured results** (committed in `eval/results/*.md`, archived pre-fix reports kept as an audit trail; re-verified byte-identical in Session B's combined re-run, and nothing since touched the eval path):

- Genuine-bug detection: **0.9952** (n=210)
- False-alarm rate: **0.0588** (n=51)
- WIR structural F1: **1.0000** (all 101 base programs)
- Natural-bug detection: **1.0** strict (164/164) / **0.9329** `task_only` (153/164)
- E3 certificate-correctness correlation: Pearson r = 0.4085, Spearman rho = 0.5400; 11/427 equivalent mutants
- Return-value observability fix: logic-bug detection 91.18% → 100% (same-lineage), 77.94% → 88.24% (cross-implementation); cross-implementation false alarms 25% → 10% under `task_only` (sensitivity cost stated openly).

**E2E harness** (`demo/eval_e2e/`, PR #77 — extends this mutation methodology to the full M01→M02→M03 chain, 6 gold spec/impl pairs): abstention (honest INCONCLUSIVE) **0.462** [0.27, 0.67] (n=26), detection **0.357** [0.13, 0.65] (n=14), false-alarm **0.000** [0.00, 0.84] (n=2), counterexample quality 0.800 (n=5). Small n — every rate carries its CI by design.

## Thesis chapter

Full **Chapter 5 draft** (§5.1–5.8, 713 lines): [[module02_chapter_draft]], plus [[module02_chapter_outline]] and figures ([[fig_detection_climb.png]], [[fig_e3_scatter.png]]) — vault copies in `Repo Docs/Thesis/` (repo `docs/` removed @ develop `05fae60`). Covers the WIR, the three-layer certificate, the removed 3-term fusion (§5.3.5), the "self-referential validation" central result with differential mode/oracle separation (§5.4), and evaluation with anti-circularity rules and correction trail (§5.6).

## Changes since the 2026-07-28 snapshot

47 commits landed; the module **did** change (the previous "unchanged since last snapshot" note no longer holds). Fixed items:

- ✅ **Call-order WIR exposed from `/verify`** — PR #75 (`08a9d5f`), on top of the D2 lifting fix PR #73 (`564c04c`). `call_order_wir` is additive alongside `wir`; empty dict on failure, same convention as `wir`.
- ✅ **extract-engine docker container never started** — PR #76 (`9e41c6f`). Root cause: sibling relative-import bug (`from .ast_extractor` → `from ..ast_extractor`) in `z3_sym_engine/` and `dynamic_tracer/`, present since the package-split refactor and masked by fallback imports; plus a `source.replace('\\n', '\n')` that corrupted genuine escape sequences in source string literals (confirmed against 13/184 real corpus variants). Fixed and verified over a real docker-compose HTTP chain (uid 44 / uid 77).
- ✅ **Dominance-frontier infinite loop** — PR #85 (`9e6fc82`, HEAD merge). networkx-version-dependent `immediate_dominators` entry convention: self-mapping `idom[entry] == entry` on networkx 3.2.1 made the frontier walk never terminate. Same commit: `sys.monitoring` parity tests now skip cleanly on Python < 3.12 instead of hard-failing (Dockerfile pins 3.11).
- ✅ **Multi-modal certificate claim reframed** — PR #83 (`96ba25a`). The V1-dominance caveat is now stated in the prominent docs (`00_overview.md`, §5.1, §5.5 table), not only deep in the eval reports. No code change; the eval reports and this file were already honest.
- ✅ **E2E evaluation harness** — PR #77 (`ce07086`), `demo/eval_e2e/` (numbers above).

**Tests — verified 2026-07-29** (repo venv, Python 3.11.15): `tests/` **169 passed, 9 skipped** (the 9 are `sys.monitoring` parity tests, correctly skipped below 3.12); `eval/` **87 passed**. 256 total, ~2s. Minor gap found while verifying: `pyyaml` is imported by `eval/` but missing from `requirements.txt` — eval test collection fails without it.

## Limitations

- V2 symbolic contributes ≈ nothing on the current corpus (container-shaped inputs force V1 fallback) — the 'multi-modal' certificate is effectively V1-driven. Now stated in the prominent docs (PR #83), not just the eval reports.
- Equivalent-mutant specificity is only 0.1111.
- Numeric-boundary bugs (`<` vs `<=` at a threshold like `credit_score=600`) are a known blind spot: V1 samples ints uniformly from −100..100 and V2 is not a per-input oracle.
- CPython timeout cannot preempt a C-level statement holding the GIL — B3's thread-based timeout only bounds GIL-releasing hangs; closing this needs process-based isolation (`multiprocessing` + `Process.terminate()`), the named honest leftover.
- B6 leftover: per-guard-site literal coverage. `randomized.py`'s round-robin literal pool is function-wide, not per-guard-site — the uid_4 constant-perturb straggler needs more than one `n_runs` budget to force-cover both string guards.
- V2-masking in self-mode: `/verify`'s self-mode composition is still the OR-formula `1−(1−v1)(1−v2)`; only differential mode uses `combined = v1`.
- Dead QCE symbolic-state-merging code was excised rather than overclaimed (documented with rationale).
- E2E harness detection 0.357 (n=14) with 0.462 abstention is honest but modest — task-drop mutants often make the dropped atom unobservable, so the pipeline abstains rather than misjudges.

## Links

- [[Home]]
- [[Module 02 Novelty]] — research positioning vs prior art
- [[Module 02 Architecture]]
- [[Module 02 Status]]
- [[Module 02 Repo Docs Index]]
