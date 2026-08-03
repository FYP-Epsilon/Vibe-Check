> [!info] What this page is
> A plain-English report on Module 03 — what it does, how we actually verify it works (there is **no standalone FLOW-BENCH benchmark for this module alone**, and this page says so honestly rather than inventing one — see §3 for why, and what we use instead), and what's genuinely new about it. Unit test numbers below were freshly re-run on 2026-08-03 against `main-demo`.

## 1. What Module 03 actually does

Module 03 is the **"referee."** It takes the rulebook Module 01 wrote from the business diagram, and the code map Module 02 extracted from the LLM-generated code, and decides: **does this code actually follow the rulebook?** Its answer is always one of three things — `COMPLIANT` (yes, it follows the rules), `VIOLATION` (no, and here's a concrete example of exactly how it breaks the rule), or `INCONCLUSIVE` (the evidence isn't good enough to say either way — it refuses to guess).

It reaches that answer in four steps:

1. **Turn the code map into a mathematical machine (Phase A — the Lifter).** The code's structure (from Module 02) is converted into a formal object called an automaton — think of it as a precise, walkable state-machine version of "what this code does, step by step." Task names in the code are matched up to task names in the diagram using a cascade of matching methods — exact name match first, then a fuzzy text-similarity match, then an AI-based meaning-similarity match as a last resort — so small naming differences don't cause a false mismatch.
2. **Simplify it, carefully (Phase B — Bisimulation).** Long, repetitive machines are compressed down to their essential behavior, the same way you'd summarize a long story without changing its meaning. The one thing this simplification is specifically careful *not* to do: if the code has a silent infinite loop (a classic LLM mistake — imagine code that just spins forever and never finishes), the simplification refuses to treat that the same as a normal, harmless wait. Getting this wrong would let broken, frozen code look identical to correctly-waiting code.
3. **Group similar implementations together (Phase C — Clustering).** If you're checking many different LLM-written versions of the same workflow, many of them will behave identically underneath, even if the code text looks different. Module 03 groups these together mathematically and only fully checks one representative from each group — so checking 20 different code samples might only cost as much work as checking 2 or 3 truly distinct behaviors.
4. **Formally check the rules (Phase D — Model Checking).** This is where the actual comparison against the rulebook happens: it mathematically proves either that no rule is broken, or produces a concrete counterexample — an actual step-by-step trace showing exactly where the code deviates from what the rulebook requires. If a rule mentions a task that never appears in this particular code at all, Module 03 does not guess — it reports `INCONCLUSIVE` rather than fabricating a verdict either way.

## 2. Evaluation results

### 2.1 Why there's no single "FLOW-BENCH accuracy number" for this module alone

Modules 01 and 02 each have their own dedicated FLOW-BENCH mutation-testing benchmark (see their evaluation pages) — take real workflows, plant known bugs, measure the catch rate. **Module 03 does not have an equivalent standalone benchmark, and this page states that plainly rather than manufacturing one.** The reason is structural, not an oversight: Module 03 is the *meeting point* of the other two modules — it doesn't have its own independent "input" to test in isolation the way Module 01 has raw diagrams and Module 02 has raw code. Its correctness only really means something once it's actually fed a real rulebook and a real code map together. So instead of one benchmark number, we verify Module 03 with three different, complementary kinds of evidence:

### 2.2 Evidence layer 1 — does its internal logic work correctly? (unit tests)

Re-run 2026-08-03: **142 passed, 2 failed, 1 skipped** (145 test functions total).

The 2 failures are a known, pre-existing, and narrow gap: two tests check a specific "deterministic hashing" feature that was planned but never actually implemented in the underlying engine — it's an unrelated bookkeeping feature, not a correctness bug in the actual rule-checking logic described in §1. This gap is already documented in the project's own internal notes; we didn't discover it as a surprise, and we didn't hide it either.

### 2.3 Evidence layer 2 — does it agree with an independent, separately-written checker? (oracle agreement)

We ran Module 03's real compiled engine against **29 real FLOW-BENCH specifications**, producing **58 individual rule checks**, and compared every single verdict against a *second, independently written* rule-checker (Module 01's own internal reference checker, which shares no code with Module 03's engine).

| Result | Count |
|---|---|
| Checks where both checkers agreed | **35 / 35 = 100%** of all checks where either checker gave a real answer |
| Checks correctly refused (`INCONCLUSIVE`) by both | 23 |
| Checks where the two checkers disagreed | 0 |

**In plain English:** on every single check where a real yes/no answer was possible, Module 03's fast, compiled engine gave the exact same answer as a slower, independently-written reference implementation. The 23 "can't tell" cases weren't disagreements — they were correctly-shared refusals, because the rule in question mentioned a task that genuinely never occurred in that specific piece of code.

**What this number does and doesn't prove:** it's strong evidence that the engine's internal machinery (the automaton-building, the simplification, the formal checking) is implemented correctly and agrees with an independent reference. It is **not** the same as "Module 03 catches 100% of real bugs" — that's a different, harder question, answered separately in the Full Project report, because it requires actually feeding the module broken code and seeing if it notices.

