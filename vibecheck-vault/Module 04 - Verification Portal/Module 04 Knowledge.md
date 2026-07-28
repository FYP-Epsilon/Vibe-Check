# Module 04 — Verification Portal

> **TL;DR** — Module 04 is the Streamlit front end of VibeCheck (`module_04_ui/src/app.py`, 565 lines), served by the `ui-engine` container (python:3.11-slim, no SPOT) on host port **8501** — the only docker-compose service exposed on a host port. It works for Modules 01/02 over HTTP, but the equivalence page is **broken by construction**. It is explicitly a UI/integration layer, *not* a research contribution. **Unchanged this cycle.**

## Purpose

A single-page-app style portal for demoing and operating the three verification engines. The module itself disclaims research novelty: *"a UI/integration layer, not a research contribution in itself."* Certificate figures shown in the UI are labeled *"illustrative inputs, not a live run."*

## Page structure (4 pages)

- **Dashboard** — overview and certificate figures
- **Spec Engine page** — calls the Spec engine over HTTP
- **Extract Engine page** — calls the Extract engine over HTTP
- **Equiv Engine page** — the only page that calls its engine **in-process** (see below)

## Health-check asymmetry

Sidebar status dots are live health checks, but they are not symmetric:

| Engine | Health check | What it actually measures |
|---|---|---|
| Spec | `GET /docs`, 2s timeout | Real engine reachability |
| Extract | `GET /docs`, 2s timeout | Real engine reachability |
| Equiv | `import vibecheck_lifter` **in the UI process** | The UI container's local Python state — *not* the equiv-engine container's reachability |

## Broken: the equivalence page

The equiv page does an in-process `import vibecheck_lifter` inside the `ui-engine` container (app.py:542, also :98). That container has **no SPOT and no lifter module**, so the import always fails — the error message itself tells the user to run it in the equiv-engine container. The compounding issue is now fixed upstream — the committed Linux x86-64 `.so` was removed from git (`*.so` gitignored) — but on the maintainer's macOS host the page is still dead: with no committed artifact and no local build, the import fails just the same.

## Status & issues

- **Working** — Spec/Extract pages and their HTTP health checks
- **Broken (red)** — Equiv page, by construction (in-process import in the wrong container)
- **Improved** — Committed Linux `.so` artifact removed from git; the macOS breakage now is simply "no locally built lifter" rather than a wrong-architecture binary
- **Gap** — Zero tests for Module 04
- **Noted** — `networkx` is in `module_04_ui/requirements.txt` but never imported (flagged, not silently assumed dead)
- **Fixed** — Earlier UI naming collision: V1/V2/V3 verification layers vs module numbers
- **Pending** — Wiki page was written directly from source (no design doc exists); still marked *pending owner review*

## Links

- [[Home]]
- [[Module 04 Architecture.canvas|Module 04 Architecture]]
- [[Module 04 Status.canvas|Module 04 Status]]
