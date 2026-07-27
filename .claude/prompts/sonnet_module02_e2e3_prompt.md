# SESSION MANDATE — Module 02: E2 (WIR structural accuracy) + E3 (certificate–correctness correlation)

You are running the two remaining research experiments for Module 02 of VibeCheck (`C:\Research\FYP\Vibe-Check`). The eval infrastructure and a working differential-mode detector already exist (E1 result: detection 0.864 [0.811, 0.906] vs false-alarm 0.059 [0.012, 0.162], τ=0.10 — `eval/results/calibration_report_differential.md`). This session produces the E2 and E3 numbers for the thesis. Module 02 only; other modules read-only.

**Branch setup**: check `gh pr view 25 --json state`. If PR #25 is merged → branch `feat/mod2/e2-e3-experiments` off `develop`. If still open → branch off `fix/mod2/verdict-and-eval-corpus` and note in the eventual PR body that it is stacked on #25.

## Ground rules

1. `CLAUDE.md` GitNexus workflow: `npx gitnexus analyze` first, `gitnexus_impact` before touching any existing symbol, `gitnexus_detect_changes()` before each commit.
2. Suite must stay green (`cd module_02_extract && python -m pytest -q`, currently 141) plus your new tests. This session should need **no changes to `src/`** — it builds measurement scripts in `eval/`. If you find yourself editing `src/`, stop and reconsider (exception: a genuine bug found by the experiments — fix it in its own clearly-labeled commit and note it in the report).
3. Keep everything dependency-free (pure stdlib), matching `eval/calibrate.py`'s style (its `clopper_pearson` uses `math.comb` bisection — reuse patterns from there).
4. Report measured numbers as-is. A weak F1 or a weak correlation is a finding, not a failure.

## Anti-circularity rules (these make the results defensible — violating them invalidates the experiment)

- **E2 gold labels must be produced by an independent code path**: a new labeler using only the `ast` module. It must not import anything from `src/ast_extractor/` (add a unit test asserting this via `sys.modules` inspection or import-graph check).
- **E3 ground truth must be code-vs-code**: the "how broken is this mutant" signal comes from executing base and mutant directly on identical inputs and diffing observable behavior. The WIR must not appear anywhere in the ground-truth side (it is the thing being evaluated).
- State both rules explicitly in each report's Methods section.

---

## TASKS

### X1 — Gold-WIR labeler (`eval/gold_wir.py`)

For each of the 101 corpus programs (`eval/corpus/uid_*.py`, manifest at `eval/manifest.json`), parse the `workflow` function with `ast` and emit a gold structure `eval/gold/uid_*.json`:

- One gold node per statement in the workflow body, with `{gold_id, type, code}` where `type` ∈ {`block`, `gateway`, `loop`, `return`} — `if`/`elif` → `gateway` (one per test), `for`/`while` → `loop`, `return` → `return`, everything else → `block`; `code` is the `ast.unparse`d statement text (for gateways: the test expression; for loops: the header).
- Gold edges as `{src_gold_id, dst_gold_id, label}` following Python control flow: sequential fall-through, gateway true/false arms, loop body/exit back-edges.
- **Before finalizing the schema, read the extractor's actual granularity**: `src/ast_extractor/cfg_extractor.py` (`_build_body`, `_make_block`, and the `visit_*` methods — statement-level nodes) and the WIR node fields (`id`, `type`, `code` list, `guard`, `successors`). The gold schema must target the *documented contract* (statement-level, types entry/exit/block/gateway/loop/task/return); if the extractor deviates (e.g. merges statements), that is an **E2 finding to measure**, not something to bake into the gold.
- Entry/exit nodes are excluded from scoring on both sides.

**Human-verification hook (required)**: pick 10 uids at random (fixed seed), render gold-vs-extracted side-by-side (plain text, node lists + edge lists) into `eval/results/e2_manual_check/`, and list the 10 uids in the report with a sentence asking the author to eyeball them. You cannot self-certify the gold; the sample makes human validation a 15-minute task.

**Test**: `eval/test_gold_wir.py` — on a small inline program (one if, one for, three calls), assert exact expected gold nodes/edges; plus the no-`ast_extractor`-import assertion.

### X2 — E2 structural accuracy (`eval/e2_structural.py`)

For each corpus program: run `run_v3_pipeline` (`src/ast_extractor/pipeline.py:19`), take `functions["workflow"]`, score extracted vs gold:

- **Node matching**: greedy 1:1 match on `(type, normalized_code)` where normalization strips whitespace and (for gateways) compares the guard expression; fall back to `(type, order-within-type)` for near-misses and count those separately as `weak_matches`.
- **Edge matching**: an extracted edge matches a gold edge iff both endpoints matched 1:1 and direction agrees (labels compared where both sides have them, reported separately, not required for the match).
- **Metrics**: micro-precision/recall/F1 over nodes and over edges, aggregated across all 101 programs; plus per-tag breakdown (linear / conditional / conditional_update / linear_update from the manifest tags) and a worst-10 list (lowest per-program F1, with one-line diagnosis each — these are the extractor-bug leads).

