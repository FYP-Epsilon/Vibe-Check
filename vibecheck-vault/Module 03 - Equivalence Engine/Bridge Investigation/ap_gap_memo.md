> [!warning] Archived from a Claude Science session — headline recommendation found incomplete on review
> Produced by Claude Science, Session 02 (2026-07-29), following on from [[bridge_memo|Session 01]].
> Independent review caught a gap this memo's own reachability discipline should have applied to
> itself: **§6's claim that option (b) "preserves P0 detection power" does not hold** on the real
> 12-property suite — the two P0 self-sentinels collapse to a tautology under (b) by the same
> mechanism that sank option (d) in §3, and 4 of the 9 P1 properties become false-VIOLATION risks
> via the still-open `node(...)` gap this memo scoped out (§9.5). (b) is still the best of the four
> options evaluated, but the "preserves P0" framing is not accurate as written. A follow-up
> investigation is in progress to resolve whether the `node(...)` gap is closable and whether the
> P0 sentinel shape is fixable by any design. Do not treat this memo's recommendation as final
> until that follow-up lands — check [[Home]] / [[Next Steps]] for the current status.

# Design Memo — Closing the Atomic-Proposition Vocabulary Gap Between Module 01 and Module 03

**Status:** design proposal. No implementation code written.
**Repo state:** `/Users/kavindu/Projects/Vibe-Check` @ `6d4c47b`
**SPOT version used for experiments:** 2.11.6 (static build from the tarball pinned in `module_03_equiv/Dockerfile:23-30`)
**Evidence log:** `ap_gap_verification_log.txt` (companion artifact; findings F1–F10 referenced inline)

**Important scope limit, stated up front:** `module_03_equiv` has **no compiled extension module on this
machine**. Nothing below involves executing VibeCheck's own C++ engine. Where I needed behavioural
evidence I built the automata *by hand in HOA* to match exactly what `lifter.cpp` constructs (verified
by reading the construction code) and ran them through the *same algorithm* Phase D uses — real SPOT,
real product-and-emptiness — plus Module 01's own `evaluate_ltlf` for the finite-trace side. Claims that
would need the project's own build to confirm are labelled **BUILD-DEPENDENT** and are not asserted.

---

## 1. The gap, stated precisely

Module 01 emits properties over a **two-atom-per-task lifecycle vocabulary**: `start(Approve)`,
`done(Approve)`. Its P0 safety tier is built almost entirely from the sentinel shape

```
!done(T) W start(T)          "T never completes before it has started"
```

Module 03's lifter emits **one atom per task**, derived from matched action names, with **no lifecycle
distinction whatsoever** (**F1**, verified: `lifter.cpp:261-297`; `grep` for `start_`/`done_`/`lifecycle`
across `lifter.cpp` and `lifter.py` returns no matches). The atom attaches to the task's **outgoing**
edge, conjoined with that edge's guard (**F1**, `lifter.cpp:432-459`).

So the two halves disagree on more than spelling. They disagree on **how many observable events a task
is**. Module 01 says two, ordered. Module 03 says one.

### 1.1 A second gap the brief did not mention, which changes the recommendation

The **pure-Python track never labels task actions at all.** `_create_transitions` reads *only* edge
guards; a task node with no guard on its outgoing edge produces the label `"tau"` (**F2**, verified:
`lifter.py:284-319`; the sole reference to node `code` is at `lifter.py:274`, where it is copied into
state metadata and never turned into a label).

This matters because it means:

- The AP gap is **entirely a C++-track concern**. The 37-test Python track has no task APs to align.
- Any option requiring lifter changes must be implemented **twice**, or explicitly declared C++-only —
  which then means the Python track can never do Phase D compliance checking against Module 01 properties.

I flag this as a **decision the brief did not anticipate** and address it in §7.

---

## 2. Option (a) / (c): collapse the spec side to one atom per task

Options (a) (change Module 01 to emit one atom) and (c) (translate two atoms down to one at the
boundary) are **the same option semantically** — they differ only in where the information is discarded.
Both reduce `!done(T) W start(T)` to `!T W T`.

**This is a tautology. Verified by experiment (F3).** Evaluated with Module 01's *own* `evaluate_ltlf`
over all 30 non-empty finite traces of length ≤ 4 over a single atom:

```
'!Approve W Approve'  =>  True on every trace
```

The two-atom control `!d W s` returns `{True, False}`, with `[['d']]` as a falsifying trace.

So collapsing does not weaken the P0 tier — it **deletes** it. Every sentinel becomes unfalsifiable, and
Phase D would report `COMPLIANT` for the entire P0 tier on every input, including code that is
flagrantly wrong. That is worse than not wiring the modules together, because it produces a
green certificate rather than an honest gap.

