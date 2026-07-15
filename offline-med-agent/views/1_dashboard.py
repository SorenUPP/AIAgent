import streamlit as st
import pandas as pd

import ui_common
from tools import (
    get_flag_counts, get_diagnosis_counts, get_age_distribution,
    compute_patient_risk_scores, detect_lab_anomalies,
)
ui_common.render_sidebar()

st.markdown("""
<div class="page-header">
  <div class="page-eyebrow">Analytics</div>
  <div class="page-title">Dashboard</div>
  <div class="page-sub">Population overview across the loaded dataset</div>
</div>
""", unsafe_allow_html=True)

if not st.session_state.file_loaded or not st.session_state.df_dict:
    st.info("Load an Excel file from the sidebar to see the dashboard.")
    st.stop()

df_dict = st.session_state.df_dict
demo = df_dict.get("Patient Demographics", pd.DataFrame())

total_pts = len(demo) if not demo.empty else 0
avg_age = "—"
if not demo.empty and "Age" in demo.columns:
    avg_age = round(pd.to_numeric(demo["Age"], errors="coerce").mean(), 1)

flag_counts = get_flag_counts(df_dict)
abnormal = flag_counts.get("Abnormal High", 0) + flag_counts.get("Abnormal Low", 0)
borderline = flag_counts.get("Borderline", 0)

st.markdown(f"""
<div class="stat-grid">
  <div class="stat-card"><div class="stat-value">{total_pts}</div><div class="stat-label">Total Patients</div></div>
  <div class="stat-card green"><div class="stat-value">{avg_age}</div><div class="stat-label">Average Age</div></div>
  <div class="stat-card red"><div class="stat-value">{abnormal}</div><div class="stat-label">Abnormal Lab Flags</div></div>
  <div class="stat-card amber"><div class="stat-value">{borderline}</div><div class="stat-label">Borderline Results</div></div>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Age Distribution")
    age_dist = get_age_distribution(df_dict)
    if age_dist:
        st.bar_chart(pd.Series(age_dist, name="Patients"))
    else:
        st.caption("No age data available.")

with col2:
    st.subheader("Lab Result Flags")
    if flag_counts:
        st.bar_chart(pd.Series(flag_counts, name="Count"))
    else:
        st.caption("No lab flag data available.")

st.subheader("Top Diagnoses")
diag_counts = get_diagnosis_counts(df_dict)
if diag_counts:
    st.bar_chart(pd.Series(diag_counts, name="Patients"))
else:
    st.caption("No diagnosis data available.")

st.markdown("---")
st.subheader("Top At-Risk Patients")
st.caption("Deterministic score based on Abnormal/Borderline lab flag counts — "
           "not AI-generated, fully reproducible.")

risk_df = compute_patient_risk_scores(df_dict)
if not risk_df.empty:
    display_cols = [c for c in ["Patient ID", "First Name", "Last Name",
                                 "Risk_Tier", "Risk_Score_Normalized",
                                 "Abnormal_Count", "Borderline_Count", "Total_Labs"]
                     if c in risk_df.columns]
    top_risk = risk_df.head(15)[display_cols].rename(columns={
        "Risk_Tier": "Risk", "Risk_Score_Normalized": "Score (0-100)",
        "Abnormal_Count": "Abnormal Labs", "Borderline_Count": "Borderline Labs",
        "Total_Labs": "Total Labs",
    })
    st.dataframe(top_risk, use_container_width=True, hide_index=True)
else:
    st.caption("Not enough lab flag data to compute risk scores.")

st.markdown("---")
st.subheader("Statistical Outliers")
st.caption("Lab values more than 2.5 standard deviations from the dataset average — "
           "unusual relative to this population, not a clinical diagnosis.")

anomalies_df = detect_lab_anomalies(df_dict)
if not anomalies_df.empty:
    st.dataframe(anomalies_df.head(25), use_container_width=True, hide_index=True)
else:
    st.caption("No statistical outliers detected in the current dataset.")