**Output**: `eval/results/e2_structural_report.md` — Methods (incl. anti-circularity statement + the manual-check uid list), aggregate table, per-tag table, worst-10 table. Also emit `eval/results/e2_per_program.csv` (uid, tag, node_p, node_r, node_f1, edge_p, edge_r, edge_f1).

**Test**: `eval/test_e2.py` — matching logic on hand-built gold/extracted pairs: perfect match → F1 1.0; one missing node → known P/R; one swapped edge direction → not matched.

### X3 — E3 certificate–correctness correlation (`eval/e3_correlation.py`)

Per mutant (all 429, manifest links `base_uid`):

1. **Ground-truth brokenness** (`semantic_diff_rate`): execute base and mutant `workflow` on the *same* N=25 seeded random inputs (reuse the input-generation approach from `src/dynamic_tracer/randomized.py:67-100` — including the guard-literal string pool — but implement locally in `eval/`; do not couple to the class). For each input, record each side's observable behavior — the sequence of stub calls plus the return value. Cheapest sound recorder: re-exec the source in a namespace where each stub def is wrapped to append `(stub_name, )` to a shared log before delegating (stubs are deterministic echoes by construction; `eval/mutate.py` never mutates them). `semantic_diff_rate` = fraction of the 25 inputs where (call-sequence, return-value) differs between base and mutant. **No WIR anywhere in this computation.**
2. **Certificate score**: reuse `eval/calibrate.py`'s differential runner (`run_differential_verification`, ~line 181) to get each mutant's `combined_confidence` against its base WIR. Cache per-mutant scores to a CSV so the run is resumable; reuse calibration-run scores if calibrate.py already persists them.
3. **Correlation**: Pearson r and Spearman ρ between `1 - combined_confidence` and `semantic_diff_rate` over all mutants; Fisher-z 95% CI for r (pure math: `atanh`, `1.96/sqrt(n-3)`). Also report the correlation restricted to mutants with `semantic_diff_rate > 0` (mutants that are semantically equivalent to their base — e.g. a boundary-shift no input distinguishes — are *label noise*, and their count is itself a finding: report how many of the 429 are behaviorally indistinguishable at N=25, with the caveat that N=25 bounds this from above).

**Output**: `eval/results/e3_correlation_report.md` — Methods (anti-circularity statement, N=25 caveat), r and ρ with CIs (full set + diff_rate>0 subset), equivalent-mutant count per operator, and `eval/results/e3_pairs.csv` (mutant_id, operator, base_uid, semantic_diff_rate, combined_confidence) for the thesis scatter plot.

**Test**: `eval/test_e3.py` — Pearson/Spearman/Fisher-z on small known vectors (assert against hand-computed values); recorder correctness on a 2-stub base vs drop-step mutant (diff_rate > 0) and base vs itself (diff_rate == 0).

### X4 — Wrap-up

- Append E2/E3 headline numbers to `.claude/memory/session_2026_07_04_t1_t7_implementation.md`.
- `gitnexus_detect_changes()`, commit per task (X1–X3 + wrap-up), push, open PR (or update the stacked-PR note) titled `feat(mod2): E2 structural-accuracy + E3 certificate-correlation experiments`. Body: both headline results, the manual-check request (10 uids), and the equivalent-mutant count.

---

## WHAT NOT TO DO

- Do not import `ast_extractor` in the gold labeler, and do not let the WIR touch E3's ground truth — the two anti-circularity rules are the experiment.
- Do not tweak `ast_extractor` to raise F1 mid-experiment; the worst-10 list is the input to a *future* fix session. (Genuine crash-level bugs: separate commit, noted in report.)
- Do not silently drop programs/mutants that error — count and report them as a category (e.g. `extraction_failed`, `execution_failed`).
- Do not add numpy/scipy/pandas — stdlib only, like the rest of `eval/`.
- Do not touch the still-open backlog (`visit_Attribute`, per-layer statuses, timeouts, `merge_states`, adaptive n_runs).

## DEFINITION OF DONE

- Suite green (141 + new tests).
- `eval/gold/` (101 files), `eval/results/e2_structural_report.md` + `e2_per_program.csv`, `eval/results/e3_correlation_report.md` + `e3_pairs.csv`, `eval/results/e2_manual_check/` (10 uids).
- Both reports carry Methods sections with the anti-circularity statements and honest caveats (N=25 equivalence bound, weak-match counts).
- PR opened/updated; session memory appended.
