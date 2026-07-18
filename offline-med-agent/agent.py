import json
import logging
import requests
import pandas as pd
from difflib import get_close_matches

import config

logger = logging.getLogger(__name__)

# ============================================================
# EXCEPTIONS
# ============================================================

class PlanValidationError(ValueError):
    """Raised when the LLM's JSON plan doesn't match the expected schema."""


class ExecutionError(Exception):
    """Raised when a structurally valid plan can't be executed (bad column, etc.)."""


ALLOWED_MODES = {"lookup", "rank", "aggregate", "group_by", "compare", "trend", "multi_step"}
AGG_FUNCS = {"count", "mean", "sum", "min", "max", "median"}


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """You are MedAgent. Return ONLY JSON. No prose, no markdown fences.

Every plan has a "mode". Pick exactly one:

1. "lookup" (default) — filter rows and show columns.
   {"sheet": "Patients", "mode": "lookup",
    "filters": {"City": "Helsingborg"},
    "columns": ["Patient ID", "First Name", "Last Name", "City"], "limit": 20}

2. "aggregate" — a single number: how many / average / total / min / max.
   "agg_func" is one of: count, mean, sum, min, max, median.
   "agg_column" is required unless agg_func is "count".
   {"sheet": "Diagnoses", "mode": "aggregate", "agg_func": "count",
    "filters": {"Diagnosis": "Diabetes"}, "label": "Patients with diabetes"}

   {"sheet": "Lab Results", "mode": "aggregate", "agg_func": "mean",
    "agg_column": "BMI", "filters": {}, "label": "Average BMI"}

3. "group_by" — a breakdown, e.g. "X by Y".
   {"sheet": "Lab Results", "mode": "group_by",
    "group_by_column": "City", "agg_func": "mean", "agg_column": "LDL",
    "filters": {}, "limit": 20}

4. "rank" — ranking/scoring (healthiest, sickest, highest risk, lowest risk).
   "rank_order": "desc" = worst-first, "asc" = best-first.
   {"sheet": "Lab Results", "mode": "rank",
    "rank_columns": ["LDL", "Total Cholesterol", "Glucose (mg/dL)"],
    "rank_order": "desc", "filters": {},
    "columns": ["Patient ID", "First Name", "Last Name"], "limit": 10}

5. "compare" — compare two or more named patients side by side.
   "compare_ids" must be a list of 2+ exact Patient IDs.
   {"sheet": "Lab Results", "mode": "compare",
    "compare_ids": ["PT-0001", "PT-0002"],
    "columns": ["LDL", "Total Cholesterol", "BMI"]}

6. "trend" — how a value changed over time for one or more patients.
   Requires a date-like column (marked in the schema) as "date_column"
   and a numeric "trend_column".
   {"sheet": "Lab Results", "mode": "trend",
    "date_column": "Visit Date", "trend_column": "BMI",
    "filters": {"Patient ID": "PT-0001"}}

7. "multi_step" — use this when the question has more than one distinct part
   (e.g. "how many diabetics, and what's their average BMI compared to
   non-diabetics", or "list the top 5 highest-risk patients, then show me
   their cholesterol trend"). Break it into 2-4 separate plans, each using
   modes 1-6 above, and put them in "steps". Each step is executed
   independently and shown to the user in order.
   {"mode": "multi_step", "steps": [
      {"sheet": "Diagnoses", "mode": "aggregate", "agg_func": "count",
       "filters": {"Diagnosis": "Diabetes"}, "label": "Diabetic patients"},
      {"sheet": "Lab Results", "mode": "rank", "rank_columns": ["Risk Score"],
       "rank_order": "desc", "filters": {}, "columns": ["Patient ID"], "limit": 5}
   ]}

FILTER RULES:
- filters is ALWAYS a plain object, never a list. Never use "Column" as a key.
- String filter:  {"City": "Helsingborg"}
- Numeric filter: {"LDL": {"value": 130, "operator": ">"}}
- Operators: "=", "!=", ">", ">=", "<", "<=", "between" (value is [low, high])
- Multiple filters are ANDed together.

GENERAL RULES:
- Always include "Patient ID", "First Name", "Last Name" in "columns" for lookup/rank/compare unless the user only asked for a count/average.
- Only use column names that appear in the schema. Never invent a column.
- Only report what's in the data. Do not infer a diagnosis, risk, or medical
  recommendation that isn't directly computed from the dataset.
"""


