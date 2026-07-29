"""
tests/test_status_code_consistency.py
=======================================
Next Steps.md item #10: api.py's run_module_01_pipeline() and main.py's
/verify route used two different, semantically-opposed status strings for
the identical outcome (PBCTS ran to completion but IDCD didn't converge
within budget, no errors elsewhere): api.py said "FAIL_ALIGNMENT_UNPROVEN",
main.py said "PASS_PBCTS_UNCONVERGED". Unified on the latter -- confirmed
correct, not just consistent, by export_for_module_03's own FAIL-blocklist
never having included either variant: an unconverged result has always
been treated as valid, exportable output, so labelling it FAIL disagreed
with this codebase's own actual behavior toward it.

Uses one real BPMN fixture through both paths (api.py's function call and
main.py's route function) to prove they now genuinely agree, not just that
each individually emits some plausible-looking string.
"""

import importlib.util
import os
import sys

_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, _SRC_DIR)

from api import export_for_module_03, run_module_01_pipeline

# See test_main_api.py's _load_main for why this can't be a plain
# `import main` -- module_03_equiv/src/main.py shares the bare name.
def _load_main():
    spec = importlib.util.spec_from_file_location(
        "module_01_spec_main_under_test_status_codes", os.path.join(_SRC_DIR, "main.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

_XML = """<?xml version="1.0" encoding="UTF-8"?>
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


def test_api_and_main_agree_on_the_unconverged_status_string():
    api_result = run_module_01_pipeline(_XML, seed=1)

    main = _load_main()
    main_result = main.verify_spec(main.BPMNPayload(bpmn_xml=_XML, seed=1))

    # Both paths hit the same real non-convergence outcome for this
    # fixture (confirmed, not assumed -- see the module docstring).
    assert api_result["status"] == "PASS_PBCTS_UNCONVERGED"
    assert main_result["status"] == "PASS_PBCTS_UNCONVERGED"
    assert api_result["status"] == main_result["status"]
    assert "FAIL" not in api_result["status"]


def test_unconverged_result_is_still_exportable_to_module_03():
    """The status rename must not change export_for_module_03's own
    behavior -- it never blocklisted either status string, so an
    unconverged result was always treated as valid output; this just
    makes the label agree with that existing behavior instead of
    contradicting it."""
    result = run_module_01_pipeline(_XML, seed=1)
    assert result["status"] == "PASS_PBCTS_UNCONVERGED"

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "module_03_input.json")
        export_for_module_03(result, filepath=filepath)  # must not raise
        assert os.path.exists(filepath)
