# Fable 5 — Module 01: End-to-End Implementation Plan (Novelties, Edge Cases, Hypotheses, FLOW-BENCH-Style Evaluation)
# Copy-paste this entire prompt into a new Fable 5 session with file access to this repo.
# Do NOT summarize or abbreviate it before starting — the full context is required.

---

## SESSION MANDATE

You are producing a **research and planning session only** — the deliverable is a single, implementation-ready **end-to-end plan** for Module 01 of a formal-verification research system, precise enough that a coding session could start from it with no further research. **No code will be written. No files will be edited.**

Module 01 belongs to a teammate, not the operator running this prompt — this session is meant to hand that teammate (or a future coding session) a rigorous plan, not to touch their code. Treat everything below as ground truth as of this session; verify anything you rely on against current source before asserting it.

**Critical ground rule, learned the hard way on this project's other module (Module 02) and already reproduced once on Module 01 itself**: the project's GitHub wiki page for Module 01 (`Module-01-Specification-Analysis.md`) was recently expanded with a large set of new claims — a Phase 4 (automata lifting via SPOT), four new named metrics (the "NC series"), a Trusted-Computing-Base defense analysis, N-version cross-validation, canonical test vectors, and a "parallel gateway super-node abstraction." **A source-code check performed before writing this prompt found zero implementation of any of it**: `module_01_spec/src/` contains exactly four files (`semantic_extractor.py` — Phase 1, 201 lines; `ltlf_synthesizer.py` — Phase 2, 244 lines; `mutation_refiner.py` — Phase 3, 304 lines; `api.py`/`main.py` — thin FastAPI wrapper, 45/67 lines), `requirements.txt` lists only `fastapi`, `uvicorn`, `networkx` (no `spot`, no `ltlf2dfa`, no `z3`), and a full-repo grep for `SFI|CGSR|PWBE|entropy|GED|isomorph|ltlf2dfa|super-?node|fidelity|N-Version|canonical test vector` returns nothing in `module_01_spec/`. **Do not trust any wiki claim — including implicit claims that something already exists — without re-verifying against current source first.** Cite file path + line range for every factual claim about the code.

You will operate as **five concurrent sub-agents**, each with a distinct mandate, followed by a **Synthesis Agent** that assembles the actual E2E plan. Read the full brief below before beginning any analysis.

---

## PROJECT BRIEF

**System**: VibeCheck — Post-Hoc Formal Verification of LLM-Generated Python Code Using BPMN-Derived Temporal Specifications
**University**: Faculty of IT, University of Moratuwa — FYP, Group 18 (Epsilon)
**Module in scope**: Module 01 — Specification Analysis / Formal Extraction (owned by a teammate; read/plan only, no edits)
**Repo**: `C:\Research\FYP\Vibe-Check`, branch `develop`. Module 01 source lives at `module_01_spec/src/{semantic_extractor.py, ltlf_synthesizer.py, mutation_refiner.py, api.py, main.py}`.
**Wiki**: separate git repo, `https://github.com/FYP-Epsilon/Vibe-Check.wiki.git` — page `Module-01-Specification-Analysis.md` is the source of the novelty claims below (fetch it directly; do not rely on secondhand paraphrase, including the paraphrase in this prompt).

### Pipeline Architecture (Dual-Track, 5-Stage)

```
Track A (Spec):   BPMN 2.0 XML ──► Module 01 ──► M_spec + LTLf Props ──────────┐
                                    (Stage S1)                                    ▼
                                                                            Module 03 ──► Verdict
                                                                            (Stage S5)    ▲
Track B (Code):   LLM Python Code ──► Module 02 ──► WIR + M_code ───────────────┘
                                       (Stages S3-S4)
```

### Module 01 — Verified Current Implementation (re-verify, don't just restate)

Four phases claimed; three exist in code as of this session:

