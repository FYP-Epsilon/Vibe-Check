# SESSION MANDATE — Module 02, Session C: multi-implementation corpus (NIM model pool + behavioral admission + implementation-freedom experiments)

You are building the multi-implementation corpus for VibeCheck (`C:\Research\FYP\Vibe-Check`) — multiple real LLM-generated implementations per FLOW-BENCH requirement — and running the style-diversity experiments on it. This is the last research-risk item in Module 02; Module 03 (early-phase, teammate-owned, read-only) will consume this corpus's shape for equivalence clustering, so the data contract you write becomes the project standard.

**Branch**: check `gh pr view 30 --json state`. If merged → `feat/mod2/multi-impl-corpus` off `develop`; else branch off `fix/mod2/differential-compose-and-perturb` and note the stack in the PR. Baseline: **190 tests passing**.

## API key discipline (non-negotiable)

The NVIDIA NIM key is in the environment as `NVIDIA_API_KEY` (fallback: `NIM_API_KEY`). Read it with `os.getenv` at call time. **Never** echo it, log it, write it to any file, include it in error messages, or let it near a commit. First action of C0: if the env var is absent, STOP and tell the user to set it — do not proceed, do not stub it.

## Context you need (verified; re-read before relying on)

- Base corpus: `eval/corpus/uid_*.py` — 101 programs, each = deterministic dict-echo stub defs + a typed `def workflow(<params>)` implementing one FLOW-BENCH requirement. The original utterances are in `module_02_extract/inputs/conditional_ootb.yaml` (`tests[i].input.utterance`, uid in `_metadata.uid`).
- Admission machinery already exists: `eval/e3_correlation.py`'s recorder executes two implementations on shared seeded inputs and compares (stub-call sequence, return value) — code-vs-code, WIR-free, anti-circular. Reuse it; do not reimplement.
- Differential verification: `eval/calibrate.py::run_differential_verification(mutant_source, base_func_wir, base_source=...)` — post-Session-A: verdict = V1 only, τ=0.10 frozen (`eval/threshold.json`), FA on untouched bases 0.0588, genuine-bug detection 0.9952.
- The pipeline's known style limits: no imports (`SAFE_BUILTINS` has no `__import__`), attribute access unsupported in V2 (`visit_Attribute` absent — the adapter rewrites `obj.attr` → `obj["attr"]`, reuse its `AttributeRewriter` from `eval/flowbench_adapter.py`).

## Ground rules

- GitNexus workflow per `CLAUDE.md`; suite green after every task; stdlib-only for everything except the NIM HTTP calls (use `urllib.request` — do not add an `openai`/`requests` dependency).
- **Cache every raw API response to disk before any processing** (`eval/variants/raw/<uid>__<model-slug>__<sample>.json`) and make generation resumable — skip uids already cached. API budget cap: hard-stop after 400 total calls this session.
- Report measured numbers as-is. Two experiments below are *expected* to produce uncomfortable numbers — that is their purpose.

---

## C0 — Preflight

Env-var check (see above). One smoke call to `https://integrate.api.nvidia.com/v1/chat/completions` (OpenAI-compatible schema) with a trivial prompt to verify auth and connectivity. Choose a **pool of 3 model families** from the NIM catalog (e.g. a large Llama, a Mistral-family model, a Qwen-coder-family model — check current availability rather than assuming ids; record the exact model ids you settle on in the manifest). If a chosen model 404s, substitute and note it.

## C1 — Generation (`eval/gen_variants.py`)

Per uid (all 101), per model (3), one sample (temperature 0.7) → **303 raw generations**.

Prompt construction (this is the experiment design — keep it exact and record a prompt hash in the manifest):
- System: "You implement one Python function. Use ONLY the provided helper functions and builtins — no imports. Return only code."
- User: the FLOW-BENCH **utterance** for the uid + the **stub signatures** verbatim (defs with their parameter lists, described as 'available helpers, already defined — do not redefine them') + the required signature line `def workflow(<exact params from the base>)` with the instruction to implement the utterance's workflow logic in that function only.
- The LLM writes only the `workflow` body/function; the corpus's own stub defs are prepended mechanically afterward. This keeps the *environment* fixed and the *implementation style* free — which is the dimension being tested.

Extract the code block from each response; store raw + extracted. No judgment calls in this step.

## C2 — Normalization + static screening (`eval/gen_variants.py --normalize`)

Mechanical, recorded per variant in the manifest (`normalization_applied: [...]`):
1. Strip any model-added stub redefinitions and imports of things that are unused; a variant that *functionally requires* an import → static-reject (`reject_reason: "imports"`).
2. `AttributeRewriter` pass (`obj.attr` → `obj["attr"]`) — reuse the adapter's transformer.
3. Screening gates, each a distinct reject reason: parses; defines `workflow` with the exact base signature; calls only known stub names / `user_task` / builtins; no `async`/`yield`/`import` remaining.
4. Survivors → `eval/variants/normalized/<uid>__<model-slug>.py` (stubs prepended, self-contained like the base corpus).

