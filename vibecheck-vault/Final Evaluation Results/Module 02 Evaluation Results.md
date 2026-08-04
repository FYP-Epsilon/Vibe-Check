> [!info] What this page is
> A plain-English report on Module 02 — what it does, how we tested it against the real IBM FLOW-BENCH dataset, what the numbers mean, and what's genuinely new about it. Numbers below were freshly re-run on 2026-08-03 against `main-demo` and matched byte-for-byte against the committed results in `module_02_extract/eval/results/`.

## 1. What Module 02 actually does

Module 02 is the **"code reader."** You give it a piece of Python code that an LLM wrote to implement a workflow (e.g., code that's supposed to "check inventory, then charge the customer, then ship the order"), and it does two things: (a) turns that code into a standard, structured map of what the code actually does (a **Workflow Intermediate Representation**, or **WIR**), and (b) produces a **confidence score** for how much you can trust that this code behaves the way it's supposed to.

It gets that confidence score from three independent checks, run one after another:

1. **V3 — does the code's shape make sense?** (`ast_extractor/`). This reads the raw structure of the Python code (loops, if/else branches, function calls) and builds the WIR map. If the code's structure is too broken or unreadable to map at all, everything stops here — there's no point running the next two checks on a map that might be wrong.
2. **V2 — what are all the possible paths through this code?** (`z3_sym_engine/`). This uses a mathematical solver (Z3) to explore, symbolically, what different input values would make the code take different branches — trying to reason about the code's behavior without actually running it. Honest caveat, stated plainly here rather than buried: on the kind of workflow code in this project's test corpus, this check currently contributes close to nothing extra — most of the real detection work is done by the next check.
3. **V1 — does the code actually behave like the map says?** (`dynamic_tracer/`). This *runs* the real code with a variety of random inputs and, separately, "runs" the WIR map itself as if it were a simplified interpreter of the code, then compares the two: same task calls, same order, same branch decisions, same return values? If the real code and its own extracted map disagree, that's a red flag — either the code has a bug, or the map failed to capture what the code really does.

These three checks combine into one confidence number between 0 and 1; code needs to score at or above 0.95 to be "accepted."

## 2. Evaluation results (FLOW-BENCH corpus + real LLM code, re-run 2026-08-03)

Because there's no dataset that comes with "this code is buggy / this code is correct" labels, Module 02's evaluation deliberately creates its own answer key by taking real code and introducing bugs on purpose (see §3 for exactly how) — then checking whether the module's confidence score actually drops for the buggy version.

### 2.1 Catching bugs we planted on purpose (synthetic mutants)

| What we measured | Result | Sample size |
|---|---|---|
| **Detection rate** — fraction of genuinely-bugged code correctly flagged | **99.5%** [97.4%–100%] | 210 planted bugs |
| **False-alarm rate** — fraction of correct, unmodified code wrongly flagged as buggy | **5.9%** [1.2%–16.2%] | 51 correct programs |

**In plain English:** when we take real, working workflow code and deliberately break it in a small way (e.g., swap two steps, delete a step, flip a condition), Module 02 catches the break 99.5% of the time. When we feed it correct, unmodified code, it wrongly cries "bug" only 5.9% of the time. That combination — very high catch rate, low false-alarm rate — is a strong result.

Breaking the detection rate down by the *type* of bug introduced (all held-out test data, not the data used to tune the module):

| Bug type                        | How many tried | How many caught | Catch rate |
| ------------------------------- | -------------- | --------------- | ---------- |
| Dropped a step                  | 51             | 51              | 100%       |
| Corrupted a container operation | 16             | 16              | 100%       |
| Wrong variable used             | 18             | 18              | 100%       |
| Flipped a decision condition    | 14             | 14              | 100%       |
| Swapped two branches            | 4              | 4               | 100%       |
| Reordered steps                 | 49             | 49              | 100%       |
| Cut the code short early        | 49             | 49              | 100%       |
| Changed a constant value        | 9              | 8               | 88.9%      |

### 2.2 The one honest weak spot: telling "equivalent" bugs apart from real ones

Some "bugs" we plant don't actually change what the code does in practice (e.g., an unreachable branch is altered, but that branch never runs) — these are called **equivalent mutants**, and correctly *not* flagging them is technically also a form of correctness.

**Result: only 11.1% [0.3%–48.2%] of equivalent mutants were correctly told apart from real bugs (n=9).**

This is a small, deliberately disclosed weak spot: with only 9 examples of this specific case in the test data, the confidence range is very wide, and we investigated it directly rather than ignoring it — 8 of the 9 cases turned out to already be borderline (the unmodified code itself scored close to the acceptance line), so the module isn't making a new mistake, it's inheriting an existing borderline case. Still, this number is reported honestly as-is, not smoothed over.

### 2.3 Catching real bugs from real LLMs (not planted — actually generated wrong)

This is the strongest evidence in the whole project: instead of planting fake bugs ourselves, we took code that three different LLMs (llama-3.1-8b, mixtral-8x7b, qwen3-next-80b) actually generated for the same tasks, and kept only the generations that were independently confirmed to genuinely misbehave (164 out of 303 generations).

| What we measured | Result |
|---|---|
| Detected the real, naturally-occurring bug (strict comparison mode) | **100.0%** (164 / 164) |
| Detected the real bug (cross-implementation comparison mode) | **93.3%** (153 / 164) |

**In plain English: every single time one of these three different LLMs actually wrote broken workflow code, Module 02 caught it.** This isn't a synthetic-bug artifact — it's real generation failures from real models.

### 2.4 Did it read the code's structure correctly?

| What we measured | Result |
|---|---|
| Structural accuracy of the extracted code map (WIR), vs. an independent check | **100%** (across all 101 base programs) |

## 3. How we evaluate this module, step by step

1. **Start with real workflow code, not invented examples.** We use 101 real Python programs derived from IBM's public FLOW-BENCH dataset.
2. **Plant bugs on purpose using known bug types.** We apply 8-9 different "mutation operators" (drop a step, swap two steps, flip a condition, etc.) to those 101 programs, producing 427 modified versions with a known, specific bug each.
3. **Split the data in half before touching the results.** Half the programs and mutants (CALIB) are used only to pick the module's pass/fail decision threshold; the other half (EVAL) is used only to measure the final numbers. This split is fixed with the same random seed every time, so the split itself can't be tuned to produce a good-looking result.
4. **Pick the threshold using a standard statistical method (Youden's J), not by hand.** The threshold that best separates "buggy" from "correct" scores on the CALIB half is chosen automatically, then frozen and applied unchanged to the EVAL half.
5. **Report every rate with a confidence interval**, using the same exact statistical method as Module 01, so a small sample never gets reported as if it were a precise, unshakeable number.
6. **Cross-check against real bugs, not just planted ones.** Separately from the planted-bug experiment, we ran three different LLMs on the same workflow-generation tasks and used their actual, naturally-occurring mistakes as a second, independent test (§2.3) — this guards against the risk that the module is only good at catching the *specific* kinds of bugs we thought to plant.
7. **Keep a visible history of corrections.** Every time a measurement bug was found in the evaluation methodology itself (three times, over the project's life), the old report was archived rather than deleted, and the new corrected numbers are shown side-by-side against the old ones in the committed reports — so nothing is quietly revised away.

## 4. What's genuinely new about this module

- **Checking LLM-written code against a diagram, after the fact, with no cooperation needed.** Module 02 doesn't need the LLM to explain itself, doesn't need special annotations in the code, and doesn't re-read the original English prompt — it treats the code as a black box and independently verifies it against the business process it's supposed to implement. A few very recent research systems do something similar for other domains (e.g., checking LLM-generated Ansible scripts) — Module 02's specific angle is using a **business-process diagram** as the source of truth, and producing a graded confidence score with a full audit trail rather than a plain yes/no.
- **A code map (WIR) with a "business order" view, not just a "written order" view.** Code is written in one order (functions defined top to bottom) but *executes* in a different order depending on what's called when. Module 02 produces both views, and the "execution order" view exists specifically because we measured that the two views actually disagree about task order in roughly **46% of real generated code samples** — meaning the naive "written order" view would have been silently wrong nearly half the time if this fix hadn't been made.
- **Using the code's own extracted map as its own truth-check.** Instead of comparing the running code against some separate hand-written "correct" reference, Module 02 compares the running code against *an interpretation of the very map it just extracted from that code*. If they disagree, that tells you the extraction itself might be unfaithful — so this one check simultaneously validates the code's behavior and the quality of the extraction step.
- **Treating the module's own verdict as something to be statistically calibrated, not hand-tuned.** The acceptance threshold, the confidence intervals, the held-out evaluation split, and the archived history of corrected measurements are all borrowed from standard classifier-evaluation practice and applied rigorously to a verification tool's own pass/fail line — something the underlying verification research literature doesn't usually do (it usually argues "this is sound," not "here is the operating point and its error bars").

**What's honestly *not* claimed:** the AST parsing, the Z3-based symbolic execution, and the general idea of "mutation testing" are all standard, well-known techniques — Module 02's contribution is combining them this way and calibrating the result, not inventing new algorithms. And the V2 (symbolic) layer, while it runs, currently contributes close to nothing extra on this project's kind of workflow code — the real detection power comes from V1 (dynamic tracing), and that's stated plainly rather than let the "three-layer" framing oversell it.

## Sources

- `module_02_extract/eval/results/calibration_report_differential.md` (regenerated 2026-08-03 via `calibrate_corrected.py`, seed 1234, matches committed numbers exactly)
- `module_02_extract/eval/results/session_b_report.md` (natural-bug corpus results)
- `module_02_extract/eval/results/e2_structural_report.md` (WIR structural accuracy)
- [[Module 02 - Verified IR Extraction/Module 02 Knowledge|Module 02 Knowledge]]
- [[Module 02 - Verified IR Extraction/Module 02 Novelty|Module 02 Novelty]]
- Unit tests re-run 2026-08-03: `module_02_extract/tests/` + `module_02_extract/eval/` — 256 passed, 9 skipped (skips are a Python-version-gated tracing feature, correctly inactive below Python 3.12)

## Links

- [[Full Project Evaluation Results]] · [[Module 01 Evaluation Results]] · [[Module 03 Evaluation Results]]
- [[../Module 02 - Verified IR Extraction/WIR Structure and Confidence Methodology|WIR Structure and Confidence Methodology]] — deep dive on the WIR's structure, a worked example, and exactly how the confidence formula and its threshold were built
- [[../Home|Home]] · [[../Project Overview|Project Overview]]
