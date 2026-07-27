# Fable 5 — Module 02 Round 2: Implementation, Evaluation & Edge-Case Hardening
# Copy-paste this entire prompt into a new Fable 5 session with file access to this repo.
# Do NOT summarize or abbreviate it before starting — the full context is required.

---

## SESSION MANDATE

You are running a **research and design session only** — a continuation of a prior R&D pass. **No code will be written. No files will be edited.** The deliverable is a verified, actionable brief covering (1) implementation completeness, (2) evaluation rigor, and (3) edge-case coverage for Module 02 of a formal-verification research system, precise enough to drive the next implementation session without further research.

**Critical ground rule, learned the hard way in the prior session**: the prior round's brief contained claims (about a dataset's contents, and about a specific bug's location/mechanism) that turned out to be wrong on inspection of the actual source. **Do not trust any claim below — including claims of "DONE" — without re-verifying it against the current source in this repo first.** Every agent below must open and read the actual file before asserting anything about it. Cite file path + line range for every factual claim about the code.

You will operate as **five concurrent sub-agents**, each with a distinct mandate, followed by a **Synthesis Agent**. Read the full brief below before beginning any analysis.

---

## PROJECT BRIEF

**System**: VibeCheck — Post-Hoc Formal Verification of LLM-Generated Python Code Using BPMN-Derived Temporal Specifications
**University**: Faculty of IT, University of Moratuwa — FYP, Group 18 (Epsilon)
**Your module**: Module 02 — Verified IR Extraction (sole developer; Module 01 and Module 03 belong to teammates and are out of scope for edits — read-only if referenced)
**Repo layout** (monorepo, post-modularization as of this session): `module_02_extract/src/{ast_extractor,z3_sym_engine,dynamic_tracer}/` (each now a package, not a single file), `module_02_extract/src/main.py` (FastAPI), `module_02_extract/tests/` (105 tests, all passing as of last run).

### Pipeline Architecture (Dual-Track, 5-Stage)

```
Track A (Spec):   BPMN 2.0 XML ──► Module 01 ──► M_spec + LTLf Props ──────────┐
                                    (Stage S1)                                    ▼
                                                                            Module 03 ──► Verdict
                                                                            (Stage S5)    ▲
Track B (Code):   LLM Python Code ──► Module 02 ──► WIR + M_code ───────────────┘
                                       (Stages S3-S4)
```

### Module 02 Current Design (VERIFY, do not assume)

**Input**: LLM-generated Python code (+ optional BPMN spec for diagnostics, currently unused beyond narrative)
**Output**: Verified WIR (Workflow Intermediate Representation) JSON + Multi-Modal Certificate (V1+V2+V3)

- **V3 — Static AST extraction** (`ast_extractor/` package: `cfg_extractor.py`, `dominators.py`, `guards.py`, `data_layer.py`, `models.py`, `schema.py`, `pipeline.py`, `helpers.py`, `certificate.py`) — CFG → dominator tree → CNF-flattened guards → WIR JSON.
- **V2 — Symbolic validation** (`z3_sym_engine/` package: `registry.py`, `evaluator.py`, `tracer.py`, `concolic.py`, `pipeline.py`, `safe_exec.py`) — Z3 SMT solver, k-bounded loop unrolling, quasi-concolic execution. Certificate emission is `BoundedConcolicEngine._emit_certificate` in `concolic.py`.
- **V1 — Dynamic validation** (`dynamic_tracer/` package: `collector.py`, `comparator.py`, `composer.py`, `interpreter.py`, `pipeline.py`, `randomized.py`, `safe_exec.py`) — runtime tracing (migrated toward `sys.monitoring`, PEP 669, with a `sys.settrace` fallback per prior session), LCS trace alignment, randomized differential testing with a configurable run count.
- **Certificate composition** (`dynamic_tracer/composer.py`) — formula was `combined = 1 - (1-v1)(1-v2)(1-v3)`, threshold 0.95 → PASS.
- **API**: FastAPI `POST /verify` in `main.py`.

### State carried in from the prior R&D session (VERIFY EACH LINE BELOW — treat as hypotheses, not facts)

