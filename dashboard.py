"""Streamlit Workspace Dashboard for Reliable Paper Mart Marketing Automation."""

from datetime import datetime
import html
from pathlib import Path
import tempfile

import streamlit as st
import streamlit.components.v1 as components

from shared.config import (
    BASE_URL,
    COMPANY_INFO,
    CREDENTIALS_FILE,
    DAILY_SEND_LIMIT,
    DAY_NAMES,
    SCHEDULE_HOUR,
    SCHEDULE_MINUTE,
    SEND_DELAY_SECONDS,
    TOKEN_FILE,
)
from shared.database import (
    add_client,
    add_or_update_stock_item,
    count_sent_today,
    get_all_clients,
    get_all_stock_items,
    get_current_week_key,
    get_in_stock_items,
    get_recent_logs,
    get_send_counts_by_recipient,
    get_summary_stats,
    import_clients_csv,
    init_db,
    seed_sample_data,
)
from task1_email_automation.email_template import render_stock_email
from task1_email_automation.scheduler import run_daily_batch, send_test_stock_email

st.set_page_config(
    page_title="Reliable Paper Mart - Marketing Workspace",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

if "nav_page" not in st.session_state:
    st.session_state["nav_page"] = "Overview"
if "ui_theme" not in st.session_state:
    st.session_state["ui_theme"] = "Light"
if "show_add_customer" not in st.session_state:
    st.session_state["show_add_customer"] = False

NAV_ITEMS = [
    ("Overview", "🏠", "Overview"),
    ("Customers", "👥", "Customers"),
    ("Inventory", "📦", "Inventory"),
    ("Email campaigns", "✉️", "Email campaigns"),
    ("AI flyer studio", "✦", "AI flyer studio"),
    ("Activity logs", "📄", "Activity logs"),
    ("Settings", "⚙️", "Settings"),
]


def _palette(is_dark: bool) -> dict[str, str]:
    if is_dark:
        return {
            "bg": "#0b1120",
            "sidebar": "#111827",
            "card": "#161f33",
            "card_subtle": "#1e293b",
            "border": "#263248",
            "text": "#f8fafc",
            "muted": "#94a3b8",
            "primary": "#4f6ef7",
            "primary_hover": "#3b5bdb",
            "nav_active_bg": "rgba(79, 110, 247, 0.18)",
            "nav_active_fg": "#818cf8",
            "green_bg": "rgba(16, 185, 129, 0.16)",
            "green_fg": "#34d399",
            "red_bg": "rgba(239, 68, 68, 0.16)",
            "red_fg": "#f87171",
            "amber_bg": "rgba(245, 158, 11, 0.16)",
            "amber_fg": "#fbbf24",
            "pill_bg": "#1e293b",
        }
    return {
        "bg": "#f6f8fc",
        "sidebar": "#ffffff",
        "card": "#ffffff",
        "card_subtle": "#f8fafc",
        "border": "#e8edf5",
        "text": "#0f172a",
        "muted": "#64748b",
        "primary": "#4361ee",
        "primary_hover": "#3651d4",
        "nav_active_bg": "#eef2ff",
        "nav_active_fg": "#4361ee",
        "green_bg": "#e6f9f0",
        "green_fg": "#0d9488",
        "red_bg": "#fee2e2",
        "red_fg": "#dc2626",
        "amber_bg": "#fef3c7",
        "amber_fg": "#d97706",
        "pill_bg": "#f1f5f9",
    }


def _inject_workspace_css(p: dict[str, str], is_dark: bool) -> None:
    st.markdown(
        f"""
        <style>
        .stApp, [data-testid="stAppViewContainer"] {{
            background-color: {p['bg']} !important;
            color: {p['text']} !important;
        }}
        [data-testid="stHeader"] {{
            background-color: transparent !important;
        }}
        .block-container {{
            padding-top: 1.6rem !important;
            padding-bottom: 2.5rem !important;
            max-width: 1280px;
        }}
        /* Sidebar styling */
        [data-testid="stSidebar"] {{
            background-color: {p['sidebar']} !important;
            border-right: 1px solid {p['border']} !important;
        }}
        [data-testid="stSidebarHeader"] {{
            padding: 0.5rem 1rem 0 1rem !important;
            height: 1.5rem !important;
            min-height: 1.5rem !important;
        }}
        [data-testid="stSidebarUserContent"] {{
            padding-top: 0.25rem !important;
        }}
        [data-testid="stSidebar"] .block-container {{
            padding-top: 0.25rem !important;
        }}
        /* Sidebar nav buttons: left-aligned with separated light-blue pill boxes */
        [data-testid="stSidebar"] div.stButton {{
            margin-bottom: 6px !important;
        }}
        [data-testid="stSidebar"] div.stButton > button {{
            width: 100%;
            display: flex !important;
            justify-content: flex-start !important;
            text-align: left !important;
            border-radius: 10px !important;
            padding: 0.58rem 0.9rem !important;
            font-weight: 500 !important;
            font-size: 0.92rem !important;
            box-shadow: none !important;
            transition: all 0.15s ease !important;
        }}
        [data-testid="stSidebar"] div.stButton > button [data-testid="stMarkdownContainer"] {{
            width: 100% !important;
            text-align: left !important;
        }}
        [data-testid="stSidebar"] div.stButton > button[kind="secondary"] {{
            background-color: {"#172236" if is_dark else "#f4f8ff"} !important;
            border: 1px solid {"#283a5c" if is_dark else "#dbeafe"} !important;
            color: {p['text']} !important;
        }}
        [data-testid="stSidebar"] div.stButton > button[kind="secondary"]:hover {{
            background-color: {"#1e2d47" if is_dark else "#e8f0fe"} !important;
            border-color: {"#3b5bdb" if is_dark else "#93c5fd"} !important;
        }}
        [data-testid="stSidebar"] div.stButton > button[kind="primary"] {{
            background-color: {"rgba(79, 110, 247, 0.24)" if is_dark else "#e0eaff"} !important;
            border: 1.5px solid {p['primary']} !important;
            color: {p['nav_active_fg']} !important;
            font-weight: 700 !important;
        }}
        /* Main buttons (including Light/Dark pill switcher & form submit buttons) */
        [data-testid="stMain"] div.stButton > button[kind="secondary"],
        [data-testid="stMain"] button[data-testid="stBaseButton-secondary"] {{
            background-color: {p['card']} !important;
            color: {p['text']} !important;
            border: 1px solid {p['border']} !important;
            border-radius: 10px !important;
            font-weight: 500 !important;
        }}
        [data-testid="stMain"] div.stButton > button[kind="secondary"]:hover,
        [data-testid="stMain"] button[data-testid="stBaseButton-secondary"]:hover {{
            background-color: {p['card_subtle']} !important;
            border-color: {p['primary']} !important;
        }}
        [data-testid="stMain"] div.stButton > button[kind="primary"],
        [data-testid="stMain"] div.stFormSubmitButton > button,
        [data-testid="stMain"] button[data-testid="stBaseButton-primary"],
        [data-testid="stMain"] button[data-testid="stBaseButton-primaryFormSubmit"] {{
            background-color: {p['primary']} !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 10px !important;
            padding: 0.55rem 1.2rem !important;
            font-weight: 600 !important;
            opacity: 1 !important;
        }}
        [data-testid="stMain"] div.stButton > button[kind="primary"] *,
        [data-testid="stMain"] div.stFormSubmitButton > button *,
        [data-testid="stMain"] button[data-testid="stBaseButton-primary"] *,
        [data-testid="stMain"] button[data-testid="stBaseButton-primaryFormSubmit"] * {{
            color: #ffffff !important;
        }}
        [data-testid="stMain"] div.stButton > button[kind="primary"]:hover,
        [data-testid="stMain"] div.stFormSubmitButton > button:hover,
        [data-testid="stMain"] button[data-testid="stBaseButton-primary"]:hover,
        [data-testid="stMain"] button[data-testid="stBaseButton-primaryFormSubmit"]:hover {{
            background-color: {p['primary_hover']} !important;
        }}
        /* Custom alert banner */
        .rpm-alert {{
            border-radius: 12px;
            padding: 12px 16px;
            margin-bottom: 14px;
            font-size: 0.9rem;
            font-weight: 500;
            border: 1px solid transparent;
        }}
        .rpm-alert-success {{
            background-color: {p['green_bg']};
            color: {p['green_fg']};
            border-color: {"rgba(52, 211, 153, 0.35)" if is_dark else "#a7f3d0"};
        }}
        .rpm-alert-error {{
            background-color: {p['red_bg']};
            color: {p['red_fg']};
            border-color: {"rgba(248, 113, 113, 0.35)" if is_dark else "#fecaca"};
        }}
        .rpm-alert-warning, .rpm-alert-info {{
            background-color: {p['amber_bg']};
            color: {p['amber_fg']};
            border-color: {"rgba(251, 191, 36, 0.35)" if is_dark else "#fde68a"};
        }}
        [data-testid="stAlert"] {{
            background-color: {p['card']} !important;
            border: 1px solid {p['border']} !important;
            border-radius: 12px !important;
            color: {p['text']} !important;
        }}
        [data-testid="stAlert"] * {{
            color: {p['text']} !important;
        }}
        /* White workspace cards */
        .rpm-card {{
            background-color: {p['card']};
            border: 1px solid {p['border']};
            border-radius: 14px;
            padding: 18px 20px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, {"0.25" if is_dark else "0.04"});
        }}
        .rpm-kpi-title {{
            font-size: 0.82rem;
            color: {p['muted']};
            font-weight: 500;
            margin-bottom: 6px;
        }}
        .rpm-kpi-value {{
            font-size: 1.85rem;
            font-weight: 700;
            color: {p['text']};
            line-height: 1.15;
            margin-bottom: 4px;
        }}
        .rpm-kpi-sub {{
            font-size: 0.76rem;
            color: {p['muted']};
        }}
        .rpm-section-title {{
            font-size: 1.05rem;
            font-weight: 700;
            color: {p['text']};
            margin: 0 0 2px 0;
        }}
        .rpm-section-sub {{
            font-size: 0.82rem;
            color: {p['muted']};
            margin: 0 0 14px 0;
        }}
        .rpm-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.88rem;
        }}
        .rpm-table th {{
            text-align: left;
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: {p['muted']};
            font-weight: 600;
            padding: 10px 12px;
            border-bottom: 1px solid {p['border']};
        }}
        .rpm-table td {{
            padding: 13px 12px;
            border-bottom: 1px solid {p['border']};
            color: {p['text']};
            vertical-align: middle;
        }}
        .rpm-table tr:last-child td {{
            border-bottom: none;
        }}
        .rpm-badge {{
            display: inline-block;
            padding: 4px 11px;
            border-radius: 999px;
            font-size: 0.76rem;
            font-weight: 600;
        }}
        .rpm-badge-green {{
            background-color: {p['green_bg']};
            color: {p['green_fg']};
        }}
        .rpm-badge-red {{
            background-color: {p['red_bg']};
            color: {p['red_fg']};
        }}
        .rpm-badge-amber {{
            background-color: {p['amber_bg']};
            color: {p['amber_fg']};
        }}
        .rpm-badge-neutral {{
            background-color: {p['pill_bg']};
            color: {p['muted']};
        }}
        .rpm-day-card {{
            background-color: {p['card']};
            border: 1px solid {p['border']};
            border-radius: 12px;
            padding: 14px 14px;
            text-align: center;
        }}
        .rpm-day-pill {{
            display: inline-block;
            background-color: {p['nav_active_bg']};
            color: {p['nav_active_fg']};
            font-size: 0.74rem;
            font-weight: 600;
            padding: 2px 10px;
            border-radius: 999px;
            margin-bottom: 6px;
        }}
        .rpm-day-num {{
            font-size: 1.5rem;
            font-weight: 700;
            color: {p['text']};
        }}
        .rpm-day-sub {{
            font-size: 0.72rem;
            color: {p['muted']};
        }}
        /* Clean inputs, selects, popovers, radios & forms */
        [data-testid="stForm"],
        [data-testid="stExpander"],
        [data-testid="stVerticalBlockBorderWrapper"] {{
            background-color: {p['card']} !important;
            border: 1px solid {p['border']} !important;
            border-radius: 14px !important;
        }}
        [data-baseweb="input"],
        [data-baseweb="base-input"],
        [data-baseweb="select"] > div {{
            background-color: {p['card_subtle']} !important;
            color: {p['text']} !important;
            border: 1px solid {p['border']} !important;
            border-radius: 10px !important;
        }}
        [data-baseweb="input"] input,
        [data-baseweb="base-input"] input,
        [data-baseweb="select"] span,
        [data-baseweb="select"] svg {{
            background-color: transparent !important;
            color: {p['text']} !important;
            fill: {p['muted']} !important;
        }}
        [data-baseweb="popover"],
        [data-baseweb="menu"],
        [role="listbox"] {{
            background-color: {p['card']} !important;
            border: 1px solid {p['border']} !important;
            color: {p['text']} !important;
        }}
        [role="option"] {{
            background-color: {p['card']} !important;
            color: {p['text']} !important;
        }}
        [role="option"]:hover {{
            background-color: {p['nav_active_bg']} !important;
        }}
        [data-testid="stNumberInput"] button {{
            background-color: {p['card_subtle']} !important;
            color: {p['text']} !important;
            border-color: {p['border']} !important;
        }}
        [data-testid="stRadio"] [role="radiogroup"] label > div:first-child {{
            background-color: {p['card']} !important;
            border: 2px solid {p['muted']} !important;
        }}
        [data-testid="stRadio"] [role="radiogroup"] label[data-checked="true"] > div:first-child {{
            border-color: {p['primary']} !important;
        }}
        [data-testid="stFileUploaderDropzone"] {{
            background-color: {p['card_subtle']} !important;
            border: 1px dashed {p['border']} !important;
            color: {p['text']} !important;
        }}
        [data-testid="stFileUploaderDropzone"] button {{
            background-color: {p['card']} !important;
            color: {p['text']} !important;
            border: 1px solid {p['border']} !important;
        }}
        [data-testid="stStatusWidget"],
        [data-testid="stToast"] {{
            background-color: {p['card']} !important;
            border: 1px solid {p['border']} !important;
            border-radius: 12px !important;
            color: {p['text']} !important;
        }}
        p, label, span, h1, h2, h3, h4 {{
            color: {p['text']};
        }}
        .stCaption, [data-testid="stCaptionContainer"] p {{
            color: {p['muted']} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _alert_box(kind: str, message: str) -> None:
    """Render a theme-safe, high-contrast status banner."""
    css_cls = f"rpm-alert-{kind if kind in ('success', 'error', 'warning', 'info') else 'info'}"
    st.markdown(
        f'<div class="rpm-alert {css_cls}">{html.escape(message)}</div>',
        unsafe_allow_html=True,
    )


def _kpi_card(title: str, value: str | int, sub: str) -> str:
    return (
        f'<div class="rpm-card">'
        f'<div class="rpm-kpi-title">{html.escape(title)}</div>'
        f'<div class="rpm-kpi-value">{html.escape(str(value))}</div>'
        f'<div class="rpm-kpi-sub">{html.escape(sub)}</div>'
        f"</div>"
    )


def _preview_with_theme(html_body: str, preview_theme: str) -> str:
    if preview_theme == "Dark":
        forced_dark = """
        <style>
          body, .email-bg { background-color: #0f172a !important; color: #e2e8f0 !important; }
          .email-card { background-color: #1e293b !important; border-color: #334155 !important; }
          .email-text { color: #e2e8f0 !important; }
          .email-muted { color: #94a3b8 !important; }
          .email-thead { background-color: #0f172a !important; border-bottom-color: #475569 !important; }
          .email-th { color: #f1f5f9 !important; }
          .email-row { border-bottom-color: #334155 !important; }
          .email-row-even { background-color: #162032 !important; }
          .email-cta { background-color: #0f172a !important; border-left-color: #38bdf8 !important; }
          .email-cta-title { color: #38bdf8 !important; }
          .email-footer { background-color: #0f172a !important; border-top-color: #334155 !important; }
          .email-link { color: #38bdf8 !important; }
        </style>
        """
        return html_body.replace("</head>", f"{forced_dark}</head>")
    forced_light = """
    <style>
      body, .email-bg { background-color: #f4f6f9 !important; color: #222222 !important; }
      .email-card { background-color: #ffffff !important; border-color: #e2e8f0 !important; }
      .email-text { color: #0f172a !important; }
      .email-muted { color: #334155 !important; }
      .email-thead { background-color: #f1f5f9 !important; border-bottom-color: #cbd5e1 !important; }
      .email-th { color: #1e293b !important; }
      .email-row { border-bottom-color: #e2e8f0 !important; }
      .email-row-even { background-color: #f8fafc !important; }
      .email-cta { background-color: #f8fafc !important; border-left-color: #1e3a5f !important; }
      .email-cta-title { color: #1e3a5f !important; }
      .email-footer { background-color: #f1f5f9 !important; border-top-color: #e2e8f0 !important; }
      .email-link { color: #1e3a5f !important; }
    </style>
    """
    return html_body.replace("</head>", f"{forced_light}</head>")


# Apply active palette
is_dark = st.session_state["ui_theme"] == "Dark"
pal = _palette(is_dark)
_inject_workspace_css(pal, is_dark)

# ------------------------------------------------------------------
# SIDEBAR (Brand Mark + Vertical Nav + Bottom Operational Card)
# ------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:12px; padding:0 2px 16px 2px; margin-top:-6px;">
          <div style="width:42px; height:42px; border-radius:11px; background:{pal['primary']};
                      color:#ffffff; display:flex; align-items:center; justify-content:center;
                      font-weight:800; font-size:20px; flex-shrink:0;">R</div>
          <div>
            <div style="font-weight:800; font-size:1.15rem; color:{pal['text']}; line-height:1.15;">
              Reliable Paper Mart
            </div>
            <div style="font-size:0.68rem; letter-spacing:0.08em; color:{pal['muted']}; font-weight:600; margin-top:2px;">
              MARKETING WORKSPACE
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for key, icon, label in NAV_ITEMS:
        btn_type = "primary" if st.session_state["nav_page"] == key else "secondary"
        if st.button(f"{icon}  {label}", key=f"nav_{key}", type=btn_type, use_container_width=True):
            st.session_state["nav_page"] = key
            st.rerun()

    st.markdown("<div style='height: 36px;'></div>", unsafe_allow_html=True)
    sync_time = datetime.now().strftime("%I:%M %p")
    sent_today = count_sent_today()
    st.markdown(
        f"""
        <div style="background:{pal['card']}; border:1px solid {pal['border']}; border-radius:12px;
                    padding:12px 14px; margin-top:auto;">
          <div style="display:flex; align-items:center; gap:8px; font-weight:600; font-size:0.83rem; color:{pal['text']};">
            <span style="width:8px; height:8px; border-radius:50%; background:#10b981; display:inline-block;"></span>
            System operational
          </div>
          <div style="font-size:0.74rem; color:{pal['muted']}; margin-top:4px;">
            Week {get_current_week_key()} &bull; {sent_today}/{DAILY_SEND_LIMIT} sent &bull; {sync_time}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------------
# TOP HEADER BAR (Page Title + Breadcrumb + Theme Pill)
# ------------------------------------------------------------------
current_page = st.session_state["nav_page"]
stats = get_summary_stats()

hdr_left, hdr_right = st.columns([5, 2.0])
with hdr_left:
    st.markdown(
        f"""
        <div style="margin-bottom: 14px;">
          <h1 style="margin:0; font-size:1.75rem; font-weight:700; color:{pal['text']};">{html.escape(current_page)}</h1>
          <div style="font-size:0.82rem; color:{pal['muted']}; margin-top:2px;">
            Reliable Paper Mart &nbsp;/&nbsp; Marketing workspace
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with hdr_right:
    t_col1, t_col2 = st.columns(2)
    with t_col1:
        if st.button(
            "☀️ Light",
            key="theme_btn_light",
            type="primary" if not is_dark else "secondary",
            use_container_width=True,
        ):
            st.session_state["ui_theme"] = "Light"
            st.rerun()
    with t_col2:
        if st.button(
            "🌙 Dark",
            key="theme_btn_dark",
            type="primary" if is_dark else "secondary",
            use_container_width=True,
        ):
            st.session_state["ui_theme"] = "Dark"
            st.rerun()

# Show persisted action feedback + toast notification after st.rerun()
if "send_feedback" in st.session_state:
    kind, payload = st.session_state.pop("send_feedback")
    if kind in ("success", "error", "warning", "info"):
        _alert_box(kind, str(payload))
        if kind == "success":
            st.toast(str(payload), icon="✅")
        elif kind == "error":
            st.toast(str(payload), icon="⚠️")
    elif kind == "batch":
        summary_msg = (
            f"Batch status: {payload.get('status')} | Day: {payload.get('day', '-')} | "
            f"Week: {payload.get('week_key', '-')} | Sent: {payload.get('sent', 0)} | Failed: {payload.get('failed', 0)}"
        )
        _alert_box("success" if payload.get("failed", 0) == 0 else "warning", summary_msg)
        st.toast(f"Batch complete: {payload.get('sent', 0)} sent", icon="📨")

# ==================================================================
# PAGE 1: OVERVIEW
# ==================================================================
if current_page == "Overview":
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(_kpi_card("Total customers", stats["total_clients"], f"{stats['active_clients']} subscribed"), unsafe_allow_html=True)
    with k2:
        st.markdown(_kpi_card("Emails sent", stats["emails_sent"], f"Batch: {stats['batch_sent']} • Test: {stats['test_sent']}"), unsafe_allow_html=True)
    with k3:
        st.markdown(_kpi_card("In-stock items", stats["in_stock_items"], "Live from inventory DB"), unsafe_allow_html=True)
    with k4:
        st.markdown(_kpi_card("Unsubscribed", stats["unsubscribed_clients"], "Automatically skipped"), unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    st.markdown(
        f'<div class="rpm-card" style="margin-bottom:14px;">'
        f'<div class="rpm-section-title">Weekly Mon–Sat dispatch spread</div>'
        f'<div class="rpm-section-sub">Active clients balanced across Monday to Saturday to stay within Gmail limits ({DAILY_SEND_LIMIT}/day)</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    clients = get_all_clients()
    active_by_day = {d: 0 for d in range(6)}
    total_by_day = {d: 0 for d in range(6)}
    for c in clients:
        total_by_day[c["assigned_day"]] += 1
        if not c["is_unsubscribed"]:
            active_by_day[c["assigned_day"]] += 1

    day_cols = st.columns(6)
    for d in range(6):
        unsub_cnt = total_by_day[d] - active_by_day[d]
        sub_txt = f"{unsub_cnt} unsubscribed" if unsub_cnt else "All active"
        day_cols[d].markdown(
            f'<div class="rpm-day-card">'
            f'<div class="rpm-day-pill">{DAY_NAMES[d][:3]}</div>'
            f'<div class="rpm-day-num">{active_by_day[d]}</div>'
            f'<div class="rpm-day-sub">{sub_txt}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)
    c_left, c_right = st.columns(2)
    with c_left:
        st.markdown(
            f'<div class="rpm-card"><div class="rpm-section-title">Recent activity</div>'
            f'<div class="rpm-section-sub">Latest email deliveries and tests</div></div>',
            unsafe_allow_html=True,
        )
        recent = get_recent_logs(limit=6)
        if not recent:
            _alert_box("info", "No emails sent yet. Open Email campaigns to send a test or run a batch.")
        else:
            rows_html = ""
            for r in recent:
                badge = (
                    '<span class="rpm-badge rpm-badge-green">Completed</span>'
                    if r["status"] == "SENT"
                    else '<span class="rpm-badge rpm-badge-red">Failed</span>'
                )
                rows_html += (
                    f"<tr>"
                    f"<td><strong>{html.escape(r['send_type'])}</strong></td>"
                    f"<td>{html.escape(r['client_email'])}</td>"
                    f"<td style='color:{pal['muted']};'>{html.escape(r['sent_at'])}</td>"
                    f"<td>{badge}</td>"
                    f"</tr>"
                )
            st.markdown(
                f'<div class="rpm-card" style="margin-top:8px; padding:6px 14px;">'
                f'<table class="rpm-table"><thead><tr><th>Type</th><th>Recipient</th><th>Time</th><th>Result</th></tr></thead>'
                f"<tbody>{rows_html}</tbody></table></div>",
                unsafe_allow_html=True,
            )

    with c_right:
        st.markdown(
            f'<div class="rpm-card"><div class="rpm-section-title">Active stock snapshot</div>'
            f'<div class="rpm-section-sub">Included automatically in weekly emails</div></div>',
            unsafe_allow_html=True,
        )
        in_stock = get_in_stock_items()[:6]
        if in_stock:
            stock_rows = ""
            for item in in_stock:
                stock_rows += (
                    f"<tr>"
                    f"<td><strong>{html.escape(item['item_name'])}</strong></td>"
                    f"<td style='color:{pal['muted']};'>{html.escape(item['unit'])}</td>"
                    f"<td>&#8377;{item['price']:.2f}</td>"
                    f"<td><span class='rpm-badge rpm-badge-green'>{item['quantity']} avail</span></td>"
                    f"</tr>"
                )
            st.markdown(
                f'<div class="rpm-card" style="margin-top:8px; padding:6px 14px;">'
                f'<table class="rpm-table"><thead><tr><th>Item</th><th>Unit</th><th>Rate</th><th>Stock</th></tr></thead>'
                f"<tbody>{stock_rows}</tbody></table></div>",
                unsafe_allow_html=True,
            )

# ==================================================================
# PAGE 2: CUSTOMERS
# ==================================================================
elif current_page == "Customers":
    clients = get_all_clients()
    active_by_day = {d: 0 for d in range(6)}
    for c in clients:
        if not c["is_unsubscribed"]:
            active_by_day[c["assigned_day"]] += 1

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(_kpi_card("Total customers", stats["total_clients"], "Registered in workspace"), unsafe_allow_html=True)
    with k2:
        st.markdown(_kpi_card("Subscribed", stats["active_clients"], "Eligible for weekly email"), unsafe_allow_html=True)
    with k3:
        st.markdown(_kpi_card("Unsubscribed", stats["unsubscribed_clients"], "Suppressed from campaigns"), unsafe_allow_html=True)
    with k4:
        today_idx = datetime.now().weekday()
        today_cnt = active_by_day.get(today_idx, 0)
        today_lbl = DAY_NAMES[today_idx]
        st.markdown(_kpi_card("Due today", today_cnt, f"Scheduled for {today_lbl}"), unsafe_allow_html=True)

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
    day_cols = st.columns(6)
    for d in range(6):
        day_cols[d].markdown(
            f'<div class="rpm-day-card">'
            f'<div class="rpm-day-pill">{DAY_NAMES[d]}</div>'
            f'<div class="rpm-day-num">{active_by_day[d]}</div>'
            f'<div class="rpm-day-sub">active clients</div>'
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    dir_hdr_l, dir_hdr_r = st.columns([4, 1.3])
    with dir_hdr_l:
        st.markdown(
            f'<div class="rpm-section-title">Customer directory</div>'
            f'<div class="rpm-section-sub">Manage contacts, delivery days, and subscription preferences</div>',
            unsafe_allow_html=True,
        )
    with dir_hdr_r:
        if st.button("+ Add customer", type="primary", use_container_width=True):
            st.session_state["show_add_customer"] = not st.session_state["show_add_customer"]

    if st.session_state["show_add_customer"]:
        a_col1, a_col2 = st.columns(2)
        with a_col1:
            with st.form("add_client_form"):
                st.markdown("**Add single customer**")
                c_name = st.text_input("Customer / Company Name")
                c_email = st.text_input("Email Address")
                c_day_choice = st.selectbox(
                    "Send Day",
                    options=["Auto-Balance (Recommended)"] + [DAY_NAMES[d] for d in range(6)],
                )
                if st.form_submit_button("Save customer", type="primary"):
                    if not c_name.strip() or not c_email.strip():
                        _alert_box("warning", "Both name and email are required.")
                    else:
                        try:
                            with st.spinner("Adding customer & balancing Mon–Sat schedule..."):
                                day_val = (
                                    None
                                    if c_day_choice.startswith("Auto")
                                    else [DAY_NAMES[d] for d in range(6)].index(c_day_choice)
                                )
                                created = add_client(c_name, c_email, assigned_day=day_val)
                            st.session_state["show_add_customer"] = False
                            st.session_state["send_feedback"] = (
                                "success",
                                f"Added {created['name']} ({DAY_NAMES[created['assigned_day']]})",
                            )
                            st.rerun()
                        except Exception as exc:
                            _alert_box("error", f"Could not add customer: {exc}")
        with a_col2:
            with st.container(border=True):
                st.markdown("**Bulk import customers (CSV)**")
                uploaded_csv = st.file_uploader(
                    "CSV columns: name, email, optional assigned_day", type=["csv"]
                )
                if uploaded_csv is not None and st.button("Import CSV", type="primary"):
                    with st.status("Importing customers from CSV...", expanded=True) as status:
                        st.write("📄 Reading CSV & balancing delivery days (Mon–Sat)...")
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                            tmp.write(uploaded_csv.getvalue())
                            tmp_path = Path(tmp.name)
                        try:
                            res = import_clients_csv(tmp_path)
                            status.update(label="✅ CSV import complete!", state="complete")
                            st.session_state["send_feedback"] = (
                                "success",
                                f"Imported CSV — Added: {res['added']}, Skipped: {res['skipped']}",
                            )
                            st.rerun()
                        finally:
                            tmp_path.unlink(missing_ok=True)
                if st.button("Seed sample data (if empty)"):
                    with st.spinner("Seeding sample stock & customers..."):
                        res = seed_sample_data()
                    st.session_state["send_feedback"] = ("success", f"Seeded: {res}")
                    st.rerun()

    # Filters row matching Screenshot 3
    f1, f2, f3 = st.columns([2.5, 1.2, 1.2])
    search_q = f1.text_input("Search", placeholder="Search name or email...", label_visibility="collapsed")
    day_filter = f2.selectbox(
        "Day Filter",
        options=["All delivery days"] + [DAY_NAMES[d] for d in range(6)],
        label_visibility="collapsed",
    )
    status_filter = f3.selectbox(
        "Status Filter",
        options=["All status", "Subscribed", "Unsubscribed"],
        label_visibility="collapsed",
    )

    filtered_clients = []
    for c in clients:
        if search_q and search_q.lower() not in c["name"].lower() and search_q.lower() not in c["email"].lower():
            continue
        if day_filter != "All delivery days" and DAY_NAMES[c["assigned_day"]] != day_filter:
            continue
        if status_filter == "Subscribed" and c["is_unsubscribed"]:
            continue
        if status_filter == "Unsubscribed" and not c["is_unsubscribed"]:
            continue
        filtered_clients.append(c)

    if not filtered_clients:
        _alert_box("info", "No matching customers found.")
    else:
        rows_html = ""
        for c in filtered_clients:
            badge = (
                '<span class="rpm-badge rpm-badge-red">Unsubscribed</span>'
                if c["is_unsubscribed"]
                else '<span class="rpm-badge rpm-badge-green">Subscribed</span>'
            )
            unsub_note = (
                f"<span style='font-size:0.75rem; color:{pal['muted']};'>{html.escape(c['unsubscribed_at'])}</span>"
                if c["unsubscribed_at"]
                else f"<span style='color:{pal['muted']};'>—</span>"
            )
            rows_html += (
                f"<tr>"
                f"<td><strong>{html.escape(c['name'])}</strong></td>"
                f"<td style='color:{pal['muted']};'>{html.escape(c['email'])}</td>"
                f"<td>{DAY_NAMES[c['assigned_day']]}</td>"
                f"<td>{badge}</td>"
                f"<td>{unsub_note}</td>"
                f"</tr>"
            )
        st.markdown(
            f'<div class="rpm-card" style="padding:8px 16px;">'
            f'<table class="rpm-table">'
            f"<thead><tr><th>Customer</th><th>Email Address</th><th>Send Day</th><th>Subscription</th><th>Unsubscribed At</th></tr></thead>"
            f"<tbody>{rows_html}</tbody></table></div>",
            unsafe_allow_html=True,
        )

# ==================================================================
# PAGE 3: INVENTORY
# ==================================================================
elif current_page == "Inventory":
    all_stock = get_all_stock_items()
    in_stock_now = get_in_stock_items()

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(_kpi_card("Total SKUs", len(all_stock), "Tracked in database"), unsafe_allow_html=True)
    with k2:
        st.markdown(_kpi_card("In stock", len(in_stock_now), "Included in emails"), unsafe_allow_html=True)
    with k3:
        st.markdown(_kpi_card("Out of stock", len(all_stock) - len(in_stock_now), "Excluded automatically"), unsafe_allow_html=True)
    with k4:
        total_units = sum(s["quantity"] for s in in_stock_now)
        st.markdown(_kpi_card("Total units", f"{total_units:,}", "Available across SKUs"), unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    inv_left, inv_right = st.columns([3, 2])

    with inv_left:
        st.markdown(
            f'<div class="rpm-section-title">Paper inventory</div>'
            f'<div class="rpm-section-sub">Updating stock here immediately updates weekly stock emails</div>',
            unsafe_allow_html=True,
        )
        rows_html = ""
        for s in all_stock:
            avail = s["in_stock"] and s["quantity"] > 0
            badge = (
                '<span class="rpm-badge rpm-badge-green">In stock</span>'
                if avail
                else '<span class="rpm-badge rpm-badge-red">Out of stock</span>'
            )
            rows_html += (
                f"<tr>"
                f"<td><strong>{html.escape(s['item_name'])}</strong><br>"
                f"<span style='font-size:0.75rem; color:{pal['muted']};'>{html.escape(s['category'])} &bull; {html.escape(s['unit'])}</span></td>"
                f"<td>&#8377;{s['price']:.2f}</td>"
                f"<td>{s['quantity']}</td>"
                f"<td>{badge}</td>"
                f"</tr>"
            )
        st.markdown(
            f'<div class="rpm-card" style="padding:8px 16px;">'
            f'<table class="rpm-table"><thead><tr><th>Item</th><th>Rate (INR)</th><th>Qty</th><th>Status</th></tr></thead>'
            f"<tbody>{rows_html}</tbody></table></div>",
            unsafe_allow_html=True,
        )

    with inv_right:
        st.markdown(
            f'<div class="rpm-section-title">Add / update item</div>'
            f'<div class="rpm-section-sub">Select an existing SKU or create a new one</div>',
            unsafe_allow_html=True,
        )
        stock_options = {"New Item": None}
        for s in all_stock:
            stock_options[f"#{s['id']} - {s['item_name']}"] = s
        selected_label = st.selectbox("Select SKU", list(stock_options.keys()), label_visibility="collapsed")
        selected_item = stock_options[selected_label]

        with st.form("stock_item_form"):
            item_name = st.text_input("Item Name", value=selected_item["item_name"] if selected_item else "")
            category = st.text_input("Category", value=selected_item["category"] if selected_item else "Office Paper")
            unit = st.text_input("Spec / Unit", value=selected_item["unit"] if selected_item else "500 Sheets / Ream")
            price = st.number_input("Rate (INR)", min_value=0.0, step=10.0, value=float(selected_item["price"]) if selected_item else 250.0)
            quantity = st.number_input("Quantity", min_value=0, step=10, value=int(selected_item["quantity"]) if selected_item else 100)
            in_stock_flag = st.checkbox("In Stock", value=bool(selected_item["in_stock"]) if selected_item else True)
            if st.form_submit_button("Save stock item", type="primary", use_container_width=True):
                if not item_name.strip():
                    _alert_box("warning", "Item Name is required.")
                else:
                    with st.spinner("Saving stock item & refreshing email template..."):
                        add_or_update_stock_item(
                            item_name=item_name,
                            category=category,
                            unit=unit,
                            price=price,
                            quantity=quantity,
                            in_stock=in_stock_flag,
                            item_id=selected_item["id"] if selected_item else None,
                        )
                    st.session_state["send_feedback"] = ("success", "Stock item saved! Email template updated.")
                    st.rerun()

# ==================================================================
# PAGE 4: EMAIL CAMPAIGNS
# ==================================================================
elif current_page == "Email campaigns":
    left, right = st.columns(2)

    with left:
        with st.form("test_email_form"):
            st.markdown(
                f'<div class="rpm-section-title">Send test stock email</div>'
                f'<div class="rpm-section-sub">Sends live stock HTML via Gmail API, logs as TEST, and blocks unsubscribed addresses</div>',
                unsafe_allow_html=True,
            )
            test_recipient = st.text_input("Recipient Email", placeholder="buyer@example.com")
            if st.form_submit_button("Send test email", type="primary", use_container_width=True):
                recipient_clean = test_recipient.strip().lower()
                if not recipient_clean:
                    _alert_box("warning", "Please enter a valid recipient email.")
                else:
                    with st.status(f"Sending test email to {recipient_clean}...", expanded=True) as status:
                        st.write("🔍 Checking subscription status & fetching live inventory...")
                        st.write("📨 Connecting to Gmail API & rendering stock email...")
                        result = send_test_stock_email(recipient_clean)
                        if result["status"] == "blocked_unsubscribed":
                            status.update(label="🚫 Blocked — client unsubscribed", state="error")
                            _alert_box(
                                "error",
                                f"Blocked: {recipient_clean} has unsubscribed ({result.get('unsubscribed_at') or 'unsubscribed'}) "
                                "and will NOT be sent any emails.",
                            )
                        elif result["status"] == "no_stock":
                            status.update(label="⚠️ No stock available", state="error")
                            _alert_box("error", "No items currently in stock.")
                        elif result["status"] == "sent":
                            status.update(label="✅ Test email sent!", state="complete")
                            st.session_state["send_feedback"] = (
                                "success",
                                f"Test email sent to {recipient_clean}! Message ID: {result['message_id']}",
                            )
                            st.rerun()
                        else:
                            status.update(label="❌ Send failed", state="error")
                            st.session_state["send_feedback"] = (
                                "error",
                                f"Failed to send test email: {result.get('error')}",
                            )
                            st.rerun()

    with right:
        with st.container(border=True):
            st.markdown(
                f'<div class="rpm-section-title">Run daily Mon–Sat batch</div>'
                f'<div class="rpm-section-sub">Dispatches once-per-week stock emails, skipping unsubscribed and already-sent clients</div>',
                unsafe_allow_html=True,
            )
            today_idx = min(datetime.now().weekday(), 5)
            selected_day = st.selectbox(
                "Target Day Batch",
                options=list(range(6)),
                index=today_idx,
                format_func=lambda d: DAY_NAMES[d],
            )
            batch_mode = st.radio(
                "Execution Mode",
                options=["Preview Only (Dry Run)", "Send Real Emails"],
                index=0,
                horizontal=True,
            )
            dry_run = batch_mode.startswith("Preview")
            if st.button("Run batch now", type="primary", use_container_width=True):
                day_label = DAY_NAMES[selected_day]
                action_label = (
                    f"Previewing {day_label} batch (Dry Run)..."
                    if dry_run
                    else f"Sending {day_label} weekly stock batch..."
                )
                with st.status(action_label, expanded=True) as status:
                    st.write("📦 Checking in-stock items & weekly deduplication...")
                    if not dry_run:
                        st.write("✉️ Sending emails via Gmail API (with rate-limit pacing)...")
                    result = run_daily_batch(day_override=selected_day, dry_run=dry_run)
                    if not dry_run:
                        status.update(label=f"✅ {day_label} batch finished!", state="complete")
                        st.session_state["send_feedback"] = ("batch", result)
                        st.rerun()
                    else:
                        status.update(label=f"✅ {day_label} dry-run preview ready", state="complete")
                        _alert_box(
                            "info",
                            f"[Dry Run] Status: {result.get('status')} | Day: {result.get('day', '-')} | "
                            f"Would send: {result.get('sent', 0)}",
                        )

    st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)
    st.markdown(
        f'<div class="rpm-section-title">Live email preview</div>'
        f'<div class="rpm-section-sub">Rendered directly from active inventory in SQLite</div>',
        unsafe_allow_html=True,
    )
    preview_theme = st.radio(
        "Email Preview Mode",
        options=["Light", "Dark"],
        index=1 if is_dark else 0,
        horizontal=True,
    )
    in_stock_now = get_in_stock_items()
    if in_stock_now:
        preview_html, _ = render_stock_email(
            client_name="Sample Client",
            stock_items=in_stock_now,
            unsubscribe_url=f"{BASE_URL.rstrip('/')}/unsubscribe/preview-token",
        )
        components.html(_preview_with_theme(preview_html, preview_theme), height=580, scrolling=True)

# ==================================================================
# PAGE 5: AI FLYER STUDIO (TASK 2 PLACEHOLDER)
# ==================================================================
elif current_page == "AI flyer studio":
    f_left, f_right = st.columns(2)
    with f_left:
        st.markdown(
            f"""
            <div class="rpm-card">
              <div class="rpm-section-title">Create a weekly promotional flyer</div>
              <div class="rpm-section-sub">Task 2 will generate AI headlines & accurate stock flyers from inventory.</div>
              <div style="margin-top:14px; padding:14px; border-radius:10px; background:{pal['card_subtle']}; border:1px solid {pal['border']};">
                <span class="rpm-badge rpm-badge-amber">Task 2 Pending</span>
                <p style="margin:8px 0 0 0; font-size:0.86rem; color:{pal['muted']};">
                  Ready to build next in <code>task2_ai_flyer/</code>: AI marketing copy, template flyer rendering into
                  <code>generated_flyers/</code>, and compliant WhatsApp &amp; Facebook distribution.
                </p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with f_right:
        in_stock_sample = get_in_stock_items()[:3]
        items_html = "".join(
            f'<div style="background:{pal["card_subtle"]}; border:1px solid {pal["border"]}; border-radius:10px; padding:10px 14px; margin-bottom:8px;">'
            f'<div style="font-weight:600; font-size:0.88rem; color:{pal["text"]};">{html.escape(i["item_name"])}</div>'
            f'<div style="font-size:0.78rem; color:{pal["primary"]}; font-weight:600;">&#8377;{i["price"]:.2f} &bull; {html.escape(i["unit"])}</div>'
            f"</div>"
            for i in in_stock_sample
        )
        st.markdown(
            f"""
            <div class="rpm-card">
              <div class="rpm-section-title">Live flyer preview</div>
              <div class="rpm-section-sub">Sample live inventory items ready for Task 2 flyer generation</div>
              <div style="background:#1e3a5f; color:#ffffff; padding:18px; border-radius:12px 12px 0 0; margin-top:10px;">
                <div style="font-size:0.7rem; letter-spacing:0.08em; opacity:0.85;">RELIABLE PAPER MART</div>
                <div style="font-size:1.25rem; font-weight:700; margin-top:4px;">Stock up. Stay ready.</div>
              </div>
              <div style="border:1px solid {pal['border']}; border-top:none; border-radius:0 0 12px 12px; padding:14px;">
                {items_html}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ==================================================================
# PAGE 6: ACTIVITY LOGS
# ==================================================================
elif current_page == "Activity logs":
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(_kpi_card("Emails sent", stats["emails_sent"], "Total successful sends"), unsafe_allow_html=True)
    with k2:
        st.markdown(_kpi_card("Weekly batch", stats["batch_sent"], "Mon–Sat campaign sends"), unsafe_allow_html=True)
    with k3:
        st.markdown(_kpi_card("Test sends", stats["test_sent"], "Preview & QA sends"), unsafe_allow_html=True)
    with k4:
        st.markdown(_kpi_card("Failed", stats["emails_failed"], "Review error details"), unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    st.markdown(
        f'<div class="rpm-section-title">Send count per recipient</div>'
        f'<div class="rpm-section-sub">Total number of emails sent to each address across batch and test runs</div>',
        unsafe_allow_html=True,
    )
    recipient_counts = get_send_counts_by_recipient()
    if not recipient_counts:
        _alert_box("info", "No emails logged yet.")
    else:
        cnt_rows = ""
        for r in recipient_counts:
            cnt_rows += (
                f"<tr>"
                f"<td><strong>{html.escape(r['client_name'])}</strong></td>"
                f"<td style='color:{pal['muted']};'>{html.escape(r['client_email'])}</td>"
                f"<td><span class='rpm-badge rpm-badge-green'>{r['total_sent']} sent</span></td>"
                f"<td>{r['batch_sent']}</td>"
                f"<td>{r['test_sent']}</td>"
                f"<td>{r['total_failed']}</td>"
                f"<td style='color:{pal['muted']};'>{html.escape(r['last_sent_at'] or '-')}</td>"
                f"</tr>"
            )
        st.markdown(
            f'<div class="rpm-card" style="padding:8px 16px; margin-bottom:18px;">'
            f'<table class="rpm-table">'
            f"<thead><tr><th>Recipient</th><th>Email</th><th>Total Sent</th><th>Batch</th><th>Test</th><th>Failed</th><th>Last Sent</th></tr></thead>"
            f"<tbody>{cnt_rows}</tbody></table></div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div class="rpm-section-title">Activity history</div>'
        f'<div class="rpm-section-sub">A traceable record of all email deliveries and test runs</div>',
        unsafe_allow_html=True,
    )
    logs = get_recent_logs(limit=200)
    if logs:
        l1, l2, l3 = st.columns([2.4, 1.1, 1.1])
        log_search = l1.text_input("Search logs", placeholder="Search email or message ID...", label_visibility="collapsed")
        type_filter = l2.selectbox("Type", ["All types", "BATCH", "TEST"], label_visibility="collapsed")
        status_filter = l3.selectbox("Status", ["All results", "SENT", "FAILED"], label_visibility="collapsed")

        filtered_logs = [
            l
            for l in logs
            if (not log_search or log_search.lower() in l["client_email"].lower() or (l["message_id"] and log_search.lower() in l["message_id"].lower()))
            and (type_filter == "All types" or l["send_type"] == type_filter)
            and (status_filter == "All results" or l["status"] == status_filter)
        ]

        log_rows = ""
        for l in filtered_logs:
            badge = (
                '<span class="rpm-badge rpm-badge-green">Completed</span>'
                if l["status"] == "SENT"
                else '<span class="rpm-badge rpm-badge-red">Failed</span>'
            )
            detail = f"{l['client_name']} ({l['client_email']}) &bull; {l['week_key']}"
            if l["message_id"]:
                detail += f" &bull; ID: {l['message_id']}"
            if l["error_message"]:
                detail += f" &bull; Error: {l['error_message']}"
            log_rows += (
                f"<tr>"
                f"<td style='color:{pal['muted']}; white-space:nowrap;'>{html.escape(l['sent_at'])}</td>"
                f"<td><strong>{html.escape(l['send_type'])} email</strong></td>"
                f"<td style='color:{pal['muted']};'>{html.escape(detail)}</td>"
                f"<td>{badge}</td>"
                f"</tr>"
            )
        st.markdown(
            f'<div class="rpm-card" style="padding:8px 16px;">'
            f'<table class="rpm-table"><thead><tr><th>Time</th><th>Event</th><th>Details</th><th>Result</th></tr></thead>'
            f"<tbody>{log_rows}</tbody></table></div>",
            unsafe_allow_html=True,
        )

# ==================================================================
# PAGE 7: SETTINGS
# ==================================================================
elif current_page == "Settings":
    cred_badge = (
        '<span class="rpm-badge rpm-badge-green">Found</span>'
        if CREDENTIALS_FILE.exists()
        else '<span class="rpm-badge rpm-badge-red">Missing</span>'
    )
    tok_badge = (
        '<span class="rpm-badge rpm-badge-green">Authorized</span>'
        if TOKEN_FILE.exists()
        else '<span class="rpm-badge rpm-badge-amber">Pending OAuth</span>'
    )
    st.markdown(
        f"""
        <div class="rpm-card">
          <div class="rpm-section-title">Workspace configuration</div>
          <div class="rpm-section-sub">Loaded from <code>shared/config.py</code> and <code>.env</code></div>
          <table class="rpm-table">
            <tbody>
              <tr><td><strong>Company Name</strong></td><td>{html.escape(COMPANY_INFO['name'])}</td></tr>
              <tr><td><strong>Gmail OAuth Credentials</strong></td><td>{cred_badge} &nbsp; <span style="color:{pal['muted']};">{html.escape(CREDENTIALS_FILE.name)}</span></td></tr>
              <tr><td><strong>Gmail User Token</strong></td><td>{tok_badge} &nbsp; <span style="color:{pal['muted']};">{html.escape(TOKEN_FILE.name)}</span></td></tr>
              <tr><td><strong>Daily Send Cap</strong></td><td>{DAILY_SEND_LIMIT} emails/day ({SEND_DELAY_SECONDS}s delay)</td></tr>
              <tr><td><strong>Automatic Schedule</strong></td><td>Monday – Saturday at {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} local time</td></tr>
              <tr><td><strong>Unsubscribe Server URL</strong></td><td><code>{html.escape(BASE_URL)}</code> (start via <code>python main.py --serve</code>)</td></tr>
            </tbody>
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )
