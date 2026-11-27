"""Streamlit Workspace Dashboard for Reliable Paper Mart Marketing Automation."""

from datetime import datetime
import html
from pathlib import Path
import tempfile
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

from shared.config import (
    BASE_URL,
    COMPANY_INFO,
    CREDENTIALS_FILE,
    DAILY_SEND_LIMIT,
    DAY_NAMES,
    FB_PAGE_ACCESS_TOKEN,
    FB_PAGE_ID,
    GROQ_API_KEY,
    SCHEDULE_HOUR,
    SCHEDULE_MINUTE,
    SEND_DELAY_SECONDS,
    TEAM_NOTIFY_EMAIL,
    TOKEN_FILE,
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_PHONE_NUMBER_ID,
)
from shared.database import (
    add_client,
    add_or_update_stock_item,
    add_whatsapp_contact,
    count_sent_today,
    get_all_clients,
    get_all_stock_items,
    get_current_week_key,
    get_in_stock_items,
    get_recent_flyers,
    get_recent_logs,
    get_recent_social_logs,
    get_send_counts_by_recipient,
    get_summary_stats,
    get_whatsapp_contacts,
    import_clients_csv,
    init_db,
    seed_sample_data,
    set_whatsapp_opt_in,
)
from task1_email_automation.email_template import render_stock_email
from task1_email_automation.scheduler import run_daily_batch, send_test_stock_email
from task2_ai_flyer.flyer_generator import LAYOUT_NAMES, STYLE_PALETTES, generate_flyer_image
from task2_ai_flyer.social_distributor import (
    create_group_share_pack,
    notify_team_with_share_pack,
    post_to_facebook_page,
    send_whatsapp_flyer_broadcast,
)

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
        :root, .stApp, [data-testid="stAppViewContainer"] {{
            background-color: {p['bg']} !important;
            color: {p['text']} !important;
            color-scheme: {"dark" if is_dark else "light"} !important;
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
        /* Main buttons (including Light/Dark pill switcher, link buttons & form submit buttons) */
        [data-testid="stMain"] div.stButton > button[kind="secondary"],
        [data-testid="stMain"] button[data-testid="stBaseButton-secondary"],
        [data-testid="stMain"] [data-testid="stLinkButton"] a,
        [data-testid="stMain"] a[data-testid^="stBaseLinkButton"] {{
            background-color: {p['card']} !important;
            color: {p['text']} !important;
            border: 1px solid {p['border']} !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            text-decoration: none !important;
        }}
        [data-testid="stMain"] [data-testid="stLinkButton"] a *,
        [data-testid="stMain"] a[data-testid^="stBaseLinkButton"] * {{
            color: {p['text']} !important;
            -webkit-text-fill-color: {p['text']} !important;
        }}
        [data-testid="stMain"] div.stButton > button[kind="secondary"]:hover,
        [data-testid="stMain"] button[data-testid="stBaseButton-secondary"]:hover,
        [data-testid="stMain"] [data-testid="stLinkButton"] a:hover,
        [data-testid="stMain"] a[data-testid^="stBaseLinkButton"]:hover {{
            background-color: {p['nav_active_bg']} !important;
            border-color: {p['primary']} !important;
        }}
        [data-testid="stMain"] div.stButton > button[kind="primary"],
        [data-testid="stMain"] div.stFormSubmitButton > button,
        [data-testid="stMain"] div.stDownloadButton > button,
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
        [data-testid="stMain"] div.stDownloadButton > button *,
        [data-testid="stMain"] button[data-testid="stBaseButton-primary"] *,
        [data-testid="stMain"] button[data-testid="stBaseButton-primaryFormSubmit"] * {{
            color: #ffffff !important;
        }}
        [data-testid="stMain"] div.stButton > button[kind="primary"]:hover,
        [data-testid="stMain"] div.stFormSubmitButton > button:hover,
        [data-testid="stMain"] div.stDownloadButton > button:hover,
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
        /* Clean inputs, textareas, selects, multiselects, popovers, radios & forms */
        [data-testid="stForm"],
        [data-testid="stExpander"],
        [data-testid="stExpander"] details,
        [data-testid="stExpanderDetails"],
        [data-testid="stVerticalBlockBorderWrapper"] {{
            background-color: {p['card']} !important;
            border: 1px solid {p['border']} !important;
            border-radius: 14px !important;
        }}
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] summary:hover,
        [data-testid="stExpander"] summary:focus,
        [data-testid="stExpander"] summary:focus-visible,
        [data-testid="stExpander"] summary:active,
        [data-testid="stExpander"] details[open] > summary {{
            background-color: {p['card_subtle']} !important;
            color: {p['text']} !important;
            border-radius: 12px !important;
        }}
        [data-testid="stExpander"] summary *,
        [data-testid="stExpander"] summary svg {{
            background-color: transparent !important;
            color: {p['text']} !important;
            fill: {p['text']} !important;
        }}
        [data-testid="stMain"] [data-testid="stTextInput"] div,
        [data-testid="stMain"] [data-testid="stTextArea"] div,
        [data-testid="stMain"] [data-testid="stNumberInput"] div,
        [data-testid="stMain"] [data-testid="stSelectbox"] div,
        [data-testid="stMain"] [data-testid="stMultiSelect"] div {{
            background-color: {p['card_subtle']} !important;
            color: {p['text']} !important;
            border-color: {p['border']} !important;
        }}
        [data-testid="stMain"] [data-testid="stTextInput"] [data-baseweb="input"],
        [data-testid="stMain"] [data-testid="stTextArea"] [data-baseweb="textarea"],
        [data-testid="stMain"] [data-testid="stNumberInput"] [data-baseweb="input"],
        [data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] > div,
        [data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="select"] > div {{
            border: 1px solid {p['border']} !important;
            border-radius: 10px !important;
        }}
        [data-testid="stMain"] input,
        [data-testid="stMain"] textarea,
        [data-testid="stMain"] [data-baseweb="select"] span,
        [data-testid="stMain"] [data-baseweb="select"] svg {{
            background-color: transparent !important;
            color: {p['text']} !important;
            -webkit-text-fill-color: {p['text']} !important;
            caret-color: {p['text']} !important;
            fill: {p['muted']} !important;
        }}
        [data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="tag"],
        [data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="tag"] * {{
            background-color: {p['primary']} !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            fill: #ffffff !important;
        }}
        [data-baseweb="popover"],
        [data-baseweb="popover"] div,
        [data-baseweb="menu"],
        [role="listbox"] {{
            background-color: {p['card']} !important;
            border-color: {p['border']} !important;
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
        [data-testid="stMain"] [data-testid="stRadioOption"] > div:first-of-type > div:first-child,
        [data-testid="stMain"] [data-testid="stRadio"] [role="radiogroup"] label > div:first-of-type > div:first-child {{
            background-color: {p['card']} !important;
            border: 2px solid {p['muted']} !important;
        }}
        [data-testid="stMain"] [data-testid="stRadioOption"] > div:first-of-type > div:first-child > div,
        [data-testid="stMain"] [data-testid="stRadio"] [role="radiogroup"] label > div:first-of-type > div:first-child > div {{
            background-color: transparent !important;
        }}
        [data-testid="stMain"] [data-selected="true"] > [data-testid="stRadioOption"] > div:first-of-type > div:first-child,
        [data-testid="stMain"] [data-testid="stRadioOption"][data-selected="true"] > div:first-of-type > div:first-child,
        [data-testid="stMain"] [data-testid="stRadio"] label:has(input:checked) > div:first-of-type > div:first-child {{
            border-color: {p['primary']} !important;
            background-color: {p['primary']} !important;
        }}
        [data-testid="stMain"] [data-selected="true"] > [data-testid="stRadioOption"] > div:first-of-type > div:first-child > div,
        [data-testid="stMain"] [data-testid="stRadioOption"][data-selected="true"] > div:first-of-type > div:first-child > div,
        [data-testid="stMain"] [data-testid="stRadio"] label:has(input:checked) > div:first-of-type > div:first-child > div {{
            background-color: #ffffff !important;
        }}
        [data-testid="stMain"] [data-testid="stCheckbox"] > label > div:first-of-type:not(:has(> div)) {{
            background-color: {p['card']} !important;
            border: 2px solid {p['muted']} !important;
            border-radius: 5px !important;
        }}
        [data-testid="stMain"] [data-testid="stCheckbox"][data-selected="true"] > label > div:first-of-type:not(:has(> div)),
        [data-testid="stMain"] [data-testid="stCheckbox"] > label[data-selected="true"] > div:first-of-type:not(:has(> div)),
        [data-testid="stMain"] [data-testid="stCheckbox"] > label:has(input:checked) > div:first-of-type:not(:has(> div)) {{
            background-color: {p['primary']} !important;
            border-color: {p['primary']} !important;
        }}
        [data-testid="stMain"] [data-testid="stCheckbox"] svg {{
            stroke: #ffffff !important;
        }}
        [data-testid="stMain"] [data-testid="stCheckbox"] > label > div:first-of-type:has(> div) {{
            background-color: {p['border']} !important;
        }}
        [data-testid="stMain"] [data-testid="stCheckbox"][data-selected="true"] > label > div:first-of-type:has(> div),
        [data-testid="stMain"] [data-testid="stCheckbox"] > label[data-selected="true"] > div:first-of-type:has(> div),
        [data-testid="stMain"] [data-testid="stCheckbox"] > label:has(input:checked) > div:first-of-type:has(> div) {{
            background-color: {p['primary']} !important;
        }}
        [data-testid="stMain"] [data-testid="stCheckbox"] > label > div:first-of-type:has(> div) > div {{
            background-color: #ffffff !important;
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
# PAGE 5: AI FLYER STUDIO (TASK 2 - PART 1)
# ==================================================================
elif current_page == "AI flyer studio":
    in_stock_all = get_in_stock_items()
    all_flyers = get_recent_flyers(limit=500)
    show_all_flyers = st.session_state.get("show_all_flyers", False)
    recent_flyers = all_flyers if show_all_flyers else all_flyers[:10]

    ai_badge = (
        '<span class="rpm-badge rpm-badge-green">Groq AI Connected</span>'
        if GROQ_API_KEY
        else '<span class="rpm-badge rpm-badge-amber">Offline Fallback (Set GROQ_API_KEY in .env for AI copy)</span>'
    )
    st.markdown(
        f'<div style="margin-bottom:14px;">{ai_badge}</div>',
        unsafe_allow_html=True,
    )

    f_left, f_right = st.columns([1.05, 1])

    with f_left:
        with st.container(border=True):
            st.markdown(
                f'<div class="rpm-section-title">Create a weekly promotional flyer</div>'
                f'<div class="rpm-section-sub">Groq AI crafts the headline &amp; offer copy; item names and prices come directly from SQLite inventory</div>',
                unsafe_allow_html=True,
            )

            campaign_theme = st.text_input(
                "Campaign Theme",
                value="Weekly paper essentials",
                placeholder="e.g., Festive Packaging Deals / Office Paper Restock",
            )
            custom_headline = st.text_input(
                "Promotional Headline (optional — leave blank for AI)",
                value="",
                placeholder="Leave blank to let Groq AI write the headline",
            )

            item_map = {
                f"{i['item_name']} — Rs. {i['price']:.2f} ({i['unit']})": i
                for i in in_stock_all
            }
            selected_labels = st.multiselect(
                "Products to include (up to 6 shown on flyer)",
                options=list(item_map.keys()),
                default=list(item_map.keys())[:6],
            )
            selected_items = [item_map[lbl] for lbl in selected_labels]

            design_style = st.radio(
                "Color Style",
                options=list(STYLE_PALETTES.keys()),
                index=0,
                horizontal=True,
            )
            flyer_layout = st.selectbox(
                "Flyer Layout",
                options=["Auto-Rotate"] + list(LAYOUT_NAMES),
                index=0,
                help="Auto-Rotate cycles between Card List, 2-Column Grid, and Featured Spotlight on each generation.",
            )

            if st.button("✨ Generate promotional flyer", type="primary", use_container_width=True):
                if not selected_items:
                    _alert_box("warning", "Select at least one in-stock product to generate a flyer.")
                else:
                    with st.status("Creating promotional flyer...", expanded=True) as status:
                        st.write("🧠 Generating headline, offer badge & social caption...")
                        st.write("🎨 Rendering 1080×1350 PNG flyer with exact inventory prices...")
                        flyer_res = generate_flyer_image(
                            stock_items=selected_items,
                            style=design_style,
                            layout=flyer_layout,
                            campaign_theme=campaign_theme.strip() or "Weekly paper essentials",
                            custom_headline=custom_headline.strip() or None,
                        )
                        status.update(label="✅ Flyer generated and saved!", state="complete")
                    st.session_state["latest_flyer"] = flyer_res
                    st.session_state["send_feedback"] = (
                        "success",
                        f"Generated {flyer_res['layout']} ({design_style}) flyer ({Path(flyer_res['image_path']).name}) via {flyer_res['ai_source']}.",
                    )
                    st.rerun()

    with f_right:
        active_flyer = st.session_state.get("latest_flyer") or (all_flyers[0] if all_flyers else None)
        with st.container(border=True):
            st.markdown(
                f'<div class="rpm-section-title">Live flyer preview</div>'
                f'<div class="rpm-section-sub">Generated PNG ready to verify and download before sharing</div>',
                unsafe_allow_html=True,
            )
            if active_flyer and Path(active_flyer["image_path"]).exists():
                flyer_file = Path(active_flyer["image_path"])
                st.caption(
                    f"Layout: **{active_flyer.get('layout', 'Card List')}** | Style: **{active_flyer['style']}** | "
                    f"AI: **{active_flyer['ai_source']}** | Items: **{active_flyer['item_count']}**"
                )
                st.image(str(flyer_file), use_container_width=True)
                with open(flyer_file, "rb") as img_fp:
                    st.download_button(
                        "⬇️ Download Flyer PNG",
                        data=img_fp.read(),
                        file_name=flyer_file.name,
                        mime="image/png",
                        type="primary",
                        use_container_width=True,
                    )
                st.text_area(
                    "Generated Social Caption (WhatsApp / Facebook)",
                    value=active_flyer["caption"],
                    height=150,
                )
            else:
                _alert_box("info", "No flyer generated yet. Pick your products and click 'Generate promotional flyer'.")

    if recent_flyers:
        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="rpm-section-title">Recent generated flyers</div>'
            f'<div class="rpm-section-sub">Showing {len(recent_flyers)} of {len(all_flyers)} generated flyers &bull; Saved inside <code>generated_flyers/</code> and logged in SQLite</div>',
            unsafe_allow_html=True,
        )
        f_rows = ""
        for fl in recent_flyers:
            f_rows += (
                f"<tr>"
                f"<td style='color:{pal['muted']}; white-space:nowrap;'>{html.escape(fl['created_at'])}</td>"
                f"<td><strong>{html.escape(fl['headline'])}</strong></td>"
                f"<td>{html.escape(fl.get('layout', 'Card List'))}</td>"
                f"<td>{html.escape(fl['style'])}</td>"
                f"<td><span class='rpm-badge rpm-badge-neutral'>{html.escape(fl['ai_source'])}</span></td>"
                f"<td>{fl['item_count']} items</td>"
                f"<td style='color:{pal['muted']};'>{html.escape(Path(fl['image_path']).name)}</td>"
                f"</tr>"
            )
        st.markdown(
            f'<div class="rpm-card" style="padding:8px 16px;">'
            f'<table class="rpm-table"><thead><tr><th>Created</th><th>Headline</th><th>Layout</th><th>Style</th><th>AI Source</th><th>Scope</th><th>File</th></tr></thead>'
            f"<tbody>{f_rows}</tbody></table></div>",
            unsafe_allow_html=True,
        )
        if len(all_flyers) > 10:
            st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
            _, btn_mid, _ = st.columns([1.2, 1, 1.2])
            with btn_mid:
                if not show_all_flyers:
                    remaining = len(all_flyers) - 10
                    if st.button(
                        f"More ({remaining} older flyer{'s' if remaining != 1 else ''} — show full history)",
                        key="flyer_history_more",
                        use_container_width=True,
                    ):
                        st.session_state["show_all_flyers"] = True
                        st.rerun()
                else:
                    if st.button(
                        "Show less (latest 10 only)",
                        key="flyer_history_less",
                        use_container_width=True,
                    ):
                        st.session_state["show_all_flyers"] = False
                        st.rerun()

    # ------------------------------------------------------------------
    # PART 2: Policy-Compliant Social & WhatsApp Distribution
    # ------------------------------------------------------------------
    st.markdown("<div style='height:22px;'></div>", unsafe_allow_html=True)

    if not active_flyer or not Path(active_flyer["image_path"]).exists():
        _alert_box("info", "Generate a flyer above first to distribute it to Facebook & WhatsApp.")
    else:
        fb_ready = bool(FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN)
        wa_ready = bool(WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_ACCESS_TOKEN)

        # Facebook Page Distribution Card
        with st.container(border=True):
            fb_badge = (
                f'<span class="rpm-badge rpm-badge-green">Page Connected ({html.escape(FB_PAGE_ID)})</span>'
                if fb_ready
                else '<span class="rpm-badge rpm-badge-amber">Dry-Run Mode</span>'
            )
            fb_h1, fb_h2, fb_h3 = st.columns([1.6, 0.9, 1.1])
            with fb_h1:
                st.markdown(
                    f'<div class="rpm-section-title" style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">'
                    f'<span>📘 Facebook Page</span>{fb_badge}'
                    f'</div>'
                    f'<div class="rpm-section-sub" style="margin-bottom:0;">Auto-publishes the active flyer &amp; caption to your owned Facebook Page</div>',
                    unsafe_allow_html=True,
                )
            with fb_h2:
                fb_dry = st.checkbox(
                    "Dry run (preview only)",
                    value=not fb_ready,
                    key="fb_dry_run_chk",
                )
            with fb_h3:
                if st.button("Publish to Facebook Page", type="primary", use_container_width=True):
                    with st.status("Publishing flyer to Facebook Page...", expanded=True) as status:
                        st.write("📤 Calling Meta Graph API `/photos`...")
                        fb_res = post_to_facebook_page(
                            image_path=active_flyer["image_path"],
                            caption=active_flyer["caption"],
                            flyer_id=active_flyer.get("id"),
                            dry_run=fb_dry,
                        )
                        if fb_res.get("ok"):
                            status.update(
                                label="✅ Facebook Page distribution complete!", state="complete"
                            )
                            st.session_state["last_fb_url"] = fb_res.get("post_url")
                            msg = (
                                f"Simulated FB Page post ({fb_res['details']})"
                                if fb_res.get("simulated")
                                else f"Published to Facebook Page! Post ID: {fb_res.get('external_id')}"
                            )
                            st.session_state["send_feedback"] = ("success", msg)
                            st.rerun()
                        else:
                            status.update(label="❌ Facebook publish failed", state="error")
                            _alert_box("error", f"Facebook API error: {fb_res.get('error')}")
            if st.session_state.get("last_fb_url"):
                st.link_button(
                    "🔗 View Facebook Post",
                    st.session_state["last_fb_url"],
                )

        # Approved WhatsApp Distribution Layout
        st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
        wa_badge = (
            '<span class="rpm-badge rpm-badge-green">● Cloud API Connected</span>'
            if wa_ready
            else '<span class="rpm-badge rpm-badge-amber">Dry-Run Mode</span>'
        )
        st.markdown(
            f'<div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap; margin-bottom:4px;">'
            f'<span style="font-size:1.35rem; font-weight:700; color:{pal["text"]};">WhatsApp Distribution</span>'
            f'{wa_badge}'
            f'</div>'
            f'<div class="rpm-section-sub">1-to-1 Flyers go only to Opted-In contacts; use Share Pack for WhatsApp Groups</div>',
            unsafe_allow_html=True,
        )

        wa_left, wa_right = st.columns([1.25, 1])

        # Left Card: Opted-In Contacts (Who Receives Flyers)
        with wa_left:
            with st.container(border=True):
                st.markdown(
                    '<div class="rpm-section-title" style="margin-bottom:10px;">Opted-In Contacts (Who Receives Flyers)</div>',
                    unsafe_allow_html=True,
                )
                all_wa = get_whatsapp_contacts(opted_in_only=False)
                if not all_wa:
                    _alert_box("info", "No WhatsApp contacts saved yet. Add one below.")
                else:
                    for idx, wc in enumerate(all_wa):
                        is_opted = bool(wc["opted_in"])
                        c_name, c_phone, c_badge, c_tog = st.columns([1.25, 1.35, 0.85, 0.55])
                        with c_name:
                            st.markdown(
                                f'<div style="padding-top:6px; font-weight:600; color:{pal["text"]};">{html.escape(wc["name"])}</div>',
                                unsafe_allow_html=True,
                            )
                        with c_phone:
                            st.markdown(
                                f'<div style="padding-top:6px; color:{pal["muted"]}; font-size:0.9rem;">+{html.escape(wc["phone_e164"])}</div>',
                                unsafe_allow_html=True,
                            )
                        with c_badge:
                            badge_cls = "rpm-badge-green" if is_opted else "rpm-badge-neutral"
                            badge_txt = "Opted-In" if is_opted else "Opted-Out"
                            st.markdown(
                                f'<div style="padding-top:4px;"><span class="rpm-badge {badge_cls}">{badge_txt}</span></div>',
                                unsafe_allow_html=True,
                            )
                        with c_tog:
                            toggled = st.toggle(
                                f"Active {wc['name']}",
                                value=is_opted,
                                key=f"wa_opt_toggle_{wc['id']}",
                                label_visibility="collapsed",
                            )
                            if toggled != is_opted:
                                set_whatsapp_opt_in(wc["id"], toggled)
                                st.rerun()
                        if idx < len(all_wa) - 1:
                            st.markdown(
                                f'<hr style="margin:6px 0; border:none; border-top:1px solid {pal["border"]};">',
                                unsafe_allow_html=True,
                            )

                st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                with st.container(border=True):
                    st.markdown(
                        '<div style="font-weight:700; font-size:0.95rem; margin-bottom:8px;">+ Add Contact</div>',
                        unsafe_allow_html=True,
                    )
                    add_c1, add_c2 = st.columns(2)
                    with add_c1:
                        wa_name = st.text_input(
                            "Name",
                            placeholder="Name",
                            label_visibility="collapsed",
                            key="new_wa_name",
                        )
                    with add_c2:
                        wa_phone = st.text_input(
                            "+91 Phone",
                            placeholder="+91 Phone (e.g. 919820000000)",
                            label_visibility="collapsed",
                            key="new_wa_phone",
                        )
                    opt_col, btn_col = st.columns([1.6, 0.7])
                    with opt_col:
                        wa_opt_confirm = st.checkbox(
                            "Opt-in confirmed",
                            value=True,
                            key="new_wa_opt_confirmed",
                        )
                    with btn_col:
                        if st.button("Add", type="primary", use_container_width=True, key="add_wa_contact_btn"):
                            if not wa_phone.strip():
                                _alert_box("warning", "Enter a phone number with country code.")
                            else:
                                try:
                                    add_whatsapp_contact(
                                        wa_name.strip() or "Client",
                                        wa_phone.strip(),
                                        opted_in=wa_opt_confirm,
                                    )
                                    st.session_state["send_feedback"] = (
                                        "success",
                                        f"Added {wa_name.strip() or 'Client'} (+{wa_phone.strip().lstrip('+')})",
                                    )
                                    st.rerun()
                                except Exception as exc:
                                    _alert_box("error", str(exc))

        # Right Card: Send & Share Flyer
        with wa_right:
            with st.container(border=True):
                st.markdown(
                    '<div class="rpm-section-title" style="margin-bottom:10px;">Send &amp; Share Flyer</div>',
                    unsafe_allow_html=True,
                )

                # Sub-card 1: 1-to-1 Cloud API Broadcast
                with st.container(border=True):
                    st.markdown(
                        '<div style="font-weight:700; font-size:0.98rem; margin-bottom:8px;">1-to-1 Cloud API Broadcast</div>',
                        unsafe_allow_html=True,
                    )
                    opted_in_contacts = get_whatsapp_contacts(opted_in_only=True)
                    n_opted = len(opted_in_contacts)
                    pill_col, dry_col = st.columns([1.45, 0.85])
                    with pill_col:
                        if n_opted > 0:
                            pill_bg = "rgba(59, 130, 246, 0.16)" if is_dark else "#e0e7ff"
                            pill_fg = "#93c5fd" if is_dark else "#1d4ed8"
                            pill_text = f"Will send to {n_opted} opted-in contact{'s' if n_opted != 1 else ''}"
                        else:
                            pill_bg = pal["amber_bg"]
                            pill_fg = pal["amber_fg"]
                            pill_text = "0 opted-in contacts active"
                        st.markdown(
                            f'<span class="rpm-badge" style="background-color:{pill_bg}; color:{pill_fg};">{pill_text}</span>',
                            unsafe_allow_html=True,
                        )
                    with dry_col:
                        wa_dry = st.toggle(
                            "Dry Run",
                            value=not wa_ready,
                            key="wa_dry_run_chk",
                        )

                    if st.button(
                        "Send Flyer to Opted-In Contacts",
                        type="primary",
                        use_container_width=True,
                        key="send_wa_broadcast_btn",
                    ):
                        with st.status("Running WhatsApp Cloud API broadcast...", expanded=True) as status:
                            st.write("📤 Uploading PNG & sending to opted-in contacts...")
                            wa_res = send_whatsapp_flyer_broadcast(
                                image_path=active_flyer["image_path"],
                                caption=active_flyer["caption"],
                                flyer_id=active_flyer.get("id"),
                                dry_run=wa_dry,
                            )
                            if wa_res["status"] == "NO_RECIPIENTS":
                                status.update(label="⚠️ No opted-in contacts", state="error")
                                _alert_box("warning", wa_res["message"])
                            elif wa_res.get("ok"):
                                status.update(label="✅ WhatsApp broadcast complete!", state="complete")
                                st.session_state["send_feedback"] = (
                                    "success",
                                    f"WhatsApp ({wa_res['status']}): {wa_res['sent']} sent, {wa_res['failed']} failed.",
                                )
                                st.rerun()
                            else:
                                status.update(label="❌ WhatsApp send failed", state="error")
                                _alert_box("error", f"WhatsApp error: {wa_res.get('error', wa_res['status'])}")

                    st.caption("Sandbox note: while using test #, recipient must reply 'Hi' within 24h.")

                # Sub-card 2: WhatsApp Groups (Compliant Share)
                with st.container(border=True):
                    st.markdown(
                        '<div style="font-weight:700; font-size:0.98rem; margin-bottom:8px;">WhatsApp Groups (Compliant Share)</div>',
                        unsafe_allow_html=True,
                    )
                    wa_direct_url = f"https://wa.me/?text={quote(active_flyer['caption'])}"
                    st.link_button(
                        "↗ Open WhatsApp (wa.me)",
                        wa_direct_url,
                        use_container_width=True,
                    )
                    st.markdown(
                        f'<div style="text-align:center; font-size:0.82rem; color:{pal["muted"]}; margin-top:4px;">'
                        f'Forward from Cloud API chat (or attach downloaded PNG inside WhatsApp)</div>',
                        unsafe_allow_html=True,
                    )
                    with st.expander("Save Share Pack & Email to Staff"):
                        if st.button("Prepare Group Share Pack", use_container_width=True):
                            pack = create_group_share_pack(
                                image_path=active_flyer["image_path"],
                                caption=active_flyer["caption"],
                                flyer_id=active_flyer.get("id"),
                                fb_post_url=st.session_state.get("last_fb_url"),
                            )
                            st.session_state["latest_share_pack"] = pack
                            st.session_state["send_feedback"] = (
                                "success",
                                f"Group Share Pack ready in {Path(pack['pack_dir']).name}!",
                            )
                            st.rerun()

                        pack_now = st.session_state.get("latest_share_pack")
                        team_email = st.text_input(
                            "Email pack to marketing staff",
                            value=TEAM_NOTIFY_EMAIL,
                            placeholder="staff@example.com",
                            key="team_notify_email_input",
                        )
                        if st.button("✉️ Email Share Pack", use_container_width=True):
                            if not team_email.strip():
                                _alert_box("warning", "Enter a recipient email.")
                            else:
                                if not pack_now:
                                    pack_now = create_group_share_pack(
                                        image_path=active_flyer["image_path"],
                                        caption=active_flyer["caption"],
                                        flyer_id=active_flyer.get("id"),
                                        fb_post_url=st.session_state.get("last_fb_url"),
                                    )
                                    st.session_state["latest_share_pack"] = pack_now
                                em_res = notify_team_with_share_pack(
                                    to_email=team_email.strip(),
                                    image_path=active_flyer["image_path"],
                                    caption=active_flyer["caption"],
                                    wa_share_url=pack_now["wa_share_url"],
                                    fb_post_url=st.session_state.get("last_fb_url"),
                                    flyer_id=active_flyer.get("id"),
                                )
                                if em_res.get("ok"):
                                    st.session_state["send_feedback"] = (
                                        "success",
                                        f"Share pack emailed to {team_email.strip()}!",
                                    )
                                    st.rerun()
                                else:
                                    _alert_box("error", f"Failed to email pack: {em_res.get('error')}")

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

    st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)
    st.markdown(
        f'<div class="rpm-section-title">Social distribution logs</div>'
        f'<div class="rpm-section-sub">Audit log for Facebook Page, WhatsApp Cloud API, Group Share Packs &amp; Team notifications</div>',
        unsafe_allow_html=True,
    )
    social_logs = get_recent_social_logs(limit=50)
    if not social_logs:
        _alert_box("info", "No social distribution events logged yet.")
    else:
        s_rows = ""
        for sl in social_logs:
            badge_cls = (
                "rpm-badge-green"
                if sl["status"] in ("SUCCESS", "READY")
                else ("rpm-badge-amber" if sl["status"] == "SIMULATED" else "rpm-badge-red")
            )
            s_rows += (
                f"<tr>"
                f"<td style='color:{pal['muted']}; white-space:nowrap;'>{html.escape(sl['created_at'])}</td>"
                f"<td><strong>{html.escape(sl['channel'])}</strong></td>"
                f"<td>{html.escape(sl['mode'])}</td>"
                f"<td style='color:{pal['muted']};'>{html.escape(sl['target'])}</td>"
                f"<td style='color:{pal['muted']};'>{html.escape(sl['details'] or '-')}</td>"
                f"<td><span class='rpm-badge {badge_cls}'>{html.escape(sl['status'])}</span></td>"
                f"</tr>"
            )
        st.markdown(
            f'<div class="rpm-card" style="padding:8px 16px;">'
            f'<table class="rpm-table"><thead><tr><th>Time</th><th>Channel</th><th>Mode</th><th>Target</th><th>Details</th><th>Status</th></tr></thead>'
            f"<tbody>{s_rows}</tbody></table></div>",
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
    groq_badge = (
        '<span class="rpm-badge rpm-badge-green">Configured</span>'
        if GROQ_API_KEY
        else '<span class="rpm-badge rpm-badge-amber">Offline Fallback</span>'
    )
    fb_cfg_badge = (
        f'<span class="rpm-badge rpm-badge-green">Connected (Page {html.escape(FB_PAGE_ID)})</span>'
        if (FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN)
        else '<span class="rpm-badge rpm-badge-amber">Dry-Run Mode</span>'
    )
    wa_cfg_badge = (
        f'<span class="rpm-badge rpm-badge-green">Connected ({html.escape(WHATSAPP_PHONE_NUMBER_ID)})</span>'
        if (WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_ACCESS_TOKEN)
        else '<span class="rpm-badge rpm-badge-amber">Dry-Run Mode</span>'
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
              <tr><td><strong>Groq AI Copywriter</strong></td><td>{groq_badge}</td></tr>
              <tr><td><strong>Facebook Page Graph API</strong></td><td>{fb_cfg_badge}</td></tr>
              <tr><td><strong>WhatsApp Cloud API</strong></td><td>{wa_cfg_badge}</td></tr>
              <tr><td><strong>Daily Send Cap</strong></td><td>{DAILY_SEND_LIMIT} emails/day ({SEND_DELAY_SECONDS}s delay)</td></tr>
              <tr><td><strong>Automatic Schedule</strong></td><td>Monday – Saturday at {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} local time</td></tr>
              <tr><td><strong>Unsubscribe Server URL</strong></td><td><code>{html.escape(BASE_URL)}</code> (start via <code>python main.py --serve</code>)</td></tr>
            </tbody>
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )
