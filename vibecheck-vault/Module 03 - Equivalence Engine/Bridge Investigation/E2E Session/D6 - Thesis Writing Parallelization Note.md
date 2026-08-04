# D6 — Thesis-Writing Parallelization Note

> Which chapters can be written *now*, before any of D4's milestones land. Repo at
> `main @ 0daf57e`.

The organizing claim: **the majority of this thesis is already writable, and one chapter that
looks like it needs implementation does not.**

## Writable now — no implementation required

### 1. The three bridge investigations (already thesis material)

`vibecheck-vault/Module 03 - Equivalence Engine/Bridge Investigation/` holds three completed
investigations with verification logs. These are a methods-and-findings chapter as they stand.
Nothing in this session contradicted them; every established fact I re-derived held.

### 2. Module 02's chapter (exists in draft)

Built on the self-referential-validation negative result. Cite numbers only from the vault's master
numbers table — genuine-bug detection 0.9952 (n=210), **427** mutants not 429. Methodology is
VERIFIED-SOURCE from `eval/calibrate.py`'s docstring: 50/50 stratified split with fixed seed,
Youden's J on CALIB, exact Clopper–Pearson on held-out EVAL; `eval/threshold.json` records
`τ = 0.1`, `youdens_j = 0.96`, `seed = 1234`.

### 3. Architecture chapter — D1 and D2 are the content

Both designs are complete and evidence-tiered. The chapter's argument (dual-track independence, the
convergence point, why the placeholder property was a structural gap and not an oversight) needs no
running system. D1's tier-gating table and D2's blast-radius table are figures.

### 4. **The evaluation-scope chapter — writable now, and this is the non-obvious one**

D3 §1's corpus inventory and construct-coverage table are **fully measured already**
(VERIFIED-EXPERIMENT, this session): 48 specs, 29 exportable, 43 e2e-runnable pairs, 427 mutants of
which 96 are eligible and 131 gateway-blocked, and the construct table showing 0 gateway-bearing
and 0 `userTask`-bearing specs in the eligible set. None of this needs a single verdict to be
computed. It establishes the thesis' scope honestly and pre-empts the obvious examiner question.

### 5. A findings chapter that does not depend on the e2e system working

Five measured results, all VERIFIED-EXPERIMENT this session, none requiring the integration:

- **Module 01 admits no gateway-bearing spec.** 19 hard-fail, and the failing set is *exactly* the
  `<exclusiveGateway>` set (set equality tested true). 0/48 specs reach `PASS`. This localizes the
  entire branching gap to one Phase-3 gate — a genuinely useful result about the tool.
- **The two sides' atom vocabularies are disjoint by construction.** 0 of 116 spec atoms can match;
  `semantic_match()` returns bare task names (VERIFIED-SOURCE, `lifter.cpp:135`) while Module 01
  emits `start_`/`done_` prefixes. Underlying name matching is fine at 86.0% mean exact match.
- **Only 17.6% of the P1 tier is checkable against code**; 82.4% reference spec-only `node(...)`
  control nodes. A synthesis-coverage metric that no existing evaluation would have revealed.
- **The dominant divergence mode is omission (23/43 pairs), and the precedence property shape is
  vacuously satisfied by omission** — with a truth table over Module 01's own evaluator to prove it.
- **Witness spuriousness.** 10 of 11 of the current lifter's extra detections rest on functions
  never called. This is the most publishable single finding here: a verifier can post a higher
  detection rate while producing witnesses that do not correspond to any execution.

That last one deserves emphasis for thesis framing. It generalizes the Module 02 chapter's theme —
Module 02 found that self-referential validation cannot detect logic bugs; this finds that a
*structurally mis-scoped* lifting can appear to detect them while explaining them wrongly. Two
instances of the same underlying point (an evaluation artifact masquerading as capability) make a
stronger thesis narrative than either alone, and the second instance is measured, not argued.

### 6. Methodology chapter on labeling-oracle artifacts

D3 §4.4: using a naive single-successor walk to derive spec task order produced an apparent 44.4%
false-positive rate that fell to **0.0%** once restricted to the 24 of 29 specs where the walk is
complete. A worked example of an artifact that would have been written up as a tool defect. Short,
concrete, and it demonstrates evaluation discipline to an examiner.

## Needs implementation before writing

| Chapter content | Blocked on |
|---|---|
| E2E detection/false-alarm/INCONCLUSIVE rates with CIs | M2 |
| Paired lifting-model comparison (D2's 53.2% vs 40.4% confirmed against the compiled lifter) | M0.1 + M3 |
| Witness-validity metric at corpus scale | M3 |
| Phase B/C behavioral-equivalence metrics | M0.1 |
| Coverage-tier results | M4.1 |
| Demo walkthrough | M5 |

Note the asymmetry: the *designs* and *scope* are writable; only the **numbers** are blocked. And
the emulated measurements in D2 §5 mean even the paired-comparison section can be drafted with
placeholders whose expected magnitudes are already known — the compiled-lifter run confirms or
refutes a stated prediction rather than filling a blank. That is a stronger position to write from,
and it also means a discrepancy between the emulation and the compiled lifter is itself a
reportable finding rather than a crisis.

## Suggested writing order

1. Evaluation-scope chapter (§4) — fully measured, unblocked, and it frames everything else.
2. Findings chapter (§5) — five measured results, no integration needed.
3. Architecture chapter (§3) — D1 + D2 as written.
4. Fold in the bridge investigations (§1) and the Module 02 chapter (§2), which exist.
5. Methodology note on labeling artifacts (§6).
6. Leave only the results tables blocked on M2/M3.

**One discipline note.** Every number in this session's documents is tagged with an evidence tier
and every figure is reproducible from `e2e_verification_log.json`. When these move into thesis
prose, keep the measured/designed distinction the vault maintains — several of the figures here
(the 53.2%/40.4% pair especially) are **emulated in Python, not observed from the compiled
lifter**, because `import vibecheck_lifter` fails in this environment (VERIFIED-EXPERIMENT). Writing
them as measured results of the C++ system would be exactly the kind of overclaim the rest of this
project has been careful to avoid.
