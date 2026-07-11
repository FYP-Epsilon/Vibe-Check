# Module 01 — End-to-End Implementation Plan
**Session**: Fable 5 research+planning session, 2026-07-11, branch `develop` (HEAD `febd547`). No code or wiki edits made.
**Deliverable owner**: Module 01's owner (teammate) / a future coding session. Every factual claim below was re-verified against current source this session; citations are `file:line`.

**Headline empirical result (new this session)**: the referenced FLOW-BENCH BPMN files are **PUBLIC and AVAILABLE** (`github.com/IBM/flow-bench`, Apache-2.0, `data/output/uid_N_output.bpmn`, 100 files) — and when Module 01's current pipeline is run over all 100 real diagrams, **only 3 pass end-to-end** (37 fail Phase 1, 6 crash Phase 2, 54 fail Phase 3). Additionally, the property suite is **unsound as evaluated**: the unmutated original graph is "killed" by its own properties (sequence template points the wrong way in time), and P0 sentinels are never actually evaluated (auditor can't parse `U`). Reproduction commands are in Appendix A.

---

## AGENT 1 — Implementation Verifier

### 1.1 Corrections to the prompt's current-state description

| Prompt claim | Actual state | Evidence |
|---|---|---|
| "`api.py`/`main.py` — thin FastAPI wrapper, 45/67 lines" | **Roles are swapped.** `main.py` (67 lines) is the FastAPI app with `POST /verify` running Phases 1→2→3. `api.py` (45 lines) is a non-FastAPI pipeline runner covering Phases 1–2 only — and it is **syntactically invalid Python**: `if __name__ == "__main__":` at `api.py:44` is followed only by a comment, so the file raises `IndentationError` on compile (verified with `py_compile`). It is dead code that cannot be imported. | `main.py:21-59`, `api.py:44-45`, Dockerfile:10 (`CMD uvicorn src.main:app`) |
| "No test suite exists (`module_01_spec/` has no `tests/` directory)" | `module_01_spec/tests/` **now exists but is empty** (zero files). Still no tests, no eval harness. | dir listing 2026-07-11 |
| "No BPMN corpus exists in the repo" | Confirmed — `**/*.bpmn` glob over the repo returns nothing. | Glob 2026-07-11 |
| "requirements only fastapi/uvicorn/networkx" | Confirmed. No `spot`, `ltlf2dfa`, `z3`. | `requirements.txt:1-3` |
| (not in prompt) | `src/__pycache__/` contains `agents.cpython-313.pyc` and `models.cpython-313.pyc` — bytecode remnants of deleted `agents.py`/`models.py`. Cosmetic, but indicates uncommitted churn. | dir listing |
| (not in prompt) | Full git history of the module is 6 commits (`e92ca9b`…`d0441cf`); most recent is "Update module_01_spec/src/api.py" — which is the commit that left `api.py` broken. | `git log -- module_01_spec` |

Phase descriptions in the prompt are otherwise accurate, with these precision fixes:
- **Phase 1**: V3 counts executable nodes **globally and recursively** (`.//bpmn:{type}`, `semantic_extractor.py:78-81`) but V2 maps only **direct children** of `bpmn:process` (`process.findall(f'bpmn:{node_type}')`, `:92-93`; edges likewise `:120`). Anything nested (e.g. tasks inside `subProcess`) is counted in the denominator but never mapped → coverage collapses. This single mismatch fails 37/100 real FLOW-BENCH diagrams (mean coverage 0.776, min 0.214). `unsupported_constructs` is initialized (`:34`) and **never populated** — the certificate field is always `[]`. The `run_pipeline` FAIL branch is a literal no-op `pass` (`:52-54`).
- **Phase 2**: `_resolve_implicit_guards` fires only when a gateway has **both** unconditioned flows **and** at least one explicit guard (`ltlf_synthesizer.py:82`). `_layer_v1_certify` requires *every* outgoing flow of *every* XOR gateway to carry a condition (`:177-180`) and raises `VerificationException` otherwise (`:186-190`) — so any XOR **join** (1 unconditioned outgoing flow) or any all-unconditioned XOR split hard-crashes Phase 2. Instance attr `guard_coverage` (`:28`) is dead; the cert writes `guard_resolution_coverage` (`:182`).
- **Phase 3**: `_certify` hardcodes `edge_cov = 1.0`, `path_cov = 1.0` (`mutation_refiner.py:246-247`), divides kills by a fixed `20.0` regardless of how many mutants were actually generated (`:250`), and reports `"mutants_generated": 20` unconditionally (`:258`). `random` is **unseeded** → the phase-3 certificate is nondeterministic run-to-run for the same input. `_generate_traces` swallows all errors with a bare `except: pass` (`:133-134`), ignores its `depth` parameter, and caps traces at `[:20]` (`:139`).

### 1.2 Novelty inventory verdicts (12 items)

