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
import os
from datetime import datetime, timedelta, timezone
import streamlit as st
import extra_streamlit_components as stx
import streamlit as st
import streamlit.components.v1 as components
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
    if "using_custom_data" not in st.session_state:
        st.session_state.using_custom_data = False
    if "data_source_name" not in st.session_state:
        st.session_state.data_source_name = None
    if "uploader_version" not in st.session_state:
        st.session_state.uploader_version = 0
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
        --accent-hover: #244569;
        --accent-subtle: #EAF0F8;
        --danger: #B3261E;
        --danger-subtle: #FBEAE9;
        --warning: #8A5A00;
        --warning-subtle: #FBF1DE;
        --success: #1E7A34;
        --success-subtle: #E7F5EA;
        --ease: cubic-bezier(0.2, 0, 0, 1);
    }

    html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
    * { scroll-behavior: smooth; }

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
    [data-testid="stSidebar"] hr { border-color: var(--border-sidebar) !important; margin: 14px 0 !important; }

    /* Sidebar nav links */
    [data-testid="stSidebarNav"] a {
        border-radius: 6px !important;
        transition: background-color 0.15s var(--ease), padding-left 0.15s var(--ease) !important;
    }
    [data-testid="stSidebarNav"] a:hover {
        background-color: rgba(255,255,255,0.06) !important;
        padding-left: 4px !important;
    }
    [data-testid="stSidebarNav"] a[aria-current="page"] {
        background-color: rgba(255,255,255,0.09) !important;
        border-left: 2px solid var(--accent);
    }

    .sidebar-wordmark {
        font-family: 'IBM Plex Mono', monospace; font-size: 15px; font-weight: 600;
        letter-spacing: 1.5px; color: var(--text-inverse-strong); padding: 18px 0 2px 0;
    }
    .sidebar-tagline {
        font-size: 10px; letter-spacing: 0.6px; text-transform: uppercase; color: #5B6478;
        padding-bottom: 16px; border-bottom: 1px solid var(--border-sidebar); margin-bottom: 16px;
    }

    /* Page header, content area */
    .page-header {
        padding: 20px 0 16px 0; border-bottom: 1px solid var(--border); margin-bottom: 24px;
        animation: fadeInUp 0.3s var(--ease);
    }
    .page-eyebrow {
        font-family: 'IBM Plex Mono', monospace; font-size: 11px; letter-spacing: 1px;
        text-transform: uppercase; color: var(--text-secondary); margin-bottom: 4px;
    }
    .page-title { font-family: 'IBM Plex Sans', sans-serif; font-size: 24px; font-weight: 600; color: var(--text-primary); letter-spacing: -0.2px; }
    .page-sub { font-size: 13px; color: var(--text-secondary); margin-top: 2px; }

    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(6px); }
        to   { opacity: 1; transform: translateY(0); }
    }

    /* Stat cards — responsive, with hover lift */
    .stat-grid {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
        gap: 12px; margin-bottom: 24px; animation: fadeInUp 0.35s var(--ease);
    }
    .stat-card {
        background: var(--bg-surface); border: 1px solid var(--border); border-left: 3px solid var(--accent);
        border-radius: 8px; padding: 16px 18px;
        transition: transform 0.15s var(--ease), box-shadow 0.15s var(--ease), border-color 0.15s var(--ease);
    }
    .stat-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 14px rgba(16, 20, 31, 0.08);
    }
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
        letter-spacing: 0.5px; border: 1px solid; transition: opacity 0.15s var(--ease);
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

    /* Native chat message bubbles get the same treatment */
    [data-testid="stChatMessage"] {
        background: var(--bg-surface); border: 1px solid var(--border); border-radius: 8px;
        padding: 4px 8px; margin-bottom: 4px;
        animation: fadeInUp 0.25s var(--ease);
        transition: box-shadow 0.15s var(--ease);
    }
    [data-testid="stChatMessage"]:hover { box-shadow: 0 2px 10px rgba(16, 20, 31, 0.06); }

    .chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 4px 0; }
    .chip {
        background: var(--bg-surface); border: 1px solid var(--border); border-radius: 6px;
        padding: 6px 12px; font-size: 12px; color: var(--text-secondary); cursor: pointer;
        transition: border-color 0.15s var(--ease), color 0.15s var(--ease), transform 0.15s var(--ease);
    }
    .chip:hover { border-color: var(--accent); color: var(--accent); transform: translateY(-1px); }

    /* Inputs & buttons — reactive states */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stNumberInput > div > div > input {
        background: var(--bg-surface) !important; border: 1px solid var(--border) !important;
        border-radius: 6px !important; color: var(--text-primary) !important;
        font-family: 'Inter', sans-serif !important; font-size: 13.5px !important; padding: 10px 14px !important;
        transition: border-color 0.15s var(--ease), box-shadow 0.15s var(--ease), background-color 0.15s var(--ease) !important;
    }
    .stTextInput > div > div > input:hover,
    .stTextArea > div > div > textarea:hover,
    .stNumberInput > div > div > input:hover {
        border-color: #B9C0CC !important;
    }
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus,
    .stNumberInput > div > div > input:focus {
        border-color: var(--accent) !important; box-shadow: 0 0 0 3px var(--accent-subtle) !important;
    }

    .stButton > button {
        background: var(--accent) !important; border: none !important; border-radius: 6px !important;
        color: #FFFFFF !important; font-family: 'Inter', sans-serif !important; font-weight: 500 !important;
        font-size: 13.5px !important; padding: 8px 18px !important;
        transition: background-color 0.15s var(--ease), transform 0.1s var(--ease), box-shadow 0.15s var(--ease) !important;
    }
    .stButton > button:hover {
        background: var(--accent-hover) !important;
        box-shadow: 0 3px 10px rgba(44, 82, 130, 0.25) !important;
        transform: translateY(-1px);
    }
    .stButton > button:active { transform: translateY(0); box-shadow: none !important; }

    .stDataFrame { border-radius: 8px; overflow: hidden; border: 1px solid var(--border); transition: box-shadow 0.15s var(--ease); }
    .stDataFrame:hover { box-shadow: 0 2px 10px rgba(16, 20, 31, 0.05); }

    [data-testid="stFileUploader"] {
        background: var(--bg-surface) !important; border: 1px dashed var(--border) !important; border-radius: 8px !important;
        transition: border-color 0.15s var(--ease), background-color 0.15s var(--ease) !important;
    }
    [data-testid="stFileUploader"]:hover { border-color: var(--accent) !important; }

    .streamlit-expanderHeader {
        background: transparent !important; border: 1px solid var(--border-sidebar) !important;
        border-radius: 6px !important; color: var(--text-inverse) !important;
        transition: background-color 0.15s var(--ease), border-color 0.15s var(--ease) !important;
    }
    .streamlit-expanderHeader:hover {
        background: rgba(255,255,255,0.05) !important; border-color: #3A4257 !important;
    }
    .stProgress > div > div { background: var(--accent) !important; transition: width 0.2s var(--ease) !important; }

    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: var(--bg-canvas); }
    ::-webkit-scrollbar-thumb { background: #C7CCD4; border-radius: 3px; transition: background-color 0.15s var(--ease); }
    ::-webkit-scrollbar-thumb:hover { background: var(--accent); }

    .stSelectbox > div > div {
        background: var(--bg-surface) !important; border-color: var(--border) !important; color: var(--text-primary) !important;
        transition: border-color 0.15s var(--ease), box-shadow 0.15s var(--ease) !important;
    }
    .stSelectbox > div > div:hover { border-color: #B9C0CC !important; }
    .stSelectbox > div > div:focus-within { border-color: var(--accent) !important; box-shadow: 0 0 0 3px var(--accent-subtle) !important; }

    /* Chat input */
    [data-testid="stChatInput"] {
        border-radius: 8px !important; transition: box-shadow 0.15s var(--ease), border-color 0.15s var(--ease) !important;
    }
    [data-testid="stChatInput"]:focus-within {
        box-shadow: 0 0 0 3px var(--accent-subtle) !important; border-color: var(--accent) !important;
    }

    /* Tabs */
    [data-baseweb="tab-list"] { gap: 4px !important; }
    [data-baseweb="tab"] { border-radius: 6px 6px 0 0 !important; transition: background-color 0.15s var(--ease) !important; }

    /* Auth screen — quiet, no motion */
    .auth-wordmark {
        font-family: 'IBM Plex Mono', monospace; font-size: 20px; font-weight: 600;
        letter-spacing: 1px; color: var(--text-primary); text-align: center; margin-bottom: 4px;
    }
    .auth-logo-wrap { text-align: center; margin-bottom: 4px; }
    .auth-logo-mark {
        display: inline-flex; align-items: center; justify-content: center;
        width: 44px; height: 44px; border-radius: 10px;
        background: var(--accent); color: #fff;
        font-family: 'IBM Plex Mono', monospace; font-size: 17px; font-weight: 700;
        letter-spacing: 0.5px;
    }
    [data-testid="stForm"] {
        background: var(--bg-surface); border: 1px solid var(--border); border-radius: 8px;
        padding: 24px 26px 8px 26px; transition: box-shadow 0.15s var(--ease);
    }
    [data-testid="stFormSubmitButton"] button { transition: background-color 0.15s var(--ease), transform 0.1s var(--ease) !important; }
    [data-testid="stFormSubmitButton"] button:hover { transform: translateY(-1px); }
    [data-testid="stAlert"] { border-radius: 6px !important; animation: fadeInUp 0.2s var(--ease); }
    /* Skeleton loaders — used instead of bare spinners for table/profile loads */
    .skeleton-row {
        height: 16px; border-radius: 4px; margin-bottom: 10px;
        background: linear-gradient(90deg, #ECEEF1 25%, #F6F7F9 37%, #ECEEF1 63%);
        background-size: 400% 100%;
        animation: skeletonShimmer 1.4s ease infinite;
    }
    @keyframes skeletonShimmer {
        0% { background-position: 100% 50%; }
        100% { background-position: 0 50%; }
    }

    /* Empty states — calmer than a bare st.info */
    .empty-state {
        text-align: center; padding: 48px 24px; border: 1px dashed var(--border);
        border-radius: 10px; background: var(--bg-surface); animation: fadeInUp 0.3s var(--ease);
    }
    .empty-state-mark {
        width: 40px; height: 40px; border-radius: 10px; background: var(--accent-subtle);
        color: var(--accent); display: flex; align-items: center; justify-content: center;
        margin: 0 auto 14px auto; font-family: 'IBM Plex Mono', monospace; font-weight: 700; font-size: 15px;
    }
    .empty-state-title { font-size: 15px; font-weight: 600; color: var(--text-primary); margin-bottom: 6px; }
    .empty-state-desc { font-size: 13px; color: var(--text-secondary); max-width: 420px; margin: 0 auto; line-height: 1.6; }

    /* Typing indicator */
    .typing-indicator { display: flex; gap: 4px; align-items: center; padding: 6px 2px; }
    .typing-dot {
        width: 6px; height: 6px; border-radius: 50%; background: var(--text-secondary);
        animation: typingBounce 1.2s infinite ease-in-out;
    }
    .typing-dot:nth-child(2) { animation-delay: 0.15s; }
    .typing-dot:nth-child(3) { animation-delay: 0.3s; }
    @keyframes typingBounce {
        0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
        30% { transform: translateY(-4px); opacity: 1; }
    }

    /* Subtle fade on every page/rerun so nav clicks and reruns feel like a
       transition instead of a hard flash */
    .main .block-container { animation: fadeInUp 0.2s var(--ease); }

    /* Tighter, more deliberate field labels */
    .stTextInput label, .stTextArea label, .stSelectbox label, .stNumberInput label {
        font-size: 12.5px !important; font-weight: 500 !important; color: var(--text-secondary) !important;
    }
    /* Sidebar structure */
    .sidebar-section { margin: 18px 0 10px 0; }
    .sidebar-section:first-of-type { margin-top: 4px; }
    .sidebar-section-label {
        font-family: 'IBM Plex Mono', monospace; font-size: 10px; letter-spacing: 1.1px;
        text-transform: uppercase; color: #5B6478 !important; margin-bottom: 10px;
        display: flex; align-items: center; gap: 8px;
    }
    .sidebar-section-label::after { content: ""; flex: 1; height: 1px; background: var(--border-sidebar); }

    .user-chip {
        display: flex; align-items: center; gap: 10px; padding: 9px 10px;
        background: rgba(255,255,255,0.04); border: 1px solid var(--border-sidebar);
        border-radius: 8px; margin-bottom: 10px; transition: background-color 0.15s var(--ease);
    }
    .user-chip:hover { background: rgba(255,255,255,0.07); }
    .user-chip-avatar {
        width: 30px; height: 30px; border-radius: 7px; background: var(--accent);
        color: #fff !important; display: flex; align-items: center; justify-content: center;
        font-family: 'IBM Plex Mono', monospace; font-weight: 700; font-size: 13px; flex-shrink: 0;
    }
    .user-chip-info { line-height: 1.35; overflow: hidden; }
    .user-chip-name {
        font-size: 13px; font-weight: 600; color: var(--text-inverse-strong) !important;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .role-pill {
        display: inline-block; font-size: 9.5px; font-weight: 600; letter-spacing: 0.4px;
        text-transform: uppercase; padding: 1px 6px; border-radius: 4px; margin-top: 2px;
    }
    .role-pill.admin { background: rgba(138,90,0,0.28); color: #E9C46A !important; }
    .role-pill.user  { background: rgba(255,255,255,0.09); color: var(--text-inverse) !important; }

    .sidebar-status-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 4px; }

    /* Nested tabs inside the admin expander need to sit flush, not float */
    [data-testid="stSidebar"] [data-baseweb="tab-list"] { margin-bottom: 10px !important; }
    /* Sidebar-scoped alert & badge theming — the light "subtle" backgrounds
       used on the white canvas (success/warning/info boxes, status badges)
       read as jarring pale rectangles against the dark sidebar, so they get
       dark, tinted variants instead. */
    [data-testid="stSidebar"] [data-testid="stAlert"] {
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid var(--border-sidebar) !important;
        border-left: 3px solid #5B6478 !important;
        border-radius: 6px !important;
    }
    [data-testid="stSidebar"] [data-testid="stAlert"] p,
    [data-testid="stSidebar"] [data-testid="stAlert"] span {
        color: var(--text-inverse-strong) !important;
    }
    [data-testid="stSidebar"] [data-testid="stAlertContentSuccess"],
    [data-testid="stSidebar"] div:has(> [data-testid="stAlertContentSuccess"]) {
        border-left-color: #3FAE5C !important;
    }
    [data-testid="stSidebar"] [data-testid="stAlertContentError"],
    [data-testid="stSidebar"] div:has(> [data-testid="stAlertContentError"]) {
        border-left-color: #D9645C !important;
    }
    [data-testid="stSidebar"] [data-testid="stAlertContentWarning"],
    [data-testid="stSidebar"] div:has(> [data-testid="stAlertContentWarning"]) {
        border-left-color: #E0A93E !important;
    }
    [data-testid="stSidebar"] [data-testid="stAlertContentInfo"],
    [data-testid="stSidebar"] div:has(> [data-testid="stAlertContentInfo"]) {
        border-left-color: var(--accent) !important;
    }

    /* status-badge: dark, tinted background instead of the light "subtle" fill,
       only inside the sidebar — the same badge on white pages (e.g. risk tier
       on Patient Explorer) keeps its original light styling. */
    [data-testid="stSidebar"] .status-badge {
        background: rgba(255,255,255,0.06) !important;
        border-width: 1px !important;
    }
    [data-testid="stSidebar"] .status-badge.online   { border-color: rgba(63,174,92,0.5) !important;  color: #6FDB8E !important; }
    [data-testid="stSidebar"] .status-badge.offline  { border-color: rgba(217,100,92,0.5) !important; color: #F0938C !important; }
    /* File uploader dropzone — same white-on-dark mismatch as the alerts,
       scoped to the sidebar only so the uploader elsewhere (if you ever use
       one on a white page) keeps its light styling. */
    [data-testid="stSidebar"] [data-testid="stFileUploader"] {
        background: transparent !important;
        border: none !important;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
        background: rgba(255,255,255,0.04) !important;
        border: 1px dashed var(--border-sidebar) !important;
        border-radius: 8px !important;
        transition: border-color 0.15s var(--ease), background-color 0.15s var(--ease) !important;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]:hover {
        border-color: var(--accent) !important;
        background: rgba(255,255,255,0.07) !important;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] small {
        color: #8B93A6 !important;
    }
    /* "Browse files" button inside the dropzone — make it a quiet outline
       instead of inheriting the solid accent-blue .stButton style, so it
       doesn't compete visually with the real action buttons in the sidebar */
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button {
        background: transparent !important;
        border: 1px solid var(--border-sidebar) !important;
        color: var(--text-inverse) !important;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button:hover {
        border-color: var(--accent) !important;
        color: var(--text-inverse-strong) !important;
        transform: none !important;
        box-shadow: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# Reusable UX helpers: skeletons, empty states, scroll-to-bottom
# ─────────────────────────────────────────────────────────────

def render_skeleton_rows(rows=4, widths=None):
    """Shimmering placeholder rows shown while a computation is in flight.
    Use with st.empty() so it can be swapped out once real data is ready."""
    widths = widths or ["92%", "78%", "85%", "60%", "70%"]
    html_rows = "".join(
        f'<div class="skeleton-row" style="width:{widths[i % len(widths)]}"></div>'
        for i in range(rows)
    )
    st.markdown(f"<div>{html_rows}</div>", unsafe_allow_html=True)


def render_empty_state(title, description, mark="—"):
    """A calmer alternative to st.info for 'nothing here yet' screens."""
    st.markdown(f"""
    <div class="empty-state">
      <div class="empty-state-mark">{mark}</div>
      <div class="empty-state-title">{title}</div>
      <div class="empty-state-desc">{description}</div>
    </div>
    """, unsafe_allow_html=True)


def scroll_chat_to_bottom():
    """Smoothly scrolls the page to the latest message. Call after rendering
    the current chat exchange so new replies land in view automatically."""
    components.html(
        """
        <script>
        const doc = window.parent.document;
        const el = doc.scrollingElement || doc.documentElement;
        el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
        </script>
        """,
        height=0,
    )
# ─────────────────────────────────────────────────────────────
# Login gate (sign in / sign up / recovery)
# ─────────────────────────────────────────────────────────────

def _first_run_setup():
    _left, center, _right = st.columns([1, 1.4, 1])
    with center:
        st.markdown('<div class="auth-logo-wrap"><span class="auth-logo-mark">MA</span></div>',
                    unsafe_allow_html=True)
        st.markdown("<h2 style='text-align:center;'>Create Admin Account</h2>", unsafe_allow_html=True)
        st.info("No accounts exist yet. Create the first admin account to get started.")
        _first_run_setup_body()


def _first_run_setup_body():

    if st.session_state.get("_pending_recovery_code"):
        code = st.session_state["_pending_recovery_code"]
        created_username = st.session_state["_pending_recovery_username"]
        st.success(f"Admin account '{created_username}' created.")
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
            clean_username = (username or "").strip()
            lockout = auth_db.get_lockout_status(clean_username) if clean_username else None

            if lockout:
                wait_min = max(1, int((lockout - datetime.now(timezone.utc)).total_seconds() // 60) + 1)
                st.error(f"Too many failed attempts. Try again in about {wait_min} minute(s).")
            else:
                with st.spinner("Checking credentials..."):
                    user = auth_db.verify_credentials(clean_username, password)
                if user:
                    auth_db.clear_failed_logins(user["username"])
                    st.session_state.auth_user = user
                    auth_db.log_action(user["username"], "login")

                    if remember_me:
                        token = auth_db.create_remember_token(user["username"], days_valid=30)
                        config.SESSION_FILE.write_text(token, encoding="utf-8")
                        try:
                            os.chmod(config.SESSION_FILE, 0o600)
                        except OSError:
                            pass

                    st.toast(f"Welcome back, {user['username']}.")
                    st.rerun()
                else:
                    if clean_username:
                        auth_db.register_failed_login(clean_username)
                    auth_db.log_action(clean_username or "(unknown)", "login_failed")
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
            st.success(f"Account '{st.session_state['_signup_username']}' created.")
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

            if st.button("Back to sign in", use_container_width=True):
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
                    st.toast("Password reset. You can sign in now.")
                    st.session_state["_auth_mode"] = "login"
                    st.rerun()
                else:
                    auth_db.log_action(r_username.strip() or "(unknown)", "password_reset_failed")
                    st.error("Username and recovery code don't match, or this account has no "
                             "recovery code on file — ask an admin to reset your password instead.")

        if st.button("Back to sign in", use_container_width=True):
            st.session_state["_auth_mode"] = "login"
            st.rerun()

    st.stop()


# ─────────────────────────────────────────────────────────────
# Sidebar (shared across all pages)
# ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=5, show_spinner=False)
def _cached_ollama_status():
    """Streamlit reruns the whole script on every widget interaction, so without
    caching this fires a real HTTP request to Ollama on every click. A 5s TTL
    keeps the sidebar status honest while cutting that down drastically."""
    return check_ollama_status()

def _sidebar_section(label):
    st.markdown(
        f'<div class="sidebar-section"><div class="sidebar-section-label">{label}</div></div>',
        unsafe_allow_html=True,
    )
def render_sidebar():
    """Renders the full sidebar. Returns the Ollama status dict for pages that need it."""
    with st.sidebar:
        st.markdown(
            '<div class="sidebar-wordmark">MEDAGENT</div>'
            '<div class="sidebar-tagline">Clinical Data Platform · Local Instance</div>',
            unsafe_allow_html=True,
        )

        # ---------------- SESSION ----------------
        _sidebar_section("Session")
        user = st.session_state.auth_user
        initial = (user["username"][:1] or "?").upper()
        role_class = "admin" if user["role"] == "admin" else "user"
        st.markdown(f"""
        <div class="user-chip">
          <div class="user-chip-avatar">{initial}</div>
          <div class="user-chip-info">
            <div class="user-chip-name">{user['username']}</div>
            <span class="role-pill {role_class}">{user['role']}</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Log out", key="sidebar_logout_btn", use_container_width=True):
            auth_db.log_action(user["username"], "logout")
            token = get_cookie_manager().get(REMEMBER_COOKIE_NAME)
            if token:
                auth_db.revoke_remember_token(token)
                get_cookie_manager().delete(REMEMBER_COOKIE_NAME, key="delete_remember_cookie")
            st.session_state.auth_user = None
            st.session_state.messages = []
            st.session_state["_remember_check_done"] = False
            st.rerun()

        # ---------------- SYSTEM STATUS (kept near the top on purpose —
        # this is the one thing every page needs to know before you trust it) ----------------
        _sidebar_section("System Status")
        ollama = _cached_ollama_status()
        if ollama["online"]:
            st.markdown(
                '<div class="sidebar-status-row">'
                '<span class="status-badge online">OLLAMA · ONLINE</span></div>',
                unsafe_allow_html=True,
            )
            if ollama["models"]:
                st.caption(f"Models: {', '.join(ollama['models'][:3])}")
        else:
            st.markdown(
                '<div class="sidebar-status-row">'
                '<span class="status-badge offline">OLLAMA · OFFLINE</span></div>',
                unsafe_allow_html=True,
            )
            st.caption("Run `ollama serve` to start")

        # ---------------- DATASET ----------------
        _sidebar_section("Dataset")

        uploaded = st.file_uploader(
            "Upload Excel (.xlsx)", type=["xlsx"], label_visibility="collapsed",
            key=f"sidebar_file_uploader_{st.session_state.uploader_version}",
        )

        if uploaded:
            with st.spinner("Parsing sheets..."):
                df_dict = load_data(uploaded)
                st.session_state.df_dict = df_dict
                st.session_state.file_loaded = True
                st.session_state.using_custom_data = True
                st.session_state.data_source_name = uploaded.name
                st.session_state.messages = []
            st.success(f"Loaded {len(df_dict)} sheets from '{uploaded.name}'")

        if not st.session_state.file_loaded:
            if config.DEFAULT_DATA_PATH.exists():
                with st.spinner("Loading default dataset..."):
                    df_dict = load_data(config.DEFAULT_DATA_PATH)
                    st.session_state.df_dict = df_dict
                    st.session_state.file_loaded = True
                    st.session_state.data_source_name = config.DEFAULT_DATA_PATH.name

        if st.session_state.file_loaded:
            source_label = st.session_state.data_source_name or "unknown"
            if st.session_state.using_custom_data:
                st.caption(f"Using uploaded file: **{source_label}**")
                if st.button("Reset to default data", key="reset_to_default_btn", use_container_width=True):
                    st.session_state.uploader_version += 1  # remounts the uploader, clearing its selection
                    st.session_state.file_loaded = False
                    st.session_state.using_custom_data = False
                    st.session_state.df_dict = {}
                    st.session_state.data_source_name = None
                    st.session_state.messages = []
                    st.rerun()
            else:
                st.caption(f"Using default dataset: **{source_label}**")

            if st.session_state.df_dict:
                stats = get_quick_stats(st.session_state.df_dict)
                with st.expander(f"View sheets ({len(stats)})"):
                    for sheet, info in stats.items():
                        st.markdown(f"**{sheet}** · {info['rows']} rows")
                        st.caption(', '.join(info['columns']))
        else:
            st.caption("No dataset loaded yet.")

        # ---------------- SECURITY ----------------
        _sidebar_section("Security")
        with st.expander("My recovery code"):
            me = user["username"]
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

        # ---------------- ADMINISTRATION (only rendered for admins) ----------------
        if user["role"] == "admin":
            _sidebar_section("Administration")
            with st.expander("Admin tools"):
                tab_add, tab_recovery, tab_reset = st.tabs(["Add user", "Recovery codes", "Reset password"])

                with tab_add:
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
                        if st.button("Create account", key="admin_create_btn", use_container_width=True):
                            if not new_username.strip() or len(new_password) < 8:
                                st.error("Username required, password must be 8+ characters.")
                            else:
                                ok, recovery_code = auth_db.create_user(new_username.strip(), new_password, role=new_role)
                                if ok:
                                    auth_db.log_action(
                                        user["username"], "user_created",
                                        detail=f"created '{new_username}' with role '{new_role}'",
                                    )
                                    st.session_state["_admin_new_recovery_code"] = recovery_code
                                    st.session_state["_admin_new_recovery_username"] = new_username.strip()
                                    st.rerun()
                                else:
                                    st.error("That username already exists.")

                with tab_recovery:
                    existing_users_rc = [u["username"] for u in auth_db.list_users()]
                    if not existing_users_rc:
                        st.caption("No users yet.")
                    elif st.session_state.get("_admin_regen_code"):
                        st.warning(f"New code for '{st.session_state['_admin_regen_username']}' — won't be shown again:")
                        st.code(st.session_state["_admin_regen_code"], language=None)
                        if st.button("Done", key="admin_regen_ack"):
                            del st.session_state["_admin_regen_code"]
                            del st.session_state["_admin_regen_username"]
                            st.rerun()
                    else:
                        target_user_rc = st.selectbox("User", existing_users_rc, key="admin_regen_target")
                        if st.button("Generate new recovery code", key="admin_regen_btn", use_container_width=True):
                            new_code = auth_db.regenerate_recovery_code(target_user_rc)
                            auth_db.log_action(
                                user["username"], "recovery_code_regenerated",
                                detail=f"for '{target_user_rc}' (admin action)",
                            )
                            st.session_state["_admin_regen_code"] = new_code
                            st.session_state["_admin_regen_username"] = target_user_rc
                            st.rerun()

                with tab_reset:
                    existing_users = [u["username"] for u in auth_db.list_users()]
                    if not existing_users:
                        st.caption("No users yet.")
                    else:
                        target_user = st.selectbox("User", existing_users, key="admin_reset_target")
                        reset_password_val = st.text_input("New password", type="password", key="admin_reset_password")
                        if st.button("Reset password", key="admin_reset_btn", use_container_width=True):
                            if len(reset_password_val) < 8:
                                st.error("Password must be at least 8 characters.")
                            else:
                                if auth_db.admin_reset_password(target_user, reset_password_val):
                                    auth_db.log_action(
                                        user["username"], "admin_password_reset",
                                        detail=f"reset password for '{target_user}'",
                                    )
                                    st.success(f"Password reset for '{target_user}'.")
                                else:
                                    st.error("User not found.")

        # ---------------- FOOTER ----------------
        _sidebar_section("Session Controls")
        if st.button("Clear chat", key="sidebar_clear_chat_btn", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

        st.markdown(
            '<div style="margin-top:16px; padding-top:12px; border-top:1px solid var(--border-sidebar);">'
            '<span style="font-size:11px; color:#5B6478;">MedAgent · Powered by Ollama<br>All patient data is synthetic.</span>'
            '</div>',
            unsafe_allow_html=True,
        )

    return ollama