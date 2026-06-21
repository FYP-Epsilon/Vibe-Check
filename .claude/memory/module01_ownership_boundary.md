---
name: module01-ownership-boundary
description: Module 01 belongs to a different developer — do not touch it; M01-dependent work is blocked until the user signals M01 is ready
metadata:
  type: feedback
---

The user (sole developer of **Module 02**) instructed (2026-05-30): **do not touch Module 01 — it belongs to a different developer.** They will explicitly inform me when M01 is done.

**Why:** Module boundaries are owned per-developer in this FYP group (Group 18 / Epsilon). Building against M01 before its contract is finalized risks wasted/conflicting work, and there is currently no M01 output contract or BPMN data in the Module 02 repo (only docstring mentions).

**How to apply:** Treat any M01-dependent task as **blocked until the user signals M01 is ready** — most importantly `Module01Adapter` (the WIR-independent reference oracle for thesis vulnerability #1). Do not design or stub against an invented M01 schema. When picking next work, prefer **Module-02-internal** items that need no M01 input (e.g. container/CrossHair V2 coverage, typed `/verify` partial-failure contract, adaptive V1 run count, ValidationConfig, QCE state-merging decision). See [[module02-rd-deliverable]] and [[z3-double-reset-misdiagnosis]].
