> [!info] What this page is
> A plain-English report on Module 01 — what it does, how we tested it against the real IBM FLOW-BENCH dataset, what the numbers actually mean, and what's genuinely new about it. Written so someone with no background in formal verification can follow it. Numbers below were freshly re-run on 2026-08-03 against `main-demo` and matched byte-for-byte against the committed results in `module_01_spec/eval/results/`.

## 1. What Module 01 actually does

Module 01 is the **"rulebook writer."** You give it a business process diagram (a BPMN 2.0 file — the boxes-and-arrows diagrams companies use to describe a workflow, like "receive order → check stock → charge payment → ship"), and it produces a strict, formal **rulebook** that says exactly what the process is and isn't allowed to do. That rulebook is later used by Module 03 to check whether some LLM-written code actually follows the diagram.

It does this in four steps, and it refuses to move to the next step if a step's own quality check fails (a "gate"):

1. **Read the diagram** (`semantic_extractor.py`). It walks through every box and arrow in the BPMN file and labels them: "this is a task," "this is a decision point," "this is the start," "this is the end." Gate: it must recognize every single labeled element in the file — if it misses even one, it goes back and tries again once, and if it still can't explain every element, it stops rather than silently working with an incomplete picture.
2. **Turn the diagram into rules** (`ltlf_synthesizer.py`). For every task and decision point, it writes formal logical statements — things like "task B must not start before task A finishes" or "if the decision says 'high risk,' the fraud-check task must eventually run." These rules come in three flavors: safety rules (bad things must never happen), liveness rules (good things must eventually happen), and fairness rules. Gate: every decision point in the diagram must have a rule that covers it, or it stops.
3. **Attack its own rules** (`mutation_refiner.py`). Before trusting the rulebook it just wrote, the module deliberately creates small "broken" versions of the diagram (e.g., delete a task, swap two tasks) and checks whether its own rules notice each broken version. If a broken version manages to sneak past the rules undetected, that's a weak rule, and the module tries to patch it — up to 3 rounds of self-repair. Gate: the rules must catch every deliberately broken version it tries.
4. **Double-check by construction** (`ltlf_progression.py` / `trace_synthesizer.py` / `bidirectional_alignment.py`, "PBCTS"). The module builds actual example walk-throughs of the process that satisfy its own rules, then compares those example walk-throughs against real walk-throughs of the diagram, to see if the rules are asking for too much or too little. If there's a mismatch, it can automatically write small correction rules. This produces a final "Formal Reliability Certificate" — a report card on how much the module trusts its own output.

If all four steps pass, Module 01 hands the finished rulebook to Module 03.

## 2. Evaluation results (FLOW-BENCH corpus, re-run 2026-08-03)

FLOW-BENCH is IBM's public dataset of real business-process diagrams and LLM-generated implementations. We used **148 real diagrams** from it (100 from FLOW-BENCH's "output" set, 48 from its "context" set — see §3 for why these are reported separately, never combined).

### 2.1 Does the module read the diagram correctly? (structural fidelity)

