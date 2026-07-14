import streamlit as st
import pandas as pd

import ui_common
import auth_db

st.set_page_config(page_title="MedAgent — Audit Log", page_icon="📋", layout="wide")
ui_common.bootstrap()
ui_common.require_login()
ui_common.render_sidebar()

st.markdown("""
<div class="medagent-header">
  <div class="medagent-logo">📋</div>
  <div>
    <div class="medagent-title">Audit Log</div>
    <div class="medagent-sub">Login, query, and account activity across MedAgent</div>
  </div>
</div>
""", unsafe_allow_html=True)

if st.session_state.auth_user["role"] != "admin":
    st.error("🔒 This page is restricted to admins.")
    st.stop()

# --------------------------------------------------
# Controls
# --------------------------------------------------
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    all_users = ["All users"] + [u["username"] for u in auth_db.list_users()]
    user_filter = st.selectbox("Filter by user", all_users)

with col2:
    action_options = [
        "All actions", "login", "login_failed", "logout", "query",
        "account_created", "user_created", "password_reset",
        "password_reset_failed", "admin_password_reset",
        "recovery_code_regenerated",
    ]
    action_filter = st.selectbox("Filter by action", action_options)

with col3:
    row_limit = st.selectbox("Rows", [100, 200, 500, 1000], index=1)

# --------------------------------------------------
# Fetch + filter
# --------------------------------------------------
entries = auth_db.get_audit_log(limit=row_limit)
df = pd.DataFrame(entries)

if not df.empty:
    if user_filter != "All users":
        df = df[df["username"] == user_filter]
    if action_filter != "All actions":
        df = df[df["action"] == action_filter]

# --------------------------------------------------
# Summary cards
# --------------------------------------------------
total_events = len(df)
failed_logins = len(df[df["action"] == "login_failed"]) if not df.empty else 0
queries_run = len(df[df["action"] == "query"]) if not df.empty else 0
unique_users = df["username"].nunique() if not df.empty else 0

st.markdown(f"""
<div class="stat-grid">
  <div class="stat-card"><div class="stat-value">{total_events}</div><div class="stat-label">Events Shown</div></div>
  <div class="stat-card amber"><div class="stat-value">{failed_logins}</div><div class="stat-label">Failed Logins</div></div>
  <div class="stat-card green"><div class="stat-value">{queries_run}</div><div class="stat-label">Queries Run</div></div>
  <div class="stat-card"><div class="stat-value">{unique_users}</div><div class="stat-label">Active Users</div></div>
</div>
""", unsafe_allow_html=True)

# --------------------------------------------------
# Table
# --------------------------------------------------
st.subheader("Event Log")

if df.empty:
    st.caption("No matching audit events.")
else:
    display_df = df.rename(columns={
        "timestamp": "Timestamp (UTC)",
        "username": "User",
        "action": "Action",
        "detail": "Detail",
    })[["Timestamp (UTC)", "User", "Action", "Detail"]]

    st.dataframe(display_df, use_container_width=True, hide_index=True, height=500)

    csv = display_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇ Export filtered log as CSV",
        data=csv,
        file_name="medagent_audit_log.csv",
        mime="text/csv",
    )