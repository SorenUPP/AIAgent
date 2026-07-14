import streamlit as st
import pandas as pd

import ui_common
from agent import run_agent

st.set_page_config(
    page_title="MedAgent — AI Medical Data Assistant",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

ui_common.bootstrap()
ui_common.require_login()
ollama = ui_common.render_sidebar()

st.markdown("""
<div class="medagent-header">
  <div class="medagent-logo">🩺</div>
  <div>
    <div class="medagent-title">MedAgent</div>
    <div class="medagent-sub">AI Medical Database Assistant · Offline · Ollama</div>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="chat-container">
  <div class="chat-title-bar">
    <span class="chat-dot green"></span>
    MEDAGENT CONSOLE — ASK ANYTHING ABOUT YOUR PATIENT DATA
  </div>
</div>
""", unsafe_allow_html=True)

for msg in st.session_state.messages:
    role = msg["role"]
    content = msg["content"]

    if role == "user":
        st.markdown(f"""
        <div class="msg-user">
          <div class="msg-label">You</div>
          {content}
        </div>
        """, unsafe_allow_html=True)
    else:
        with st.container():
            st.markdown('<div class="msg-label">MedAgent</div>', unsafe_allow_html=True)
            if isinstance(content, dict):
                if content.get("type") == "table":
                    st.subheader(content["title"])
                    st.dataframe(content["data"], use_container_width=True, hide_index=True)
            else:
                st.markdown(content)

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

col_input, col_send = st.columns([6, 1])
with col_input:
    question = st.text_input(
        "Ask a medical question...", key="chat_input",
        placeholder="e.g. Which patients have hypertension and abnormal labs?",
        label_visibility="collapsed",
    )
with col_send:
    send = st.button("Send →", use_container_width=True)

pending = st.session_state.pop("_pending_question", None)
if pending:
    question = pending
    send = True

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

        outcome = "error" if isinstance(answer, str) and answer.startswith(("⚠️", "ERROR")) else "success"
        import auth_db
        auth_db.log_action(st.session_state.auth_user["username"], "query", detail=f"[{outcome}] {question}")

        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()

if not st.session_state.file_loaded:
    st.info("👈 Upload an Excel file (or the default patients.xlsx will load automatically) to get started.")