We built a second, completely independent "gold" labeler that reads the raw BPMN XML by itself (it never looks at Module 01's own code) and compares its labeling to Module 01's.

| Corpus | Diagrams | Node-labeling accuracy | Edge-labeling accuracy |
|---|---|---|---|
| output | 100 | **100%** (1.0000) | **100%** (1.0000) |
| context | 48 | **100%** (1.0000) | **100%** (1.0000) |

**In plain English:** on every single diagram in this dataset, Module 01 labeled every box and arrow exactly the way an independent, from-scratch labeler did. We didn't just trust a perfect score at face value — we deliberately fed the module slightly broken diagrams (a deleted task, a mislabeled task) to prove the test would actually notice mistakes if there were any. It did. So this "100%" is a real, checked result, not an accident of an insensitive test — but it only proves the module handles the *kinds* of diagram elements that appear in this dataset (tasks, gateways, start/end events, sub-processes); BPMN has other element types (like parallel gateways or message events) that simply don't appear in these 148 diagrams, so this result says nothing about those.

### 2.2 Are the rules internally consistent? (suite soundness — the headline metric)

This asks a narrower but very important question: **if you take the rulebook Module 01 wrote for a diagram, does that diagram itself actually obey its own rulebook?** If it doesn't, something is clearly wrong — you can't trust a rulebook that rejects the very process it was written to describe.

| Corpus | All diagrams | Diagrams with a decision point (branching) | Diagrams with no decision point |
|---|---|---|---|
| output | 98/100 = **98.0%** | 31/31 = **100%** | 67/69 = **97.1%** |
| context | 47/48 = **97.9%** | 18/19 = **94.7%** | 29/29 = **100%** |

Out of 148 total diagrams, **145 passed this check.** The 3 that didn't (out of 148) were individually identified and diagnosed — all three fail because two different tasks in the diagram happen to share the exact same name, which confuses the rule that's supposed to keep them apart. That's a known, narrow limitation, not a mystery.

### 2.3 Does the rulebook actually catch bugs? (mutation kill rate — the honest weak spot)

This is the most important number to read carefully, and we report it exactly as measured, not rounded up. For every diagram whose rulebook passed the soundness check above (2,900 mutated diagrams total, across both corpora), we deliberately introduced a small bug (deleted a task, swapped two tasks, etc.) and asked: **did a rule actually notice the specific bug we introduced?**

**Result: 0 out of 2,900 (0.0%).**

This does **not** mean the module is useless — it means something more specific. Many of those "broken" diagrams get flagged as invalid for an unrelated reason (the bug happened to disconnect part of the diagram entirely, which a much simpler check already catches, with no actual rule involved). Once you filter those out and ask only "did an actual *rule* — not just structural breakage — catch the bug," the answer on this corpus is currently zero. This is a real, measured limitation of the current rule set, not a system failure: Module 01's rulebook is internally consistent and doesn't reject good diagrams (see 2.2), but on this specific test it hasn't yet been shown to catch the kinds of small bugs we tried against it. This is disclosed as an honest gap the project is aware of, not smoothed over.

## 3. How we evaluate this module, step by step

There's no official "correct answer key" for turning a business diagram into formal logic — nobody ships a dataset that says "here is the one true rulebook for this diagram." So instead of measuring "accuracy against a known answer," we measure three different, independently meaningful things:

1. **Structural fidelity** — did it read the diagram correctly? Checked against a second, independently-built labeler that never shares code with Module 01 (§2.1).
2. **Suite soundness** — is the rulebook self-consistent? Checked by seeing if the diagram obeys its own rules (§2.2). A rulebook that fails this test is definitely broken; passing it is necessary, but on its own doesn't prove the rules are *good* — only that they're not obviously wrong.
3. **Discriminative mutation kills** — does the rulebook actually notice small, deliberately introduced bugs (§2.3)? This is the sharpest test, and it's the one where the current result is weak.

Two more honesty rules we followed while measuring:
- **The two corpora (100 "output" diagrams, 48 "context" diagrams) are never mixed together into one combined number.** 47 of the 48 "context" diagrams are actually the *same underlying workflows* as diagrams already in "output," just rendered differently. Combining them would double-count the same evidence and make the sample look bigger than it really is.
- **Every rate is reported with a confidence interval** (a range, not just one number) using the standard exact statistical method for small samples (Clopper-Pearson). A single number like "98%" can look precise even when the sample is small; the range next to it (e.g., "[93%, 99.8%]") is the honest picture of how much that number could shift with different diagrams.

## 4. What's genuinely new about this module

Three things stand out, explained here without the academic framing (see `Module 01 Novelty.md` in the vault for the full literature comparison):

- **Self-checking rulebook writer (PBCTS).** Most systems that turn a diagram into formal rules just... trust the rules they produced. Module 01 additionally *constructs actual example walk-throughs* that satisfy its own rules and compares them against real walk-throughs of the diagram, specifically to catch cases where the rulebook is asking for too much or too little — and it can automatically write small correction rules when it finds a mismatch. We didn't find another published system that does this specific "write rules → construct evidence about the rules → self-correct" loop for auto-generated specifications.
- **A rulebook that has to survive its own attack.** Before Module 01 hands off a rulebook, it deliberately tries to break it with fake bugs and won't ship a rulebook that misses one — and if a rule is too weak, it tries to patch it automatically, up to three tries. Testing your own output this aggressively, automatically, inside the pipeline (not as a separate offline research exercise) is the novel combination here.
- **A rulebook that never silently gives up.** If Module 01 can't map every part of the diagram, or can't write a rule for every decision point, it refuses to produce a partial rulebook — it stops with an explicit error instead. That "fail loud, never fail quiet" discipline is a deliberate design choice, carried all the way through to how Module 03 later reports "excluded, and here's exactly why" instead of silently dropping properties it can't check.

**What's honestly *not* claimed:** the underlying idea of turning temporal logic into "progressed" step-by-step checks, and the basic idea of mutation-testing a specification, are both known techniques from the literature — Module 01's contribution is the specific combination and how it's wired together automatically, not inventing the underlying math. And as §2.3 shows plainly, "attacks its own rules" currently catches 0 of the specific bugs we tried on this dataset — that's a real, open weak spot, not a solved problem.

## Sources

- `module_01_spec/eval/results/m01_eval_report.md` (regenerated 2026-08-03, `python module_01_spec/eval/report.py`, seed 42, matches committed numbers exactly)
- [[Module 01 - Specification Analysis/Module 01 Knowledge|Module 01 Knowledge]]
- [[Module 01 - Specification Analysis/Module 01 Novelty|Module 01 Novelty]]
- [[Module 01 - Specification Analysis/FlowBench Evaluation Investigation/M01 FlowBench Evaluation Methodology|M01 FlowBench Evaluation Methodology]]
- Unit tests re-run 2026-08-03: `module_01_spec/tests/` 56/56 passing, `module_01_spec/eval/` 42/42 passing (98 total)

## Links

- [[Full Project Evaluation Results]] · [[Module 02 Evaluation Results]] · [[Module 03 Evaluation Results]]
- [[../Home|Home]] · [[../Project Overview|Project Overview]]
