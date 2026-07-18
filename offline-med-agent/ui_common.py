"""
Shared UI utilities used across every page of the multipage app:
CSS, session-state init, the login gate, and the sidebar.

Every page (app.py and everything in pages/) should start with:
    import ui_common
    ui_common.bootstrap()
    ui_common.require_login()
    ollama_status = ui_common.render_sidebar()
"""
import logging
from datetime import datetime, timedelta, timezone
import streamlit as st
import extra_streamlit_components as stx

import config
import auth_db
from data_loader import load_data, get_quick_stats
from agent import check_ollama_status

logger = logging.getLogger(__name__)

REMEMBER_COOKIE_NAME = "medagent_remember_token"


def get_cookie_manager():
    """One CookieManager instance per browser session, reused across reruns/pages."""
    if "cookie_manager" not in st.session_state:
        st.session_state.cookie_manager = stx.CookieManager(key="medagent_cookie_manager")
    return st.session_state.cookie_manager


# ─────────────────────────────────────────────────────────────
# Bootstrap: logging, session state, CSS
# ─────────────────────────────────────────────────────────────

def bootstrap():
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    auth_db.init_db()
    _init_session_state()
    _inject_css()


def login_entry():
    """The sole st.Page target while logged out (see app.py)."""
    st.markdown(
        "<style>[data-testid='stSidebarCollapsedControl'], "
        "[data-testid='collapsedControl'] { display: none; }</style>",
        unsafe_allow_html=True,
    )
    require_login()


def _init_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "df_dict" not in st.session_state:
        st.session_state.df_dict = {}
    if "file_loaded" not in st.session_state:
        st.session_state.file_loaded = False
    if "auth_user" not in st.session_state:
        st.session_state.auth_user = None
    if "_auth_mode" not in st.session_state:
        st.session_state["_auth_mode"] = "login"


