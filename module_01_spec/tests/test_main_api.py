"""
tests/test_main_api.py
========================
Next Steps.md item #8: main.py's FastAPI route and status-code vocabulary
had zero tests -- including a regression test for the real startup bug
(main.py:11,16 imported the deleted automata_lifter module, so the whole
app -- and the Docker `uvicorn` CMD -- crashed before serving a single
request; fixed 2026-07-29, see Next Steps.md item 1).

Calls verify_spec() directly as a plain function rather than going through
fastapi.testclient.TestClient, which requires an httpx dependency this
project doesn't otherwise need -- FastAPI route handlers are ordinary
Python functions and HTTPException is a real, catchable exception either
way.
"""

import importlib.util
import os
import sys

_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, _SRC_DIR)

import pytest
from fastapi import HTTPException


def _load_main():
    """module_01_spec/src/main.py and module_03_equiv/src/main.py share the
    same bare module name "main" -- a plain `import main` is a real hazard
    in this test session specifically because
    test_export_for_module_03.py's test_real_export_is_ingestible_by_module_03
    inserts module_03_equiv/src onto sys.path *ahead* of module_01_spec/src
    (confirmed empirically: a bare `import main` after that test runs
    resolves to the wrong file's main.py). Loading by explicit file path
    under a private module name sidesteps sys.modules collision entirely,
    regardless of what other test files do to sys.path or run order."""
    spec = importlib.util.spec_from_file_location(
        "module_01_spec_main_under_test", os.path.join(_SRC_DIR, "main.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

_HAPPY_XML = """<?xml version="1.0" encoding="UTF-8"?>
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

_PHASE_1_GATE_FAIL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_1" isExecutable="true">
  </bpmn:process>
</bpmn:definitions>
"""


def test_app_imports_and_constructs_without_error():
    """Regression test for the startup bug: main.py used to import a
    deleted `automata_lifter` module at import time, so this import alone
    (not even a request) crashed the whole spec-engine, Docker CMD
    included. Must always succeed."""
    from fastapi import FastAPI

    main = _load_main()
    assert isinstance(main.app, FastAPI)


def test_read_root_reports_online():
    main = _load_main()
    result = main.read_root()
    assert result["status"] == "online"


def test_empty_bpmn_xml_is_a_400():
    main = _load_main()
    with pytest.raises(HTTPException) as exc_info:
        main.verify_spec(main.BPMNPayload(bpmn_xml="   "))
    assert exc_info.value.status_code == 400


def test_malformed_xml_is_a_400_syntax_error():
    """SemanticExtractionEngine.__init__ raises a bare ValueError on
    unparseable XML -- main.py now maps that to an explicit 400 SYNTAX_ERROR
    (previously fell through to the generic 500 branch; item #10's status-code
    vocabulary pass)."""
    main = _load_main()
    with pytest.raises(HTTPException) as exc_info:
        main.verify_spec(main.BPMNPayload(bpmn_xml="not xml at all"))
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error_code"] == "SYNTAX_ERROR"


def test_phase_1_gate_fail_is_a_422_with_the_certificate_attached():
    """A process with zero executable nodes is a genuine, still-reachable FAIL
    through real end-to-end XML. The vendor-namespaced-extension-element
    fixture this test previously used no longer fails post-namespace-aware-scan
    (see test_phase1_gate.py::test_unmappable_non_bpmn_extension_element_is_safely_ignored)
    -- and no BPMN-namespaced substitute works either: _recovery_pass() sweeps
    up any id-bearing BPMN-namespaced element not already mapped (its own
    NON_NODE_TAGS is a strict subset of V3's), so an unmappable-but-namespaced
    node self-heals to PASS just like the out-of-scope-node case does. Checked
    empirically, not assumed."""
    main = _load_main()
    with pytest.raises(HTTPException) as exc_info:
        main.verify_spec(main.BPMNPayload(bpmn_xml=_PHASE_1_GATE_FAIL_XML))
    detail = exc_info.value.detail
    assert exc_info.value.status_code == 422
    assert detail["error_code"] == "PHASE_1_GATE_FAIL"
    assert detail["certificate"]["status"] == "FAIL"


def test_happy_path_returns_a_known_status_and_all_phase_keys():
    """A real BPMN diagram all the way through Phase 1-4 (PBCTS included).
    Asserts against the two overall_status values main.py can currently
    emit -- not pinning which one this particular fixture lands on, since
    PBCTS convergence for a real synthesized property suite is its own
    concern (see test_pbcts_convergence.py)."""
    main = _load_main()
    result = main.verify_spec(main.BPMNPayload(bpmn_xml=_HAPPY_XML, seed=1))
    assert result["status"] in ("PASS", "PASS_PBCTS_UNCONVERGED")
    assert set(result.keys()) == {"status", "phase_1", "phase_2", "phase_3", "phase_4", "phase_5"}
    assert result["phase_1"]["phase_1_certificate"]["status"] == "PASS"
