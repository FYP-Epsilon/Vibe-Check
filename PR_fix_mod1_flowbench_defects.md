# fix(mod1): three FlowBench-diagnosed defects in the Specification Engine

`fix/mod1/flowbench-defects` → `main-demo` (base `9165513`)

Fixes the three defects the FlowBench evaluation design memo diagnosed in
`module_01_spec`, each verified against the full 148-diagram FLOW-BENCH corpus
(100 `output` + 48 `context`, seed 42). Changes are confined to
`module_01_spec/` — 4 source files, 5 test files, no other module touched.

**Evidence classes** follow the memo's convention: `[SRC]` read directly from
source, `[MEAS]` measured in this session, `[EXP]` explanatory,
`[REAS]` reasoning.

---

## Headline before → after

| Metric (148 diagrams) | Before | After |
|---|---|---|
| Suites admitting their own diagram (soundness) `[MEAS]` | 79/148 | **145/148** |
| — branching diagrams | 0/50 | **49/50** |
| — non-branching diagrams | 79/98 | **96/98** |
| Phase 4 `FAIL_WITH_ERRORS` `[MEAS]` | 148/148 | **4/148** |
| Phase 4 real v2.0 PBCTS certificate `[MEAS]` | 0/148 | **90/148** |
| Connected mutants recorded as surviving `[MEAS]` | 13 | **1231** |
| Property kills attributable to a *sound* suite `[MEAS]` | 0 | 0 (now visible, see §2/§3) |

Tests: **0 → 56 passing** (35 pre-existing in-repo + 21 added here).

---

## 1. P2 loop bound was carried in-band, making the formula unparseable

**Commit** `a3acf0b`

`[SRC]` `_generate_sentinels` appended the P2 bounded-loop property as
`"/* loop_bound=10 */ G(start -> F(done))"`. `[SRC]` `ltlf_eval.TOKEN_SPEC`
has no comment syntax, so `evaluate_ltlf` raised `ValueError` on Module 01's
own synthesised property. `[MEAS]` Phase 4 returned `FAIL_WITH_ERRORS` on
**148/148** diagrams with the identical message.

**Fix.** The bound is now a typed field on `FLTLSynthesizer.spec_metadata`
(`loop_bound_documented`), and the formula is left as well-formed LTLf.
`export_for_module_03` reads the structured field instead of regexing the
comment out of formula text.

`[REAS]` **The trap this avoids:** deleting the comment alone would have made
the formula parse while silently zeroing the downstream bound extraction — and
the pre-existing `test_loop_bound_defaults_to_zero_when_undocumented` would
have kept passing against a permanently-zero extractor. Both halves are pinned
in `test_loop_bound_decoupling.py`.

### 1b. A second defect this one was masking

`[MEAS]` With only the above fixed, Phase 4 produced a real certificate on just
**14/148**; the remaining 134 failed on a *different* parse error.
`[SRC]` `semantic_extractor` emits `node({name})` for every non-task node, but
`TOKEN_SPEC` had rules only for `start(...)` and `done(...)` — so every P0
sentinel and P1 control-flow property over a node proposition was unparseable.
Adding a `NODE_ATOM` rule took Phase 4 to a real certificate on **148/148** at
that point in the branch. Pinned in `test_node_atom_tokenization.py`, including
a semantic assertion that the new atom is satisfied by membership rather than
being vacuously true.

**Test-literal update, disclosed:** `test_status_code_consistency.py` had two
hardcoded `PASS_PBCTS_UNCONVERGED` literals. `[MEAS]` That fixture only reached
the non-convergence branch *because* its properties were unparseable; it now
converges honestly (SCov 1.0, 129/129 obligation nodes). The invariant the test
exists to protect — `api.py` and `main.py` never labelling one outcome two
different ways — is unchanged and still asserted.

---

## 2. Disconnection kills and property kills were scored identically

**Commit** `e9c426b`

`[SRC]` `LTLfAuditor.is_killed()` returned `True` whenever a mutant produced no
complete trace (`if not traces: return True`) **without consulting a single
property**. `[REAS]` These two events are not interchangeable as evidence: a
property kill measures suite strength, whereas a disconnection kill would be
detected just as reliably by an *empty* property suite. Both fed one
`mutants_killed_ratio`, which read **1.0 on all 148 diagrams**.

**Fix.** New `classify_kill()` returns `(killed, mechanism, detail)` with
mechanism in `{KILL_BY_PROPERTY, KILL_BY_DISCONNECTION, NOT_KILLED}`.
The Phase 3 certificate gains four append-only fields:
`mutants_killed_by_property`, `mutants_killed_by_disconnection`,
`property_kill_ratio`, `kill_evidence_vacuous`.