**Verdict: reject both.** Option (c) has the additional defect that it is a boundary layer whose job is
to destroy information, which is the opposite of what a boundary layer between independently-derived
objects should do.

---

## 3. Option (d): conjoin `start_T` and `done_T` onto the same transition

This is the cheap option, and the brief asks me to be skeptical of it. The skepticism is warranted:
**option (d) is vacuous by construction.**

The reasoning that makes (d) look attractive is that the sentinel is *not* trivially satisfied — and a
first-pass experiment appears to confirm this (**F4**). Running hand-built alive-instrumented words
through the real Phase D algorithm, with the property translated by `from_ltlf`:

| word | verdict |
|---|---|
| `start_Approve` ∧ `done_Approve` simultaneously | COMPLIANT |
| `done_Approve` alone, `start_Approve` never | **VIOLATION** |
| neither fires | COMPLIANT |

That middle row is why (d) looks defensible: the property *can* still fail. But that row is
**unreachable under (d)**. If the lifter conjoins both atoms onto the same edge, it will never emit
`done_Approve` without `start_Approve`. Option (d) enforces a structural invariant on every automaton
it produces:

```
G(done_T <-> start_T)
```

The decisive test (**F4**) intersects that invariant with the negation of the translated property:

```
invariant, translated:  alive & G(!alive | (done_Approve <-> start_Approve)) & (alive U G!alive)
intersect with !property  =>  EMPTY
```

**No option-(d)-shaped automaton can ever violate the sentinel.** Cross-checked independently against
Module 01's `evaluate_ltlf` over the 14 simultaneity-respecting traces: `!d W s` returns `{True}`.

Two independent tools, two semantics (infinite-trace SPOT and finite-trace `evaluate_ltlf`), same answer.

**Verdict: reject.** Option (d) is not "weaker but cheaper" — it is *exactly as detective as option (a)*
while carrying the extra cost of doubling the AP count and the false appearance of lifecycle awareness.
It is the worst of the four: it produces a green P0 tier and looks like it earned it. If anything in this
memo should be treated as settled, it is this.

---

## 4. Option (b): split each task into two lifted events

Give each task node a synthetic intermediate state, so a task becomes two consecutive observable
transitions: one labelled `start_T`, one labelled `done_T`.

**This discriminates correctly. Verified by experiment (F5):**

| word | verdict |
|---|---|
| `start_Approve` then `done_Approve` (correct order) | COMPLIANT |
| `done_Approve` then `start_Approve` (**inverted lifecycle**) | **VIOLATION** |

Ordering becomes observable, so the sentinel retains its intended meaning. This is the only one of the
four options for which that is true.

### 4.1 It survives Phase B, which is not obvious and needed checking

A synthetic state is only useful if stuttering collapse does not eat it. It does not (**F6**, verified):

- C++: `is_tau(cond)` returns true only when `cond == bddtrue` or `cond` is a registered tau variable
  (`lifter.cpp:551-557`).
- Python: silent iff `lbl in ("tau", "true")` (`stuttering_engine.py:170`, `:344`).

A `start_T` / `done_T`-labelled edge is a genuine observable, so the synthetic state is **not** absorbed
into a stuttering block and survives into the quotient. Option (b) therefore does not quietly undo
itself one phase later.

### 4.2 The plumbing already exists

The lifter already receives spec-side task names: `set_bpmn_tasks()` (`lifter.cpp:101-103`), passed
through from `pipeline.py:96-97` (**F9**). Option (b) needs **no new cross-module channel** to know which
tasks to split — and note this channel does not violate dual-track independence, since it carries
*vocabulary*, not structure or expected behaviour.

---

## 5. Blast radius of option (b)

This is where option (b) stops being free. Concretely:

### 5.1 Tests that break (F8, verified by reading assertions)

Test totals by file: `test_cpp_engine.py` 29, `test_phase_b.py` 28, `test_phase_c.py` 19,
`test_pipeline.py` 37.

| test | assertion | why it breaks |
|---|---|---|
| `test_cpp_engine.py:127` | `num_states() == 3` | `SIMPLE_LINEAR_WIR` has 1 task → becomes 4 states |
| `test_cpp_engine.py:133` | `num_edges() == 2` | → 3 edges |
| `test_cpp_engine.py:145` | `num_states() == 5` | `BRANCHING_WIR`, 2 tasks → 7 states |
| `test_cpp_engine.py:151` | `num_edges() == 5` | → 7 edges |
| `test_phase_b.py:434` | `collapsed.num_states() == graph.num_states() - 1` | relative, but the tau-cycle fixture's absolute geometry changes |
| `test_pipeline.py:193`, `:202` | `num_states() == 3`, `== 5` | **Python track — unaffected** (F2: no task labels there) |

