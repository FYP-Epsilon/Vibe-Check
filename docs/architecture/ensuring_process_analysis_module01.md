# Module 01 — The "Ensuring Process": How It Works, Its Novelty, and How to Make It Stronger

## The Core Question

> "How does Module 01 know that its BPMN → LTLf translation was done correctly?"

This is the **meta-verification problem** — you're not just translating a diagram into rules, you need to PROVE the translation itself is faithful. Module 01 has a multi-layered system to do this. Let's break it down.

---

## Part 1: How the Ensuring Process Currently Works

Think of it like a **5-checkpoint security system** where each checkpoint catches different kinds of errors:

```
BPMN XML
   │
   ▼
┌──────────────────────────────────────────────────────────┐
│  CHECKPOINT 1: "Did we read the diagram correctly?"      │
│  Phase 1 Coverage Gate (≥95% nodes mapped)               │
│  ➜ Counts: did we find and map every task, gateway,      │
│    event in the XML? If we missed >5%, STOP.             │ // change this to 100%
└──────────────────────────────────────────────────────────┘
   │ PASS ✓
   ▼
┌──────────────────────────────────────────────────────────┐
│  CHECKPOINT 2: "Are all decisions fully defined?"        │
│  Phase 2 Guard Completeness (100% XOR resolution)        │
│  ➜ Every decision point must have ALL branches labeled.  │
│    If any "else" is missing, auto-generate the negation. │
│    If we CAN'T resolve it → hard crash (blocking).       │
└──────────────────────────────────────────────────────────┘
   │ PASS ✓
   ▼
┌──────────────────────────────────────────────────────────┐
│  CHECKPOINT 3: "Are the rules sensitive enough?"         │
│  Phase 3 Mutation Testing (100% kill rate target)        │
│  ➜ Deliberately break the diagram 20+ ways.             │
│    Check if our rules catch EVERY broken version.        │
│    If a broken version sneaks through → auto-synthesize  │
│    a new "killer" rule and re-test. Loop until 100%.     │
└──────────────────────────────────────────────────────────┘
   │ PASS ✓
   ▼
┌──────────────────────────────────────────────────────────┐
│  CHECKPOINT 4: "Does repairing rules weaken them?"       │
│  CGSR Over-Weakening Guard (≤5% regression tolerance)    │
│  ➜ If Phase 3 had to weaken/remove a rule, check that    │
│    overall detection didn't drop by more than 5%.        │
│    If it did → OverWeakeningException (STOP).            │
└──────────────────────────────────────────────────────────┘
   │ PASS ✓
   ▼
┌──────────────────────────────────────────────────────────┐
│  CHECKPOINT 5: "Is the quality metric trustworthy?"      │
│  SFI Monotonicity Invariant (≤5% violation rate)         │
│  ➜ If you damage a diagram MORE, the fidelity score      │
│    should go DOWN. If it ever goes UP, the metric        │
│    itself is broken. Empirically validated.              │
└──────────────────────────────────────────────────────────┘
   │ ALL PASS ✓
   ▼
  ✅ "Translation is verified"
```

### In Simple English, Each Checkpoint Does:

| Checkpoint | Analogy | What It Catches |
|---|---|---|
| **1. Coverage Gate** | "Did the scanner read every page?" | Missing tasks, skipped gateways, unparsed elements |
| **2. Guard Completeness** | "Does every crossroads have signs for ALL directions?" | Missing "else" branches, ambiguous decision points |
| **3. Mutation Testing** | "If I sabotage the blueprint, do the rules notice?" | Rules too weak to detect errors, blind spots |
| **4. Over-Weakening Guard** | "Did fixing one leak create ten new ones?" | Self-repair that accidentally destroys detection |
| **5. SFI Monotonicity** | "Does 'more damage = lower score' always hold?" | Broken quality metric that gives misleading numbers |

---

## Part 2: Does This Ensuring Process Have Its Own Novelty?

**Yes — but it's mixed.** Let me separate genuinely novel parts from standard engineering:

### ✅ What's Genuinely Novel

````carousel
### Novel Element 1: Mutation Testing on BPMN Specifications

**What it is:** Taking mutation testing (normally used to test *code test suites*) and applying it to test *temporal logic rule suites* extracted from *process models*.