# ============================================================
# SCHEMA CONTEXT
# ============================================================

def build_schema_context(df_dict):
    lines = []
    for sheet_name, df in df_dict.items():
        if df is None or df.empty:
            continue
        lines.append(f"\nSheet: {sheet_name}")
        lines.append("Columns: " + ", ".join(df.columns.tolist()))
        for col in df.columns:
            if df[col].dtype == object:
                uniques = df[col].dropna().unique().tolist()
                if len(uniques) <= 25:
                    lines.append(f"  '{col}' possible values: {uniques}")
                else:
                    lines.append(f"  '{col}' sample values: {uniques[:5]}")
                parsed = pd.to_datetime(df[col], errors="coerce")
                if len(df) > 0 and parsed.notna().mean() > 0.8:
                    lines.append(f"  '{col}' looks like a DATE column (usable for trend queries)")
    return "\n".join(lines)


# ============================================================
# PLAN VALIDATION
# ============================================================

def validate_plan(plan, valid_sheets=None):
    if not isinstance(plan, dict):
        raise PlanValidationError("Plan must be a JSON object.")

    sheet = plan.get("sheet")
    if plan.get("mode") != "multi_step":
        if not sheet or not isinstance(sheet, str):
            raise PlanValidationError("'sheet' is required and must be a string.")

    if sheet and valid_sheets is not None and sheet not in valid_sheets:
        raise PlanValidationError(
            f"'sheet' must be exactly one of {sorted(valid_sheets)} — got '{sheet}'."
        )

    mode = plan.setdefault("mode", "lookup")
    if mode not in ALLOWED_MODES:
        raise PlanValidationError(f"'mode' must be one of {sorted(ALLOWED_MODES)}, got '{mode}'.")

    if mode == "multi_step":
        steps = plan.get("steps")
        if not isinstance(steps, list) or not steps:
            raise PlanValidationError("'steps' must be a non-empty list for mode 'multi_step'.")
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                raise PlanValidationError(f"Step {i} must be a JSON object.")
            validate_plan(step, valid_sheets=valid_sheets)
        return plan  # sub-plans are already fully validated individually

    filters = plan.get("filters", {})
    if not isinstance(filters, dict):
        raise PlanValidationError("'filters' must be a JSON object, not a list.")

    if mode in ("aggregate", "group_by"):
        agg_func = plan.get("agg_func")
        if agg_func not in AGG_FUNCS:
            raise PlanValidationError(f"'agg_func' must be one of {sorted(AGG_FUNCS)}.")
        if agg_func != "count" and not plan.get("agg_column"):
            raise PlanValidationError("'agg_column' is required unless agg_func is 'count'.")

    if mode == "group_by" and not plan.get("group_by_column"):
        raise PlanValidationError("'group_by_column' is required for mode 'group_by'.")

    if mode == "rank" and not plan.get("rank_columns"):
        raise PlanValidationError("'rank_columns' is required for mode 'rank'.")

    if mode == "compare":
        ids = plan.get("compare_ids")
        if not isinstance(ids, list) or len(ids) < 2:
            raise PlanValidationError("'compare_ids' must be a list of 2+ patient IDs for mode 'compare'.")

    if mode == "trend" and (not plan.get("date_column") or not plan.get("trend_column")):
        raise PlanValidationError("'date_column' and 'trend_column' are required for mode 'trend'.")

    return plan


# ============================================================
# GENERATE QUERY PLAN (WITH ONE SELF-CORRECTION RETRY)
# ============================================================

