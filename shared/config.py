"""Central configuration for the Reliable Paper Mart marketing automation system."""

import os
from pathlib import Path
from dotenv import dotenv_values, load_dotenv

# Project root (parent of shared/)
BASE_DIR = Path(__file__).resolve().parent.parent
_DOTENV_VALUES = dotenv_values(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env")


def _cfg(key: str, default: str = "") -> str:
    """Prefer non-empty .env value for app/API settings, else OS env, else default."""
    if key != "DB_PATH":
        env_val = (_DOTENV_VALUES.get(key) or "").strip()
        if env_val:
            return env_val
    return os.getenv(key, default)


# Database, Credentials & Output Folders
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "marketing.db"))
CREDENTIALS_FILE = Path(_cfg("CREDENTIALS_FILE", str(BASE_DIR / "credentials.json")))
TOKEN_FILE = Path(_cfg("TOKEN_FILE", str(BASE_DIR / "token.json")))
TEMPLATES_DIR = BASE_DIR / "task1_email_automation" / "templates"
GENERATED_FLYERS_DIR = BASE_DIR / "generated_flyers"
DATA_DIR = BASE_DIR / "data"

# Gmail API Configuration (least-privilege scope)
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# Task 2: Groq AI Configuration (Free tier at console.groq.com)
GROQ_API_KEY = _cfg("GROQ_API_KEY", "")
GROQ_MODEL = _cfg("GROQ_MODEL", "openai/gpt-oss-120b")

# Task 2: Meta Graph API (Facebook Page & WhatsApp Cloud API)
META_GRAPH_API_VERSION = _cfg("META_GRAPH_API_VERSION", "v21.0")
FB_PAGE_ID = _cfg("FB_PAGE_ID", "")
FB_PAGE_ACCESS_TOKEN = _cfg("FB_PAGE_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = _cfg("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_ACCESS_TOKEN = _cfg("WHATSAPP_ACCESS_TOKEN", "")
TEAM_NOTIFY_EMAIL = _cfg("TEAM_NOTIFY_EMAIL", "")
SHARE_PACKS_DIR = GENERATED_FLYERS_DIR / "share_packs"

# Sending Limits & Compliance
# Free Gmail: ~500/day; Google Workspace: ~2000/day.
DAILY_SEND_LIMIT = int(os.getenv("DAILY_SEND_LIMIT", "400"))
SEND_DELAY_SECONDS = float(os.getenv("SEND_DELAY_SECONDS", "2.0"))
REPLY_TO_EMAIL = os.getenv("REPLY_TO_EMAIL", "")

# Unsubscribe Server
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
BASE_URL = os.getenv("BASE_URL", f"http://localhost:{SERVER_PORT}")

# Scheduler (Monday=0 to Saturday=5, runs at 09:30 AM local time)
SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "9"))
SCHEDULE_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "30"))

# Company Branding & Contact Details
COMPANY_INFO = {
    "name": "Reliable Paper Mart",
    "tagline": "Quality Paper & Packaging Solutions Since 1998",
    "email": os.getenv("COMPANY_EMAIL", "sales@reliablepapermart.com"),
    "phone": os.getenv("COMPANY_PHONE", "+91 98200 00000"),
    "address": os.getenv("COMPANY_ADDRESS", "Plot 42, Paper Market Industrial Estate, Mumbai - 400001"),
    "hours": "Mon - Sat, 9:30 AM - 6:30 PM IST",
    "website": "www.reliablepapermart.com",
}

DAY_NAMES = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}
