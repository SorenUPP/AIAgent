import json
import requests
import pandas as pd
from difflib import get_close_matches

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3"

SYSTEM_PROMPT = """You are MedAgent. Return ONLY JSON.

RULES:
1. Identify the correct sheet from the schema.
2. filters MUST be a plain object (not a list). Each key is the exact column name:
   - String filter:  {"City": "Helsingborg"}
   - Numeric filter: {"LDL": {"value": 130, "operator": ">"}}
   - Multiple:       {"LDL": {"value": 130, "operator": ">"}, "Total Cholesterol": {"value": 170, "operator": ">"}}
3. NEVER use a list for filters. NEVER use "Column" as a key.
4. Always include "Patient ID", "First Name", "Last Name" in columns.
5. For ranking/scoring queries (healthiest, sickest, most abnormal, highest risk, lowest risk):
   - Set "mode": "rank"
   - Set "rank_columns": [list of numeric columns to score by]
   - Set "rank_order": "desc" for worst-first (unhealthiest), "asc" for best-first (healthiest)

Example for ranking unhealthiest:
{
  "sheet": "Lab Results",
  "mode": "rank",
  "rank_columns": ["LDL", "Total Cholesterol", "Triglycerides", "Glucose (mg/dL)"],
  "rank_order": "desc",
  "filters": {},
  "columns": ["Patient ID", "First Name", "Last Name", "LDL", "Total Cholesterol", "Triglycerides", "Glucose (mg/dL)"],
  "limit": 10
}
"""


# --------------------------------------------------
# BUILD SCHEMA CONTEXT
# --------------------------------------------------

def build_schema_context(df_dict):
    lines = []
    for sheet_name, df in df_dict.items():
        if df is None or df.empty:
            continue
        lines.append(f"\nSheet: {sheet_name}")
        lines.append("Columns: " + ", ".join(df.columns.tolist()))
        for col in df.columns:
            if df[col].dtype == object:
                samples = df[col].dropna().unique()[:5].tolist()
                if samples:
                    lines.append(f"  '{col}' sample values: {samples}")
    return "\n".join(lines)


# --------------------------------------------------
# GENERATE QUERY PLAN USING OLLAMA
# --------------------------------------------------

def generate_query_plan(df_dict, question):

    schema_context = build_schema_context(df_dict)

    planner_prompt = f"""
Available medical database schema:

{schema_context}

Convert the user's request into a dataframe query plan.

Return ONLY valid JSON.
"""

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": planner_prompt + f"\n\nUser Question: {question}"}
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "num_predict": 300
        }
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=60)
    response.raise_for_status()

    content = response.json()["message"]["content"]
    print("RAW LLM RESPONSE:")
    print(content)

    content = content.replace("```json", "").replace("```", "").strip()
    return json.loads(content)


# --------------------------------------------------
# FUZZY STRING MATCH HELPER
# --------------------------------------------------

def fuzzy_filter(series, search_val, cutoff=0.75):
    normalized = series.astype(str).str.lower().str.strip()
    search_val = str(search_val).lower().strip()
    unique_vals = normalized.unique().tolist()
    close = get_close_matches(search_val, unique_vals, n=1, cutoff=cutoff)
    match_val = close[0] if close else search_val
    if close and close[0] != search_val:
        print(f"  [fuzzy] '{search_val}' matched to '{close[0]}'")
    return normalized == match_val


# --------------------------------------------------
# EXECUTE QUERY PLAN
# --------------------------------------------------