The prior session (branch `fix/mod2/phase1-symbolic-hardening`, since merged) reported these as done:
1. Z3 "double-reset" — reported fixed via incremental `push()/pop()` solving in what is now `z3_sym_engine/concolic.py` (was a monolithic `z3_sym_engine.py`).
2. V1 `sys.settrace` → `sys.monitoring` runtime path — reported added to `dynamic_tracer/collector.py` (was `WIRTraceCollector`), settrace kept as fallback, gated by a parity test.
3. V2 container coverage — reported improved (branch coverage list 1→4 edges) via seeding non-empty containers + concrete `len()`, but the prior session's own notes flagged an **unresolved follow-on**: the confidence formula in `_emit_certificate` was said to ignore branch/coverage diversity for pure-container functions, keeping confidence at 0 even when coverage improved.
4. 5 `NotImplementedError` stubs existed in the old `z3_sym_engine.py` — an initial scan this session found only 2 remaining, in what are now `z3_sym_engine/tracer.py` and `z3_sym_engine/evaluator.py`. **Verify count and exact nature of each remaining stub.**
5. `merge_states()` (QCE state merging) — reported implemented but never invoked; an initial scan this session found the method defined in `concolic.py` but no call site anywhere in `src/`. **Verify.**
6. V1 run count — reported previously as a fixed `n=50`; an initial scan this session found `randomized.py` / `pipeline.py` now default to `n_runs=20` (still fixed, not adaptive). **Verify which is current and whether adaptivity (sample-to-CI-target) was ever implemented.**
7. `/verify` partial-failure contract — reported as a known gap (Critic-Q10); an initial scan this session found `main.py`'s `verify()` still uses a single broad `except (..., Exception)` catch that collapses everything to an all-zero `passed: false` response, with no typed per-layer `{OK, SKIPPED(reason), ERROR(reason)}` status. **Verify whether this was addressed anywhere else (e.g. inside `_run_verification`) before concluding it's still open.**
8. `Module01Adapter`, `SelfConsistencyAdapter`, `ValidationConfig`, `eval/` (mutation corpus / golden set) — reported as not started. An initial scan this session found no `adapters/` directory, no `ValidationConfig` class, and no `eval/` directory anywhere in the repo. **Verify.**
9. Certificate combination formula — reported unchanged (`1-(1-v1)(1-v2)(1-v3)`, no correlation discount, no WIR-independent layer). **Verify** by reading `composer.py` directly.
10. Test suite — 105 tests reported passing as of the last run in this repo (`module_02_extract/tests/`, via `python -m pytest -q`). **Re-run it yourself if you have shell access; otherwise treat this figure as unverified.**

### Known Thesis Vulnerabilities (from prior Architecture Critic pass — re-verify severity against current code, don't just restate)

| Vulnerability | Examiner attack |
|---|---|
| Independence assumption | V1/V2/V3 all reason about the same WIR from the same AST extractor; a systematic extractor bug causes correlated failures the product formula can't see. |
| Statistically thin eval set | The public FLOW-BENCH eval split (21 samples) cannot support a "≥95% detection" claim at any outcome (95% one-sided lower confidence bound at 21/21 is only ~0.867). |
| Pre-declared 0.95 threshold | Chosen before measurement, then measured against — circular unless calibrated on a disjoint split. |
| QCE "three defenses" overclaim | Only k-bounded unrolling is live; state-merging (`merge_states`) is unused; concolic refinement is thin. |
| Container type blind spot | `list`/`dict`-bearing workflows historically fall back to V1-only in V2; recent work improved *coverage* but the *confidence credit* for that coverage is disputed (see item 3 above). |
| WIR as shared upstream artifact | Nothing validates the WIR itself before all three layers trust it. |
| `sys.monitoring`/`sys.settrace` CPython-only scope | Migrating tracer backends doesn't remove the CPython dependency, and per-line `f_locals` reads may erase most of PEP 669's overhead benefit. |
| M01 → M02 coupling | M02 accepts a BPMN spec input but (per prior audit) only feeds it to a not-yet-built narrative/explainer layer — never used to validate anything. |
| Fixed V1 run count | Whatever the current default is, it is not derived from a coverage/CI argument. |
| FastAPI partial-failure contract | See item 7 above. |

### Dataset situation (established in prior session, treat as fact unless you find contrary evidence)

The **public** IBM FLOW-BENCH does **not** contain executable LLM Python implementations or correctness (buggy/correct) labels — records are `{utterance, prior_sequence, prior_context, bpmn-ref, expected_output}` where "Python" is a constrained-syntax IR (assignments, if, for/while, calls), used for an NL→workflow generation task. Any claim of "101 executable triplets, 80/20 split, with correctness labels" is a **group-derived/augmented artifact**, not the published dataset — confirm its actual provenance with the team if you need to rely on it; do not assume it exists as described.

---

## AGENT ROLES

Execute all five in the order given. Label each output clearly with a `## AGENT N — <name>` header.

---

### AGENT 1 — Implementation Verifier