`[REAS]` **`is_killed()`'s 2-tuple contract is deliberately unchanged.**
GitNexus rates `execute_validation_pipeline` **HIGH risk** (15 impacted
symbols, 3 direct callers, on the `verify_spec` flow reaching
`demo/e2e_demo.py` and `demo/eval_e2e/harness.py`, both out of scope for this
branch). The mechanism is therefore exposed through a *new* method plus
*append-only* fields rather than by changing any existing contract.

`[MEAS]` **The gate is also deliberately unchanged.** Immediately after this
fix, corpus-wide: 1248 property kills vs 1712 disconnection kills
(`property_kill_ratio` 0.4216), with **81/148** diagrams passing Phase 3 on
zero property evidence. Tightening the gate to require property kills would
fail 81/148 diagrams — that is a scoring-policy change, not a defect fix, on a
HIGH-risk path. The vacuity is made *visible* via `kill_evidence_vacuous`
instead of being silently repaired.

---

## 3. P4 completion obligations were not tier-correct on branching diagrams

**Commit** `bff92f1`

`[SRC]` `_generate_sentinels` emitted an unconditional `F(done(X))` for **every**
task. `[EXP]` That asserts X completes on every execution — true only for a task
on every start→end path. For a task behind a gateway it is false on any trace
taking the other branch, and `_generate_traces` enumerates each branch
separately. The suite therefore rejected the diagram it was derived from.
`[MEAS]` Before: **0/50** branching diagrams had a sound suite.

### Both candidate repairs were measured, not argued

All 148 diagrams, on the post-fix-1/2 tree:

| Candidate | Sound | P4 obligations kept | Still unconditional |
|---|---|---|---|
| A — `F(done)` only for mandatory tasks, dropped elsewhere | 145/148 | 242 / 437 | 242 |
| B — every `F(done)` weakened to `G(start → F(done))` | 145/148 | 437 / 437 | 0 |
| **CHOSEN — hybrid** | **145/148** | **437 / 437** | **242** |

`[REAS]` A and B tie on soundness but each pays something: A discards 195
obligations entirely, B needlessly weakens the 242 claims that were valid. The
hybrid — strong claim where the task is mandatory, conditional form elsewhere —
**strictly dominates both**: identical soundness with strictly more information
retained. This third option was not in the memo; it was found by measuring A and
B and noticing they trade against each other rather than against soundness.

`[SRC]` Mandatory nodes are computed as the intersection of all simple start→end
paths via iterative DFS — deliberately matching how `_generate_traces`
enumerates traces, since a disagreement there would reintroduce the defect. No
new module dependency (`networkx` is not imported by the synthesizer).

`[MEAS]` **Residual 3 unsound diagrams are a different defect:**
`output/uid_67`, `output/uid_8`, `context/uid_92` have two distinct task
node-ids collapsing to one atomic proposition, which the memo diagnoses
separately and scopes out. Pinned in the test module so the two cannot be
conflated.

### Consequence, reported rather than smoothed over

`[MEAS]` The removed obligation was *also* killing mutants. Corpus-wide,
property kills fall **1248 → 168**, and **54/148** diagrams no longer pass the
Phase 3 gate — their suites genuinely cannot kill a connected mutant.
`[REAS]` This is a truthful measurement replacing a flattering one. Combined
with §2, it means Phase 3's uniform 1.0 kill ratio was resting on an unsound
property and on disconnection, not on suite strength. Pinned as an explicit
test rather than left to be rediscovered by re-measurement.

---

## Pilot outputs, before → after

`crosstab.py` — suite soundness × kill mechanism:

```
BEFORE                                   AFTER
sound=True  disconnect->killed   1580    sound=True  connected->SURVIVED   1228
sound=False connected->SURVIVED    13    sound=True  disconnect->killed    1672
sound=False property-killed      1235    sound=False connected->SURVIVED      3
sound=False disconnect->killed    132    sound=False property-killed         17
                                         sound=False disconnect->killed      40

on SOUND-suite diagrams:                 on SOUND-suite diagrams:
  mutants 1580, survived 0                 mutants 2900, survived 1228 (42.3%)
  property kills 0 (0.0%)                  property kills 0 (0.0%)
```

`[EXP]` The sound-suite population grows 79 → 145 diagrams, so far more mutants
are now interpretable at all. Within them, connected mutants are honestly
recorded as *surviving* instead of being killed by a property that also rejected
the original diagram.

