> [!info] What this page is
> A plain-English report on VibeCheck as a whole — what problem it solves, what happens when all three modules run together, the real end-to-end numbers, how those numbers were produced, and what's genuinely new about the whole system (as opposed to any one module). Numbers below were freshly re-run on 2026-08-03 against `main-demo` and matched the committed results in `demo/eval_e2e/results/` within expected run-to-run variance (see §3).

## 1. What the whole system does, in one paragraph

"Vibe coding" — asking an LLM to write code from a description — produces code fast, but business processes have hard requirements (do these steps in this order, don't skip this approval, don't loop forever) that plausible-looking code can silently break. VibeCheck's answer is: **don't trust the code, and don't trust the LLM to check itself.** Instead, take the original business diagram and the LLM-generated code, turn *both* into independent, formal mathematical objects using completely separate modules that never see each other's input, and let a neutral, automatic checker (Module 03) decide whether they actually agree. The answer is never a vague "looks fine" — it's a specific `COMPLIANT`, a `VIOLATION` with a concrete example of what went wrong, or an honest `INCONCLUSIVE` when the evidence genuinely isn't enough to say either way.

```
BPMN diagram  →  Module 01 (rulebook writer)   →  formal rules
LLM's code    →  Module 02 (code reader)        →  code map + confidence score
                                                          ↓
                            Module 03 (referee) compares rules vs. code map
                                                          ↓
                    COMPLIANT  /  VIOLATION + example  /  INCONCLUSIVE
```

**The one design decision that matters most:** Module 01 (which reads the diagram) never looks at the code, and Module 02 (which reads the code) never looks at the diagram. They only meet inside Module 03, as two independently-produced objects. This matters because if either module could "peek" at the other's input, it would be too easy for the system to quietly bend its own judgment to make things match — which would defeat the entire point of an independent check.

## 2. End-to-end evaluation results

Real business-process diagrams don't come with a label saying "this LLM-written implementation is correct" or "this one is buggy" — so, like Modules 01 and 02, the full-pipeline evaluation builds its own ground truth: start from a real diagram-and-code pair that's been independently confirmed to work correctly end to end, then deliberately introduce a specific, known kind of bug, and check whether the whole pipeline's final verdict changes the way that bug predicts.

**Gold set:** 18 real (diagram, working implementation) pairs from FLOW-BENCH — pairs where we independently confirmed the implementation genuinely passes every check the pipeline can currently make.

| Test | What it measures | Result |
|---|---|---|
| **Abstention rate** | Out of 60 order-mutation trials (swap two steps, or delete a step), how often the pipeline honestly said "I can't tell" instead of guessing | **38.3%** [26%–52%] |
| **Detection rate** | Out of the trials where it *did* commit to an answer, how often it correctly caught the introduced bug | **16.2%** [6%–32%] |
| **False-alarm rate** | Out of 9 trials where we changed something *without* actually breaking the logic, how often the pipeline wrongly cried "bug" | **0.0%** [0%–34%] |
| **Counterexample quality** | Out of the bugs it correctly caught, how often the example it showed you actually named every task the broken rule was about | **83.3%** [36%–100%] |

**Read this plainly, because the shape of the result matters as much as the numbers:** the pipeline currently misses more order-swap and step-deletion bugs than it catches outright (16.2% detection) — but it is also **never fooled into a false alarm on correct code (0.0%)**, and a large share of its "misses" (38.3%) are actually honest refusals to guess, not wrong guesses. Digging into *why* it abstains so often: when a step is deleted entirely, that step's own "did this happen" marker often disappears completely from what the code-side checker can observe — so the pipeline correctly says "I can no longer see whether this happened at all," rather than confidently (and wrongly) saying "still fine." Broken down by bug type:

| Bug type | Trials | Correctly caught | Missed | Honestly abstained |
|---|---|---|---|---|
| Delete a step | 38 | 0 | 15 | 23 |
| Swap two adjacent steps | 22 | 6 | 16 | 0 |

Notice that deleting a step abstains far more often (23 of 38) than being wrongly waved through (15 of 38) — exactly the "can't observe it, so don't guess" behavior described above. Swapping two steps, by contrast, never triggers an abstention — both steps still visibly happen, just in the wrong order, so the pipeline always commits to an answer; it's just currently right only 6 times out of 22.

**Honest summary, stated the way this project states it internally:** this is a pipeline that is currently better at *not lying* than at *catching everything* — 0% false alarms, meaningful honest abstention, but a real, open gap in outright detection rate that the project doesn't hide behind the more flattering-looking abstention number.

## 3. How we evaluate the full pipeline, step by step