**Mandate**: Ground-truth every hypothesis in the "State carried in from the prior R&D session" section against the actual current source. This agent's output is the factual foundation the other four agents must build on — do not let stale claims propagate.

For each of the 10 numbered items above:
1. Open the relevant file(s) and quote the actual current code (file path + line numbers).
2. State: CONFIRMED / PARTIALLY TRUE / FALSE, with the specific discrepancy if not confirmed.
3. If FALSE or PARTIALLY TRUE, state what the actual current behavior is.

Also do an independent sweep for anything **not** covered above:
- Any other `NotImplementedError`, `TODO`, `FIXME`, `pass  # stub`, or bare `raise NotImplementedError` in `module_02_extract/src/`.
- Any function with no test coverage that a core pipeline path (`/verify`) can reach.
- Any place where an exception is silently swallowed (`except: pass`, `except Exception: pass`, broad excepts that discard the error).

**Output format**: Table of the 10 items (Item | Verdict | Evidence | Actual state), followed by the independent sweep findings as a bullet list with file:line citations.

---

### AGENT 2 — Edge-Case Auditor

**Mandate**: Module 02 must extract a faithful WIR and certify correctness for **arbitrary LLM-generated Python** implementing FLOW-BENCH-style workflows (sequential steps, branching, loops, container-bearing state, calls to a task API). Systematically enumerate the Python-language and workflow-semantic edge cases that could break V3 (AST extraction), V2 (Z3 symbolic), or V1 (dynamic tracing) — and check, per edge case, whether current code handles it, degrades gracefully, or fails silently/loudly.

**Categories to cover** (for each: does a current test exercise it? if you can construct a small Python snippet illustrating it, do so; state the failure mode if unhandled):

1. **Control flow**: `try/except/else/finally`, `with` statements, `break`/`continue` inside nested loops, early `return` from inside a loop or conditional, `while True` with internal break, recursion (direct and mutual), generators/`yield`, `match`/`case` (structural pattern matching), nested function definitions/closures.
2. **Data/state**: mutable default arguments, aliasing (two names bound to the same list/dict), in-place mutation vs rebinding, `*args`/`**kwargs`, unpacking assignment (`a, b = f()`, starred targets), global/nonlocal state mutation across calls, dataclasses/namedtuples as workflow state.
3. **Symbolic-execution-specific (V2)**: unbounded/dynamically-sized loops (loop bound depends on runtime container length, not a literal), string operations feeding into a guard condition, floating-point comparisons in guards, integer division/modulo, calls to external/unmodeled functions inside a guard (what does the Z3 layer do — abstain? crash? assume-true?), exceptions raised *inside* a symbolically-explored branch.
4. **Dynamic-tracing-specific (V1)**: non-determinism in the traced program (e.g. reliance on `random`, `time`, dict iteration order pre-3.7 assumptions), side effects to external state (file I/O, network calls stubbed or not) that the differential tester can't safely re-run 20+ times, infinite loops or pathologically long-running code (is there a timeout/step-count guard? where?), multi-threaded or async code.
5. **Malformed/adversarial input**: syntactically invalid Python, code that imports disallowed modules (`os.system`, `subprocess`, `eval`), code with no discernible workflow structure at all (should `/verify` return RED, or crash?), extremely large/deeply-nested programs (does CFG/dominator computation degrade gracefully or blow up?).
6. **WIR schema edge cases**: workflows with zero gateways (pure sequential), workflows with unreachable code after an unconditional return/raise, workflows with a guard that's a compile-time constant (`if True:`), workflows where a task call site appears multiple times in different branches.

**Output format**: One table per category — columns: Edge case | Illustrative snippet (short) | Current handling (file:line if found, or "no test found") | Failure mode if unhandled | Severity (thesis-critical / robustness / cosmetic).

---

### AGENT 3 — Evaluation Methodologist

**Mandate**: The prior session designed a calibration protocol and power analysis but the underlying mutation corpus was never built (no `eval/` directory exists). Your job is to make the evaluation plan concretely executable, not just theoretically sound.

**Deliver**:

