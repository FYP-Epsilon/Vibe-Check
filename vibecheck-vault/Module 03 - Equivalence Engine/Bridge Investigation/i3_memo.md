> [!info] Archived from a Claude Science session — one caveat added on review
> Produced by Claude Science, Session 03 (2026-07-29), following on from Sessions 01 and 02. Its
> two headline EXECUTED claims (§2.2/§2.4's 47.5% definition-order-vs-call-order mismatch, and
> §3's 0/184 gateway/task graph partition) were **independently reproduced** with a
> fresh script against the same corpus — 45.5% and 0/184 respectively (see
> [[AP Vocabulary and Lifting Scope Findings]]). One nuance to hold onto: §6's recommendation #2
> ("wire P1 only") is in tension with this memo's own §5, which notes that ordering defects make
> *any* wiring unreliable while they stand — P1's flagship shape is itself an ordering property.
> Treat "reclassify P0" and "gate unmatched atoms to INCONCLUSIVE" (§6 items 3–4) as the safe
> near-term actions; "wire P1" is downstream of the lifting-scope decision, not independent of it.
> Full reasoning in the consolidated findings note linked above.

# Design Memo — Gateway Atoms and Sentinel Falsifiability

**Session 3 of the Module 01 ↔ Module 03 bridge investigation.**

**Status:** design/research. No implementation code written.
**Repo state:** `/Users/kavindu/Projects/Vibe-Check` @ `af28e52`
**SPOT:** 2.11.6, static build from the tarball pinned in `module_03_equiv/Dockerfile`
**Evidence log:** `i3_verification_log.txt` (companion artifact; findings G1–G5, S1–S5 referenced inline)

**Scope limit, stated up front.** `module_03_equiv` has **no compiled extension module on this
machine**, so nothing below executes VibeCheck's own C++ engine. What *is* executed directly is
Module 02's `CFGExtractor` (real code, real WIR output, on real FLOW-BENCH variants) and Module 01's
`evaluate_ltlf`. C++ lifter behaviour is established by reading `lifter.cpp` and, where noted,
simulating its documented logic. Claims are tagged **SOURCE**, **EXECUTED**, **EXPERIMENT**, or
**REASONED** throughout, and the claim ledger in §8 restates every one.

---

## 1. Headline: both questions have answers, and both answers are "no, but"

The brief asked two questions. Both turn out to have clean negative answers, and in both cases the
negative answer is more useful than a yes would have been, because it relocates the problem.

**Q1 — can the gateway-atom gap be closed so the dangerous P1 properties become checkable?**
**No, and not because of labelling.** Gateway nodes were never the problem. They already carry guard
text and already produce an atom today (G1 — this **corrects a premise Session 2 recorded wrongly**).
The real obstruction is structural and much larger: across all 184 normalized FLOW-BENCH variants,
**gateway nodes and task-type nodes never once appear in the same graph** (G5). Task atoms live only
in the top-level graph; gateway atoms live only inside function sub-CFGs. The two atoms in a
dangerous property shape are in *different automata*. No amount of atom-naming work bridges that.

**Q2 — is the single-task self-referential sentinel fixable by some better lifting design?**
**No — it is unfalsifiable for every possible construction, and this is now proven rather than
observed case-by-case.** The invariant that makes a lifting *faithful* ("every `done_T` is preceded
by that task's `start_T`") is logically identical to the property `!done_T W start_T` itself.
Intersecting the negated property with the space of invariant-respecting models gives the empty
language (S1). Session 2's reviewer was right about option (b), and the result generalises: there is
no design to find. **But** the same test shows the entire P1 tier *is* genuinely checkable under that
identical invariant (S2, S3) — so the checking power was never in P0 to begin with.

**Additionally, and not asked about:** the C++ lifter lifts a chain of *function definitions* in
definition order. On the real corpus that order disagrees with execution order for **47.5% of
variants** (G4). Ordering properties checked against that automaton are checked against the wrong
sequence roughly half the time. This is arguably more urgent than either question posed.

---

## 2. What Module 02 actually emits (the reconnaissance that reframed everything)

Three findings here, in increasing order of consequence.

### 2.1 Gateways do carry guards — Session 2's premise was wrong (G1, SOURCE)

`visit_If` (`cfg_extractor.py:335-338`) creates a `gateway` node and sets `guard` to the unparsed
condition text; `cfg_extractor.py:357-358` then puts that same text on both outgoing edges, with the
false branch negated. On the lifter side, `resolve_edge_label` (`lifter.cpp:222-259`) sanitises guard
text into an AP name. So `if score > 50:` already yields an atom today — something like `score_50`.

Session 2's memo recorded gateways as receiving `bddtrue`. That was incorrect and is corrected here.
The gap is not "gateways have no atom"; it is that the atom is a **sanitised guard expression**, not
Module 01's `node(...)` identity. That is a name-matching problem, and name matching is the one class
of problem Phase A's three-tier matcher (exact → edit-distance → Sentence-BERT) was built for.

Which would make Q1 look easy — except for what follows.

### 2.2 A WIR "task" is a function *definition*, not a business action (G2, EXECUTED)

`node_type="task"` is set in exactly one place: `visit_FunctionDef` (`cfg_extractor.py:474`), where
the code line recorded is the literal string `def <name>(...)`. Business calls like
`approve_loan(score)` become `type="block"` nodes via `visit_Expr` — and `resolve_task_label`
(`lifter.cpp:264-266`) returns `bddtrue` for anything whose type is not `"task"`, so it never looks at
them.

Running the real extractor on a four-line approval workflow makes this concrete:

| graph | contents |
|---|---|
| top-level (**the only graph the C++ lifter reads**) | `entry`, `exit`, `task code=['def run(...)']` |
| sub-CFG `run` (C++ lifter never reads) | `gateway guard='score > 50'`, `block ['approve_loan(score)']`, `block ['reject_loan(score)']` |

The atom emitted is `run` — the definition. `approve_loan` and `reject_loan`, the actual BPMN-level
business actions Module 01 writes properties about, are not lifted at all.

This premise ("the lifter emits one atom per business action") was shared by all three session briefs
including this one. It is wrong. The lifter emits one atom per *function definition*.

### 2.3 The C++ lifter never reads the sub-CFGs (G3, SOURCE)

`grep functions module_03_equiv/src/lifter.cpp` returns nothing. The pure-Python track does read them
(`lifter.py:153`) — but it lifts each function as its **own separate LTS**, appended to a list. So:

- **C++ track:** the real control flow is invisible.
- **Python track:** the real control flow is present, but partitioned across disconnected automata, so
  no single automaton contains a cross-function ordering to check.

Neither track can currently check a property spanning two business actions in different functions.

### 2.4 Definition order ≠ execution order, for half the corpus (G4, EXECUTED)

FLOW-BENCH variant `1__qwen3-next-80b.py` defines `GitHub_..._create_Repository`, then
`Jira_..._create_Issue`, then `workflow()`. Its `workflow()` calls **Jira first, then GitHub**. The
lifted top-level chain is `entry → GitHub → Jira → workflow → exit` — definition order, i.e. inverted
relative to execution.

Measured across all 184 normalized variants (0 parse errors):

| | count |
|---|---|
| variants with an orchestrating function | 181 |
| definition order **==** call order | 95 |
| definition order **!=** call order | **86 (47.5%)** |

For nearly half the corpus, any ordering property evaluated against the top-level automaton is
evaluated against a sequence the program does not execute. Whether that currently produces *wrong
verdicts* depends on the properties actually reaching `check_compliance`, which today is a hardcoded
placeholder — so this is a latent defect, not an observed failure. Flagging it as REASONED on the
"would produce wrong verdicts once wired" step; the order mismatch itself is measured.

---

## 3. Q1 answered: the gateway gap is not the binding constraint

The brief's dangerous category is a property mentioning both a gateway-derived atom and a
task-derived atom — for instance `!start(Approve) W node(xor_gate)`, where an unmatched right-hand
atom turns the property into a false-violation generator on correct code.

I measured whether such a property could be checked even in principle. Across all 184 variants
(881 graphs):

| measurement | value |
|---|---|
| variants with a gateway **anywhere** | 62 |
| variants with a gateway at **top level** | **0** |
| `task`-type nodes inside a **sub-CFG** | **0** |
| variants where gateway + task **share a graph** | **0** |

Per-graph type combinations: 626 graphs with none of gateway/task/loop, 184 with `[task]`, 41 with
`[gateway]`, 30 with `[loop]`, 21 with `[gateway, loop]`. The `[task]` count of 184 is exactly one per
variant — the top-level graph — and no combination containing both `task` and `gateway` occurs at all.

**This is a partition, not a coincidence.** It follows from §2.2 and §2.3: `task` nodes are created
only by `visit_FunctionDef`, which at module level puts them in the top-level graph; gateways inside
those functions land in sub-CFGs, which are separate WIR fragments.

So the answer to Q1 is: **giving gateways `node(...)`-style atoms would not make the dangerous
properties checkable**, because the property's two atoms would still be in different automata. The
atom-vocabulary framing — which drove Sessions 2 and 3's briefs — is addressing the wrong layer. The
binding constraint is **graph scope**, not atom naming.

### 3.1 What would actually be required

Sketching this to size it, not proposing it as this session's deliverable:

1. **Lift call sites, not definitions.** Treat a `block` node whose code contains a non-builtin call
   as the liftable action. `extract_actions_from_code` already does the regex work; it is simply
   gated behind `node_type == "task"`.
2. **Inline or link the sub-CFGs** so that a single automaton contains both the orchestrator's
   gateways and the actions it calls. Inlining is the simpler option and fixes §2.4's order problem
   as a side effect, since the orchestrator's own CFG has the calls in execution order.
3. Only then does gateway atom *naming* become the remaining gap — and at that point it is an
   ordinary Phase A matching problem.

Steps 1 and 2 change lifted geometry substantially, so every hard-coded state/edge count in the test
suites is affected, and Phase C's isomorphism check is state/edge-count sensitive (established in
Session 2). This is a considerably larger change than the split Session 2 recommended. I am **not**
recommending it be undertaken on the strength of this memo alone; §7 says what I think should happen
first.

---

## 4. Q2 answered: the P0 sentinel is unfalsifiable under every construction

Session 2 recommended splitting each task into `start_T` then `done_T`; review found this forces
"every `done_T` is immediately preceded by that task's own `start_T`", making `!done_T W start_T`
vacuous. The brief asks whether *any* design avoids this.

**It does not, and the reason is not about designs at all.** Any lifting faithful to task semantics
enforces the invariant *every occurrence of `done_T` is preceded by `start_T`*. That invariant is the
property. Testing it directly (S1): translate the invariant through `from_ltlf`, build the automaton
of the invariant and of the negated property, take the product — 4 states, and `--is-empty` reports
**empty**.

So `!done_T W start_T` is unfalsifiable not because a construction is badly chosen, but because the
property asks the code to violate the very invariant that makes the lifting faithful. **A construction
under which it were falsifiable would be one that lifts tasks unfaithfully.** There is no design to
find, and no further search is warranted.

Applying the reachability discipline to my own reasoning, as the brief requires: the counterexample
here is not "a word violating the property exists" — it is that **no invariant-respecting model
produces such a word**, which is exactly the check Session 2 omitted. And the negative claim is the
safe direction to be wrong in: if I have the invariant slightly wrong, the risk is that the property
is *more* checkable than I say, not less.

### 4.1 The constructive half: the P1 tier is genuinely checkable (S2, S3)

The same invariant, applied to Module 01's actual P1 sequence-flow shape
(`ltlf_synthesizer.py:119,127-128`, `!start(B) W done(A)`), gives the opposite result. Under
`(!done_A W start_A) & (!done_B W start_B)` the negated property is still satisfiable — **product
non-empty**, with SPOT's witness word:

```
alive & !done_A & start_A & start_B; cycle{!alive}
```

B starts in the same step A starts, before A is done. A real violation, producible by a faithful
lifting.

Cross-checked against Module 01's own `evaluate_ltlf` over the 1,979 faithful traces of length ≤ 3
(out of 4,368 total):

| property | truth values over faithful traces | verdict |
|---|---|---|
| `!done_A W start_A` (P0, self-referential) | `{True}` | **unfalsifiable** |
| `!start_B W done_A` (P1, cross-task) | `{True, False}` | **falsifiable**, witness `[['start_B']]` |

Two tools, two trace semantics (infinite-trace SPOT, finite-trace `evaluate_ltlf`), same verdict.

Extending across every shape Module 01 emits:

| tier | shape | verdict under faithful lifting |
|---|---|---|
| P0 | `!done_A W start_A` | **unfalsifiable (vacuous)** |
| P1 | `!start_B W done_A` (sequence flow) | falsifiable |
| P1 | `G(done_A -> !done_B)` (XOR exclusivity) | falsifiable |
| P1 | `G(start_A <-> start_B)` (AND sync) | falsifiable |
| P1 | `G(done_A <-> done_B)` (AND sync) | falsifiable |

**Exactly one of the five shapes is inherently vacuous, and it is the one Module 01 labels
`P0_Critical_Sentinels`.** All the genuine discriminating power sits in P1. That is an uncomfortable
finding for a tier named "critical safety", and it should be stated that way in the thesis rather
than smoothed over.

### 4.2 The dangerous category confirmed: unmatched atoms give false RED (S4)

The brief's third category is real and I can reproduce it. If `done_A` is never matched, its AP is
permanently false, and `!start_B W done_A` collapses to `G(!start_B)`. Under `evaluate_ltlf`:

| trace | verdict |
|---|---|
| correct code: B starts, A's `done` unobservable | **False → reports VIOLATION** |
| correct code: B never starts | True |

Whenever `start_B` matches but `done_A` does not, **correct code is reported non-compliant.** This is
worse than vacuity: vacuity yields false green, which is embarrassing; this yields false red, which
sends a user hunting a bug that does not exist. And G5 shows the atoms sit in different automata
*precisely* in the shape where this arises — so under the current lifter this is the expected outcome,
not an edge case.

### 4.3 Multiple call sites do not create a loophole (S5)

Testing whether retry/exception shapes could produce `done` without a preceding `start`: a
`try: approve_loan(data) / except TimeoutError: log_retry(data); approve_loan(data)` body yields two
distinct `block` nodes for the same action, on the normal and exception paths respectively. A
per-call-site split would emit `start`/`done` twice — faithful, and still never `done` without a
preceding `start`. S1 stands.

---

## 5. What this means for the bridge, in order

Combining across three sessions, the seam has four defects, and their order of severity has changed:

| # | defect | status |
|---|---|---|
| 1 | vacuous COMPLIANT on non-looping automata | Session 1; fixable via `alive` instrumentation |
| 2 | LTLf vs LTL semantics | Session 1; solved by `spot::from_ltlf` |
| 3 | atom vocabulary mismatch | Sessions 2–3; **reframed — the real issue is graph scope, not naming** |
| 4 | **lifter lifts definitions, not actions; sub-CFGs unread; order wrong for 47.5%** | **new, this session; largest** |

Defect 4 dominates. Fixing 1–3 while 4 stands produces a bridge that reliably model-checks the wrong
automaton. That is not obviously better than the current honest placeholder.

---

## 6. Recommendation

**Do not implement the Session 2 split, and do not implement gateway atom naming yet.** Both are
downstream of a lifting-scope decision that has not been made.

Recommended order:

1. **Decide the lifting scope question first** — does the lifted automaton represent the top-level
   definition chain (current behaviour) or the orchestrator's execution flow (what the properties are
   about)? This is a design decision for the maintainer, not something a patch author should settle.
   Everything else depends on it. Flagged **REASONED** — it is my judgement about sequencing, not a
   verified fact.
