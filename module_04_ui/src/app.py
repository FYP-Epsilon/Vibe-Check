import json
import time
import requests
import streamlit as st
import sys
import os

# Module 01 integration is handled via the spec-engine HTTP API.

st.set_page_config(
    page_title="VibeCheck Portal",
    page_icon="🛡️",
    layout="wide",
)

# ── Custom CSS for clickable engine cards ──────────────────────────────────
st.markdown("""
<style>
    /* Sidebar engine button styling */
    div[data-testid="stSidebar"] .engine-card {
        background: linear-gradient(135deg, rgba(30,36,50,0.95), rgba(22,28,40,0.98));
        border: 1px solid rgba(100,120,200,0.25);
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 8px;
        cursor: pointer;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    div[data-testid="stSidebar"] .engine-card:hover {
        border-color: rgba(100,140,255,0.6);
        box-shadow: 0 0 16px rgba(100,140,255,0.15);
        transform: translateY(-1px);
    }
    div[data-testid="stSidebar"] .engine-card.active {
        border-color: rgba(100,180,255,0.7);
        background: linear-gradient(135deg, rgba(40,50,80,0.95), rgba(30,40,65,0.98));
        box-shadow: 0 0 20px rgba(100,140,255,0.2);
    }
    .engine-title { font-weight: 600; font-size: 0.95rem; margin: 0; }
    .engine-module { font-size: 0.75rem; color: #8892b0; margin: 2px 0 0 0; }
    .status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
    .status-online { background: #00d68f; box-shadow: 0 0 6px #00d68f; }
    .status-idle { background: #ffaa00; box-shadow: 0 0 6px #ffaa00; }
    /* Section headers on engine pages */
    .section-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: #ccd6f6;
        border-bottom: 1px solid rgba(100,120,200,0.2);
        padding-bottom: 6px;
        margin-top: 1.2rem;
    }
    .file-chip {
        display: inline-block;
        background: rgba(100,140,255,0.12);
        border: 1px solid rgba(100,140,255,0.25);
        border-radius: 6px;
        padding: 3px 10px;
        margin: 3px 4px;
        font-family: monospace;
        font-size: 0.82rem;
    }
</style>
""", unsafe_allow_html=True)


# ── Session state for navigation ───────────────────────────────────────────
if "active_page" not in st.session_state:
    st.session_state.active_page = "dashboard"


def navigate(page: str):
    st.session_state.active_page = page


# ── Engine health check helpers ────────────────────────────────────────────
def _check_extract_engine() -> str:
    """Return 'online' or 'idle' for the Extract Engine."""
    try:
        r = requests.get("http://extract-engine:8000/docs", timeout=2)
        return "online" if r.status_code == 200 else "idle"
    except Exception:
        return "idle"


def _check_spec_engine() -> str:
    """Check if Spec Engine (Module 01) is online via API."""
    try:
        r = requests.get("http://spec-engine:8000/docs", timeout=2)
        return "online" if r.status_code == 200 else "idle"
    except Exception:
        return "idle"


def _check_equiv_engine() -> str:
    """Check if Equiv Engine (Module 03) is online via its HTTP API."""
    try:
        r = requests.get("http://equiv-engine:8000/health", timeout=2)
        return "online" if r.status_code == 200 else "idle"
    except Exception:
        return "idle"


# ── Sidebar ────────────────────────────────────────────────────────────────
st.title("VibeCheck: Formal Verification Portal")