def generate_query_plan(df_dict, question, max_attempts=2):
    schema_context = build_schema_context(df_dict)
    valid_sheets = {name for name, df in df_dict.items() if df is not None and not df.empty}

    user_prompt = f"""Available medical database schema:

{schema_context}

Convert the user's request into a dataframe query plan. Return ONLY valid JSON.

User Question: {question}
"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    last_error = None
    for attempt in range(1, max_attempts + 1):
        payload = {
            "model": config.OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "num_predict": 800},
        }
        response = requests.post(config.OLLAMA_CHAT_URL, json=payload, timeout=config.OLLAMA_TIMEOUT)
        response.raise_for_status()

        content = response.json()["message"]["content"]
        content = content.replace("```json", "").replace("```", "").strip()
        logger.debug("Raw LLM response (attempt %d): %s", attempt, content)

        try:
            plan = json.loads(content)
            validate_plan(plan, valid_sheets=valid_sheets)
            return plan
        except (json.JSONDecodeError, PlanValidationError) as e:
            last_error = e
            logger.warning("Plan attempt %d rejected: %s", attempt, e)
            if attempt < max_attempts:
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": f"That JSON was invalid: {e}. Return corrected JSON only, following the rules exactly.",
                })

    raise last_error


# ============================================================
# FUZZY STRING MATCH
# ============================================================

def fuzzy_filter(series, search_val, cutoff=config.FUZZY_MATCH_CUTOFF):
    normalized = series.astype(str).str.lower().str.strip()
    search_val = str(search_val).lower().strip()
    unique_vals = normalized.unique().tolist()
    close = get_close_matches(search_val, unique_vals, n=1, cutoff=cutoff)
    match_val = close[0] if close else search_val
    if close and close[0] != search_val:
        logger.debug("Fuzzy match: '%s' -> '%s'", search_val, close[0])
    return normalized == match_val


# ============================================================
# FILTERS
# ============================================================

def apply_filters(df, filters):
    if isinstance(filters, list):
        filters = {
            f["column"]: {"value": f["value"], "operator": f.get("operator", "=")}
            for f in filters if "column" in f
        }

    result = df
    for col, value in filters.items():
        if col not in result.columns:
            logger.warning("Filter column '%s' not found, skipping", col)
            continue

        if isinstance(value, dict):
            operator = value.get("operator", "==")
            raw_val = value.get("value")

            if operator == "between":
                lo, hi = raw_val
                numeric_col = pd.to_numeric(result[col], errors="coerce")
                result = result[(numeric_col >= float(lo)) & (numeric_col <= float(hi))]
                continue

            numeric_attempt = pd.to_numeric(pd.Series([raw_val]), errors="coerce")
            is_numeric_val = numeric_attempt.notna().all() and str(raw_val).strip() != ""

            if operator in ("=", "==") and not is_numeric_val:
                result = result[fuzzy_filter(result[col], raw_val)]
            elif operator == "!=" and not is_numeric_val:
                result = result[~fuzzy_filter(result[col], raw_val)]
            elif not is_numeric_val:
                logger.warning("Skipping non-numeric value '%s' for operator '%s' on '%s'", raw_val, operator, col)
                continue
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
                elif operator == "!=":
                    result = result[numeric_col != num_val]
                else:
                    result = result[numeric_col == num_val]
        else:
            result = result[fuzzy_filter(result[col], value)]

    return result


# ============================================================
# AUTO-JOIN
# ============================================================

def collect_needed_columns(plan):
    cols = set(plan.get("columns", []))
    cols.update(plan.get("rank_columns", []))
    cols.update(plan.get("filters", {}).keys())
    for key in ("agg_column", "group_by_column", "trend_column", "date_column"):
        if plan.get(key):
            cols.add(plan[key])
    return cols


def auto_join(base_df, sheet_name, df_dict, needed_cols):
    result = base_df
    if "Patient ID" not in result.columns:
        return result

    missing = [c for c in needed_cols if c not in result.columns]
    for other_name, other_df in df_dict.items():
        if not missing:
            break
        if other_name == sheet_name or other_df is None or other_df.empty:
            continue
        if "Patient ID" not in other_df.columns:
            continue
        needed = [c for c in missing if c in other_df.columns]
        if needed:
            logger.debug("Joining columns %s from sheet '%s'", needed, other_name)
            join_df = other_df[["Patient ID"] + needed].drop_duplicates(subset="Patient ID")
            result = result.merge(join_df, on="Patient ID", how="left").reset_index(drop=True)
            missing = [c for c in missing if c not in needed]

    return result


# ============================================================
# MODE EXECUTORS
# ============================================================

AGG_FUNC_MAP = {"mean": "mean", "sum": "sum", "min": "min", "max": "max", "median": "median"}


def _select_and_limit(df, plan, extra_cols=None):
    columns = plan.get("columns", [])
    if extra_cols:
        for c in extra_cols:
            if c in df.columns and c not in columns:
                columns = columns + [c]
    if columns:
        valid = [c for c in columns if c in df.columns]
        if valid:
            df = df[valid]
    limit = plan.get("limit", config.DEFAULT_QUERY_LIMIT)
    return df.head(limit)


def _execute_lookup(df, plan):
    return _select_and_limit(df, plan)


def _execute_rank(df, plan):
    rank_cols = plan.get("rank_columns", [])
    ascending = plan.get("rank_order", "desc") == "asc"

    df = df.reset_index(drop=True).copy()
    valid_cols = []
    for col in rank_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            valid_cols.append(col)
        else:
            logger.warning("Rank column '%s' not found, skipping", col)

    if valid_cols:
        score = pd.Series(0.0, index=df.index)
        for col in valid_cols:
            lo, hi = df[col].min(), df[col].max()
            if hi > lo:
                score += ((df[col] - lo) / (hi - lo)).fillna(0)
        df["Health Risk Score"] = score.round(2)
        df = df.sort_values("Health Risk Score", ascending=ascending)

    return _select_and_limit(df, plan, extra_cols=["Health Risk Score"])


def _execute_aggregate(df, plan):
    agg_func = plan["agg_func"]

    if agg_func == "count":
        value = df["Patient ID"].nunique() if "Patient ID" in df.columns else len(df)
    else:
        col = plan["agg_column"]
        if col not in df.columns:
            raise ExecutionError(f"Aggregate column '{col}' not found after filtering.")
        numeric = pd.to_numeric(df[col], errors="coerce")
        raw = getattr(numeric, AGG_FUNC_MAP[agg_func])()
        value = round(float(raw), 2) if pd.notna(raw) else None

    label = plan.get("label") or f"{agg_func.title()} of {plan.get('agg_column', 'records')}"
    return {"type": "metric", "label": label, "value": value}


def _execute_group_by(df, plan):
    group_col = plan["group_by_column"]
    agg_func = plan.get("agg_func", "count")
    limit = plan.get("limit", config.DEFAULT_QUERY_LIMIT)

    if group_col not in df.columns:
        raise ExecutionError(f"Group-by column '{group_col}' not found after filtering.")

    if agg_func == "count":
        if "Patient ID" in df.columns:
            grouped = df.groupby(group_col)["Patient ID"].nunique().reset_index(name="Count")
        else:
            grouped = df.groupby(group_col).size().reset_index(name="Count")
        value_col = "Count"
    else:
        agg_col = plan.get("agg_column")
        if agg_col not in df.columns:
            raise ExecutionError(f"Aggregate column '{agg_col}' not found after filtering.")
        df = df.copy()
        df[agg_col] = pd.to_numeric(df[agg_col], errors="coerce")
        grouped = df.groupby(group_col)[agg_col].agg(AGG_FUNC_MAP[agg_func]).round(2).reset_index()
        value_col = agg_col

    grouped = grouped.sort_values(value_col, ascending=False).head(limit)
    return grouped


def _execute_compare(df_dict, plan):
    sheet_name = plan["sheet"]
    ids = plan["compare_ids"]

    df = df_dict[sheet_name].copy()
    needed_cols = collect_needed_columns(plan)
    df = auto_join(df, sheet_name, df_dict, needed_cols)

    if "Patient ID" not in df.columns:
        raise ExecutionError("Sheet has no 'Patient ID' column to compare on.")

    df = df[df["Patient ID"].isin(ids)]
    if df.empty:
        return df

    columns = plan.get("columns") or [c for c in df.columns if c != "Patient ID"]
    columns = [c for c in columns if c in df.columns]

    df = df.drop_duplicates(subset="Patient ID").set_index("Patient ID")[columns]
    return df.transpose()


def _execute_trend(df, plan):
    date_col = plan["date_column"]
    value_col = plan["trend_column"]

    if date_col not in df.columns or value_col not in df.columns:
        raise ExecutionError("Trend requires both the date column and value column to be present.")

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    df = df.dropna(subset=[date_col, value_col]).sort_values(date_col)

    keep = [date_col, value_col]
    if "Patient ID" in df.columns:
        keep.append("Patient ID")
    df = df[keep]

    return {"type": "chart", "chart_kind": "line", "x": date_col, "y": value_col, "data": df}


# ============================================================
# EXECUTE QUERY PLAN (DISPATCH)
# ============================================================

def execute_query_plan(df_dict, plan):
    mode = plan.get("mode", "lookup")

    if mode == "multi_step":
        return [
            {"step_plan": step, "result": execute_query_plan(df_dict, step)}
            for step in plan["steps"]
        ]

    sheet_name = plan.get("sheet")
    if not sheet_name:
        raise ExecutionError("No sheet specified by AI.")
    if sheet_name not in df_dict:
        raise ExecutionError(f"Sheet '{sheet_name}' not found.")

    if mode == "compare":
        return _execute_compare(df_dict, plan)

    base_df = df_dict[sheet_name].copy()
    needed_cols = collect_needed_columns(plan)
    base_df = auto_join(base_df, sheet_name, df_dict, needed_cols)
    base_df = apply_filters(base_df, plan.get("filters", {}))

    if mode == "aggregate":
        return _execute_aggregate(base_df, plan)
    if mode == "group_by":
        return _execute_group_by(base_df, plan)
    if mode == "trend":
        return _execute_trend(base_df, plan)
    if mode == "rank":
        return _execute_rank(base_df, plan)
    return _execute_lookup(base_df, plan)


# ============================================================
# MAIN AGENT FUNCTION
# ============================================================

def _format_result(result, plan, question):
    """Turns a raw execute_query_plan() result into a renderable content dict
    or a plain-string message. Shared by single-step and multi-step paths."""
    if isinstance(result, dict):
        if result.get("type") == "metric" and result.get("value") is None:
            return f"Couldn't compute that in the '{plan.get('sheet')}' sheet — check the column used."
        if result.get("type") == "chart" and result["data"].empty:
            return f"No trend data found for that query in the '{plan.get('sheet')}' sheet."
        result.setdefault("title", result.get("label") or f"Query Results: {question}")
        return result

    if result.empty:
        return f"No records found for that criteria in the '{plan.get('sheet')}' sheet."

    return {"type": "table", "title": f"Query Results: {question}", "data": result}


def run_agent(df_dict: dict, question: str):
    if not question or not question.strip():
        return "Please ask a question about the medical data."

    try:
        plan = generate_query_plan(df_dict, question)
        logger.debug("QUERY PLAN: %s", plan)

        result = execute_query_plan(df_dict, plan)

        if plan.get("mode") == "multi_step":
            formatted = [
                _format_result(item["result"], item["step_plan"], question)
                for item in result
            ]
            return {"type": "multi", "title": f"Query Results: {question}", "results": formatted}

        return _format_result(result, plan, question)

    except requests.exceptions.ConnectionError:
        logger.warning("Ollama connection failed")
        return "OLLAMA_OFFLINE"
    except requests.exceptions.Timeout:
        logger.warning("Ollama request timed out")
        return "TIMEOUT"
    except (json.JSONDecodeError, PlanValidationError) as e:
        logger.warning("LLM plan rejected after retries for question '%s': %s", question, e)
        return "AI returned an invalid query plan. Try rewording the question."
    except ExecutionError as e:
        logger.warning("Execution error for question '%s': %s", question, e)
        return f"⚠️ Couldn't run that query: {e}"
    except KeyError:
        logger.exception("Query plan missing expected field")
        return "The AI's query plan was malformed. Try rewording the question."
    except Exception:
        logger.exception("Unhandled error in run_agent for question: %s", question)
        return "Something went wrong processing that question. Please try again."


# ============================================================
# OLLAMA STATUS CHECK
# ============================================================

def check_ollama_status() -> dict:
    try:
        r = requests.get(config.OLLAMA_TAGS_URL, timeout=config.OLLAMA_STATUS_TIMEOUT)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        return {"online": True, "models": models}
    except Exception:
        return {"online": False, "models": []}