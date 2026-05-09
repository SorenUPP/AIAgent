"""
Utility tools for the medical agent: quick computed insights
that don't need the LLM.
"""
import pandas as pd


def get_flag_counts(df_dict: dict) -> dict:
    """Count lab result flags from the Lab Results sheet."""
    lab = df_dict.get("Lab Results")
    if lab is None or lab.empty:
        return {}
    flag_col = None
    for c in lab.columns:
        if "flag" in c.lower() or "result" in c.lower():
            flag_col = c
            break
    if not flag_col:
        return {}
    return lab[flag_col].value_counts().to_dict()


def get_diagnosis_counts(df_dict: dict) -> dict:
    """Count top diagnoses from Medical Records sheet."""
    med = df_dict.get("Medical Records")
    if med is None or med.empty:
        return {}
    diag_col = None
    for c in med.columns:
        if "diagnosis" in c.lower() and "secondary" not in c.lower():
            diag_col = c
            break
    if not diag_col:
        return {}
    return med[diag_col].value_counts().head(10).to_dict()


def get_age_distribution(df_dict: dict) -> dict:
    """Bucket patients by age group."""
    demo = df_dict.get("Patient Demographics")
    if demo is None or demo.empty:
        return {}
    age_col = None
    for c in demo.columns:
        if "age" in c.lower():
            age_col = c
            break
    if not age_col:
        return {}
    ages = pd.to_numeric(demo[age_col], errors="coerce").dropna()
    buckets = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "80+": 0}
    for a in ages:
        if a <= 20: buckets["0-20"] += 1
        elif a <= 40: buckets["21-40"] += 1
        elif a <= 60: buckets["41-60"] += 1
        elif a <= 80: buckets["61-80"] += 1
        else: buckets["80+"] += 1
    return buckets
