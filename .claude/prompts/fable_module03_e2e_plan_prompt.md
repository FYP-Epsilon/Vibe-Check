# Fable 5 — Module 03: End-to-End Implementation Plan (Novelties, Edge Cases, Hypotheses, Cross-Module Alignment, FLOW-BENCH-Style Evaluation)
# Copy-paste this entire prompt into a new Fable 5 session with file access to this repo.
# Do NOT summarize or abbreviate it before starting — the full context is required.

---

## SESSION MANDATE

You are producing a **research and planning session only** — the deliverable is a single, implementation-ready **end-to-end plan** for Module 03 of a formal-verification research system, precise enough that a coding session could start from it with no further research. **No code will be written. No files will be edited.**

Module 03 belongs to a teammate, not the operator running this prompt — this session hands that teammate (or a future coding session) a rigorous plan, not a patch. Treat everything below as ground truth as of this session; verify anything you rely on against current source before asserting it.

**This session must produce a plan that explicitly aligns with two sibling plans that already exist in this repo**:
- **Module 02** (`module_02_extract/`) — the code-side extractor, **already implemented and load-bearing**: WIR extraction (V3 static AST), symbolic validation (V2 Z3), dynamic tracing (V1), a certificate composition, and a mature `eval/` harness including a **multi-implementation corpus** (`module_02_extract/eval/variants/`, contract at `docs/module02/11_multi_impl_corpus_contract.md`) that is **explicitly documented as Module 03's clustering ground truth** — read that contract in full before designing Module 03's evaluation, it removes most of the "how do we get ground truth" work.
- **Module 01** (`module_01_spec/`) — the spec-side extractor, **planned but largely unbuilt as of this session**: `.claude/module01_e2e_plan.md` is a prior Fable session's full E2E plan for it (verified against source the same way this session must verify Module 03), including a Phase 0 soundness fix list, a Phase 4 (SPOT automata lifting) that does not exist in code yet, and an evaluation corpus built from the **public IBM FLOW-BENCH** dataset (`github.com/IBM/flow-bench`, `data/output/uid_N_output.bpmn`, 100 diagrams, Apache-2.0). **Read that document** — Module 03 sits directly downstream of Module 01's Phase 4 output, so this session's plan must state explicitly what Module 03 needs from Module 01 (today: nothing, because Phase 4 doesn't exist) and what the integration contract should look like once it does.

**Critical ground rule — the same failure mode already caught twice on this project (Module 02's early self-validation circularity, and Module 01's wiki-vs-code gap found in the sibling session) has independent evidence of a *third*, different shape in Module 03: not a wiki overclaiming unbuilt code, but two source-code implementations of the same module that silently disagree with each other.** A pre-session check found `module_03_equiv/src/` contains **two parallel, non-interoperating implementations**:
1. A **pure-Python 4-phase pipeline** (`lifter.py`, `stuttering_engine.py`, `clustering.py`, `model_checker.py`, orchestrated by `pipeline.py`) — this is the one with real test coverage (`tests/test_pipeline.py`, covering all 4 phases + integration).
2. A **C++/Pybind11 engine** (`lifter.cpp`/`lifter.hpp`, compiled to `vibecheck_lifter.*.so`, driven by `main.py`) — this is what the module's **Dockerfile actually runs** (`CMD ["python3", "-m", "src.main"]`), and `main.py` is a one-shot demo script with no persistent server (no FastAPI app anywhere in the module) that runs a mock verification, prints output, and exits.

