"""
Differential parity tests for the V1 WIRTraceCollector.

The runtime tracer prefers sys.monitoring (PEP 669); a sys.settrace path is
retained as a fallback and is the path exercised by the trace_callback unit
tests.  These tests assert the two paths produce IDENTICAL trace output across
representative cases — including the exception-propagation corners (uncaught
single-frame unwind, locally-caught, and multi-frame propagation) where the
settrace 'return'/'exception' semantics differ from monitoring's
PY_RETURN/PY_UNWIND/RAISE and must be reconciled explicitly.
"""
from __future__ import annotations

import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import dynamic_tracer  # noqa: E402
from dynamic_tracer import WIRTraceCollector  # noqa: E402


# (label, source, config, inputs)
CASES = [
    (
        "normal_task",
        "def task_process(x):\n    y = x + 1\n    return y\n",
        dict(task_patterns=["task"], branch_lines=set(),
             control_variables=["x", "y"], state_variables=[], for_loop_lines=set()),
        {"x": 5},
    ),
    (
        "branchy_loop",
        "def task_loop(n):\n    total = 0\n    for i in range(n):\n        if i > 0:\n            total += i\n    return total\n",
        dict(task_patterns=["task"], branch_lines={4},
             control_variables=["n", "i", "total"], state_variables=[], for_loop_lines=set()),
        {"n": 3},
    ),
    (
        "dict_iteration",
        "def task_dict(d):\n    out = 0\n    for k in d:\n        out += 1\n    return out\n",
        dict(task_patterns=["task"], branch_lines={3},
             control_variables=["d", "k", "out"], state_variables=[], for_loop_lines={3}),
        {"d": {"a": 1, "b": 2}},
    ),
    (
        "exception_exit_task",
        "def task_fail(x):\n    y = x + 1\n    raise ValueError('boom')\n",
        dict(task_patterns=["task"], branch_lines=set(),
             control_variables=["x", "y"], state_variables=[], for_loop_lines=set()),
        {"x": 1},
    ),
    (
        "same_file_helper",
        "def helper(a):\n    if a > 0:\n        return a\n    return -a\ndef task_main(x):\n    r = helper(x)\n    return r\n",
        dict(task_patterns=["task"], branch_lines={2},
             control_variables=["a", "x", "r"], state_variables=[], for_loop_lines=set()),
        {"x": 7},
    ),
    (
        "locally_caught",
        "def task_catch(x):\n    try:\n        raise ValueError('x')\n    except ValueError:\n        y = 1\n    return y\n",
        dict(task_patterns=["task"], branch_lines=set(),
             control_variables=["x", "y"], state_variables=[], for_loop_lines=set()),
        {"x": 0},
    ),
    (
        "multi_frame_uncaught",
        "def inner_raise(a):\n    if a > 0:\n        raise ValueError('deep')\n    return a\ndef task_outer(x):\n    return inner_raise(x)\n",
        dict(task_patterns=["task"], branch_lines={2},
             control_variables=["a", "x"], state_variables=[], for_loop_lines=set()),
        {"x": 5},
    ),
    (
        "mutation_outside_task",
        "def helper2(loan_status):\n    loan_status = 'approved'\n    return loan_status\ndef driver(loan_status):\n    return helper2(loan_status)\n",
        dict(task_patterns=["task"], branch_lines=set(),
             control_variables=["loan_status"], state_variables=["loan_status"], for_loop_lines=set()),
        {"loan_status": "pending"},
    ),
    (
        # F2: branch_arms populated -- exercises both the sys.monitoring.
        # events.BRANCH path and the settrace next-line fallback, and
        # asserts they land on identical taken_branch values (line 4 =
        # true arm "total += i" starts at line 5, false arm "else" body
        # at line 7; per _derive_branch_arms, arms map gateway/loop line
        # -> (true_line, false_line)).
        "branch_decision_if_else_in_loop",
        "def task_loop(items):\n    total = 0\n    for i in items:\n        if i > 0:\n            total += i\n        else:\n            total -= i\n    return total\n",
        dict(task_patterns=["task"], branch_lines={3, 4},
             control_variables=["items", "i", "total"], state_variables=[],
             for_loop_lines={3}, branch_arms={3: (4, 8), 4: (5, 7)}),
        {"items": [1, -2, 3]},
    ),
]


def _norm(obj):
    """Replace volatile per-process hash values with a sentinel."""
    if isinstance(obj, dict):
        return {k: ("H" if (k in ("hash", "key_hash") and v is not None) else _norm(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_norm(x) for x in obj]
    return obj


def _entry_name(ns, config):
    for name, val in ns.items():
        if not name.startswith("__") and callable(val) \
                and any(p in name for p in config["task_patterns"]):
            return name
    return [n for n, v in ns.items() if not n.startswith("__") and callable(v)][-1]


def _collect(source, config, inputs):
    ns = {"__builtins__": __builtins__}
    exec(compile(source, "<string>", "exec"), ns)
    entry = _entry_name(ns, config)
    coll = WIRTraceCollector(target_file="<string>", **config)
    with coll:
        try:
            ns[entry](**copy.deepcopy(inputs))
        except BaseException:
            pass
    return {
        "trace_log": _norm(coll.trace_log),
        "exception_records": _norm(coll.exception_records),
        "mutation_warnings": _norm(coll.mutation_warnings),
    }


@pytest.mark.parametrize("label,source,config,inputs", CASES, ids=[c[0] for c in CASES])
def test_monitoring_matches_settrace(label, source, config, inputs, monkeypatch):
    # Path A: sys.monitoring (default runtime path).
    assert getattr(sys, "monitoring", None) is not None, "sys.monitoring expected on 3.12+"
    mon_result = _collect(source, config, inputs)

    # Path B: force the sys.settrace fallback by hiding sys.monitoring.
    monkeypatch.setattr(dynamic_tracer.sys, "monitoring", None, raising=False)
    settrace_result = _collect(source, config, inputs)

    assert mon_result == settrace_result, (
        f"Tracer parity broken for case '{label}':\n"
        f"monitoring={mon_result}\nsettrace={settrace_result}"
    )


def test_branch_decision_populated_on_both_backends(monkeypatch):
    """F2: with branch_arms supplied, every branch_point event on both
    backends carries a non-None taken_branch -- not just equal to each
    other (which the parametrized parity test already checks), but
    actually present, so this can't silently pass via both sides staying
    empty."""
    label, source, config, inputs = next(
        c for c in CASES if c[0] == "branch_decision_if_else_in_loop"
    )

    mon_result = _collect(source, config, inputs)
    monkeypatch.setattr(dynamic_tracer.sys, "monitoring", None, raising=False)
    settrace_result = _collect(source, config, inputs)

    for result, backend in ((mon_result, "monitoring"), (settrace_result, "settrace")):
        branch_events = [e for e in result["trace_log"] if e["event"] == "branch_point"]
        assert len(branch_events) == 7, f"{backend}: expected 7 branch_point events"
        assert all(e.get("taken_branch") is not None for e in branch_events), (
            f"{backend}: taken_branch missing on some branch_point events: {branch_events}"
        )

    # Expected decisions for items=[1, -2, 3]: loop fires 3x (True) + 1
    # exhausted (False); if/else per item: True, False, True.
    mon_taken = [e["taken_branch"] for e in mon_result["trace_log"] if e["event"] == "branch_point"]
    assert mon_taken == [True, True, True, False, True, True, False]