| # | Item | Verdict | Evidence | Actual state |
|---|---|---|---|---|
| 1 | Self-Strengthening Formalization (Phase 3 mutation testing) | **PARTIALLY-IN-CODE — mechanism empirically unsound** | `mutation_refiner.py:20-268`; empirical run Appendix A | Code exists, but the kill signal is vacuous: the sequence template is backwards in time (see 1.3), so **every graph with ≥1 complete trace is "killed," including the unmutated original**; the only survivors are mutants whose traces became empty (disconnections). On the real corpus, 54/57 diagrams reaching Phase 3 FAIL its own certificate (kill ratios 0.65–0.95) despite the "refine until all killed" claim. |
| 2 | Zero Dead-Zone Protocol (implicit else) | **PARTIALLY-IN-CODE — never fires on real data** | `ltlf_synthesizer.py:75-92`; corpus profile | The negated-conjunction logic is real, but requires ≥1 explicit `conditionExpression` on a sibling flow. The entire 100-diagram FLOW-BENCH corpus contains **zero** `conditionExpression` elements (predicates live in the gateway's `name` attribute, e.g. `"Decision: object.size > 100"`), so the protocol never activates; instead certification crashes. No support for BPMN's `default` flow attribute (0 occurrences in corpus, but standard-required). |
| 3 | Coverage-Quantified Property Extraction (certificates) | **CONFIRMED-IN-CODE — several fields vacuous** | `semantic_extractor.py:141-157`, `ltlf_synthesizer.py:170-199`, `mutation_refiner.py:241-268` | Certificates exist at all three phases. But `edge_cov`/`path_cov` are hardcoded 1.0, `sentinel_coverage_fraction` is `1.0 if total_props > 0` (`ltlf_synthesizer.py:197`), and `unsupported_constructs` is always empty — several "measured" numbers are constants. |
| 4 | Sentinel Property Synthesis (P0 forbidden states) | **PARTIALLY-IN-CODE — malformed and never evaluated** | `ltlf_synthesizer.py:152-163`; `mutation_refiner.py:144-171` | P0 strings `G(!done(X) U start(X))` are emitted, but (a) `G(φ U ψ)` is a nonstandard nesting for the intended "not done until started" (should be `!done(X) U start(X)` or a weak-until), (b) the auditor's `_evaluate` handles only `G(a -> b)` and `F(a)` — anything else **falls through to `return True`** (`mutation_refiner.py:171`), so P0 sentinels are never checked, and (c) the Kripke labeling puts `start(X)` and `done(X)` in the **same trace step** (`semantic_extractor.py:102-103` + `mutation_refiner.py:140`), so the temporal separation the sentinel talks about doesn't exist in any trace. |
| 5 | Hierarchical P0/P1/P2 classification | **CONFIRMED-IN-CODE — P2 is one hardcoded string** | `ltlf_synthesizer.py:21-25, 166-168` | The three tiers exist as dict keys. P2 always contains exactly one input-independent example property (`G(iteration_count <= 10 -> F(process_complete))`). |
| 6 | NC-1 SFI | **DESIGN-ONLY-NO-CODE** | grep `SFI\|fidelity\|GED\|Jaccard` over `module_01_spec/` → 0 hits | Wiki text only (wiki L60). No monotonicity theorem written down anywhere either. |
| 7 | NC-2 CGSR | **DESIGN-ONLY-NO-CODE** | grep → 0; nearest code `_synthesize_killer` (`mutation_refiner.py:219-233`) | The killer synthesizer is one weak repair operator, not ISOLATE/WEAKEN/SYNTHESIZE; its fallback emits `G(refined_constraint_N)`, which the evaluator special-cases to **always fail** (`mutation_refiner.py:149-151`) — a literal auto-kill token (Module 01's own "V3 confidence=1.0"). |
| 8 | NC-3 PWBE | **DESIGN-ONLY-NO-CODE** | grep → 0 | Wiki L62 only. Note the per-tier verdict would belong at the M03 comparison, not in M01 alone. |
| 9 | NC-4 ΔH | **DESIGN-ONLY-NO-CODE** | grep `entropy` → 0 | Wiki L63 only. |
| 10 | Parallel-gateway super-node abstraction | **DESIGN-ONLY-NO-CODE** | `semantic_extractor.py` has no trace of it; wiki L18 even claims it's "in Phase 1" | Also: corpus contains **zero** `parallelGateway` elements — the state-explosion problem it solves does not occur in the target dataset. |
| 11 | Phase 4 dual validation (SPOT lifting, language inclusion, GED diagnostics) | **DESIGN-ONLY-NO-CODE** | `requirements.txt:1-3`; no `spot` import anywhere; `main.py:27-54` runs phases 1–3 and returns | Wiki L24-26. Module 03 (`module_03_equiv/src/lifter.cpp` + prebuilt `.so`) has its own SPOT integration — the only SPOT in the repo. |
| 12 | TCB analysis (normalizer invertibility, N-version vs `ltlf2dfa`, canonical vectors) | **DESIGN-ONLY-NO-CODE** | grep `ltlf2dfa\|normaliz\|canonical` → 0 | Wiki L35-40 only. |

The live wiki page itself carries a "⚠️ Pending module-owner review" banner (wiki L3) and a hedged status note (L42-44) — the *page* is more honest than the novelty section reads in isolation, but the NC-series and Phase-4 text is written in the present tense as if operational.

### 1.3 Independent sweep (bugs and dead code found beyond the checklist)

- **`api.py:44-45` — SyntaxError.** File cannot be imported at all (verified `py_compile`: `IndentationError: expected an indented block after 'if' statement on line 44`). Dead file; the container works only because Dockerfile runs `src.main:app`.
- **Sequence template is temporally backwards** (`ltlf_synthesizer.py:108-114`): for edge A→B it emits `G(start(B) -> F(done(A)))` where `F` is evaluated **forward** from the step where `start(B)` holds (`mutation_refiner.py:158-162`). In any linear trace, `done(A)` occurs strictly *before* `start(B)`, so the property **fails on every correct execution**. Empirically confirmed: the auditor kills the unmutated original graph of `uid_1` with counterexample `G(start(Jira_…create_Issue) -> F(Start)) failed`. The intended semantics needs a past-operator formulation (`start(B) -> O(done(A))`) or `!start(B) U done(A)`-style ordering — plus the trace-encoding fix from item 4 above.
- **`refined_constraint` auto-kill token** (`mutation_refiner.py:149-151` + `:233`): once any structurally-invisible mutant (gateway-type swap, task retype, condition inversion — none of which change the trace set) survives, the synthesized fallback killer contains the substring `refined_constraint`, which `_evaluate` hard-codes to `False` — killing *everything* thereafter, original included. Kill-ratio inflation by construction.
- **XOR-join crash**: any exclusive gateway used as a merge (1 unconditioned outgoing flow) makes `_layer_v1_certify` raise (`ltlf_synthesizer.py:177-190`). 34 XOR-joins exist in the corpus; 6/100 diagrams reach Phase 2 with one and crash (the rest die in Phase 1 first).
- **Nondeterministic verdicts**: `random` unseeded in `BPMNMutationEngine` (`mutation_refiner.py:32`) → the same BPMN input can PASS or FAIL `/verify` across runs.
- **Phase-3 denominator bug**: graphs too small for 20 distinct mutants exit the `max_attempts=1000` loop with fewer, but `killed_ratio = killed/20.0` (`:250`) → structurally guaranteed FAIL for small diagrams, mislabeled `"mutants_generated": 20` (`:258`).
- **Error-shape collapse in `main.py`**: Phase-1 failure gets a typed 422 with certificate (`main.py:32-39`), but Phase-2/3 `VerificationException` collapses to a bare string 422 (`:56-57`) and everything else to a generic 500 (`:58-59`) — same failure-masking pattern Module 02 had. Also `@app.get("/docs")` (`main.py:61`) shadows FastAPI's Swagger UI route.
- **First-start-event-only**: `initial_state` is the first `startEvent` encountered (`semantic_extractor.py:108-110`); 37/100 corpus diagrams have multiple start events (and 37 multiple ends) — the extra entry points are silently ignored by trace generation.
- **Multi-process flattening**: all `bpmn:process` elements share one `states`/`edges` list with no process boundary — collaboration diagrams would be merged into one graph silently.
- **Whitespace/None conditions**: `cond_node.text` may be `None` or whitespace; `if condition:` (`semantic_extractor.py:135`) drops empty but keeps whitespace-only text as a live guard.
- **Name-collision propositions**: atomic props are derived from the `name` attribute (`semantic_extractor.py:100-106`); two distinct tasks with the same name get identical propositions — properties can't distinguish them.

---

## AGENT 2 — Novelty → Hypothesis → Falsification Mapper

| # | Claim (wiki cite) | Falsifiable hypothesis | Testable? | Vacuousness risk | Minimum experiment |
|---|---|---|---|---|---|
| 1 | Self-strengthening mutation validation makes the property suite *sensitive* to LLM-style errors (wiki L22, L52) | **H1**: After Phase-3 refinement, the suite's detection rate on an *external* mutant corpus (not Phase 3's own mutants) is significantly higher than the pre-refinement suite's. | **Y** — but only after the soundness fixes; today the kill signal doesn't measure sensitivity at all | **CRITICAL — already realized.** Kill = "mutant kept ≥1 complete trace"; original graph is also killed; `refined_constraint` auto-kills. Direct analog of M02's V3-confidence=1.0. | Fix template/evaluator (Phase 0 below); run pre- vs post-refinement suites on the external `mutate_bpmn.py` EVAL corpus; falsified if post-refinement detection ≤ pre-refinement (95% CI overlap). |
| 2 | Zero Dead-Zone: every XOR branch gets an explicit, mutually-exclusive, exhaustive guard (wiki L20, L53) | **H2**: For every well-formed XOR split, the synthesized guard set is (a) exhaustive (disjunction ≡ true) and (b) pairwise disjoint, checkable by an SMT solver (Z3) on the guard predicates. | **Y** (per-gateway decidable check for the guard grammar in the corpus) | Medium: with ≥2 unconditioned flows, current code assigns the *same* negated conjunction to all of them — mutually-exclusive fails by construction; with 0 explicit guards it crashes instead of inferring. | Z3-check exhaustiveness+disjointness for every gateway across the 100-diagram corpus (after the dialect adapter); falsified by any gateway whose guards aren't a partition. |
| 3 | Coverage certificates let downstream modules make trust decisions (wiki L54) | **H3**: Certificate values correlate with actual extraction quality — diagrams with higher `node_coverage_Y_Struct` have higher structural micro-F1 vs independent gold (Agent 4 §2). | **Y** | Medium: several certificate fields are constants (Agent 1 item 3) — a constant can't correlate with anything. | Compute Spearman ρ between certificate fields and gold-graph micro-F1 over the corpus; falsified if ρ ≈ 0 (or the field is constant). |
| 4 | Sentinel properties create a "forbidden zone" against LLM shortcuts (wiki L55) | **H4**: Injecting order-violation defects (task executed before its prerequisite) into traces/mutants is caught by P0 sentinels at a rate > the P1-only suite. | **Y** after trace-encoding + evaluator fixes | **High — currently sentinels are never evaluated** (parser fallthrough → `True`) and start/done share a trace step. | Ablation: run external eval with and without the P0 tier; falsified if detection identical (sentinels contribute nothing). |
| 5 | P0/P1/P2 hierarchy enables severity-aware verdicts (wiki L56) | **H5**: Tier assignment is meaningful — P0 violations correspond to human-judged critical defects more often than P2 violations do. | **Weakly** — tiering is a design taxonomy; empirical content is limited | Low-medium: P2 contains exactly one hardcoded property, so the "hierarchy" is currently 2 real tiers. | Have 2 annotators severity-rate 30 sampled violations blind to tier; falsified if agreement with tier ≈ chance. Otherwise label as engineering taxonomy, not a research claim. |
| 6 | NC-1 SFI ∈ [0,1] with "formally proven monotonicity theorem" (wiki L60) | **H6**: For nested error chains e1 ⊂ e2 (e2 strictly more information loss), SFI(spec, e2-corrupted) ≤ SFI(spec, e1-corrupted). | **Y** (the theorem, however, doesn't exist on paper — demand the proof or downgrade the claim) | **High**: a weighted sum of Jaccard + normalized-GED + coverage is *not* automatically monotone (GED normalization can be non-monotone under graph growth). "Proven" is currently an unbacked word. | Build 20 nested-perturbation chains (5 steps each) over corpus diagrams; falsified if SFI increases along any chain step > noise ε. Also: write the actual proof or restate as empirical property. |
| 7 | NC-2 CGSR repairs the suite from failed traces (wiki L61) | **H7**: After CGSR repair triggered by a failing trace, (a) the failing trace passes, (b) detection on the external EVAL corpus does not drop by more than δ (repair doesn't over-WEAKEN). | **Y** | **High**: WEAKEN without an over-weakening guard is self-defeating — the loop converges to a suite that accepts everything (the M02 lesson in different clothes). (b) is the load-bearing half. | Implement; run repair on 20 seeded spec-bugs; falsified if post-repair external detection drops >5 points or any repair loop fails to terminate in k iterations. |
| 8 | NC-3 PWBE vector verdict with hard P0 veto (wiki L62) | **H8**: The P1/P2 components carry information beyond the P0 bit — i.e., among cases with no P0 violation, P1/P2 scores discriminate mutant from clean better than chance. | **Y** | **High**: if most realistic defects trip a P0 sentinel, the veto makes the vector collapse to a boolean in practice (M02's vacuous-combined-verdict pattern). Must measure the conditional distribution, not assert it. | On the external corpus: report fraction of mutants with P0 hits; among the P0-clean remainder, AUC of P1/P2 scores; falsified if AUC ≈ 0.5 or P0-clean stratum is <10% of cases (veto dominates). |
| 9 | NC-4 ΔH pinpoints *which* BPMN element lost information (wiki L63) | **H9**: For a single-element corruption at element x, argmax of per-element conditional-entropy delta = x at rate ≫ 1/\|elements\|. | **Y** | Medium: `H = log2\|L\|` needs finite, computable trace-language sizes — unbounded loops make \|L\| infinite unless bounded unrolling is fixed first; the metric may be well-defined only on the loop-free fragment. | Inject 100 known single-element corruptions; falsified if top-1 attribution accuracy is not significantly above the uniform baseline (exact binomial vs 1/n̄). |
| 10 | Super-node abstraction prevents state explosion while staying faithful (wiki L18, L66) | **H10**: For diagrams with AND-blocks, verification with super-nodes agrees with unabstracted verification (same verdicts) at ≥ some bound, with measurable state-count savings. | **Y in principle** | **High for this corpus**: zero `parallelGateway` in FLOW-BENCH — no instance where the abstraction fires; savings claim would be untestable on the target data. Also collides with H9 (localization inside a collapsed node is impossible by construction). | Requires a synthetic AND-heavy mini-corpus (10 diagrams); falsified if any verdict flips under abstraction or state savings <2×. Recommend descoping instead (Synthesis §3). |
| 11 | Phase 4 proves L(G_BPMN) = L(A_SPOT), sound + complete (wiki L24-26) | **H11**: For every corpus diagram, the language-inclusion check passes both directions; for every seeded translation bug (deliberately corrupted formula), it fails. | **Y** | Medium: "exhaustively proves" needs bounded traces (LTLf/finite); the check is only as good as the trace enumeration bound — state the bound. | Implement Phase 4; run both directions over corpus + 20 seeded translation faults; falsified if any seeded fault passes or any clean diagram fails. |
| 12 | TCB defenses drive shared-compilation-error probability "to zero" (wiki L38-40) | **H12a**: normalizer round-trip `denormalize(normalize(φ)) == φ` holds over the entire generated suite. **H12b**: SPOT-vs-ltlf2dfa disagreement detects seeded normalizer bugs. | **Y** (a is a plain assertion suite; b is a fault-injection experiment) | **High for the rhetoric**: N-version checking cannot catch a *specification-level* error (same wrong φ fed to both compilers) — "to zero" is unfalsifiable marketing; scope it to "compiler-implementation faults." | H12a: property-based test (Hypothesis) over the suite grammar. H12b: 20 seeded normalizer mutations; falsified if <90% flagged by the equivalence check. |

**Scholarly-positioning (not scientific) claims**: "first application of mutation-based sensitivity validation to BPMN property extraction" (wiki L52), "first systematic integration of negative-invariant synthesis…" (L55), "first equivalence relation to output a vector verdict" (L62), "first application of Shannon entropy to…" (L63). None are falsifiable by experiment; they are literature-positioning claims and survive only via a related-work search (note: PWBE's "first vector verdict" is at high risk — multi-valued/graded semantics for LTL and severity-tiered conformance checking both exist in the literature). Label them as positioning, cite the closest prior art, and never present them as results.

---

## AGENT 3 — Edge-Case Auditor (BPMN/LTLf)

Empirical grounding: all frequencies below are from the 100-diagram FLOW-BENCH `data/output` corpus (Appendix A). Severity: **T** = thesis-critical, **R** = robustness, **C** = cosmetic.

### 3.1 Structural BPMN edge cases

| Edge case | Corpus frequency | Current handling | Failure mode | Sev |
|---|---|---|---|---|
| `subProcess` with nested tasks | **37/100 files** (40 subProcesses, all with `multiInstanceLoopCharacteristics`) | `subProcess` not in `EXECUTABLE_NODES` (`semantic_extractor.py:19-22`); children counted by V3's recursive `.//` (`:80`) but never mapped by V2's direct-child `findall` (`:93`) | Coverage denominator inflated → **Phase 1 FAIL, 37/100 real diagrams** (mean cov 0.776, min 0.214). Failure is at least loud. | **T** |
| `inclusiveGateway` (OR) | 0 in corpus | Not in `EXECUTABLE_NODES` **and** not counted by V3 → invisible to both numerator and denominator | **Silent**: diagram PASSes Phase 1 with the gateway and its semantics entirely absent from the graph. Same for any unlisted type (`intermediateCatchEvent`, `callActivity`, `eventBasedGateway`…) | **T** (silent-pass class) |
| Multiple start events | **37/100 files** | First one wins (`semantic_extractor.py:108-110`); others become ordinary mapped states | Traces only explored from one entry → properties blind to alternative entries; no warning | **T** |
| Multiple end events | 37/100 files | Handled implicitly (any out-degree-0 node is a trace sink, `mutation_refiner.py:130`) | OK-ish; but *unreachable* end events silently produce zero traces | R |
| Lanes / pools / collaboration | 0 in corpus | All `bpmn:process` elements merged into one flat state/edge list (`semantic_extractor.py:88-90`) | Cross-pool message flows dropped; multi-participant semantics conflated silently | R |
| Boundary events (interrupting or not) | 0 in corpus | In `EXECUTABLE_NODES`, mapped as a plain state; `attachedToRef` ignored | Exception-path semantics lost; boundary event floats disconnected → island (below) | R |
| Loop markers (`multiInstanceLoopCharacteristics` / `standardLoopCharacteristics`) | **40 in corpus** (on subProcesses) | Ignored entirely | Iteration semantics invisible; P2 "quality limit" tier can never bind to a real loop | **T** |
| Sequence-flow cycles (loop via back-edge) | present in corpus (task→earlier gateway) | Graph stores them; but `nx.all_simple_paths` (`mutation_refiner.py:131`) never traverses a node twice | Loop bodies checked at most once; loop-specific mutants (operator 5) behaviorally invisible | **T** |

### 3.2 Gateway edge cases

| Edge case | Corpus frequency | Current handling | Failure mode | Sev |
|---|---|---|---|---|
| XOR-join (1 outgoing, unconditioned) | **34 gateways** | `_layer_v1_certify` demands a condition on *every* outgoing flow of *every* XOR (`ltlf_synthesizer.py:177-180`) | `VerificationException` — **any diagram with an XOR merge fails Phase 2** (6/100 crash there; rest die in Phase 1 first) | **T** |
| XOR split, all flows unconditioned | **34 gateways** | `_resolve_implicit_guards` needs ≥1 explicit guard (`:82`) → does nothing; certify raises | Same crash; and this is *the normal FLOW-BENCH encoding* (predicate in gateway `name`, e.g. `"Decision: incident.priority == 'high'"`) | **T** |
| ≥2 unconditioned flows w/ ≥1 explicit guard | 0 in corpus (possible in wild) | All unconditioned flows get the **same** negated conjunction (`:86-92`) | Two "else" branches with identical guards — mutual exclusion violated by construction, but cert PASSes (all flows now conditioned) | R |
| `default` attribute on gateway | 0 in corpus | Never read | A declared default flow is treated as implicit-else → double-handling risk on Camunda-style exports | R |
| Gateway with 1 outgoing flow + XOR mutex O(k²) | k≤4 in corpus | Mutex pairs only for ≥2 outgoing (`:124`); O(k²) properties per gateway (`:127-131`) | Non-issue at corpus scale; a 50-way gateway → 1225 props (quadratic blow-up) — bound it | C |
| Nested gateways (gateway→gateway edge) | present | Branch prop = target's first prop — for a gateway target that's its single name-prop | Mutex property talks about gateway occupancy, not task execution; weak but not crashing | R |

### 3.3 Guard/condition edge cases

| Edge case | Current handling | Failure mode | Sev |
|---|---|---|---|
| Predicate in gateway `name` (FLOW-BENCH dialect: `"Decision: x == 'y'"`, branch flows unlabeled) | Invisible — only `bpmn:conditionExpression` children of flows are read (`semantic_extractor.py:126-129`) | The entire corpus's decision logic is dropped; then Phase 2 crashes | **T** |
| Compound/parenthesized/function-call conditions | Stored as opaque text; negation is string-wrapping `!(…)` (`ltlf_synthesizer.py:84`) | OK for storage; anything downstream that parses guards (Z3 exhaustiveness check, M03) needs a defined grammar — undefined today | R |
| Double negation via mutation | `_mutate_condition_inversion` strips `!(…)` if present else wraps (`mutation_refiner.py:76-79`) | `!(a) && !(b)`-style inferred guards get mangled (strip only handles exact prefix/suffix) | C |
| Whitespace-only condition text | Kept as truthy guard (`semantic_extractor.py:135`) | Phantom guard satisfies certification while meaning nothing | R |
| Non-XML-safe chars / CDATA | ElementTree normalizes text; fine | — | C |

### 3.4 Malformed/adversarial XML

| Edge case | Current handling | Failure mode | Sev |
|---|---|---|---|
| Parses but no `bpmn:process` | V3 counts globally, so nodes outside a process still count; V2 maps nothing → coverage 0 → FAIL. If truly empty: `executable_nodes_count == 0` → coverage 0.0 → FAIL (`semantic_extractor.py:146-150`) | Loud FAIL — acceptable, but error is just a certificate wrapped in a 422 | C |
| Zero sequence flows (islands) | States mapped, no edges; Phase 2 emits only sentinels; Phase 3 traces empty → nothing killable → FAIL cert | Confusing FAIL far from the actual cause | R |
| Dangling `sourceRef`/`targetRef` | Edge stored as-is (`semantic_extractor.py:122-124` checks presence, not resolution); `_get_node_props` falls back to raw id (`ltlf_synthesizer.py:94-98`) | Properties over nonexistent propositions; never satisfiable/checkable; silent | **T** (silent class) |
| Duplicate node IDs | Both appended; `_get_node_props` returns the first match | Ambiguous properties, silent | R |
| Same `name` on distinct nodes | Distinct states, **identical atomic propositions** (`semantic_extractor.py:100-106`) | Properties can't distinguish the two tasks; silent | R |
| Very large diagrams | O(k²) mutex growth; `nx.all_simple_paths` worst-case exponential (`mutation_refiner.py:131`) with only a post-hoc `[:20]` cap | `/verify` latency blow-up on dense graphs (DoS-ish); cap applied *after* full enumeration | R |
| Phase-1 FAIL propagation | `main.py:32-39` returns typed 422 with certificate — clean. Internal FAIL branch is a no-op `pass` (`semantic_extractor.py:52-54`) but harmless since caller checks | — | C |

### 3.5 Phase 3 (mutation) edge cases

| Edge case | Current handling | Failure mode | Sev |
|---|---|---|---|
| Graph too small for 20 distinct mutants | Loop exits at `max_attempts=1000` with fewer (`mutation_refiner.py:30`) — terminates cleanly | But `killed_ratio = killed/20.0` (`:250`) → guaranteed FAIL; cert lies `"mutants_generated": 20` (`:258`) | **T** |
| Structurally-distinct but behaviorally-equivalent mutants | `!=` is dict comparison (`:34`) — e.g. task-retype (`task`→`userTask`) changes nothing observable; 9/20 mutants for uid_1 were type-changes "killed" only via the backwards template | Kill count inflated by mutants no sound checker could or should kill | **T** |
| Mutant disconnects the graph | `_generate_traces` returns `[]` → `is_killed` False forever; refinement synthesizes killers that also can't fire (no traces) | Permanent survivors → cert FAIL with misleading "refinement executed" counts (54/57 real diagrams) | **T** |
| Condition-inversion mutants | Conditions don't participate in trace generation at all (`:117-119` uses only source/target) | Behaviorally invisible → survive → trigger `refined_constraint` auto-kill fallback → all subsequent audits vacuous | **T** |
| Unseeded RNG | `random.choice` unseeded (`:32`) | Nondeterministic certificates; irreproducible thesis numbers | **T** |
| Bare `except: pass` in trace gen | `:133-134` | Any networkx error silently yields "no traces" → mutant unkillable, cause hidden | R |

### 3.6 Phase-4-and-beyond edge cases (for the planned work)

| Edge case | Risk | Sev |
|---|---|---|
| Hand-rolled LTLf strings vs SPOT grammar | Current props use `start(Task_Name)` with parens in atom names and C-style `&&`/`!`; SPOT expects `&`/`!` and plain identifiers — **every current property fails SPOT's parser** without the (unbuilt) Formula Normalizer. Round-trip test (H12a) must be the first Phase-4 artifact. | **T** |
| Unbounded loops → non-terminating automaton semantics | LTLf is finite-trace; loops need a documented unrolling bound (M03's stuttering/unroll approach exists — reuse its convention, don't invent a second one) | **T** |
| Super-node vs counterexample localization | A violation inside a collapsed AND-block yields a counterexample naming the super-node, not the branch — directly contradicts NC-4's "pinpoints exactly which element" (H9/H10 conflict) | **T** (for the *claims*; moot if descoped — corpus has 0 AND gateways) |
| `spot` install on Windows | No Windows wheel; conda-forge or Docker only. `module_01_spec/Dockerfile` (python:3.10-slim) needs an apt/conda layer; M03 already ships a compiled Linux `.so` — align on one containerized toolchain | R |
| `ltlf2dfa` dependency | Requires MONA (Linux binary) — same containerization constraint; N-version check is Docker-only | R |

---

## AGENT 4 — Evaluation Methodologist

### 4.1 FLOW-BENCH `bpmn-ref` resolution: **AVAILABLE** ✅

Checked this session, directly:
- `github.com/IBM/flow-bench` (public, **Apache-2.0** LICENSE) contains `data/output/uid_{1..101}_output.bpmn` — **exactly the `$ref` targets** of `module_02_extract/inputs/conditional_ootb.yaml`. 100 files present (**uid 90 is missing** — 100 diagrams for 101 YAML records). Plus `data/context/` with 48 more BPMN files (the `prior_context` diagrams), `data/conditional_ootb.yaml` (same file M02 vendored), `data/ootb_catalog.json`.
- Cloned and parsed: **100/100 parse** under the exact namespace Module 01 expects (`http://www.omg.org/spec/BPMN/20100524/MODEL`).
- The `.claude/memory/flowbench_groundtruth_finding.md` precedent concerned *executable-Python correctness labels* (still absent, still true for M02's E1) — it does **not** apply here: for Module 01 the BPMN diagrams *are* the input domain, and the paired `expected_output.sequence` is the independent label source.

So Module 01 gets what Module 02 never had: a **real, public, non-synthetic corpus** shared with Module 02's uid space. Caveats to state in the thesis: single vendor (IBM), single BPMN dialect (see 4.2's adapter), construct coverage skewed (no parallel/inclusive gateways, no lanes/boundary events) — supplement with a small synthetic construct-coverage set (below).

### 4.2 Corpus plan

**Primary (available) path:**
1. `module_01_spec/eval/fetch_corpus.py`: shallow-clone `github.com/IBM/flow-bench` at a **pinned commit SHA**, copy `data/output/*.bpmn` to `module_01_spec/eval/corpus/flowbench/`, record SHA + Apache-2.0 attribution in `eval/corpus/PROVENANCE.md`.
2. **Dialect adapter** `eval/adapter.py` (eval-side, so Module 01 core stays dialect-agnostic; the core fixes in Synthesis §3 Phase 0 make the core *survive* the dialect, the adapter makes it *understand* it): parse `exclusiveGateway/@name` of the form `Decision:\s*(.+)` into a predicate; attach `pred` to one outgoing flow and mark the gateway so Phase 2's Zero-Dead-Zone infers `!(pred)` for the other — exercising novelty 2 on real data. **Branch-assignment ambiguity** (which arm is "then"): in the adapter, assignment is a fixed documented convention (first `outgoing` in XML order = then-branch); the gold-label builder resolves the true assignment from the sequence IR, and the evaluation metric scores branch-swap as a distinct error category rather than silently forgiving it.
3. **Independent gold labels** — the anti-circularity core. Source: `expected_output.sequence` (IBM-authored constrained-Python IR; provenance fully external to Module 01). Build `eval/gold_from_sequence.py`: `ast.parse` the IR → gold structural skeleton: ordered task list (call names), XOR blocks (if/else with predicate text), loop blocks (for/while). This yields, per uid, a **gold graph** and a **gold property set** (task ordering pairs, branch-exclusivity pairs, branch membership) derived 100% from IBM's labels. Analogy: M02's E2 gold-WIR labeler (`module_02_extract/eval/e2_structural.py`) — same role, different parser; port the *micro-F1 bookkeeping*, not the code.
4. **Structural-accuracy experiment (M1-E2)**: Module 01 Phase 1 graph vs gold graph — micro-precision/recall/F1 over (tasks, ordering edges, XOR branch membership), reported per category. Validates extraction *without ever using Module 01's own outputs as truth*.
5. **Synthetic construct-coverage supplement** `eval/corpus/synthetic/` (~15 hand-authored diagrams, one per Agent-3 structural category the corpus lacks: parallel split/join, inclusive gateway, boundary event, lanes, default flow, multi-start, deep nesting, explicit `conditionExpression` dialect). Each with a hand-written gold annotation in a sibling `.gold.json`. For *robustness reporting*, not headline detection rates (N too small for stats — say so).

**Fallback path (if the IBM repo vanishes)**: the pinned clone vendored by `fetch_corpus.py` makes this moot after the first run; absent that, the synthetic plan scales to ~40 diagrams using the same `.gold.json` scheme. (One line because the primary path is verified available today.)

### 4.3 External BPMN mutation operators (`eval/mutate_bpmn.py`) — distinct from Phase 3

Operate on the **XML**, not on Module 01's extracted graph (so the corpus stays meaningful even if extraction is buggy). Each mutant records `{uid, operator, target_element_id}` for NC-4-style localization scoring later. Modeling realistic LLM/BPMN-authoring errors:

| Op | Description | Before → After (sketch) |
|---|---|---|
| `task_drop` | Delete a task, reconnect predecessor→successor (LLM omits a step) | `A→T→B` ⇒ `A→B` |
| `task_swap` | Swap two adjacent tasks' flow order (LLM reorders steps) | `A→B` ⇒ `B→A` |
| `branch_drop` | Remove one XOR arm and its subtree (LLM drops the else) | `XOR→{T1,T2}` ⇒ `XOR→{T1}` |
| `branch_swap` | Exchange the two arms' subtrees w.r.t. the predicate (then/else inverted) | then↔else |
| `gateway_type_swap` | `exclusiveGateway` ⇒ `parallelGateway` (choice becomes concurrency) | XOR ⇒ AND |
| `condition_negate` | Negate the decision predicate in the gateway `name` (post-adapter: on the flow condition) | `x == 'high'` ⇒ `!(x == 'high')` |
| `flow_retarget` | Redirect one sequence flow to skip its target (off-by-one wiring) | `A→T` ⇒ `A→U` |
| `task_duplicate` | Insert a duplicate task in sequence (LLM repeats a step) | `A→B` ⇒ `A→A'→B` |
| `join_drop` | Delete a merge gateway, wire branches straight to the successor | structural merge error |
| `loop_unroll_off` | On a `multiInstanceLoopCharacteristics` subProcess: remove the loop marker | iteration lost |

**Equivalent-mutant control set**: semantics-preserving edits (rename a flow id, reorder sibling XML elements, edit `bpmndi` layout, whitespace in names) — detection on these is the **false-alarm/specificity** figure, mirroring M02's three-figure split.

### 4.4 Statistical requirements (exact binomial, computed this session)

| n (EVAL mutants) | observed rate | one-sided 95% exact lower bound |
|---|---|---|
| 50 | 50/50 = 1.00 | 0.942 |
| 100 | 95/100 = 0.95 | 0.898 |
| 150 | 142/150 = 0.95 | **0.906** |
| 200 | 190/200 = 0.95 | 0.917 |
| 300 | 285/300 = 0.95 | 0.924 |

Power to *defend a pre-registered "≥90% detection" claim* when the true rate is 95%: n=100 → 0.44; n=150 → 0.66; **n=200 → 0.80**; n=300 → 0.95.

**Floor**: no "≥90%" detection claim with fewer than **150 EVAL mutants**; target **≥280** (70 EVAL diagrams × 4 mutants). A "≥95%" headline needs n≈600 at true rate ~0.98 — don't pre-register 95%; pre-register **90%** (the M02 lesson: a 21-sample "≥95%" was statistically fatal).

### 4.5 Calibration protocol and non-circular wording

- **Split by uid, not by mutant**: `CALIB = {uid : sha1(str(uid)) % 10 < 3}` (~30 diagrams), `EVAL` = the rest (~70). All mutants of a diagram inherit its split. Frozen in `eval/split.json`, committed before any EVAL run.
- **Pre-registered decision rule** (fix on CALIB only, then freeze): "a mutant is *detected* iff the frozen post-Phase-3 property suite synthesized from the **unmutated** diagram, evaluated by the (fixed) checker on the **mutant's** graph, reports ≥1 violated P0 or P1 property; the suite is regenerated per base diagram, never per mutant." Any threshold/weighting tuned on CALIB is written into `eval/OPERATING_POINT.md` with rationale *before* the EVAL run.
- **Three-figure honest report** (M02 pattern): (a) detection on real mutants, (b) specificity on equivalent mutants, (c) **false-alarm rate on the 70 unmutated EVAL diagrams** — note that today figure (c) would be ~100% (the suite kills its own original); the Phase-0 fixes are a hard prerequisite and figure (c) is the regression test proving them.
- **Thesis wording** (use verbatim): *"Phase 3's mutation-refinement loop is an internal design feature that strengthens the property suite against defects Module 01 itself can imagine; we report its statistics as descriptive engineering telemetry only. All evaluation claims derive exclusively from the external protocol: IBM-authored FLOW-BENCH diagrams, gold labels parsed from IBM's paired sequence IR, XML-level mutants generated independently of Module 01's extraction, a CALIB/EVAL split disjoint by diagram, and an operating rule frozen before evaluation."*

### 4.6 NC-series metric validation designs

- **NC-1 SFI monotonicity**: 20 EVAL diagrams × 5-step nested perturbation chains (each step adds one more `mutate_bpmn` edit to the previous mutant, so information loss strictly grows). Metric: violation rate = fraction of chain steps where SFI increases by > ε=0.01. Pre-register: claim holds iff violation rate ≤ 5% (exact binomial CI reported). Also demand the written theorem+proof; if the proof needs assumptions (e.g., GED normalizer monotone in edit count), state them or demote the claim to "empirically monotone."
- **NC-4 ΔH localization**: the 280 EVAL mutants already carry `target_element_id`. Score top-1 (and top-3) accuracy of the per-element entropy-delta attribution vs the uniform baseline 1/n̄ (n̄ ≈ mean element count). Pre-register: top-1 ≥ 50%. Define \|L\| on bounded-unrolled traces (bound = M03's unrolling convention) or restrict to loop-free diagrams and say so.
- **NC-3 PWBE non-vacuousness**: over EVAL mutants, report (i) fraction tripping ≥1 P0 sentinel (if >90%, the veto collapses the vector — report and discuss), (ii) among P0-clean cases, AUC of the (E_P1, E_P2) scores for mutant-vs-equivalent-mutant discrimination; pre-register AUC ≥ 0.7 as "carries information."
- **What to build first**: `fetch_corpus.py` → `gold_from_sequence.py` + structural-accuracy runner (works against *current* code, quantifies the Phase-0 fixes) → `mutate_bpmn.py` → calibration. NC metrics only after Phase 4 exists.

---

## AGENT 5 — Architecture Critic (committee attacks)

1. **"Your own module's wiki claims four novel metrics, a Phase 4, and a TCB defense. Show me the code."** There is none — zero matching identifiers in `module_01_spec/` (Agent 1, items 6–12). Publishing NC-1..4 as contributions with nothing runnable is indefensible. Honest scoping if the term ends early: *implemented* = Phases 1–3 (with the fixes); *designed-and-evaluation-planned* = Phase 4 + NC series with this document as the design artifact; *dropped* = super-node, N-version. The wiki must be relabeled accordingly *now*, not at write-up time.
2. **"I downloaded IBM's public dataset — your own benchmark — and 97 of 100 diagrams fail your module."** An afternoon's work for any examiner (the dataset is public and the repo names it). 37 Phase-1 failures (subProcess), 6 Phase-2 crashes (XOR joins), 54 Phase-3 certificate failures. There is no defense except fixing it before submission; this plan's Phase 0 exists for exactly that.
3. **"Your property suite rejects the correct process."** The sequence template `G(start(B) -> F(done(A)))` fails on every valid trace (Agent 1 §1.3). Any claim of "mathematically precise ground truth" collapses the moment a committee member asks you to run the suite on the diagram it was extracted from. This is a soundness bug, not a style issue.
4. **"Isn't Phase 3 just grading its own homework?"** Yes — and worse than M02's version: the `refined_constraint` token guarantees kills by string-matching (`mutation_refiner.py:149-151`). Any thesis sentence of the form "the suite kills 100% of mutants" is circular *and* mechanically rigged. Mitigation: report Phase 3 as telemetry only; all claims from Agent 4's external protocol.
5. **"Four 'first application of X to Y' claims — did you search?"** Not falsifiable, and at least NC-3's "first vector verdict for equivalence" is likely false (graded/multi-valued LTL semantics; severity-tiered conformance checking in the BPM literature). Obvious counter: one citation kills the sentence. Reframe every one as "we adapt X to Y; closest prior art is Z, from which we differ by W."
6. **"Super-node abstraction destroys the localization your ΔH metric promises."** A violation inside a collapsed AND-block cannot name the offending element (Agent 3 §3.6). And your evaluation corpus contains **zero parallel gateways**, so the abstraction never even fires — you can't demonstrate the state-explosion win on your own data. Either build a synthetic AND-corpus and accept the localization caveat, or **descope it** (recommended).
7. **"Your TCB argument is circular at the top and leaky at the bottom."** "SPOT is trusted because peer-reviewed" is an appeal to authority (fine as engineering posture, not as proof); and N-version checking with `ltlf2dfa` only catches *compiler* divergence — if Module 01 synthesizes the wrong formula, both compilers faithfully agree on the wrong automaton. Scope the claim to implementation faults; the *specification-level* defense is Agent 4's external gold-label evaluation, nothing else.
8. **"If Phase 4 slips, what does Module 03 consume?"** Today: nothing — `module_03_equiv/src/{pipeline,main}.py` reference no Module 01 output at all; `model_checker.check_all_properties` takes `(name, monitor_LTS)` tuples built inside M03 (`model_checker.py:154-171`), and M03 has its own SPOT lifter (`lifter.cpp`, prebuilt `.so`). So the blast radius of a Phase-4 slip is **zero code breakage but total integration absence**: the "final judge" currently judges against hand-built monitors, not the BPMN. The fallback is real and should be documented: M01 ships the (fixed) LTLf property strings + a defined syntax contract; M03's existing lifter builds the monitors. Phase 4 then becomes an *internal QA layer* for M01, not the M03 interface — which also shrinks its criticality honestly.
9. **"Same diagram, different verdict on Tuesday."** Unseeded RNG in Phase 3 makes `/verify` nondeterministic. Every number in the thesis must be reproducible: seed it, and version the certificate schema.
10. **Committee-attack forms of the worst edge cases**: (a) "Add an OR-gateway to your loan example — your module passes it with the gateway silently deleted; where's the 'Zero Dead-Zone' now?" (silent-drop class, Agent 3 §3.1); (b) "Your BPMN has two tasks both named 'Send Email' — your propositions can't tell them apart; which one does the sentinel protect?"; (c) "This diagram has an XOR merge — the most common BPMN pattern after sequence — and your Phase 2 throws an exception."

---

## SYNTHESIS — E2E Implementation Plan

### 1. Verified Current-State Scorecard

Agent 1 §1.2 stands as the scorecard. Compressed: **items 1–5** (original novelties): in code but with load-bearing defects — 1 (kill signal vacuous), 2 (never fires on real data + join crash), 3 (constant fields), 4 (malformed + never evaluated), 5 (P2 hardcoded). **Items 6–12**: no code whatsoever. Plus sweep findings: `api.py` SyntaxError; backwards sequence template; `refined_constraint` auto-kill; unseeded RNG; `/20.0` denominator; error-shape collapse; first-start-only; silent unsupported-construct drops. Empirical bottom line: **3/100 real diagrams pass end-to-end**.

### 2. Novelty & Hypothesis Register

Agent 2's 12-row table stands. Load-bearing flags: H1 vacuousness already realized (fix before any claim); H6 "proven monotonicity" currently an unbacked adjective; H8 P0-veto vacuousness must be measured, not assumed; H10 untestable on the target corpus (descope); H12's "to zero" unfalsifiable (rescope to compiler faults); four "first-X" claims are positioning, not science.

### 3. Phase-Ordered Implementation Plan

**Phase 0 — Soundness of Phases 1–3 (prerequisite for every claim; do first).**
Files: `semantic_extractor.py`, `ltlf_synthesizer.py`, `mutation_refiner.py`, `main.py`, `api.py`. No new deps.
- **0.1** Delete or complete `api.py` (an unimportable duplicate of `main.py` minus Phase 3; recommend delete + note in PR). Effort S.
- **0.2** Trace-encoding fix: emit `start(X)` and `done(X)` as **separate consecutive trace steps** per task in `_generate_traces`; then fix the sequence template to a finite-trace-correct ordering form — `!start(B) U done(A)` per edge A→B (or a past-operator formulation), and fix P0 sentinels to top-level `!done(X) U start(X)` (weak-until if X may never run). Acceptance: the unmutated graph of every corpus diagram satisfies its own suite (false-alarm figure ≈ 0). Effort **M** (the heart of the module).
- **0.3** Evaluator honesty: implement `U`/`W` and `<->` in `_evaluate` (better: factor a small recursive-descent LTLf evaluator into new `src/ltlf_eval.py`); **delete the `refined_constraint` special case**; killer synthesis must emit only checkable formulas or explicitly report "no killer found." Effort M.
- **0.4** Extraction coverage: recursive per-process `findall('.//…')` in V2; add `subProcess`, `inclusiveGateway`, `intermediateCatchEvent`/`ThrowEvent`, `callActivity`, `eventBasedGateway` to `EXECUTABLE_NODES` (map + flatten subProcess children with a `parent` field; read `multiInstanceLoopCharacteristics` into a `loop: true` flag); populate `unsupported_constructs` for anything matched by `.//bpmn:*` but unmapped, surfaced in the certificate. Acceptance: 0/100 corpus diagrams fail Phase 1 on coverage; unknown constructs FAIL loudly or certify with a named warning — never silent. Effort M.
- **0.5** Gateway semantics: exempt single-outgoing XORs (joins) from guard certification; support `default`; multiple unconditioned flows = certification FAIL with a named reason (not same-guard duplication); multi-start events → synthetic super-start or per-start trace roots. Acceptance: 0 Phase-2 crashes on corpus. Effort S–M.
- **0.6** Phase-3 hygiene: seed RNG (accept `seed` through `/verify`), `killed_ratio` over *actual* mutant count, report actual `mutants_generated`, replace bare `except`, cap `all_simple_paths` with `cutoff` + node-count guard. Effort S.
- **0.7** Typed per-phase errors in `main.py` (`{phase, error_code, certificate}` — mirror M02's typed `/verify` layers, PR #35 precedent); un-shadow `/docs`. Effort S.

**Phase A — Evaluation harness (parallelizable with Phase 0 after 0.2; new dir `module_01_spec/eval/`).**
- **A.1** `eval/fetch_corpus.py` + `eval/corpus/PROVENANCE.md` (pinned SHA, Apache-2.0 notice). Effort S.
- **A.2** `eval/adapter.py` — FLOW-BENCH dialect (gateway-name predicates → flow conditions + else-inference marking). Acceptance: ≥95/100 diagrams pass Phases 1–2 post-adapter. Effort S–M.
- **A.3** `eval/gold_from_sequence.py` + structural micro-F1 runner (M1-E2). Acceptance: metric runs on all 100; report committed as `eval/reports/m1_e2_structural.md`. Effort M.
- **A.4** `eval/mutate_bpmn.py` — 10 operators + equivalent-mutant set, `eval/split.json` (uid-hash 30/70), `eval/OPERATING_POINT.md`. Acceptance: ≥280 EVAL mutants; three-figure report (detection / equivalent-specificity / base false-alarm). Effort M.

**Phase B — Phase 4 automata lifting (`src/automata_lifter.py`).**
Deps: `spot` (conda-forge or Docker layer — no Windows pip; update `Dockerfile`; align with M03's existing SPOT toolchain), plus `src/formula_normalizer.py` **first** (M01 LTLf strings → SPOT grammar: `&&`→`&`, `start(X)`→`start_X` mangling, plus `denormalize`). Order within B: normalizer + round-trip test → LTLf→automaton per property → monitor export → language-inclusion check vs the semantic graph (bounded unrolling = M03's convention). Agent-3 §3.6 cases it must handle before "done": parser-reject fallback (typed error, not 500), documented loop bound, per-property compile-time budget. Acceptance: 100/100 corpus suites compile; 20 seeded translation faults all caught (H11); round-trip holds across all generated suites (H12a). Effort **L**.

**Phase C — NC series (each gated on Phase B; "implemented" = code + validated hypothesis):**
- **C.1** NC-1 `src/fidelity_index.py` (+ the monotonicity statement written down with assumptions). Acceptance: H6 ≤5% violations. Effort M.
- **C.2** NC-4 `src/entropy_delta.py` (bounded-\|L\| definition). Acceptance: H9 top-1 ≥ pre-registered 50%. Effort M–L.
- **C.3** NC-3 PWBE — belongs at the M01→M03 boundary: per-tier verdict vector in the comparison layer (coordinate with M03's owner; M01's deliverable is the per-tier grouping already present). Acceptance: H8 measured (veto prevalence + conditional AUC), reported *whatever the result*. Effort M.
- **C.4** NC-2 `src/spec_refiner.py` (ISOLATE/WEAKEN/SYNTHESIZE with an over-weakening guard: external-detection regression ≤5 points, H7b). Effort L. **Lowest priority — cut first if the term runs out.**

**Phase D — TCB defenses (independent of C; gate-able):**
- **D.1** Normalizer invertibility property-test (`tests/test_normalizer_roundtrip.py`, Hypothesis-based). Effort S (once B exists).
- **D.2** N-version vs `ltlf2dfa` (Docker-only; MONA dep). Scope claim to compiler-implementation faults. Effort M. **Optional.**
- **D.3** Canonical vectors `tests/canonical/` — 10 diagrams from bpmn2constraints-style literature + expected automata. Effort M. **Optional; FLOW-BENCH already provides stronger external grounding.**

**Descoped (recommend, with wiki relabeling): super-node abstraction** — zero parallel gateways in the target corpus (benefit undemonstrable), direct conflict with NC-4 localization, and Phase B's per-property monitors don't hit the product-state explosion the wiki worries about. Keep as future-work text, not a claim. **Tests throughout**: `tests/` is empty; every Phase-0 fix lands with a pytest regression (fixtures = Appendix A's corpus-run numbers).

### 4. BPMN/LTLf Edge-Case Risk Register (top 10)

| # | Risk | Fix | Effort |
|---|---|---|---|
| 1 | Sequence template backwards → suite rejects correct process (FA ≈ 100%) | Phase 0.2 | M |
| 2 | `refined_constraint` auto-kill → rigged kill ratio | Phase 0.3 | S |
| 3 | subProcess coverage mismatch → 37/100 Phase-1 FAIL | Phase 0.4 | M |
| 4 | XOR-join / unconditioned-XOR crash → Phase 2 unusable on standard BPMN | Phase 0.5 | S |
| 5 | Silent drop of unlisted node types (inclusiveGateway etc.) → PASS certificate on unfaithful graph | Phase 0.4 (`unsupported_constructs`) | S |
| 6 | P0 sentinels never evaluated + start/done same-step encoding | Phase 0.2/0.3 | M |
| 7 | Unseeded RNG → irreproducible certificates | Phase 0.6 | S |
| 8 | FLOW-BENCH dialect (gateway-name predicates) invisible → Zero-Dead-Zone never exercised | Phase A.2 adapter | S–M |
| 9 | `killed/20.0` denominator → small diagrams can never pass | Phase 0.6 | S |
| 10 | Hand-rolled LTLf vs SPOT grammar mismatch → Phase 4 dead on arrival | Phase B normalizer-first | M |

### 5. Executable Evaluation Plan

Agent 4 in full; reconciled build order: **(1)** `fetch_corpus.py` (availability resolved — AVAILABLE, Apache-2.0, pin the SHA), **(2)** `gold_from_sequence.py` + structural micro-F1 (runs against current code immediately and becomes the before/after instrument for every Phase-0 fix — M02's "experiment as instrument" pattern), **(3)** `adapter.py`, **(4)** `mutate_bpmn.py` + split + pre-registered rule (frozen before EVAL), **(5)** three-figure report. Statistical floor: no "≥90%" claim under 150 EVAL mutants; target 280; pre-register 90%, not 95%. Phase-3 numbers are telemetry, never evidence (§4.5 wording verbatim in the thesis).

### 6. Top Thesis Vulnerabilities (ranked)

| # | Vulnerability | Mitigation | Risk if unaddressed |
|---|---|---|---|
| 1 | 97/100 public-corpus failure — examiner-reproducible in an afternoon | Phase 0 + A; re-run Appendix A as the headline before/after table | Fatal credibility loss on the module's core claim |
| 2 | Suite kills its own correct process (soundness) | Phase 0.2/0.3; FA-figure regression test | "Formally grounded" collapses under one live demo |
| 3 | Wiki claims (NC-1..4, Phase 4, TCB) with zero code | Relabel wiki now (implemented / designed / future); this doc as the design artifact | Misrepresentation finding — the worst outcome available |
| 4 | Circular + rigged self-validation narrative | §4.5 wording; external protocol only; disclose `refined_constraint` in the correction trail (M02's "correction trail as methodology" narrative worked — reuse it) | Examiner rejects all quantitative claims |
| 5 | Unfalsifiable "first-X" claims (×4) | Reframe as adaptation + closest-prior-art citations | Cheap committee kill; collateral damage to real contributions |
| 6 | "≥95%"-style overclaim on small N | Pre-register 90% @ n≥280 (power 0.80–0.95) | Statistically indefensible headline (M02 precedent) |
| 7 | Super-node vs ΔH self-contradiction | Descope super-node | Two claimed novelties refute each other in the viva |
| 8 | M01→M03 integration undefined (no code touchpoint today) | Property-suite contract doc (M02's `12_` contract-doc pattern); Phase 4 as QA layer, M03's lifter as consumer | "Final judge judges nothing from the diagram" |
| 9 | Nondeterministic verdicts | Seed + version certificates | Irreproducible thesis numbers |
| 10 | Single-vendor, construct-skewed corpus | Disclose skew; synthetic supplement for construct coverage | External-validity attack |

### 7. Next Implementation Session Plan (ordered, one sitting each)

1. **T1** — Fix `api.py` (delete, or complete and test); seed Phase-3 RNG + actual-count denominator + actual `mutants_generated` + replace bare `except` (`mutation_refiner.py:30-37,133-134,246-258`); typed per-phase errors + `/docs` un-shadow (`main.py:56-64`). Create `tests/test_phase3_determinism.py`. *(Phase 0.1/0.6/0.7 — the mechanical batch.)*
2. **T2** — `eval/fetch_corpus.py` + `PROVENANCE.md` + `eval/run_corpus.py` reproducing Appendix A's 100-diagram sweep as a committed baseline report (`eval/reports/baseline_pre_fix.md`). Locks the before-numbers.
3. **T3** — Trace-encoding + template + evaluator fixes (Phase 0.2/0.3: `ltlf_synthesizer.py:100-168`, new `src/ltlf_eval.py`, `mutation_refiner.py:101-177` incl. deleting `:149-151`). Acceptance: base false-alarm 0 on all corpus diagrams passing Phase 1. `tests/test_ltlf_eval.py` with hand-built truth tables.
4. **T4** — Extraction coverage + gateway semantics (Phase 0.4/0.5: `semantic_extractor.py:19-22,83-139`; `ltlf_synthesizer.py:75-92,170-199`). Acceptance: 0 Phase-1 coverage FAILs, 0 Phase-2 crashes on corpus; `unsupported_constructs` live.
5. **T5** — `eval/adapter.py` + `eval/gold_from_sequence.py` + structural micro-F1 report (Phase A.2/A.3), then re-run T2's sweep → `eval/reports/baseline_post_fix.md` (the thesis before/after table).
6. **T6** — `eval/mutate_bpmn.py` + split + `OPERATING_POINT.md` + three-figure calibration report (Phase A.4).
7. **T7** — Phase B start: `src/formula_normalizer.py` + round-trip test + Dockerfile SPOT layer (coordinate with M03's SPOT toolchain).

---

## NEXT SESSION

1. Hand this plan to Module 01's owner (M01 is their code — per the project boundary, confirm whether these fixes are done for them or by them) and relabel the wiki page's NC/Phase-4/TCB sections as **designed-not-built**, referencing this doc (`.claude/module01_e2e_plan.md`).
2. Start T1: `module_01_spec/src/api.py` (delete/complete), `mutation_refiner.py:30-37,133-134,246-258` (seed/denominator/except), `main.py:56-64` (typed errors) + first pytest files in the empty `module_01_spec/tests/`.
3. T2: create `module_01_spec/eval/fetch_corpus.py` pinning `github.com/IBM/flow-bench` (`data/output/*.bpmn`, Apache-2.0 notice, record SHA) and commit the pre-fix baseline sweep report.
4. T3: the soundness core — `ltlf_synthesizer.py:100-168` template rewrite + new `src/ltlf_eval.py` + delete `mutation_refiner.py:149-151`; acceptance = zero base false alarms.
5. T5-prep: draft the M01→M03 property-suite contract doc (LTLf string grammar, certificate schema, tier semantics) with M03's owner — `docs/` `12_`-style, since M03 currently consumes nothing from M01 (`module_03_equiv/src/model_checker.py:154-171` builds its own monitors).

---

## Appendix A — Reproduction of the empirical claims (all run 2026-07-11, seed 42)

```
corpus: git clone https://github.com/IBM/flow-bench  →  data/output/*.bpmn (100 files; uid 90 absent)
parse:  100/100 parse; namespace == http://www.omg.org/spec/BPMN/20100524/MODEL
profile: conditionExpression 0; parallelGateway 0; inclusiveGateway 0; boundaryEvent 0; lanes 0;
         default attr 0; exclusiveGateway 68 (31 files); XOR splits all-unconditioned 34; XOR joins 34;
         subProcess 40 (37 files, all with multiInstanceLoopCharacteristics); multi-start files 37; multi-end 37
pipeline (sys.path += module_01_spec/src; random.seed(42)):
         Phase1 FAIL 37/100 (coverage mean 0.776, min 0.214)
         Phase2 VerificationException 6/100 (uid 2,3,11,12,31,88)
         Phase3: of 57 reaching it → PASS 3, FAIL 54; kill ratio min 0.65 / mean 0.88; killers synthesized in 54
uid_1 diagnostic: 20 mutants → 9 type-change "killed" (via backwards template), 7 edge-del killed,
         4 edge-del unkillable (empty traces); ORIGINAL graph killed by own suite:
         "Property G(start(Jira_Issue__2_0_0__create_Issue) -> F(Start)) failed"
         sample P0 sentinel G(!done(X) U start(X)) evaluates → True (parser fallthrough, mutation_refiner.py:171)
binomial: one-sided exact 95% LBs and power table as in §4.4 (pure-python Clopper-Pearson, no scipy)
```