def _inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600&display=swap');

    :root {
        --bg-canvas: #F4F5F7;
        --bg-surface: #FFFFFF;
        --bg-sidebar: #10141F;
        --border: #E2E5EA;
        --border-sidebar: #232A3B;
        --text-primary: #1B2430;
        --text-secondary: #667085;
        --text-inverse: #C7CDD9;
        --text-inverse-strong: #EDEFF3;
        --accent: #2C5282;
        --accent-subtle: #EAF0F8;
        --danger: #B3261E;
        --danger-subtle: #FBEAE9;
        --warning: #8A5A00;
        --warning-subtle: #FBF1DE;
        --success: #1E7A34;
        --success-subtle: #E7F5EA;
    }

    html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }

    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stBottom"],
    [data-testid="stMainBlockContainer"],
    [data-testid="stBottomBlockContainer"],
    .main .block-container {
        background: var(--bg-canvas) !important;
        color: var(--text-primary);
    }

    [data-testid="stHeader"] { border-bottom: 1px solid var(--border); }
    [data-testid="stToolbar"] { background: transparent !important; }

    /* Sidebar shell */
    [data-testid="stSidebar"] { background: var(--bg-sidebar) !important; border-right: 1px solid var(--border-sidebar); }
    [data-testid="stSidebar"] * { color: var(--text-inverse) !important; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: var(--text-inverse-strong) !important; font-family: 'IBM Plex Mono', monospace !important;
    }
    [data-testid="stSidebar"] hr { border-color: var(--border-sidebar) !important; }

    .sidebar-wordmark {
        font-family: 'IBM Plex Mono', monospace; font-size: 15px; font-weight: 600;
        letter-spacing: 1.5px; color: var(--text-inverse-strong); padding: 18px 0 2px 0;
    }
    .sidebar-tagline {
        font-size: 10px; letter-spacing: 0.6px; text-transform: uppercase; color: #5B6478;
        padding-bottom: 16px; border-bottom: 1px solid var(--border-sidebar); margin-bottom: 16px;
    }

    /* Page header, content area */
    .page-header { padding: 20px 0 16px 0; border-bottom: 1px solid var(--border); margin-bottom: 24px; }
    .page-eyebrow {
        font-family: 'IBM Plex Mono', monospace; font-size: 11px; letter-spacing: 1px;
        text-transform: uppercase; color: var(--text-secondary); margin-bottom: 4px;
    }
    .page-title { font-family: 'IBM Plex Sans', sans-serif; font-size: 24px; font-weight: 600; color: var(--text-primary); letter-spacing: -0.2px; }
    .page-sub { font-size: 13px; color: var(--text-secondary); margin-top: 2px; }

    /* Stat cards */
    .stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }
    .stat-card { background: var(--bg-surface); border: 1px solid var(--border); border-left: 3px solid var(--accent); border-radius: 6px; padding: 14px 18px; }
    .stat-card.red { border-left-color: var(--danger); }
    .stat-card.amber { border-left-color: var(--warning); }
    .stat-card.green { border-left-color: var(--success); }
    .stat-value {
        font-family: 'IBM Plex Mono', monospace; font-size: 26px; font-weight: 600;
        color: var(--text-primary); line-height: 1.1; font-variant-numeric: tabular-nums;
    }
    .stat-label { font-size: 11px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.6px; margin-top: 4px; }

    /* Chat */
    .chat-container { background: var(--bg-surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; margin-bottom: 16px; }
    .chat-title-bar {
        background: #FAFBFC; padding: 10px 18px; border-bottom: 1px solid var(--border);
        font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: var(--text-secondary);
        letter-spacing: 0.4px; display: flex; align-items: center; gap: 10px;
    }

    .status-badge {
        display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 4px;
        font-family: 'IBM Plex Mono', monospace; font-size: 10px; font-weight: 600;
        letter-spacing: 0.5px; border: 1px solid;
    }
    .status-badge.online   { background: var(--success-subtle); border-color: #B7DFC0; color: var(--success); }
    .status-badge.offline  { background: var(--danger-subtle);  border-color: #EFC3C0; color: var(--danger); }
    .status-badge.high     { background: var(--danger-subtle);  border-color: #EFC3C0; color: var(--danger); }
    .status-badge.moderate { background: var(--warning-subtle); border-color: #E9D8AE; color: var(--warning); }
    .status-badge.low      { background: var(--success-subtle); border-color: #B7DFC0; color: var(--success); }

    .chat-messages { padding: 18px; max-height: 480px; overflow-y: auto; display: flex; flex-direction: column; gap: 14px; }
    .msg-user {
        align-self: flex-end; background: var(--accent-subtle); border: 1px solid #CFE0F0;
        border-radius: 8px; padding: 10px 14px; max-width: 72%; font-size: 13.5px;
        color: var(--text-primary); line-height: 1.6;
    }
    .msg-agent {
        align-self: flex-start; background: var(--bg-surface); border: 1px solid var(--border);
        border-radius: 8px; padding: 12px 16px; max-width: 82%; font-size: 13.5px;
        color: var(--text-primary); line-height: 1.65;
    }
    .msg-agent code {
        background: var(--bg-canvas); border: 1px solid var(--border); border-radius: 4px;
        padding: 1px 6px; font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: var(--accent);
    }
    .msg-agent pre {
        background: var(--bg-canvas); border: 1px solid var(--border); border-radius: 6px;
        padding: 12px; overflow-x: auto; font-family: 'IBM Plex Mono', monospace;
        font-size: 12px; color: var(--text-primary); margin: 6px 0;
    }
    .msg-label { font-family: 'IBM Plex Mono', monospace; font-size: 10px; text-transform: uppercase; letter-spacing: 0.6px; color: var(--text-secondary); margin-bottom: 4px; }

    .chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 4px 0; }
    .chip {
        background: var(--bg-surface); border: 1px solid var(--border); border-radius: 6px;
        padding: 6px 12px; font-size: 12px; color: var(--text-secondary); cursor: pointer; transition: all 0.12s;
    }
    .chip:hover { border-color: var(--accent); color: var(--accent); }

    /* Inputs & buttons */
    .stTextInput > div > div > input {
        background: var(--bg-surface) !important; border: 1px solid var(--border) !important;
        border-radius: 6px !important; color: var(--text-primary) !important;
        font-family: 'Inter', sans-serif !important; font-size: 13.5px !important; padding: 10px 14px !important;
    }
    .stTextInput > div > div > input:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 2px var(--accent-subtle) !important; }
    .stButton > button {
        background: var(--accent) !important; border: none !important; border-radius: 6px !important;
        color: #FFFFFF !important; font-family: 'Inter', sans-serif !important; font-weight: 500 !important;
        font-size: 13.5px !important; padding: 8px 18px !important; transition: opacity 0.12s !important;
    }
    .stButton > button:hover { opacity: 0.9 !important; }

    .stDataFrame { border-radius: 6px; overflow: hidden; border: 1px solid var(--border); }
    [data-testid="stFileUploader"] { background: var(--bg-surface) !important; border: 1px dashed var(--border) !important; border-radius: 8px !important; }
    .streamlit-expanderHeader { background: transparent !important; border: 1px solid var(--border-sidebar) !important; border-radius: 6px !important; color: var(--text-inverse) !important; }
    .stProgress > div > div { background: var(--accent) !important; }

    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: var(--bg-canvas); }
    ::-webkit-scrollbar-thumb { background: #C7CCD4; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--accent); }

    .stSelectbox > div > div { background: var(--bg-surface) !important; border-color: var(--border) !important; color: var(--text-primary) !important; }

    /* Auth screen — quiet, no motion */
    .auth-wordmark {
        font-family: 'IBM Plex Mono', monospace; font-size: 20px; font-weight: 600;
        letter-spacing: 1px; color: var(--text-primary); text-align: center; margin-bottom: 4px;
    }
    [data-testid="stForm"] { background: var(--bg-surface); border: 1px solid var(--border); border-radius: 8px; padding: 24px 26px 8px 26px; }
    [data-testid="stFormSubmitButton"] button { transition: opacity 0.12s ease !important; }
    [data-testid="stFormSubmitButton"] button:hover { opacity: 0.9 !important; }
    [data-testid="stAlert"] { border-radius: 6px !important; }
    </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Login gate (sign in / sign up / recovery)
# ─────────────────────────────────────────────────────────────

def _first_run_setup():
    _left, center, _right = st.columns([1, 1.4, 1])
    with center:
        st.markdown('<div class="auth-logo-wrap"><span class="auth-logo">🩺</span></div>',
                    unsafe_allow_html=True)
        st.markdown("<h2 style='text-align:center;'>Create Admin Account</h2>", unsafe_allow_html=True)
        st.info("No accounts exist yet. Create the first admin account to get started.")
        _first_run_setup_body()


def _first_run_setup_body():

    if st.session_state.get("_pending_recovery_code"):
        code = st.session_state["_pending_recovery_code"]
        created_username = st.session_state["_pending_recovery_username"]
        st.success(f"Admin account '{created_username}' created!")
        st.warning("**Save this recovery code somewhere safe.** It won't be shown again.")
        st.code(code, language=None)
        if st.button("I've saved my recovery code — continue", use_container_width=True):
            del st.session_state["_pending_recovery_code"]
            del st.session_state["_pending_recovery_username"]
            st.rerun()
        st.stop()

    with st.form("bootstrap_admin_form"):
        username = st.text_input("Admin username")
        password = st.text_input("Password (min 8 characters)", type="password")
        confirm = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create admin account", use_container_width=True)

    if submitted:
        if not username.strip():
            st.error("Username is required.")
        elif len(password) < 8:
            st.error("Password must be at least 8 characters.")
        elif password != confirm:
            st.error("Passwords do not match.")
        else:
            with st.spinner("Creating account..."):
                created, recovery_code = auth_db.create_user(username.strip(), password, role="admin")
            if created:
                auth_db.log_action(username.strip(), "account_created", detail="first-run admin")
                st.session_state["_pending_recovery_code"] = recovery_code
                st.session_state["_pending_recovery_username"] = username.strip()
                st.rerun()
            else:
                st.error("That username is already taken.")

    st.stop()


def require_login():
    """Blocks the rest of the page until a user is authenticated. Call on every page."""
    if st.session_state.auth_user:
        return  # already logged in

    # Try silent auto-login from a locally-saved session file before showing
    # any form. This is a desktop app on one machine for one user, so we
    # persist the remember-me token to disk instead of a browser cookie --
    # no dependency on browser settings, SameSite policy, or which browser
    # the .bat happens to open.
    if "_remember_check_done" not in st.session_state:
        st.session_state["_remember_check_done"] = True
        if config.SESSION_FILE.exists():
            token = config.SESSION_FILE.read_text(encoding="utf-8").strip()
            user = auth_db.validate_remember_token(token) if token else None
            if user:
                st.session_state.auth_user = user
                auth_db.log_action(user["username"], "login", detail="via saved session")
                st.rerun()
            else:
                config.SESSION_FILE.unlink(missing_ok=True)  

    if auth_db.user_count() == 0:
        _first_run_setup()
        return

    _left, center, _right = st.columns([1, 1.4, 1])
    with center:
        _render_auth_forms()


def _render_auth_forms():
    mode = st.session_state["_auth_mode"]

    if mode == "login":
        st.markdown("<h2 style='text-align:center;'>Sign in to MedAgent</h2>", unsafe_allow_html=True)
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            remember_me = st.checkbox("Remember me on this device (30 days)")
            submitted = st.form_submit_button("Sign in", use_container_width=True)

        if submitted:
            with st.spinner("Checking credentials..."):
                user = auth_db.verify_credentials(username, password)
            if user:
                st.session_state.auth_user = user
                auth_db.log_action(user["username"], "login")

                if remember_me:
                    token = auth_db.create_remember_token(user["username"], days_valid=30)
                    config.SESSION_FILE.write_text(token, encoding="utf-8")

                st.toast(f"Welcome back, {user['username']}!", icon="✅")
                st.rerun()
            else:
                auth_db.log_action(username or "(unknown)", "login_failed")
                st.error("Invalid username or password.")

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Create account", use_container_width=True):
                st.session_state["_auth_mode"] = "signup"
                st.rerun()
        with col_b:
            if st.button("Forgot password?", use_container_width=True):
                st.session_state["_auth_mode"] = "recovery"
                st.rerun()

    elif mode == "signup":
        st.markdown("<h2 style='text-align:center;'>Create Account</h2>", unsafe_allow_html=True)

        if st.session_state.get("_signup_recovery_code"):
            st.success(f"Account '{st.session_state['_signup_username']}' created!")
            st.warning("**Save this recovery code somewhere safe.** It won't be shown again.")
            st.code(st.session_state["_signup_recovery_code"], language=None)
            if st.button("I've saved my recovery code — go to sign in", use_container_width=True):
                del st.session_state["_signup_recovery_code"]
                del st.session_state["_signup_username"]
                st.session_state["_auth_mode"] = "login"
                st.rerun()
        else:
            with st.form("signup_form"):
                s_username = st.text_input("Choose a username")
                s_password = st.text_input("Choose a password (min 8 characters)", type="password")
                s_confirm = st.text_input("Confirm password", type="password")
                s_submitted = st.form_submit_button("Create account", use_container_width=True)

            if s_submitted:
                if not s_username.strip():
                    st.error("Username is required.")
                elif len(s_password) < 8:
                    st.error("Password must be at least 8 characters.")
                elif s_password != s_confirm:
                    st.error("Passwords do not match.")
                else:
                    with st.spinner("Creating account..."):
                        created, recovery_code = auth_db.create_user(s_username.strip(), s_password, role="user")
                    if created:
                        auth_db.log_action(s_username.strip(), "account_created", detail="self-signup")
                        st.session_state["_signup_recovery_code"] = recovery_code
                        st.session_state["_signup_username"] = s_username.strip()
                        st.rerun()
                    else:
                        st.error("That username is already taken.")

            if st.button("← Back to sign in", use_container_width=True):
                st.session_state["_auth_mode"] = "login"
                st.rerun()

    else:  # recovery
        st.markdown("<h2 style='text-align:center;'>Reset Password</h2>", unsafe_allow_html=True)
        st.caption("Enter your username and the recovery code you saved when your account was created.")

        with st.form("recovery_form"):
            r_username = st.text_input("Username")
            r_code = st.text_input("Recovery code", placeholder="XXXX-XXXX-XXXX")
            r_new_password = st.text_input("New password", type="password")
            r_confirm = st.text_input("Confirm new password", type="password")
            r_submitted = st.form_submit_button("Reset password", use_container_width=True)

        if r_submitted:
            if len(r_new_password) < 8:
                st.error("Password must be at least 8 characters.")
            elif r_new_password != r_confirm:
                st.error("Passwords do not match.")
            else:
                with st.spinner("Verifying recovery code..."):
                    ok = auth_db.reset_password_with_recovery(r_username.strip(), r_code.strip(), r_new_password)
                if ok:
                    auth_db.log_action(r_username.strip(), "password_reset", detail="via recovery code")
                    st.toast("Password reset. You can sign in now.", icon="✅")
                    st.session_state["_auth_mode"] = "login"
                    st.rerun()
                else:
                    auth_db.log_action(r_username.strip() or "(unknown)", "password_reset_failed")
                    st.error("Username and recovery code don't match, or this account has no "
                             "recovery code on file — ask an admin to reset your password instead.")

        if st.button("← Back to sign in", use_container_width=True):
            st.session_state["_auth_mode"] = "login"
            st.rerun()

    st.stop()


# ─────────────────────────────────────────────────────────────
# Sidebar (shared across all pages)
# ─────────────────────────────────────────────────────────────

def render_sidebar():
    """Renders the full sidebar. Returns the Ollama status dict for pages that need it."""
    with st.sidebar:
        st.markdown(
            '<div class="sidebar-wordmark">MEDAGENT</div>'
            '<div class="sidebar-tagline">Clinical Data Platform · Local Instance</div>',
            unsafe_allow_html=True,
        )
        st.caption(f"Signed in as **{st.session_state.auth_user['username']}** "
                   f"({st.session_state.auth_user['role']})")
        if st.button("Log out", key="sidebar_logout_btn"):
            auth_db.log_action(st.session_state.auth_user["username"], "logout")
            token = get_cookie_manager().get(REMEMBER_COOKIE_NAME)
            if token:
                auth_db.revoke_remember_token(token)
                get_cookie_manager().delete(REMEMBER_COOKIE_NAME, key="delete_remember_cookie")
            st.session_state.auth_user = None
            st.session_state.messages = []
            st.session_state["_remember_check_done"] = False
            st.rerun()

        with st.expander("My recovery code"):
            me = st.session_state.auth_user["username"]
            has_code = auth_db.has_recovery_code(me)

            if st.session_state.get("_my_new_recovery_code"):
                st.warning("Save this code somewhere safe — it won't be shown again:")
                st.code(st.session_state["_my_new_recovery_code"], language=None)
                if st.button("Done", key="my_recovery_ack"):
                    del st.session_state["_my_new_recovery_code"]
                    st.rerun()
            else:
                if has_code:
                    st.caption("You already have a recovery code on file. Generating a new one invalidates the old one.")
                else:
                    st.caption("You don't have a recovery code yet. Generate one so you can reset your own password later.")
                confirm_pw = st.text_input("Confirm your password", type="password", key="my_recovery_confirm_pw")
                label = "Generate new recovery code" if has_code else "Generate my recovery code"
                if st.button(label, key="my_recovery_generate_btn"):
                    if not auth_db.verify_credentials(me, confirm_pw):
                        st.error("Incorrect password.")
                    else:
                        new_code = auth_db.regenerate_recovery_code(me)
                        auth_db.log_action(me, "recovery_code_regenerated", detail="self-service")
                        st.session_state["_my_new_recovery_code"] = new_code
                        st.rerun()

        if st.session_state.auth_user["role"] == "admin":
            with st.expander("Add user (admin)"):
                if st.session_state.get("_admin_new_recovery_code"):
                    st.success(f"User '{st.session_state['_admin_new_recovery_username']}' created.")
                    st.warning("Give this recovery code to the user now — it won't be shown again:")
                    st.code(st.session_state["_admin_new_recovery_code"], language=None)
                    if st.button("Done", key="admin_recovery_ack"):
                        del st.session_state["_admin_new_recovery_code"]
                        del st.session_state["_admin_new_recovery_username"]
                        st.rerun()
                else:
                    new_username = st.text_input("New username", key="admin_new_username")
                    new_password = st.text_input("New password", type="password", key="admin_new_password")
                    new_role = st.selectbox("Role", ["user", "admin"], key="admin_new_role")
                    if st.button("Create account", key="admin_create_btn"):
                        if not new_username.strip() or len(new_password) < 8:
                            st.error("Username required, password must be 8+ characters.")
                        else:
                            ok, recovery_code = auth_db.create_user(new_username.strip(), new_password, role=new_role)
                            if ok:
                                auth_db.log_action(
                                    st.session_state.auth_user["username"], "user_created",
                                    detail=f"created '{new_username}' with role '{new_role}'",
                                )
                                st.session_state["_admin_new_recovery_code"] = recovery_code
                                st.session_state["_admin_new_recovery_username"] = new_username.strip()
                                st.rerun()
                            else:
                                st.error("That username already exists.")

            with st.expander("Regenerate a user's recovery code (admin)"):
                existing_users_rc = [u["username"] for u in auth_db.list_users()]
                target_user_rc = st.selectbox("User", existing_users_rc, key="admin_regen_target")
                if st.session_state.get("_admin_regen_code"):
                    st.warning(f"New code for '{st.session_state['_admin_regen_username']}' — won't be shown again:")
                    st.code(st.session_state["_admin_regen_code"], language=None)
                    if st.button("Done", key="admin_regen_ack"):
                        del st.session_state["_admin_regen_code"]
                        del st.session_state["_admin_regen_username"]
                        st.rerun()
                else:
                    if st.button("Generate new recovery code", key="admin_regen_btn"):
                        new_code = auth_db.regenerate_recovery_code(target_user_rc)
                        auth_db.log_action(
                            st.session_state.auth_user["username"], "recovery_code_regenerated",
                            detail=f"for '{target_user_rc}' (admin action)",
                        )
                        st.session_state["_admin_regen_code"] = new_code
                        st.session_state["_admin_regen_username"] = target_user_rc
                        st.rerun()

            with st.expander("Reset a user's password (admin)"):
                existing_users = [u["username"] for u in auth_db.list_users()]
                target_user = st.selectbox("User", existing_users, key="admin_reset_target")
                reset_password_val = st.text_input("New password", type="password", key="admin_reset_password")
                if st.button("Reset password", key="admin_reset_btn"):
                    if len(reset_password_val) < 8:
                        st.error("Password must be at least 8 characters.")
                    else:
                        if auth_db.admin_reset_password(target_user, reset_password_val):
                            auth_db.log_action(
                                st.session_state.auth_user["username"], "admin_password_reset",
                                detail=f"reset password for '{target_user}'",
                            )
                            st.success(f"Password reset for '{target_user}'.")
                        else:
                            st.error("User not found.")

        st.markdown("---")

        ollama = check_ollama_status()
        if ollama["online"]:
            st.markdown('<span class="status-badge online">OLLAMA · ONLINE</span>', unsafe_allow_html=True)
            if ollama["models"]:
                st.caption(f"Models: {', '.join(ollama['models'][:3])}")
        else:
            st.markdown('<span class="status-badge offline">OLLAMA · OFFLINE</span>', unsafe_allow_html=True)
            st.caption("Run `ollama serve` to start")

        st.markdown("---")
        st.markdown("### Load Data")
        uploaded = st.file_uploader(
            "Upload Excel (.xlsx)", type=["xlsx"], label_visibility="collapsed",
            key="sidebar_file_uploader",
        )

        if uploaded:
            with st.spinner("Parsing sheets..."):
                df_dict = load_data(uploaded)
                st.session_state.df_dict = df_dict
                st.session_state.file_loaded = True
                st.session_state.messages = []
            st.success(f"Loaded {len(df_dict)} sheets")

        if not st.session_state.file_loaded:
            if config.DEFAULT_DATA_PATH.exists():
                df_dict = load_data(config.DEFAULT_DATA_PATH)
                st.session_state.df_dict = df_dict
                st.session_state.file_loaded = True
                st.caption("↑ Using default patients.xlsx")

        st.markdown("---")

        if st.session_state.file_loaded and st.session_state.df_dict:
            stats = get_quick_stats(st.session_state.df_dict)
            st.markdown("###Sheets")
            for sheet, info in stats.items():
                with st.expander(f"{sheet} ({info['rows']} rows)"):
                    st.caption(f"**Columns:** {', '.join(info['columns'])}")

        st.markdown("---")
        if st.button("🗑 Clear Chat", key="sidebar_clear_chat_btn"):
            st.session_state.messages = []
            st.rerun()

        st.markdown("---")
        st.caption("MedAgent · Powered by Ollama\nAll patient data is synthetic.")

    return ollama