# Module 03 — End-to-End Implementation Plan
**Session**: Fable 5 research+planning session, 2026-07-11, branch `develop` (HEAD `febd547`). No code or wiki edits made.
**Deliverable owner**: Module 03's owner (teammate) / a future coding session. Every claim re-verified against current source this session, with the module-specific discipline: each claim states **which implementation** (Python vs C++) it is true of. Sibling documents: `.claude/module01_e2e_plan.md` (M01 plan, cited not re-verified) and `docs/module02/11_multi_impl_corpus_contract.md` (M02→M03 contract, read in full).

**Headline empirical results (new this session)**:
1. **The tested pipeline was run end-to-end on its own documented ground truth** (M02's multi-impl corpus, contract §4) — M02 V3 extraction → Python lifter → clustering over the 13 uids with admitted variants: **pairwise precision 0.459, recall 0.630**. It fails in *both* directions at once: rejected_behavioral variants merge with their bases (20 FP pairs — over-merge), while bases split from their own *admitted* variants (10 FN pairs — over-split).
2. **Root causes isolated**: (a) task calls **never become transition labels** — the Python lifter labels edges only from guards (`lifter.py:284-319`), so a linear workflow lifts to an all-tau LTS (uid_1 base: 3 states, labels `{tau: 2}`) and behaviorally different programs look identical; (b) guard strings are compared as **opaque text** — `folder['name'] == None` vs `not (folder_name is not None)` are disjoint alphabets (uid_3, real corpus data); (c) the partition refinement is **finer than stuttering bisimulation** — a program with one extra silent step is judged NOT equivalent (hand-built tau-prefix/mid-tau tests both return False where the definition says True).
3. **The quality gate refuses 38/101 of Module 02's own clean base corpus** (`guard_success_rate` 0.0–0.667 with `abort=False`) — M03 reads `guard_success_rate` as a confidence score at 0.95; M02's certificate defines it as "fraction of branch conditions decomposed into CNF" (`certificate.py:19`), a different quantity that is legitimately low on loop-heavy code. Semantic contract mismatch, not a schema one.
4. **`pytest tests/` cannot even collect**: `tests/test_cpp_engine.py:1` is a bare path line (`/tests/test_cpp_engine.py`, not a `#` comment) — SyntaxError, whole-directory collection abort. `test_pipeline.py` alone: 37 passed. **No CI exists** (no `.github/workflows`), so nothing ever caught this. Same authoring-bug class as M01's `api.py`.

Reproduction commands in Appendix A.

---

## AGENT 1 — Implementation Verifier

### 1.1 The split-brain, confirmed and sharpened

Two parallel, non-interoperating implementations confirmed:

| | Pure-Python path | C++/Pybind11 path |
|---|---|---|
| Files | `lifter.py` (462L), `stuttering_engine.py` (415L), `clustering.py` (241L), `model_checker.py` (352L), orchestrated by `pipeline.py` (295L) | `lifter.cpp` (715L)/`lifter.hpp` (162L) → `vibecheck_lifter.cpython-312-x86_64-linux-gnu.so`, driven by `main.py` (80L) |
| Tests | `test_pipeline.py`, 37 tests, all 4 phases — pass when run alone | `test_cpp_engine.py` — SyntaxError at line 1; even if fixed, `sys.exit(0)` on ImportError (`:16`) makes it vacuously green anywhere the `.so` doesn't load (it is Linux/cp312-only; dev machine is Windows/cp313) |
| Docker | not the CMD | **is the CMD** (`Dockerfile:50`, `python3 -m src.main`) — a one-shot demo that runs 3 hardcoded semantic matches, sleeps 2s, exits |
| M04 integration | none | **M04's integration point**: `module_04_ui/src/app.py` `_check_equiv_engine()` imports `vibecheck_lifter`; the demo tab says "must be compiled — run inside the equiv-engine Docker container"; the info tab describes only the C++ core |
| Quality gate | yes (`lifter.py:170-206`) | **none** — `lift_to_lts` never reads a certificate |
| Loop unrolling | yes (`lifter.py:363-462`) | **none** |
| Semantic task matching | **never called** | `semantic_match` 3-tier cascade (`lifter.cpp:108-156`), calls `nlp_utils.compute_max_similarity` via Pybind11 (`:130-149`) |
| Clustering | pairwise O(n²) + Union-Find (`clustering.py:163-216`) | `compute_deterministic_hash` exists (`lifter.cpp:652-670`) — **no caller anywhere** |

**Owner intent (from the docs, as instructed)**: `docs/architecture/module_03_execution_plan.md` is explicitly a C++ roadmap — header says "Target: C++17 (SPOT Library), Python 3.10+ (Pybind11), Linux/WSL". It describes Phase D as a SPOT synchronous product against Module 01's `LTS_spec` + `Φ_spec` and a 3-tier EQI gate (GREEN/YELLOW/RED with guard-widening in YELLOW) — **neither exists in either implementation**. `docs/module_summery/Module_03_Equivalence_Engine.md` §6.2 lists "operational components" `m_code_lifter.py`, `verify_determinism.py`, `test_equivalence.py`, `main_role_c.py` — **none of these files exist anywhere in the repo** (recursive glob, 2026-07-11). So M03 has its own M01-style doc-vs-code gap layered on top of the split-brain: the docs describe a third codebase.

**CLI-vs-service: confirmed intentional-as-CLI, but unfinished-as-CLI.** No FastAPI/uvicorn anywhere in the module; M04 already treats it as an importable/in-container CLI (`app.py` health check = import check). However, the only entrypoints are a hardcoded demo (`main.py`) and a single-WIR pipeline (`pipeline.py` — see below), so "CLI" currently means "demo", not "invocable tool". Gap, not architecture.

**A finding the prompt didn't anticipate**: `pipeline.py`'s `run_pipeline` takes **one** WIR and clusters that WIR's own fragments — `lift()` returns `[__top_level__, fn1, fn2, …]` including **stub function definitions**, and Phase C clusters those together (`pipeline.py:125,189`). **No entrypoint in either path accepts N implementations of the same task** — the module's central use case (batch clustering of implementations) has no orchestrator, and nothing selects the `workflow` fragment out of a real M02 WIR (whose `functions` dict contains the stub defs too — verified live on `uid_1`: `functions` = `[GitHub_Repository__3_0_0__create_Repository, Jira_Issue__2_0_0__create_Issue, workflow]`).

### 1.2 Novelty inventory verdicts (5 items)

| # | Item | Verdict | Evidence | Actual state |
|---|---|---|---|---|
| 1 | Independent-automata spec comparison (wiki L33) | **DESIGN-ONLY-NO-CODE** (both paths) | `model_checker.py:54-118` — exactly two factories, `from_reachability`/`from_loop_bound_check`; no BPMN/LTLf/M01 reference in any `module_03_equiv` file; execution-plan §4 describes the SPOT product — unbuilt | Phase D today = 2 canned checks (`pipeline.py:224-247`): loop-bound trap scan + reachability of `"error"/"abort"/"panic"` **iff those strings happen to be transition labels**. Mirrors `.claude/module01_e2e_plan.md` Agent 5 pt 8 from the other side. |
| 2 | Divergence-sensitive stuttering bisimulation (wiki L34) | **SPLIT-IMPLEMENTATION; Python path PARTIALLY — divergence real, stuttering wrong** | Python: `stuttering_engine.py:258-320` (SCC + backward propagation — correct on hand-built tests); refinement `:324-415` **fails textbook stuttering equivalence** (tau-prefix and mid-tau pairs judged NOT bisimilar — empirical, Appendix A). C++: `refine_blocks` (`lifter.cpp:462-553`) is a different algorithm (tau-SCC collapse + topological closure) — plausibly closer to correct, **no parity test exists**, `.so` not runnable on the dev machine | The safety half (divergence) works; the usability half (absorbing benign silent steps — the wiki's entire selling point for LLM variation) does not, in the tested path. |
| 3 | Hash-based clustering (wiki L35) | **SPLIT + claim false as stated** | `clustering.py:163-198` is O(n²) pairwise; `compute_deterministic_hash` only in C++ (`lifter.cpp:652-670`), zero callers; and it is `std::hash<std::string>` formatted as 16 hex chars — **not SHA-256** as `lifter.hpp:72-77` claims, not stable across platforms/STL implementations | The tested path contradicts the wiki claim outright; even the untested path's hash is mislabeled and unwired. |
| 4 | Parallel-gateway abstraction (wiki L36) | **DESIGN-ONLY-NO-CODE** (both paths) — prompt's open question resolved | Full read of `lifter.py` and `lifter.cpp`: no gateway-type-specific handling anywhere (node `type` is stored as metadata, never branched on); `DEMO_WIR` has only an XOR-style gateway (`pipeline.py:51`); execution-plan §5.1 describes the k!-interleaving abstraction — unbuilt | Same status as its M01 twin (M01 plan item 10), and same recommendation: descope or build a synthetic AND corpus. |
| 5 | Bounded equivalence checking for loops (wiki L37) | **CONFIRMED-IN-CODE (Python path only)** | `LifterConfig.loop_max=3` (`lifter.py:100`), unrolling + `loop_exceeds_bound_error` trap (`:363-462`), tests exercise it (`test_pipeline.py:250-282`) | Real, but with a semantic caveat Agent 3 §3.4 details: the trap conflates "exceeded the analysis bound" with "genuinely divergent", and the bound is a config default — **not** "taken from the BPMN diagram" as the wiki says (no BPMN input exists). C++ path has no unrolling at all. |

### 1.3 Independent sweep (file:line, with which-path tags)

- **[tests] `test_cpp_engine.py:1`** — bare `/tests/test_cpp_engine.py` line, SyntaxError; `pytest tests/` aborts collection entirely (verified: "1 error during collection"). The suite is only green as `pytest tests/test_pipeline.py`. **No CI workflow exists in the repo**, so nothing enforces even that.
- **[Python] Task-call observability gap** — `_create_transitions` derives labels only from `edge.guard/condition` (`lifter.py:309-319`); node `code` (which holds the calls, e.g. `issue = Jira_Issue__2_0_0__create_Issue()`) never contributes a label. Verified: uid_1 base `workflow` lifts to 3 states with labels `{tau: 2}`. This is what the C++ path's `semantic_match` was designed for and is exactly the wiring gap the prompt flagged — with its blast radius now measured (headline #1).
- **[Python] Constant fallback label** — every unresolvable guard becomes the *same* observable label `unknown_unresolved_guard` (`lifter.py:359`, despite the docstring's "unique label identifier" at `:328`); two different unresolvable guards, or two different programs' unresolved guards, are indistinguishable — verified over-merge on a hand-built pair, and the label appears in real corpus lifts (uid_3 variants).
- **[Python] Guard labels are raw strings** — no canonicalization; `approval == None` vs `not (not approval)` (uid_31, real data) are unrelated symbols. Predicate paraphrase ⇒ non-equivalence.
- **[Python] Gate miscalibration** — `_check_quality_gate` treats `guard_success_rate` as confidence at 0.95 (`lifter.py:186-196`); M02 defines it as CNF-decomposition fraction (`module_02_extract/src/ast_extractor/certificate.py:19,128`) and its own abort criterion is `node_coverage < 0.95` (`:44`). Result: 38/101 clean bases refused (measured). The M02→M03 interface is schema-compatible (verified live — `run_v3_pipeline` output lifts with no KeyError; `DEMO_WIR`'s shape matches current schema) but **semantically miscalibrated**.
- **[Python] Loop-body over-approximation** — `_apply_loop_unrolling` computes the "loop body" as *everything forward-reachable from the loop node* (`lifter.py:381-390`), including post-loop nodes; benign for the corpus shapes seen, fragile for loops followed by branches.
- **[Python] Phase-D "not applicable" = "PASS"** — `pipeline.py:241-247` runs reachability checks only if `"error"/"abort"/"panic"` is in `atomic_propositions`; a run where the check never fired is indistinguishable in the summary from one where it passed.
- **[Python] `node["id"]` KeyError** on a dict node without `id` (`lifter.py:268`) — no schema validation before access; unknown node `type`s silently become `"block"` (`:266,271`).
- **[C++] `compute_deterministic_hash`**: `std::hash`, 64-bit, implementation-defined — the "SHA-256 signature" doc string (`lifter.hpp:72-77`) is false; hashes are not comparable across platforms or STL versions, which matters for any cached/cross-machine clustering.
- **[C++] every guard goes through task-name matching** — `lift_to_lts` calls `semantic_match(guard)` on each labeled edge (`lifter.cpp:246`), conflating guard predicates with action names; a guard like `approved` could Levenshtein-match a BPMN task. Tier-2 threshold ≤2 on normalized names is dangerous for short names (`check_in`/`check_out` → distance 2 → cross-match).
- **[C++] unreachable-state pruning is a TODO** (`lifter.cpp:283-285` — reachable set computed, never used); deadlock detection prints to `stderr` and continues (`:291-297`).
- **[C++] `semantic_match` before `set_bpmn_tasks`** returns `"unlabeled_task"` (`lifter.cpp:109`) — safe, not a crash.
- **[both] no parity test** — nothing ever runs the same WIR through both paths and compares (prompt's Agent 3 cat-6 question: unanswered by any artifact in the repo).
- **[hygiene] `src/__pycache__` `.pyc` files and the 897KB Linux/cp312 `.so` are committed to git** — binary artifacts in source control.

---

## AGENT 2 — Novelty → Hypothesis → Falsification Mapper

| # | Claim (wiki cite) | Falsifiable hypothesis | Testable? | Risk flag | Minimum experiment — and result where already run |
|---|---|---|---|---|---|
| 1 | Independent-automata spec comparison, "first framework" for BPMN-spec vs LLM-code (wiki L33) | **H1**: Given M01's spec automaton/properties and a code LTS for the same uid, M03's Phase-D verdict agrees with IBM's `expected_output.sequence`-derived correctness label at ≥ pre-registered rate. | **N today — needs-prerequisite** (M01 Phase 4 unbuilt per `.claude/module01_e2e_plan.md`; no ingestion point in M03). The "first framework" half is scholarly positioning, not falsifiable. | needs-prerequisite | Design now, run post-M01-Phase-4: per-uid agreement of end-to-end verdict vs IBM-label (Agent 4 §4.4). Until then, any thesis sentence must say "designed, blocked on sibling module". |
| 2 | Divergence-sensitive stuttering bisimulation absorbs benign silent variation while refusing divergent merges (wiki L34) | **H2a** (divergence): an LTS with a reachable silent cycle never merges with one without. **H2b** (stuttering): two LTS differing only by finite silent steps always merge. | **Y — both already tested** | none for H2a; **H2b is falsified as implemented** | Hand-built pairs (Appendix A): H2a **holds** (divergent-vs-not → False, correctly). H2b **fails** — tau-prefix pair and mid-tau pair both judged NOT bisimilar by `stuttering_engine.py`. Fix experiment: after Phase-0.4 rewrite, both micro-tests plus the corpus FN pairs (uid 2/3/31 admitted variants) must flip to equivalent. |
| 3 | Hash-based clustering avoids full pairwise comparison (wiki L35) | **H3**: for every corpus batch, clusters from `compute_deterministic_hash` on the minimized quotient are set-identical to pairwise-bisimulation clusters. | **Y in principle**, only in the C++ path, only on Linux | **claim-should-be-corrected** | The honest correction: a hash of a *canonical minimized quotient* can be exact only if quotienting is correct (item 2's bug says it isn't, in the tested path) and label identity is stable — but BDD ids and `std::hash` are process/platform-local, so "identical hash ⇒ equivalent" holds at best within one process. Correct claim: *hash as an exact-match fast path / pre-filter inside one run; pairwise checks remain for non-identical hashes*. Experiment (post-unification): run both on the multi-impl corpus, report agreement + speedup. |
| 4 | Parallel-gateway abstraction avoids k! interleavings (wiki L36) | **H4**: for AND-block WIRs, verdicts with abstraction = verdicts without, at ≥2× state-count savings. | **Y in principle** — no code, and **no AND construct exists anywhere in the shared corpus** (M01 plan: 0 `parallelGateway` in all 100 FLOW-BENCH diagrams; `DEMO_WIR` has none; the Python workflow corpus has no fork/join shape) | **tautology-adjacent + needs-prerequisite**: code-side parallelism would first need to exist in the WIR at all | Descope (recommended, matching the M01 plan's identical call on its twin claim), or build a 10-example synthetic AND-WIR corpus and demonstrate; without that it is future-work text. |
| 5 | Bounded equivalence checking with predictable cost (wiki L37) | **H5a**: two loops with identical bodies and bounds ≤ loop_max are equivalent; differing observable iteration counts ≤ loop_max are distinguished. **H5b**: a loop that legitimately needs > loop_max iterations is *not* reported as a spec violation (vs. a genuinely divergent loop, which is). | **Y** (Python path) | H5b currently fails by construction: the trap state is typed `"error"` (`lifter.py:443-447`) and Phase D counts any such state as a violation (`model_checker.py:231-242`) — "analysis bound exceeded" and "runaway loop" are the same verdict | Seeded loop corpus (Agent 4 §4.4): k=2 vs k=2 same body → merge; k=2 vs k=3 → split; long-but-finite loop (k=10) vs `while True` — falsified if the k=10 program FAILs the same way the infinite one does. Today it does. |

**Positioning claims** ("first framework to...", wiki L33; "previously-unidentified vulnerability", L34): not falsifiable; survive only via related-work search. Divergence-sensitive stuttering/branching bisimulation is textbook (Groote–Vaandrager — the module's own reference list cites the O(m log n) papers); the *application* framing is the only defensible novelty. Same treatment as the M01 plan's four "first-X" claims.

---

## AGENT 3 — Edge-Case Auditor (LTS / bisimulation / clustering / model checking)

Severity: **T** = thesis-critical, **R** = robustness, **C** = cosmetic. Rows state which implementation they concern.

### 3.1 Lifting (Phase A — Python path unless noted)

| Edge case | Current handling | Failure mode | Sev |
|---|---|---|---|
| Task-call actions (every real WIR) | Never lifted to labels (`lifter.py:309-319`); only guards observable | Linear workflows → all-tau LTS → behaviorally different programs equivalent. **Measured: 20 FP pairs on the ground-truth corpus** | **T** |
| WIR with zero nodes / empty | `lift` returns `[]` with a warning (`:163-165`); pipeline then clusters an empty list | Graceful, but Phase D silently has nothing to check — no distinct "empty input" status | R |
| Node dict without `id` | `node["id"]` KeyError (`:268`) | Crash with raw traceback; no schema validation | R |
| Unknown node `type` | Defaults to `"block"` silently (`:266,271`) | Semantics of unmodeled constructs quietly flattened | R |
| Stub-function fragments in `functions` | All lifted as separate LTS; nothing selects `workflow` | Any batch orchestrator naively using `lift()` output clusters stub defs with workflows (this session's first pilot run did exactly that) | **T** (for the harness) |
| Recursion (direct/mutual) | Calls are not followed at all — each function is an isolated LTS | Terminates trivially; call structure (incl. recursion) simply invisible — same root cause as row 1 | **T** (same fix) |
| Loop guard unresolvable / unbounded | Unrolls to `loop_max` regardless; trap typed `"error"` (`:443-447`) | Bound-exceeded ≡ divergence in Phase D (see 3.4); `loop_max=3` is a config default, not BPMN-derived — wiki L17 says otherwise | **T** |
| Loop followed by post-loop branch | "Body" = everything forward-reachable from the loop node (`:381-390`) — over-approximate | Post-loop nodes classified into body; edge misclassification risk on loop+branch shapes; untested | R |
| Missing `certificate` / missing `guard_success_rate` | `cert={}` → `gsr` 0.0 → **rejected** at gate (`:179-196`) | Graceful, but conflated with "low-quality extraction"; no distinct error shape | C |
| Certificate gate semantics | `guard_success_rate < 0.95` → reject (`:186-196`) | **38/101 clean M02 bases refused** (measured) | **T** |
| C++ `lift_to_lts` | No gate, no unrolling, guards through `semantic_match` (`lifter.cpp:195-299`) | Same WIR produces structurally different automata in the two paths — unification prerequisite | **T** (if C++ stays) |

### 3.2 Divergence / bisimulation (Phase B — Python path)

| Edge case | Current handling | Failure mode | Sev |
|---|---|---|---|
| Finite tau-prefix / mid-tau difference (the canonical benign LLM variation) | Judged NOT bisimilar (`stuttering_engine.py:324-415`; empirical TEST1/TEST6 → False) | **Over-splitting: the module's core promise fails**; measured FN pairs on real corpus (uid 2/3/31) | **T** |
| Divergent vs non-divergent | Correctly distinguished (TEST3 → False); SCC + self-loop criteria (`:258-290`) + backward propagation (`:294-320`) | — works | — |
| Unreachable divergent SCC | Flagged divergent (TEST5) but does not corrupt initial-state comparison (F~G → True) | `divergent_states` counts include dead code — telemetry noise only | C |
| Symmetry | Partition-based on merged LTS (`are_bisimilar`, `:104-153`) — symmetric by construction (TEST7) | — | — |
| Legitimate polling loop vs hallucinated no-op | Both are silent self-loops → both divergent → both refused merge; **indistinguishable by design** | False positives on real code that legitimately polls; wiki L19's "harmless wait state" is exactly what gets flagged | R (honest-disclosure item) |
| Fixed-point iteration cap | `max_iterations = len(all_states)` (`:380`) | Sufficient in theory for splitting-only refinement; unproven — a stabilization assert is missing | C |
| Two engines, one truth | C++ `refine_blocks` is a different algorithm; no input ever run through both | Results depend on which binary runs — reproducibility risk | **T** (if C++ stays) |

### 3.3 Clustering (Phase C — Python path)

| Edge case | Current handling | Failure mode | Sev |
|---|---|---|---|
| Full-corpus batch (~285 LTS) | O(n²) ≈ 40k pairwise refinements | Feasible (small LTS) but minutes-scale; moot if clustering is per-uid (n ≤ 8), which the contract's ground truth implies — document the granularity rather than defending O(n²) at corpus scale | C |
| All identical / one giant cluster | Representative = min (cyclomatic, name) (`clustering.py:220-241`) — deterministic tie-break | — | — |
| All distinct (n singletons) | Every member flagged `singleton_anomalies` (`:130-134`) | "Anomaly" carries false urgency on small/diverse corpora — the contract itself warns clusters are size 1-3 | C |
| Equivalence-matrix transitivity | Union-Find merges via any True pair; sound iff the checker is correct — with the current checker's errors, one spurious True chains whole groups (measured: uid_8's two rejected variants ride into the base cluster) | Over-merge amplification | R (fixed by 3.2 fix) |
| `unknown_unresolved_guard` collision | Two programs with different unresolvable guards share an alphabet symbol (TEST8 → merged) | Cross-program over-merge on garbled guards | **T** (one-line fix) |

### 3.4 Model checking (Phase D — Python path)

| Edge case | Current handling | Failure mode | Sev |
|---|---|---|---|
| None of `error/abort/panic` in APs | Check silently skipped (`pipeline.py:241-247`) | "Checked-and-passed" indistinguishable from "not applicable" in the summary JSON | R |
| Loop needs > loop_max iterations legitimately | Trap typed `error` → FAIL under the loop monitor (`model_checker.py:231-242`) | Bound-exceeded conflated with divergence — false FAIL on correct-but-longer loops (H5b) | **T** |
| Monitor label semantics | Observable label with no matching monitor edge → monitor stays via tau self-loop (`:265-272`), *in addition to* matching transitions | Benign for reachability monitors; for richer monitors (Phase-C contract) this "may-observe" semantics is unsound — a documented completeness rule is prerequisite to `from_property_suite` | R→**T** (at M01 integration) |
| Trap states under non-loop monitors | Recorded but PASS possible; noted only in the free-text message (`:294-303`) | Structured verdict fields don't carry it | C |

### 3.5 Cross-module

| Edge case | Current handling | Failure mode | Sev |
|---|---|---|---|
| M02 WIR schema drift | Shape verified compatible today (live `run_v3_pipeline` → `lift()` works; `DEMO_WIR` matches current schema incl. certificate fields) | None now; the WIR *field* contract is implicit — the planned `12_` WIR contract doc (M02 docs-refresh session) is the right anchor | C |
| `guard_success_rate` semantics | Misread as confidence (3.1) | 38/101 clean inputs refused | **T** |
| Exception edges (`exception_type` on WIR edges) | Ignored — only `source/target/guard` read (`lifter.py:298-309`); M02 models exception control flow | try/except flow indistinguishable from plain flow; programs differing only in exception structure merge | R |
| Bookkeeping nodes | Contract: post-F1 WIRs have none — no M03-side filtering needed | — confirmed non-issue | — |
| Non-terminating branch | Lifting always terminates (bounded unrolling; calls not followed); BFS product over finite states | No hang path found in Phases A/B/D — genuine robustness positive | — |

### 3.6 C++-path-specific (relevant only if C++ becomes/remains a production path)

| Edge case | Current handling | Failure mode | Sev |
|---|---|---|---|
| `semantic_match` before `set_bpmn_tasks` | Returns `"unlabeled_task"` (`lifter.cpp:109`) | Safe | C |
| Levenshtein tier ≤2 absolute on normalized names | `check_in`/`check_out` → distance 2 → **wrong confident match** | Mislabeled actions poison equivalence; threshold must be length-relative | R |
| Guards fed to task matching | Every non-`true` guard through `semantic_match` (`:246`) | Guard predicates can match task names; predicates and actions conflated | **T** (fix at unification) |
| Memory/ownership | Copy/move deleted, shared_ptr bindings (`lifter.hpp:32-33`, `lifter.cpp:677-713`); registry-automaton AP pattern sound | Untested under repeated calls — needs a soak test if productionized | R |
| Python-vs-C++ tau semantics | Python: `tau`/`true` labels; C++: `bddtrue` or registered `tau/silent/_` APs (`:302-308`) | Label universes differ; a parity test needs a common serialization first | R |

---

## AGENT 4 — Evaluation Methodologist

### 4.1 Clustering evaluation on the multi-impl corpus — ready today, pilot already run

**Asset (verified counts)**: `module_02_extract/eval/variants/manifest.json` — 294 records; screen: 184 pass; admission: **20 admitted** (13 uids: 1,2,3,4,6,8,31,32,34,40,42,70,78 — 7 uids×1, 5×2, 1×3), **164 rejected_behavioral** (95 uids), 110 never-tested. 184 normalized `.py` on disk. Ground truth per contract §4: base + admitted = one cluster; each rejected_behavioral = singleton (merging one into the base cluster = over-merging evidence, the contract's own words).

**Wiring (build as `module_03_equiv/eval/cluster_eval.py`)** — the exact recipe this session executed:
1. Load manifest; group by uid; keep uids with ≥1 admitted; per uid take base (`module_02_extract/eval/corpus/uid_<uid>.py`) + admitted + rejected_behavioral variants (`eval/variants/normalized/<variant_id>.py`).
2. WIR per program via `module_02_extract/src/ast_extractor/pipeline.py::run_v3_pipeline(source)` (put `module_02_extract/src` on `sys.path` and import as `ast_extractor.*` — no package collision with M03's `src`).
3. Lift via **the Python path** (`WIRLifter().lift(wir)`) and **select the `workflow` fragment by name** — not `lts_list[0]`; the functions dict contains stub defs (this session's pilot #1 accidentally clustered stubs — bake the selection rule in).
4. Cluster per uid with `BehavioralClusterer(StutteringEngine())`; score **pairwise precision/recall** on same-uid pairs (gt-same = neither member is rejected).
5. Emit per-uid table + totals to `module_03_equiv/eval/reports/cluster_eval.md`.

**Which implementation**: the **Python path** — tested, orchestrated by `pipeline.py`, and the only one runnable on the dev machine (the `.so` is Linux/cp312). The C++ path enters evaluation only after unification + a parity test (Synthesis Phase D).

**Metric justification**: pairwise precision/recall, not ARI/NMI — clusters here are size 1-4 (the contract's own warning); chance-corrected indices are unstable at that n, and the ground truth is explicitly asymmetric (an FP pair = over-merge *evidence*; an FN pair = missed benign variation), so the two error directions must stay separate figures, which ARI destroys.

**Pilot result (2026-07-11, this session — the "before" row for every future fix)**: 12 usable uids (uid 4 excluded: its *base* fails the quality gate), 52 scored pairs: **TP 17, FN 10, FP 20, TN 5 → precision 0.459, recall 0.630**. FN concentrated where guards exist (uid 2, 3, 31 — guard-string paraphrase + tau-prefix over-split); FP everywhere labels don't (linear uids 8, 32, 34, 40, 42, 70 — all-tau LTS).

### 4.2 Statistical requirements for the clustering figure

The corpus is **too small for a defensible headline rate** — state this plainly. 20 admitted variants → 27 gt-same and 25 gt-diff pairs, and pairs are correlated within uid, so binomial CIs are optimistic. At n=27 independent trials even 27/27 gives a one-sided exact 95% lower bound of only ~0.90 (cf. M01 plan §4.4: n=50 perfect → 0.942); correlated pairs are worse. **Report pilot-scale figures with a per-uid breakdown and a bootstrap-over-uids CI, labeled "pilot"; make no "≥X%" claim.** To earn a headline number: extend the variant pool with the existing Session-C machinery (`eval/gen_variants.py`, NIM key via env, raw-cache resumable — see `.claude/prompts/sonnet_module02_sessionC_prompt.md`), targeting ≥100 admitted variants (~5 per uid over ~20 uids); at that scale gt-same pairs exceed 150 and the M01-plan power table applies (n=200 → 0.80 power for a pre-registered ≥90% claim). Until then the honest deliverable is the before/after fix table, not a rate.

### 4.3 Divergence-sensitivity evaluation (independent of the corpus — external-by-construction)

Build `module_03_equiv/eval/divergence_corpus.py`: hand-written WIR pairs (WIR-level, not Python-level, so M02 is out of the loop and the fault is seeded, never discovered by M03 itself):
- **20 divergent pairs**: member B = member A + an injected reachable silent self-loop/tau-cycle. Pass: never merged. *(Current engine: expected to pass — divergence detection works.)*
- **20 benign-silent pairs**: member B = member A + one extra tau step (unguarded intermediate node). Pass: merged. *(Current engine: expected to FAIL — this is the H2b regression suite for the Phase-0.4 fix.)*
- **10 polling controls**: silent self-loop representing legitimate wait — indistinguishable from livelock by design today (Agent 3 §3.2). Pre-register the intended semantics: (a) polling-without-observable-heartbeat is *correctly* flagged (divergence-sensitivity is the point; the control set then documents the false-positive class honestly), or (b) polling must carry an observable heartbeat label in the WIR to be mergeable. Recommend (a) + disclosure; do not silently special-case.
Scoring: pass/fail counts per set; 40 seeded decisions is a regression gate, not a headline rate — same honesty rule as §4.2.

### 4.4 Phase-D evaluation — today and post-M01-Phase-4

**Today** (only `from_reachability`/`from_loop_bound_check`): `module_03_equiv/eval/phase_d_seeded.py` — 20 WIRs with a reachable `error`-labeled transition (must FAIL), 20 with it unreachable (must PASS), 10 loops at k < loop_max (must PASS), 10 at k > loop_max but finite (today: FAIL — H5b's known-broken case; pre-register the intended semantics before fixing), 5 genuine `while True` (must FAIL). Three-figure report (detection / specificity / false-alarm), M02-style.

**Post-M01-Phase-4 (design now, build later — the integration contract)**:
- **Input contract** (one doc, two consumers — this is M01 plan's "T5-prep" contract doc with M03's consumption schema added): M01 ships per uid `{uid, properties: [{id, tier: P0|P1|P2, formula: <LTLf in the contract grammar>, atoms: [task names]}], certificate}`. M03 adds `PropertyMonitor.from_property_suite(suite, task_matcher)` — for the safety fragment (`G(!x)`, `!a U b`, reachability) monitors are constructible in pure Python (extending the existing 2-state pattern); full LTLf needs the C++/SPOT path (execution-plan §4 is the blueprint) — scope the first deliverable to the safety fragment so it doesn't block on C++ unification. Prerequisite: fix the product construction's "may-observe" semantics (Agent 3 §3.4) before any richer monitor lands.
- **Task-name bridge**: BPMN task names ↔ WIR call labels via the ported `semantic_match` cascade (pure-Python Levenshtein with a length-relative threshold + the existing `nlp_utils.py`) — the C++ path's one unique working asset, made load-bearing without requiring the `.so`.
- **External ground truth**: per uid, IBM's `expected_output.sequence` defines the correct call structure (same anchor as M01 plan §4.2 item 3). End-to-end agreement experiment: BPMN → M01 suite → M03 Phase D on (base program = should-PASS; M02 mutation-corpus programs with seeded defects = should-FAIL). Never use M03's own Phase-D output as its own ground truth.

### 4.5 Three-way corpus alignment table (the concrete definition of "aligned")

Per shared FLOW-BENCH `uid` (1–101):

| Artifact | Module | Where it lives today | Status |
|---|---|---|---|
| BPMN diagram | M01 (input) | **public**: `github.com/IBM/flow-bench` `data/output/uid_<uid>_output.bpmn` (100 files; uid 90 absent); to be vendored per M01 plan T2 | exists (external) |
| LTLf property suite / spec automaton | M01 (output) | nowhere usable — Phases 1-3 pre-Phase-0-fix unsound (M01 plan headline); Phase 4 unbuilt | **missing** |
| Base program | M02 | `module_02_extract/eval/corpus/uid_<uid>.py` (101 files) | exists |
| WIR per program | M02 | computed on demand via `run_v3_pipeline`; not cached to disk | exists (transient) |
| Multi-impl variants + admission verdicts | M02 | `module_02_extract/eval/variants/{normalized/*.py, manifest.json}` — 184 normalized, 20 admitted, 164 rejected_behavioral | exists |
| Clusters vs ground truth | M03 | **nowhere** — `module_03_equiv/eval/` does not exist; this plan's Phase A creates it | missing (buildable today) |
| Phase-D spec verdicts | M03 | nowhere — blocked on M01 property suite + `from_property_suite` | missing (blocked) |
| uid-level caveats | — | uid 90: no BPMN; uid 4 + 37 others: base refused by M03's gate today (fix 0.5); uids with admitted variants: 13 | — |

### 4.6 `comparison_mode` note

Any evaluation step that reuses Module 02's differential comparator for cross-implementation checks (e.g., re-verifying admission, or a behavioral tie-break) **must pass `comparison_mode="task_only"`** per contract §7: `strict` aligns on full trace lineage and was measured to inflate cross-implementation false alarms (0.25 → 0.10 when switched). Independent implementations legitimately differ in non-task-event internals; using `strict` in any M03-adjacent figure biases the false-alarm rate upward and double-counts exactly the benign variation M03 exists to absorb.

---

## AGENT 5 — Architecture Critic (committee attacks)

1. **"Two implementations disagree on the algorithm and on whether semantic matching happens at all — which one is 'Module 03' in your thesis?"** Forced answer (Synthesis §1): the **Python path is canonical** for every thesis result — tested, orchestrated, platform-portable. The C++/SPOT path is scoped as the Phase-D-future/performance engine; its one unique working asset (semantic matching) gets ported to Python. "Both exist" is not a defensible resting state: today the two would give different answers on the same WIR, with no parity test to even measure the disagreement.
2. **"Your Docker container runs a demo, prints, sleeps two seconds, and exits. How does Module 04 call Module 03 in the live demo?"** Today M04 *imports the C++ module in-process*, and its "online" health check means "the .so compiled" (`app.py` `_check_equiv_engine`) — while every tested behavior lives in the Python path the container never exercises. CLI-as-architecture is defensible only once a real batch entrypoint exists (Phase 0.6) and M04 invokes *that*.
3. **"Your clustering scored precision 0.46 on the corpus your own contract designates as ground truth."** Reproducible by an examiner in an afternoon from repo contents (Appendix A). Worse than either error alone: it over-merges the behaviorally-divergent (safety failure) *and* over-splits the benign (usefulness failure). No defense except the Phase-0 fixes and a committed before/after table.
4. **"The hash-based-clustering claim is checkable in one grep — the function has no caller, and it isn't even SHA-256."** Correct the claim (within-run fast path / pre-filter, Agent 2 item 3) or drop it. Any sentence containing "cryptographic" dies at `std::hash<std::string>` (`lifter.cpp:666`).
5. **"Phase D checks two hardcoded properties. Where is the spec-conformance verdict your Overview says is the module's entire purpose?"** Today Module 03 does behavioral clustering plus generic safety checks; **nothing derived from a BPMN diagram is ever checked**. Honest scoping: "spec-vs-code equivalence checking: designed (execution-plan §4), integration contract specified (this plan Phase C), blocked on Module 01 Phase 4" — fallback narrative mirrored to M01's (property-strings contract, M01 plan vulnerability #8).
6. **"Two implementations of the bisimulation — do they agree on the same input?"** Unknown: no parity test; the Python one demonstrably fails textbook stuttering cases; the C++ one can't run on the dev machine. Until Phase 0.4 + a parity suite, any equivalence number depends on which binary produced it.
7. **"Your quality gate refuses 38% of your own pipeline's clean inputs."** The 0.95 threshold reads M02's CNF-decomposition fraction as a confidence score. A live demo on a random FLOW-BENCH uid has a ~38% chance of M03 refusing the *correct base program*.
8. **"Run `pytest tests/` — it doesn't collect. Where's your CI?"** One malformed comment line has disabled the suite for anyone running tests the normal way, and no CI exists to notice. The 37 passing tests are real but reachable only by knowing which file to avoid.
9. **"An implementation that polls silently is flagged exactly like a hallucinated `while True: pass` — your divergence-sensitivity can't tell the feature from the bug it was built to catch."** Pre-registered semantics + disclosure required (§4.3).
10. **"Your docs describe operational components — `m_code_lifter.py`, `verify_determinism.py` — that are not in the repository."** The summary doc's "What We Have Done So Far" describes a third codebase. Same misrepresentation-risk class as M01's wiki gap (M01 plan vulnerability #3); relabel now.

---

## SYNTHESIS — E2E Implementation Plan

### 1. Verified Current-State Scorecard — and the canonical-implementation decision

Agent 1 §1.2 is the scorecard. **Canonical-path decision (recommended, pending owner ratification): the pure-Python path is Module 03 for all thesis results.** Rationale: it has the tests, the orchestrator, platform portability, and three of five novelties at least partially live. The C++ path contributes exactly one unique working asset (3-tier semantic matching — cheap to port: pure-Python Levenshtein + the already-present `nlp_utils.py`; `sentence-transformers`/`torch` are already in `requirements.txt`), one design blueprint (SPOT Phase D — future), and one unwired, mislabeled hash. Resolution is **port-and-freeze**: (i) port the matcher, (ii) keep C++ as the future full-LTLf Phase-D engine, (iii) no thesis number from it until a parity suite exists (Phase D.1). Not delete, not unify-now.

Compressed state: novelty 1 DESIGN-ONLY (both paths); 2 divergence-real / stuttering-broken (Python), untested (C++); 3 false as stated; 4 DESIGN-ONLY; 5 real-with-caveat (Python only). Sweep: uncollectable test dir, no CI, no batch entrypoint, no workflow-fragment selection, task-calls-never-labels, opaque guard strings, constant fallback label, gate refusing 38/101, Phase-D not-applicable≡PASS, docs describing nonexistent files. Empirical bottom line: **precision 0.459 / recall 0.630 against its own contract's ground truth.**

### 2. Novelty & Hypothesis Register

Agent 2's table stands. Load-bearing: H2b already falsified as implemented (fix, then re-run — the corpus FN pairs are the regression set); item 3 is correct-the-claim, not defend-the-claim; item 4 descope (0 parallel constructs anywhere in the shared corpus — matching the M01 plan's identical decision); H5b's bound-vs-divergence conflation needs pre-registered semantics before the fix.

### 3. Phase-Ordered Implementation Plan

**Phase 0 — Reconciliation & soundness (prerequisite for every claim).** Files: `module_03_equiv/src/*`, `tests/*`. No new deps.
- **0.1** Fix `tests/test_cpp_engine.py:1` (comment the path line; replace `sys.exit(0)` with `pytest.importorskip("vibecheck_lifter")` so skips are visible); add CI (or at minimum a documented `make test`) running `pytest module_03_equiv/tests`. Acceptance: `pytest tests/` collects; passes/skips honestly. Effort **S**.
- **0.2** **Task-call observability** (the single highest-leverage fix): derive an action label per node from its WIR `code`/AST metadata (callee name of the stub call) and emit it as the observable label on the node's outgoing transition(s), composing with guard labels. Coordinate with M02's owner: WIR gains an explicit `calls` field per node (schema addition → recorded in the `12_` WIR contract doc) vs M03 parsing `code` strings — prefer the schema field. Acceptance: uid_1 base workflow LTS carries its two stub-call labels; corpus FP pairs collapse (20 → target <3). Effort **M**.
- **0.3** **Guard canonicalization + unique fallback**: (a) normalize guard strings before use as labels (ast-parse → canonical form: `== None`→`is None`, quote normalization, double-negation elimination, operand ordering); (b) replace the constant `unknown_unresolved_guard` with a per-guard deterministic label (`unresolved_<sha1(raw)[:8]>`) at `lifter.py:359`. Full semantic guard equivalence (Z3) is out of scope this term — say so; note uid_31's `approval == None` vs `not (not approval)` still won't unify syntactically (known-open item; the 0.2 action alphabet dominates equivalence anyway). Acceptance: TEST8 no longer merges; uid_3 canonicalizable labels align. Effort **S–M**.
- **0.4** **Correct stuttering refinement**: replace `_naive_partition_refinement`'s signature scheme with a branching-bisimulation-correct algorithm (Groote–Vaandrager — the module's own reference list cites the O(m log n) papers; the C++ `refine_blocks` tau-closure design is the nearer starting point but must itself be validated). Acceptance: TEST1/TEST6 → True; TEST3 still False; corpus FN pairs from tau-structure flip to merged; divergence corpus (A.2) all green. Effort **M–L** (the algorithmic core — budget accordingly).
- **0.5** **Gate recalibration**: gate on `certificate.abort` + `node_coverage` (matching M02's own semantics, `certificate.py:44`); demote `guard_success_rate` to telemetry or a documented low threshold; surface the applied thresholds in output. Acceptance: 101/101 clean bases pass (Appendix A set). Effort **S**.
- **0.6** **Batch entrypoint + fragment selection**: `cluster_implementations(wirs: list[tuple[name, wir]]) -> ClusterResult` in `pipeline.py` (or new `batch.py`) — selects the `workflow` fragment per WIR (explicit rule; error if absent), lifts, clusters, checks representatives. This is what M04 should eventually invoke. Acceptance: §4.1 evaluation runs through this entrypoint. Effort **S–M**.
- **0.7** Phase-D honesty: `"not_applicable"` status per skipped check (`pipeline.py:241-247`); separate `bound_exceeded` from `divergence` in trap reporting per the pre-registered H5b semantics. Effort **S**.

**Phase A — Evaluation harness (new dir `module_03_equiv/eval/`; buildable today, parallel with Phase 0).**
- **A.1** `eval/cluster_eval.py` + `eval/reports/` per §4.1; commit this session's numbers as `reports/cluster_eval_baseline.md` (the "before" row). Effort **S–M**.
- **A.2** `eval/divergence_corpus.py` per §4.3 (20 divergent + 20 benign-silent + 10 polling pairs, WIR-level, seeded). Effort **S–M**.
- **A.3** Variant-pool expansion (optional, gate for any headline rate): grow admitted set to ≥100 via M02's Session-C machinery — belongs to M02's owner; this plan records the dependency (§4.2). Effort M (mostly API budget).

**Phase B — Phase-D-today hardening.**
- **B.1** `eval/phase_d_seeded.py` per §4.4-today (65 seeded WIRs, three-figure report). Effort **M**.
- **B.2** Loop-bound semantics: implement the pre-registered H5b choice (recommend: trap typed `bound_exceeded`; Phase D reports `INCONCLUSIVE(bound)` distinct from FAIL; genuine divergence is Phase B's job). Effort **S–M**.

**Phase C — M01 integration contract (design-complete now; code gated on M01 Phase 4).**
- **C.1** Author the M01→M03 property-suite contract doc jointly with M01's owner (single doc — this is M01 plan's T5-prep task plus M03's consumption schema from §4.4). Effort **S** (writing).
- **C.2** `PropertyMonitor.from_property_suite(...)` for the safety fragment (pure Python, extends the 2-state monitors; prerequisite: fix the product's "may-observe" semantics) + the ported 3-tier `semantic_match` (length-relative Levenshtein + `nlp_utils`) as the task-name bridge. Effort **M**.
- **C.3** End-to-end agreement experiment vs IBM sequence labels (§4.4) — harness skeleton against a hand-authored mock suite now; real run after M01 Phase 4. Effort **M**.

**Phase D — C++ path disposition (explicitly gated, lowest priority).**
- **D.1** Parity suite: common LTS serialization + same-WIR runs through both paths inside the Docker image; agreement report. Only after this may any C++ number appear anywhere. Effort **M**.
- **D.2** Hash-claim correction in docs/wiki (pre-filter framing, `std::hash` disclosure) — wording task, do with the wiki relabeling regardless. Effort **S**.

**Descoped**: parallel-gateway abstraction (novelty 4) — zero parallel constructs in the shared corpus, mirroring the M01 plan's descoping of its twin; future-work text only. Full-LTLf SPOT Phase D — behind C.2's safety fragment.

### 4. Domain Edge-Case Risk Register (top 10)

| # | Risk | Fix | Effort |
|---|---|---|---|
| 1 | Task calls never become labels → over-merge (20 FP pairs measured) | 0.2 | M |
| 2 | Refinement finer than stuttering equivalence → over-split (10 FN pairs measured) | 0.4 | M–L |
| 3 | Gate refuses 38/101 clean bases (gsr misread as confidence) | 0.5 | S |
| 4 | Guard strings as opaque labels (paraphrase ⇒ non-equivalence) | 0.3 | S–M |
| 5 | `pytest tests/` uncollectable + no CI | 0.1 | S |
| 6 | No batch entrypoint / no workflow-fragment selection (stubs clustered with workflows) | 0.6 | S–M |
| 7 | Constant `unknown_unresolved_guard` label → cross-program merges | 0.3 | S |
| 8 | Loop-bound trap ≡ divergence in Phase D (false FAIL on long-but-finite loops) | B.2 | S–M |
| 9 | Phase-D "not applicable" indistinguishable from PASS | 0.7 | S |
| 10 | Two engines, no parity test (reproducibility) | D.1 (or freeze C++) | M |

### 5. Executable Evaluation Plan (cross-module aligned)

§§4.1–4.6 in full; the three-way alignment table (§4.5) is the checkable definition of alignment. Build order: **(1)** A.1 `cluster_eval.py` + commit the 0.459/0.630 baseline — the instrument that measures every Phase-0 fix; **(2)** Phase 0.2/0.3/0.4/0.5 with the eval re-run after each (the M02 "experiment as instrument" pattern, third module in a row); **(3)** A.2 divergence corpus (regression-gates 0.4 against over-correction); **(4)** B.1 Phase-D seeded corpus; **(5)** C.1 contract doc with M01's owner. Honesty rules: no "≥X%" claim below the §4.2 floor; internal M03 outputs never count as ground truth; admitted/rejected verdicts come only from the manifest (independent execution-diff); `comparison_mode="task_only"` for any comparator reuse (§4.6).

### 6. Top Thesis Vulnerabilities (ranked)

| # | Vulnerability | Mitigation | Risk if unaddressed |
|---|---|---|---|
| 1 | Clustering scores ~coin-flip (0.459/0.630) on its own contract-designated ground truth — examiner-reproducible | Phase 0.2/0.3/0.4 + committed before/after table | Core-contribution credibility loss |
| 2 | Split-brain: results depend on which of two disagreeing implementations runs | §1 canonical decision (Python) + port-and-freeze + D.1 parity gate | Any number challengeable as implementation-dependent |
| 3 | "Final judge" checks nothing from the spec (Phase D = 2 canned checks; no M01 input) | Honest scoping wording + C.1/C.2 contract + safety-fragment monitors; fallback narrative pre-written | Overview claim collapses in the viva |
| 4 | Hash-based-clustering claim false as stated (unwired + `std::hash` ≠ SHA-256) | Correct to fast-path/pre-filter; fix doc strings; wiki relabel | One-grep committee kill |
| 5 | Gate refuses 38% of clean pipeline inputs | 0.5 | Live-demo failure in front of the committee |
| 6 | Docs describe files that don't exist (`m_code_lifter.py` etc.); wiki describes one coherent pipeline | Relabel summary doc §6.2 + wiki (implemented-Python / designed-C++ / not-in-repo) | Misrepresentation finding |
| 7 | Test suite uncollectable, no CI | 0.1 | "Do your tests pass?" — currently unanswerable honestly |
| 8 | Divergence-sensitivity flags legitimate polling identically to livelock | Pre-registered semantics + disclosure (§4.3) | Novelty #2 reframed as a false-positive generator |
| 9 | Corpus too small for any headline clustering rate (20 admitted) | §4.2 honesty rule + optional A.3 expansion | Statistically indefensible claim (M02's 21-sample lesson, third module in a row) |
| 10 | M01 dependency slip (Phase 4 unbuilt; M01 itself pre-Phase-0) | Fallback narrative: "behavioral clustering + safety checking; spec-conformance designed & contract-specified" — C.1 doc is the evidence | Thesis-chapter scope collapse late in the term |

### 7. Next Implementation Session Plan (ordered, one sitting each)

*(Early task per the mandate: read `.claude/module01_e2e_plan.md` §7 (M01's T1–T7). Sequencing: M03's T1–T6 below are fully independent of M01; M03-T7's contract doc should be co-authored the same week M01's team does their T5-prep; only C.3's real run waits for M01 Phase 4.)*

1. **T1** — Test/CI batch: fix `tests/test_cpp_engine.py:1` + `pytest.importorskip`; add CI running `pytest module_03_equiv/tests`; raise the tracked-`.so`/`__pycache__` question with the owner (S).
2. **T2** — `eval/cluster_eval.py` + commit `reports/cluster_eval_baseline.md` reproducing this session's 0.459/0.630 pilot (Appendix A recipe; uid-4 exclusion documented). The before-numbers, locked.
3. **T3** — Gate recalibration (0.5: `lifter.py:170-206`) + unique unresolved-guard labels (0.3b: `lifter.py:359`) + Phase-D not-applicable status (0.7: `pipeline.py:241-247`); re-run T2 → expect uid 4 restored (13 uids), zero clean-base refusals, FP unchanged.
4. **T4** — Task-call observability (0.2: `lifter.py:252-319` + decision memo with M02's owner on the WIR `calls` field); re-run T2 → expect FP ≈ 0; recall may *drop* further (more labels = more splitting) — that drop is the honest motivation for T5.
5. **T5** — Stuttering refinement rewrite (0.4: `stuttering_engine.py:324-415` + new micro-test file encoding TEST1–TEST8 from Appendix A); re-run T2 + A.2 divergence corpus → target precision ≥0.9 AND recall ≥0.9 on the pilot.
6. **T6** — Guard canonicalization (0.3a) + batch entrypoint & workflow-fragment selection (0.6); final T2 re-run = the thesis before/after table.
7. **T7** — Phase-D seeded corpus + loop-bound semantics (B.1/B.2); co-author the M01→M03 property-suite contract doc (C.1).
8. **T8** — Semantic-matcher port (C.2 prerequisite): pure-Python 3-tier matcher, length-relative Levenshtein, unit-tested against the C++ tier examples.

---

## NEXT SESSION

1. Hand this plan to Module 03's owner alongside `.claude/module01_e2e_plan.md` (cross-referenced siblings); get the Synthesis-§1 split-brain decision (Python canonical, C++ port-and-freeze) ratified before T4/T5 touch the algorithmic core.
2. T1: fix `module_03_equiv/tests/test_cpp_engine.py:1` (comment line) + `pytest.importorskip`; add `.github/workflows/` CI for `pytest module_03_equiv/tests`.
3. T2: create `module_03_equiv/eval/cluster_eval.py` from Appendix A's recipe (manifest → `run_v3_pipeline` → `WIRLifter` → per-uid `BehavioralClusterer`, `workflow`-fragment selection by name, pairwise P/R) and commit the 0.459/0.630 baseline report.
4. T3: `lifter.py:170-206` gate recalibration (abort + node_coverage, not guard_success_rate@0.95 — restores the 38 refused bases incl. uid 4) + `lifter.py:359` per-guard unique fallback labels.
5. Book the joint session with M01's owner for the shared property-suite contract doc (M01 plan T5-prep ≡ this plan C.1) — the one artifact both modules' Phase-4/Phase-D halves must agree on before either builds.

---

## Appendix A — Reproduction of the empirical claims (all run 2026-07-11)

```
tests:   cd module_03_equiv && python -m pytest tests/ -q
           → ERROR tests/test_cpp_engine.py (SyntaxError line 1) — collection aborted
         python -m pytest tests/test_pipeline.py -q  → 37 passed in 0.04s
         .github/workflows: does not exist

micro-tests (sys.path += module_03_equiv; src.lifter.LTS + src.stuttering_engine.StutteringEngine):
  TEST1 A: s0-tau->s1-a->s2  vs  B: t0-a->t1          → are_bisimilar = False  (stuttering equivalence says True)
  TEST2 identical copies of A                          → True  (ok)
  TEST3 C: c0-tau->c0, c0-a->c1  vs  D: d0-a->d1       → False (ok — divergence-sensitive)
  TEST4 label a vs label b                             → False (ok)
  TEST5 unreachable tau-self-loop f2: flagged divergent; F~G → True (init comparison unaffected)
  TEST6 s0-a->s1-tau->s2-b->s3  vs  h0-a->h1-b->h2     → False (stuttering equivalence says True)
  TEST7 symmetry A~B == B~A                            → True
  TEST8 two programs, both labeled 'unknown_unresolved_guard' → True (over-merge via constant fallback)

corpus pilot (manifest: 294 records; screen pass 184; admitted 20 / rejected_behavioral 164 / null 110;
  admitted uids [1,2,3,4,6,8,31,32,34,40,42,70,78]; per uid: base + admitted + ≤2 rejected;
  WIR via ast_extractor.pipeline.run_v3_pipeline (module_02_extract/src on sys.path);
  lift via WIRLifter(LifterConfig()); fragment = functions['workflow'];
  cluster via BehavioralClusterer(StutteringEngine())):
    uid 4 dropped — BASE fails gate (guard_success_rate=0.6667 < 0.95)
    per-uid: 1,6,8,32,34,40,42,70,78 → single cluster incl. rejected variants (over-merge)
             2,3,31 → base split from its own admitted variants (over-split)
    pairs: TP=17 FN=10 FP=20 TN=5 → precision 0.459, recall 0.630
    uid_1 base workflow LTS: 3 states, labels {tau: 2} — task calls never lifted to labels
    uid_3 alphabets: base ["folder['name'] == None", "not (folder['name'] == None)"]
                     qwen ['not (folder_name is not None)', 'unknown_unresolved_guard']
    uid_31: base ['approval == None', ...] vs qwen ['not (not approval)', ...] — opaque-string mismatch

gate sweep: run_v3_pipeline over all 101 eval/corpus/uid_*.py → 38 fail M03's gate
  (gsr 0.0–0.667, abort=False in all cases; uids 4,5,7,9,10,13,14,...,101)

M04 integration: module_04_ui/src/app.py _check_equiv_engine imports vibecheck_lifter (C++ path);
Docker CMD (module_03_equiv/Dockerfile:50): python3 -m src.main (one-shot demo, time.sleep(2), exit)
phantom doc files: m_code_lifter.py / verify_determinism.py / test_equivalence.py / main_role_c.py — absent from repo
```
