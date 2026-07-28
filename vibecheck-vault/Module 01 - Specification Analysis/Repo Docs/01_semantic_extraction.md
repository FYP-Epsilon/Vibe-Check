> [!info] Imported from repo docs
> Source: `docs/module01/01_semantic_extraction.md` @ main `7089711` (2026-07-28). `docs/` was removed from the repo (develop @ `05fae60`, 2026-07-28) after this import — **this vault copy is now the surviving snapshot** (git history retains the originals).

# Phase 1: Semantic Extraction

## Objective
To safely parse a BPMN 2.0 XML file, strip away presentational metadata, and extract a clean semantic Kripke structure representing the business logic workflow.

## V3 -> V2 -> V1 Architecture

### V3: Syntactic Sanitization
The engine (`semantic_extractor.py`) first strips away all UI/DI tags (e.g., `bpmndi:BPMNDiagram`). It strictly targets executable control-flow nodes such as `startEvent`, `task`, `exclusiveGateway`, and `endEvent`.

### V2: Semantic Graph Construction & Labeling
The sanitized DOM is traversed to apply Kripke-compatible labeling:
* **Tasks:** A single BPMN Task (e.g., "Check Inventory") is split into two temporal atomic propositions: `start(Check_Inventory)` and `done(Check_Inventory)`. This ensures duration and execution flow are properly tracked.
* **Events & Gateways:** Retain their raw names or extracted logic conditions.

### V1: Quality Gate Certification
The phase concludes by calculating Node Coverage ($C_{struct}$). If the extracted graph fails to map 100% of the executable nodes from the XML ($C_{struct} < 1.0$), the pipeline halts with a `FAIL` certificate. Unrecognized elements are safely tracked in an `unsupported_constructs` array to ensure execution resilience.
