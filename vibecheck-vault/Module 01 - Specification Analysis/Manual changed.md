

Module01 Architecutre
# Module 01 — Specification Analysis 
Implemented 4-phase architecture (post-pivot: PBCTS replaced the one-day-old SPOT/HOA Phase4) 


## Novelty scoreboard (churned ×2)
- **SPOT/HOA lifting + process-mining EAS** — implemented, then **deleted after one day**
- - **SFI / ΔH / PWBE** — implemented, then removed earlier same cycle


Module01 Knowledge

> ⚠ **Architecture pivot (2026-07-28):** the SPOT/HOA Phase 4 (`automata_lifter.py`) and process-mining Phase 5 (`process_mining_alignment.py`) were **deleted** after one day and replaced by a pure-Python **PBCTS** Phase 4. SPOT no longer appears in any executable code — but the Dockerfile still builds SPOT 2.11.6 from source (dead weight).


**SPOT/HOA automata lifting, GED, process-mining EAS** — implemented, then **DELETED** one day later in the pivot.
- **SFI / ΔH / PWBE** — implemented, then removed earlier in the same cycle. Nothing remains.


- ⛔ **STARTUP BUG:** `main.py:11,16` still does `from .automata_lifter import AutomataLifter` — the module was deleted, so the FastAPI app (and the Docker `uvicorn src.main:app` CMD) raises `ModuleNotFoundError` on startup. The `/verify` route never uses the import.




Module01 Status
## ⛔ STARTUP BUG
`main.py:11,16` still imports the deleted `automata_lifter` → FastAPI app (and Docker `uvicorn` CMD) raises `ModuleNotFoundError` on startup.
**The spec-engine service is down.**
Also: status codes inconsistent (`FAIL_ALIGNMENT_UNPROVEN` vs `PASS_PBCTS_UNCONVERGED`).