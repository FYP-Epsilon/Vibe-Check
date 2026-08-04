import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from ltlf_synthesizer import FLTLSynthesizer

@pytest.fixture
def sample_graph():
    return {
        "semantic_graph": {
            "initial_state": "Start_1",
            "states": [
                {"node_id": "Start_1", "node_type": "startEvent", "atomic_propositions": ["node(start)"]},
                {"node_id": "Task_1", "node_type": "task", "atomic_propositions": ["start(T1)", "done(T1)"]},
                {"node_id": "Gateway_1", "node_type": "exclusiveGateway", "atomic_propositions": ["node(xor)"]},
                {"node_id": "Task_2", "node_type": "task", "atomic_propositions": ["start(T2)", "done(T2)"]},
                {"node_id": "End_1", "node_type": "endEvent", "atomic_propositions": ["node(end)"]}
            ],
            "edges": [
                {"source_id": "Start_1", "target_id": "Task_1"},
                {"source_id": "Task_1", "target_id": "Gateway_1"},
                {"source_id": "Gateway_1", "target_id": "Task_2"},
                {"source_id": "Task_2", "target_id": "End_1"}
            ]
        }
    }

def test_ltlf_synthesizer(sample_graph):
    synthesizer = FLTLSynthesizer(sample_graph)
    result = synthesizer.run_pipeline()

    assert result["phase_2_certificate"]["status"] == "PASS"
    suite = result["ltlf_property_suite"]
    assert "P1_Structural_Control_Flow" in suite
    assert "P0_Critical_Sentinels" in suite

    # Check that structural flow properties for tasks are generated properly
    has_flow = any("!start(T2)W(done(T1))" in p.replace(" ", "") for p in suite["P1_Structural_Control_Flow"])
    assert has_flow, f"Expected a bridged control flow property for Task_1 -> Task_2, got: {suite['P1_Structural_Control_Flow']}"


def _two_predecessor_graph(gateway_type):
    """TaskA and TaskB both feed a single gateway of the given type, which
    feeds TaskC. Mirrors the real-corpus merge shapes found in
    demo/spiffworkflow/dataset/bpmn/spiff_cli_call_activity.bpmn (exclusive)
    and spiff_model_misc_test_a23_a_2_3.bpmn (parallel)."""
    return {
        "semantic_graph": {
            "initial_state": "Start_1",
            "states": [
                {"node_id": "Start_1", "node_type": "startEvent", "atomic_propositions": ["node(start)"]},
                {"node_id": "Split", "node_type": gateway_type, "atomic_propositions": ["node(split)"]},
                {"node_id": "TaskA", "node_type": "task", "atomic_propositions": ["start(TaskA)", "done(TaskA)"]},
                {"node_id": "TaskB", "node_type": "task", "atomic_propositions": ["start(TaskB)", "done(TaskB)"]},
                {"node_id": "Join", "node_type": gateway_type, "atomic_propositions": ["node(join)"]},
                {"node_id": "TaskC", "node_type": "task", "atomic_propositions": ["start(TaskC)", "done(TaskC)"]},
                {"node_id": "End_1", "node_type": "endEvent", "atomic_propositions": ["node(end)"]},
            ],
            "edges": [
                {"source_id": "Start_1", "target_id": "Split"},
                {"source_id": "Split", "target_id": "TaskA"},
                {"source_id": "Split", "target_id": "TaskB"},
                {"source_id": "TaskA", "target_id": "Join"},
                {"source_id": "TaskB", "target_id": "Join"},
                {"source_id": "Join", "target_id": "TaskC"},
                {"source_id": "TaskC", "target_id": "End_1"},
            ],
        }
    }


def test_exclusive_gateway_join_emits_disjunction_not_conjunction():
    """Regression for the OR->AND precedence bug: a target task merged from
    an exclusive-gateway join must only require that ONE of its predecessor
    branches completed, not both -- only one branch ever executes on a real
    trace, so requiring both would flag every compliant execution as a
    violation (confirmed against spiff_cli_call_activity.bpmn's real
    Gateway_0y2l88d -> Activity_1x0wxtq join, which has this exact shape)."""
    graph = _two_predecessor_graph("exclusiveGateway")
    result = FLTLSynthesizer(graph).run_pipeline()
    suite = result["ltlf_property_suite"]

    tgt_formulas = [p for p in suite["P1_Structural_Control_Flow"] if p.startswith("!start(TaskC)")]
    assert len(tgt_formulas) == 1, (
        f"expected exactly one (disjunctive) precedence formula for TaskC, "
        f"got: {tgt_formulas}"
    )
    formula = tgt_formulas[0].replace(" ", "")
    assert "done(TaskA)" in formula and "done(TaskB)" in formula and "|" in formula


def test_parallel_gateway_join_emits_conjunction():
    """A genuine AND-join (parallelGateway) really does require every
    incoming branch to finish before the join task starts, so a
    per-predecessor formula for each branch is correct here -- unlike the
    exclusive-gateway case above."""
    graph = _two_predecessor_graph("parallelGateway")
    result = FLTLSynthesizer(graph).run_pipeline()
    suite = result["ltlf_property_suite"]

    tgt_formulas = [p.replace(" ", "") for p in suite["P1_Structural_Control_Flow"] if p.startswith("!start(TaskC)")]
    assert len(tgt_formulas) == 2, (
        f"expected two (conjunctive) precedence formulas for TaskC, got: {tgt_formulas}"
    )
    assert "!start(TaskC)Wdone(TaskA)" in tgt_formulas
    assert "!start(TaskC)Wdone(TaskB)" in tgt_formulas
