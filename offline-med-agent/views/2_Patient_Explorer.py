import streamlit as st
import pandas as pd

import ui_common
from tools import compute_patient_risk_scores

st.set_page_config(page_title="MedAgent — Patient Explorer", page_icon="👥", layout="wide")
ui_common.bootstrap()
ui_common.require_login()
ui_common.render_sidebar()

st.markdown("""
<div class="page-header">
  <div class="page-eyebrow">Records</div>
  <div class="page-title">Patient Explorer</div>
  <div class="page-sub">Search and browse individual patient records</div>
</div>
""", unsafe_allow_html=True)

if not st.session_state.file_loaded or not st.session_state.df_dict:
    st.info("Load an Excel file from the sidebar to browse patients.")
    st.stop()

df_dict = st.session_state.df_dict
demo = df_dict.get("Patient Demographics", pd.DataFrame())

if demo.empty:
    st.warning("No 'Patient Demographics' sheet found in the loaded data.")
    st.stop()

search = st.text_input("Search by name or Patient ID", placeholder="e.g. Smith or PT-0001")

filtered = demo
if search.strip():
    term = search.strip().lower()
    name_cols = [c for c in ["First Name", "Last Name", "Patient ID"] if c in demo.columns]
    mask = pd.Series(False, index=demo.index)
    for col in name_cols:
        mask |= demo[col].astype(str).str.lower().str.contains(term, na=False)
    filtered = demo[mask]

st.caption(f"{len(filtered)} of {len(demo)} patients shown")
st.dataframe(filtered, use_container_width=True, hide_index=True)

if "Patient ID" in filtered.columns and not filtered.empty:
    st.markdown("---")
    st.subheader("View Patient Profile")
    selected_id = st.selectbox("Select a Patient ID", filtered["Patient ID"].tolist())

    if selected_id:
        risk_df = compute_patient_risk_scores(df_dict)
        if not risk_df.empty:
            patient_risk = risk_df[risk_df["Patient ID"] == selected_id]
            if not patient_risk.empty:
                tier = patient_risk.iloc[0]["Risk_Tier"]
                score = patient_risk.iloc[0]["Risk_Score_Normalized"]
                badge_class = tier.lower()
                st.markdown(
                    f'<span class="status-badge {badge_class}">{tier.upper()} RISK</span>'
                    f'&nbsp;&nbsp;<span style="color: var(--text-secondary); font-size: 13px;">Score {score}/100</span>',
                    unsafe_allow_html=True,
                )

        tabs = st.tabs([name for name in df_dict.keys() if not df_dict[name].empty])
        sheet_names = [name for name in df_dict.keys() if not df_dict[name].empty]

        for tab, sheet_name in zip(tabs, sheet_names):
            with tab:
                sheet_df = df_dict[sheet_name]
                if "Patient ID" in sheet_df.columns:
                    patient_rows = sheet_df[sheet_df["Patient ID"] == selected_id]
                    if not patient_rows.empty:
                        st.dataframe(patient_rows, use_container_width=True, hide_index=True)
                    else:
                        st.caption("No records for this patient in this sheet.")
                else:
                    st.caption("This sheet has no Patient ID column to filter by.")