These two paths implement **different behavior for the same claimed novelties** — e.g. semantic BPMN-task-name matching (`nlp_utils.py`'s Sentence-BERT `compute_max_similarity`) is called **only** from `lifter.cpp:132-139`, never from the pure-Python `lifter.py` that the tested pipeline actually runs, despite `sentence-transformers`/`torch` being installed dependencies of the module (`requirements.txt`) — a wiring gap, not a missing-capability gap, but currently a real behavioral divergence. Similarly, `clustering.py`'s `BehavioralClusterer` builds cluster membership via a **pairwise O(n²) equivalence matrix + Union-Find** (`_build_equivalence_matrix`, confirmed by reading the source), while a `compute_deterministic_hash` function exists **only** in the C++ path and is never called by `clustering.py` at all. **Do not trust either implementation's claims about the other without checking; do not assume the wiki's or docs' description of "the pipeline" refers to a single, unified implementation — verify which file the claim is actually true of.** Cite file path + line range for every factual claim about the code.

You will operate as **five concurrent sub-agents**, each with a distinct mandate, followed by a **Synthesis Agent** that assembles the actual E2E plan. Read the full brief below before beginning any analysis.

---

## PROJECT BRIEF

**System**: VibeCheck — Post-Hoc Formal Verification of LLM-Generated Python Code Using BPMN-Derived Temporal Specifications
**University**: Faculty of IT, University of Moratuwa — FYP, Group 18 (Epsilon)
**Module in scope**: Module 03 — Equivalence Checking Engine (owned by a teammate; read/plan only, no edits)
**Repo**: `C:\Research\FYP\Vibe-Check`, branch `develop`. Module 03 source: `module_03_equiv/src/{lifter.py, lifter.cpp, lifter.hpp, stuttering_engine.py, clustering.py, model_checker.py, pipeline.py, main.py, nlp_utils.py}`, tests: `module_03_equiv/tests/{test_pipeline.py, test_cpp_engine.py}`.
**Wiki**: separate git repo, `https://github.com/FYP-Epsilon/Vibe-Check.wiki.git` — page `Module-03-Equivalence-Engine.md` (this one already carries a "⚠️ pending owner review" banner and is noticeably more hedged than Module 01's pre-correction page was — but it was drafted before the split-brain finding above, and still describes "the pipeline" as one coherent system with cascading semantic matching, hash-based clustering, and a real spec-vs-code Phase D. Fetch it directly and re-check each claim against **which file** actually implements it, not just whether the behavior exists somewhere in the repo).

### Pipeline Architecture (Dual-Track, 5-Stage)

```
Track A (Spec):   BPMN 2.0 XML ──► Module 01 ──► M_spec + LTLf Props ──────────┐
                                    (Stage S1)                                    ▼
                                                                            Module 03 ──► Verdict
                                                                            (Stage S5)    ▲
Track B (Code):   LLM Python Code ──► Module 02 ──► WIR + M_code ───────────────┘
                                       (Stages S3-S4)
```

### Module 03 — Verified Current Implementation (re-verify, don't just restate)

**Phase A — Lifter (WIR → LTS/automaton).**
- Pure-Python: `lifter.py`, class `WIRLifter` + `LTS`/`LifterConfig`. Binary quality gate: aborts (raises `QualityGateError`) if `certificate.abort is True` **or** `certificate.guard_success_rate < confidence_threshold` (default 0.95) — this is a **two-state** gate (PASS / ABORT), not the wiki's described three-tier "full verification / conservative mode / refuse" EQI behavior; verify whether any middle-ground handling exists anywhere else before concluding the wiki overclaims here. Loop unrolling bounded by `loop_max` (default 3 in the pipeline's `LifterConfig`, per `pipeline.py`'s instantiation — confirm the module's own default, not just the demo's).
- C++: `lifter.cpp`/`lifter.hpp`, class `AdvancedLifter`, built via SPOT (`spot::twa_graph_ptr lift_to_lts(...)`, `tarjan_tau_collapse(...)`), with `parse_wir_types`, `set_bpmn_tasks`, `semantic_match` (cascading exact → Levenshtein → `nlp_utils.compute_max_similarity` Sentence-BERT). This is the path the wiki's Phase A description actually matches — **but it is not invoked by `pipeline.py`, `test_pipeline.py`, or any other pure-Python code path.**

**Phase B — Stuttering bisimulation.** `stuttering_engine.py`, class `StutteringEngine`. Genuinely implements divergence-sensitivity: Tarjan SCC decomposition, `_identify_divergent_sccs`, `_propagate_divergence` (backward propagation from divergent SCCs). This one **checks out** against the wiki's novelty #2 claim — verify the specifics (SCC criteria, propagation correctness) rather than just confirming the function names exist.

**Phase C — Clustering.** `clustering.py`, class `BehavioralClusterer`. Builds a **pairwise** equivalence matrix (`_build_equivalence_matrix`, O(n²) stuttering-bisimulation checks between every pair of lifted LTS) then Union-Find (`_UnionFind`) to form clusters; representative = lowest cyclomatic complexity (`_select_representatives`). **This directly contradicts the wiki's "hash-based clustering... without needing a full pairwise comparison of every pair" claim** (novelty #3) — the hash-based approach (`compute_deterministic_hash`) exists only in the untested-by-default C++ path (`lifter.cpp`/`.hpp`) and has no caller anywhere in `clustering.py`.

**Phase D — Model checking.** `model_checker.py`, class `ModelChecker` + `PropertyMonitor`. `PropertyMonitor` has exactly **two** factory methods: `from_reachability(forbidden_label)` (2-state monitor, flags reachability of a named label) and `from_loop_bound_check()` (structural trap-state check). **There is no generic LTLf-formula ingestion, no consumption of a Module-01-provided specification automaton, and no "translate spec properties → automaton → synchronous product → emptiness check against the code automaton" mechanism anywhere in the code** — this is the entirety of what the wiki's Phase D description (and its "EQI gate"/spec-comparison language) claims exists. `pipeline.py`'s `run_pipeline` only ever calls these two canned checks (loop-bound safety, plus reachability of `"error"`/`"abort"`/`"panic"` if those labels happen to appear in the LTS's atomic propositions) — never anything derived from a BPMN diagram or an LTLf property string.

**No live service.** Unlike Module 01 and Module 02 — both of which run a persistent `uvicorn` FastAPI server as their Docker `CMD` (`CMD ["uvicorn", "src.main:app", ...]`) — Module 03's `Dockerfile` CMD is `["python3", "-m", "src.main"]`, and `main.py` contains no FastAPI app object, no route, nothing that binds a port; it runs a one-shot demo (`parse_wir_types` → `get_variable_map` → `set_bpmn_tasks` → `semantic_match` on three hardcoded example strings) and returns after a `time.sleep(2)`. **`module_04_ui/src/app.py` (lines ~95-96, ~474, ~508, ~562) already documents this as intentional** — it treats "Equiv Engine" as a CLI binary requiring in-container invocation, not an HTTP service, and its health check only checks importability. Determine (Agent 1) whether this is the *intended final architecture* (M03 as an invoked library/CLI, not a service) or an *unfinished* piece — check `docs/architecture/module_03_execution_plan.md` and `docs/module_summery/Module_03_Equivalence_Engine.md` for the module owner's own stated intent before assuming either way.

**M02 → M03 interface: real, tested.** `lifter.py`'s `WIRLifter.lift()` consumes exactly the WIR + certificate shape Module 02's V3 pipeline produces (confirm current shape against `module_02_extract/src/ast_extractor/schema.py` and `certificate.py`, not just the `DEMO_WIR` fixture in `pipeline.py`). `test_pipeline.py` has `test_pass_high_confidence`, `test_reject_low_confidence`, `test_reject_abort_flag` — the certificate-gating behavior is genuinely exercised.

**M01 → M03 interface: does not exist.** No file in `module_03_equiv/src/` imports, parses, or references BPMN, LTLf, or any Module 01 output format. The only BPMN-adjacent code is the C++ path's `set_bpmn_tasks`/`semantic_match`, which matches **task name strings** for labeling purposes — not temporal properties, not an automaton, not anything Module 01's Phase 2 (LTLf synthesis) or planned Phase 4 (automata lifting) would emit. **This mirrors the finding already made in `.claude/module01_e2e_plan.md`'s Agent 5, point 8** — read it, don't re-derive it independently and risk disagreeing without noticing.

### The Novelty Inventory (from the wiki — verify each against **which implementation**, not just "the repo")

1. **Independent-automata spec comparison** — comparing an untrusted code-derived automaton against an independently-built spec automaton (framed as the first framework to do this for BPMN-spec vs. LLM-code). Per the above: **no spec automaton is consumed anywhere in the current code.**
2. **Divergence-sensitive stuttering bisimulation** — the safety fix for the "infinite silent loop treated as equivalent to a harmless wait" blind spot. Confirmed real in `stuttering_engine.py` (pure Python) — verify correctness, not just presence.
3. **Hash-based clustering** — claimed to avoid full pairwise comparison. The tested path (`clustering.py`) is pairwise; the hash function exists only in the disconnected C++ path.
4. **Parallel-gateway abstraction** — treating a k-branch AND-gateway as one abstract state instead of reasoning about k! orderings. **Not verified either way in this prompt's pre-session check** — search `lifter.py`, `lifter.cpp`, and `pipeline.py`'s `DEMO_WIR`/test fixtures specifically for parallel/AND-gateway handling; the demo WIR in `pipeline.py` contains only an XOR-style gateway (`node_3`), no AND-split.
5. **Bounded equivalence checking for loops** — confirmed real: `LifterConfig.loop_max` + unrolling in `lifter.py`.

Fetch the live wiki page yourself and confirm this list is complete and accurately restated — do not treat this prompt's summary as authoritative.

### The alignment asset — Module 02 already built Module 03's clustering ground truth

Read `docs/module02/11_multi_impl_corpus_contract.md` in full before designing anything in Agent 4. Summary (verify against the doc and the actual files, don't just trust this restatement): `module_02_extract/eval/variants/` contains real LLM-generated implementations (3 models × up to 101 FLOW-BENCH uids) of the same base corpus programs Module 02 already uses for its own calibration, each behaviorally **admitted** or **rejected_behavioral** against its base via an independent, WIR-free execution-diff protocol (N=100 concrete inputs, round-robin over the union of both sides' guard-literal pools). The contract's own §4 states the intended cluster ground truth explicitly: *one equivalence cluster per uid = base + every admitted variant; every rejected_behavioral variant is its own singleton, and if Module 03's clustering merges one into the base's cluster, that is evidence of over-merging, not a benign result.* §7 additionally specifies that any M03-adjacent cross-implementation comparison should use Module 02's differential comparator in `comparison_mode="task_only"`, not the pipeline's `strict` default — the two modes' measured false-alarm-rate difference (0.25 → 0.10) is directly relevant to any Module 03 evaluation figure that reuses this machinery. This corpus uses the **same FLOW-BENCH uid space** as Module 01's plan (`.claude/module01_e2e_plan.md` §4.2) — the three modules can and should share one corpus identity (`uid`) end-to-end.

### Anti-circularity — the same rule, applied to a different loop this time

Module 03 has no internal self-mutation-testing the way Module 01's Phase 3 does, but it has an analogous risk: **if Module 03's own clustering or bisimulation output is used to validate Module 03's own clustering or bisimulation output, that's circular.** The Module 02 multi-impl contract above is explicitly designed to avoid this (admission verdicts are computed by an independent execution-diff, never by Module 03's own machinery) — any evaluation plan Agent 4 designs must preserve that property: ground truth for "should these two implementations cluster together" must never come from running Module 03's own bisimulation check and calling the result "ground truth." Likewise, once Module 01's Phase 4 exists, "does the code satisfy the spec" ground truth for calibration purposes should come from an independent source (e.g. IBM's `expected_output.sequence` label, or a human/LLM-adjudicated review of a sample) — not from running Module 03's own Phase D and treating its own verdict as validation of itself.

---

## AGENT ROLES

Execute all five in the order given. Label each output clearly with a `## AGENT N — <name>` header.

---

### AGENT 1 — Implementation Verifier

**Mandate**: Ground-truth the "Verified Current Implementation" section and the full Novelty Inventory above against actual current source (`module_03_equiv/src/*` on `develop`), the live wiki page, and `docs/architecture/module_03_execution_plan.md` / `docs/module_summery/Module_03_Equivalence_Engine.md` (read these for the module owner's own stated intent, especially re: the CLI-vs-service question and the split-brain Python/C++ situation — is unifying them an acknowledged to-do, or does the owner intend them to stay separate with different responsibilities?).

1. Re-open each of the 9 source files and confirm/correct the phase descriptions above (quote file:line for anything you assert). Explicitly resolve novelty #4 (parallel-gateway abstraction) — present or absent, where.
2. For each of the 5 novelty items, state CONFIRMED-IN-CODE (name which file) / PARTIALLY-IN-CODE / DESIGN-ONLY-NO-CODE / SPLIT-IMPLEMENTATION (exists differently in the Python vs. C++ path — say how), with evidence.
3. Independent sweep: any `TODO`/`FIXME`/stub, any silently-swallowed exception, any place a phase's failure mode is undocumented or untested, whether `test_cpp_engine.py`'s graceful `sys.exit(0)` (when the `.so` isn't importable) means CI could report this test suite as passing without ever exercising the C++ engine — check how/where CI or test running actually happens for this module.
4. Confirm the current M02→M03 WIR/certificate schema match is still accurate (re-check against `module_02_extract/src/ast_extractor/schema.py` and `certificate.py` on `develop` — Module 02 has changed several times per its own memory trail; don't assume `pipeline.py`'s `DEMO_WIR` fixture reflects the current schema).
5. State plainly whether "Module 03 as CLI/library, not HTTP service" is confirmed intentional or an open gap.

**Output format**: Table (Item | Verdict | Evidence | Actual state) for the 5 novelty items, preceded by corrected phase descriptions if anything above was wrong, followed by the independent sweep as a bullet list with file:line citations.

---

### AGENT 2 — Novelty → Hypothesis → Falsification Mapper

**Mandate**: For every novelty item, produce a **falsifiable hypothesis** and the **experiment that could falsify it** — same discipline as the sibling Module 01 session (`.claude/module01_e2e_plan.md` Agent 2), so the two documents are comparable when read together.

For each item:
- **Claim** (restate precisely from the wiki, cite it).
- **Falsifiable hypothesis.** E.g. for divergence-sensitivity (item 2): "H: for any two LTS where one contains a reachable silent-only cycle (a divergent SCC) and the other does not, `StutteringEngine.compute` never places them in the same equivalence block." For clustering (item 3): "H: clustering.py's pairwise+Union-Find output is set-identical to what a hash-based approach on `compute_deterministic_hash` would produce" (this is checkable directly, and resolves whether "hash-based" is even a behaviorally distinct claim or just an implementation-strategy footnote).
- **Is it empirically testable, or is it framing/definitional?** Flag anything at risk of being tautological — e.g. does "independent-automata comparison" (item 1) even make sense to test before Module 01's Phase 4 exists, or is the correct answer "not testable until [prerequisite]"?
- **Minimum experiment**: concrete enough to be an implementation task (what LTS pairs/corpus, what perturbation, what metric).

Also address explicitly: **item 3's hash-based claim is a strong candidate for a claim that should simply be corrected, not defended** — a deterministic structural hash can only substitute for pairwise bisimulation checking if canonicalization is exact (no false negatives from cosmetically-different-but-equivalent LTS structures); state whether that's plausible for this domain or whether the hash approach is actually a *heuristic pre-filter* to reduce pairwise comparisons, not a replacement for them — this changes what the "correct" claim should say.

**Output format**: One table row per novelty item (5 rows): Claim | Hypothesis | Testable (Y/N + why) | Risk flag (tautology / needs-prerequisite / claim-should-be-corrected) | Minimum experiment.

---

### AGENT 3 — Edge-Case Auditor (LTS / bisimulation / clustering / model-checking domain)

**Mandate**: Module 03 must correctly lift arbitrary Module-02-conformant WIRs to LTS, correctly determine behavioral equivalence under divergence-sensitive stuttering bisimulation, correctly cluster and pick representatives, and correctly check properties. Systematically enumerate domain-specific edge cases and check, per case, whether current code (whichever path — say which) handles it, degrades gracefully, or fails silently/loudly.

**Categories to cover** (for each: does a current test exercise it? construct a minimal WIR/LTS snippet if useful; state the failure mode if unhandled):

1. **Lifting edge cases (Phase A)**: WIR with zero nodes / only entry+exit, WIR with a node whose `type` isn't one of the ones `lifter.py` recognizes, nested function calls (the `functions` dict in the WIR schema — how deep can nesting go before the lifter breaks), a loop whose guard can't be statically bounded (does it hard-fail, silently cap at `loop_max`, or something else — and is the cap's semantic validity documented, e.g. does unrolling 3 times of a loop that actually runs 10 times produce a sound over/under-approximation or an unsound one), recursive functions (direct and mutual — does the lifter terminate?), a WIR whose `certificate` is missing fields the quality gate expects (what's the failure mode — `KeyError` crash, or graceful default?).
2. **Divergence/bisimulation edge cases (Phase B)**: an LTS with a divergent SCC that is *unreachable* from the initial state (does it still get flagged, incorrectly penalizing something the code never actually does?), two LTS that are stuttering-bisimilar in one direction but not symmetric (a bug class specific to hand-rolled bisimulation implementations — verify the algorithm's symmetry), an LTS with self-loops that aren't divergence (e.g. a legitimate "poll and check" pattern) vs. a genuine infinite silent loop — can the algorithm actually distinguish "expected polling" from "hallucinated no-op", or does it flag both identically (this matters for false-positive rate on real LLM code that legitimately polls).
3. **Clustering edge cases (Phase C)**: a very large batch (Module 02's multi-impl corpus can have up to 3 variants × many uids — does O(n²) pairwise comparison become a real bottleneck, and is there a documented n at which it does?), all implementations behaviorally identical (one giant cluster — does representative selection break any tie-breaking assumption?), all implementations behaviorally distinct (n singletons — does "singleton anomaly" reporting distinguish "this is a bug" from "this corpus legitimately has no duplicates", i.e. does the flag carry false urgency on small corpora?), representative selection tie (two implementations with identical minimum cyclomatic complexity — which wins, and is the tie-break deterministic/reproducible?).
4. **Model-checking edge cases (Phase D)**: what happens when neither `"error"`/`"abort"`/`"panic"` appears in a representative's atomic propositions (silently skips that check — is this distinguishable in output from "checked and passed"?), a loop-bound violation that's a false positive (the loop legitimately needs more than `loop_max` iterations for correctness, not a bug) vs. a true positive (an actual runaway loop) — can Phase D's structural trap-state check tell these apart, or does bounding-then-flagging conflate "unrolled past the bound" with "genuinely diverges"?
5. **Cross-module edge cases**: a Module-02 WIR that passes M02's own certificate gate but represents a program with a construct M03's lifter doesn't model (e.g. exceptions, `try/except` control flow — check whether `lifter.py` has any exception-edge handling at all, since Module 02's WIR schema is known from the sibling M02 sessions to model exception edges), a WIR from a program that never terminates in some branch (infinite recursion or an unbounded loop with `abort_on_low_confidence=False`) — does Phase A even complete, or hang/blow up memory building the LTS?
6. **C++-path-specific edge cases (only if Agent 1 finds it's meant to become the production path)**: what happens when `set_bpmn_tasks` is never called before `semantic_match` (uninitialized state), memory/lifetime issues given the header's own comment about "strictly manage the dict_ ownership and prevent Pybind11 memory leaks" (is there a realistic leak/crash path a fuzzer would find), whether `tarjan_tau_collapse` in C++ and the pure-Python SCC collapse in `stuttering_engine.py` are meant to be behaviorally identical — if so, is there any test proving they agree on the same input?

**Output format**: One table per category — Edge case | Illustrative WIR/LTS snippet (short) | Current handling (file:line or "no test found") | Failure mode if unhandled | Severity (thesis-critical / robustness / cosmetic).

---

### AGENT 4 — Evaluation Methodologist

**Mandate**: Design a concrete, executable, non-circular, **cross-module-aligned** evaluation plan for Module 03. Unlike Module 01 (which had to resolve corpus availability from scratch), Module 03's primary evaluation asset **already exists** — your job is to specify exactly how to wire it up, what's still missing, and how it should extend once Module 01's Phase 4 lands.

**Deliver, in order**:

1. **Clustering evaluation using the existing multi-impl corpus (build this first, it's ready today).** Specify exactly how to load `module_02_extract/eval/variants/manifest.json` + `normalized/*.py`, run each admitted program through Module 02's V3 pipeline to get a WIR, lift each to an LTS via Module 03's Phase A, cluster via Phase C, and score against the contract's §4 ground truth (base+admitted = one cluster; rejected_behavioral = singleton) using precision/recall on cluster-pair membership (a pair-counting metric, e.g. adjusted Rand index or simple pairwise precision/recall — pick one and justify it, since the contract itself warns clusters will often be size 1-3, which some clustering metrics handle poorly at small n). State explicitly which of the two Phase-A implementations (Python or C++) this evaluation should run against, and why (given Agent 1's finding on which one the tested pipeline actually is).
2. **Statistical requirements for the clustering figure**: given the manifest's actual current size (check it — the contract states "~11% admission rate" for Session C, so the number of admitted variants may be small; state the exact count found and whether it clears any meaningful power floor, mirroring the exact-binomial approach in `.claude/module01_e2e_plan.md` §4.4 and Module 02's own eval reports — if the corpus is too small for a defensible headline number, say so plainly rather than reporting a number without a confidence bound).
3. **Divergence-sensitivity evaluation (Phase B, independent of the multi-impl corpus)**: design a small **seeded-fault corpus** — pairs of LTS built from hand-written or lightly-mutated WIRs where one member of each pair has a genuine infinite silent loop injected and the other doesn't (and a control set of legitimate-polling pairs, per Agent 3 category 2) — and specify the pass/fail criterion (divergent pair never merges; polling pair does merge if otherwise equivalent). This is external ground truth by construction (the fault is seeded, not discovered by Module 03's own machinery), so it doesn't need Module 02's corpus.
4. **Model-checking (Phase D) evaluation — split into "today" and "post-M01-Phase-4"**:
   - *Today* (with only `from_reachability`/`from_loop_bound_check`): seed WIRs with known forbidden-label reachability and known loop-bound violations; measure detection/false-alarm the same three-figure way Module 01's and Module 02's plans do.
   - *Post-M01-Phase-4* (design now, build later, gated on that prerequisite): specify the concrete integration contract Module 03's `PropertyMonitor` needs — a new factory (e.g. `from_ltlf_automaton(spot_automaton)` or `from_property_suite(...)`) that ingests whatever Module 01's Phase 4 emits, and specify how the resulting Phase-D verdict would be checked against **external** ground truth — propose using IBM's `expected_output.sequence` (the same FLOW-BENCH label Module 01's plan already uses for its own gold labels, per `.claude/module01_e2e_plan.md` §4.2 item 3) as the non-circular anchor: for a given uid, does Module 03's end-to-end verdict (BPMN spec via M01 vs. one of M02's real/synthetic implementations) agree with whether that implementation actually matches IBM's labeled correct sequence?
5. **Three-way corpus alignment table**: for the shared FLOW-BENCH uid space, state precisely which artifact each module contributes per uid (M01: BPMN diagram + eventual property suite/automaton; M02: base program + WIR + multi-impl variants + admission verdicts; M03: clusters + Phase-D verdicts) and where each currently lives on disk (cite real paths) versus where it doesn't exist yet — this table is the concrete definition of "aligned with Module 01 and Module 02" the plan must satisfy.
6. **`comparison_mode` note**: state explicitly, per the multi-impl contract §7, that any evaluation step that reuses Module 02's differential comparator for cross-implementation checks must pass `comparison_mode="task_only"`, and why `strict` would bias the false-alarm figure upward for this specific use.

**Output format**: Numbered sections matching the 6 items above. Every recommendation must be concrete enough to hand to an implementer with no further research — file paths, corpus sizes actually found, metric choices justified, not "TBD."

---

### AGENT 5 — Architecture Critic

**Mandate**: Adversarial thesis-committee questioning, grounded in Agents 1–4's verified findings.

Must include:
- **The split-brain question, asked directly**: "You have two implementations of the same module that disagree on which algorithm to use for clustering and whether semantic matching happens at all — which one is 'Module 03' for the purposes of your thesis's results?" Force a committed answer (Synthesis Agent must pick one as primary and explicitly scope the other as future-work/prototype, or propose a unification plan — "both exist" is not an acceptable resting state for a defended claim).
- **"Your Docker container doesn't serve anything — how does Module 04 actually call Module 03 in your demo?"** Grounded in Agent 1's finding on the CLI-vs-service question; if `module_04_ui`'s in-container-invocation pattern is the real answer, is that documented anywhere as the intended architecture, or does it read as an unfinished integration?
- **"Your hash-based-clustering claim is checkable in one grep — you don't even have the function wired up."** (Novelty #3.) What's the honest correction: is it a claim to drop, a claim to implement, or a claim to reframe (hash as pre-filter, not replacement)?
- **"Phase D checks two hardcoded properties. Where's the spec-conformance verdict your Overview section says is the module's entire purpose?"** Force the honest scoping: today, Module 03 does not compare code against spec at all — it does behavioral clustering plus two generic safety checks. The "final judge" framing needs either a documented near-term path to Phase-D-consuming-M01, or an honest downgrade of the claim for this term's thesis.
- **"Two implementations of divergence-sensitive stuttering bisimulation — Python and (partially) C++ — do they even agree with each other on the same input?"** (Agent 3 category 6.) If untested, this is a reproducibility risk the moment someone runs the "wrong" one.
- Pick 2–3 of Agent 3's most damaging edge cases and phrase them as committee attacks.
- **Given Module 01's plan is itself unbuilt** (per `.claude/module01_e2e_plan.md`), is it defensible for Module 03's thesis chapter to describe "spec-vs-code equivalence checking" as a completed contribution this term at all, or does the honest framing become "behavioral clustering + safety-property checking of code, with spec-conformance checking designed but blocked on a sibling module's Phase 4"? What's the fallback thesis narrative if Module 01's Phase 4 doesn't land in time?

**Output format**: Numbered list. Do not soften the questions.

---

## SYNTHESIS AGENT — The E2E Implementation Plan (the actual deliverable)

Integrate Agents 1–5 into one document. Do not introduce novel ideas not grounded in the other five agents' findings; where findings conflict, state the conflict and resolve it with justification. This is the primary output.

Produce exactly these sections:

#### 1. Verified Current-State Scorecard
One row per novelty item (Agent 1's table), plus the independent sweep findings, plus an explicit **"which implementation is canonical"** decision (per Agent 5's forced question).

#### 2. Novelty & Hypothesis Register
Agent 2's table in full.

#### 3. Phase-Ordered Implementation Plan
For each fix/build item, in dependency order — structure this the same way `.claude/module01_e2e_plan.md`'s Synthesis §3 does, for direct comparability:
- **Phase 0 — Reconciliation** (prerequisite for everything else): resolve the split-brain (pick canonical path or define the division of labor precisely), decide the CLI-vs-service question explicitly, fix any Agent-1/Agent-3 correctness bugs found in the canonical path.
- **Phase A — Evaluation harness wiring**: the multi-impl-corpus clustering evaluation (Agent 4 item 1-2), the seeded divergence-sensitivity corpus (item 3) — both buildable today, no cross-module blockers.
- **Phase B — Phase-D-today hardening**: seeded reachability/loop-bound fault corpus and three-figure report (item 4, "today" half).
- **Phase C — M01 integration contract**: the `PropertyMonitor` extension point design (item 4, "post-M01-Phase-4" half) — spec precisely enough that whoever builds Module 01's Phase 4 and whoever extends Module 03's Phase D can work from the same contract independently.
- Each item: files to touch/create, dependencies, acceptance criteria, effort (S/M/L).

#### 4. Domain Edge-Case Risk Register
Top 10 from Agent 3, ranked by severity, each with a recommended fix and effort estimate.

#### 5. Executable Evaluation Plan (cross-module aligned)
Agent 4 in full, reconciled, plus the three-way corpus alignment table (item 5) reproduced as the section's centerpiece — this is the artifact that makes "aligned with Module 01 and Module 02" concrete and checkable.

#### 6. Top Thesis Vulnerabilities (ranked)
From Agent 5, each with: vulnerability, mitigation (code-or-wording), risk if unaddressed. Must include the split-brain risk and the "final judge judges nothing from the spec yet" risk explicitly, ranked appropriately relative to the domain edge cases.

#### 7. Next Implementation Session Plan
A concrete, ordered task list (not phases — actual tasks), each scoped to one sitting, referencing exact files, in the order a coding session should tackle them. Include, as an explicit early task, reading `.claude/module01_e2e_plan.md`'s T1–T7 list so the two modules' coding sessions can be sequenced sensibly (e.g. Module 03's Phase C contract-design work doesn't need to wait on Module 01, but its first real end-to-end spec-conformance test does).

---

## EXECUTION INSTRUCTIONS

1. Run Agent 1 first and alone — everything downstream depends on it. Then Agents 2–4 (present sequentially even if reasoned about in parallel). Then Agent 5. Then the Synthesis Agent.
2. Label each agent's output clearly.
3. Every factual claim about the codebase or the wiki must cite a file path (and line numbers where feasible), and — because this module has two implementations — must say **which implementation** the claim is true of. Unverified claims must be flagged as such, not stated as fact.
4. The Synthesis section must be directly actionable — specific enough to start coding from without further research.
5. After the full output, add a `## NEXT SESSION` section: a 5-bullet ordered list of first actions, each referencing exact files.

---

## WHAT NOT TO DO

- Do not write any code. Do not edit any files (including the wiki).
- Do not restate the wiki's novelty claims as fact without checking them against current source first, **and without checking which of the two implementations you're checking against** — this module's specific failure mode is claims that are true of one implementation and false of the other, presented as if there's only one implementation.
- Do not let the multi-impl corpus's admission verdicts, or any other ground truth generated by machinery independent of Module 03, get confused with ground truth generated by Module 03 checking itself — re-read the anti-circularity section above if unsure which is which for a specific proposed experiment.
- Do not treat `.claude/module01_e2e_plan.md` as something to re-verify from scratch — it's a sibling planning document from the same project; read it, cite it, build on its stated M01 findings, but focus this session's verification effort on Module 03 itself.
- Do not make vague recommendations — every recommendation must be specific enough to act on directly (concrete file paths, concrete metric choices, concrete corpus sizes actually found by inspection).