1. **Start from real, independently-confirmed-correct pairs.** We only use (diagram, code) pairs from FLOW-BENCH where the implementation has already been separately confirmed to pass cleanly end-to-end — this is the "gold" baseline every mutation is measured against.
2. **Introduce a small, specific, known kind of change** — either an order-mutation (delete a step, or swap two adjacent steps) that should genuinely break at least one rule, or a "decoy" change (e.g., change an unrelated constant) that should *not* break anything, to test for false alarms separately.
3. **Run the mutated version through all three modules, in sequence, exactly like a real user would** — Module 01's rulebook for that diagram, Module 02's code map for the mutated code, Module 03's final verdict comparing the two.
4. **Compare the final verdict against what the mutation predicts.** A step-deletion or step-swap should, in principle, produce a `VIOLATION`; if the pipeline says `COMPLIANT` instead, that's a miss; if it says `INCONCLUSIVE`, that's reported as its own honest category, not lumped in with either a hit or a miss.
5. **Report every rate with a confidence interval**, same discipline as Modules 01 and 02 — with only 18 gold pairs and 60-ish trials, these are small-sample numbers, and the range is the honest picture, not the single percentage.
6. **Re-run to check the result is stable, not a fluke of one run.** We independently re-ran this exact evaluation twice more this session; the results matched within a small amount of expected variance (a single trial occasionally flips between "missed" and "honestly abstained," because which random example gets picked isn't pinned down by a fixed random seed in this part of the harness) — the headline numbers above (18 gold pairs, ~16% detection, ~38% abstention, 0% false alarms) held steady across every run.

**A new addition this session: testing the real, deployed system, not just an internal script.** Previously, these end-to-end numbers only came from an internal test script that calls all three modules' code directly, in one process — a fair evaluation, but not proof that the actual, deployed, separately-running services (each module runs as its own independent web service in this project) can be wired together and driven the same way in practice. This session, we built and verified a real live version of that: a new page in the project's web interface (`module_04_ui/src/e2e_orchestrator.py` + the "🔄 E2E Pipeline" page) that sends a real diagram and real code, over the network, to the three actually-running services in turn, and shows the final verdict — including a working example that correctly caught a real planted bug (an order-swap), with a readable counterexample, through the real deployed system, not just the internal test script. This closes a gap the project's own notes had previously and correctly flagged: that the full pipeline was demonstrated by an internal script, but had no live, click-through demo of the actual deployed `/check` endpoint.

## 4. What's genuinely new about the system as a whole

- **Checking generated code against a diagram, after the fact, with zero cooperation from the LLM.** No special prompting, no annotations added to the code, no re-reading the original request in natural language — the code is treated as untrusted, finished output, and checked independently against the business process it's supposed to implement.
- **Two tracks that never see each other, meeting only as math.** The diagram-reading half and the code-reading half are built, and run, completely independently — they only come together inside the referee module, as two formal objects, specifically to prevent either side from quietly bending its interpretation to match the other. We're not aware of a published system that enforces this kind of hard separation for this exact problem (checking LLM-generated workflow code against a business-process diagram).
- **A three-way verdict, not a pass/fail.** Most comparable systems in the research literature give a yes/no (or a single confidence score). This system's final answer is always one of `COMPLIANT`, `VIOLATION` (with a concrete counterexample), or `INCONCLUSIVE` — and `INCONCLUSIVE` is a first-class, intentional outcome, not an error state. As the results in §2 show, honest abstention is currently a large and meaningful part of how this system behaves, and it's treated as a feature to measure and report, not a failure to hide.
- **A live, working demo of the full chain, this session, against the actual deployed services** — described in §3 — not just an internal test script.

**What's honestly *not* claimed:** the full-pipeline detection rate (16.2%) is a real, open weakness, not a solved problem — it should never be quoted on its own without the abstention rate and false-alarm rate next to it, because "16%" alone reads as a failing grade when the honest picture is "a system that mostly declines to guess rather than guessing wrong, on a still-small sample." The sample size (18 gold pairs, 60 trials) is small by design — every number above carries its confidence interval specifically so this isn't mistaken for a large-scale, high-precision measurement.

## Sources

- `demo/eval_e2e/results/e2e_eval_report.md` and `e2e_eval_results.json` (committed numbers; independently reproduced twice this session via `python -m demo.eval_e2e.harness`, small expected variance noted in §3)
- `module_04_ui/src/e2e_orchestrator.py` and the "🔄 E2E Pipeline" page in `module_04_ui/src/app.py` (the new live, deployed-system demo built and verified this session, including a real caught violation with counterexample, shown in the actual browser UI)
- `demo/sample_inputs/` — ready-made example diagram+code pairs covering COMPLIANT, VIOLATION, INCONCLUSIVE, and engine-rejection cases, for anyone who wants to try the live demo themselves
- [[../Project Overview|Project Overview]]
- [[../Home|Home]]

## Links

- [[Module 01 Evaluation Results]] · [[Module 02 Evaluation Results]] · [[Module 03 Evaluation Results]]
- [[../Home|Home]] · [[../Project Overview|Project Overview]]

> [!warning] Numbers elsewhere in this vault are stale
> `Evaluation Summary (Poster).md`, `Home.md`, and `Project Overview.md` still headline an older E2E run (6 gold pairs, 35.7% detection, 46.2% abstention) from before the property-suite ingestion was expanded, and the poster page's Module 03 section still states the `/check` endpoint "defaults to a placeholder" — which is no longer accurate (see §3's note on the new live orchestrator). This folder's numbers are the current ones as of 2026-08-03. Reconciling the older pages was flagged to the user as a separate decision, not silently done here.
