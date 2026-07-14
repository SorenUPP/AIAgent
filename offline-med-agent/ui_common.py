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
import streamlit as st

import config
import auth_db
from data_loader import load_data, get_quick_stats
from agent import check_ollama_status

logger = logging.getLogger(__name__)


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
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=DM+Sans:wght@300;400;500;600&display=swap');

    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .stApp { background: #0a0f1a; color: #c9d8e8; }

    [data-testid="stSidebar"] { background: #0d1421 !important; border-right: 1px solid #1e2d45; }
    [data-testid="stSidebar"] * { color: #a8c0d6 !important; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: #e2eef7 !important; }

    .medagent-header { display: flex; align-items: center; gap: 16px; padding: 28px 0 20px 0; border-bottom: 1px solid #1e2d45; margin-bottom: 28px; }
    .medagent-logo { font-size: 42px; line-height: 1; }
    .medagent-title { font-family: 'IBM Plex Mono', monospace; font-size: 28px; font-weight: 600; color: #4fc3f7; letter-spacing: -0.5px; }
    .medagent-sub { font-size: 13px; color: #5a7a9a; letter-spacing: 0.4px; text-transform: uppercase; margin-top: 2px; }

    .stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 28px; }
    .stat-card { background: #0d1421; border: 1px solid #1e2d45; border-radius: 10px; padding: 18px 20px; position: relative; overflow: hidden; }
    .stat-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, #4fc3f7, #0288d1); }
    .stat-card.red::before { background: linear-gradient(90deg, #ef5350, #b71c1c); }
    .stat-card.amber::before { background: linear-gradient(90deg, #ffa726, #e65100); }
    .stat-card.green::before { background: linear-gradient(90deg, #66bb6a, #1b5e20); }
    .stat-value { font-family: 'IBM Plex Mono', monospace; font-size: 32px; font-weight: 600; color: #e2eef7; line-height: 1.1; }
    .stat-label { font-size: 11px; color: #5a7a9a; text-transform: uppercase; letter-spacing: 0.8px; margin-top: 4px; }

    .chat-container { background: #0d1421; border: 1px solid #1e2d45; border-radius: 12px; padding: 0; overflow: hidden; margin-bottom: 16px; }
    .chat-title-bar { background: #111c2e; padding: 12px 20px; border-bottom: 1px solid #1e2d45; font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: #4fc3f7; letter-spacing: 0.5px; display: flex; align-items: center; gap: 8px; }
    .chat-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
    .chat-dot.green { background: #4caf50; }
    .chat-dot.red   { background: #ef5350; }
    .chat-dot.amber { background: #ffa726; }
    .chat-messages { padding: 20px; max-height: 480px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px; }

    .msg-user { align-self: flex-end; background: #1a3a5c; border: 1px solid #1e5082; border-radius: 16px 16px 4px 16px; padding: 12px 16px; max-width: 72%; font-size: 14px; color: #cde8f8; line-height: 1.6; }
    .msg-agent { align-self: flex-start; background: #111c2e; border: 1px solid #1e2d45; border-radius: 4px 16px 16px 16px; padding: 14px 18px; max-width: 82%; font-size: 14px; color: #c9d8e8; line-height: 1.7; }
    .msg-agent code { background: #0a0f1a; border: 1px solid #1e2d45; border-radius: 4px; padding: 1px 6px; font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: #4fc3f7; }
    .msg-agent pre { background: #0a0f1a; border: 1px solid #1e2d45; border-radius: 8px; padding: 14px; overflow-x: auto; font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: #a8c0d6; margin: 8px 0; }
    .msg-label { font-family: 'IBM Plex Mono', monospace; font-size: 10px; text-transform: uppercase; letter-spacing: 0.8px; color: #3a5a7a; margin-bottom: 4px; }

    .status-pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 20px; font-family: 'IBM Plex Mono', monospace; font-size: 11px; font-weight: 600; letter-spacing: 0.3px; }
    .status-online { background: #1a3a1a; border: 1px solid #2a6a2a; color: #66bb6a; }
    .status-offline { background: #3a1a1a; border: 1px solid #6a2a2a; color: #ef5350; }

    .chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0 4px 0; }
    .chip { background: #111c2e; border: 1px solid #1e3a5a; border-radius: 20px; padding: 6px 14px; font-size: 12px; color: #7ab3d4; cursor: pointer; transition: all 0.15s; }
    .chip:hover { background: #1a3a5c; border-color: #4fc3f7; color: #cde8f8; }

    .stTextInput > div > div > input { background: #111c2e !important; border: 1px solid #1e3a5a !important; border-radius: 10px !important; color: #c9d8e8 !important; font-family: 'DM Sans', sans-serif !important; font-size: 14px !important; padding: 12px 16px !important; }
    .stTextInput > div > div > input:focus { border-color: #4fc3f7 !important; box-shadow: 0 0 0 2px rgba(79,195,247,0.15) !important; }
    .stButton > button { background: linear-gradient(135deg, #0288d1, #4fc3f7) !important; border: none !important; border-radius: 10px !important; color: #000d1a !important; font-family: 'DM Sans', sans-serif !important; font-weight: 600 !important; font-size: 14px !important; padding: 10px 24px !important; transition: opacity 0.15s !important; }
    .stButton > button:hover { opacity: 0.88 !important; }

    .stDataFrame { border-radius: 10px; overflow: hidden; }
    [data-testid="stDataFrameResizable"] { background: #0d1421; }
    [data-testid="stFileUploader"] { background: #0d1421 !important; border: 1px dashed #1e3a5a !important; border-radius: 12px !important; }
    .streamlit-expanderHeader { background: #0d1421 !important; border: 1px solid #1e2d45 !important; border-radius: 8px !important; color: #a8c0d6 !important; }
    .stProgress > div > div { background: #4fc3f7 !important; }

    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #0a0f1a; }
    ::-webkit-scrollbar-thumb { background: #1e3a5a; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #4fc3f7; }

    .stSelectbox > div > div { background: #111c2e !important; border-color: #1e3a5a !important; color: #c9d8e8 !important; }

    /* ── Auth screen motion ── */
    @keyframes fadeSlideUp { from { opacity: 0; transform: translateY(18px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes logoPulse { 0%, 100% { transform: scale(1); filter: drop-shadow(0 0 0px #4fc3f7); } 50% { transform: scale(1.08); filter: drop-shadow(0 0 12px #4fc3f7aa); } }

    .auth-logo-wrap { text-align: center; margin-bottom: 4px; }
    .auth-logo { font-size: 52px; display: inline-block; animation: logoPulse 2.6s ease-in-out infinite; }

    [data-testid="stForm"] { background: #0d1421; border: 1px solid #1e2d45; border-radius: 14px; padding: 24px 26px 8px 26px; animation: fadeSlideUp 0.5s cubic-bezier(0.22, 1, 0.36, 1); transition: border-color 0.25s ease, box-shadow 0.25s ease; }
    [data-testid="stForm"]:hover { border-color: #2a4a6a; box-shadow: 0 4px 24px rgba(79, 195, 247, 0.08); }
    [data-testid="stForm"] input:focus { transform: scale(1.01); transition: transform 0.15s ease, box-shadow 0.15s ease; }
    [data-testid="stFormSubmitButton"] button { transition: transform 0.15s ease, opacity 0.15s ease, box-shadow 0.15s ease !important; }
    [data-testid="stFormSubmitButton"] button:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(79, 195, 247, 0.25); }
    [data-testid="stFormSubmitButton"] button:active { transform: translateY(0px) scale(0.98); }
    [data-testid="stAlert"] { animation: fadeSlideUp 0.35s ease; }
    </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Login gate (sign in / sign up / recovery)
# ─────────────────────────────────────────────────────────────

def _first_run_setup():
    st.markdown('<div class="auth-logo-wrap"><span class="auth-logo">🩺</span></div>', unsafe_allow_html=True)
    st.markdown("<h2 style='text-align:center;'>Create Admin Account</h2>", unsafe_allow_html=True)
    st.info("No accounts exist yet. Create the first admin account to get started.")

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

    if auth_db.user_count() == 0:
        _first_run_setup()
        return

    mode = st.session_state["_auth_mode"]
    st.markdown('<div class="auth-logo-wrap"><span class="auth-logo">🩺</span></div>', unsafe_allow_html=True)

    if mode == "login":
        st.markdown("<h2 style='text-align:center;'>Sign in to MedAgent</h2>", unsafe_allow_html=True)
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", use_container_width=True)

        if submitted:
            with st.spinner("Checking credentials..."):
                user = auth_db.verify_credentials(username, password)
            if user:
                st.session_state.auth_user = user
                auth_db.log_action(user["username"], "login")
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
        st.markdown("## 🩺 MedAgent")
        st.caption(f"Signed in as **{st.session_state.auth_user['username']}** "
                   f"({st.session_state.auth_user['role']})")
        if st.button("🔒 Log out"):
            auth_db.log_action(st.session_state.auth_user["username"], "logout")
            st.session_state.auth_user = None
            st.session_state.messages = []
            st.rerun()

        with st.expander("🔑 My recovery code"):
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
            with st.expander("➕ Add user (admin)"):
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

            with st.expander("🔁 Regenerate a user's recovery code (admin)"):
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

            with st.expander("🔑 Reset a user's password (admin)"):
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
            st.markdown('<span class="status-pill status-online">● Ollama Online</span>', unsafe_allow_html=True)
            if ollama["models"]:
                st.caption(f"Models: {', '.join(ollama['models'][:3])}")
        else:
            st.markdown('<span class="status-pill status-offline">● Ollama Offline</span>', unsafe_allow_html=True)
            st.caption("Run `ollama serve` to start")

        st.markdown("---")
        st.markdown("### 📂 Load Data")
        uploaded = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"], label_visibility="collapsed")

        if uploaded:
            with st.spinner("Parsing sheets..."):
                df_dict = load_data(uploaded)
                st.session_state.df_dict = df_dict
                st.session_state.file_loaded = True
                st.session_state.messages = []
            st.success(f"✓ Loaded {len(df_dict)} sheets")

        if not st.session_state.file_loaded:
            if config.DEFAULT_DATA_PATH.exists():
                df_dict = load_data(config.DEFAULT_DATA_PATH)
                st.session_state.df_dict = df_dict
                st.session_state.file_loaded = True
                st.caption("↑ Using default patients.xlsx")

        st.markdown("---")

        if st.session_state.file_loaded and st.session_state.df_dict:
            stats = get_quick_stats(st.session_state.df_dict)
            st.markdown("### 📋 Sheets")
            for sheet, info in stats.items():
                with st.expander(f"{sheet} ({info['rows']} rows)"):
                    st.caption(f"**Columns:** {', '.join(info['columns'])}")

        st.markdown("---")
        if st.button("🗑 Clear Chat"):
            st.session_state.messages = []
            st.rerun()

        st.markdown("---")
        st.caption("MedAgent v2.0 · Powered by Ollama + llama3\nAll patient data is synthetic.")

    return ollama