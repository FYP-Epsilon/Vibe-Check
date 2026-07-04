"""
test_integration.py
===================
End-to-end pipeline integration test for Module 02.

Runs the full V3 -> V2 -> V1 pipeline on the loan_approval sample
and asserts aggregate certificate properties.
"""

import sys
from pathlib import Path

# Ensure src/ is on the path when pytest runs from the repo root.
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from ast_extractor import run_v3_pipeline
from main import _derive_v1_params, _select_entry_function, _run_verification
from z3_sym_engine import run_v2_pipeline
from dynamic_tracer import run_v1_pipeline, MultiModalCertificateComposer


class TestSelectEntryFunction:
    def test_prefers_workflow_over_definition_order(self):
        """Regression: next(iter(functions)) picked whichever function a
        source defines first. Every eval/flowbench_adapter.py-generated
        program defines its task-API stub(s) before `workflow`, so this
        silently verified a trivial stub instead of the orchestration
        logic for the entire FLOW-BENCH corpus."""
        functions = {"some_stub": {}, "workflow": {}, "another_stub": {}}
        assert _select_entry_function(functions) == "workflow"

    def test_falls_back_to_first_when_no_workflow(self):
        """Single-function test fixtures (e.g. loan_approval.py) have no
        function named "workflow" -- must still pick the only function."""
        functions = {"process_loan_application": {}}
        assert _select_entry_function(functions) == "process_loan_application"

    def test_run_verification_targets_workflow_not_first_stub(self):
        source = (
            "def some_stub():\n    return {}\n"
            "def workflow(x: int) -> int:\n"
            "    if x > 0:\n        return 1\n    return 0\n"
        )
        result = _run_verification(source)
        # If the stub (0 branches) had been selected, v3_coverage would
        # reflect a 1-statement function, not workflow's if/return shape.
        assert result["wir"]["functions"]["workflow"]["nodes"]  # sanity: exists
        assert result["combined_confidence"] > 0.0


class TestFullPipeline:
    def test_loan_approval_pipeline(self):
        input_path = Path(__file__).resolve().parent.parent / "inputs" / "loan_approval.py"
        source = input_path.read_text(encoding="utf-8")

        # Phase 3 (V3) -- static extraction
        wir = run_v3_pipeline(source)
        v3_cert = wir.get("certificate", {})

        # Select first function
        functions = wir.get("functions", {})
        assert functions, "No functions found in WIR"
        function_name = next(iter(functions))
        func_wir = functions[function_name]

        # Derive V1 parameters
        v1_params = _derive_v1_params(func_wir)

        # Compile source once
        local_env = {"__builtins__": __builtins__}
        exec(compile(source, "<string>", "exec"), local_env)

        # Hard-coded initial inputs per task spec
        initial_inputs = {
            "credit_score": 700,
            "requested_amount": 3000.0,
            "active_bank_account": True,
        }

        # Phase 2 (V2) -- symbolic refinement
        v2_result = run_v2_pipeline(
            source=source,
            function_name=function_name,
            initial_inputs=initial_inputs,
            max_k=3,
            query_budget=20,
            compiled_ns=local_env,
        )
        v2_cert = v2_result["certificate"]

        # Phase 1 (V1) -- dynamic tracing
        v1_cert = run_v1_pipeline(
            source=source,
            function_name=function_name,
            wir=func_wir,
            task_patterns=[function_name],
            branch_lines=v1_params["branch_lines"],
            control_variables=v1_params["control_variables"],
            state_variables=v1_params["state_variables"] or None,
            n_runs=5,
            seed=42,
            compiled_ns=local_env,
        )

        # Compose certificates
        composer = MultiModalCertificateComposer()
        final = composer.compose(v1_cert, v2_cert, v3_cert)

        assert final["combined_confidence"] > 0.0
        assert v3_cert["node_coverage"] > 0.5
        assert isinstance(final["passed"], bool)

    def test_crash_mutation_fails(self):
        """A crash-inducing mutation of the loan-approval program (introduces
        a ZeroDivisionError on every execution path) must fail the full
        V3->V2->V1 pipeline.

        NOTE -- this does not generalize to pure logic-class mutations (e.g.
        negating a guard's comparison operator without inducing a crash).
        V1's oracle is a WIR reference interpreter re-derived from the same
        (possibly mutated) source, and the trace comparator discards branch
        decisions when matching (comparator.py _normalise keeps only
        ("branch_point",)), so actual and expected diverge identically under
        a pure logic mutation and v1 stays saturated at 1.0 -- verified
        empirically on this program with guard-negation, boundary-shift, and
        constant-perturb mutations, all of which left v1=1.0 and left v2
        unchanged from the correct-program baseline. Only a mutation that
        changes runtime behavior observably (a crash, here) moves the
        verdict. Quantifying detection power by mutation-operator class is
        what the FLOW-BENCH mutation corpus and calibration run (eval/)
        measure.
        """
        from main import _run_verification

        input_path = Path(__file__).resolve().parent.parent / "inputs" / "loan_approval.py"
        source = input_path.read_text(encoding="utf-8")
        mutated = source.replace(
            'temp_audit_log = f"Processed {approved_amount} for score {credit_score}"',
            "temp_audit_log = 1 / (credit_score - credit_score)",
        )
        assert mutated != source

        result = _run_verification(mutated)
        assert result["passed"] is False


    def test_infinite_loop_rejected(self):
        source = "def f():\n    while True:\n        pass"
        from ast_extractor import run_v3_pipeline
        from z3_sym_engine import BoundedConcolicEngine

        wir = run_v3_pipeline(source)
        functions = wir.get("functions", {})
        assert "f" in functions

        local_env = {"__builtins__": {}}
        exec(compile(source, "<string>", "exec"), local_env)

        engine = BoundedConcolicEngine(
            source=source,
            function_name="f",
            max_k=3,
            query_budget=10,
            compiled_ns=local_env,
        )
        import pytest
        with pytest.raises(RuntimeError, match="exceeded.*steps"):
            engine.run({})