**Why it's novel:**
- MutPy, PITest → mutate **source code** to test **unit tests**
- Wodel, MutaBPMN → mutate **BPMN models** to test **process compliance**
- Module 01 → mutates **the BPMN graph** to test whether **the LTLf rules extracted from it are complete enough**

This is a different target: you're not testing if a test suite is good, you're testing if a *specification extraction* is complete. Nobody else does this.

**Closest prior art:** Wodel (DSL for model mutants), MutaBPMN — but those test conformance checkers, not extraction completeness.
<!-- slide -->
### Novel Element 2: Self-Strengthening Refinement Loop

**What it is:** When a mutant survives (the rules didn't catch the error), the system automatically synthesizes a new rule to kill that specific mutant, then re-tests.

**Why it's novel:**
- Traditional mutation testing **reports** surviving mutants — a human writes new tests
- Module 01 **automatically synthesizes** new temporal logic constraints to kill survivors
- It's a closed-loop self-correction: detect gap → generate fix → verify fix → iterate

**Closest prior art:** Adaptive test generation (EvoSuite for Java), but that generates *test inputs*, not *specification rules*. Reactive synthesis (GR(1) games) auto-generates strategies, but from fixed specifications, not from detected gaps.
<!-- slide -->
### Novel Element 3: Over-Weakening Guard (CGSR)

**What it is:** When the system repairs its rules (weakens or removes a failing rule), it checks that the repair didn't accidentally destroy the suite's detection power.

**Why it's novel:**
- Self-repairing systems exist (automated program repair — GenProg, etc.)
- But they rarely have a **formal guard against regression** — they just check the original failing test passes
- Module 01's guard measures detection on an **external set** and rejects repairs that drop detection >5%
- This prevents the "repair death spiral" where fixing one issue breaks five others

**Closest prior art:** Regression test selection in CI/CD, but applied to test suites not specification suites. The explicit over-weakening bound with a mathematical threshold is novel.
<!-- slide -->
### Novel Element 4: SFI Monotonicity as a Meta-Verification

**What it is:** The Specification Fidelity Index has a **provable mathematical property**: if you damage a diagram more, the SFI must go down. If it doesn't, the metric itself is broken.

**Why it's novel:**
- Most quality metrics in BPM are ad-hoc (7PMG, SEQUAL) with no formal properties
- SFI has a **structural monotonicity guarantee** that can be empirically validated
- This is a "metric that checks itself" — if the monotonicity test fails, you know the metric is unreliable

**Closest prior art:** Mutation score in testing is monotone by construction (more mutants killed = higher score). SFI's novelty is applying monotonicity to a *fidelity metric* on graph similarity, where it's not trivially guaranteed (GED normalization CAN be non-monotone).
````

### ❌ What's Standard Engineering (Not Novel)

| Mechanism | Why It's Not Novel |
|---|---|
| Coverage gate (≥95% node mapping) | Standard coverage metrics — same as code coverage tools | //should be 100%
| Guard completeness (100% XOR resolution) | Input validation — standard in any parser |
| Sequential phase gates | Standard pipeline pattern (CI/CD, compiler passes) |
| Certificate output (JSON reports) | Standard observability/logging |
| Phase 4 round-trip (LTLf → automaton → language inclusion) | Well-established in model checking (SPOT, ltlf2dfa do this) |

---

## Part 3: How to Increase Both Novelty AND Reliability

Here are **6 concrete proposals** ranked by impact. Each adds a genuinely new verification mechanism that doesn't exist in the literature for BPMN→LTLf translation.

### Proposal 1: Metamorphic Relations for BPMN→LTLf Translation ⭐⭐⭐

> [!IMPORTANT]
> This is the highest-impact addition — genuinely novel in this context, directly testable, and it catches a DIFFERENT class of bugs than mutation testing.

**The idea:** Define algebraic rules that the translation MUST obey. If any rule is violated, the translation has a bug — regardless of whether the output "looks right."

**Metamorphic relations (MRs):**

| MR | If you do this to the BPMN... | ...the LTLf rules MUST change like this |
|---|---|---|
| **MR-1: Task Addition** | Insert task T between A→B (making A→T→B) | Must gain ordering rules: `!start(T) U done(A)` and `!start(B) U done(T)`. Must lose: direct `!start(B) U done(A)` |
| **MR-2: Task Deletion** | Remove task T from A→T→B (making A→B) | Must lose all rules mentioning T. Must gain: `!start(B) U done(A)` |
| **MR-3: Branch Addition** | Add branch C to XOR{A,B} making XOR{A,B,C} | Must gain: mutex pairs (A,C) and (B,C). Existing (A,B) unchanged |
| **MR-4: Branch Removal** | Remove branch B from XOR{A,B} making XOR{A} | Must lose: all mutex pairs involving B. Warning: XOR with 1 branch is degenerate |
| **MR-5: Gateway Swap** | Change XOR to AND | Must lose: mutex rules. Must gain: concurrent-execution rules |
| **MR-6: Idempotent Re-extraction** | Extract rules twice from the same BPMN | Identical output both times (determinism check) |
| **MR-7: Semantic-Preserving Refactor** | Inline a subprocess (flatten its children into the parent) | Rule set must be **trace-equivalent** (same accepted behaviors) |

**Why this is novel:**
- Metamorphic testing is used for ML models, compilers, databases — but NOT for BPMN→LTLf specification extraction
- Each MR provides a **correctness oracle without needing gold-standard labels**
- It catches bugs that mutation testing CANNOT: mutation testing checks sensitivity (do rules detect errors?), metamorphic testing checks **faithfulness** (are the right rules generated?)

**Implementation sketch:**
```
src/meta_relations.py
├── apply_mr(bpmn_xml, mr_type) → (modified_bpmn, expected_rule_delta)
├── verify_mr(original_rules, modified_rules, expected_delta) → bool
└── run_all_mrs(bpmn_xml) → MetamorphicReport

tests/test_metamorphic.py
├── test_mr1_task_addition()
├── test_mr2_task_deletion()
├── ...
```

---

### Proposal 2: Differential Verification Against bpmn2constraints ⭐⭐⭐

**The idea:** Run the same BPMN through BOTH Module 01 AND the independent `bpmn2constraints` library. Compare the generated constraints. Disagreements = potential bugs.

**Why this is novel:**
- N-version programming is well-known, but applying it to **specification extraction** (not code execution) is novel
- `bpmn2constraints` generates LTLf/DECLARE constraints from the same BPMN input
- Two independent implementations extracting the same rules provides a **cross-validation oracle**

**The key insight:** If Module 01 says "Task A must happen before Task B" but `bpmn2constraints` says no such constraint exists, one of them is wrong. This catches:
- Template bugs (like the backwards sequence template that was found)
- Missing rules (extraction gaps)
- Extra/spurious rules (over-specification)

**How it differs from existing N-version approaches:**
- N-version programming runs the same *specification* through multiple *implementations*
- This runs the same *input* through multiple *specification extractors* and compares *outputs*
- It's more like differential testing (à la CSmith for C compilers) than N-version execution

**Implementation sketch:**
```
eval/differential_checker.py
├── extract_with_m01(bpmn_xml) → Set[LTLf_Rule]
├── extract_with_b2c(bpmn_xml) → Set[DECLARE_Constraint]
├── normalize_to_common(m01_rules, b2c_constraints) → (Set, Set)
├── compare(set_a, set_b) → DifferentialReport
│   ├── agreed: rules both extractors produce
│   ├── m01_only: rules only Module 01 produces
│   ├── b2c_only: rules only bpmn2constraints produces
│   └── contradictions: directly conflicting rules
```

> [!TIP]
> The `agreed` set gives you HIGH-CONFIDENCE rules. The `m01_only` and `b2c_only` sets are where bugs hide. This naturally produces a **confidence-weighted rule suite** — another potential novel contribution.

---

### Proposal 3: Compositional Verification with Pattern Proofs ⭐⭐

**The idea:** Instead of verifying the entire translation end-to-end (expensive, hard to debug), verify it **per BPMN pattern** and prove that correct translations compose correctly.

**How it works:**

```
Step 1: Define canonical BPMN micro-patterns
  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
  │  Sequence    │  │  XOR Split  │  │  AND Join   │
  │  A → B → C  │  │  ⬦→{A,B}   │  │  {A,B}→⬦   │
  └─────────────┘  └─────────────┘  └─────────────┘

Step 2: For each micro-pattern, prove the translation is correct
  - Sequence: produces ordering rules ✓ (proven once)
  - XOR: produces mutex + coverage rules ✓ (proven once)
  - AND: produces concurrency rules ✓ (proven once)

Step 3: Prove the COMPOSITION THEOREM
  "If pattern P₁ is correctly translated and pattern P₂ is
   correctly translated, then P₁∘P₂ (P₁ composed with P₂
   via shared boundary nodes) is correctly translated."

Step 4: Any BPMN diagram decomposes into micro-patterns
  → Composition theorem guarantees the whole translation is correct
```

**Why this is novel:**
- Compositional verification exists for hardware (assume-guarantee) and concurrent programs
- Applying it to **BPMN→LTLf extraction** — decomposing a process model into verified patterns and proving composition — is new
- Closest prior art: compositional LTLf→DFA translation (Bansal et al., AAAI), but that composes *formulas*, not *extraction from models*

**Reliability gain:** Instead of hoping end-to-end testing catches all bugs, you get **modular guarantees** — fix a pattern once, it's correct everywhere that pattern appears.

---

### Proposal 4: Trace-Equivalence Sanity Check (Zero False-Alarm Gate) ⭐⭐

**The idea:** Before any mutation testing or downstream use, verify that **the original unmutated diagram satisfies its own rules**. If it doesn't, the translation is definitely wrong.

**Why this matters:** This was literally the bug that killed Module 01 — the backwards sequence template caused the rules to reject the correct process. A simple "does the original pass its own rules?" check would have caught this immediately.

```
                    ┌─────────────────────────────────────┐
                    │  CHECKPOINT 0: SANITY CHECK         │
    BPMN ──────┐    │                                     │
               │    │  Generate traces from BPMN graph    │
    LTLf ──────┤───▶│  Evaluate ALL rules on ALL traces   │
    Rules      │    │  If ANY rule fails → TRANSLATION    │
               │    │  IS WRONG (abort, don't proceed)    │
                    └─────────────────────────────────────┘
```

**Why this is novel (as a formal checkpoint):**
- Obviously "test your own output" sounds basic
- But formalizing it as a **mandatory quality gate with a name** (e.g., "Reflexive Consistency Gate") with a formal property ("a sound extraction must be reflexively consistent: the source model satisfies its own extracted specification") is publishable
- The interesting part: this is a **necessary but not sufficient** condition for correctness — you can prove that any violation here means the translation is unsound, but passing doesn't guarantee soundness
- Combined with mutation testing (which tests sufficiency), you get a **sound-and-complete verification sandwich**

**This also enables a new metric:**
> **Reflexive Consistency Rate (RCR)** = fraction of diagrams where the extracted rules accept the original graph's traces. Must be 1.0 for a sound extractor. Currently it's ≈ 0.0 (the backwards template bug).

---

### Proposal 5: Confidence-Stratified Property Suite ⭐⭐

**The idea:** Not all extracted rules are equally trustworthy. Assign a **confidence score** to each rule based on how it was verified:

| Confidence Level | How It Was Verified | Score |
|---|---|---|
| **Gold** | Agreed by both Module 01 AND bpmn2constraints (Proposal 2) | 1.0 |
| **Silver** | Passed metamorphic relation checks (Proposal 1) | 0.85 |
| **Bronze** | Survived mutation testing (killed all relevant mutants) | 0.7 |
| **Copper** | Generated by pattern template, no independent verification | 0.5 |
| **Synthesized** | Auto-generated "killer" rule from Phase 3 refinement | 0.3 |

**Why this is novel:**
- Existing specification extraction outputs flat rule sets — all rules are treated equally
- Confidence-stratified suites let Module 03 make **risk-aware decisions**: trust gold rules absolutely, flag copper rules for manual review
- This is like how ML systems output prediction probabilities, not just labels — but applied to formal specifications

**The novelty for the thesis:**
> "To our knowledge, this is the first confidence-stratified temporal specification suite, where each extracted LTLf property carries a provenance-based confidence score derived from independent verification mechanisms."

---

### Proposal 6: Behavioral Equivalence Classes for Mutation Filtering ⭐

**The idea:** Current mutation testing counts "killed" mutants, but some mutants are **semantically equivalent** to the original (they look different but behave identically). Killing those is meaningless.

**The improvement:** Formally classify mutants into behavioral equivalence classes before testing:

```
All Mutants
├── Behaviorally Equivalent (same traces as original)
│   ├── Cosmetic changes (rename, reorder XML)
│   └── Structurally different but trace-identical
│       → These SHOULD survive. Killing them = false alarm.
│
└── Behaviorally Distinct (different traces)
    ├── Killed by existing rules ✓ (sensitivity confirmed)
    └── Surviving ✗ (gap detected → synthesize killer)
```

**Why this matters:** The current code already filters equivalent mutants (`mutation_refiner.py` L47-52), but it's basic dict comparison. A proper equivalence-class analysis using trace-language comparison would:
1. Prevent inflated kill ratios (killing equivalent mutants doesn't prove anything)
2. Focus refinement on genuinely dangerous survivors
3. Provide a **specificity metric** (false alarm rate on equivalent mutants)

---

### Proposal 7: Reverse Process Mining Alignment for Specification Validation ⭐⭐⭐

> [!IMPORTANT]
> This is a **transformative** addition — it bridges two entire research communities (process mining and formal verification), provides quantitative fitness/precision/generalization metrics for the extraction itself, and leverages battle-tested algorithms in a completely novel context.

**The idea:** Use process mining alignment algorithms (Adriansyah et al.) **in reverse**. Instead of aligning event logs to a process model (the standard use), align the **extracted LTLf specification** back to the **original BPMN model** to quantify extraction fidelity.

**How it works:**

```
Standard Process Mining:     Event Logs  ──align──▶  Process Model
                             (observed)               (expected)

Reverse Alignment:           LTLf Rules  ──align──▶  BPMN Model
                             (extracted spec)         (source truth)

What you get:
┌─────────────────────────────────────────────────────────────────┐
│  FITNESS:        Do the extracted rules accept all traces      │
│                  that the BPMN model allows?                   │
│                  Low fitness = under-specification              │
│                                                                 │
│  PRECISION:      Do the extracted rules reject all traces      │
│                  that the BPMN model forbids?                  │
│                  Low precision = over-permissive rules           │
│                                                                 │
│  GENERALIZATION: Do the rules generalize correctly to unseen   │
│                  valid traces (not just the ones tested)?       │
│                  Low generalization = overfitting to test set   │
└─────────────────────────────────────────────────────────────────┘
```

**Why this is genuinely transformative:**
- Process mining alignment is well-established (Adriansyah 2014, implemented in PM4Py/ProM) but **always** used for conformance checking: event logs vs. process model
- Using it for **specification validation** (extracted rules vs. source model) is an entirely novel application — nobody has done this
- It provides **three quantitative metrics** (fitness, precision, generalization) that are well-understood in the process mining community, applied to a formal verification context
- It creates a **publishable bridge** between two research communities that rarely interact
- The alignment computation also produces **diagnostic information**: exactly which rules misalign, at which process points, enabling targeted repair

**Closest prior art:**
- Conformance checking (van der Aalst et al.) — but checks execution logs, not extracted specifications
- Token-based replay (Rozinat & van der Aalst 2008) — similar metrics but on observed behavior, not formal properties
- The key novelty: treating an LTLf rule suite as a "behavioral description" that can be aligned against its source model

**Key insight — why this catches bugs others can't:**
- Mutation testing asks: "Do the rules detect errors?" (sensitivity)
- Metamorphic testing asks: "Do the rules change correctly?" (faithfulness of transformation)
- Reverse alignment asks: "Do the rules **mean** the same thing as the diagram?" (semantic equivalence)
- This is the only proposal that directly measures **semantic fidelity** — how much meaning was preserved in translation

**Implementation sketch:**
```
src/alignment_validator.py
├── bpmn_to_petri_net(bpmn_xml) → PetriNet
│   # Convert BPMN to Petri net (standard, pm4py has this)
├── ltlf_to_trace_set(rules, bound=k) → Set[Trace]
│   # Generate traces accepted by the LTLf conjunction
│   # (bounded unrolling via ltlf2dfa → DFA → enumerate paths)
├── compute_alignment(petri_net, trace_set) → AlignmentResult
│   # Standard alignment algorithm (Adriansyah)
│   # Returns fitness, precision, generalization
├── diagnose_misalignment(alignment) → List[MisalignmentPoint]
│   # For each misaligned trace, identify the exact process
│   # point where the specification diverges from the model
└── validate_extraction(bpmn_xml, ltlf_rules) → ValidationReport
    # Full pipeline: convert, align, diagnose
    # Returns: fitness, precision, generalization scores
    #          + per-rule alignment diagnostics
    #          + suggested rule repairs

tests/test_alignment_validation.py
├── test_perfect_extraction()      # fitness=1.0, precision=1.0
├── test_under_specified()         # fitness<1.0 (missing rules)
├── test_over_specified()          # precision<1.0 (spurious rules)
├── test_backwards_template_bug()  # fitness≈0.0 (known failure)
```

**New metric this enables:**
> **Extraction Alignment Score (EAS)** = harmonic mean of fitness and precision (F1-style). A sound and complete extraction has EAS = 1.0. The backwards template bug would produce EAS ≈ 0.0. This is a single-number summary of extraction quality that is directly comparable across different extraction approaches.

**Integration with existing proposals:**
- Feeds into Proposal 5 (Confidence Stratification): rules with high individual alignment fitness get higher confidence
- Validates Proposal 1 (Metamorphic Relations): alignment scores should change predictably under MR transformations
- Complements Proposal 4 (Reflexive Consistency): RCR is a binary version of alignment fitness — alignment generalizes it to a continuous metric

---

## Summary: The Ensuring Process — Current vs. Proposed

| Dimension | Current State | With Proposals | Novelty Gain |
|---|---|---|---|
| **Bug classes caught** | Sensitivity gaps (mutation), coverage drops, guard gaps | + Faithfulness bugs (metamorphic), cross-tool disagreements (differential), composition errors, semantic divergence (alignment) | 4 new bug classes |
| **Verification independence** | Self-referential (tests own output with own tools) | + External oracle (bpmn2constraints), algebraic invariants (MRs), process mining alignment | Breaks circularity |
| **Confidence granularity** | Binary (PASS/FAIL per phase) | + Per-rule confidence scores with provenance, continuous alignment fitness/precision | Continuous, not binary |
| **Soundness guarantee** | None (backwards template passed all gates) | + Reflexive Consistency Gate catches this class entirely | Formal necessary condition |
| **Semantic fidelity** | Untested (no measure of how much meaning is preserved) | + Alignment fitness/precision/generalization quantify meaning preservation | First quantitative fidelity measure |
| **Compositionality** | Monolithic end-to-end | + Pattern-level proofs with composition theorem | Modular guarantees |
| **Publishable novel mechanisms** | 4 (mutation on specs, self-strengthening, over-weakening guard, SFI monotonicity) | + 6 (metamorphic relations, differential extraction, compositional proofs, reflexive consistency, confidence stratification, reverse alignment) | **10 total** |

> [!TIP]
> **Recommended implementation order for maximum thesis impact:**
> 1. **Reflexive Consistency Gate** (Proposal 4) — trivial to implement, catches the worst current bug, gives you a named contribution
> 2. **Reverse Process Mining Alignment** (Proposal 7) — transformative novelty, bridges two research communities, provides quantitative semantic fidelity metrics, leverages existing PM4Py infrastructure
> 3. **Metamorphic Relations** (Proposal 1) — highest structural novelty, directly publishable, catches bugs mutation testing can't
> 4. **Differential Verification** (Proposal 2) — practical, leverages existing tool, provides the confidence stratification input
> 5. **Confidence Stratification** (Proposal 5) — ties 1–4 together into a unified framework (now enriched with alignment scores)
> 6. **Compositional Verification** (Proposal 3) — strongest theoretically, but hardest to implement
> 7. **Equivalence Classes** (Proposal 6) — refines existing mutation testing, less novel but more rigorous

---

## The Thesis Narrative This Creates

> "Module 01 doesn't just extract specifications — it subjects them to a **6-layer verification gauntlet** combining coverage analysis, guard completeness, mutation-based sensitivity testing with self-strengthening refinement, metamorphic relation checking for faithfulness, differential cross-validation against an independent extraction tool, and **reverse process mining alignment** that quantifies semantic fidelity via fitness, precision, and generalization metrics borrowed from conformance checking. Each layer catches a distinct class of translation error, and the confidence-stratified output — enriched with per-rule alignment diagnostics — enables downstream modules to make risk-aware decisions. To our knowledge, this is the first BPMN specification extraction pipeline with formally characterized verification properties (reflexive consistency, metamorphic invariance, over-weakening bounds, SFI monotonicity, and **alignment-based semantic fidelity**), and the first to apply process mining alignment algorithms to validate specification extraction rather than log conformance."

This is a genuinely strong story — and most of it is implementable.