1. **Phase 1 — Semantic Extraction** (`semantic_extractor.py`, class `SemanticExtractionEngine`). V3→V2→V1 sub-pipeline: `_layer_v3_sanitize` strips `bpmndi:BPMNDiagram` nodes and counts executable node types (`EXECUTABLE_NODES` constant); `_layer_v2_construct_and_label` walks `bpmn:process` children, assigns Kripke atomic propositions (`start(X)`/`done(X)` for tasks, single prop otherwise), and maps `sequenceFlow` edges (with `conditionExpression` text if present); `_layer_v1_certify` computes `node_coverage_Y_Struct = mapped/executable` and gates PASS/FAIL at ≥0.95.
2. **Phase 2 — LTLf Synthesis** (`ltlf_synthesizer.py`, class `FLTLSynthesizer`). Identifies `exclusiveGateway` outgoing flows, then `_resolve_implicit_guards` computes the negated-conjunction "else" guard for unconditioned XOR flows (the "Zero Dead-Zone" claim — this one is real and matches the wiki's description). `_instantiate_ltlf_templates` emits sequence (`G(start(B) -> F(done(A)))`), XOR mutual-exclusion, and AND-gateway synchronization properties into three tiers (`P0_Critical_Sentinels`, `P1_Structural_Control_Flow`, `P2_Quality_Limits`). `_generate_sentinels` adds a generic "can't be done before started" sentinel per task plus one hardcoded example quality-limit property (`iteration_count <= 10`). `_layer_v1_certify` requires 100% guard-resolution coverage or raises.
3. **Phase 3 — Mutation-Based Validation** (`mutation_refiner.py`, class `BPMNMutationEngine` + `LTLfAuditor`/`MutationValidator`). Generates up to 20 mutants via 5 operators (gateway-type substitution, sequence-flow deletion, task retyping, condition inversion, loop-boundary edit) and checks whether the Phase 2 property suite "kills" each mutant.
4. **Phase 4 — Automata Lifting** — **claimed in the wiki, not present in code.** No SPOT integration, no NetworkX-based automaton construction beyond what `networkx` (already a dependency) could support, no isomorphism/language-inclusion proof, no GED/subgraph-homomorphism diagnostics. `main.py`'s `/verify` endpoint runs Phases 1–3 only and returns.

**API**: FastAPI `POST /verify` in `main.py`, phases 1→2→3 sequentially, broad `except Exception` at the top level (check whether per-phase error typing exists or whether failures collapse to one shape — mirrors a known Module 02 issue, verify independently here).

**No test suite exists** for Module 01 (`module_01_spec/` has no `tests/` directory — verify this is still true). **No BPMN corpus exists in the repo** (`find . -iname "*.bpmn"` returns nothing tracked — verify).

### The Novelty Inventory (everything the wiki now claims — "cover all novelties" means all of these)

**Original five (predate this update — verify each still matches code, they mostly should):**
1. Self-Strengthening Formalization Framework (Phase 3's own-graph mutation testing)
2. Zero Dead-Zone Protocol (Phase 2's implicit-else inference)
3. Coverage-Quantified Property Extraction (the per-phase certificates)
4. Sentinel Property Synthesis (the P0 "forbidden state" properties)
5. Hierarchical Property Classification (P0/P1/P2 tiers)

**New "NC series" (added this update — zero code, treat as unimplemented design):**
6. NC-1 — Specification Fidelity Index (SFI): composite score in `[0,1]` unifying trace-level Jaccard, normalized Graph Edit Distance, and propositional coverage, claimed to have "a formally proven monotonicity theorem."
7. NC-2 — Counterexample-Guided Specification Refinement (CGSR): CEGAR-inspired self-healing loop with three repair operators (ISOLATE, WEAKEN, SYNTHESIZE) triggered by a failed trace.
8. NC-3 — Priority-Weighted Behavioral Equivalence (PWBE): vector verdict `⟨E_P0, E_P1, E_P2⟩` per priority tier with a "hard P0 safety veto."
9. NC-4 — Specification Entropy Delta (ΔH): Shannon-entropy-based ($H = \log_2|L|$) measurement of information loss/inflation per BPMN element across the BPMN→LTLf transformation, using conditional entropy to localize the loss.

**New algorithmic + infrastructure claims (added this update — zero code):**
10. Parallel Gateway Super-Node Abstraction: collapsing AND-split/AND-join branches into a single super-node with the union of internal atomic propositions, to avoid state explosion.
11. Phase 4 dual validation: Trace Language Inclusion proof (`L(G_BPMN) = L(A_SPOT)`, soundness + completeness) and Structural Similarity Assessment (GED + subgraph homomorphism diagnostics).
12. TCB (Trusted Computing Base) analysis: SPOT + NetworkX as "trusted," the custom Formula Normalizer and Automaton-to-NetworkX Converter as "untrusted," defended by three strategies — (a) normalizer invertibility proof (`denormalize(normalize(φ)) == φ` across the whole suite), (b) N-version cross-validation against an independent `ltlf2dfa` compilation with `spot.are_equivalent` checking, (c) a canonical test-vector library (10+ baseline process maps from formal-verification literature, e.g. `bpmn2constraints` papers) that must compile isomorphically before certification.

Fetch the live wiki page yourself and confirm this list is complete and accurately restated — do not treat this prompt's summary as authoritative.

### The FLOW-BENCH question — verify, do not assume an answer

Module 02's evaluation harness (`module_02_extract/eval/flowbench_adapter.py`, consuming `module_02_extract/inputs/conditional_ootb.yaml`, the IBM FLOW-BENCH conditional/OOTB test set) has already established that the public FLOW-BENCH record schema is `{_metadata: {uid, tags}, input: {utterance, prior_sequence, prior_context}, expected_output: {sequence, bpmn}}`, and — critically — **each record's `expected_output.bpmn` field is itself a `$ref` to a file** (e.g. `output/uid_2_output.bpmn`) that is **not present anywhere in this repo**. A pre-session check confirmed `module_02_extract/inputs/output/` does not exist and no `.bpmn` file is tracked anywhere in the repo. This means:

- If those referenced `.bpmn` files exist in the full/public FLOW-BENCH release (outside this repo) and can be obtained, Module 01 has a **ready-made, non-synthetic evaluation corpus** — real BPMN diagrams paired with the same utterances/expected-sequences Module 02 already uses, letting the two modules' evaluations share a corpus.
- If those files are unobtainable (private/internal-only, like other IBM-internal FLOW-BENCH assets), Module 01 needs its **own synthetic BPMN corpus**, generated or hand-authored, the way Module 02 built `eval/corpus/` from scratch once the public dataset turned out not to have executable ground truth (`.claude/memory/flowbench_groundtruth_finding.md` in this repo has that precedent — read it).

**This is Agent 4's first task, not an assumption to make going in.**

### Anti-circularity — port Module 02's hard-won rule, do not repeat the mistake

Phase 3 (`mutation_refiner.py`) already does self-mutation-testing: it mutates Module 01's **own extracted graph**, then checks whether Module 01's **own synthesized property suite** kills the mutants it made from itself. That is a legitimate internal design feature (it's how the property suite gets strengthened before shipping), but **it is not external validation** — it is the tool grading its own homework, and it will always trend toward 100% because failing mutants trigger the refinement loop until they're caught.

Module 02's team spent multiple sessions on exactly this failure mode (see `.claude/memory/round3_verified_findings_2026_07_04.md` and `.claude/memory/session_2026_07_04_t1_t7_implementation.md` in this repo — the "V3 confidence=1.0 makes combined verdict vacuous" finding, and the eventual anti-circularity rules: disjoint calibration/evaluation splits, an **independent** gold-label process not derived from the tool under test, and a pre-registered (not post-hoc-fitted) operating threshold). **Any "evaluate Module 01 using a FLOW-BENCH-like method" plan must be built from ground truth external to Module 01** — e.g., BPMN diagrams independently labeled "structurally valid / structurally broken" or "captures the utterance / drops a requirement," not diagrams Module 01 mutated and then judged with its own property suite. Say explicitly in your evaluation deliverable which parts of Phase 3 are internal self-strengthening (keep, but don't count as evaluation) and which parts of your new plan are the actual external evaluation.

---

## AGENT ROLES

Execute all five in the order given. Label each output clearly with a `## AGENT N — <name>` header.

---

### AGENT 1 — Implementation Verifier

**Mandate**: Ground-truth the "Verified Current Implementation" section and the full Novelty Inventory above against actual current source (`module_01_spec/src/*` on `develop`) and the live wiki page. Do not let stale or unverified claims propagate to Agents 2–5.

1. Re-open each of the four source files and confirm/correct the phase descriptions above (quote file:line for anything you assert).
2. For each of the 12 novelty items, state CONFIRMED-IN-CODE / PARTIALLY-IN-CODE / DESIGN-ONLY-NO-CODE, with evidence.
3. Independent sweep: any `TODO`/`FIXME`/stub/`pass`-only method, any silently-swallowed exception, any place `main.py`'s `/verify` masks a phase-specific failure behind a generic 500.
4. Confirm whether `module_01_spec/` has any test directory, any `eval/`-style harness, or any BPMN sample file anywhere in the repo (tracked or untracked) — re-run the check, don't trust this prompt's claim of "none."

**Output format**: Table (Item | Verdict | Evidence | Actual state) for the 12 novelty items, preceded by corrected phase descriptions if anything above was wrong, followed by the independent sweep as a bullet list with file:line citations.

---

### AGENT 2 — Novelty → Hypothesis → Falsification Mapper

**Mandate**: For every novelty item Agent 1 marked DESIGN-ONLY or PARTIALLY-IN-CODE (expect this to be most of items 6–12), and for the already-implemented items 1–5 too, produce a **falsifiable hypothesis** and the **experiment that could falsify it**. This is the step that turns "we built X" into "we can show X is true."

For each item:
- **Claim** (restate precisely from the wiki, cite it).
- **Falsifiable hypothesis** (e.g. for NC-1/SFI: "H: SFI is monotonic — for any two specification-transformation errors e1, e2 where e1 is a strict subset of e2's information loss, SFI(e1) ≥ SFI(e2)." For NC-4/ΔH: "H: conditional entropy correctly attributes information loss to the specific BPMN element that caused it, not just to the transformation as a whole.")
- **Is it empirically testable, or is it framing/definitional?** Be honest — some claims (e.g. "first application of X to Y" novelty-priority claims) are not falsifiable and should be labeled as scholarly-positioning claims, not scientific ones. Flag anything that risks being **vacuous by construction** the way Module 02's original V3-confidence=1.0 combined-verdict was — e.g., check whether NC-1's "monotonicity theorem" is provable only under assumptions that never occur in practice, or whether NC-3's P0 veto makes the P1/P2 sub-scores unreachable/irrelevant whenever any P0 property is touched.
- **Minimum experiment to test it**: concrete enough to be an implementation task (what corpus, what perturbation, what metric, what would count as falsification).

**Output format**: One table row per novelty item (12 rows): Claim | Hypothesis | Testable (Y/N + why) | Vacuousness risk (if any) | Minimum experiment.

---

### AGENT 3 — Edge-Case Auditor (BPMN/LTLf domain)

**Mandate**: Module 01 must extract a faithful semantic graph and a sound, sensitive LTLf property suite for **arbitrary well-formed and malformed BPMN 2.0 XML**. Systematically enumerate BPMN/LTLf-specific edge cases and check, per case, whether current code (Phases 1–3) handles it, degrades gracefully, or fails silently/loudly. Also cover what the *planned* Phase 4 + NC-series work will need to handle.

**Categories to cover** (for each: does anything in current code exercise it? construct a minimal BPMN snippet illustrating it if useful; state the failure mode if unhandled):

1. **Structural BPMN edge cases**: sub-processes (nested `bpmn:subProcess`), call activities, event sub-processes, boundary events (interrupting vs non-interrupting), multiple start/end events, inclusive (`inclusiveGateway`, OR-semantics) gateways — note `EXECUTABLE_NODES` in `semantic_extractor.py` doesn't list `inclusiveGateway` at all, verify what happens to one, message/signal/timer intermediate events, lanes/pools (multi-participant collaboration diagrams, not single `process`), loops expressed via BPMN's native loop markers vs. sequence-flow cycles back to an earlier node.
2. **Gateway edge cases**: unbalanced gateways (an AND-split with no matching AND-join, or vice versa), nested gateways (a gateway whose branch immediately hits another gateway), an XOR gateway with 3+ outgoing flows and 2+ unconditioned ("else") flows (which "else" wins, or is this an error?), a gateway with only one outgoing flow, cyclic gateway structures (loops through the same XOR).
3. **Guard/condition edge cases**: conditions that aren't simple comparisons (compound boolean expressions, nested parens, function-call-like expressions in BPMN's `conditionExpression`), non-XML-safe characters in condition text (needs escaping), a default-flow marker (`default` attribute on the gateway, which BPMN uses instead of an implicit no-condition flow — does `_resolve_implicit_guards` check for this or would it double-handle a diagram that already declares a default explicitly?), empty/whitespace-only condition text.
4. **Malformed/adversarial XML**: an XML document that parses but has no `bpmn:process` element, a process with executable nodes but zero sequence flows (isolated islands), dangling `sourceRef`/`targetRef` (pointing to a node ID that doesn't exist), duplicate node IDs, extremely large diagrams (hundreds of gateways — does mutual-exclusion property generation, which is O(n²) per gateway in `_instantiate_ltlf_templates`, blow up?), a diagram below the 95% node-coverage threshold (confirm the actual behavior when Phase 1 FAILs — does `api.py`/`main.py` propagate a clean error or crash?).
5. **Phase 3 (mutation) edge cases**: a graph too small for 20 distinct mutants to exist (the `max_attempts=1000` loop in `generate_mutants` — does it terminate cleanly with fewer mutants, or hang/silently under-deliver?), a mutation that produces an unparseable or self-contradictory graph, mutants that are semantically identical to the original despite being structurally different (the `!=` check in `generate_mutants` is a dict/structural comparison — could two different-looking mutants both be logically equivalent, inflating the "kill" count without real sensitivity?).
6. **Phase-4-and-beyond edge cases (for the planned work)**: what happens when the LTLf-to-SPOT translation encounters a property SPOT's parser rejects (syntax mismatch between Module 01's hand-rolled LTLf strings and SPOT's expected format — note the wiki's own TCB section flags exactly this risk via the "Formula Normalizer"), unbounded/infinite-state BPMN patterns (unbounded loops with no P2 quality-limit property attached) that could make automaton construction or emptiness-checking non-terminating or intractable, and what the super-node abstraction does to counterexample traces (does a violation inside a super-node produce a diagnosable trace, or does the abstraction destroy the information needed to localize the error — this interacts directly with NC-4's "pinpoint which element" claim).

**Output format**: One table per category — Edge case | Illustrative BPMN/LTLf snippet (short) | Current handling (file:line or "no code/test found") | Failure mode if unhandled | Severity (thesis-critical / robustness / cosmetic).

---

### AGENT 4 — Evaluation Methodologist

**Mandate**: Design a concrete, executable, non-circular evaluation plan for Module 01, structurally analogous to what Module 02 built (mutation corpus → calibration protocol → detection/specificity split → honest reporting) but correctly adapted to Module 01's actual domain (BPMN/LTLf, not Python). Do not port Module 02's mechanics blindly — verify what transfers and what doesn't.

**Deliver, in order**:

1. **Resolve the FLOW-BENCH `bpmn-ref` question first.** Check whether `module_02_extract/inputs/conditional_ootb.yaml`'s `expected_output.bpmn[].$ref` targets (e.g. `output/uid_2_output.bpmn`) are obtainable from the public IBM FLOW-BENCH release, any cached/mirrored copy accessible to you, or must be treated as unavailable (matching the precedent in `.claude/memory/flowbench_groundtruth_finding.md`, where the public FLOW-BENCH turned out not to have the executable ground truth Module 02 initially assumed). State your finding plainly: AVAILABLE / UNAVAILABLE / PARTIALLY AVAILABLE, with what you checked.
2. **Corpus plan for both outcomes**, so the plan works either way:
   - If BPMN refs are available: how to acquire them, how many usable diagrams result, and — critically — how to get an **independent** correct/broken (or utterance-match/utterance-mismatch) label for each one that isn't derived from Module 01 itself (e.g., the paired `expected_output.sequence` Python already gives an independent cross-check: does the BPMN's structure actually match the sequence Module 02 treats as ground truth for the same uid?).
   - If unavailable: a concrete synthetic-corpus construction plan — e.g., hand-author or LLM-draft N canonical BPMN diagrams spanning the structural categories from Agent 3 (sequential, XOR, AND, nested, cyclic), with an independently-authored (not Module-01-derived) "this diagram should imply property set P" gold annotation for a structural-accuracy check, analogous to Module 02's E2 gold-WIR labeler (`module_02_extract/eval/e2_structural.py` — read it for the pattern, don't copy it mechanically).
3. **BPMN-specific mutation operator specification for *external* evaluation** (distinct from Phase 3's internal self-check): define mutation operators that model realistic LLM-authoring errors in a BPMN-generation context (e.g., an LLM asked to draw a process from a spec draws the wrong gateway type, drops a branch, mislabels a condition) — each with a one-line description and a before/after snippet, concrete enough to hand to an implementer as `eval/mutate_bpmn.py`.
4. **Statistical requirements**: given whatever corpus size Agent 4's step 2 lands on, restate the exact-binomial power analysis for a "≥X% detection" claim (mirror Module 02's approach — `.claude/memory` has the precedent for what a too-small N produces) and state the minimum floor before any detection-rate claim is defensible.
5. **Calibration protocol**: CALIB/EVAL disjoint split, a pre-registered operating-point rule (don't fit the threshold to the same data you evaluate it on), and exact non-circular thesis wording — explicitly distinguishing "Phase 3 self-strengthening (design feature, not evidence)" from "the external evaluation above (the actual evidence)."
6. **Metrics for the NC series specifically**: for NC-1 (SFI) propose how to validate the monotonicity claim empirically (a controlled perturbation series of increasing severity, checking SFI is non-increasing); for NC-4 (ΔH) propose how to validate localization accuracy (inject a known single-element corruption, check whether the entropy-delta attribution correctly points at that element, at what rate); for NC-3 (PWBE) propose how to check the P0-veto doesn't make P1/P2 information vacuous in practice (what fraction of real/synthetic cases have P0 violations, and does the vector verdict carry real information in the rest).

**Output format**: Numbered sections matching the 6 items above. Every recommendation must be concrete enough to hand to an implementer with no further research — no "TBD" or "further investigation needed" as a final answer; if something is genuinely unresolvable without external access, say so explicitly and give the fallback plan.

---

### AGENT 5 — Architecture Critic

**Mandate**: Adversarial thesis-committee questioning, grounded in Agents 1–4's verified findings (not the wiki's framing). Generate the hardest current questions.

Must include:
- The wiki-vs-code gap itself: is claiming NC-1..4, Phase 4, and the TCB analysis in the thesis defensible before any of it exists in code — what's the honest scoping (implemented / designed-not-built / aspirational-future-work) if the term runs out before Phase 4 is built?
- Self-strengthening circularity (Phase 3) — is there any risk the thesis narrative conflates "our mutation testing improved our own suite" with "we validated our suite," the way Module 02 initially did?
- The "first application of X to Y" priority claims (items 1, 4, 6, 9 in the inventory) — are these actually checkable, or purely rhetorical? What's the examiner's obvious counter?
- The super-node abstraction's information loss vs. NC-4's localization claim (flagged in Agent 3, category 6) — do these two features actively undermine each other?
- The TCB analysis's own soundness: is "SPOT and NetworkX are trusted because peer-reviewed/battle-tested" itself an unfalsifiable assumption, and does the N-version cross-validation strategy (comparing against `ltlf2dfa`) actually catch shared-specification-level errors (both compilers being fed the same wrong LTLf formula) or only compiler-implementation bugs?
- Given Module 01 depends on nothing upstream (per the wiki, it "runs entirely independently of the code side") but Module 03 depends on Module 01's automaton output — what's the blast radius on Module 03 if Phase 4 slips, and is there a documented fallback (e.g., Module 03 operating on the Phase 1–3 property suite directly without the automaton)?
- Pick 2–3 of Agent 3's most damaging edge cases and phrase them as committee attacks.

**Output format**: Numbered list. Do not soften the questions.

---

## SYNTHESIS AGENT — The E2E Implementation Plan (the actual deliverable)

Integrate Agents 1–5 into one document. Do not introduce novel ideas not grounded in the other five agents' findings; where findings conflict, state the conflict and resolve it with justification. This is the primary output — the agent sections above are its evidence base, not the deliverable itself.

Produce exactly these sections:

#### 1. Verified Current-State Scorecard
One row per novelty item (Agent 1's table), plus the independent sweep findings.

#### 2. Novelty & Hypothesis Register
Agent 2's table in full — every claimed contribution with its hypothesis, testability verdict, and vacuousness risk flagged.

#### 3. Phase-Ordered Implementation Plan
For each unbuilt or partially-built piece (Phase 4, NC-1..4, super-node abstraction, TCB defenses), in a sensible dependency order (e.g. Phase 4's base automaton construction almost certainly must exist before NC-1/NC-3/NC-4 can be computed against it; the TCB invertibility proof and N-version check are likely gate-able independently):
- What file(s) to create/modify (propose concrete paths under `module_01_spec/src/`, following the existing `*_extractor.py`/`*_synthesizer.py`/`*_refiner.py` naming pattern).
- What new dependency (if any) it needs (e.g. `spot`, `ltlf2dfa`) and any known integration risk (SPOT is a C++ library with Python bindings — note install/Docker implications given `module_01_spec/Dockerfile` exists and would need updating).
- Which edge cases from Agent 3 it must handle before being called done.
- Acceptance criteria (what would make this piece "implemented," not just "present").
- Effort estimate (S/M/L).

#### 4. BPMN/LTLf Edge-Case Risk Register
Top 10 from Agent 3, ranked by severity, each with a recommended fix and effort estimate.

#### 5. Executable Evaluation Plan
Agent 4's output, reconciled, ending with a concrete "what to build first" instruction (e.g. "resolve the bpmn-ref availability question, then write `eval/mutate_bpmn.py` implementing operators X, Y, Z against corpus source Z").

#### 6. Top Thesis Vulnerabilities (ranked)
From Agent 5, each with: vulnerability, mitigation (code-or-wording), risk if unaddressed.

#### 7. Next Implementation Session Plan
A concrete, ordered task list (not phases — actual tasks), each scoped to one sitting, referencing exact files, in the order a coding session should tackle them.

---

## EXECUTION INSTRUCTIONS

1. Run Agent 1 first and alone — everything downstream depends on it. Then Agents 2–4 (present sequentially even if reasoned about in parallel). Then Agent 5. Then the Synthesis Agent.
2. Label each agent's output clearly.
3. Every factual claim about the codebase or the wiki must cite a file path (and line numbers / commit where feasible). Unverified claims must be flagged as such, not stated as fact.
4. The Synthesis section must be directly actionable — specific enough to start coding from without further research.
5. After the full output, add a `## NEXT SESSION` section: a 5-bullet ordered list of first actions, each referencing exact files.

---

## WHAT NOT TO DO

- Do not write any code. Do not edit any files (including the wiki).
- Do not restate the wiki's novelty claims as fact without checking them against current source first — this is the #1 failure mode on this project and has already happened once (Module 02) and once already within this very wiki page (claims added with no corresponding code).
- Do not let Phase 3's internal self-mutation-testing count as "the evaluation" — it is a design feature, not external evidence. The evaluation plan must use ground truth independent of Module 01's own output.
- Do not copy Module 02's evaluation mechanics mechanically — verify what transfers to the BPMN/LTLf domain (Agent 4, item 1) before assuming FLOW-BENCH works the same way here.
- Do not make vague recommendations — every recommendation must be specific enough to act on directly (concrete file paths, concrete operator definitions, concrete thresholds/splits).