**One important scoping caveat, stated plainly rather than rounded up:** this specific 35/35 run used an earlier way of reading the code's task order (task names in the order they're *defined* in the source file, not the order they actually *execute* in). That earlier mode was later found to disagree with real execution order in a large share of real generated code (see Module 02's report, §4) and has since been replaced everywhere else in the pipeline by an "execution order" reading. So this 100% figure is solid proof that Module 03's checking logic itself is correct and matches an independent reference — but it was measured on that earlier reading, not on the execution-order reading the rest of the pipeline (including the Full Project results) uses today. It should be read as "the engine's core logic is correct," not as "this exact number describes today's full pipeline."

### 2.4 Evidence layer 3 — how does it perform in the real, full pipeline?

Because Module 03's real job only makes sense in context — checking real rules against real code — its actual bug-catching behavior is measured as part of the full end-to-end pipeline, not on its own. See **"Full Project Evaluation Results"** in this same folder for those numbers (abstention rate, detection rate, false-alarm rate) — they are, in effect, Module 03's real-world performance report, just measured together with Modules 01 and 02 rather than in isolation.

## 3. How we evaluate this module, step by step

1. **Unit-test its internal logic in isolation** (§2.2) — do the individual pieces (the lifter, the simplifier, the clustering, the model-checker) behave correctly on carefully constructed small examples?
2. **Cross-check its real output against an independent reference implementation** (§2.3) — feed it 29 real specifications from the FLOW-BENCH dataset and compare every verdict against a second checker that was built completely separately, to catch any disagreement that unit tests on small examples might miss.
3. **Measure its real bug-catching behavior only as part of the full pipeline** (§2.4, detailed in the Full Project report) — because Module 03 alone has no "input" of its own, its practical value is measured by actually running real business diagrams and real (sometimes deliberately broken) LLM code all the way through, and checking whether Module 03's final verdict is correct.

We're explicit that this is a different *shape* of evidence than Modules 01 and 02 have, not a lesser one — it reflects what Module 03 actually is: the convergence point, not an independent stage.

## 4. What's genuinely new about this module

- **Choosing a stricter form of "sameness" specifically because of how LLMs fail.** When simplifying the code's behavior, Module 03 deliberately refuses to treat "silently stuck forever in a loop" the same as "normally waiting" — a distinction that matters enormously for LLM-generated code, because "spin forever and never finish" is a real, common failure pattern for generated code, and a checker that missed this distinction could wrongly certify frozen, broken code as fine. The underlying mathematical technique for this ("divergence-sensitive" equivalence) is well-established in computer science theory; applying it specifically because of this LLM failure pattern, inside a code-checking pipeline, is the new part.
- **Grouping implementations by actual behavior to save work, not by superficial similarity.** Instead of checking every single LLM-generated code sample completely from scratch, Module 03 mathematically proves which samples behave identically and only fully checks one representative per group — so if a violation is found in one, it applies to every code sample grouped with it too.
- **Finding and fixing three subtle, real bugs at a genuinely hard technical boundary.** Business-process rules are naturally written in a style that talks about finite, ending processes ("eventually X happens"). The underlying mathematical checking engine, however, is naturally built for infinite, ongoing processes. Bridging these two was where the hardest, least-textbook work in this module happened — and in doing so, the team found and fixed three real bugs: (1) a bug where every single rule check would have silently and always said "compliant" no matter what, for any code that eventually finishes; (2) a bug where the checker could invent a violation using a fact the code never actually asserted one way or the other; (3) making sure that when a rule mentions something the code never does at all, the answer is an honest "can't tell," never a made-up verdict. All three were found through direct, hands-on investigation (not assumed), fixed, and then verified against the independent reference checker described in §2.3.
- **Refusing to guess when the evidence doesn't support an answer.** `INCONCLUSIVE` isn't a bug or a cop-out — it's a deliberate, built-in third answer, used specifically so the module never has to choose between "silently guess" and "silently break."

**What's honestly *not* claimed:** the core mathematical machinery Module 03 uses (the model-checking algorithm, the simplification algorithm) is standard, well-published computer science — not new research. The novelty is entirely in *how* and *why* it's applied to this specific problem (checking LLM-written code against business rules), and in the real bugs found and fixed while making that application actually work correctly. Also, as §2.1 makes clear, this module still doesn't have its own standalone bug-detection benchmark the way Modules 01 and 02 do — the closest thing to that number lives in the Full Project report.

## Sources

- `module_03_equiv/tests/` — unit tests re-run 2026-08-03 (via the project's Python 3.9 environment, since the compiled checking engine only loads under Python 3.9): 142 passed, 2 failed (known, documented gap), 1 skipped
- `module_03_equiv/src/lifter.cpp` — confirmed directly: the "Deterministic Hashing" section referenced by the 2 failing tests is an empty placeholder, never implemented
- [[Module 03 - Equivalence Engine/Module 03 Knowledge|Module 03 Knowledge]] (source of the 29-spec / 58-check / 100% oracle-agreement figures, and the definition-order lifting caveat on that figure)
- [[Module 03 - Equivalence Engine/Module 03 Novelty|Module 03 Novelty]]
- [[Module 03 - Equivalence Engine/Bridge Investigation/E2E Integration Verification Findings|Bridge Investigation findings]] (the three-bug investigation this page's novelty section summarizes)

## Links

- [[Full Project Evaluation Results]] · [[Module 01 Evaluation Results]] · [[Module 02 Evaluation Results]]
- [[../Home|Home]] · [[../Project Overview|Project Overview]]