2. **Wire the bridge for the P1 tier only**, and say so explicitly. P1 is measurably falsifiable
   (§4.1) and is where the discriminating power is.
3. **Reclassify P0 in the thesis.** The self-referential sentinel is a well-formedness check on the
   lifting, not a check on the code. It is worth keeping as a **lifting self-test** — if a lifted
   automaton *violates* `!done_T W start_T`, the lifter has a bug — but it must not be counted as
   evidence about the generated code. Reporting it as a passed safety property is the
   self-referential-validation failure mode Module 02's own central finding warns about, reappearing
   at the Module 01↔03 seam.
4. **Gate on atom matching before reporting any violation.** Given §4.2, an unmatched atom on the RHS
   of a weak-until must produce `INCONCLUSIVE`, never `VIOLATION`. This is cheap, independent of the
   scope decision, and prevents the worst outcome.

---

## 7. What this memo does not resolve

- **Whether inlining sub-CFGs is the right fix for defect 4.** I sized it (§3.1); I did not evaluate
  alternatives (call-graph linking, per-function checking with an ordering side-condition), and
  recursion makes naive inlining unbounded.
- **Post-change geometry.** Every state/edge count under any proposed change is **BUILD-DEPENDENT** —
  there is no compiled extension here, so I read the construction rather than running it.
