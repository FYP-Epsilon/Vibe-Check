"""test_gold_bpmn.py -- tests for the independent gold BPMN labeler.

Includes the two load-bearing checks without which the structural-fidelity
numbers would be worthless:

1. **Anti-circularity** -- ``gold_bpmn.py`` must never import anything from
   ``module_01_spec/src/``, or the extractor is being graded against a copy
   of itself. Same discipline as ``module_02_extract/eval/test_gold_wir.py``.
2. **Non-vacuity** -- the metric reports node/edge F1 = 1.0000 on the whole
   corpus. A metric that cannot fail is not evidence, so these tests inject
   known defects and assert the score actually drops.
"""

from __future__ import annotations

import ast
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).resolve().parent
MODULE01_DIR = EVAL_DIR.parent
sys.path.insert(0, str(EVAL_DIR))
sys.path.insert(0, str(MODULE01_DIR / "src"))

import gold_bpmn  # noqa: E402
from gold_bpmn import (  # noqa: E402
    BPMN_NS,
    SPEC_FLOW_NODES,
    corpus_files,
    gold_label,
    score_sets,
    uid_of,
)
from semantic_extractor import SemanticExtractionEngine  # noqa: E402

GOLD_SOURCE = Path(gold_bpmn.__file__)

MINIMAL_BPMN = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                  targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_1" isExecutable="false">
    <bpmn:startEvent id="Start_1" />
    <bpmn:task id="Task_A" name="Do A" />
    <bpmn:exclusiveGateway id="GW_1" />
    <bpmn:task id="Task_B" name="Do B" />
    <bpmn:endEvent id="End_1" />
    <bpmn:sequenceFlow id="F1" sourceRef="Start_1" targetRef="Task_A" />
    <bpmn:sequenceFlow id="F2" sourceRef="Task_A" targetRef="GW_1" />
    <bpmn:sequenceFlow id="F3" sourceRef="GW_1" targetRef="Task_B" />
    <bpmn:sequenceFlow id="F4" sourceRef="GW_1" targetRef="End_1" />
    <bpmn:sequenceFlow id="F5" sourceRef="Task_B" targetRef="End_1" />
  </bpmn:process>
  <bpmndi:BPMNDiagram id="Diagram_1">
    <bpmndi:BPMNPlane id="Plane_1" bpmnElement="Process_1">
      <bpmndi:BPMNShape id="Shape_1" bpmnElement="Task_A">
        <dc:Bounds x="0" y="0" width="100" height="80" />
      </bpmndi:BPMNShape>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>
