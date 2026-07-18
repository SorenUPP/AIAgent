import streamlit as st

import ui_common

st.set_page_config(
    page_title="MedAgent",
    layout="wide",
    initial_sidebar_state="expanded",
)

ui_common.bootstrap()

if not st.session_state.get("auth_user"):
    # Only ONE page is ever registered while logged out — Streamlit has
    # nothing else to draw into the nav, so there's nothing to flash.
    # position="hidden" also suppresses the nav widget itself entirely.
    pg = st.navigation(
        [st.Page(ui_common.login_entry, title="Sign In")],
        position="hidden",
    )
else:
    pg = st.navigation([
        st.Page("views/0_Console.py", title="Console", icon="🩺", default=True),
        st.Page("views/1_dashboard.py", title="Dashboard", icon="📊"),
        st.Page("views/2_Patient_Explorer.py", title="Patient Explorer", icon="👥"),
        st.Page("views/3_Audit_Log.py", title="Audit Log", icon="📋"),
    ])

pg.run()