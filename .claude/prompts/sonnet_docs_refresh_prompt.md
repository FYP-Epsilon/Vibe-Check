# SESSION MANDATE — Repo docs refresh: reconcile Module 02's documents with the implemented reality

The Module 02 implementation diverged substantially from its original design docs over seven engineering sessions (verdict formula changed, EQI never existed, WIR layers never existed, QCE deleted, tracer migrated, evaluation rebuilt). The wiki now reflects reality; several repo docs do not. This session fixes that — **docs only, zero code changes**. Repo: `C:\Research\FYP\Vibe-Check`, branch `docs/mod2/refresh` off `develop`, PR to `develop` at the end. Baseline: 246 tests must still pass untouched (`cd module_02_extract && python -m pytest -q` before and after — you are not editing code, this catches accidents).

## Ownership boundary (hard rule)

You may edit: `README.md`, `docs/module02/**`, `docs/module_summery/Module_02_*.md`, and create new files under `docs/module02/`. You may **NOT** edit Module 01's or Module 03's docs (`docs/module_summery/Module_01_*.md`, `Module_03_*.md`, `docs/module03/**`) or any code — cross-module doc drift is *flagged*, not fixed (task D5).

## The classification rubric (apply to every file you touch)

- **(a) Living contract/reference docs** → update in place to current verified state.
- **(b) Historical plan/finding docs** → do NOT rewrite history; add a short banner at the top: `> **Historical document** (written <date-context>): describes the design/plan as of that point. Superseded by <pointer>. Kept as the project's finding trail.` — then leave the body alone.
- **(c) Wrong and consumed by others** → full rewrite from current source, preserving any still-valid literature/background sections.

Where you need ground truth: the source itself, `module_02_extract/eval/results/*.md` (current reports), `docs/module02/11_multi_impl_corpus_contract.md` (current corpus contract), and the wiki's Module-02 page (recently verified). Verify every number you write against the current reports — do not copy numbers from this prompt without checking.

## Tasks

### D1 — `docs/module02/00_overview.md` → rubric (a), update in place
Verified stale content: line ~30 shows the removed formula `combined = 1 - (1-v1)(1-v2)(1-v3)`; line ~25 describes V1 as `sys.settrace` differential testing; the example response block yields the impossible-under-current-formula 99.97% combined. Update: current composition (`1-(1-v1)(1-v2)` with V3 as an abort **gate**, and why — one sentence on the vacuous-verdict fix), monitoring-first tracer with settrace fallback, the `layers` per-phase status key, wall-clock timeout env (`VERIFY_TIMEOUT_S`), and a corrected example response computed with the real formula. Keep the doc's original structure.

### D2 — `docs/module_summery/Module_02_Verified_IR_Extraction.md` → rubric (c), full rewrite
This is the pre-overhaul design doc (12 verified hits of EQI / WIR-Type / WIR-Proc / settrace / merge_states / QCE / old formula). None of those exist in the implementation: there is no EQI score (the certificate is `v1/v2/v3/combined_confidence` + `passed` + `layers`), no WIR-Core/Data/Proc/Type layers (the actual WIR is `nodes/edges/functions/dominators/dominance_frontier/guard_extraction/certificate`), no QCE state merging (deleted as dead code, session B4), and V1 is monitoring-first. Rewrite the doc to the implemented, measured state:
- Preserve the literature-review and gap-analysis sections if present and still valid (check them; they age well).
- Replace design/status/schema sections with current reality: pipeline description, real WIR schema (derive from `src/ast_extractor/` and a real `/verify` response — generate one locally rather than guessing), certificate semantics, comparison modes, and the headline evaluation numbers **taken from `eval/results/` reports** (calibration, E2, E3, multi-impl, session B).
- Add a short "Design history" section pointing to `docs/module02/`'s numbered docs and `eval/results/archive/` as the auditable correction trail — one paragraph, not a retelling.
- Keep the same file name and top-level heading style as the M01/M03 sibling docs.

### D3 — `docs/module02/05..10_*.md` → audit each against the rubric
`05_core_hardening.md` (mentions merge_states-never-called and other since-resolved findings), `06_ai_refinement.md`, `07_multi_impl.md` (predates the actual Session C implementation), `08_eval_data.md` (the 1,172-line eval *plan*, superseded by the real `eval/` subsystem), `09_experiments.md` (superseded by the actual reports), `10_integration.md`. Expected outcome: most get the **(b) historical banner** with a pointer to what superseded them (respectively: the current source + session reports; `11_multi_impl_corpus_contract.md` + `eval/results/multi_impl_report.md`; `eval/` itself; `eval/results/*.md`). If any turns out to be a living reference (read before deciding), update it instead — state your classification per file in the PR body. `11_multi_impl_corpus_contract.md` is current — leave it (D4 appends to it or creates a sibling).

### D4 — Create the authoritative WIR/certificate contract doc for Module 03
New file `docs/module02/12_wir_and_certificate_contract.md` (or extend `11_` if more natural — your call, say which): the **actual** interface M03 consumes, generated from reality: full WIR JSON schema (mirror `src/ast_extractor/schema.py` + a real example), certificate fields with semantics (`v3` = extraction fidelity gate, not a correctness vote; `combined` semantics per mode; `layers` statuses), the comparison-mode guidance (strict = same-lineage, task_only = independent implementations), and the two facts M03's owner must know: WIRs contain **no blank structural nodes** (post-F1) and there is **no EQI field** — map their doc's GREEN/YELLOW/RED EQI policy onto the real fields (`combined_confidence` + `v3_cert.abort`) as a suggested translation, clearly labeled as M02's suggestion for the M03 owner to adopt or adapt. ≤2 pages.

### D5 — Flag cross-module doc drift (do not fix)
Open a GitHub issue titled `docs: Module 01/03 design docs reference interfaces that diverged from Module 02's implemented output` listing, factually and politely: `docs/module_summery/Module_03_Equivalence_Engine.md` consumes "EQI" scores and "WIR-Type/WIR-Proc layers" that do not exist in M02's actual output (pointer to D4's contract doc); Module 01's summary describes `module_01_spec/src/` files that live on unmerged `feat/mod1/xml-semantic-graph`. Address it to the module owners; no edits to their files.

### D6 — `README.md` → rubric (a), small fixes
Verified issues: lists "three decoupled, containerized modules" — there are four (`module_04_ui` missing); "mathematically guarantee" overclaims relative to the project's own quantified-confidence framing (every other document says quantified confidence, not proof). Fix the module list, soften the guarantee sentence to the quantified-confidence framing, and add one status line pointing to the wiki for current per-module state. Check the Docker instructions still match `docker-compose.yml` while you're there. Don't restructure the rest.

## Wrap-up

- `git status` must show only doc files changed; test suite green (unchanged 246).
- PR to `develop`: `docs(mod2): reconcile Module 02 docs with implemented reality` — body: per-file classification table (file → rubric letter → action), the D5 issue link, and a note that the wiki was synced in a parallel session. Standard footer.

## WHAT NOT TO DO

- No code, test, eval, or wiki edits (wiki is a separate session).
- Do not rewrite the historical docs' bodies — banners only. The correction trail is thesis material; erasing it destroys evidence the project deliberately preserved.
- Do not touch M01/M03-owned docs, `eval/results/` reports, or the archive.
- Do not write any number you did not verify against a current report or the source during this session.