"""


class TestAntiCircularity:
    """gold_bpmn.py must be derivable from the BPMN spec alone."""

    def test_gold_bpmn_never_imports_from_src(self):
        tree = ast.parse(GOLD_SOURCE.read_text(encoding="utf-8"))
        forbidden = {
            "semantic_extractor",
            "ltlf_synthesizer",
            "ltlf_eval",
            "ltlf_progression",
            "mutation_refiner",
            "trace_synthesizer",
            "bidirectional_alignment",
            "adversarial_generator",
            "api",
            "main",
        }
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        offenders = imported & forbidden
        assert not offenders, (
            "gold_bpmn.py imports %s from the system under test -- the "
            "structural-fidelity numbers would be circular" % sorted(offenders)
        )

    def test_gold_vocabulary_is_not_a_copy_of_the_extractor(self):
        """The allowlist is transcribed from BPMN 2.0, not from src/.

        If someone ever "tidies" SPEC_FLOW_NODES into equality with
        EXECUTABLE_NODES, agreement becomes definitional. These three
        BPMN 2.0 activity/gateway subclasses are in the standard and absent
        from the extractor, and must stay in the gold vocabulary.
        """
        extractor_vocab = set(SemanticExtractionEngine.EXECUTABLE_NODES)
        spec_only = SPEC_FLOW_NODES - extractor_vocab
        assert {"transaction", "adHocSubProcess", "complexGateway"} <= spec_only


class TestLabeler:
    def test_nodes_and_edges_on_minimal_diagram(self):
        gold = gold_label(MINIMAL_BPMN)
        assert gold["nodes"] == {
            ("Start_1", "startEvent"),
            ("Task_A", "task"),
            ("GW_1", "exclusiveGateway"),
            ("Task_B", "task"),
            ("End_1", "endEvent"),
        }
        assert gold["edges"] == {
            ("F1", "Start_1", "Task_A"),
            ("F2", "Task_A", "GW_1"),
            ("F3", "GW_1", "Task_B"),
            ("F4", "GW_1", "End_1"),
            ("F5", "Task_B", "End_1"),
        }

    def test_presentation_elements_are_never_nodes(self):
        """bpmndi:/dc: shapes carry ids but are not flow nodes."""
        node_ids = {nid for nid, _t in gold_label(MINIMAL_BPMN)["nodes"]}
        assert "Shape_1" not in node_ids
        assert "Plane_1" not in node_ids
        assert "Diagram_1" not in node_ids

    def test_branch_detection_uses_out_degree(self):
        gold = gold_label(MINIMAL_BPMN)
        assert gold["has_branch"] is True
        assert gold["branch_points"] == ["GW_1"]

    def test_linear_diagram_has_no_branch(self):
        linear = MINIMAL_BPMN.replace(
            '<bpmn:sequenceFlow id="F4" sourceRef="GW_1" targetRef="End_1" />', ""
        )
        assert gold_label(linear)["has_branch"] is False

    def test_duplicate_activity_names_are_reported(self):
        dup = MINIMAL_BPMN.replace('name="Do B"', 'name="Do A"')
        assert gold_label(dup)["duplicate_names"] == {"Do_A": ["Task_A", "Task_B"]}

    def test_uid_of_strips_corpus_suffix(self):
        assert uid_of(Path("flow-bench/data/output/uid_20_output.bpmn")) == "uid_20"
        assert uid_of(Path("flow-bench/data/context/uid_92_context.bpmn")) == "uid_92"


class TestMetricIsNotVacuous:
    """The corpus scores F1 = 1.0000. Prove the metric *can* score lower.

    Defects are injected into the XML the extractor sees while the gold
    labels stay pinned to the pristine document, so any score drop is the
    metric detecting a genuine gold-vs-extracted discrepancy.
    """

    @staticmethod
    def _first_corpus_file() -> Path:
        files = corpus_files("output")
        if not files:
            pytest.skip("FLOW-BENCH corpus not present")
        return files[0]

    def _score_against_pristine_gold(self, pristine: str, mutated_xml: str):
        gold = gold_label(pristine)["nodes"]
        graph = SemanticExtractionEngine(mutated_xml).run_pipeline()["semantic_graph"]
        got = {(s["node_id"], s["node_type"]) for s in graph["states"]}
        return score_sets(gold, got)

    def test_baseline_is_exact(self):
        pristine = self._first_corpus_file().read_text(encoding="utf-8")
        scores = self._score_against_pristine_gold(pristine, pristine)
        assert scores["fp"] == 0 and scores["fn"] == 0
        assert scores["f1"] == pytest.approx(1.0)

    def test_deleting_a_node_lowers_recall(self):
        pristine = self._first_corpus_file().read_text(encoding="utf-8")
        root = ET.fromstring(pristine)
        removed = False
        for parent in root.iter():
            kids = [c for c in list(parent) if c.tag == "{%s}task" % BPMN_NS]
            if kids:
                parent.remove(kids[0])
                removed = True
                break
        assert removed, "corpus diagram unexpectedly has no bpmn:task"
        scores = self._score_against_pristine_gold(
            pristine, ET.tostring(root, encoding="unicode")
        )
        assert scores["fn"] >= 1
        assert scores["recall"] < 1.0
        assert scores["f1"] < 1.0

    def test_retyping_a_node_lowers_precision_and_recall(self):
        pristine = self._first_corpus_file().read_text(encoding="utf-8")
        root = ET.fromstring(pristine)
        retyped = False
        for elem in root.iter():
            if elem.tag == "{%s}task" % BPMN_NS:
                elem.tag = "{%s}userTask" % BPMN_NS
                retyped = True
                break
        assert retyped, "corpus diagram unexpectedly has no bpmn:task"
        scores = self._score_against_pristine_gold(
            pristine, ET.tostring(root, encoding="unicode")
        )
        assert scores["fp"] >= 1 and scores["fn"] >= 1
        assert scores["f1"] < 1.0


class TestScoreSets:
    def test_perfect_match(self):
        s = score_sets({1, 2, 3}, {1, 2, 3})
        assert (s["tp"], s["fp"], s["fn"]) == (3, 0, 0)
        assert s["f1"] == pytest.approx(1.0)

    def test_partial_match(self):
        s = score_sets({1, 2, 3}, {2, 3, 4})
        assert (s["tp"], s["fp"], s["fn"]) == (2, 1, 1)
        assert s["precision"] == pytest.approx(2 / 3)
        assert s["recall"] == pytest.approx(2 / 3)

    def test_empty_gold_and_empty_extracted_is_not_an_error(self):
        s = score_sets(set(), set())
        assert s["f1"] == pytest.approx(1.0)
