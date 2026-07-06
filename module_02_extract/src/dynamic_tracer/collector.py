"""collector.py -- runtime trace collector (WIRTraceCollector).

(Auto-extracted verbatim from the original monolith during modularization.)
"""

from __future__ import annotations

import sys
import types
from typing import Any, Callable, Optional, get_type_hints


class WIRTraceCollector:
    """
    Low-overhead trace collector built on ``sys.settrace``.

    Implements the **selective observable pattern**: only task boundaries
    (function entry/exit matching BPMN tasks) and control-flow decisions
    (lines containing ``if`` / ``while`` / ``for``) are recorded.  All
    library frames are dropped immediately by returning ``None``.

    Gotcha fixes
    ------------
    * **Gotcha 2** -- For ``for`` loops iterating over dicts/sets the
      collector stores ``(iteration_index, key_hash)`` instead of raw
      key values, making trace comparison robust against insertion-order
      non-determinism.
    * **Gotcha 3** -- The ``'exception'`` trace event is captured and
      stored so that exception edges in the WIR can be validated against
      real runtime behaviour.
    * **Gotcha 4** -- A **State-Mutation Audit** compares consecutive
      line-event snapshots of ``frame.f_locals``.  If a *state variable*
      changes while ``_inside_task`` is ``False``, a warning is emitted.
    """

    def __init__(
        self,
        target_file: str,
        task_patterns: list[str],
        branch_lines: set[int],
        control_variables: list[str],
        state_variables: Optional[list[str]] = None,
        for_loop_lines: Optional[set[int]] = None,
        branch_arms: Optional[dict[int, tuple[Optional[int], Optional[int]]]] = None,
    ) -> None:
        self.target_file = target_file
        self.task_patterns = task_patterns
        self.branch_lines = branch_lines
        self.control_variables = set(control_variables)
        self.state_variables = set(state_variables or [])
        self.for_loop_lines = for_loop_lines or set()
        # F2: per-branch-line (true_line, false_line) -- the first source
        # line reached via each outgoing edge, derived from the code under
        # test's own WIR (see main.py's _derive_branch_arms). Used to turn a
        # branch_point's observed destination line into a "taken" bool.
        self.branch_arms = branch_arms or {}
        self.max_trace_steps = 2000
        self.trace_step_count = 0

        # Trace storage
        self.trace_log: list[dict[str, Any]] = []
        self.mutation_warnings: list[dict[str, Any]] = []
        self.exception_records: list[dict[str, Any]] = []

        # Runtime state
        self._original_trace: Optional[Callable] = None
        self._task_depth = 0
        self._last_locals: dict[str, Any] = {}
        self._loop_counters: dict[int, int] = {}  # line_no -> iteration count
        self._mon_tool_id: Optional[int] = None
        self._exc_origin: dict[int, int] = {}  # id(exception) -> id(origin frame)
        # F2: id(frame) -> (branch_point dict, branch_line) awaiting a
        # "taken" decision, resolved once we observe which line executes
        # next in that same frame (see _resolve_pending_branch/_infer_taken).
        self._pending_branches: dict[int, tuple[dict[str, Any], int]] = {}
        self._colines_cache: dict[int, list[tuple[int, int, int]]] = {}  # id(code) -> co_lines()

    # -- public API ------------------------------------------------------

    def start_tracing(self) -> None:
        """
        Install the runtime tracer.

        Prefers ``sys.monitoring`` (PEP 669, Python 3.12+); falls back to
        ``sys.settrace`` on older interpreters or if no monitoring tool id is
        free.  Both paths populate ``trace_log`` identically (verified by the
        differential parity suite).  Note: this is behaviour-preserving and
        does **not** remove the CPython-only dependency — both APIs are
        CPython-specific.
        """
        self._mon_tool_id = None
        mon = getattr(sys, "monitoring", None)
        tid = self._acquire_monitoring_tool_id(mon) if mon is not None else None
        if tid is not None:
            self._mon_tool_id = tid
            E = mon.events
            mon.register_callback(tid, E.PY_START, self._mon_py_start)
            mon.register_callback(tid, E.PY_RETURN, self._mon_py_return)
            mon.register_callback(tid, E.PY_UNWIND, self._mon_py_unwind)
            mon.register_callback(tid, E.RAISE, self._mon_raise)
            mon.register_callback(tid, E.LINE, self._mon_line)
            mon.register_callback(tid, E.BRANCH, self._mon_branch)
            mon.set_events(
                tid,
                E.PY_START | E.PY_RETURN | E.PY_UNWIND | E.RAISE | E.LINE | E.BRANCH,
            )
            return
        # Fallback: classic sys.settrace path (see trace_callback).
        self._original_trace = sys.gettrace()
        sys.settrace(self.trace_callback)

    def stop_tracing(self) -> None:
        """Uninstall the tracer, restoring prior interpreter state."""
        mon = getattr(sys, "monitoring", None)
        if self._mon_tool_id is not None and mon is not None:
            tid = self._mon_tool_id
            E = mon.events
            mon.set_events(tid, E.NO_EVENTS)
            for ev in (E.PY_START, E.PY_RETURN, E.PY_UNWIND, E.RAISE, E.LINE, E.BRANCH):
                mon.register_callback(tid, ev, None)
            mon.free_tool_id(tid)
            self._mon_tool_id = None
            return
        sys.settrace(self._original_trace)

    @staticmethod
    def _acquire_monitoring_tool_id(mon: Any) -> Optional[int]:
        """Reserve a free ``sys.monitoring`` tool id (0–5), or None if none free."""
        for tid in range(6):
            if mon.get_tool(tid) is None:
                try:
                    mon.use_tool_id(tid, "vibecheck.wir_tracer")
                    return tid
                except ValueError:
                    continue
        return None

    def __enter__(self) -> WIRTraceCollector:
        self.start_tracing()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop_tracing()

    # -- trace callback --------------------------------------------------

    def trace_callback(
        self,
        frame: types.FrameType,
        event: str,
        arg: Any,
    ) -> Optional[Callable]:
        """Main ``sys.settrace`` hook."""
        if event == "line":
            self.trace_step_count += 1
            if self.trace_step_count > self.max_trace_steps:
                raise RuntimeError(
                    f"Trace collection exceeded {self.max_trace_steps} steps — possible infinite loop."
                )

        # Tier-1 filter: drop everything that does not belong to the target file.
        if not self._is_target_frame(frame):
            return None

        func_name = frame.f_code.co_name
        line_no = frame.f_lineno
        locals_dict = frame.f_locals

        if event == "call" and self._is_task_function(frame):
            self._task_depth += 1
            self.trace_log.append({
                "event": "task_entry",
                "function": func_name,
                "line": line_no,
                "observables": self._extract_observables(locals_dict),
            })
            return self.trace_callback

        if event == "return" and self._is_task_function(frame):
            self.trace_log.append({
                "event": "task_exit",
                "function": func_name,
                "line": line_no,
                "return_value": self._serialize_value(arg),
                "observables": self._extract_observables(locals_dict),
            })
            self._task_depth = max(0, self._task_depth - 1)
            return None  # stop tracing after task exit

        if event == "line":
            # Gotcha 4: mutation audit -- run on *every* line in the target.
            self._audit_mutations(locals_dict, line_no, func_name)

            # F2 (settrace fallback): a branch pending in *this* frame is
            # resolved by the next line this same frame executes.
            self._resolve_pending_branch(id(frame), line_no)

            if line_no in self.branch_lines:
                # Gotcha 2: dict-iteration hashing (must run before _last_locals is updated)
                iteration_info = self._capture_iteration_info(frame, line_no, locals_dict)

                branch_event = {
                    "event": "branch_point",
                    "line": line_no,
                    "function": func_name,
                    "observables": self._extract_observables(locals_dict),
                    "iteration_info": iteration_info,
                }
                self.trace_log.append(branch_event)
                self._pending_branches[id(frame)] = (branch_event, line_no)

            # Update snapshot AFTER all diff-based logic.
            self._last_locals = dict(locals_dict)
            return self.trace_callback

        if event == "exception":
            # Gotcha 3: capture exception events
            exc_type, exc_value, _ = arg
            record = {
                "event": "exception",
                "line": line_no,
                "function": func_name,
                "exception_type": exc_type.__name__ if exc_type else None,
                "exception_msg": str(exc_value) if exc_value else None,
            }
            self.trace_log.append(record)
            self.exception_records.append(record)
            return self.trace_callback

        # All other events: continue tracing but do not record.
        return self.trace_callback

    # -- sys.monitoring callbacks (PEP 669 runtime path) -----------------
    #
    # These mirror trace_callback's recording semantics exactly (verified by
    # tests/test_dynamic_tracer_parity.py).  Mapping from settrace events:
    #   'call'+task   -> PY_START      'return'+task (normal) -> PY_RETURN
    #   'line'        -> LINE          'return'+task (unwind) -> PY_UNWIND
    #   'exception'   -> RAISE (origin frame) + PY_UNWIND (propagating frames)
    # Monitoring callbacks receive (code, ...) not a frame, so locals are
    # recovered from the monitored frame via sys._getframe(1).

    def _mon_py_start(self, code: Any, instruction_offset: int) -> Any:
        if code.co_filename != self.target_file:
            return
        if not any(pat in code.co_name for pat in self.task_patterns):
            return
        frame = sys._getframe(1)
        self._task_depth += 1
        self.trace_log.append({
            "event": "task_entry",
            "function": code.co_name,
            "line": frame.f_lineno,
            "observables": self._extract_observables(frame.f_locals),
        })

    def _mon_py_return(self, code: Any, instruction_offset: int, retval: Any) -> Any:
        if code.co_filename != self.target_file:
            return
        if not any(pat in code.co_name for pat in self.task_patterns):
            return
        frame = sys._getframe(1)
        self.trace_log.append({
            "event": "task_exit",
            "function": code.co_name,
            "line": frame.f_lineno,
            "return_value": self._serialize_value(retval),
            "observables": self._extract_observables(frame.f_locals),
        })
        self._task_depth = max(0, self._task_depth - 1)

    def _mon_raise(self, code: Any, instruction_offset: int, exception: BaseException) -> Any:
        if code.co_filename != self.target_file:
            return
        frame = sys._getframe(1)
        # Remember where this exception originated so PY_UNWIND can tell the
        # origin frame (already recorded here) from propagating ancestors.
        self._exc_origin[id(exception)] = id(frame)
        record = {
            "event": "exception",
            "line": frame.f_lineno,
            "function": code.co_name,
            "exception_type": type(exception).__name__ if exception else None,
            "exception_msg": str(exception) if exception else None,
        }
        self.trace_log.append(record)
        self.exception_records.append(record)

    def _mon_py_unwind(self, code: Any, instruction_offset: int, exception: BaseException) -> Any:
        if code.co_filename != self.target_file:
            return
        frame = sys._getframe(1)
        # settrace fires 'exception' in every frame the exception propagates
        # through; the origin frame already recorded it at RAISE, so emit only
        # for propagating ancestors here.
        if self._exc_origin.get(id(exception)) != id(frame):
            record = {
                "event": "exception",
                "line": frame.f_lineno,
                "function": code.co_name,
                "exception_type": type(exception).__name__ if exception else None,
                "exception_msg": str(exception) if exception else None,
            }
            self.trace_log.append(record)
            self.exception_records.append(record)
        # settrace 'return' also fires on exception exit -> emit task_exit.
        if any(pat in code.co_name for pat in self.task_patterns):
            self.trace_log.append({
                "event": "task_exit",
                "function": code.co_name,
                "line": frame.f_lineno,
                "return_value": self._serialize_value(None),
                "observables": self._extract_observables(frame.f_locals),
            })
            self._task_depth = max(0, self._task_depth - 1)

    def _mon_line(self, code: Any, line_number: int) -> Any:
        if code.co_filename != self.target_file:
            return
        self.trace_step_count += 1
        if self.trace_step_count > self.max_trace_steps:
            raise RuntimeError(
                f"Trace collection exceeded {self.max_trace_steps} steps — possible infinite loop."
            )
        frame = sys._getframe(1)
        locals_dict = frame.f_locals
        func_name = code.co_name

        # Gotcha 4: mutation audit on every line in the target.
        self._audit_mutations(locals_dict, line_number, func_name)

        # F2: a branch pending in *this* frame is resolved by the next line
        # this same frame executes (mirrors trace_callback's settrace path;
        # _mon_branch below may already have resolved it more precisely).
        self._resolve_pending_branch(id(frame), line_number)

        if line_number in self.branch_lines:
            iteration_info = self._capture_iteration_info(frame, line_number, locals_dict)
            branch_event = {
                "event": "branch_point",
                "line": line_number,
                "function": func_name,
                "observables": self._extract_observables(locals_dict),
                "iteration_info": iteration_info,
            }
            self.trace_log.append(branch_event)
            self._pending_branches[id(frame)] = (branch_event, line_number)

        # Update snapshot AFTER all diff-based logic.
        self._last_locals = dict(locals_dict)

    def _mon_branch(self, code: Any, instruction_offset: int, destination_offset: int) -> Any:
        """
        F2 (preferred mechanism): PEP 669 fires this on every conditional
        jump, with ``destination_offset`` telling us exactly where control
        went. We only act on it when it clearly resolves a branch_line's
        outcome -- compound conditions (``a and b``) and a for-loop's
        "continue iterating" case can produce a BRANCH event whose
        destination is still on the *same* source line (more evaluation
        left on this line), which is ambiguous; those are left pending for
        _resolve_pending_branch (the next LINE event) to settle instead.
        This is also what keeps the two tracer backends in parity: settrace
        has no BRANCH event at all and relies solely on that same fallback.
        """
        if code.co_filename != self.target_file:
            return
        frame = sys._getframe(1)
        pending = self._pending_branches.get(id(frame))
        if pending is None:
            return
        branch_event, branch_line = pending
        if self._line_for_offset(code, instruction_offset) != branch_line:
            return
        dest_line = self._line_for_offset(code, destination_offset)
        taken = self._infer_taken(branch_line, dest_line)
        if taken is not None:
            branch_event["taken_branch"] = taken
            del self._pending_branches[id(frame)]

    # -- F2: branch-decision inference ------------------------------------

    def _resolve_pending_branch(self, frame_id: int, dest_line: int) -> None:
        """Settle a pending branch_point in *frame_id* using the line that
        frame executed next (the settrace path's only signal; also the
        monitoring path's fallback for whatever _mon_branch left ambiguous)."""
        pending = self._pending_branches.pop(frame_id, None)
        if pending is None:
            return
        branch_event, branch_line = pending
        taken = self._infer_taken(branch_line, dest_line)
        if taken is not None:
            branch_event["taken_branch"] = taken

    def _infer_taken(self, branch_line: int, dest_line: Optional[int]) -> Optional[bool]:
        """
        Map an observed destination line to True/False using branch_arms
        (WHERE each arm starts, from the code-under-test's own WIR -- see
        main.py's _derive_branch_arms). Exact-match only: an unrecognised
        destination (e.g. mid-line compound-condition evaluation) returns
        None rather than guessing, so the event simply stays without a
        "taken_branch" field -- parity beats precision.
        """
        arms = self.branch_arms.get(branch_line)
        if arms is None or dest_line is None:
            return None
        true_line, false_line = arms
        if true_line is not None and dest_line == true_line:
            return True
        if false_line is not None and dest_line == false_line:
            return False
        return None

    def _line_for_offset(self, code: Any, offset: Optional[int]) -> Optional[int]:
        """Map a bytecode offset to its source line via code.co_lines(),
        cached per code object (queried once per BRANCH event)."""
        if offset is None:
            return None
        cache = self._colines_cache.get(id(code))
        if cache is None:
            cache = list(code.co_lines())
            self._colines_cache[id(code)] = cache
        for start, end, line in cache:
            if start <= offset < end:
                return line
        return None

    # -- filtering helpers -----------------------------------------------

    def _is_target_frame(self, frame: types.FrameType) -> bool:
        return frame.f_code.co_filename == self.target_file

    def _is_task_function(self, frame: types.FrameType) -> bool:
        return any(pat in frame.f_code.co_name for pat in self.task_patterns)

    # -- observable extraction -------------------------------------------

    def _extract_observables(self, locals_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Shallow-copy only control-relevant variables, serialising each as
        ``{type, hash}`` to keep trace size bounded.
        """
        result: dict[str, Any] = {}
        for var_name in self.control_variables:
            if var_name in locals_dict:
                val = locals_dict[var_name]
                try:
                    h = hash(val) & 0xFFFFFFFF
                except TypeError:
                    h = hash(id(val)) & 0xFFFFFFFF
                result[var_name] = {
                    "type": type(val).__name__,
                    "hash": h,
                }
        return result

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """Lightweight serialisation of a return value for the trace log."""
        if value is None:
            return None
        if isinstance(value, (bool, int, float, str)):
            return value
        return f"<{type(value).__name__}>"

    # -- Gotcha 2: dict-iteration hashing --------------------------------

    def _capture_iteration_info(
        self,
        frame: types.FrameType,
        line_no: int,
        locals_dict: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """
        If this branch line is a ``for`` loop, return the current iteration
        index and a hash of the loop variable (if determinable).
        """
        if line_no not in self.for_loop_lines:
            return None

        self._loop_counters[line_no] = self._loop_counters.get(line_no, 0) + 1
        iteration_idx = self._loop_counters[line_no]

        # Heuristic: find a local variable that changed since the last
        # line event and that is iterable (dict/set/list).
        key_hash: Optional[int] = None
        for name, val in locals_dict.items():
            if name.startswith("__"):
                continue
            if name not in self._last_locals:
                # New variable appeared -- could be the loop variable.
                key_hash = hash(val) & 0xFFFFFFFF
                break
            elif self._last_locals[name] is not val:
                # Variable reassigned.
                key_hash = hash(val) & 0xFFFFFFFF
                break

        return {
            "iteration_index": iteration_idx,
            "key_hash": key_hash,
        }

    # -- Gotcha 4: state-mutation audit ----------------------------------

    def _audit_mutations(
        self,
        locals_dict: dict[str, Any],
        line_no: int,
        func_name: str,
    ) -> None:
        """
        Detect assignments to state variables that occur **outside** a
        recognised task boundary.
        """
        if not self.state_variables:
            return

        inside_task = self._task_depth > 0
        for var_name in self.state_variables:
            if var_name not in locals_dict:
                continue
            old_val = self._last_locals.get(var_name)
            new_val = locals_dict[var_name]
            if old_val is not None and old_val is not new_val:
                if not inside_task:
                    self.mutation_warnings.append({
                        "variable": var_name,
                        "line": line_no,
                        "function": func_name,
                        "old": self._serialize_value(old_val),
                        "new": self._serialize_value(new_val),
                    })
