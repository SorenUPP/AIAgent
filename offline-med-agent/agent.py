import json
import requests
import pandas as pd
from difflib import get_close_matches

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3"

SYSTEM_PROMPT = """You are MedAgent. Return ONLY JSON.

RULES:
1. Identify the correct sheet from the schema.
2. Filters:
   - For strings (Blood Type, City, Gender): {"Column": "Value"}
   - For numbers (Age): {"Column": {"value": 45, "operator": ">"}}
3. Always include "Patient ID", "First Name", and "Last Name" in columns.
4. If the user asks for a column that may be in another sheet, still include it in columns[].

Example:
{
  "sheet": "Patient Demographics",
  "filters": {"Blood Type": "A-"},
  "columns": ["Patient ID", "First Name", "Last Name", "Blood Type"],
  "limit": 20
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
        # Add sample values for text columns so AI uses correct filter strings
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
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": planner_prompt + f"\n\nUser Question: {question}"
            }
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "num_predict": 300
        }
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=60
    )

    response.raise_for_status()

    content = response.json()["message"]["content"]

    print("RAW LLM RESPONSE:")
    print(content)

    # Clean possible markdown JSON
    content = content.replace("```json", "")
    content = content.replace("```", "")
    content = content.strip()

    return json.loads(content)


# --------------------------------------------------
# FUZZY STRING MATCH HELPER
# --------------------------------------------------

def fuzzy_filter(series, search_val, cutoff=0.75):
    """
    Filter a Series by fuzzy string match.
    Falls back to exact match if no close match found.
    """
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
        missing_cols = [c for c in requested_cols if c not in result.columns]
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

    for col, value in filters.items():
        if col not in result.columns:
            print(f"  [warn] Filter column '{col}' not found, skipping")
            continue

        if isinstance(value, dict):
            operator = value.get("operator", "==")
            raw_val = value.get("value")

            # Check if it's actually a string comparison wrapped in a dict
            numeric_attempt = pd.to_numeric(pd.Series([raw_val]), errors="coerce")
            is_numeric_val = numeric_attempt.notna().all()

            if operator in ("=", "==") and not is_numeric_val:
                # String equality wrapped in dict (AI quirk)
                mask = fuzzy_filter(result[col], raw_val)
                result = result[mask]
            else:
                # True numeric comparison
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
            # Plain string filter — use fuzzy match
            mask = fuzzy_filter(result[col], value)
            result = result[mask]

    # --------------------------------------------------
    # SELECT COLUMNS
    # --------------------------------------------------

    columns = plan.get("columns", [])

    if columns:
        valid_columns = [c for c in columns if c in result.columns]
        if valid_columns:
            result = result[valid_columns]

    # --------------------------------------------------
    # LIMIT ROWS
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

        # STEP 1: AI creates query plan
        plan = generate_query_plan(df_dict, question)

        print("QUERY PLAN:")
        print(plan)

        # STEP 2: Python executes query
        result_df = execute_query_plan(df_dict, plan)

        # STEP 3: Return structured response
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

        r = requests.get(
            "http://localhost:11434/api/tags",
            timeout=5
        )

        r.raise_for_status()

        models = [
            m["name"]
            for m in r.json().get("models", [])
        ]

        return {
            "online": True,
            "models": models
        }

    except Exception:

        return {
            "online": False,
            "models": []
        }