---
name: next-phase-plan
description: Post-PR#28 plan — Fable implements directly (no more Sonnet prompts); NIM key offered for multi-impl model pool; backlog approved; M03 early-phase means M02 defines the shared corpus schema
metadata:
  type: project
---

Decisions from 2026-07-07 (after PR #28 merged into develop):

1. ~~Fable implements directly from here on~~ **Corrected next day: the prompt-for-Sonnet workflow continues** — the user asked for a Session A prompt (saved at `.claude/prompts/sonnet_module02_sessionA_prompt.md`). Fable's role stays: design, prompts, post-session verification.
2. **NVIDIA NIM API key** will be provided for a model pool to generate multiple LLM implementations per FLOW-BENCH requirement. Key handling: environment variable (`NVIDIA_API_KEY` or `NIM_API_KEY`), never in chat, never committed; loaded via `os.getenv` in eval scripts.
3. **M03 owner is early-phase** → M02 has the flexibility (and responsibility) to define the multi-implementation corpus schema that M03's equivalence clustering will consume. Deliverable includes a data-contract doc for the M03 owner.
4. **Backlog approved.** Session plan:
   - **Session A (instrument-facing, eval-only)**: (A1) differential-mode composition discount — in `eval/calibrate.py`, stop letting self-referential V2 floor the verdict (`combined = v1` in differential mode, V2 reported but not composed; see [[round3-verified-findings]] Round-3h V2-masking caveat and the comment in `eval/test_calibrate.py::test_value_only_guard_mutation_now_detected`); (A2) constant-perturb input sharpening — string pool for mutant scoring should include BOTH base and mutant guard literals so the mutated comparison is exercised reliably (currently 0/9 detected; confidence moves 0.8→0.32 but not past τ). Re-run calibration + E3, archive superseded reports, expect constant-perturb and the stub-free-scalar class to move.
   - **Session B (robustness batch, src/)**: typed per-layer `/verify` statuses; wall-clock timeout around `_run_verification`; `merge_states` excise (recommend: delete the dead QCE-merge claim path, keep k-bounding as the honest story); n_runs justification (fixed n with power note, or CI-stopping).
   - **Session C (multi-impl corpus, needs NIM key)**: `eval/gen_variants.py` (model pool, constrained prompt: use provided stub signatures, no imports); mechanical normalization (reuse adapter's AttributeRewriter; `visit_Attribute` in V2 evaluator lands here if normalization is insufficient); admission oracle = behavioral equivalence vs FLOW-BENCH reference on N=100 seeded inputs (E3 recorder machinery — code-vs-code, anti-circular); rejected variants kept as natural-bug corpus; manifest schema doc for M03; then re-run E1/E2/E3 across variants for the style-diversity dimension.

Order rationale: A before C because the multi-impl variants will include stub-free/scalar styles where V2-masking (A1) would corrupt detection numbers; A2's sharpening also matters more once variants diversify guard usage.