def execute_query_plan(df_dict, plan):

    sheet_name = plan.get("sheet")
    requested_cols = plan.get("columns", [])

    if not sheet_name:
        raise Exception("No sheet specified by AI")
    if sheet_name not in df_dict:
        raise Exception(f"Sheet '{sheet_name}' not found")

    result = df_dict[sheet_name].copy()

    # --------------------------------------------------
    # AUTO-JOIN other sheets for columns not in primary sheet
    # --------------------------------------------------

    if "Patient ID" in result.columns:
        # Also include rank_columns in the list of columns to look for
        all_wanted = list(set(requested_cols + plan.get("rank_columns", [])))
        missing_cols = [c for c in all_wanted if c not in result.columns]

        for other_name, other_df in df_dict.items():
            if not missing_cols:
                break
            if other_name == sheet_name or other_df is None or other_df.empty:
                continue
            if "Patient ID" not in other_df.columns:
                continue
            needed = [c for c in missing_cols if c in other_df.columns]
            if needed:
                print(f"  [join] Pulling {needed} from '{other_name}'")
                result = result.merge(
                    other_df[["Patient ID"] + needed],
                    on="Patient ID",
                    how="left"
                )
                missing_cols = [c for c in missing_cols if c not in needed]

    # --------------------------------------------------
    # APPLY FILTERS
    # --------------------------------------------------

    filters = plan.get("filters", {})

    # Fix: AI sometimes returns a list instead of a dict
    if isinstance(filters, list):
        filters = {
            f["column"]: {"value": f["value"], "operator": f.get("operator", "=")}
            for f in filters if "column" in f
        }

    for col, value in filters.items():
        if col not in result.columns:
            print(f"  [warn] Filter column '{col}' not found, skipping")
            continue

        if isinstance(value, dict):
            operator = value.get("operator", "==")
            raw_val = value.get("value")

            numeric_attempt = pd.to_numeric(pd.Series([raw_val]), errors="coerce")
            is_numeric_val = numeric_attempt.notna().all()

            if operator in ("=", "==") and not is_numeric_val:
                mask = fuzzy_filter(result[col], raw_val)
                result = result[mask]
            else:
                numeric_col = pd.to_numeric(result[col], errors="coerce")
                num_val = float(raw_val)
                if operator == ">":
                    result = result[numeric_col > num_val]
                elif operator == ">=":
                    result = result[numeric_col >= num_val]
                elif operator == "<":
                    result = result[numeric_col < num_val]
                elif operator == "<=":
                    result = result[numeric_col <= num_val]
                else:
                    result = result[numeric_col == num_val]
        else:
            mask = fuzzy_filter(result[col], value)
            result = result[mask]

    # --------------------------------------------------
    # RANKING MODE — must happen BEFORE column selection and limit
    # --------------------------------------------------

    if plan.get("mode") == "rank":
        rank_cols = plan.get("rank_columns", [])
        rank_order = plan.get("rank_order", "desc")
        ascending = (rank_order == "asc")

        valid_rank_cols = []
        for col in rank_cols:
            if col in result.columns:
                result[col] = pd.to_numeric(result[col], errors="coerce")
                valid_rank_cols.append(col)
            else:
                print(f"  [warn] Rank column '{col}' not found, skipping")

        if valid_rank_cols:
            score = pd.Series(0.0, index=result.index)
            for col in valid_rank_cols:
                col_min = result[col].min()
                col_max = result[col].max()
                if col_max > col_min:
                    normalized = (result[col] - col_min) / (col_max - col_min)
                    score += normalized.fillna(0)
            result = result.copy()
            result["Health Risk Score"] = score.round(2)
            result = result.sort_values("Health Risk Score", ascending=ascending)
            print(f"  [rank] Sorted by score ({rank_order}) using {valid_rank_cols}")

    # --------------------------------------------------
    # SELECT COLUMNS — after ranking so score column is included
    # --------------------------------------------------

    columns = plan.get("columns", [])

    if columns:
        # Always keep Health Risk Score if it was computed
        if "Health Risk Score" in result.columns and "Health Risk Score" not in columns:
            columns = columns + ["Health Risk Score"]
        valid_columns = [c for c in columns if c in result.columns]
        if valid_columns:
            result = result[valid_columns]

    # --------------------------------------------------
    # LIMIT ROWS — always last
    # --------------------------------------------------

    limit = plan.get("limit", 20)
    result = result.head(limit)

    return result


# --------------------------------------------------
# MAIN AGENT FUNCTION
# --------------------------------------------------

def run_agent(df_dict: dict, question: str):

    if not question or not question.strip():
        return "Please ask a question about the medical data."

    try:
        plan = generate_query_plan(df_dict, question)
        print("QUERY PLAN:")
        print(plan)

        result_df = execute_query_plan(df_dict, plan)

        if result_df.empty:
            return f"No records found for that criteria in the '{plan.get('sheet')}' sheet."

        return {
            "type": "table",
            "title": f"Query Results: {question}",
            "data": result_df
        }

    except requests.exceptions.ConnectionError:
        return "OLLAMA_OFFLINE"
    except requests.exceptions.Timeout:
        return "TIMEOUT"
    except json.JSONDecodeError:
        return "AI returned invalid JSON. Try rewording the question."
    except Exception as e:
        return f"ERROR: {str(e)}"


# --------------------------------------------------
# OLLAMA STATUS CHECK
# --------------------------------------------------

def check_ollama_status() -> dict:

    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        return {"online": True, "models": models}
    except Exception:
        return {"online": False, "models": []}