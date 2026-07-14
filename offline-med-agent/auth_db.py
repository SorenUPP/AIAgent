"""
Lightweight local auth + audit trail for MedAgent.

Stores ONLY: user accounts (hashed passwords) and an audit log of
questions/actions. Patient data stays in Excel as before — this is a
separate, small SQLite file purely for who-did-what tracking.
"""
import hashlib
import hmac
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import config

logger = logging.getLogger(__name__)


@contextmanager
def get_connection():
    config.APP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.APP_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                detail TEXT,
                timestamp TEXT NOT NULL
            )
        """)


def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, config.PBKDF2_ITERATIONS
    ).hex()


def create_user(username: str, password: str, role: str = "user") -> bool:
    """Returns False if the username already exists."""
    salt = os.urandom(16)
    password_hash = _hash_password(password, salt)
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO users (username, salt, password_hash, role, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (username, salt.hex(), password_hash, role,
                 datetime.now(timezone.utc).isoformat()),
            )
        logger.info("Created user '%s' with role '%s'", username, role)
        return True
    except sqlite3.IntegrityError:
        logger.warning("Attempted to create duplicate user '%s'", username)
        return False


def verify_credentials(username: str, password: str):
    """Returns the user row (as dict) on success, None on failure."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT username, salt, password_hash, role FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if row is None:
        # Still run a hash to avoid leaking via response-time whether the
        # username exists at all.
        _hash_password(password, os.urandom(16))
        return None

    salt = bytes.fromhex(row["salt"])
    candidate_hash = _hash_password(password, salt)
    if hmac.compare_digest(candidate_hash, row["password_hash"]):
        return {"username": row["username"], "role": row["role"]}
    return None


def log_action(username: str, action: str, detail: str = ""):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO audit_log (username, action, detail, timestamp) VALUES (?, ?, ?, ?)",
            (username, action, detail, datetime.now(timezone.utc).isoformat()),
        )


def get_audit_log(limit: int = 200):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT username, action, detail, timestamp FROM audit_log "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def user_count() -> int:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]