---
name: module01-wiki-novelty-gap-2026-07-11
description: Module 01 wiki was expanded with a large unimplemented novelty layer (Phase 4 SPOT lifting + NC-1..4 series + TCB analysis); source has zero code for any of it — grounds the fable_module01_e2e_plan_prompt.md
metadata:
  type: project
---

On 2026-07-11 the GitHub wiki page `Module-01-Specification-Analysis.md` (repo `https://github.com/FYP-Epsilon/Vibe-Check.wiki.git`, commits `65010be`/`824e82d`) was updated by the Module 01 owner to add a large set of new claims on top of the original 5 novelties:

- **Phase 4 — Automata Lifting**: SPOT-based automaton construction, dual validation (Trace Language Inclusion proof + Structural Similarity/GED diagnostics)
- **NC series**: NC-1 Specification Fidelity Index (SFI, composite score w/ claimed monotonicity theorem), NC-2 Counterexample-Guided Specification Refinement (CGSR, CEGAR-style self-healing), NC-3 Priority-Weighted Behavioral Equivalence (PWBE, vector verdict w/ P0 veto), NC-4 Specification Entropy Delta (ΔH, Shannon-entropy loss localization)
- **Parallel Gateway Super-Node Abstraction** (state-explosion mitigation)
- **TCB (Trusted Computing Base) analysis**: SPOT/NetworkX trusted, custom Formula Normalizer + Automaton-to-NetworkX Converter untrusted, defended by (a) normalizer invertibility proof, (b) N-version cross-validation vs `ltlf2dfa`, (c) 10+ canonical test vectors from formal-verification literature

**Verified against source on `develop` the same session**: `module_01_spec/src/` has exactly 4 files — `semantic_extractor.py` (201 lines, Phase 1, real), `ltlf_synthesizer.py` (244 lines, Phase 2, real — implicit-else/Zero-Dead-Zone claim checks out), `mutation_refiner.py` (304 lines, Phase 3, real — 5 mutation operators, self-mutation-testing), `api.py`/`main.py` (45/67 lines, thin FastAPI wrapper, phases 1→2→3 only). `requirements.txt` = `fastapi, uvicorn, networkx` only — no `spot`, no `ltlf2dfa`, no `z3`. Repo-wide grep for `SFI|CGSR|PWBE|entropy|GED|isomorph|ltlf2dfa|super-?node|fidelity|N-Version|canonical test vector` returns **zero hits** in `module_01_spec/`. No `tests/` directory, no `.bpmn` file anywhere in the repo (tracked or untracked).

Also discovered: Module 02's `module_02_extract/inputs/conditional_ootb.yaml` (IBM FLOW-BENCH) has an `expected_output.bpmn[].$ref` field per record (e.g. `output/uid_2_output.bpmn`) — but those referenced `.bpmn` files are **not present in this repo** (`module_02_extract/inputs/output/` doesn't exist). Whether they're obtainable from the public FLOW-BENCH release is unresolved — this is the open question for any Module-01 FLOW-BENCH-style evaluation, handed to Fable as a verification task rather than assumed either way.

**Why**: Same pattern that hit [[z3_double_reset_misdiagnosis]] and the early Module 02 circularity issues — a wiki/docs layer describing novel contributions ahead of (or divorced from) the code that would substantiate them. Caught before it propagated into the thesis.

**How to apply**: [[fable_module01_e2e_plan_prompt]] was written to hand this gap to a Fable session as a verify-first, five-agent E2E implementation-planning prompt (novelty inventory → falsifiable hypothesis per claim → BPMN/LTLf edge-case audit → non-circular FLOW-BENCH-style evaluation plan → adversarial critique → synthesized phase-ordered plan). [[module01_ownership_boundary]] still applies — this is planning only, no code edits to Module 01. If a future session touches Module 01's wiki or source, re-verify the NC-series claims against code state at that time rather than trusting this snapshot.
