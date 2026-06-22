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
from main import _derive_v1_params
from z3_sym_engine import run_v2_pipeline
from dynamic_tracer import run_v1_pipeline, MultiModalCertificateComposer


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
