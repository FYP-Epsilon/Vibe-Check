# SESSION MANDATE — Wiki sync: fix verified mismatches between the GitHub wiki and the repo

You are fixing specific, pre-verified mismatches in the VibeCheck GitHub wiki. The wiki is a **separate git repository**: clone `https://github.com/FYP-Epsilon/Vibe-Check.wiki.git` into a scratch directory, edit the pages, commit, and `git push` (wikis have no PR mechanism — pushes land directly, so verify each claim against the main repo source **before** writing it). The main repo is at `C:\Research\FYP\Vibe-Check` (use `develop`).

## Ground rules

- **Verify before writing**: every factual claim you add must be checked against current source the same way the mismatches below were found. Cite nothing you didn't open.
- **Preserve the wiki's voice and honesty devices**: the "⚠️ pending owner review" banners on Modules 01/03/04, the hedged phrasing, and the plain-English style are deliberate. Fix facts, don't restyle.
- Do not touch `Module-01-Specification-Analysis.md` (verified accurate and correctly hedged) except where a listed fix requires it. Keep each fix minimal.
- One wiki commit per page (or one commit total with a clear message listing pages) — message style: `wiki: <what was corrected>`.

## The verified mismatches (fix all six)

### W1 — `Home.md`: Module 03's merge status is wrong
"Modules 01 and 03 are in active development on feature branches not yet merged to `main`/`develop`" is **half wrong**: Module 03's Python pipeline (~1,900 lines: `lifter.py`, `stuttering_engine.py`, `clustering.py`, `model_checker.py`, `pipeline.py`, `nlp_utils.py`) IS merged on `develop`/`main` — only the C++/SPOT production path is in-progress. (The wiki's own Module-03 page says the source exists — Home contradicts it.) Fix the status sentence: Module 01 = on unmerged branch `feat/mod1/xml-semantic-graph`; Module 03 = Python prototype merged, C++/SPOT path in development.

### W2 — `Architecture-and-E2E-Pipeline.md` Step 3: bisimulation vs model checking conflated
The page says the cluster representative is "compared against Module 01's specification automaton using divergence-sensitive stuttering bisimulation." Per Module 03's own design (and the wiki's own Module-03 page): **bisimulation is used to cluster implementations against each other** (Phase B); the **spec-conformance verdict comes from automata-theoretic model checking** — translate negated properties to an automaton, synchronous product, emptiness check (Phase D). Rewrite that sentence to keep the two mechanisms distinct. Also adjust `Home.md`'s Module-03 diagram box if you can do it without breaking the ASCII art (acceptable to leave the box as shorthand and rely on the corrected prose).

### W3 — `Architecture-and-E2E-Pipeline.md` Step 2: the guard-literal claim is wrong for numeric guards
"randomly-generated inputs (drawing on the same guard literals the code itself compares against, e.g. actual boundary-adjacent credit scores)" — **the V1 literal pool collects string constants only** (`src/dynamic_tracer/randomized.py`, the `ast.Compare` walk collects `str` constants; ints are `random.randint(-100, 100)`). For the loan example specifically, credit scores of 600/750 are **outside** the random int range, so V1's generator never produces them — reaching numeric branches is V2's (Z3's) job, and numeric-literal pooling is a named backlog item. Fix the parenthetical: string guard literals (e.g. `"urgent"`, `"high"`) are pooled and guaranteed-drawn; numeric boundaries are explored by the symbolic layer. Then re-check the later sentence about the `<`/`<=` bug at score 600 — as written it implies V1 catches it via input generation; correct it to attribute boundary-input discovery to V2's solved inputs feeding the concolic loop, or switch the illustration to a string-guard example (verify whichever mechanism you claim against the source first).

### W4 — `Module-02-Verified-IR-Extraction.md`: stale mutant count
"429 synthetic mutants across 9 distinct mutation operators" — the count changed when early-return mutants were regenerated (99 applicable instead of 101). **Verify the current number from `module_02_extract/eval/manifest.json`** (expected: 427 mutants; 10 operators implemented, 9 with applicable sites in this corpus — `off-by-one-loop` never applies). Write the verified numbers, phrased so both facts are right (e.g. "427 synthetic mutants across 9 applicable operator classes (10 implemented)").

### W5 — `Module-04-Verification-Portal.md`: describes an app 5× smaller than reality
The page says `app.py` is 108 lines, a thin single-page client that only calls Module 02, with a **static** sidebar checkmark display. Current `module_04_ui/src/app.py` is **565 lines**: multi-page navigation (`navigate()`), **live health checks** for all three engines (`_check_extract_engine`/`_check_spec_engine`/`_check_equiv_engine`, probing each service's `/docs` with a 2s timeout), a Module-01 page POSTing to `spec-engine:8000/verify` with Semantic Graph / LTLf Property Suite / Status tabs, the Module-02 verify flow with V3/V2/V1 tabs, and a Module-03 demo tab (noting the C++ module must be compiled inside the `equiv-engine` container). Rewrite the "How it works" section **from the current source** (read all 565 lines; don't trust this summary either), update the line count, re-verify the dependency claim against `module_04_ui/requirements.txt`, and correct the "static sidebar" note to live health checks. Keep the honest note about the V1/V2/V3-vs-module-numbering overlap if it still applies.

### W6 — `Module-04-Verification-Portal.md` (and the doc it cites): example numbers use the removed formula
The illustrative figures "V3 98.0%, V2 85.0%, V1 92.0%, Combined 99.97%" come from `docs/module02/00_overview.md`, which still shows the OLD three-term formula `1-(1-v1)(1-v2)(1-v3)` (99.97 is only reachable with the v3 term that was removed for making the verdict vacuous). With the current formula those inputs give `1-(1-.85)(1-.92)` = 98.8%. Update the wiki example to current-formula numbers and note that the repo doc is being fixed separately (the docs-refresh session covers `00_overview.md` itself).

## Definition of done

- All six fixes pushed to the wiki repo; every changed claim re-verified against `develop` source during the session.
- No regressions to the pages' hedging banners, tone, or the Module-01 page.
- Reply with a per-page diff summary (one line per change) so the owner can spot-check.
