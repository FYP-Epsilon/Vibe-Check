# Sample inputs for the E2E Pipeline demo

Upload the `spec.bpmn` + `implementation.py` pair from one of these folders
into the **🔄 E2E Pipeline → ▶️ Run Full Check** page in the M04 UI
(http://localhost:8501) to exercise a specific outcome of the real
M01 → M02 → M03 HTTP chain (`module_04_ui/src/e2e_orchestrator.py`).

Each pair below was actually run against the live `spec-engine` /
`extract-engine` / `equiv-engine` containers — "Expected
result" is the real observed output as of 2026-08-03.

**Heads-up on runtime:** `spec-engine`'s `/verify` runs Module 01's Phase 3
mutation-based quality gate, whose cost scales with diagram complexity, not
just task count. The 3-4 task FLOW-BENCH specs (`01`-`08`) resolve in
seconds. The two 6-task/2-gateway custom examples (`09`/`10`) took
**~146s and ~290s respectively** in testing — legitimately computing, not
hung (confirmed via `docker stats`: steady ~100% CPU, no runaway memory).
The E2E Pipeline page's client timeout was bumped to 600s
(`module_04_ui/src/e2e_orchestrator.py`) specifically because of this —
the original 60s default made these two cases fail with a spurious
"network error" that had nothing to do with the chain being broken.

| Folder | Demonstrates | Expected result |
|---|---|---|
| `01_compliant/` | A real BPMN spec + a real, unmodified LLM-generated implementation that is fully conformant. | `COMPLIANT` on every checkable property. |
| `02_violation_order_swap/` | The same implementation with two adjacent calls swapped (an order-mutation), breaking an ordering property. | One `VIOLATION` (with a readable counterexample trace) + the remaining properties `COMPLIANT`. |
| `03_inconclusive_task_drop/` | The same implementation with a task's own call dropped entirely. | Mostly `INCONCLUSIVE` — the dropped task's atom becomes unmatched, so the pipeline honestly declines to verdict rather than guessing. |
| `04_spec_gate_fail/` | A real BPMN spec that legitimately fails Module 01's own Phase 3 mutation-adequacy quality gate (`uid_13`, verified deterministic). | The **spec-engine** stage rejects the request (HTTP 422, `PHASE_3_GATE_FAIL`) with a stage-tagged error. |
| `05_extract_syntax_error/` | A deliberately invalid Python file (syntax error) paired with a valid BPMN spec. | The **extract-engine** stage rejects the request — `/verify` reports syntax error, no `call_order_wir` produced. |
| `06_exclusive_gateway_compliant/` | Complex branching workflow with an exclusive gateway (`uid_11`: ServiceNow incident priority check $\to$ Jira+Slack vs GitHub). | `COMPLIANT` across conditional execution paths. |
| `07_exclusive_gateway_violation/` | The same branching workflow with an order swap inside the high-priority conditional branch. | `VIOLATION` with counterexample trace isolating the faulty branch sequence. |
| `08_s3_storage_workflow_compliant/` | Multi-task S3 storage workflow (`uid_88`: bucket lookup $\to$ object retrieve vs bucket creation). | `COMPLIANT` across branching state transitions. |
| `09_custom_order_processing_compliant/` | **Custom E-Commerce Workflow**: Natural task names (`Receive_Customer_Order`, `Check_Inventory_Stock`, `Assess_Risk_Score`, `Process_Credit_Payment`, `Send_Fraud_Alert_Email`, `Fulfill_Standard_Shipping`). | `COMPLIANT` across risk assessment decision branches. |
| `10_custom_order_processing_violation/` | **Custom E-Commerce Workflow Violation**: Order swap inside the high-risk branch (`Send_Fraud_Alert_Email` called before `Process_Credit_Payment`). | `VIOLATION` with counterexample trace isolating out-of-order execution. |
| `11_z3_symbolic_loan_approval/` | **Purpose-built to exercise Module 02's V2 (Z3 symbolic) layer** — see below. | `spec-engine` `status: PASS`. `extract-engine`: `v2_confidence: 0.5`, `v1_confidence: 1.0`, `combined_confidence: 1.0`, `passed: true`. |

### Why `11_z3_symbolic_loan_approval` is different

The other 10 examples exercise Module 02's **V1** layer (dynamic differential tracing) almost exclusively — V1 does the real detection work on this project's corpus, and V2 (Z3) normally contributes close to nothing (see `Module 02 Evaluation Results.md` §4, "what's honestly not claimed"). This example is built specifically to make V2 do real, visible work, and it was verified directly against the live `extract-engine` container (not just a local script) on 2026-08-03.

`workflow()`'s only interesting branch is `if referral_code == 77531:` — an exact-value gate on the function's own integer parameter. V1's random sampler (`dynamic_tracer/randomized.py`) draws inputs with `random.randint(-100, 100)` — so `77531` is **structurally outside the sampling range**, not just statistically unlikely. No number of V1 runs could ever land on it. Z3, by contrast, doesn't sample — it solves the guard directly and returns `referral_code = 77531` as a concrete witness in a single query.

The measured V2 certificate confirms this: `branch_diversity_score: 1.0` and `covered_edges: 2` mean **both** sides of that gateway were reached — the `else` path (found by plain concrete execution) and the priority-loan path (found only because Z3 solved for it). `solver_success_rate: 1.0` shows the one Z3 query needed actually succeeded. (V2's confidence caps at `0.5` here, not higher, because of how the engine's iteration-count-vs-solved-path ratio is defined for a single gateway — not because anything failed; see `total_paths: 2` / `feasible_paths: 1` in the raw certificate.)

Note the `combined_confidence: 1.0`: since the certificate formula is `1 − (1−v1)(1−v2)`, V1's already-perfect 1.0 score (on the branch it *did* see) masks V2's contribution in the final number — a live instance of the documented "V2-masking in self-mode" limitation (`Module 02 Knowledge.md`). To see V2's contribution on its own, look at `v2_details` directly rather than the top-level `combined_confidence`.

## Regenerating / extending these

- `01`/`02`/`03` all come from FLOW-BENCH `uid_45` (`flow-bench/data/context/uid_45_context.bpmn` + `module_02_extract/eval/variants/normalized/45__llama-3.1-8b.py`).
- `06`/`07` come from FLOW-BENCH `uid_11` (`flow-bench/data/context/uid_11_context.bpmn` + `module_02_extract/eval/variants/normalized/11__llama-3.1-8b.py`).
- `08` comes from FLOW-BENCH `uid_88` (`flow-bench/data/context/uid_88_context.bpmn`).
- `09`/`10` are **custom-designed domain workflows** using natural, human-readable function names (`Receive_Customer_Order`, `Check_Inventory_Stock`, etc.) rather than FLOW-BENCH service API identifiers.
