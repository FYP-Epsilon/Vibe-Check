# Multi-Implementation Corpus: Style-Diversity Experiments (Session C)

Corpus: `eval/variants/` -- see `docs/module02/11_multi_impl_corpus_contract.md` for the manifest schema and admission protocol.

## Corpus funnel

- Raw generations attempted: 294 / 303 target (shortfall: 9, see 'Generation shortfall' below)
- Clean (screened, self-contained) variants: 184
- Admitted (behaviorally == base, N=100): 20
- Rejected-behavioral (natural-bug corpus): 164

### Generation shortfall

`qwen/qwen3-next-80b-a3b-instruct` began failing consistently (read-timeouts and connection resets) after 49/101 successful generations, confirmed via repeated direct health-check probes spaced across the session (all failed) -- a sustained NIM-side outage/throttle for this specific model, not a client bug (the other two models kept succeeding normally throughout, including concurrently with the qwen failures). 49/101 qwen generations and the resulting downstream counts are reported as-is, per the session mandate's explicit allowance for a documented shortfall.

## C5a -- Extraction robustness across styles

V3 (`run_v3_pipeline`) run on every ADMITTED variant (the same set C5b verifies) -- gold-F1 doesn't apply here (variants legitimately differ structurally from the base), robustness does.

- n = 20
- V3 abort-gate rate: 0.0000
- Crash rate (V3 itself raised): 0.0000
- Exception taxonomy: {}
- node_coverage: mean=1.0000, min=1.0000
- Base corpus's own node_coverage is 1.0000 for all 101 programs (F1 baseline).

## C5b -- Implementation-freedom specificity (headline)

**Pre-registered expectation** (written before running): admitted variants are behaviorally equivalent to the base by construction (diff_rate==0 over N=100 inputs) but were independently written by a different model -- branch-structure differences (extra guards, different control-flow shape, different stub-call counts even when the OBSERVABLE sequence matches on the sampled inputs) will likely still diverge on `branch_point` events the differential comparator tracks, even when task-event sequences agree. False-alarm rate here is therefore expected to sit well above the base rate (0.0588, Session A) -- this measures whether the certificate tolerates implementation freedom or punishes style, and a high number IS the finding, not a defect to fix this session.

- n = 20 admitted variants
- False-alarm rate (raw): 0.2500 (95% CI [0.087, 0.491], 5/20)

**Confound check**: an admitted variant of a base program that is ITSELF already flagged (scores below tau against its own WIR -- the 0.0588 base false-alarm class from Session A) would inherit that flagged status regardless of style -- that would be the base's own coverage weakness showing through, not the certificate punishing implementation freedom. Checked directly: of the 13 distinct base programs underlying these 20 admitted variants, **0 are pre-flagged**. Base-controlled false-alarm rate (excluding variants of a pre-flagged base): 0.2500 (95% CI [0.087, 0.491], 5/20).
The controlled rate equals the raw rate exactly here (zero pre-flagged bases in this sample) -- the confound does not apply; these 5 flags are genuine implementation-freedom false alarms, not inherited base-coverage weakness.

- Divergence-source breakdown across flagged variants' failing runs (comparator `divergence_points` event-type tallies, pooled across all flagged variants' runs): {"exception": 20, "branch_point": 70}

That pooled tally includes `exception` divergences (20/90), which are NOT branch-structure differences -- they mean a flagged variant crashed on one of C5b's 10 sampled inputs (seed=42), a case the N=100 admission check in C3 may simply not have sampled. The pooled number alone cannot say whether the 5 flagged variants are uniformly "style-punished" or whether some are admission-N gaps. Per-variant breakdown:

| variant | uid | variant combined | base combined | has exception? |
|---|---|---|---|---|
| 1__mixtral-8x7b | 1 | 0.0000 | 0.1000 | yes |
| 2__llama-3.1-8b | 2 | 0.0000 | 0.5000 | no |
| 3__qwen3-next-80b | 3 | 0.0000 | 0.3000 | no |
| 4__qwen3-next-80b | 4 | 0.0000 | 0.8000 | no |
| 42__llama-3.1-8b | 42 | 0.0000 | 0.1000 | yes |