- **Whether the Python track should follow.** Unchanged from Session 2: the maintainer's call.
- **The 47.5% figure's downstream impact.** Measured as an order mismatch. Whether it yields wrong
  verdicts depends on properties that do not yet flow through the seam.
- **Corpus scope.** All measurements are on the 184 normalized FLOW-BENCH variants in
  `module_02_extract/eval/variants/normalized/`. Whether hand-written or differently-structured
  workflows show the same clean gateway/task partition is untested — G5's zero counts are strong for
  this corpus but I would not assert them as a language-level invariant.
- **Multi-action tasks.** Session 2's blocker (which action is the start, which the done) is untouched
  and becomes moot only if lifting moves to call-site granularity.

---

## 8. Claim ledger

| # | claim | evidence class |
|---|---|---|
| 1 | Gateway nodes carry guard text; guards reach edges | **SOURCE** — `cfg_extractor.py:335-338, 357-358` |
| 2 | `resolve_edge_label` sanitises guard text into an AP | **SOURCE** — `lifter.cpp:222-259` |
| 3 | Session 2's "gateways get bddtrue" was wrong | **SOURCE** — corrected by claims 1–2 |
| 4 | `node_type="task"` set only in `visit_FunctionDef` | **SOURCE** — `cfg_extractor.py:474`; sole match for `node_type=` |
| 5 | Task node code is `def <name>(...)`, not a business call | **SOURCE** — `cfg_extractor.py:475` |
| 6 | `resolve_task_label` skips non-`task` nodes | **SOURCE** — `lifter.cpp:264-266` |
| 7 | Business calls become `block` nodes, never lifted as actions | **EXECUTED** — real `CFGExtractor` run |
| 8 | C++ lifter never reads `functions` | **SOURCE** — no grep match in `lifter.cpp` |
| 9 | Python lifter lifts each function as a separate LTS | **SOURCE** — `lifter.py:153` |
| 10 | Definition order ≠ call order for 86/181 = 47.5% | **EXECUTED** — 184 variants, 0 parse errors |
| 11 | Gateway and task nodes never share a graph (0/184) | **EXECUTED** — 881 graphs measured |
| 12 | Gateways never at top level; task nodes never in sub-CFGs | **EXECUTED** — same run |
| 13 | P0 self-referential sentinel unfalsifiable for any faithful lifting | **EXPERIMENT** — invariant ∩ ¬property = empty, 4-state product |
| 14 | P1 cross-task sequence flow falsifiable under same invariant | **EXPERIMENT** — non-empty; witness `alive & !done_A & start_A & start_B; cycle{!alive}` |
| 15 | Same P0/P1 verdicts under `evaluate_ltlf` on 1,979 faithful traces | **EXPERIMENT** — finite-trace cross-check |
| 16 | 4 of 5 M01 shapes falsifiable; only P0 vacuous | **EXPERIMENT** — per-shape intersection test |
| 17 | Unmatched RHS atom makes correct code report VIOLATION | **EXPERIMENT** — `evaluate_ltlf`, 2 traces |
| 18 | Multi-call-site retry shapes give distinct nodes, no `done`-without-`start` | **EXECUTED** — real extractor run |
| 19 | Defect 4 dominates defects 1–3 | **REASONED** — severity judgement |
| 20 | Lifting-scope decision must precede split/naming work | **REASONED** — sequencing judgement |
| 21 | P0 should be reclassified as a lifting self-test | **REASONED** — design proposal |
| 22 | Unmatched atoms should yield INCONCLUSIVE not VIOLATION | **REASONED** — follows from claim 17 |
| 23 | Any post-change state/edge count | **BUILD-DEPENDENT** — not confirmed; no compiled extension |
| 24 | G5's partition holds beyond FLOW-BENCH | **NOT ESTABLISHED** — explicitly untested |
