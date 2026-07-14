import streamlit as st
import pandas as pd
import json
import time

from data_loader import load_data, get_quick_stats
from agent import run_agent, check_ollama_status
from tools import get_flag_counts, get_diagnosis_counts, get_age_distribution

# ─────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MedAgent — AI Medical Data Assistant",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# CSS  — dark clinical theme, IBM Plex Mono + DM Sans
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

/* ── Root background ── */
.stApp {
    background: #0a0f1a;
    color: #c9d8e8;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #0d1421 !important;
    border-right: 1px solid #1e2d45;
}
[data-testid="stSidebar"] * { color: #a8c0d6 !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color: #e2eef7 !important; }

/* ── Main header ── */
.medagent-header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 28px 0 20px 0;
    border-bottom: 1px solid #1e2d45;
    margin-bottom: 28px;
}
.medagent-logo {
    font-size: 42px;
    line-height: 1;
}
.medagent-title {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 28px;
    font-weight: 600;
    color: #4fc3f7;
    letter-spacing: -0.5px;
}
.medagent-sub {
    font-size: 13px;
    color: #5a7a9a;
    letter-spacing: 0.4px;
    text-transform: uppercase;
    margin-top: 2px;
}

/* ── Stat cards ── */
.stat-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-bottom: 28px;
}
.stat-card {
    background: #0d1421;
    border: 1px solid #1e2d45;
    border-radius: 10px;
    padding: 18px 20px;
    position: relative;
    overflow: hidden;
}
.stat-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, #4fc3f7, #0288d1);
}
.stat-card.red::before { background: linear-gradient(90deg, #ef5350, #b71c1c); }
.stat-card.amber::before { background: linear-gradient(90deg, #ffa726, #e65100); }
.stat-card.green::before { background: linear-gradient(90deg, #66bb6a, #1b5e20); }
.stat-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 32px;
    font-weight: 600;
    color: #e2eef7;
    line-height: 1.1;
}
.stat-label {
    font-size: 11px;
    color: #5a7a9a;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-top: 4px;
}

/* ── Chat area ── */
.chat-container {
    background: #0d1421;
    border: 1px solid #1e2d45;
    border-radius: 12px;
    padding: 0;
    overflow: hidden;
    margin-bottom: 16px;
}
.chat-title-bar {
    background: #111c2e;
    padding: 12px 20px;
    border-bottom: 1px solid #1e2d45;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    color: #4fc3f7;
    letter-spacing: 0.5px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.chat-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.chat-dot.green { background: #4caf50; }
.chat-dot.red   { background: #ef5350; }
.chat-dot.amber { background: #ffa726; }

.chat-messages {
    padding: 20px;
    max-height: 480px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

/* ── Message bubbles ── */
.msg-user {
    align-self: flex-end;
    background: #1a3a5c;
    border: 1px solid #1e5082;
    border-radius: 16px 16px 4px 16px;
    padding: 12px 16px;
    max-width: 72%;
    font-size: 14px;
    color: #cde8f8;
    line-height: 1.6;
}
.msg-agent {
    align-self: flex-start;
    background: #111c2e;
    border: 1px solid #1e2d45;
    border-radius: 4px 16px 16px 16px;
    padding: 14px 18px;
    max-width: 82%;
    font-size: 14px;
    color: #c9d8e8;
    line-height: 1.7;
}
.msg-agent code {
    background: #0a0f1a;
    border: 1px solid #1e2d45;
    border-radius: 4px;
    padding: 1px 6px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    color: #4fc3f7;
}
.msg-agent pre {
    background: #0a0f1a;
    border: 1px solid #1e2d45;
    border-radius: 8px;
    padding: 14px;
    overflow-x: auto;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    color: #a8c0d6;
    margin: 8px 0;
}
.msg-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #3a5a7a;
    margin-bottom: 4px;
}

/* ── Status pill ── */
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 20px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.3px;
}
.status-online { background: #1a3a1a; border: 1px solid #2a6a2a; color: #66bb6a; }
.status-offline { background: #3a1a1a; border: 1px solid #6a2a2a; color: #ef5350; }

/* ── Suggestion chips ── */
.chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 12px 0 4px 0;
}
.chip {
    background: #111c2e;
    border: 1px solid #1e3a5a;
    border-radius: 20px;
    padding: 6px 14px;
    font-size: 12px;
    color: #7ab3d4;
    cursor: pointer;
    transition: all 0.15s;
}
.chip:hover {
    background: #1a3a5c;
    border-color: #4fc3f7;
    color: #cde8f8;
}

/* ── Input box overrides ── */
.stTextInput > div > div > input {
    background: #111c2e !important;
    border: 1px solid #1e3a5a !important;
    border-radius: 10px !important;
    color: #c9d8e8 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 14px !important;
    padding: 12px 16px !important;
}
.stTextInput > div > div > input:focus {
    border-color: #4fc3f7 !important;
    box-shadow: 0 0 0 2px rgba(79,195,247,0.15) !important;
}
.stButton > button {
    background: linear-gradient(135deg, #0288d1, #4fc3f7) !important;
    border: none !important;
    border-radius: 10px !important;
    color: #000d1a !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    padding: 10px 24px !important;
    transition: opacity 0.15s !important;
}
.stButton > button:hover { opacity: 0.88 !important; }

/* ── Data table ── */
.stDataFrame { border-radius: 10px; overflow: hidden; }
[data-testid="stDataFrameResizable"] { background: #0d1421; }

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: #0d1421 !important;
    border: 1px dashed #1e3a5a !important;
    border-radius: 12px !important;
}

/* ── Expander ── */
.streamlit-expanderHeader {
    background: #0d1421 !important;
    border: 1px solid #1e2d45 !important;
    border-radius: 8px !important;
    color: #a8c0d6 !important;
}

/* ── Progress bar ── */
.stProgress > div > div { background: #4fc3f7 !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0a0f1a; }
::-webkit-scrollbar-thumb { background: #1e3a5a; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #4fc3f7; }

/* Selectbox */
.stSelectbox > div > div {
    background: #111c2e !important;
    border-color: #1e3a5a !important;
    color: #c9d8e8 !important;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# Session state init
# ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "df_dict" not in st.session_state:
    st.session_state.df_dict = {}
if "file_loaded" not in st.session_state:
    st.session_state.file_loaded = False

# ─────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🩺 MedAgent")
    st.markdown("---")

    # Ollama status
    ollama = check_ollama_status()
    if ollama["online"]:
        st.markdown(
            '<span class="status-pill status-online">● Ollama Online</span>',
            unsafe_allow_html=True
        )
        if ollama["models"]:
            model_list = ", ".join(ollama["models"][:3])
            st.caption(f"Models: {model_list}")
    else:
        st.markdown(
            '<span class="status-pill status-offline">● Ollama Offline</span>',
            unsafe_allow_html=True
        )
        st.caption("Run `ollama serve` to start")

    st.markdown("---")

    # File uploader
    st.markdown("### 📂 Load Data")
    uploaded = st.file_uploader(
        "Upload Excel (.xlsx)",
        type=["xlsx"],
        label_visibility="collapsed"
    )

    if uploaded:
        with st.spinner("Parsing sheets..."):
            df_dict = load_data(uploaded)
            st.session_state.df_dict = df_dict
            st.session_state.file_loaded = True
            st.session_state.messages = []  # reset chat on new file

        st.success(f"✓ Loaded {len(df_dict)} sheets")

    # Load default patients.xlsx if exists
    if not st.session_state.file_loaded:
        import os
        default_path = os.path.join(os.path.dirname(__file__), "data", "patients.xlsx")
        if os.path.exists(default_path):
            df_dict = load_data(default_path)
            st.session_state.df_dict = df_dict
            st.session_state.file_loaded = True
            st.caption("↑ Using default patients.xlsx")

    st.markdown("---")

    # Sheet browser
    if st.session_state.file_loaded and st.session_state.df_dict:
        stats = get_quick_stats(st.session_state.df_dict)
        st.markdown("### 📋 Sheets")
        for sheet, info in stats.items():
            with st.expander(f"{sheet} ({info['rows']} rows)"):
                st.caption(f"**Columns:** {', '.join(info['columns'])}")

    st.markdown("---")

    # Clear chat
    if st.button("🗑 Clear Chat"):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.caption("MedAgent v2.0 · Powered by Ollama + llama3\nAll patient data is synthetic.")

# ─────────────────────────────────────────────────────────────
# Main area header
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="medagent-header">
  <div class="medagent-logo">🩺</div>
  <div>
    <div class="medagent-title">MedAgent</div>
    <div class="medagent-sub">AI Medical Database Assistant · Offline · Ollama</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# KPI cards (only when data loaded)
# ─────────────────────────────────────────────────────────────
if st.session_state.file_loaded and st.session_state.df_dict:
    df_dict = st.session_state.df_dict
    demo = df_dict.get("Patient Demographics", pd.DataFrame())
    med  = df_dict.get("Medical Records",      pd.DataFrame())
    lab  = df_dict.get("Lab Results",          pd.DataFrame())

    total_pts = len(demo) if not demo.empty else 0
    avg_age = 0
    if not demo.empty and "Age" in demo.columns:
        try:
            avg_age = round(pd.to_numeric(demo["Age"], errors="coerce").mean(), 1)
        except Exception:
            avg_age = "—"

    flag_counts = get_flag_counts(df_dict)
    abnormal = flag_counts.get("Abnormal High", 0) + flag_counts.get("Abnormal Low", 0)
    borderline = flag_counts.get("Borderline", 0)

    st.markdown(f"""
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-value">{total_pts}</div>
        <div class="stat-label">Total Patients</div>
      </div>
      <div class="stat-card green">
        <div class="stat-value">{avg_age}</div>
        <div class="stat-label">Average Age</div>
      </div>
      <div class="stat-card red">
        <div class="stat-value">{abnormal}</div>
        <div class="stat-label">Abnormal Lab Flags</div>
      </div>
      <div class="stat-card amber">
        <div class="stat-value">{borderline}</div>
        <div class="stat-label">Borderline Results</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Quick data preview tabs
    tab1, tab2, tab3 = st.tabs(["👥 Demographics", "🩺 Medical Records", "🔬 Lab Results"])
    with tab1:
        if not demo.empty:
            st.dataframe(demo.head(40), use_container_width=True, hide_index=True)
    with tab2:
        if not med.empty:
            st.dataframe(med.head(40), use_container_width=True, hide_index=True)
    with tab3:
        if not lab.empty:
            st.dataframe(lab.head(40), use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# Chat interface
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="chat-container">
  <div class="chat-title-bar">
    <span class="chat-dot green"></span>
    MEDAGENT CONSOLE — ASK ANYTHING ABOUT YOUR PATIENT DATA
  </div>
</div>
""", unsafe_allow_html=True)

# Render messages
for msg in st.session_state.messages:

    role = msg["role"]
    content = msg["content"]

    # USER MESSAGE
    if role == "user":

        st.markdown(f"""
        <div class="msg-user">
          <div class="msg-label">You</div>
          {content}
        </div>
        """, unsafe_allow_html=True)

    # ASSISTANT MESSAGE
    else:

        with st.container():

            st.markdown(
                '<div class="msg-label">MedAgent</div>',
                unsafe_allow_html=True
            )

            # TABLE RESPONSE
            if isinstance(content, dict):

                if content.get("type") == "table":

                    st.subheader(content["title"])

                    st.dataframe(
                        content["data"],
                        use_container_width=True,
                        hide_index=True
                    )

            # TEXT RESPONSE
            else:

                st.markdown(content)

# Suggestion chips (shown when no messages yet)
if not st.session_state.messages and st.session_state.file_loaded:
    suggestions = [
        "How many patients have diabetes?",
        "Show me PT-0001's full profile",
        "Which patients have abnormal cholesterol?",
        "What is the average BMI?",
        "List all patients over 70",
        "Who has a penicillin allergy?",
    ]
    st.markdown("**💡 Try asking:**")
    cols = st.columns(3)
    for i, s in enumerate(suggestions):
        with cols[i % 3]:
            if st.button(s, key=f"chip_{i}"):
                st.session_state._pending_question = s
                st.rerun()

# Input row
col_input, col_send = st.columns([6, 1])
with col_input:
    question = st.text_input(
        "Ask a medical question...",
        key="chat_input",
        placeholder="e.g. Which patients have hypertension and abnormal labs?",
        label_visibility="collapsed"
    )
with col_send:
    send = st.button("Send →", use_container_width=True)

# Handle chip pre-fill
pending = st.session_state.pop("_pending_question", None)
if pending:
    question = pending
    send = True

# Process question
if send and question and question.strip():
    if not st.session_state.file_loaded or not st.session_state.df_dict:
        st.warning("⚠️ Please load an Excel file first (sidebar).")
    elif not ollama["online"]:
        st.error("Ollama is offline. Start it with `ollama serve` and pull a model with `ollama pull llama3`.")
    else:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.spinner("🔬 Analysing..."):
            answer = run_agent(st.session_state.df_dict, question)

        if answer == "OLLAMA_OFFLINE":
            answer = "⚠️ **Ollama went offline.** Please restart with `ollama serve`."
        elif answer == "TIMEOUT":
            answer = "⚠️ **Timeout.** The model is taking too long — try a shorter question."

        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()

# No data notice
if not st.session_state.file_loaded:
    st.info("👈 Upload an Excel file (or the default patients.xlsx will load automatically) to get started.")
