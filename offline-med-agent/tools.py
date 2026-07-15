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


def compute_patient_risk_scores(df_dict: dict) -> pd.DataFrame:
    """
    Deterministic (non-LLM) per-patient risk scoring based on lab flags.

    This is a transparent proxy, not a clinical judgment: it counts how many
    of each patient's lab results are flagged Abnormal (weight 2) or
    Borderline (weight 1), normalizes to 0-100 against the highest scorer in
    the dataset, and buckets into Low/Moderate/High tiers. No AI involved,
    so it's fast, reproducible, and easy to explain to a user.
    """
    lab = df_dict.get("Lab Results")
    demo = df_dict.get("Patient Demographics")
    if lab is None or lab.empty or "Patient ID" not in lab.columns:
        return pd.DataFrame()

    flag_col = None
    for c in lab.columns:
        if "flag" in c.lower() or "result" in c.lower():
            flag_col = c
            break
    if not flag_col:
        return pd.DataFrame()

    lab = lab.copy()
    flag_str = lab[flag_col].astype(str).str.lower()

    grouped = lab.groupby("Patient ID").apply(
        lambda g: pd.Series({
            "Abnormal_Count": g[flag_col].astype(str).str.contains("abnormal", case=False, na=False).sum(),
            "Borderline_Count": g[flag_col].astype(str).str.contains("borderline", case=False, na=False).sum(),
            "Total_Labs": g[flag_col].count(),
        }),
        include_groups=False,
    ).reset_index()

    grouped["Risk_Score"] = grouped["Abnormal_Count"] * 2 + grouped["Borderline_Count"] * 1

    max_score = grouped["Risk_Score"].max()
    grouped["Risk_Score_Normalized"] = (
        (grouped["Risk_Score"] / max_score * 100).round(1) if max_score and max_score > 0 else 0.0
    )

    def _tier(score_norm):
        if score_norm >= 60:
            return "High"
        elif score_norm >= 25:
            return "Moderate"
        return "Low"

    grouped["Risk_Tier"] = grouped["Risk_Score_Normalized"].apply(_tier)

    if demo is not None and not demo.empty and "Patient ID" in demo.columns:
        name_cols = [c for c in ["Patient ID", "First Name", "Last Name"] if c in demo.columns]
        grouped = grouped.merge(demo[name_cols], on="Patient ID", how="left")

    return grouped.sort_values("Risk_Score_Normalized", ascending=False).reset_index(drop=True)


def detect_lab_anomalies(df_dict: dict, z_threshold: float = 2.5) -> pd.DataFrame:
    """
    Statistical outlier detection across numeric lab columns using z-scores.

    Flags values more than `z_threshold` standard deviations from that
    column's mean *within this dataset*. This is population-relative, not a
    clinical threshold — it finds what's unusual compared to everyone else
    in the loaded data, which can catch things a fixed normal-range flag
    might miss (or over-flag, depending on how the source data was labeled).
    """
    lab = df_dict.get("Lab Results")
    if lab is None or lab.empty or "Patient ID" not in lab.columns:
        return pd.DataFrame()

    numeric_cols = []
    for c in lab.columns:
        if c == "Patient ID":
            continue
        converted = pd.to_numeric(lab[c], errors="coerce")
        if converted.notna().sum() > 1:
            numeric_cols.append(c)

    if not numeric_cols:
        return pd.DataFrame()

    outlier_rows = []
    for col in numeric_cols:
        series = pd.to_numeric(lab[col], errors="coerce")
        mean, std = series.mean(), series.std()
        if not std or pd.isna(std) or std == 0:
            continue
        z_scores = (series - mean) / std
        flagged_idx = z_scores[z_scores.abs() >= z_threshold].index
        for idx in flagged_idx:
            outlier_rows.append({
                "Patient ID": lab.loc[idx, "Patient ID"],
                "Column": col,
                "Value": lab.loc[idx, col],
                "Z-Score": round(float(z_scores.loc[idx]), 2),
            })

    if not outlier_rows:
        return pd.DataFrame()

    return (pd.DataFrame(outlier_rows)
            .sort_values("Z-Score", key=lambda s: s.abs(), ascending=False)
            .reset_index(drop=True))