These are **expected-value updates, not logic breakage** — the assertions encode the old geometry, not a
correctness property. That is the cheap kind of test breakage. But it is not zero, and every updated
number needs to be re-derived rather than fitted to whatever the new code prints, or the tests stop
being evidence.

### 5.2 Phase C is the real risk, and it constrains the design

Phase C clusters by `spot::isomorphism_checker::are_isomorphic`, which (**F7**, verified) requires the
bijection to preserve **transition conditions and acceptance sets** (`are_isomorphic.hh:37-41`), and
short-circuits to "not isomorphic" when `num_states` or `num_edges` differ
(`are_isomorphic.cc:101-105`).

Consequence: **the split must be uniform.** If it is applied to some task nodes and not others — e.g.
only to tasks that appear in a Module 01 property, or only to tasks whose action matched — then two
implementations of the same process that differ only in *which* of their tasks matched the spec
vocabulary will get different state counts and **fall out of the same cluster**. Phase C would report
spurious singleton anomalies.

This is a genuine design constraint and it rules out the "optimisation" of splitting only
property-relevant tasks. **Split every task node or none.**

### 5.3 Cost summary

- **C++ lifter:** synthetic state insertion in the build loop; two-atom naming; `resolve_task_label`
  restructured to return an ordered pair rather than a conjunction.
- **Python lifter:** currently has no task labels at all (F2). Either implement labelling from scratch
  or accept C++-only Phase D. See §7.
- **Tests:** ~6 hard-coded count assertions to re-derive (§5.1), plus new tests (§8).
- **Module 01:** **no change required.** Its vocabulary is already correct. This is the strongest
  argument for (b): it is the only option that does not ask the more-formal side to degrade itself to
  accommodate the less-formal side.
- **WIR schema / `shared_schemas`:** **no change required.** The split is a lifting-time decision, not a
  representation change. Worth stating explicitly, since the brief asked that schema changes be treated
  as a real cost — option (b) does not incur it.

---

## 6. Recommendation

**Adopt option (b), uniformly, in the C++ track.**

Rationale, in order of weight:

1. It is the **only option that preserves P0 detection power** — the other three make the safety tier
   unfalsifiable (F3, F4), and P0 is the tier the certificate leans on hardest.
2. It requires **no change to Module 01 and no change to the WIR schema**. The information asymmetry is
   real: Module 01's vocabulary is strictly richer, and the correct repair is to raise the code side's
   resolution, not lower the spec side's.
3. Its costs are **localised and mechanical** — one construction loop, ~6 expected-value test updates —
   with the single genuine constraint that the split be uniform (§5.2).
4. It survives Phase B (F6) and does not require new cross-module plumbing (F9).

The cheap option is not cheap. It is free in effort and it costs the entire P0 tier, silently.

---

## 7. The Python-track decision this forces (flagged, not resolved)

Because the Python lifter has no task labels at all (F2), option (b) creates a fork:

- **7a. C++-only.** Implement the split in `lifter.cpp` only; document that Phase D compliance checking
  against Module 01 properties requires the C++/SPOT container. Cheap, honest, but leaves the
  pure-Python track permanently unable to do the thing this whole bridge is for.
- **7b. Both tracks.** Also implement action extraction and lifecycle labelling in `lifter.py`. Larger
  effort, and it means reimplementing the three-tier semantic matching cascade in Python.

I **recommend 7a for now** and explicitly recording it as a known limitation, on the grounds that the
Python track's stated purpose is dependency-free structural analysis, not model checking — but this is
**reasoned judgement, not a verified claim about intent**, and it is properly the maintainer's call. It
should not be decided implicitly by whoever writes the patch.

---

## 8. Test plan

Ordered so that the first test that fails tells you the most.

1. **Lifecycle-inversion detection (the test that justifies the whole change).** WIR for a task whose
   code completes an action before any start is observable — the `done`-then-`start` shape from F5 —
   checked against `!done(T) W start(T)`. Must report **VIOLATION** with a counterexample trace. Assert
   on the *verdict and the trace*, not just the verdict.
2. **Negative control on the same fixture.** Correctly-ordered `start`-then-`done` must report
   **COMPLIANT**. Without this, test 1 passes for a broken reason.
3. **Anti-vacuity regression.** Assert directly that the sentinel is falsifiable under the new lifting:
   that some constructible automaton violates it. This is the test that would have caught option (d), and
   it should exist permanently so nobody reintroduces simultaneity as an optimisation.
4. **Geometry tests, re-derived.** Update the ~6 assertions in §5.1 by deriving the expected counts from
   the fixture (nodes + tasks), not by recording observed output.
5. **Phase B non-absorption.** A task-split fixture must retain its synthetic state through
   `tarjan_tau_collapse` — direct regression on F6.
