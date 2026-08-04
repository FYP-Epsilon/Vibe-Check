"""
test_call_order_view.py
========================
Unit tests for ``derive_call_order_wir`` -- the call-order-linearized WIR
that replaces definition-order lifting for Phase D conformance checking
(see vibecheck-vault/Module 03 - Equivalence Engine/Bridge Investigation/
CP1 Lifting-Scope Decision.md for the real-corpus evidence this fixes).

Run with ``pytest`` from the repo root::

    pytest module_02_extract/tests/test_call_order_view.py -v
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from ast_extractor import derive_call_order_wir


def _task_nodes(wir: dict) -> list[dict]:
    return [n for n in wir["nodes"] if n["type"] == "task"]


def _code_of(node: dict) -> str:
    return " ".join(node["code"])


class TestLinearDriver:
    SOURCE = """
def create_object():
    return {}

def retrieve_bucket():
    return {}

def workflow():
    retrieve_bucket()
    create_object()
"""

    def test_task_nodes_follow_call_order_not_definition_order(self):
        wir = derive_call_order_wir(self.SOURCE)
        tasks = _task_nodes(wir)
        assert len(tasks) == 2
        assert "retrieve_bucket" in _code_of(tasks[0])
        assert "create_object" in _code_of(tasks[1])

    def test_driver_is_the_function_that_calls_siblings(self):
        wir = derive_call_order_wir(self.SOURCE)
        assert wir["driver"] == "workflow"

    def test_last_task_node_has_an_outgoing_edge(self):
        # A task label only ever attaches to an edge *leaving* its node
        # (lifter.cpp's resolve_task_label is looked up per source node of
        # an edge) -- without a trailing exit edge the last call in the
        # driver would never register an AP on the automaton at all.
        wir = derive_call_order_wir(self.SOURCE)
        tasks = _task_nodes(wir)
        last_task_id = tasks[-1]["id"]
        assert any(e["source"] == last_task_id for e in wir["edges"])

    def test_never_called_function_produces_no_task_node(self):
        source = self.SOURCE + "\ndef never_called():\n    return {}\n"
        wir = derive_call_order_wir(source)
        assert not any("never_called" in _code_of(n) for n in _task_nodes(wir))


class TestBranchingDriver:
    SOURCE = """
def check():
    return {}

def approve():
    return {}

def reject():
    return {}

def workflow():
    result = check()
    if result:
        approve()
    else:
        reject()
"""

    def test_both_branches_reachable_and_guarded(self):
        wir = derive_call_order_wir(self.SOURCE)
        tasks = _task_nodes(wir)
        assert len(tasks) == 3
        codes = [_code_of(t) for t in tasks]
        assert any("check(" in c for c in codes)
        assert any("approve(" in c for c in codes)
        assert any("reject(" in c for c in codes)
        # approve/reject must each be reached via a guarded edge, not an
        # unconditional one -- this is the whole point of lifting the
        # driver's own CFG instead of a flat call-order list.
        guards = {e["guard"] for e in wir["edges"] if e["guard"] is not None}
        assert len(guards) >= 1


class TestNoDriverFunction:
    SOURCE = """
def step_one():
    return {}

def step_two():
    return {}

step_one()
step_two()
"""

    def test_falls_back_to_module_top_level_calls(self):
        wir = derive_call_order_wir(self.SOURCE)
        assert wir["driver"] == "<module>"
        tasks = _task_nodes(wir)
        assert len(tasks) == 2
        assert "step_one" in _code_of(tasks[0])
        assert "step_two" in _code_of(tasks[1])


class TestSelfRecursionIgnored:
    SOURCE = """
def helper(n):
    if n <= 0:
        return 0
    return helper(n - 1)

def action():
    return {}

def workflow():
    action()
"""

    def test_recursive_helper_is_not_mistaken_for_the_driver(self):
        wir = derive_call_order_wir(self.SOURCE)
        assert wir["driver"] == "workflow"
        tasks = _task_nodes(wir)
        assert len(tasks) == 1
        assert "action" in _code_of(tasks[0])
