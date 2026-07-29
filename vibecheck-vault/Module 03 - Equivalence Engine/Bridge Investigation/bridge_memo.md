> [!info] Archived from a Claude Science session
> Produced by Claude Science, Session 01 (2026-07-29), from the [[Claude Science Plan#Ready-to-use prompt — P1.4 (LTLf→LTL bridge design)|P1.4 bridge-design prompt]]. Original output location: `Claude-Science-VibeCheck/Session-01/` (outside this repo). Independent verification of its most load-bearing claims, plus one open question it resolved further, is in [[P1.4 Bridge Findings]].

# Design Memo — The LTLf→LTL Bridge Between Module 01 and Module 03

**Status:** design proposal, no implementation code written
**Repo state:** `/Users/kavindu/Projects/Vibe-Check` @ `b791f2d` (2026-07-28, merge of PR #65)
**SPOT version examined:** 2.11.6 — the exact version pinned in `module_03_equiv/Dockerfile:23-30`
**Evidence log:** `bridge_verification_log.txt` (companion artifact; experiment IDs E1–E8 referenced below)

---

## 0. Evidence discipline

Every claim below carries one of three labels.

| Label | Meaning |
|---|---|
| **[VERIFIED-SOURCE]** | Read directly in repo source or SPOT 2.11.6 source at a cited file:line |
| **[VERIFIED-EXPERIMENT]** | Observed by running a real SPOT 2.11.6 build I compiled from the pinned tarball; experiment ID in the evidence log |
| **[REASONED]** | Inferred from general knowledge of LTL/automata theory; **not** confirmed against this codebase |

I built SPOT 2.11.6 from the official tarball (`configure.ac:24` → `AC_INIT([spot], [2.11.6])`) so that SPOT-specific claims are empirical rather than recalled. The build required `--disable-shared --enable-static CFLAGS="-fcommon"`; the bundled BuDDy fails to link as a shared library on arm64 macOS. That is a local build detail, **not** a finding about the project's Docker image.

---

## 1. Executive summary

The bridge is **not** a syntax-conversion problem. Reformatting LTLf strings into SPOT infix syntax is roughly 15 lines of work and is the least interesting part. The real content is three separate defects, of which only the first is the one the project has been describing:

1. **Semantic gap (known).** Module 01 emits finite-trace LTLf; `check_compliance` interprets strings as infinite-trace LTL. SPOT 2.11.6 ships `spot::from_ltlf()` which implements the De Giacomo & Vardi reduction and solves the formula half of this. **[VERIFIED-SOURCE + E1]**

2. **Vacuity defect (previously undiagnosed, and it dominates).** Even with a perfectly translated formula, the current pipeline returns `COMPLIANT` for *every* property, because Module 03's code automata are finite and acyclic with no acceptance condition — their Büchi language is empty, so the product is empty. I reproduced a **false PASS on a genuinely violating automaton**. **[VERIFIED-EXPERIMENT E3]** Translating formulas without also instrumenting the automaton would produce a bridge that is 100% "compliant" and detects nothing.

3. **Vocabulary defect (previously undiagnosed).** Module 01's atoms (`done(Approve)`, `iteration_count <= 10`) are **rejected by SPOT's parser outright**, and `FormulaNormalizer` — the component apparently intended to fix this — is dead code that only handles some atom families. **[VERIFIED-EXPERIMENT E7 + VERIFIED-SOURCE]**

A fourth issue is a genuine design decision rather than a defect: the `alive` reduction makes **non-terminating code unrepresentable**, which collides with the divergence-sensitivity Module 03 deliberately preserves in Phase B (§6).

I also found and confirmed two upstream bugs in Module 01 while validating (§7): a **strong-vs-weak `X` mismatch** against SPOT, and a **tokenizer bug** where `Gb` silently parses as an atom named `Gb` instead of `G(b)`.

**Bottom line:** the bridge is feasible and the mathematics is sound. After fixing the operator mismatch, Module 01's own finite-trace evaluator and SPOT's translated formula agreed on **12,600 / 12,600** formula-trace pairs. **[VERIFIED-EXPERIMENT E5]** But it requires changes on *both* sides — formula translation alone is worse than useless, because it yields a confident, uniformly passing verdict.

---

## 2. What each side actually is

### 2.1 Module 01's output — [VERIFIED-SOURCE]

`export_for_module_03` (`module_01_spec/src/api.py:117-145`) writes three keys: `semantic_graph`, `ltlf_property_suite`, `loop_bound_documented`.

Running the real synthesizer on a five-node XOR workflow produced 12 properties across three tiers:

| Tier | Count | Shape |
|---|---|---|
| `P0_Critical_Sentinels` | 2 | `!done(T) W start(T)` |
| `P1_Structural_Control_Flow` | 9 | `!node(x) W node(y)`, plus one `G(start(A) -> !start(B))` |
| `P2_Quality_Limits` | 1 | `G(iteration_count <= 10 -> F(process_complete))` |

The suite is dominated by **weak-until safety patterns**. This matters: `W` and `G` are exactly the operators whose LTLf/LTL divergence is subtlest, since both are trivially satisfiable by short traces.

Semantics are defined by `ltlf_eval.py` (208 lines) and `ltlf_progression.py`. `evaluate_ltlf` walks a finite `List[Set[str]]` (`ltlf_eval.py:207`).

### 2.2 Module 03's input — [VERIFIED-SOURCE]

`check_compliance` (`module_03_equiv/src/lifter.cpp:1065`) is a textbook pipeline: `parse_infix_psl` → `formula::Not` → `translator` with `set_type(Buchi)` → `spot::product` → `is_empty()` → `accepting_run()`. It correctly reuses the code automaton's `bdd_dict`, which the comment flags as critical and which is genuinely necessary for the product to be well-defined.

The sole caller is `process_wir_batch` (`pipeline.py:53-58`), whose signature carries `ltl_property: str = 'G("approved")'` — the hardcoded placeholder.

---

## 3. Defect 1 — the semantic gap, and `from_ltlf`

### 3.1 `from_ltlf` exists at the pinned version — [VERIFIED-SOURCE E1]

```
spot/tl/ltlf.hh:49   SPOT_API formula from_ltlf(formula f, const char* alive = "alive");
```

Its implementation (`spot/tl/ltlf.cc:27-73`) cites De Giacomo & Vardi IJCAI'13, and the source comments note that the paper's Theorem 1 contains a typo in `t(a U b)`, corrected per Dutta & Vardi Memocode'14 — and that the Memocode'14 version in turn omits the "alive holds initially" conjunct. SPOT implements the corrected combination. This is a meaningful reassurance: the tricky cases have been handled upstream by the authors rather than by us.

The top-level wrapper adds three conjuncts (`ltlf.cc:71-72`):

```
And{ from_ltlf_aux(f, alive),        // per-operator rewrite
     alive,                          // alive holds initially
     U(alive, G(Not(alive))) }       // alive holds a while, then dies forever
```

Per-operator rules (`ltlf.cc:32-59`), confirmed by running the built binary:

| LTLf | LTL |
|---|---|
| `F φ` | `F(alive & t(φ))` |
| `G φ` | `G(!alive \| t(φ))` |
| `a U b` | `t(a) U (alive & t(b))` |
| `a W b` | `(!alive \| t(a)) W t(b)` |
| `X φ` (weak) | `X(!alive \| t(φ))` |
| `X[!] φ` (strong) | `X(alive & t(φ))` |

Applied to a real Module 01 sentinel **[VERIFIED-EXPERIMENT E2]**:

```
!done_Approve W start_Approve
  ↦  alive & ((!alive | !done_Approve) W start_Approve) & (alive U G!alive)
```

All 12 real properties translated without error after sanitization (§5). **[E2]**

`to_finite()` also exists (`spot/twaalgos/remprop.hh:55`), introduced in 2.11 and bug-fixed in 2.11.4 per `NEWS:67`. It converts an `alive`-instrumented automaton into a state-based Büchi automaton where states with an outgoing `!alive` edge become accepting (`remprop.cc:179-240`). It is an alternative to §4's instrumentation, not a replacement for it — it still requires the `alive` AP to exist on the automaton.

### 3.2 A CLI front end exists — [VERIFIED-SOURCE]

`ltlfilt --from-ltlf[=alive]` (`bin/ltlfilt.cc:166-168, 465, 648-652`). Useful for building test oracles without linking C++.

---

## 4. Defect 2 — the vacuity problem (the one that actually decides the design)

### 4.1 The code automata have empty Büchi language — [VERIFIED-SOURCE]

`grep` for `set_buchi|set_acceptance|set_generalized_buchi` across `lifter.cpp` returns **nothing**. Automata are built via `make_twa_graph(dict_)` (`lifter.cpp:354`), whose base constructor leaves `acc_` default-constructed (`twa.cc:39-45`, `acc.hh:1480-1485`) — the "t"/`all` condition with zero sets.

Exit states are explicitly permitted to have **no outgoing edges**: `lifter.cpp:499-512` checks `if (!has_outgoing)` and suppresses the deadlock diagnostic when the state is in `exit_node_ids`. No self-loop is added.

So a terminating workflow lifts to a finite acyclic automaton. It has no infinite runs, hence no accepting runs, hence empty language.

### 4.2 Module 03's own test suite documents this — [VERIFIED-SOURCE]

`module_03_equiv/tests/test_cpp_engine.py:366-404`, class `TestPhaseD`, docstring:

> a finite automaton with no cycles vacuously satisfies ALL liveness/safety LTL properties because the synchronous product has no accepting runs

and `test_finite_automaton_passes_all_properties` asserts `is_compliant is True` with the comment `# vacuously true`. The suite obtains a failing verdict only by using `LOOPING_WIR`, which has a deliberate `G→T2→G` retry cycle (`:340-363`).

This is correct Büchi semantics. It is also a **complete absence of verification power** for exactly the terminating workflows BPMN describes.

### 4.3 Reproduced end-to-end — [VERIFIED-EXPERIMENT E3]

I hand-built the automaton the lifter would produce for code that fires `done_Approve` **without** `start_Approve` — an unambiguous violation of the P0 sentinel — and ran the real Phase D pipeline:

```
naive code automaton language      = EMPTY
product with !(LTLf property)      = EMPTY   → verdict COMPLIANT
ground truth                       = VIOLATION
```

**A false PASS on a real violation.** Had I translated formulas and stopped there, the bridge would have reported perfect compliance on arbitrarily wrong code. This is the finding that most changes the shape of the work.

### 4.4 The fix, and proof that it works — [VERIFIED-EXPERIMENT E4]

The `alive` reduction requires the model to be instrumented to match the formula. For each lifted code automaton:

1. Register an `alive` AP; conjoin `alive` onto every existing edge label.
2. Add a fresh `dead` sink state with a `!alive` self-loop, marked accepting (Büchi).
3. Add a `!alive` edge from each exit state to the sink.

I built the violating and compliant instrumented automata and ran the real check:

| Model | Language | Verdict |
|---|---|---|
| violating | non-empty | **VIOLATION**, counterexample found |
| compliant | non-empty | **COMPLIANT** |

Correct verdicts in both directions. The bridge works — but only with both halves.

### 4.5 Where the instrumentation belongs

**[REASONED]** — this is a judgement call, not a verified fact. Two options:

- **(a) Inside `build_spot_automaton`**, always. Every automaton is born instrumented. Risk: Phases B and C consume the same automata, and adding a state plus an AP could perturb the stuttering-bisimulation quotient and the clustering.
- **(b) A separate `instrument_for_ltlf()` applied only on the Phase D path.** Phases B/C keep byte-identical inputs; Phase D gets its own instrumented copy.

**I recommend (b)**, because Phase B's divergence sensitivity is a deliberate research contribution and should not be perturbed by a Phase D concern. The cost is one automaton copy per check.

---

## 5. Defect 3 — the atom vocabulary problem

### 5.1 Module 01's atoms do not parse — [VERIFIED-EXPERIMENT E7]

| Formula | SPOT parser |
|---|---|
| `!done(Approve) W start(Approve)` | **PARSE ERROR** (unexpected `(`) |
| `!start_Approve W node(xor_gate)` | **PARSE ERROR** |
| `!done_Approve W start_Approve` | parses |
| `G(iteration_count <= 10 -> F(process_complete))` | **PARSE ERROR** (invalid token) |
| `G("iteration_count <= 10" -> F(process_complete))` | parses |

SPOT reads `done(Approve)` as an identifier followed by a parenthesis. Since `check_compliance` **throws** `std::invalid_argument` on parse errors (`lifter.cpp:1072-1078`), an unsanitized suite fails loudly rather than silently — the one piece of good news here.

Arithmetic comparisons parse **only** when double-quoted, which makes them opaque atoms. That is semantically honest: SPOT has no arithmetic. But it means `iteration_count <= 10` is an uninterpreted boolean, and the loop bound is **not** actually checked by the model checker. That should be stated in the certificate rather than implied.

### 5.2 `FormulaNormalizer` is dead code and incomplete — [VERIFIED-SOURCE + EXPERIMENT]

`grep` for `FormulaNormalizer|formula_normalizer` across `module_01_spec/src` and `module_03_equiv` returns **only its own definition** (`formula_normalizer.py:4`). Nothing calls it.

Running it on the real generated suite, it rewrites `done(Approve)` → `done_Approve` and `start(Approve)` → `start_Approve`, but leaves `node(xor_gate)` and `node(end_event)` untouched — so its output *still* fails to parse. It handles the `start`/`done` families and misses the `node` family.

### 5.3 The deeper problem: the vocabularies may not intersect at all

**[VERIFIED-SOURCE]** Code-side APs come from `semantic_match` (`lifter.cpp:134-177`), which maps extracted call names to BPMN task names through exact → Levenshtein(≤2) → Sentence-BERT(≥0.85), falling back to `"unlabeled_task"`. The resulting AP is the **matched BPMN task name** — e.g. `Approve`.

Module 01's atoms are **`start(Approve)` and `done(Approve)`** — two distinct lifecycle events per task.

**[REASONED]** So even after sanitization, spec-side `start_Approve`/`done_Approve` need not correspond to any code-side AP named `Approve`. An AP that appears in the formula but never on any edge is simply always false, which silently makes safety properties of the form `!done(T) W start(T)` **trivially true** — a second, quieter vacuity channel.

**This is the largest remaining unknown and I did not resolve it.** I did not run the full C++ lifter (the container build was out of scope here), so I could not enumerate the actual AP set of a real lifted automaton. Before implementing, someone should dump the APs of a lifted automaton and diff them against a sanitized Module 01 suite. If they don't intersect, the bridge needs an **event-lifecycle mapping layer** (one code action ↦ a `start`/`done` AP pair), which is a substantially larger design task than formula translation and would deserve its own memo.

---

## 6. Design tension: divergence vs. the `alive` reduction

**[VERIFIED-EXPERIMENT E8]** The conjunct `alive U G!alive` requires the trace to eventually stop being alive. I checked whether the translated property can be satisfied by any word where `alive` holds forever: **no intersection**. Translated properties are **unsatisfiable on never-dying traces**.

Consequence: a hallucinated `while True: pass` lifts to an automaton that never reaches an exit, so `alive` never drops, so **every** LTLf property reports VIOLATION.

Is that right? I think it is defensible and arguably desirable — non-termination genuinely violates a BPMN process that specifies an end event. But note the tension with Module 03's Phase B, which deliberately does *not* collapse a divergent loop into a normal wait state. Phase D would flag divergence indiscriminately, without distinguishing "diverged" from "reached a bad state."

**[REASONED] Recommendation:** treat divergence as its own verdict rather than a property violation. Before model-checking, test whether the instrumented automaton can reach the `dead` sink at all; if not, return a distinct `NON_TERMINATING` verdict with the divergent SCC as the witness. This preserves the Phase B distinction and avoids reporting a misleading "property X violated" when the real finding is "this code never finishes."

---

## 7. Two upstream Module 01 bugs found while validating

Both were discovered by differential testing, not by inspection.

### 7.1 Strong-vs-weak `X` mismatch — [VERIFIED-SOURCE + EXPERIMENT E6]

- Module 01: `ltlf_eval.py:166-169` — `X` at the last index returns `False`. That is **strong** next.
- SPOT: `ltlf.cc:37-39` — `op::X` is grouped with `op::G` and rewritten as `X(!alive | t(φ))`. That is **weak** next. Strong next is `op::strong_X`, surface syntax `X[!]`.

Passing Module 01's `X` to `from_ltlf` unchanged **silently flips the semantics at the end of the trace**. My first differential run showed 2,655 disagreements out of 10,080, overwhelmingly from `X`.

**The bridge must rewrite `X` to `X[!]`.** This is a genuine trap: it is silent, and it only manifests at trace boundaries.

Caveat: none of the 12 properties in the sample suite used `X`, so this is currently latent rather than active. It will bite as soon as the synthesizer emits `X`.

### 7.2 Tokenizer absorbs operators into atom names — [VERIFIED-SOURCE + EXPERIMENT]

`TOKEN_SPEC` in `ltlf_eval.py:11` defines `('LTL_OP', r'\b[GfFXUW]\b')`. The trailing `\b` requires a word boundary, so an operator directly adjacent to its operand is not recognized:

```
'Gb'     → [('IDENT_ATOM', 'Gb')]        # atom named "Gb" — G silently lost
'G(b)'   → [('LTL_OP','G'), ...]         # correct
'Fdone_X'→ [('IDENT_ATOM','Fdone_X')]    # F silently lost
```

Confirmed behaviorally: `evaluate_ltlf('G(b)', [{'b'}])` is `True` while `evaluate_ltlf('Gb', [{'b'}])` is `False`.

This is a **silent misparse producing a wrong truth value**, not an error. It is independent of the bridge and worth filing regardless. It also has a nasty interaction with §5: sanitizing `done(Approve)` → `done_Approve` is safe, but any sanitizer that produced an atom name *starting with* `G`, `F`, `X`, `U`, or `W` adjacent to nothing would be at risk. Recommend the bridge emit parenthesized operator arguments and treat the tokenizer regex as needing a separate fix (`(?![a-zA-Z0-9_])` instead of `\b`).

### 7.3 Clean differential validation — [VERIFIED-EXPERIMENT E5]

With `X` mapped to `X[!]` and all unary arguments parenthesized (avoiding 7.2):

- 150 random formulas, depth 3, APs `{a,b}`, all operators including `U`/`W`/`R`-free subset
- 84 traces (all words of length 1–3 over 2 APs)
- **12,600 comparisons: agree = 12,600, disagree = 0**

Method: evaluate the LTLf formula with Module 01's own `evaluate_ltlf`; independently translate with `from_ltlf`, encode the trace as an `alive`-instrumented one-word Büchi automaton, and test intersection with the translated property via `autfilt --intersect`.

This is the strongest evidence in the memo: it validates the reduction, the `X[!]` fix, and my proposed automaton instrumentation **simultaneously**, against Module 01's actual semantics rather than a specification of them.

Limits, stated plainly: 2 APs, traces ≤3, no `R`/`M` operators, and the empty trace excluded (`evaluate_ltlf` returns `False` for it, `ltlf_eval.py:203-204`). It is a strong smoke test, not a proof.

---

## 8. Recommended design

A single translation function, owned by Module 01 (it owns LTLf semantics), plus an instrumentation step owned by Module 03 (it owns automata).

**Stage 1 — sanitize (Module 01 side).** Rewrite `f(x)` → `f_x` for all functional atoms; wrap comparison atoms in double quotes; parenthesize all unary operator arguments. Replace `FormulaNormalizer`, which is dead and incomplete. Emit an explicit **atom manifest** mapping each sanitized AP back to its BPMN origin — needed for §5.3 diagnosis and for readable counterexamples.

**Stage 2 — operator repair.** Rewrite strong `X` to `X[!]`. Do this before `from_ltlf`, never after.

**Stage 3 — translate.** Call `spot::from_ltlf(f, "alive")`. Do **not** hand-roll the reduction; SPOT's version already handles two published paper errata.

**Stage 4 — instrument the model (Module 03 side).** `instrument_for_ltlf(aut)` per §4.4, on the Phase D path only.

**Stage 5 — divergence pre-check.** If the `dead` sink is unreachable, return `NON_TERMINATING` (§6) instead of model-checking.

**Stage 6 — check and aggregate.** Call `check_compliance` per property; replace the `ltl_property: str` placeholder in `process_wir_batch` with a suite plus per-tier results. **[REASONED]** P0 failures should gate; P1/P2 should be reported with weights, mirroring Module 02's V3-gates-V1/V2 structure.

**Stage 7 — vacuity guard.** Before trusting any `COMPLIANT`, assert the instrumented model's language is non-empty and that every AP in the formula occurs on some edge. Given that vacuity has already produced one false PASS here (§4.3) and that self-referential vacuity is the central finding of Module 02, this belongs in the certificate as a first-class field, not in a comment.

### Alternative considered and rejected

Using `to_finite()` to convert the instrumented automaton to a finite-word Büchi automaton and checking the **untranslated** formula. Rejected: `to_finite` still requires `alive` instrumentation (`remprop.cc:187-194`), so it saves nothing on the model side, and it moves the finite-trace semantics into a less-tested code path. **[REASONED]** — I did not benchmark the two.

---

## 9. Explicitly out of scope

- **Whether the AP vocabularies intersect (§5.3).** The most important open question. Needs a real lifted automaton's AP dump.
- **Running the actual C++ lifter.** I verified `check_compliance` by reading its source and by reproducing its exact algorithm against a real SPOT build with hand-built automata. I did **not** execute the project's compiled `vibecheck_lifter` module.
- **Module 01 startup.** `main.py:11,16` imports `automata_lifter`, which is absent from `module_01_spec/src/`. Confirmed still broken at `b791f2d`. Module 01 also still has **no `tests/` directory**.
- **PBCTS / trace-synthesis interaction.** `loop_bound_documented` is extracted by regex over `P2_Quality_Limits` looking for `loop_bound\s*=\s*(\d+)` (`api.py:126-135`), which matches nothing in the observed P2 output, so it stays `0`. The comment claims a default of 3 while the code defaults to 0. Flagged, not addressed.
- **Fairness/P2 tier semantics** under the reduction beyond parseability.
- **Performance.** No measurements. Product size and translation cost unmeasured.

---

## 10. Claim ledger

| # | Claim | Label | Source |
|---|---|---|---|
| 1 | `from_ltlf` exists at 2.11.6 | VERIFIED-SOURCE | `spot/tl/ltlf.hh:49` |
| 2 | Reduction = De Giacomo & Vardi, with 2 errata fixed | VERIFIED-SOURCE | `ltlf.cc:40-47` |
| 3 | `to_finite` exists, added 2.11, fixed 2.11.4 | VERIFIED-SOURCE | `remprop.hh:55`, `NEWS:67,238` |
| 4 | All 12 real M01 properties translate after sanitization | VERIFIED-EXPERIMENT | E2 |
| 5 | Lifter never sets an acceptance condition | VERIFIED-SOURCE | grep over `lifter.cpp` |
| 6 | Exit states get no self-loop | VERIFIED-SOURCE | `lifter.cpp:499-512` |
| 7 | Current pipeline gives a **false PASS** on a real violation | VERIFIED-EXPERIMENT | E3 |
| 8 | M03's own tests document the vacuity | VERIFIED-SOURCE | `test_cpp_engine.py:366-404` |
| 9 | `alive` instrumentation yields correct verdicts both ways | VERIFIED-EXPERIMENT | E4 |
| 10 | M01 atoms are rejected by SPOT's parser | VERIFIED-EXPERIMENT | E7 |
| 11 | `FormulaNormalizer` has no callers and is incomplete | VERIFIED-SOURCE + EXP | grep; run on real suite |
| 12 | M01 `X` is strong; SPOT's bare `X` is weak | VERIFIED-SOURCE + EXP | `ltlf_eval.py:166-169`; `ltlf.cc:37-39`; E6 |
| 13 | `Gb` misparses as atom `Gb` | VERIFIED-SOURCE + EXP | `ltlf_eval.py:11`; tokenizer dump |
| 14 | 12,600/12,600 agreement after fixes | VERIFIED-EXPERIMENT | E5 |
| 15 | Translated properties unsatisfiable on never-dying traces | VERIFIED-EXPERIMENT | E8 |
| 16 | `main.py` imports missing `automata_lifter`; no M01 tests | VERIFIED-SOURCE | grep; `ls` |
| 17 | Instrumentation belongs on the Phase D path only | **REASONED** | design judgement |
| 18 | AP vocabularies may not intersect | **REASONED** | unresolved; needs AP dump |
| 19 | Divergence should be its own verdict | **REASONED** | design judgement |
| 20 | P0 should gate, P1/P2 weighted | **REASONED** | analogy to Module 02 |