with st.sidebar:
    st.header("🛡️ Engines")

    # --- Spec Engine button ---
    spec_status = _check_spec_engine()
    if st.button(
        "🔬  Spec Engine  ·  Module 01",
        key="btn_spec",
        use_container_width=True,
        type="primary" if st.session_state.active_page == "spec_engine" else "secondary",
    ):
        navigate("spec_engine")
        st.rerun()

    # --- Extract Engine button ---
    extract_status = _check_extract_engine()
    if st.button(
        "⚙️  Extract Engine  ·  Module 02",
        key="btn_extract",
        use_container_width=True,
        type="primary" if st.session_state.active_page == "extract_engine" else "secondary",
    ):
        navigate("extract_engine")
        st.rerun()

    # --- Equiv Engine button ---
    equiv_status = _check_equiv_engine()
    if st.button(
        "🔗  Equiv Engine  ·  Module 03",
        key="btn_equiv",
        use_container_width=True,
        type="primary" if st.session_state.active_page == "equiv_engine" else "secondary",
    ):
        navigate("equiv_engine")
        st.rerun()

    st.markdown("---")

    # Dashboard / home button
    if st.button("📊  Dashboard", key="btn_home", use_container_width=True):
        navigate("dashboard")
        st.rerun()

    st.markdown("---")

    # Status summary
    st.caption("Engine Status")
    status_html = ""
    for name, status in [("Spec", spec_status), ("Extract", extract_status), ("Equiv", equiv_status)]:
        dot_class = "status-online" if status == "online" else "status-idle"
        status_html += f'<p style="margin:4px 0;"><span class="status-dot {dot_class}"></span>{name} — {status.title()}</p>'
    st.markdown(status_html, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD (default landing)
# ══════════════════════════════════════════════════════════════════════════
if st.session_state.active_page == "dashboard":
    st.subheader("System Overview")
    st.info("Select an engine from the sidebar to view its details, run verifications, or inspect source components.")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### 🔬 Spec Engine")
        st.markdown(
            "BPMN 2.0 → Semantic Graph → LTLf properties.  \n"
            "Modules: `SemanticExtractionEngine`, `FLTLSynthesizer`, `MutationValidator`"
        )
        if st.button("Open Spec Engine →", key="dash_spec"):
            navigate("spec_engine")
            st.rerun()

    with col2:
        st.markdown("#### ⚙️ Extract Engine")
        st.markdown(
            "Python source → AST CFG → Z3 symbolic → dynamic tracing.  \n"
            "Modules: `CFGExtractor`, `BoundedConcolicEngine`, `MultiModalCertificateComposer`"
        )
        if st.button("Open Extract Engine →", key="dash_extract"):
            navigate("extract_engine")
            st.rerun()

    with col3:
        st.markdown("#### 🔗 Equiv Engine")
        st.markdown(
            "WIR → BDD variable lifting → semantic action matching.  \n"
            "Modules: `AdvancedLifter`, `vibecheck_lifter` (C++/Pybind11)"
        )
        if st.button("Open Equiv Engine →", key="dash_equiv"):
            navigate("equiv_engine")
            st.rerun()

    st.markdown("---")
    mode = st.radio(
        "Quick Launch",
        ["BPMN Spec Verification", "Python Workflow Verification"],
        index=None,
        horizontal=True,
    )
    if mode == "BPMN Spec Verification":
        navigate("spec_engine")
        st.rerun()
    elif mode == "Python Workflow Verification":
        navigate("extract_engine")
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# PAGE: SPEC ENGINE (Module 01)
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.active_page == "spec_engine":
    st.subheader("🔬 Spec Engine — Module 01")

    # Module info tabs
    info_tab, verify_tab = st.tabs(["📂 Module Info", "▶️ Run Verification"])

    with info_tab:
        st.markdown('<p class="section-header">Architecture</p>', unsafe_allow_html=True)
        st.markdown(
            "The Spec Engine converts BPMN 2.0 XML into a formal semantic graph, "
            "synthesises LTLf temporal properties, and validates them via mutation-based refinement."
        )

        st.markdown('<p class="section-header">Pipeline Phases</p>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        col1.metric("Phase 1", "Semantic Extraction")
        col2.metric("Phase 2", "LTLf Synthesis")
        col3.metric("Phase 3", "Mutation Refinement")

        st.markdown('<p class="section-header">Source Components</p>', unsafe_allow_html=True)
        files_html = "".join(
            f'<span class="file-chip">{f}</span>'
            for f in [
                "semantic_extractor.py",
                "ltlf_synthesizer.py",
                "mutation_refiner.py",
                "api.py",
                "main.py",
            ]
        )
        st.markdown(files_html, unsafe_allow_html=True)

        st.markdown('<p class="section-header">Key Classes</p>', unsafe_allow_html=True)
        st.markdown(
            "- `SemanticExtractionEngine` — BPMN XML → Semantic Graph  \n"
            "- `FLTLSynthesizer` — Semantic Graph → LTLf property suite  \n"
            "- `MutationValidator` — Property suite → mutation-refined suite  \n"
            "- `BPMNMutationEngine` — Wodel-style structural mutant generation"
        )

        st.markdown('<p class="section-header">Docker Service</p>', unsafe_allow_html=True)
        st.code("spec-engine  ·  python:3.10-slim  ·  CMD python -m src.main", language="text")

    with verify_tab:
        st.markdown("### BPMN Spec Verification (Module 01)")
        bpmn_xml = st.text_area(
            "BPMN 2.0 XML Content",
            height=300,
            placeholder='<?xml version="1.0" encoding="UTF-8"?>...',
        )

        if st.button("Run Spec Verification", type="primary"):
            if not bpmn_xml.strip():
                st.warning("Please provide BPMN XML content.")
            else:
                with st.spinner("Executing Module 01 Pipeline..."):
                    try:
                        response = requests.post(
                            "http://spec-engine:8000/verify",
                            json={"bpmn_xml": bpmn_xml},
                            timeout=120,
                        )
                        response.raise_for_status()
                        res_data = response.json()
                        p1_result = res_data["phase_1"]
                        p2_result = res_data["phase_2"]
                        p3_result = res_data["phase_3"]

                        st.divider()
                        st.subheader("Spec Verification Results")

                        m1, m2, m3 = st.columns(3)
                        m1.metric("Node Coverage", f"{p1_result['phase_1_certificate']['node_coverage_Y_Struct'] * 100:.1f}%")
                        m2.metric("Guard Resolution", f"{p2_result['phase_2_certificate']['guard_resolution_coverage'] * 100:.1f}%")
                        m3.metric("Structural Coefficient", f"{p3_result['phase_3_certificate']['C_struct_coefficient'] * 100:.1f}%")

                        status = p3_result["phase_3_certificate"]["status"]
                        if status == "PASS":
                            st.success("✅ SPEC VERIFIED — All quality gates passed.")
                        else:
                            st.error("❌ SPEC VALIDATION FAILED — Coverage or Mutation criteria not met.")

                        tab1, tab2, tab3 = st.tabs(["Semantic Graph", "LTLf Property Suite", "Status"])

                        with tab1:
                            st.json(p1_result["semantic_graph"])
                        with tab2:
                            st.json(p3_result["refined_ltlf_property_suite"])
                        with tab3:
                            st.json(p3_result["phase_3_certificate"])

                        st.divider()
                        st.subheader("📦 Finalized LTLf Property Suite")
                        st.download_button(
                            label="📥 Download Refined Property Suite JSON",
                            data=json.dumps(p3_result["refined_ltlf_property_suite"], indent=2),
                            file_name="refined_properties.json",
                            mime="application/json",
                        )

                    except requests.exceptions.HTTPError as exc:
                        err_msg = str(exc)
                        try:
                            detail = exc.response.json().get("detail", {})
                            if isinstance(detail, dict) and "message" in detail:
                                err_msg = detail["message"]
                        except Exception:
                            pass
                        st.error(f"❌ Pipeline Error: {err_msg}")
                        
                        import re
                        match = re.search(r'line (\d+)', err_msg, re.IGNORECASE)
                        if match:
                            try:
                                line_no = int(match.group(1))
                                lines = bpmn_xml.splitlines()
                                start = max(0, line_no - 4)
                                end = min(len(lines), line_no + 3)
                                snippet = []
                                for i in range(start, end):
                                    prefix = ">> " if i + 1 == line_no else "   "
                                    snippet.append(f"{prefix}{i + 1:3d} | {lines[i]}")
                                st.code("\n".join(snippet), language="xml")
                            except Exception:
                                pass
                    except Exception as e:
                        st.error(f"Module 01 Pipeline Error: {str(e)}")


# ══════════════════════════════════════════════════════════════════════════
# PAGE: EXTRACT ENGINE (Module 02)
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.active_page == "extract_engine":
    st.subheader("⚙️ Extract Engine — Module 02")

    info_tab, verify_tab = st.tabs(["📂 Module Info", "▶️ Run Verification"])

    with info_tab:
        st.markdown('<p class="section-header">Architecture</p>', unsafe_allow_html=True)
        st.markdown(
            "The Extract Engine analyses Python workflow source code through a three-layer "
            "verification pipeline: structural AST extraction (V3), bounded concolic / Z3 "
            "symbolic analysis (V2), and dynamic differential tracing (V1)."
        )

        st.markdown('<p class="section-header">Pipeline Phases</p>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        col1.metric("V3", "AST / CFG Extraction")
        col2.metric("V2", "Z3 Symbolic Engine")
        col3.metric("V1", "Dynamic Tracer")

        st.markdown('<p class="section-header">Source Components</p>', unsafe_allow_html=True)
        files_html = "".join(
            f'<span class="file-chip">{f}</span>'
            for f in [
                "ast_extractor.py",
                "z3_sym_engine.py",
                "dynamic_tracer.py",
                "main.py",
            ]
        )
        st.markdown(files_html, unsafe_allow_html=True)

        st.markdown('<p class="section-header">Key Classes</p>', unsafe_allow_html=True)
        st.markdown(
            "- `CFGExtractor` — Python AST → control-flow graph & WIR  \n"
            "- `BoundedConcolicEngine` — Z3-backed symbolic path exploration  \n"
            "- `MultiModalCertificateComposer` — V1+V2+V3 certificate fusion  \n"
            "- `run_v3_pipeline` / `run_v2_pipeline` / `run_v1_pipeline` — phase entry points"
        )

        st.markdown('<p class="section-header">API Endpoint</p>', unsafe_allow_html=True)
        st.code("POST /verify  ·  FastAPI  ·  uvicorn :8000", language="text")

        st.markdown('<p class="section-header">Docker Service</p>', unsafe_allow_html=True)
        st.code("extract-engine  ·  python:3.11-slim  ·  Port 8000", language="text")

    with verify_tab:
        st.markdown("### Python Workflow Verification (Modules 02 & 03)")
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
                        # Note: Using localhost/direct IP if running locally without docker-compose networking
                        # Defaulting to extract-engine for compatibility with existing docker setup
                        response = requests.post(
                            "http://extract-engine:8000/verify",
                            json={"source_code": workflow_code},
                            timeout=120,
                        )
                        response.raise_for_status()
                        data = response.json()
                    except requests.exceptions.RequestException as exc:
                        st.error(f"Backend request failed: {exc}")
                        st.info("Check if extract-engine is running at http://extract-engine:8000")
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


# ══════════════════════════════════════════════════════════════════════════
# PAGE: EQUIV ENGINE (Module 03)
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.active_page == "equiv_engine":
    st.subheader("🔗 Equiv Engine — Module 03")

    info_tab, demo_tab = st.tabs(["📂 Module Info", "▶️ Run Demo"])

    with info_tab:
        st.markdown('<p class="section-header">Architecture</p>', unsafe_allow_html=True)
        st.markdown(
            "The Equivalence Engine uses a C++/Pybind11 core (`vibecheck_lifter`) built on "
            "the SPOT library for automata-theoretic verification. It lifts WIR type maps into "
            "BDD variable registries and performs tiered semantic action matching "
            "(Lexical → Levenshtein → NLP/Sentence-BERT)."
        )

        st.markdown('<p class="section-header">Pipeline Phases</p>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        col1.metric("P1.1", "WIR Type Lifting")
        col2.metric("P1.2", "Semantic Matching")
        col3.metric("Core", "BDD / SPOT LTLf")

        st.markdown('<p class="section-header">Source Components</p>', unsafe_allow_html=True)
        files_html = "".join(
            f'<span class="file-chip">{f}</span>'
            for f in [
                "lifter.cpp",
                "lifter.hpp",
                "main.py",
                "nlp_utils.py",
                "CMakeLists.txt",
            ]
        )
        st.markdown(files_html, unsafe_allow_html=True)

        st.markdown('<p class="section-header">Key Classes</p>', unsafe_allow_html=True)
        st.markdown(
            "- `AdvancedLifter` (C++) — WIR JSON → BDD variable registry  \n"
            "- `vibecheck_lifter` — Pybind11 bridge module  \n"
            "- `nlp_utils` — Sentence-BERT similarity for action matching  \n"
            "- SPOT 2.11.6 — LTLf automaton backend"
        )

        st.markdown('<p class="section-header">Docker Service</p>', unsafe_allow_html=True)
        st.code("equiv-engine  ·  ubuntu:22.04  ·  g++ / cmake / SPOT  ·  FastAPI  ·  uvicorn :8000", language="text")
        st.markdown(
            "`POST /lift` — WIR type-lifting + semantic action matching (this demo).  \n"
            "`POST /check` — full Phase A–D conformance check against a property suite. "
            "Requires a call-order-lifted WIR (see `module_02_extract`'s `derive_call_order_wir`) — "
            "not yet produced by extract-engine's own HTTP API, so this endpoint has no UI demo here yet."
        )

    with demo_tab:
        st.markdown("### Equivalence Engine Demo")
        st.markdown(
            "Provide a WIR-style JSON payload to test type lifting and "
            "semantic action matching via the compiled C++ core."
        )

        default_wir = json.dumps({
            "control_variables": ["loan_approved", "credit_score"],
            "data_variables": ["requested_amount"],
            "types": {
                "loan_approved": "bool",
                "credit_score": "int",
                "requested_amount": "float",
                "risk_profile": "Any",
            },
        }, indent=2)

        wir_input = st.text_area("WIR JSON Payload", value=default_wir, height=220)

        bpmn_tasks_input = st.text_input(
            "BPMN Task Names (comma-separated)",
            value="Check Funds, Approve Loan, Verify Identity",
        )

        action_input = st.text_input(
            "Action to match",
            value="check_funds",
        )

        if st.button("Run Equiv Engine", type="primary"):
            try:
                wir_data = json.loads(wir_input)
                tasks = [t.strip() for t in bpmn_tasks_input.split(",") if t.strip()]
                response = requests.post(
                    "http://equiv-engine:8000/lift",
                    json={
                        "wir": wir_data,
                        "bpmn_tasks": tasks,
                        "action": action_input.strip() or None,
                    },
                    timeout=10,
                )
                response.raise_for_status()
                result = response.json()

                st.subheader("BDD Variable Registry")
                st.json(result["variable_map"])

                if "matched_action" in result:
                    st.subheader("Semantic Match Result")
                    st.success(f"Action `{action_input}` → Matched: **{result['matched_action']}**")

            except requests.exceptions.RequestException as exc:
                st.error(f"Cannot reach equiv-engine: {exc}")
                st.info("Check if equiv-engine is running at http://equiv-engine:8000")
            except Exception as e:
                st.error(f"Equiv Engine Error: {str(e)}")
