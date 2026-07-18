"""
Centralized configuration for MedAgent.
Reads from environment variables (or a local .env file) so nothing
is hardcoded across agent.py / app.py / data_loader.py.
"""
import os
from pathlib import Path

# Load .env if python-dotenv is available (optional, dev convenience)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent

# --- Ollama ---
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_CHAT_URL = f"{OLLAMA_HOST}/api/chat"
OLLAMA_TAGS_URL = f"{OLLAMA_HOST}/api/tags"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b-instruct")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120")) 
OLLAMA_STATUS_TIMEOUT = int(os.getenv("OLLAMA_STATUS_TIMEOUT", "5"))

# --- Data ---
DEFAULT_DATA_PATH = BASE_DIR / "data" / "patients.xlsx"
DEFAULT_QUERY_LIMIT = int(os.getenv("DEFAULT_QUERY_LIMIT", "20"))
FUZZY_MATCH_CUTOFF = float(os.getenv("FUZZY_MATCH_CUTOFF", "0.75"))

# --- App ---
APP_TITLE = os.getenv("APP_TITLE", "MedAgent — AI Medical Data Assistant")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# --- Auth / Audit ---
# Separate from patient data on purpose — this only holds accounts + the audit trail.
APP_DB_PATH = BASE_DIR / "data" / "medagent_app.db"
SESSION_FILE = BASE_DIR / "data" / ".session_token"
PBKDF2_ITERATIONS = int(os.getenv("PBKDF2_ITERATIONS", "260000"))
SESSION_IDLE_HINT_MIN = int(os.getenv("SESSION_IDLE_HINT_MIN", "60"))  # informational only, see note below

# --- Login rate limiting ---
# After MAX_FAILED_LOGIN_ATTEMPTS consecutive failures for a username, that
# username is locked out for LOGIN_LOCKOUT_MINUTES. Resets on any success.
MAX_FAILED_LOGIN_ATTEMPTS = int(os.getenv("MAX_FAILED_LOGIN_ATTEMPTS", "5"))
LOGIN_LOCKOUT_MINUTES = int(os.getenv("LOGIN_LOCKOUT_MINUTES", "5"))