Report the screening funnel (303 → parsed → signature-ok → clean) per model — this table is itself a finding about instructability.

## C3 — Behavioral admission (the correctness oracle)

For each normalized variant, run the E3 recorder against the **base** implementation on **N=100 seeded inputs** (higher than E3's 25 — admission errors poison everything downstream; use the base+variant guard-literal union and round-robin coverage, mirroring Session A's A2 rationale):
- `diff_rate == 0` → **admitted** (label: correct variant; caveat recorded: equivalence is N-bounded, same caveat language as E3).
- `diff_rate > 0` → **rejected-behavioral** → kept as the **natural-bug corpus** (label: `natural_bug`, with `diff_rate` and the first divergent input as evidence).

Manifest per variant: `{uid, variant_id, model, temperature, prompt_sha256, normalization_applied, screen: pass|<reason>, admission: {verdict, n_inputs, diff_rate, first_divergence_input}, source_file}`.

## C4 — The M03 data contract

`docs/module02/11_multi_impl_corpus_contract.md`: the manifest schema (field-by-field), the admission protocol (N=100 behavioral equivalence, anti-circularity statement), directory layout, and the **cluster ground truth M03's synthetic-variant protocol needs**: admitted variants of the same uid = one equivalence cluster (benign variation, should cluster together); rejected-behavioral variants = should isolate; the base program is each cluster's canonical member. Also note the F1-era change (WIRs contain no blank structural nodes). Keep it ≤2 pages — it's a contract, not a paper.

## C5 — The experiments (three, all instrument-reuse)

**C5a — Extraction robustness across styles**: run `run_v3_pipeline` on every admitted variant. Report: V3 abort-gate rate, crash rate with exception taxonomy, node_coverage distribution vs the base corpus's (all 1.0). This is E2's style-diversity extension — gold-F1 doesn't apply (variants legitimately differ structurally), robustness does.

**C5b — Implementation-freedom specificity (the headline)**: run `run_differential_verification(variant_source, base_wir, base_source=base)` for every **admitted** variant. These are behaviorally equivalent, differently-written correct programs — the false-alarm rate on them measures whether the certificate tolerates implementation freedom or punishes style. **Pre-registered expectation, write it in the report before running**: branch-structure differences will likely produce branch_point-count divergence even when stub sequences match, so FA here may be far above the 0.0588 base rate. If so, that is the finding — quantify it, break it down by divergence source (branch events vs task events vs exceptions — the comparator's normalized tuples tell you), and name the anticipated follow-up (a cross-implementation comparison mode that aligns on task events only) as backlog. **Do not implement that mode this session, and do not weaken the comparator to improve the number.**

**C5c — Natural-bug detection**: run the same differential verification on every **rejected-behavioral** variant. Detection rate on *real LLM bugs* (with CI), compared per-operator-style against the synthetic-mutant 0.9952 — the first non-synthetic detection figure in the project.

Output: `eval/results/multi_impl_report.md` — funnel table, admission stats per model, C5a/b/c sections each with their tables and the pre-registered-expectation paragraph, and honest caveats (N-bounded equivalence; single-sample-per-model; prompt-format sensitivity).

## C6 — Wrap-up

Suite green (190 + new unit tests: prompt builder, screening gates, admission plumbing — mock the HTTP layer, never call the API from tests). `gitnexus_detect_changes()`; commits per task; PR to `develop`: `feat(mod2): multi-implementation corpus via NIM model pool + implementation-freedom experiments` — body: funnel, admission stats, C5a/b/c headline numbers, M03 contract pointer, backlog items (cross-impl comparison mode; per-guard-site literal coverage carried from Session A). Append numbers to the session memory file.

## WHAT NOT TO DO

- No `src/` changes at all this session — C5b's expected bad number is measured, not fixed. `visit_Attribute` stays out (normalization covers it); the cross-impl comparison mode is next-session scope.
- Do not curate generations: no regenerating a variant because it failed screening or admission, no prompt-tweaking after the first full run (one prompt revision is allowed IF the C2 funnel shows a >50% parse-failure rate — record both prompt hashes and report both funnels).
- Do not let rejected variants leak into the admitted set or vice versa — the manifest verdict is load-bearing for M03's ground truth.
- Do not exceed the 400-call budget; do not retry a failed call more than twice.
- Key discipline as above — a leaked key in any committed file is a session-failing event.

## DEFINITION OF DONE

- 303 raw generations cached (or a documented shortfall with reasons); funnel table; admitted + natural-bug corpora on disk with complete manifest.
- M03 contract doc committed.
- `multi_impl_report.md` with C5a/b/c measured numbers, pre-registered expectations, and divergence-source breakdown for C5b.
- Suite green; PR open; memory appended; zero API-key bytes anywhere in the repo.
