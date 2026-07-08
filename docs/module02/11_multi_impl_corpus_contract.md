# Multi-Implementation Corpus — Data Contract (Session C)

> **Scope**: `eval/variants/` — real LLM implementations of each FLOW-BENCH requirement, behaviorally admitted against the base corpus.
> **Consumer**: Module 03 (equivalence clustering) reads this corpus for synthetic-variant ground truth. This document is the contract between Module 02 (producer) and Module 03 (consumer) — treat field renames as a breaking change.
> **Status**: generated once per session; not regenerated automatically (`eval/gen_variants.py`, `--normalize`, `--admit`).

## 1. Directory layout

```
eval/variants/
  raw/<uid>__<model-slug>.json          # C1: cached raw NIM response + extracted code (or {error})
  normalized/<uid>__<model-slug>.py     # C2 survivors: self-contained, real base stub defs prepended
  manifest.json                          # one record per (uid, model) attempt -- see schema below
```

`<model-slug>` is one of `llama-3.1-8b`, `mixtral-8x7b`, `qwen3-next-80b` (§4 of the session record has the exact NIM model ids and the substitution note for the unavailable Qwen-coder variant).

## 2. Manifest schema (`eval/variants/manifest.json`)

One record per (uid, model) generation attempt, in three layers accumulated by C1→C2→C3:

| Field | Set by | Type | Meaning |
|---|---|---|---|
| `uid` | C1 | int | Base corpus program id (`eval/corpus/uid_<uid>.py`) |
| `variant_id` | C2 | str | `"<uid>__<model-slug>"`, unique key |
| `model` | C1 | str | Full NIM model id |
| `prompt_sha256` | C1 | str | Hash of the exact (system, user) prompt sent — reproducibility/audit |
| `temperature` | C1 | float | Sampling temperature (0.7, fixed) |
| `screen` | C2 | str | `"pass"` or a reject reason: `parse_error`, `imports`, `no_single_workflow_def`, `signature_mismatch`, `async_or_yield`, `unknown_call`, `generation_failed` |
| `normalization_applied` | C2 | list[str] | Mechanical transforms applied (e.g. `attribute_rewrite`, `stripped_unused_imports:...`) |
| `source_file` | C2 | str, present iff `screen=="pass"` | Path (relative to `eval/`) to the self-contained normalized program |
| `admission` | C3 | dict or `null` | `null` if `screen != "pass"` (never behaviorally tested). Otherwise: `{verdict, n_inputs, diff_rate, first_divergent_input}` |
| `admission.verdict` | C3 | str | `"admitted"` \| `"rejected_behavioral"` \| `"error"` |
| `admission.diff_rate` | C3 | float | Fraction of `n_inputs` where variant and base observably diverged |
| `admission.first_divergent_input` | C3 | dict or `null` | First diverging input + both sides' `(stub_call_sequence, return_value)`, for debugging |

## 3. Admission protocol

**What it measures**: whether a normalized variant is *behaviorally* the same program as its base, by executing both directly on the same concrete inputs and diffing observable behavior (stub-call sequence + return value) — the same code-vs-code, WIR-free method `eval/e3_correlation.py` already uses for mutation calibration, reused directly (`_instrument`, `run_recorded`), not reimplemented.

**N=100** (vs. E3's N=25 — admission errors poison everything downstream, so this needs tighter bounds). Inputs are generated **round-robin-first** over the **union** of the base's and the variant's own guard-literal pools (mirrors Session A's A2 fix — a model that renames a guard literal, e.g. base's `"high"` vs. a variant's `"urgent"`, must have both literals actually exercised within the N-input budget, or the two sides can agree vacuously on every run). This input generator is an independent, local reimplementation, not an import of `RandomizedDifferentialTester` — same anti-coupling rule E3 already established: admission establishes ground truth, so it must not share machinery with the verification pipeline C5b/C5c measure against.

