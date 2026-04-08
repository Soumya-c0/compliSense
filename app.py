import streamlit as st
import os
import json
import logging
from datetime import datetime
from fpdf import FPDF
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components

from ocr_engine import extract_text_with_ocr
from vector_db import (create_contract_knowledge_base, retrieve_contract_context,
                       retrieve_regulatory_context, get_master_db_status, get_available_frameworks,
                       audit_compliance_clause, answer_deep_query, generate_full_audit_report,
                       decompose_query)

# --- SETUP LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- PAGE CONFIG ---
st.set_page_config(page_title="Fin-Audit AI | Enterprise", layout="wide")

if 'current_page' not in st.session_state:
    st.session_state.current_page = "landing"

def navigate_to(page):
    st.session_state.current_page = page

# --- CSS & BACKGROUND ---
st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <div class="wave-bg"></div>
    <style>
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif !important; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} .stApp { background: transparent; }
    .wave-bg { position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: -999; background-color: #0b0f19; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1440 320'%3E%3Cpath fill='none' stroke='%2300d2ff' stroke-width='1' stroke-opacity='0.15' d='M0,160L80,149.3C160,139,320,117,480,138.7C640,160,800,224,960,245.3C1120,267,1280,245,1360,234.7L1440,224'/%3E%3C/svg%3E"); background-size: 200vw 100vh; animation: moveWaves 25s linear infinite; }
    @keyframes moveWaves { 0% { background-position: 0 0; } 100% { background-position: -200vw 0; } }
    .glass-card { background: rgba(17, 24, 39, 0.4); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 35px; margin-bottom: 25px; box-shadow: 0 4px 20px 0 rgba(0, 0, 0, 0.2); }
    .cta-button>button { background: linear-gradient(135deg, #0052D4 0%, #4364F7 50%, #6FB1FC 100%); color: white; padding: 14px 28px; font-weight: 600; width: 100%; border-radius: 6px; border: none; }
    .glow-text { text-align: center; font-size: 4rem; font-weight: 700; color: #ffffff; }
    .accent-text { color: #00d2ff; }
    </style>
""", unsafe_allow_html=True)

# --- PDF GENERATOR ---
def create_pdf_report(clauses_data, total, low, med, high):
    class PDF(FPDF):
        def header(self):
            self.set_font('Helvetica', 'B', 16)
            self.set_text_color(0, 82, 212)
            self.cell(0, 10, 'Fin-Audit AI | Enterprise Compliance Report', 0, 1, 'C')
            self.line(10, 22, 200, 22)
            self.ln(10)
    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    def clean_txt(t): return str(t).encode('latin-1', 'replace').decode('latin-1')

    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, f'Executive Summary - {datetime.now().strftime("%Y-%m-%d")}', 0, 1)
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 8, f'Total Clauses Scanned: {total}', 0, 1)
    pdf.cell(0, 8, f'Low Risk: {low}   |   Medium Risk: {med}   |   High Risk: {high}', 0, 1)
    pdf.ln(10)

    for clause in clauses_data:
        if not isinstance(clause, dict): continue
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_text_color(20, 20, 20)
        pdf.multi_cell(0, 8, clean_txt(clause.get('clause_name', 'Unknown Clause')))

        status = clean_txt(clause.get('status', 'UNKNOWN'))
        risk   = clean_txt(clause.get('risk_level', 'UNKNOWN')).upper()

        score_val = clause.get('confidence_score')
        score = f"{score_val * 100:.0f}%" if isinstance(score_val, (int, float)) else "N/A"

        pdf.set_font('Helvetica', 'B', 10)
        if risk == 'HIGH':   pdf.set_text_color(220, 38, 38)
        elif risk == 'MEDIUM': pdf.set_text_color(217, 119, 6)
        else:                  pdf.set_text_color(34, 197, 94)

        pdf.cell(0, 6, f'Status: {status} | Risk: {risk} | Judge Confidence: {score}', 0, 1)
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(80, 80, 80)
        pdf.multi_cell(0, 6, clean_txt(clause.get('reason', 'No reason provided.')))
        pdf.ln(5)

    return pdf.output(dest='S').encode('latin-1')

# --- GRAPHRAG VISUALIZER ---
def render_interactive_graph():
    graph_path = "chroma_db/contract_graph.graphml"
    if not os.path.exists(graph_path):
        return "<p style='color:#94a3b8;'>Graph map not yet generated. Initialize a contract first.</p>"
    
    try:
        G = nx.read_graphml(graph_path)
        net = Network(height="400px", width="100%", bgcolor="rgba(0,0,0,0)", font_color="#e2e8f0", directed=True)
        net.barnes_hut(gravity=-8000, central_gravity=0.3, spring_length=150)
        
        for node in G.nodes():
            net.add_node(node, label=node, color="#38bdf8", shape="dot", size=15)
        for u, v, data in G.edges(data=True):
            relation_label = data.get('relation', '')
            net.add_edge(u, v, title=relation_label, label=relation_label, color="#475569", arrows="to")
            
        net.save_graph("interactive_graph.html")
        with open("interactive_graph.html", "r", encoding="utf-8") as f:
            html_string = f.read()
        return html_string
    except Exception as e:
        return f"<p style='color:red;'>Error rendering graph: {str(e)}</p>"


# ==========================================
# PAGE 1: LANDING PAGE
# ==========================================
if st.session_state.current_page == "landing":
    st.markdown("""<style>[data-testid="collapsedControl"] {display: none;} [data-testid="stSidebar"] {display: none;}</style>""", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([2, 6, 2])
    with col2:
        st.markdown("<h1 class='glow-text'>Fin-Audit <span class='accent-text'>AI</span></h1>", unsafe_allow_html=True)
        st.markdown('<div class="cta-button">', unsafe_allow_html=True)
        if st.button("Launch Audit Terminal", use_container_width=True):
            navigate_to("app")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


# ==========================================
# PAGE 2: MAIN APPLICATION
# ==========================================
elif st.session_state.current_page == "app":
    with st.sidebar:
        st.markdown('<div class="cta-button">', unsafe_allow_html=True)
        if st.button("Return to Home", use_container_width=True):
            navigate_to("landing")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        from dotenv import load_dotenv
        load_dotenv()
        groq_key_present = bool(os.getenv("GROQ_API_KEY"))
        if groq_key_present:
            st.success("✅ Groq API Key loaded from .env")
        else:
            st.error("❌ GROQ_API_KEY missing — add it to your .env file")

        st.markdown("---")
        st.markdown("### 🏛️ Master Regulatory DB")
        st.markdown(f"**Status:** {get_master_db_status()}")
        available_frameworks = get_available_frameworks()
        st.session_state.selected_framework = st.selectbox(
            "🎯 Target Jurisdiction:",
            ["ALL"] + available_frameworks if available_frameworks else ["ALL"]
        )

        st.markdown("---")
        st.markdown("### 📄 Contract Ingestion")
        uploaded_file = st.file_uploader("Upload Target Contract", type=["pdf"])

        # STATE INITIALIZATION
        if 'extracted_text' not in st.session_state:
            st.session_state.extracted_text = ""
            st.session_state.db_ready = False
            
        if 'audit_data' not in st.session_state:
            st.session_state.audit_data = None
            st.session_state.audit_metrics = None
            st.session_state.audit_pdf = None
            
        if 'deep_query_data' not in st.session_state:
            st.session_state.deep_query_data = None
            st.session_state.deep_query_evidence = None

        if st.button("Initialize Contract", use_container_width=True):
            if not groq_key_present:
                st.error("Add GROQ_API_KEY to .env before initializing.")
            elif uploaded_file is not None:
                with st.spinner("Processing Document & Building GraphRAG Map..."):
                    temp_pdf = "temp_contract.pdf"
                    with open(temp_pdf, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    text = extract_text_with_ocr(temp_pdf)
                    if os.path.exists(temp_pdf):
                        os.remove(temp_pdf)

                    if "Error" in text:
                        st.error(text)
                    else:
                        st.session_state.extracted_text = text
                        create_status = create_contract_knowledge_base(text)
                        if "Error" in create_status:
                            st.error(create_status)
                        else:
                            st.session_state.db_ready = True
                            # Clear old caches when a new doc is uploaded
                            st.session_state.audit_data = None
                            st.session_state.deep_query_data = None
                            st.success("Contract Initialized.")
            else:
                st.warning("Upload a document first.")

    st.markdown("<h2>Fin-Audit Terminal</h2>", unsafe_allow_html=True)

    if st.session_state.get('db_ready', False):
        tab1, tab2, tab3 = st.tabs(["Auto-Audit Dashboard", "Deep Query (Cross-Reference)", "Raw Data"])

        # ── TAB 1: FULL AUDIT REPORT ──────────────────────────────────────
        with tab1:
            if st.button("Generate Two-Agent Audit Report"):
                with st.spinner("Executing Two-Agent Pipeline (Extracting → Searching → Judging)..."):
                    json_array_response = generate_full_audit_report(
                        st.session_state.extracted_text,
                        target_framework=st.session_state.selected_framework
                    )
                    try:
                        clauses_data = json.loads(json_array_response)
                        first = clauses_data[0] if clauses_data else {}
                        if "error" in first:
                            st.error(first["error"])
                        else:
                            valid_clauses    = [c for c in clauses_data if isinstance(c, dict) and "clause_name" in c]
                            total_clauses    = len(valid_clauses)
                            high_risk_count  = sum(1 for c in valid_clauses if c.get('risk_level', '').upper() == 'HIGH')
                            medium_risk_count= sum(1 for c in valid_clauses if c.get('risk_level', '').upper() == 'MEDIUM')
                            low_risk_count   = sum(1 for c in valid_clauses if c.get('risk_level', '').upper() == 'LOW')

                            # SAVE TO SESSION STATE
                            st.session_state.audit_data = valid_clauses
                            st.session_state.audit_metrics = (total_clauses, low_risk_count, medium_risk_count, high_risk_count)
                            st.session_state.audit_pdf = create_pdf_report(valid_clauses, total_clauses, low_risk_count, medium_risk_count, high_risk_count)
                            
                    except json.JSONDecodeError:
                        st.error("Failed to parse audit response. Check logs for details.")

            # RENDER FROM SESSION STATE (Outside the button)
            if st.session_state.audit_data:
                valid_clauses = st.session_state.audit_data
                total_clauses, low_risk_count, medium_risk_count, high_risk_count = st.session_state.audit_metrics
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Clauses Evaluated", total_clauses)
                col2.metric("Low Risk",    low_risk_count)
                col3.metric("Medium Risk", medium_risk_count)
                col4.metric("High Risk",   high_risk_count)
                st.markdown("---")

                for clause in valid_clauses:
                    status = clause.get("status", "UNKNOWN")
                    icon_html = (
                        '<i class="fa-solid fa-circle-check" style="color: #22c55e;"></i>'
                        if status == "COMPLIANT" else
                        '<i class="fa-solid fa-circle-xmark" style="color: #ef4444;"></i>'
                        if status == "NON_COMPLIANT" else
                        '<i class="fa-solid fa-triangle-exclamation" style="color: #eab308;"></i>'
                    )
                    risk_color = (
                        '#ef4444' if clause.get('risk_level') == 'HIGH' else
                        '#eab308' if clause.get('risk_level') == 'MEDIUM' else
                        '#22c55e'
                    )
                    score_val     = clause.get('confidence_score')
                    display_score = f"{score_val * 100:.0f}%" if isinstance(score_val, (int, float)) else "N/A"

                    st.markdown(f"""
                    <div class="glass-card" style="text-align: left; padding: 25px; margin-bottom: 20px;">
                        <h4 style="color: #f8fafc; font-weight: 600; margin-top: 0;">{icon_html} {clause.get('clause_name', 'Unknown Clause')}</h4>
                        <p style="margin-bottom: 8px; font-size: 0.95rem; color: #cbd5e1;">
                            <strong>Status:</strong> {status} &nbsp;|&nbsp;
                            <strong>Risk Level:</strong> <span style="color: {risk_color}; font-weight: 600;">{clause.get('risk_level', 'N/A')}</span> &nbsp;|&nbsp;
                            <strong>Judge Confidence:</strong> <span style="color: #38bdf8;">{display_score}</span>
                        </p>
                        <p style="margin-bottom: 0; font-size: 0.95rem; color: #94a3b8; line-height: 1.5;">{clause.get('reason', 'No reason provided.')}</p>
                    </div>
                    """, unsafe_allow_html=True)

                st.download_button(
                    "📥 Download Official PDF Report",
                    data=st.session_state.audit_pdf,
                    file_name=f"Fin-Audit_Report_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )


        # ── TAB 2: DEEP QUERY ─────────────────────────────────────────────
        with tab2:
            st.markdown("Ask a specific compliance question about the uploaded contract.")
            audit_question = st.text_input(
                "Enter a specific compliance question:",
                placeholder='e.g. "Is clause 4 compliant?" or "Which clauses violate GDPR?"'
            )
            if st.button("Run Deep Query"):
                if audit_question:
                    with st.spinner(f"Decomposing query → Retrieving evidence → Analysing..."):

                        decomposed = decompose_query(audit_question)
                        clause_q   = decomposed.get("clause_search_query",   audit_question)
                        reg_q      = decomposed.get("regulation_search_query", audit_question)
                        intent     = decomposed.get("intent", "OTHER")

                        raw_contract   = retrieve_contract_context(clause_q)
                        raw_regulation = retrieve_regulatory_context(
                            reg_q, st.session_state.selected_framework
                        )

                        if intent == "SPECIFIC_CLAUSE_CHECK":
                            json_response = audit_compliance_clause(
                                audit_question, raw_contract, raw_regulation
                            )
                        else:
                            json_response = answer_deep_query(
                                audit_question, raw_contract, raw_regulation
                            )

                        try:
                            parsed_json = json.loads(json_response)
                            if "error" in parsed_json:
                                st.error(parsed_json["error"])
                            else:
                                # SAVE TO SESSION STATE
                                st.session_state.deep_query_data = parsed_json
                                st.session_state.deep_query_evidence = (clause_q, reg_q, raw_contract, raw_regulation, intent)
                                
                        except json.JSONDecodeError:
                            st.error("Failed to parse deep query response. Check logs.")
                else:
                    st.warning("Please enter a compliance question first.")

            # RENDER FROM SESSION STATE (Outside the button)
            if st.session_state.deep_query_data:
                parsed_json = st.session_state.deep_query_data
                clause_q, reg_q, raw_contract, raw_regulation, intent = st.session_state.deep_query_evidence
                
                status = parsed_json.get("status") or parsed_json.get("detected_query_type", "")
                risk   = parsed_json.get("risk_level") or parsed_json.get("overall_risk_level", "N/A")
                score_val = parsed_json.get("confidence_score")
                display_score = f"{score_val * 100:.0f}%" if isinstance(score_val, (int, float)) else "N/A"

                answer_text = (
                    parsed_json.get("comprehensive_answer") or
                    parsed_json.get("reason") or
                    "No answer generated."
                )
                clauses_ref = parsed_json.get("clauses_referenced", [])

                risk_color = (
                    '#ef4444' if str(risk).upper() == 'HIGH' else
                    '#eab308' if str(risk).upper() == 'MEDIUM' else
                    '#22c55e'
                )

                st.markdown(f"""
                <div class="glass-card" style="padding: 25px;">
                    <p style="color: #94a3b8; font-size: 0.85rem; margin-bottom: 4px;">
                        Query Type: <strong style="color:#38bdf8;">{intent}</strong>
                        &nbsp;|&nbsp; Risk: <strong style="color:{risk_color};">{risk}</strong>
                        &nbsp;|&nbsp; Confidence: <strong style="color:#38bdf8;">{display_score}</strong>
                    </p>
                    <hr style="border-color: rgba(255,255,255,0.08); margin: 12px 0;">
                    <p style="color: #e2e8f0; line-height: 1.7; white-space: pre-wrap;">{answer_text}</p>
                </div>
                """, unsafe_allow_html=True)

                if clauses_ref:
                    st.markdown("**Clauses / Articles Referenced:**")
                    for ref in clauses_ref:
                        st.markdown(f"- {ref}")

                with st.expander("🔍 View GraphRAG & Cross-Reference Evidence", expanded=True):
                    st.markdown(f"**Intent Detected:** `{intent}` | **Clause Target:** `{clause_q}`")
                    
                    ev_col1, ev_col2 = st.columns([1, 1])
                    with ev_col1:
                        st.markdown("#### 🧠 Entity Relationship Map")
                        st.markdown("<span style='font-size: 0.8rem; color: #94a3b8;'>Interactive GraphRAG map extracted from the document. Drag nodes to explore.</span>", unsafe_allow_html=True)
                        graph_html = render_interactive_graph()
                        components.html(graph_html, height=420)
                        
                    with ev_col2:
                        st.markdown("#### 📄 Vector Retrieval Evidence")
                        st.info(f"**Master Regulation Applied:**\n{raw_regulation}")
                        st.success(f"**Contract Text Pulled:**\n{raw_contract}")


        # ── TAB 3: RAW DOCUMENT ───────────────────────────────────────────
        with tab3:
            st.text_area("Read-Only Document Memory", st.session_state.extracted_text, height=400)

    else:
        st.info("Please upload a Target Contract and Initialize it in the sidebar to begin.")