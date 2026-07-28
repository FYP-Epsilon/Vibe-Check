> [!info] Imported from repo docs
> Source: `docs/README.md` @ main `7089711` (2026-07-28). `docs/` was removed from the repo (develop @ `05fae60`, 2026-07-28) after this import — **this vault copy is now the surviving snapshot** (git history retains the originals).

# 📚 VibeCheck Internal Wiki

Welcome to the VibeCheck knowledge base! This directory contains all the contextual information required to understand, develop, and extend the framework.

## 🗂️ Directory Structure & Key Documents

### 1. 🏗️ Architecture (`/architecture`)

System design, execution plans, and data flow diagrams.

* [Module 02: E2E Execution Plan & Deep Technical Reference](./architecture/module_02_execution_plan.md) — The master roadmap for Z3 integration, CFG extraction, and the `sys.settrace` differential execution pipeline.
* *Interim Report.pdf* — The foundational academic report detailing the formal verification strategy and dual-track architecture.

### 2. 🔗 APIs & Schemas (`/api_and_schemas`)

Data contracts and intermediate representation formats.

* [WIR Schema Documentation](./api_and_schemas/wir_schema_docs.md) — Defines the JSON structure (Workflow Intermediate Representation) passed between Module 02 and Module 03.

### 3. 🔬 Research (`/research`)

Reference materials, formal methods literature, and library documentation (e.g., SPOT Model Checker, Z3 Theorem Prover, and FLOW-BENCH dataset papers).

---

## 🤖 Note for AI Coding Agents (Kimi, Cursor, Copilot)

When implementing new features, debugging, or refactoring code in this repository, you **MUST** refer to the documents in this directory to ensure your code aligns with the formal verification parameters defined in our research.

Specifically, consult the execution plans in the `architecture/` folder before generating complex logic or altering data structures.