**Anti-circularity**: the WIR never appears on either side of this comparison. Admission is a property of the *code*, established independently of anything Module 02's V1/V2/V3 layers do.

**Verdict**:
- `diff_rate == 0` → **admitted**. Caveat (same as E3): equivalence is bounded by N=100 — a variant that differs only on inputs outside this sample looks equivalent here but may not be with a larger sample.
- `diff_rate > 0` → **rejected_behavioral**. Kept, not discarded — see §5.

## 4. Cluster ground truth (for Module 03)

Per base `uid`:

- **One equivalence cluster** = the base program + every variant with `admission.verdict == "admitted"` for that uid. These are benign implementation-style variation (different variable names, control-flow shape, API-call ordering) that should cluster together under Module 03's equivalence checking.
- The **base program is each cluster's canonical member** (it is the FLOW-BENCH-derived reference; every variant is admitted *against* it, never the reverse).
- Every `rejected_behavioral` variant is its own **singleton** — it should NOT cluster with the base or with any admitted variant. It is evidence Module 03's clustering is over-merging if it does.
- `screen != "pass"` variants (static-screening rejects) are not part of the corpus at all — they never became executable programs.

Session C's measured admission rate is low (~11% of clean/screened variants) — see `eval/results/multi_impl_report.md`. Most rejections are genuine stub-call-sequence divergence, not return-value artifacts (checked directly): variants often guess wrong about a stub's return *shape* (only signatures, not bodies, were shown per the generation protocol — see report), producing real `KeyError`/`TypeError` crashes or a different control-flow interpretation of the same utterance. Module 03 should expect small clusters (frequently size 1: base only, or base + 1–2 admitted variants), not large ones.

## 5. Natural-bug corpus

`rejected_behavioral` variants are a first-class deliverable (label `natural_bug`), not discarded output — they are C5c's real-LLM-bug detection corpus, the first non-synthetic detection figure in the project (`eval/results/multi_impl_report.md`).

## 6. F1-era note

Base-corpus WIRs (`run_v3_pipeline` output) contain **no blank structural/bookkeeping nodes** as of the F1 mechanical-fixes session (`contract_bookkeeping_nodes` post-pass, node/edge P/R/F1 all 1.0000) — Module 03 does not need to special-case or filter merge/exit bookkeeping nodes when consuming WIRs for equivalence checking.

## 7. Comparison mode for cross-implementation equivalence checking (Session D)

The differential comparator (`src/dynamic_tracer/comparator.py::DifferentialComparator`) takes a `comparison_mode` parameter (`"strict"` default, or `"task_only"`), threaded through `RandomizedDifferentialTester` / `run_v1_pipeline` / `eval/calibrate.py::run_differential_verification`. **Any M03-adjacent consumer doing cross-implementation equivalence checking against this corpus (an admitted variant vs. its base's WIR, or variant vs. variant) should pass `comparison_mode="task_only"`, not the default `strict`.** Two independently-written but behaviorally-equivalent implementations legitimately differ in branch structure (different guard nesting, extra defensive checks, a different control-flow shape for the same task) — `strict` mode treats that structural difference as a mismatch (measured false-alarm rate 0.25 on this corpus's 20 admitted variants), while `task_only` drops branch-decision events from the comparison entirely and measures only task-observable behavior (stub-call sequence + exceptions), recovering most of that false-alarm rate (0.25 → 0.10, with the residual driven by exception-class divergences that correctly still compare in either mode). `strict` remains correct — and is the pipeline's default — for same-lineage comparison (a mutant vs. its own base), where branch-decision divergence is real detection signal; do not use `task_only` there, it measurably weakens mutation detection (see `eval/results/cross_impl_mode_report.md`'s D3 control table). Known gap in both modes: a divergence that is *only* a different return value with an identical call sequence is invisible to V1 traces either way (V1 never observes return values) — named as a backlog item, not yet built.
