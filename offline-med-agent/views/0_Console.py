import html
import streamlit as st
import pandas as pd

import ui_common
import auth_db
from agent import run_agent

st.set_page_config(
    page_title="MedAgent",
    layout="wide",
    initial_sidebar_state="expanded",
)

ui_common.bootstrap()
ui_common.require_login()
ollama = ui_common.render_sidebar()

st.markdown("""
<div class="page-header">
  <div class="page-eyebrow">Clinical Data Assistant</div>
  <div class="page-title">Query Console</div>
  <div class="page-sub">Ask a question about the loaded patient dataset in plain language.</div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="chat-container">
  <div class="chat-title-bar">CONVERSATION</div>
</div>
""", unsafe_allow_html=True)

# --- message renderer (reused for both archived + current) ----------
def render_block(content, key_prefix="block"):
    """Renders one result block (table/metric/chart/string), no chat_message wrapper."""
    if isinstance(content, dict):
        ctype = content.get("type")
        if ctype == "table":
            st.subheader(content["title"])
            st.dataframe(content["data"], use_container_width=True, hide_index=True)
            csv = content["data"].to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇ Export as CSV", data=csv, file_name="medagent_query_result.csv",
                mime="text/csv", key=f"{key_prefix}_export",
            )
        elif ctype == "metric":
            st.metric(content["label"], content["value"])
        elif ctype == "chart":
            st.subheader(content.get("title", "Trend"))
            chart_df = content["data"].set_index(content["x"])
            st.line_chart(chart_df[[content["y"]]])
            csv = content["data"].to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇ Export as CSV", data=csv, file_name="medagent_trend_result.csv",
                mime="text/csv", key=f"{key_prefix}_export",
            )
        else:
            st.write(content)
    else:
        st.markdown(html.escape(str(content)))


def render_message(msg, msg_index):
    role = msg["role"]
    content = msg["content"]
    avatar = "🧑‍⚕️" if role == "user" else "🩺"
    with st.chat_message(role, avatar=avatar):
        if isinstance(content, dict) and content.get("type") == "multi":
            st.subheader(content["title"])
            for i, block in enumerate(content["results"], start=1):
                st.markdown(f"**Step {i}:**")
                render_block(block, key_prefix=f"msg{msg_index}_step{i}")
                st.divider()
        else:
            render_block(content, key_prefix=f"msg{msg_index}")

# --- split into archived vs current exchange -------------------------
messages = st.session_state.messages
if len(messages) > 2:
    archived, current = messages[:-2], messages[-2:]
else:
    archived, current = [], messages

# --- floating "history" tab, pinned to right edge --------------------
st.markdown("""
<style>
div.history-tab-marker + div[data-testid="stPopover"] {
    position: fixed;
    top: 45%;
    right: 0;
    z-index: 999;
}
div.history-tab-marker + div[data-testid="stPopover"] > button {
    writing-mode: vertical-rl;
    transform: rotate(180deg);
    border-radius: 8px 0 0 8px;
    padding: 16px 10px;
    background: #1f2937;
    color: #f9fafb;
    border: none;
    font-size: 0.85rem;
    letter-spacing: 0.03em;
}
</style>
<div class="history-tab-marker"></div>
""", unsafe_allow_html=True)

if archived:
    with st.popover(f"◂ History ({len(archived)})"):
        st.caption("Earlier in this conversation")
        for i, msg in enumerate(archived):
            render_message(msg, msg_index=f"archived{i}")

# --- current exchange, always visible --------------------------------
for i, msg in enumerate(current):
    render_message(msg, msg_index=f"current{i}")

# --- suggestion chips (only before first message) --------------------
if not st.session_state.messages and st.session_state.file_loaded:
    suggestions = [
        "How many patients have diabetes?",
        "Show me PT-0001's full profile",
        "Which patients have abnormal cholesterol?",
        "What is the average BMI?",
        "List all patients over 70",
        "Who has a penicillin allergy?",
    ]
    st.markdown("**Try asking:**")
    cols = st.columns(3)
    for i, s in enumerate(suggestions):
        with cols[i % 3]:
            if st.button(s, key=f"chip_{i}"):
                st.session_state._pending_question = s
                st.rerun()

# --- input -------------------------------------------------------
pending = st.session_state.pop("_pending_question", None)
question = pending or st.chat_input(
    "Ask a medical question... e.g. Which patients have hypertension and abnormal labs?"
)

if question and question.strip():
    if not st.session_state.file_loaded or not st.session_state.df_dict:
        st.warning("Please load an Excel file first (sidebar).")
    elif not ollama["online"]:
        st.error("Ollama is offline. Start it with `ollama serve` and pull a model with `ollama pull llama3`.")
    else:
        st.session_state.messages.append({"role": "user", "content": question})

        with st.spinner("Analysing..."):
            try:
                answer = run_agent(st.session_state.df_dict, question)
            except Exception as e:
                answer = f"! **Unexpected error while analysing:** `{e}`"

        if answer == "OLLAMA_OFFLINE":
            answer = "**Ollama went offline.** Please restart with `ollama serve`."
        elif answer == "TIMEOUT":
            answer = "**Timeout.** The model is taking too long — try a shorter question."

        is_error = isinstance(answer, str) and (
            answer.startswith(("!", "ERROR", "⚠️", "**Ollama", "**Timeout"))
        )
        outcome = "error" if is_error else "success"
        auth_db.log_action(st.session_state.auth_user["username"], "query", detail=f"[{outcome}] {question}")

        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()

if not st.session_state.file_loaded:
    st.info("Upload an Excel file (or the default patients.xlsx will load automatically) to get started.")