`invalidate.py` — structural node/edge F1 stays **1.0000** on all four
corpus/element combinations (682 nodes, 576 edges output; 342/293 context; zero
fp/fn), confirming these fixes did not perturb extraction. Sound-suite diagrams
with zero properties: 0/79 → 0/145.

`mutdiag.py` — unchanged by design (2960 mutants, all
`sequence_flow_deletion`, 1712 without traces). It measures the mutation engine,
which this branch does not touch; identical output is the expected result.

`phase4_sound.py` — soundness 79/148 → **145/148** (branching 0/50 → 49/50).

> `[MEAS]` **Bug found in the pilot script itself, not in Module 01:**
> `phase4_sound.py` reports Phase 4 status via `cert.get('status')`, but a
> *successful* `phase_4_certificate` has no `status` key — only the
> `FAIL_WITH_ERRORS` error stub sets one. The script therefore prints `None`
> for every success. Corrected measurement (`after/phase4_status_corrected.txt`):
> **90** real v2.0 certificates, **54** aborted at the Phase 3 gate, **4**
> `FAIL_WITH_ERRORS`.

---

## A fifth defect found and NOT fixed here

`[MEAS]` The 4 remaining `FAIL_WITH_ERRORS` diagrams (`output/uid_20`,
`uid_21`, `uid_28`, `uid_69`) fail on `'!node(Event_1ycwwda) W node()'` and
`'!node() W done(...)'` — `semantic_extractor` emits an **empty proposition
name**. `[REAS]` That is a genuine extractor defect, not a tokenizer gap, and
is out of scope for this branch. Recorded here so it is not mistaken for
residue of defect #1.

---

## Impact analysis (GitNexus)

| Symbol | Risk | Impacted | Direct |
|---|---|---|---|
| `_generate_sentinels` | LOW | 5 | 1 |
| `evaluate_ltlf` | LOW | 2 | 1 |
| `export_for_module_03` | LOW | 10 | 3 |
| `is_killed` | LOW | 0 | 0 |
| **`execute_validation_pipeline`** | **HIGH** | **15** | **3** |

`[REAS]` The single HIGH-risk finding drove the §2 design: append-only fields
and a new method, so no existing caller's contract changes. `detect-changes`
after each commit confirmed every changed symbol lies inside `module_01_spec/`
and every affected execution flow is the `verify_spec` synthesis path.

`[SRC]` Verified independently: nothing outside `module_01_spec` reads
`loop_bound_documented`. Module 03's `property_ingest.py` does not consume it,
so the §1 change does not cross the module boundary.

---

## Tests added (21 new, 56 total passing)

- `test_loop_bound_decoupling.py` — both halves of §1; guards the
  parse-but-silently-zero trap.
- `test_node_atom_tokenization.py` — §1b; both failure shapes, a semantics
  assertion, and a guard that the inserted ordered rule does not shadow the two
  atom forms that already worked.
- `test_kill_mechanism_accounting.py` — §2; each mechanism separately, the
  disconnection kill firing even with an **empty** suite (the direct
  demonstration that it is not evidence of suite strength), decomposition
  summing to the headline count, and `is_killed`'s tuple shape guarded on
  account of its HIGH-risk consumers.
- `test_p4_completion_tier_semantics.py` — §3; optional vs mandatory task
  forms, no obligation lost, soundness on both a fixture and a real corpus
  branching diagram, and the Phase 3 kill-rate consequence.
- `test_status_code_consistency.py` — updated literals, disclosed above.

`[REAS]` Tests are built on real corpus diagrams wherever the defect was
measured corpus-wide, rather than on hand-written fixtures that can be
accidentally easy.

### One fixture repinned, disclosed

`test_loop_bound_decoupling.py`'s corpus fixture moves from `uid_100` to
`uid_11`. `[MEAS]` After §3, `uid_100` aborts at the Phase 3 gate, so its
result dict has no `phase_2`/`phase_4` keys and the §1 assertions could not run
end-to-end. `uid_11` still completes all five phases. The reason is recorded in
the fixture docstring, since the abort is a true finding about `uid_100`'s
suite rather than a regression in §1.

---

## What this branch does *not* claim

`[REAS]` Phase 3's kill ratio is still not evidence of property-suite strength:
on sound-suite diagrams, property kills remain **0**. This branch makes that
fact *visible* (§2) and stops an unsound property from concealing it (§3); it
does not make the suite stronger. The gate threshold is unchanged and no
scoring policy was altered.