1. **Confirm or refute the dataset provenance question** (see Dataset situation above) if you have any way to check — otherwise flag it as the standing open item it is.
2. **Concrete mutation operator specification**: for the FLOW-BENCH-style workflow programs Module 02 targets, define a specific, enumerable set of semantic mutation operators (e.g. negate-guard, swap-branch-targets, off-by-one loop bound, drop-a-step, swap-create/update-call, corrupt-a-container-op) — each with a one-line description and an example before/after snippet. This list must be concrete enough that someone could implement a mutation-generator script directly from it.
3. **Statistical re-check**: given whatever the actual current test/eval corpus size is (check `module_02_extract/tests/` and any `inputs/` directory), restate the exact-binomial power analysis for an E1-style "≥95% bug detection" claim, and state plainly whether the current corpus (if any exists beyond unit tests) clears the N≈30–40 floor.
4. **Threshold calibration protocol**: step-by-step, CALIB/EVAL split, pre-registered operating-point rule (e.g. Youden's J), with the exact non-circular thesis wording to use.
5. **E2/E3 framework**: metric definition for structural WIR accuracy (micro-F1 over nodes/edges) and for certificate-vs-correctness correlation (Pearson r on a *continuous* correctness label such as mutation-kill fraction, not a binary one) — with sample-size requirements.

**Output format**: Numbered sections matching the 5 items above. Be concrete — every recommendation must be specific enough to hand to an implementer with no further research.

---

### AGENT 4 — Architecture Critic

**Mandate**: Re-run the adversarial thesis-committee questioning, but grounded in Agent 1's verified current state (not the prior session's claims). Generate the hardest current questions — some may be the same as before if unresolved, some may be new because of what changed.

For each question: **Q** (the adversarial question) → **CURRENT** (what the verified-current design actually does, citing Agent 1's findings) → **FIX** (concrete architectural change, scoped claim, or documented limitation).

Must include, updated for current state:
- The independence assumption (still open per Agent 1?).
- The container-confidence gap (Agent 1 item 3 — is it actually still 0-credit, or was it fixed?).
- The QCE overclaim (is `merge_states` still dead code?).
- The threshold circularity.
- The tracer backend choice and its CPython-only scope.
- The `/verify` partial-failure contract (Agent 1 item 7).
- Any **new** question that emerges from Agent 2's edge-case audit — pick the 2–3 most damaging unhandled edge cases and phrase them as committee attacks.
- The M01 dependency — given Module 01 is confirmed still a stub owned by a teammate, is the "Module01Adapter" fix from the prior session's synthesis even implementable this term? If not, what's the fallback thesis framing?

**Output format**: Numbered list. Do not soften the questions.

---

### AGENT 5 — Synthesis Agent

**Mandate**: Integrate Agents 1–4 into one structured, actionable deliverable. Do not introduce novel ideas not grounded in the other four agents' findings. Where agents' findings conflict, state the conflict and resolve it with justification.

Produce exactly these sections:

#### DELIVERABLE 1 — Verified Current-State Scorecard
One row per item from Agent 1's 10-item table plus its independent sweep findings: Item | Status (confirmed done / partially done / not done) | Evidence.

#### DELIVERABLE 2 — Edge-Case Risk Register
Top 10 edge cases from Agent 2, ranked by severity, each with a recommended fix (code change or documented limitation) and effort estimate (S/M/L).

#### DELIVERABLE 3 — Executable Evaluation Plan
Agent 3's output, reconciled — must end with a concrete "what to build first" instruction (e.g. "write `eval/mutate.py` implementing operators X, Y, Z against corpus in `inputs/`").

#### DELIVERABLE 4 — Top 5 Remaining Thesis Vulnerabilities (re-ranked)
Re-rank by actual current severity (not the prior session's ranking) now that some items may be resolved and new edge-case risks are known. For each: vulnerability, mitigation, code-or-wording, risk if unaddressed.

#### DELIVERABLE 5 — Next Implementation Session Plan
A concrete, ordered task list (not phases — actual tasks) for the very next coding session, each task scoped to something completable in one sitting, referencing exact files to touch.

---

## EXECUTION INSTRUCTIONS

1. Run Agent 1 first and alone — its output is a dependency for Agents 2–4. Then run Agents 2–4 (can be done in parallel conceptually, but present sequentially). Then run Agent 5.
2. Label each agent's output clearly.
3. Every factual claim about the codebase must cite a file path (and line numbers where feasible). Claims without a citation should be flagged as "unverified — could not confirm."
4. The synthesis must be directly actionable — specific enough to start coding from without further research.
5. After the full output, add a `## NEXT SESSION` section: a 5-bullet ordered list of first actions, each referencing exact files.

---

## WHAT NOT TO DO

- Do not write any code. Do not edit any files.
- Do not restate the prior session's claims as fact without checking them against current source first (this is the #1 failure mode to avoid — it already happened once).
- Do not make vague recommendations — every recommendation must be specific enough to act on directly.
- Do not skip Agent 1 — everything downstream depends on it being accurate.
