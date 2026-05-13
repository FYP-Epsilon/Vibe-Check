import json
import time

import requests
import streamlit as st

st.set_page_config(
    page_title="VibeCheck Portal",
    page_icon="🛡️",
    layout="wide",
)

st.title("VibeCheck: Formal Verification Portal")

with st.sidebar:
    st.header("Engine Status")
    st.markdown("✅ V1 — Spec Engine")
    st.markdown("✅ V2 — Extract Engine")
    st.markdown("✅ V3 — Equiv Engine")

st.subheader("Input")
workflow_code = st.text_area(
    "LLM-Generated Python Workflow Code",
    height=300,
    placeholder="Paste your generated Python workflow code here...",
)

if st.button("Run Verification Pipeline", type="primary"):
    if not workflow_code.strip():
        st.warning("Please paste some workflow code before running the pipeline.")
    else:
        with st.spinner("Analyzing structural and symbolic equivalence..."):
            try:
                response = requests.post(
                    "http://extract-engine:8000/verify",
                    json={"source_code": workflow_code},
                    timeout=120,
                )
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.RequestException as exc:
                st.error(f"Backend request failed: {exc}")
                st.stop()

        st.divider()
        st.subheader("Verification Results")

        cols = st.columns(4)
        cols[0].metric("V3 Coverage", f"{data.get('v3_coverage', 0) * 100:.1f}%")
        cols[1].metric("V2 Confidence", f"{data.get('v2_confidence', 0) * 100:.1f}%")
        cols[2].metric("V1 Confidence", f"{data.get('v1_confidence', 0) * 100:.1f}%")
        cols[3].metric("Combined Confidence", f"{data.get('combined_confidence', 0) * 100:.1f}%")

        passed = data.get("passed", False)
        if passed:
            st.success(f"✅ PASSED — {data.get('message', '')}")
        else:
            st.error(f"❌ FAILED — {data.get('message', '')}")

        st.subheader("🔍 Engine Telemetry Deep-Dive")
        tab1, tab2, tab3 = st.tabs(["V3: Structural (AST)", "V2: Symbolic (Z3)", "V1: Dynamic (Tracer)"])

        with tab1:
            v3 = data.get("v3_details", {})
            if v3:
                c1, c2, c3 = st.columns(3)
                c1.metric("Nodes", v3.get("nodes", "N/A"))
                c2.metric("Edges", v3.get("edges", "N/A"))
                c3.metric("Node Coverage", f"{v3.get('node_coverage', 0) * 100:.1f}%")
                st.json(v3)
            else:
                st.info("No V3 telemetry available.")

        with tab2:
            v2 = data.get("v2_details", {})
            if v2:
                c1, c2, c3 = st.columns(3)
                c1.metric("Iterations", v2.get("iterations", "N/A"))
                c2.metric("Feasible Paths", v2.get("feasible_paths", "N/A"))
                c3.metric("Solver Success", f"{v2.get('solver_success_rate', 0) * 100:.1f}%")
                st.json(v2)
            else:
                st.info("No V2 telemetry available.")

        with tab3:
            v1 = data.get("v1_details", {})
            if v1:
                c1, c2, c3 = st.columns(3)
                c1.metric("Matching Traces", v1.get("matching_traces", "N/A"))
                c2.metric("Total Runs", v1.get("total_runs", "N/A"))
                c3.metric("Input Coverage", f"{v1.get('input_coverage_score', 0) * 100:.1f}%")
                st.json(v1)
            else:
                st.info("No V1 telemetry available.")

        st.divider()
        st.subheader("📦 Compiled WIR Output")

        wir = data.get("wir", {})
        with st.expander("View Raw JSON WIR"):
            st.json(wir)

        st.download_button(
            label="📥 Download WIR JSON",
            data=json.dumps(wir, indent=2),
            file_name="wir_output.json",
            mime="application/json",
        )
