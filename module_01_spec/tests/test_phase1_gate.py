"""
tests/test_phase1_gate.py
==========================
Next Steps.md item #8: Phase 1's quality gate (semantic_extractor.py's
_layer_v1_certify, Milestone P1.5) had zero tests. Covers the gate's own
PASS/FAIL boundary (node_coverage_Y_Struct >= 1.0) directly, plus the
self-healing recovery pass that can turn an initial FAIL back into PASS.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from semantic_extractor import SemanticExtractionEngine

_MINIMAL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_1" isExecutable="true" />
</bpmn:definitions>
"""

_LINEAR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_1" isExecutable="true">
    <bpmn:startEvent id="Start_1" name="Start" />
    <bpmn:task id="Task_A" name="Approve" />
    <bpmn:endEvent id="End_1" name="End" />
    <bpmn:sequenceFlow id="F1" sourceRef="Start_1" targetRef="Task_A" />
    <bpmn:sequenceFlow id="F2" sourceRef="Task_A" targetRef="End_1" />
  </bpmn:process>
</bpmn:definitions>
"""

# A custom, non-BPMN-namespaced element with an id: _layer_v3_sanitize counts
# any element with an id whose *local* tag isn't in NON_NODE_TAGS as an
# executable node needing mapping (no namespace check there), but both
# _layer_v2_construct_and_label and _recovery_pass only ever look at
# elements in the BPMN namespace -- so this can never be mapped, and stays
# a genuine, unrecoverable gate FAIL. Confirmed against source, not assumed.
_UNMAPPABLE_EXTENSION_XML = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:vendor="http://example.com/vendor"
                  targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_1" isExecutable="true">
    <bpmn:startEvent id="Start_1" name="Start" />
    <bpmn:task id="Task_A" name="Approve" />
    <bpmn:endEvent id="End_1" name="End" />
    <bpmn:sequenceFlow id="F1" sourceRef="Start_1" targetRef="Task_A" />
    <bpmn:sequenceFlow id="F2" sourceRef="Task_A" targetRef="End_1" />
    <vendor:widget id="Vendor_1" />
  </bpmn:process>
</bpmn:definitions>
"""

# A task defined outside any <bpmn:process> scope: V2's process-scoped
# findall misses it (FAIL on the first pass), but _recovery_pass searches
# from the XML root and picks up any un-mapped bpmn:-namespaced element --
# so this must self-heal back to PASS.
_OUT_OF_PROCESS_SCOPE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_1" isExecutable="true">
    <bpmn:startEvent id="Start_1" name="Start" />
    <bpmn:endEvent id="End_1" name="End" />
    <bpmn:sequenceFlow id="F1" sourceRef="Start_1" targetRef="Task_A" />
    <bpmn:sequenceFlow id="F2" sourceRef="Task_A" targetRef="End_1" />
  </bpmn:process>
  <bpmn:task id="Task_A" name="Approve" />
</bpmn:definitions>
"""


class TestGateBoundaryDirect:
    """Exercises _layer_v1_certify's own PASS/FAIL threshold directly,
    isolated from BPMN-parsing specifics."""

    def _engine(self) -> SemanticExtractionEngine:
        return SemanticExtractionEngine(_MINIMAL_XML)

    def test_exactly_full_coverage_passes(self):
        eng = self._engine()
        eng.executable_nodes_count = 3
        eng.mapped_nodes_count = 3
        cert = eng._layer_v1_certify()
        assert cert["status"] == "PASS"
        assert cert["node_coverage_Y_Struct"] == 1.0

    def test_just_below_full_coverage_fails(self):
        eng = self._engine()
        eng.executable_nodes_count = 3
        eng.mapped_nodes_count = 2
        cert = eng._layer_v1_certify()
        assert cert["status"] == "FAIL"
        assert cert["node_coverage_Y_Struct"] < 1.0

    def test_zero_executable_nodes_is_a_fail_not_a_vacuous_pass(self):
        """Checked, not assumed: the `if executable_nodes_count > 0` guard
        only prevents a ZeroDivisionError -- it leaves node_coverage at its
        0.0 default rather than special-casing it to 1.0, so a genuinely
        empty/degenerate diagram correctly FAILs the gate instead of
        vacuously passing (there is nothing to certify as covered)."""
        eng = self._engine()
        eng.executable_nodes_count = 0
        eng.mapped_nodes_count = 0
        cert = eng._layer_v1_certify()
        assert cert["status"] == "FAIL"
        assert cert["node_coverage_Y_Struct"] == 0.0


class TestGateEndToEnd:
    """The same boundary, driven through real BPMN XML via run_pipeline()."""

    def test_fully_covered_linear_diagram_passes(self):
        result = SemanticExtractionEngine(_LINEAR_XML).run_pipeline()
        assert result["phase_1_certificate"]["status"] == "PASS"
        assert result["phase_1_certificate"]["node_coverage_Y_Struct"] == 1.0

    def test_out_of_process_scope_node_self_heals_to_pass(self):
        """First pass under-counts (Task_A outside <process> scope); the
        recovery pass's root-level scan must bring it back to PASS."""
        result = SemanticExtractionEngine(_OUT_OF_PROCESS_SCOPE_XML).run_pipeline()
        assert result["phase_1_certificate"]["status"] == "PASS"
        recovered = [s for s in result["semantic_graph"]["states"] if s.get("recovered")]
        assert len(recovered) == 1
        assert recovered[0]["node_id"] == "Task_A"

    def test_unmappable_non_bpmn_extension_element_is_a_genuine_unrecoverable_fail(self):
        """A non-BPMN-namespaced element with an id is counted toward
        executable_nodes_count by V3's namespace-blind scan, but neither
        V2 nor the recovery pass (both BPMN-namespace-scoped) can ever map
        it -- confirmed to survive self-healing, not just assumed."""
        result = SemanticExtractionEngine(_UNMAPPABLE_EXTENSION_XML).run_pipeline()
        assert result["phase_1_certificate"]["status"] == "FAIL"
        assert result["phase_1_certificate"]["node_coverage_Y_Struct"] < 1.0