Reading the split: bases sit at 0.1-0.8 combined confidence, not uniformly at a healthy score -- two of the five flagged variants (uids scoring 0.1 on their own base) sit on the Session-A threshold floor themselves, where base and variant are both weak and the flag is marginal rather than a clean style penalty. The honest read is **3/5 are clear implementation-freedom false alarms** (variant collapses well below a non-degenerate base, no exception involved) and **2/5 are marginal / exception-driven** (either the base itself is already near the floor, or the divergence is a crash the N=100 admission check didn't happen to sample, not a pure branch-structure penalty). The headline ("the certificate does not tolerate implementation freedom for this corpus") still holds directionally, but "branch-structure specifically" is too strong a claim for the full set of 5 -- it applies cleanly to the clear-style subset only.

Backlog (named, not implemented this session, per mandate): a cross-implementation comparison mode that aligns on task events only (ignoring branch-decision divergence) would likely recover most of this false-alarm rate for implementation-freedom cases specifically, without touching the mutation-detection numbers (which need branch-decision sensitivity, per Session A/F2). Not built here -- comparator was not weakened to improve this number, per explicit instruction.

## C5c -- Natural-bug detection

Detection rate on REJECTED-BEHAVIORAL variants (real LLM bugs, not synthetic mutations) -- the first non-synthetic detection figure in the project. Compare against the synthetic-mutant genuine-bug detection rate of **0.9952** (Session A).

**Read this rate together with its exception/logic split below -- not on its own.** A large share of this corpus is a model raising an exception (KeyError/TypeError) from guessing wrong about a stub's return SHAPE, because the generation protocol showed only stub signatures, not bodies (deliberate -- see the M03 contract doc). A crash of that kind is trivially detectable (both traces diverge immediately, maximally) and is only PARTIALLY a natural "bug" in the sense of flawed reasoning about the utterance -- it is partly harness-induced (the model was never shown enough to get the shape right). Do not cite the raw figure below as "detects natural logic bugs" -- cite the logic-class row.

- n = 164 rejected-behavioral variants
- Detection rate (all): 0.9634 (95% CI [0.922, 0.986], 158/164)

By divergence class (classified from the admission record's `first_divergent_input` -- already computed in C3, no extra runs needed):

| class | n | detected | rate | 95% CI |
|---|---|---|---|---|
| exception | 96 | 96 | 1.0000 | [0.962, 1.000] |
| logic | 68 | 62 | 0.9118 | [0.818, 0.967] |

`exception`: either side raised (a crash-shaped divergence -- trivially detectable by construction). `logic`: both sides ran to completion but produced different observable behavior (call sequence and/or return value) -- the harder, more meaningful class, and the one closest to "genuine reasoning bug about the utterance."

By model:

| model | n | detected | rate |
|---|---|---|---|
| llama-3.1-8b | 81 | 80 | 0.988 |
| mixtral-8x7b | 43 | 43 | 1.000 |
| qwen3-next-80b | 40 | 35 | 0.875 |

## Caveats

- Admission equivalence is N=100-bounded (same caveat as E3): a variant differing only on unsampled inputs looks equivalent here but may not be with a larger sample.
- Single sample per (uid, model) -- no repeated-sampling variance estimate for any one model's output distribution.
- Prompt-format sensitivity: stub SIGNATURES only were shown, not bodies (deliberately, to test genuine implementation freedom without leaking the adapter's echo-shape) -- this is very likely why the admission rate is low (~11% of clean variants): many rejections are the model guessing wrong about a stub's return shape (KeyError/TypeError), not benign style variation. See the M03 contract doc and C5c's exception/logic split for this finding in full.