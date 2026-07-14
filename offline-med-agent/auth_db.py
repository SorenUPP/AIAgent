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
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

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
        # Migration: add recovery-code columns if upgrading an existing db
        existing_cols = [row["name"] for row in conn.execute("PRAGMA table_info(users)")]
        if "recovery_salt" not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN recovery_salt TEXT")
        if "recovery_code_hash" not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN recovery_code_hash TEXT")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS remember_tokens (
                token_hash TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                expires_at TEXT NOT NULL,
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


def _generate_recovery_code() -> str:
    """Human-typeable code like 'XK4P-7QRT-2MNB', avoiding ambiguous characters."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L
    groups = ["".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3)]
    return "-".join(groups)


def create_user(username: str, password: str, role: str = "user"):
    """
    Returns (success: bool, recovery_code: str | None).

    The recovery code is generated here and returned ONCE in plaintext so it
    can be shown to the user. Only its hash is stored — it cannot be
    retrieved again later, the same as a password.
    """
    salt = os.urandom(16)
    password_hash = _hash_password(password, salt)

    recovery_code = _generate_recovery_code()
    recovery_salt = os.urandom(16)
    recovery_hash = _hash_password(recovery_code, recovery_salt)

    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO users "
                "(username, salt, password_hash, role, created_at, recovery_salt, recovery_code_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (username, salt.hex(), password_hash, role,
                 datetime.now(timezone.utc).isoformat(),
                 recovery_salt.hex(), recovery_hash),
            )
        logger.info("Created user '%s' with role '%s'", username, role)
        return True, recovery_code
    except sqlite3.IntegrityError:
        logger.warning("Attempted to create duplicate user '%s'", username)
        return False, None


def reset_password_with_recovery(username: str, recovery_code: str, new_password: str) -> bool:
    """Self-service reset: validates the recovery code, then sets a new password."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT recovery_salt, recovery_code_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if row is None or not row["recovery_salt"]:
        _hash_password(recovery_code, os.urandom(16))  # constant-time-ish, avoids leaking existence
        return False

    salt = bytes.fromhex(row["recovery_salt"])
    candidate = _hash_password(recovery_code.strip().upper(), salt)
    if not hmac.compare_digest(candidate, row["recovery_code_hash"]):
        return False

    new_salt = os.urandom(16)
    new_hash = _hash_password(new_password, new_salt)
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET salt = ?, password_hash = ? WHERE username = ?",
            (new_salt.hex(), new_hash, username),
        )
    revoke_all_tokens_for_user(username)
    logger.info("Password reset via recovery code for user '%s'", username)
    return True


def admin_reset_password(target_username: str, new_password: str) -> bool:
    """Admin-driven reset: no recovery code needed, just admin authority."""
    new_salt = os.urandom(16)
    new_hash = _hash_password(new_password, new_salt)
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE users SET salt = ?, password_hash = ? WHERE username = ?",
            (new_salt.hex(), new_hash, target_username),
        )
    if cur.rowcount > 0:
        revoke_all_tokens_for_user(target_username)
    return cur.rowcount > 0


def list_users():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT username, role, created_at FROM users ORDER BY username"
        ).fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────
# Remember-me tokens
# ─────────────────────────────────────────────────────────────

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_remember_token(username: str, days_valid: int = 30) -> str:
    """Generates a new remember-me token, stores its hash, returns the raw token (put in a cookie)."""
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(days=days_valid)).isoformat()

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO remember_tokens (token_hash, username, expires_at, created_at) "
            "VALUES (?, ?, ?, ?)",
            (token_hash, username, expires_at, now.isoformat()),
        )
    return token


def validate_remember_token(token: str):
    """Returns {'username', 'role'} if the token is valid and unexpired, else None."""
    if not token:
        return None

    token_hash = _hash_token(token)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT username, expires_at FROM remember_tokens WHERE token_hash = ?",
            (token_hash,),
        ).fetchone()

    if row is None:
        return None

    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        revoke_remember_token(token)
        return None

    with get_connection() as conn:
        user_row = conn.execute(
            "SELECT username, role FROM users WHERE username = ?", (row["username"],)
        ).fetchone()

    if user_row is None:
        return None
    return {"username": user_row["username"], "role": user_row["role"]}


def revoke_remember_token(token: str):
    if not token:
        return
    with get_connection() as conn:
        conn.execute("DELETE FROM remember_tokens WHERE token_hash = ?", (_hash_token(token),))


def revoke_all_tokens_for_user(username: str):
    """Call this on password change so old remember-me cookies stop working."""
    with get_connection() as conn:
        conn.execute("DELETE FROM remember_tokens WHERE username = ?", (username,))
    logger.info("Revoked all remember-me tokens for '%s'", username)


def has_recovery_code(username: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT recovery_code_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    return bool(row and row["recovery_code_hash"])


def regenerate_recovery_code(username: str):
    """
    Generates a new recovery code for an existing user, invalidating any
    previous one. Returns the new plaintext code (shown once), or None if
    the user doesn't exist.
    """
    recovery_code = _generate_recovery_code()
    recovery_salt = os.urandom(16)
    recovery_hash = _hash_password(recovery_code, recovery_salt)

    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE users SET recovery_salt = ?, recovery_code_hash = ? WHERE username = ?",
            (recovery_salt.hex(), recovery_hash, username),
        )
    if cur.rowcount == 0:
        return None
    logger.info("Recovery code regenerated for user '%s'", username)
    return recovery_code

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