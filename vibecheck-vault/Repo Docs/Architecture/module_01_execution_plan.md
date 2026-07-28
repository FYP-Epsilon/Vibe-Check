> [!info] Imported from repo docs
> Source: `docs/architecture/module_01_execution_plan.md` @ main `7089711` (2026-07-28). `docs/` was removed from the repo (develop @ `05fae60`, 2026-07-28) after this import — **this vault copy is now the surviving snapshot** (git history retains the originals).

# Module 01: Formal Specification Engine — E2E Execution Plan & Deep Technical Reference

**Prepared for:** VibeCheck Framework
**Classification:** Technical Deep-Dive / Implementation Architecture
**Status:** 100% Implemented & Hardened

---

## 1. Executive Summary

Module 01 is the **AI-Native Formal Specification Engine** for the VibeCheck framework. Its core responsibility is to translate human-readable business logic (BPMN 2.0 XML) into strict, mathematically verifiable Linear Temporal Logic (LTLf) properties. 

However, unlike traditional, passive parsers, Module 01 operates as a **Predictive AI Defense System**. It actively mutates the logic graph and utilizes an **Adversarial Red-Teaming LLM** to hallucinate deceptive logic bypasses, automatically compiling defenses against vulnerabilities before the downstream AI even writes the code.

---

## 2. The E2E Master Execution Pipeline (Phases 1–4)

Module 01 is structured into a rigorous 4-phase pipeline. Every phase enforces a mathematical **Quality Gate**. If a gate fails, the system halts with a detailed certificate of failure.

### Phase 1: Semantic Extraction (Syntactic Sanitization)
**Objective:** Parse the BPMN XML, strip UI/DI elements, and extract a clean semantic Kripke structure.
* **V3 Sanitization:** Removes presentation layers (`bpmndi:BPMNDiagram`).
* **V2 Labeling:** Assigns atomic propositions to states. Tasks are split into `start(Task)` and `done(Task)`.
* **V1 Certification:** Validates Node Coverage. If $C_{struct}$ < 1.0, the pipeline halts.

### Phase 2: LTLf Synthesis (Logic Instantiation)
**Objective:** Translate the semantic graph into strict LTLf temporal formulas.
* **Zero Dead-Zone Protocol:** Automatically infers missing implicit "Else" conditions on XOR gateways to prevent logic gaps.
* **Property Suites:** Synthesizes `P0_Critical_Sentinels` (tasks must start before they finish), `P1_Structural_Control_Flow` (gateway and sequence logic), and `P2_Quality_Limits` (bounded loop limits).

### Phase 3: PWBE Mutation & Adversarial Red-Teaming (The Core Novelty)
**Objective:** Proactively test and harden the LTLf property suite against structural and AI-hallucinated failures.
* **PWBE (Property-Weighted Bisimulation Equivalence):** Intentionally mutates the semantic graph (e.g., swapping AND for XOR) to ensure the LTLf auditor successfully catches structural regressions.
* **Adversarial Formal Specification:** Injects an LLM agent to hallucinate deceptive traces (e.g., skipping payment tasks while making the workflow look valid). The engine algorithmically compiles these hallucinations into `P3_Adversarial_Defenses` (Killer Properties).

### Phase 4: PBCTS (Progression-Based Constructive Trace Synthesis)
**Objective:** A-priori Formal Verification without C++ or graph circularity.
* **Inverted Progression Enumeration:** Synthesizes theoretical execution traces strictly from the LTLf formulas without generating automata.
* **BDA (Bidirectional Differential Alignment):** Cross-compares formula traces against semantic graph traces to calculate exact set-difference extraction scores (EAS_BDA).
* **IDCD (Iterative Deepening Convergence):** Automatically finds the necessary execution length bounds for completeness verification.

---

## 3. Deep Dive: Adversarial Formal Specification (LLM Red-Teaming)

### The Academic Gap
Traditionally, formal specification engines are passive. They read a diagram and extract structural properties. However, Generative AI models do not fail in predictable, structural ways. They suffer from **Deceptive Hallucinations**—generating code that *appears* structurally sound but contains hidden logical bypasses.

### The Breakthrough Solution
Module 01 actively attacks its own specifications. 
1. **Adversarial Trace Hallucination:** A local LLM is mathematically prompted to intentionally hallucinate "adversarial traces" (workflow executions that bypass the business rules while trying to look valid).
2. **Auto-Compilation of "Killer Properties":** Module 01 parses the adversarial trace, identifies the topological anomaly, and synthesizes a negated LTLf formula (e.g., `!(F(done(Ship) & !O(done(Payment))))`) to strictly forbid that specific temporal sequence from ever occurring.

This concept—using adversarial AI generation to automatically synthesize and harden formal logic proofs prior to code execution—is a PhD-level novelty unique to VibeCheck.

---

## 4. Decoupled Handoff (The JSON Payload API)

Module 01 is perfectly decoupled from the rest of the framework. It exposes its results via `api.py`, which generates perfectly formatted JSON artifacts for the downstream engines:

1. **`module_02_input.json` (For IR Extraction):**
   * Passes the `semantic_graph` and the `task_patterns` list (e.g., `["Check_Inventory", "Ship_Order"]`). Module 02 uses this strictly to filter its `sys.settrace` dynamic tracker, preventing it from intercepting standard Python library code.

2. **`module_03_input.json` (For Verification Engine):**
   * Passes the full, mathematically hardened `ltlf_property_suite` (including the new `P3_Adversarial_Defenses`). Module 03 uses these rules alongside C++ SPOT to perform Stuttering Bisimulation proof checking on the LLM's code execution traces.
