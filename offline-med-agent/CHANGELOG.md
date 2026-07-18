# Changelog — Bug Fix & Security Hardening Pass

Scope: fix real bugs and harden security/config. Existing architecture,
styling, and features were left intact (they were already solid).

## Critical
- **Dashboard crash on direct load/refresh**: `views/1_dashboard.py` was the
  only page that skipped `ui_common.bootstrap()` / `ui_common.require_login()`.
  A fresh session landing there directly would `KeyError` on
  `st.session_state.auth_user`. Now matches every other view.
- **Broken page route on case-sensitive filesystems**: `app.py` registered
  `views/1_Dashboard.py`, but the file on disk is `views/1_dashboard.py`.
  Worked by luck on Windows/macOS, would 404/crash on Linux. Fixed the
  reference to match the real filename.

## High (security)
- **No login rate limiting**: added a `failed_logins` table and lockout —
  5 failed attempts locks a username out for 5 minutes (both configurable
  via `MAX_FAILED_LOGIN_ATTEMPTS` / `LOGIN_LOCKOUT_MINUTES`). Resets on
  success.
- **Secrets/session artifacts were being shipped**: removed `.env`,
  `data/.session_token`, and the local `medagent_app.db` from the
  distributed copy; added `.env.example`; closed the `.gitignore` gap so
  `.session_token` is never committed either.
- **Remember-me token file permissions**: the on-disk session token is now
  written with `chmod 600` where the OS supports it.
- **Username whitespace inconsistency**: sign-up stripped usernames, sign-in
  didn't — a copy-pasted username with trailing whitespace could silently
  fail to match. Login now strips consistently.

## Medium
- **Ollama status hit the network on every rerun**: Streamlit reruns the
  whole script on every widget interaction, so the sidebar's "online/offline"
  check fired a real HTTP request every time. Wrapped in `st.cache_data(ttl=5)`.
- **Admin "reset password" / "regenerate recovery code" panels crashed if no
  users existed** (empty `st.selectbox`) — now shows a caption instead.

## Low
- Fixed a literal `###Sheets` rendering as plain text instead of a heading
  (missing space) in the sidebar.
- Removed stale shipped `__pycache__` bytecode.

## Not changed
The auth model (PBKDF2 + constant-time compare), audit logging, deterministic
risk-scoring/anomaly tools, and the existing visual design were already in
good shape and were left as-is.

---

# Changelog — UX Gaps Pass

## Reset to default data
- The sidebar previously had no way to drop an uploaded file and go back to
  the default `patients.xlsx` short of restarting the app. Added a
  "↺ Reset to default data" button, plus a clear label showing whether the
  currently loaded dataset is the default or an uploaded file (and its name).
  The file uploader widget is remounted on reset so its old selection
  actually clears, not just the app's internal state.

## Export results, not just the audit log
- Query Console table and trend-chart results can now be exported as CSV
  individually via a per-result "⬇ Export as CSV" button, including inside
  multi-step query results and archived history — previously only the Audit
  Log page had an export option.

## Loading feedback for heavier computations
- Dashboard's risk-scoring and statistical-outlier detection now show a
  spinner while computing, instead of a blank pause on larger datasets.
- Patient Explorer's per-patient risk lookup (triggered on every patient
  selection) now shows a spinner too.

---

# Changelog — "AI got dumber" regression fix

## Root cause: pandas 3.0 broke the LLM's schema context
`requirements.txt` had an unpinned `pandas>=2.0`, so a fresh install now
pulls **pandas 3.0**, which changed the default dtype for text columns from
`object` to a native `string` dtype (PDEP-14). `agent.py`'s
`build_schema_context()` — the function that tells the LLM what values
actually exist in each column (city names, diagnoses, gender values, etc.) —
checked `df[col].dtype == object`, which now silently returns `False` for
every text column. The LLM was effectively answering questions with no idea
what real values existed in the data, causing it to guess sheet names and
filter values instead of picking correct ones — that's the "gotten dumber"
behavior, and almost certainly the direct cause of failures like a plain
"give me a table of patients" query erroring out.

**Fix:**
- `build_schema_context()` now detects text columns with
  `pd.api.types.is_object_dtype()` **or** `pd.api.types.is_string_dtype()`,
  so it works correctly on both old and new pandas.
- Verified against the real `patients.xlsx`: value hints (e.g. `'City'
  possible values: [...]`, `'Gender' possible values: ['Male', 'Female']`)
  are restored for every text column, and a fuzzy-filtered lookup query
  (`City = Stockholm`) runs end-to-end correctly.
- Fixing the check also means all text columns are now correctly checked for
  looking like dates, which triggered a `UserWarning` flood on every single
  question (one per non-date text column, e.g. names/emails/addresses).
  Suppressed that warning since `errors="coerce"` already handles it safely
  — it was just noise, not a real issue.
- Pinned `pandas>=2.0,<3.1` in `requirements.txt` so this can't silently
  regress again on a future fresh install.

---

# Changelog — Silent HTTP error swallowed as generic message

## Root cause: `requests.exceptions.HTTPError` was never caught
`generate_query_plan()` calls `response.raise_for_status()`, which raises
`requests.exceptions.HTTPError` whenever Ollama responds with a non-2xx
status — most commonly a **404 when `OLLAMA_MODEL` isn't pulled locally**,
or a 500 from Ollama itself. `run_agent()`'s exception handling only caught
`ConnectionError` and `Timeout`, so `HTTPError` fell straight through to the
catch-all `except Exception`, which returns the generic, unhelpful
"Something went wrong processing that question." — for *any* question,
however simple, as long as the underlying HTTP call kept failing. This is
almost certainly what was happening: the code silently threw away the real
reason for the failure.

**Fix:**
- Added a dedicated `except requests.exceptions.HTTPError` branch that reads
  the response status code and surfaces an actionable message — e.g. for a
  404 it now explicitly says the configured model isn't available and gives
  the exact `ollama pull <model>` command to run.
- Added `except requests.exceptions.RequestException` as a safety net above
  the final catch-all, so any other networking failure talking to Ollama
  also gets a real, specific message instead of the generic one.
- Verified with mocked 404, 500, and successful responses — all three now
  produce correct, distinct outcomes.
- Fixed a related bug this surfaced: the Query Console's audit-log
  "success"/"error" classification only checked for messages starting with
  `"!"` or `"ERROR"`, which nothing in `agent.py` actually returns — every
  real error message (including the pre-existing `ExecutionError` message)
  starts with `⚠️` and was being logged as `success`. Fixed the
  classification to match the agent's actual message prefixes.
- Fixed `README.md`, which told users to `ollama pull llama3`, while the
  real installer (`INSTALL.bat`) and `config.py`'s actual default both use
  `qwen2.5:14b-instruct`. Anyone following the README instead of the
  installer would have hit exactly this 404 — updated the README to match
  reality, and pointed the "changing the model" section at `config.py`/`.env`
  instead of a stale line reference in `agent.py`.