6. **Phase C uniformity.** Two implementations of the same process where only one has spec-matched
   actions must remain **in the same cluster** — direct regression on the §5.2 hazard.
7. **Multi-action task behaviour** — see §9, item 1. Whatever rule is chosen, pin it with a test on
   `MULTI_ACTION_TASK_WIR`.

---

## 9. What this memo does *not* resolve

1. **Multi-action tasks.** `resolve_task_label` conjoins every matched action onto one label
   (**F10**, `lifter.cpp:279-295`), and `MULTI_ACTION_TASK_WIR` (`test_cpp_engine.py:81-96`) has three
   code lines in one task node: `verify_identity(user)`, `approve_loan(data)`, `print('done')`. Under
   option (b), **which action is the `start` and which the `done` is undefined.** Candidate rules —
   first-matched is `start` and last-matched is `done`; or split per action rather than per task; or
   treat the node as one task and conjoin all actions onto both events — have materially different
   detection properties and I have not evaluated them. **This is the largest open question and it blocks
   implementation.**
2. **Whether real Module 02 output even produces distinguishable start/done evidence.** The split is only
   meaningful if the WIR carries enough information to place the boundary. I have not examined real
   FLOW-BENCH WIR output, only the test fixtures.
3. **BUILD-DEPENDENT: actual state/edge counts after the change.** Every count in §5.1 is derived by
   reading the construction code, not by running it. They should be confirmed against a real build before
   being written into tests.
4. **BUILD-DEPENDENT: whether any of the 113 C++ tests fail for reasons other than counts.** I audited
   assertions by grep; I did not run the suite. There may be behavioural assertions I did not surface.
5. **Non-task nodes.** Gateways and events carry `bddtrue` labels (F1). Module 01 emits `node(...)`
   atoms for them. That is a *second, separate* vocabulary gap, out of scope here, and it means P1
   structural properties referencing `node(...)` atoms remain unmatched even after (b).
6. **Atom spelling.** Option (b) fixes lifecycle *granularity*. It does not fix the syntactic mismatch
   documented in the P1.4 memo — `FormulaNormalizer` is still uncalled and incomplete. Both must be
   fixed for end-to-end checking; this memo addresses only the first.

---

## 10. Claim ledger

| # | Claim | Evidence class |
|---|---|---|
| 1 | Lifter emits one atom per task, no lifecycle | **VERIFIED-SOURCE** — `lifter.cpp:261-297`, grep |
| 2 | Task label attaches to outgoing edge, conjoined with guard | **VERIFIED-SOURCE** — `lifter.cpp:432-459` |
| 3 | Python track labels only guards, never task actions | **VERIFIED-SOURCE** — `lifter.py:284-319`, `:274` |
| 4 | Collapse to one atom makes P0 sentinel a tautology | **VERIFIED-EXPERIMENT** — F3, Module 01 evaluator, 30 traces |
| 5 | Option (d) can produce a VIOLATION on some word | **VERIFIED-EXPERIMENT** — F4, real Phase D algorithm |
| 6 | …but that word is unreachable under (d); (d) is vacuous | **VERIFIED-EXPERIMENT** — F4, invariant ∩ ¬φ = ∅, two independent tools |
| 7 | Option (b) distinguishes correct from inverted lifecycle | **VERIFIED-EXPERIMENT** — F5 |
| 8 | Split states survive Phase B stuttering collapse | **VERIFIED-SOURCE** — `lifter.cpp:551-557`, `stuttering_engine.py:170,344` |
| 9 | Phase C isomorphism is condition- and count-sensitive | **VERIFIED-SOURCE** — `are_isomorphic.hh:37-41`, `.cc:101-105` |
| 10 | Therefore the split must be uniform | **REASONED** — follows from 9 |
| 11 | Six named test assertions break; Python-track ones do not | **VERIFIED-SOURCE** — F8 line-by-line; not executed |
| 12 | `set_bpmn_tasks` already carries spec vocabulary to the lifter | **VERIFIED-SOURCE** — `lifter.cpp:101-103`, `pipeline.py:96-97` |
| 13 | Multi-action tasks conjoin onto one label | **VERIFIED-SOURCE** — `lifter.cpp:279-295` |
| 14 | Option (b) needs no Module 01 or WIR schema change | **REASONED** — split is a lifting-time decision |
| 15 | Recommend (b), uniform, C++-only for now | **REASONED** — design judgement |
| 16 | Python track's purpose doesn't require model checking | **REASONED** — maintainer's call, not verified intent |
| 17 | Post-change state/edge counts | **BUILD-DEPENDENT** — not confirmed |
| 18 | No non-count test failures among the 113 | **BUILD-DEPENDENT** — grep audit only, suite not run |
