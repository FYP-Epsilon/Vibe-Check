# Cross-Implementation Comparison Mode (Session D)

Adds `comparison_mode` (`strict` | `task_only`) to the differential comparator (`src/dynamic_tracer/comparator.py`), threaded through `RandomizedDifferentialTester` -> `run_v1_pipeline` -> `run_differential_verification`. Default `strict` everywhere; the `/verify` self-mode path is untouched.

## The mode-selection rule

**strict when the two sides share source lineage; task_only when they are independent implementations.** This is decided by what the comparison can assume shared, before looking at any number:

- **strict** (default) -- a mutant vs its own base program. Branch structure is shared by construction (the mutation is a small, localized edit), so branch-decision divergence is real signal -- this is what F2/Session A exploited (negate-guard 8/14 -> 14/14; constant-perturb 0/9 -> 8/9, see `calibration_report_differential.md`).
- **task_only** -- an independently-written implementation (Session C's multi-implementation corpus) vs a reference WIR. Branch structure legitimately differs between correct implementations (different guard nesting, extra defensive checks, different control-flow shape for the same task), so branch events are noise; only task-observable behavior (which stubs run, in what order, plus exceptions) is comparable.

## D2 -- Session C corpus re-run in task_only mode

Frozen inputs (not regenerated, not re-admitted): `eval/variants/manifest.json`'s 20 admitted / 164 rejected-behavioral variants, from PR #31.

### C5b -- implementation-freedom specificity

| | strict (frozen, PR #31) | task_only (this session) |
|---|---|---|
| False-alarm rate | 0.2500 (5/20) | 0.1000 (2/20) |

Pre-registered expectation (written before running): the 3 clear style-punishment false alarms (uids 2/3/4, per the corrected per-variant C5b table) recover; the 2 exception/marginal ones (uids 1/42) may not, since exceptions still compare correctly in task_only mode. **Confirmed exactly**: task_only flags only uids 1 and 42 (both `has_exception: true`, divergence breakdown `{'exception': 20}` -- entirely exception events, zero branch_point, since branch_point is dropped from the comparison entirely in this mode). Uids 2, 3, 4 -- the clean style-driven false alarms -- all recover to a passing score.

### C5c -- natural-bug detection

| | strict (frozen, PR #31) | task_only (this session) |
|---|---|---|
| Detection rate (all) | 0.9634 (158/164) | 0.8841 (145/164) |
| exception-class | 1.0000 (96/96) | 0.9583 (92/96) |
| logic-class | 0.9118 (62/68) | 0.7794 (53/68) |

**Logic-class detection drops materially under task_only (0.9118 -> 0.7794) -- stated plainly, not smoothed over.** This is the expected trade the mode exists to make explicit: some real logic bugs (in a cross-implementation setting, ones that happen to manifest as a branch-decision-only divergence with an otherwise-matching task sequence) become invisible when branch structure is excluded. Even exception-class detection drops slightly (1.0000 -> 0.9583) -- checked directly (the 4 variants that flip from strict-detected to task_only-missed: `10__qwen3-next-80b`, `20__llama-3.1-8b`, `30__qwen3-next-80b`, `99__llama-3.1-8b`): all 4 are branch_point-dominated in strict mode's own divergence-source breakdown (28-50 `branch_point` events vs. 0-6 task/exception events each). C5c's own N=10, seed=42 sampled inputs caught these via branch-decision divergence on those specific inputs, not by independently triggering the admission-recorded exception (which came from a *different*, N=100 input set) on the same inputs -- task_only correctly can't see that signal once branch_point is dropped. task_only trades this sensitivity for style tolerance; D2's C5b result above is the return on that trade, and D3 below quantifies it further on synthetic mutations where the trade is starkest.

### The 6 strict-mode logic-class misses (68 logic, 62 detected)

Diagnosis only, per the mandate -- not implemented this session. For each of the 6 undetected logic-class variants, checked whether the admission record's `first_divergent_input` shows an identical stub-call sequence on both sides (so V1's task-event trace has nothing to diverge on) with only the final return value differing -- a class of divergence V1 traces cannot see in EITHER mode, since V1 never observes return values, only task_entry / task_exit / branch_point / exception events.

| variant | uid | combined_confidence | same call sequence? | base return | variant return |
|---|---|---|---|---|---|
| 33__qwen3-next-80b | 33 | 0.1000 | yes | `None` | `{'tickets': {}, 'users': {}}` |
| 35__qwen3-next-80b | 35 | 0.1000 | yes | `None` | `{'workspaces': {}, 'scorecards': {}, 'goals': {}}` |
| 38__qwen3-next-80b | 38 | 0.1000 | yes | `None` | `{}` |
| 42__qwen3-next-80b | 42 | 0.1000 | yes | `None` | `{}` |
| 49__qwen3-next-80b | 49 | 0.1000 | yes | `None` | `{}` |
| 68__llama-3.1-8b | 68 | 0.1000 | yes | `None` | `({'label': 'Enter candidate name'}, {})` |

**6/6 of the misses are return-value-only divergences** -- identical call sequence, base returns `None` (the workflow falls through with no explicit return) while the variant returns a real value. All 6 sit exactly at combined_confidence == 0.1 (the frozen tau), not below it -- a floor artifact, not graded uncertainty. **Backlog item (named, not implemented): a return-value observable in V1 traces** would close this specific gap; out of scope for this session per the mandate.

## D3 -- Control: mutation calibration under task_only

Full differential mutation calibration (same manifest, same seed=1234, same tau-selection procedure as `calibrate_corrected.py`) re-run fresh in both modes via the standalone `eval/d3_control.py` -- **does not write `threshold.json`**; both rows below are clearly-labeled experiments, not a new frozen operating point.

### Strict-mode regression proof

The strict-mode row below is a fresh, independent re-run (not a copy) and reproduces Session A's frozen numbers exactly -- `comparison_mode="strict"` is a behavioral no-op against the pre-D1 code path.

| mode | tau | Youden's J | genuine-bug detection | false-alarm rate |
|---|---|---|---|---|
| strict | 0.1000 | 0.9600 | 0.9952 | 0.0588 |
| task_only | 0.1000 | 0.8241 | 0.8952 | 0.0588 |

Strict: tau=0.1000, J=0.9600, detection=0.9952, FA=0.0588 -- byte-identical to Session A's frozen figures (`threshold.json`, `calibration_report_differential.md`).

### Per-operator collapse under task_only (the answer to "why not always use the forgiving mode?")

| operator | strict | task_only |
|---|---|---|
| constant-perturb | 0.889 (8/9) | 0.222 (2/9) |
| corrupt-container-op | 1.000 (16/16) | 1.000 (16/16) |
| drop-step | 1.000 (51/51) | 1.000 (51/51) |
| early-return | 1.000 (49/49) | 0.898 (44/49) |
| negate-guard | 1.000 (14/14) | 0.286 (4/14) |
| reorder-steps | 1.000 (49/49) | 1.000 (49/49) |
| swap-branches | 1.000 (4/4) | 1.000 (4/4) |
| wrong-variable | 1.000 (18/18) | 1.000 (18/18) |

`negate-guard` (14/14 -> 4/14) and `constant-perturb` (8/9 -> 2/9) collapse back toward their pre-F2/pre-A2 levels, exactly as predicted -- both operators' detection rides on the branch-decision divergence F2/A2 made visible, which task_only discards by design. `early-return` also drops (49/49 -> 44/49): an early return sometimes only changes which branch is taken without changing the eventual stub-call sequence. The purely task-sequence-affecting operators (`drop-step`, `reorder-steps`, `corrupt-container-op`, `wrong-variable`, `swap-branches`) are **unchanged** -- their mutations alter what stubs get called, not just which branch is taken, so task_only still catches them. This is the data-driven case for keeping strict as the default for same-lineage comparison: task_only would silently give up most of F2/A2's hard-won detection power on exactly the mutation classes those sessions were built to catch.

## Caveats

- C5b's n=20 is small (Session C, carried forward); the 2/5 -> 0/5-clean-style split under task_only is consistent with, not an independent replication of, the strict-mode per-variant finding -- same 20 variants, same 20 bases.
- Admission equivalence (which variants are "correct" ground truth for C5b) is N=100-bounded, per Session C's own caveat -- unchanged by this session.
- Single sample per (uid, model) in the underlying corpus -- carried from Session C, not addressed here.
- task_only's exception-only comparison (D2) means a natural bug that raises no exception and reaches an identical stub-call sequence with a different return value is invisible to it too, same as strict -- the 6-miss diagnosis above is a V1-wide gap, not specific to either comparison mode.