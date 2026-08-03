# Project Memory

Durable, project-level context for anyone (human or AI) picking this repo up cold.
Not a replacement for `CLAUDE.md` (tool usage rules) or the Obsidian vault
(`vibecheck-vault/`, deep per-module knowledge notes) — this file is the short
index of *what's currently true* and *why*, so a new session doesn't have to
re-derive it from git log and vault archaeology.

## What this project is

BPMN 2.0 → formal-spec → code-verification pipeline, evaluated against the
IBM FLOW-BENCH dataset (arXiv:2505.11646), which has no native correctness
labels — every module builds its own ground truth (mutation testing, oracle
agreement, independent gold labelers).

- **Module 01** (`module_01_spec/`) — BPMN XML → tiered LTLf property suite
  (P0 sentinels / P1 structural / P2 quality / P3 adversarial / P4 task
  coverage) + PBCTS trace certificate.
- **Module 02** (`module_02_extract/`) — Python code → WIR (workflow
  intermediate representation) extraction.
- **Module 03** (`module_03_equiv/`) — model-checks Module 02's WIR against
  Module 01's property suite (SPOT/C++ lifter), consuming M01's JSON export
  only — never its source (dual-track independence, deliberate).

## Current status (as of the 2026-08-02/03 FlowBench evaluation push)

- **Module 01 FlowBench evaluation**: real, current. `module_01_spec/eval/`
  (gold_bpmn.py, soundness.py, mutate_eval.py, report.py) is a durable,
  re-runnable harness — not throwaway pilot scripts. Built via a 3-phase
  process: design memo → fix 3 real defects found by the memo (PR #89) →
  build the permanent harness (PR #90). Both merged into
  `demo/evaluation-finale` (not yet `main-demo`).
- **Module 03 ingestion** (`module_03_equiv/src/property_ingest.py`):
  tier-gated by design — only formulas this layer can *soundly* check are
  checked; everything else is excluded with a stated reason, never silently
  dropped. P4_Task_Coverage is now integrated (previously crashed ingestion
  entirely): its unconditional form (`F(done(X))`) is a genuine, checkable
  omission property; its conditional form (`G(start(X) -> F(done(X)))`) is
  excluded as a verified tautology under this layer's start/done atom
  collapsing (same failure mode already documented for P0).
- **E2E harness** (`demo/eval_e2e/harness.py`): re-run 2026-08-02/03 against
  the post-fix pipeline. Fixing the P4 crash alone tripled the discoverable
  gold-spec set (6→18) and trial count (26→60) — the crash had been silently
  starving the harness of most of its own eligible data. Current figures live
  in `demo/eval_e2e/results/e2e_eval_report.md`; treat any number older than
  this run's timestamp as stale.

## Known, deliberately deferred (not bugs — scoped out, funded later if ever)

- **P4's conditional form** can't be checked meaningfully without a real fix
  to Module 03's start/done atom collapsing (a two-event-split lifting
  change, already scoped and rejected for now in the vault's
  `ap_gap_memo.md`). Excluding it is the honest current answer, not a
  placeholder for "will fix soon."
- **Module 03's own standalone 58-check figures** (quoted on the printed
  poster) predate the P4 fix and an open question about call-order vs.
  definition-order lifting (`CP1 Lifting-Scope Decision.md` in the vault) —
  orthogonal to the E2E numbers above, not yet investigated.
- The 4 residual `FAIL_WITH_ERRORS` diagrams in Module 01 (empty `node()`
  proposition names from `semantic_extractor`) — disclosed, unfixed, out of
  scope for the harness work.

## Where to look for more

- `vibecheck-vault/Module 01 - Specification Analysis/Module 01 Knowledge.md`
  and `.../FlowBench Evaluation Investigation/` — the full defect-diagnosis
  and fix history, with independent reproduction logs (not self-reported).
- `vibecheck-vault/Module 03 - Equivalence Engine/Bridge Investigation/` —
  `ap_gap_memo.md` (atom-collapsing tradeoffs), `CP1 Lifting-Scope
  Decision.md` (call-order vs. definition-order lifting).
- `CLAUDE.md` / `AGENTS.md` — GitNexus MCP tool usage rules (mandatory
  `impact()` before edits, `detect_changes()` before commits).
