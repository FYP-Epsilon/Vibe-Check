# Module 04 — Verification Portal

> **TL;DR** — Module 04 is the Streamlit front end of VibeCheck (`module_04_ui/src/app.py`, 573 lines), served by the `ui-engine` container (python:3.11-slim) on host port **8501** — the only docker-compose service exposed on a host port. All four pages now call their engines over HTTP; the equivalence page — **broken by construction** at the last snapshot — was fixed when Module 03 gained a real FastAPI service (PR #74). The unused `networkx` dependency was removed from requirements (PR #84). It remains a UI/integration layer, *not* a research contribution.

## Purpose

A single-page-app style portal for demoing and operating the three verification engines. The module itself still disclaims research novelty: *"a UI/integration layer, not a research contribution in itself."* All certificate figures shown are now live results parsed from engine HTTP responses — the old "illustrative inputs, not a live run" figures are gone from the UI.

## Page structure (4 pages)

- **Dashboard** — system overview, engine cards, quick-launch radio
- **Spec Engine page** — info tab + verification tab: `POST spec-engine:8000/verify` with BPMN XML; renders phase-1/2/3 certificate metrics, semantic graph / refined LTLf suite / certificate tabs, and a property-suite JSON download
- **Extract Engine page** — info tab + verification tab: `POST extract-engine:8000/verify` with Python source; renders V3/V2/V1 + combined confidence metrics, per-layer telemetry tabs, and a WIR JSON download
- **Equiv Engine page** — info tab + demo tab: `POST equiv-engine:8000/lift` with a WIR payload, BPMN task names, and an action to match; renders the BDD variable registry and the semantic match result. Now HTTP like the other pages — the in-process import is gone

## Health checks (symmetric now)

Sidebar status dots are live HTTP health checks for all three engines — the asymmetry from the last snapshot is gone:

| Engine | Health check | What it measures |
|---|---|---|
| Spec | `GET /docs`, 2s timeout | Engine reachability |
| Extract | `GET /docs`, 2s timeout | Engine reachability |
| Equiv | `GET /health`, 2s timeout | Engine reachability (FastAPI service added in PR #74) |

## Fixed: the equivalence page (PR #74)

At the last snapshot the equiv page did an in-process `import vibecheck_lifter` inside the `ui-engine` container, which has **no SPOT and no lifter module** — broken by construction. The root cause was upstream: Module 03's `main.py` was a print-and-exit demo script with no HTTP service at all, so there was nothing to call. PR #74 rewrote `module_03_equiv/src/main.py` as FastAPI (`POST /lift`, `POST /check`, `GET /health`, uvicorn :8000 — mirroring Module 01's pattern) and rewired M04's equiv health check and demo button to call `/lift` over HTTP, the same pattern as the Spec/Extract pages. Verified locally against a scratchpad-built `.so`; the docker-compose build (SPOT-from-source too slow) and the Streamlit page in a browser were **not** verified in that PR.

## Status & issues (2026-07-29, main-demo @ `5c65046`)

- **Working** — All three engine pages call their services over HTTP; all three sidebar dots are real reachability checks
- **Fixed (PR #74)** — Equiv page no longer does an in-process import; equiv-engine is now a real FastAPI service (`/lift`, `/check`, `/health`)
- **Fixed (PR #84)** — `networkx` removed from `module_04_ui/requirements.txt` (confirmed zero references first; container rebuilt and serving 200 without it)
- **Gap** — `POST /check` (full Phase A–D conformance) has no UI demo: it needs a call-order-lifted WIR, which extract-engine's own HTTP API does not yet produce — the page documents this itself
- **Gap** — Zero tests for Module 04 (the module is a single 573-line `app.py`, plus a 12-line Dockerfile and 2-line requirements)
- **Caveat** — PR #74's verification was local-only; the equiv-engine docker-compose build and the equiv page in a real browser remain unverified end-to-end
- **Fixed earlier** — UI naming collision: V1/V2/V3 verification layers vs module numbers
- **Pending** — Wiki page written directly from source (no design doc exists); still marked *pending owner review*

## Links

- [[Home]]
- [[Module 04 Architecture.canvas|Module 04 Architecture]]
- [[Module 04 Status.canvas|Module 04 Status]]
