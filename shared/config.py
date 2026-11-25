"""Central configuration for the Reliable Paper Mart marketing automation system."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Project root (parent of shared/)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Database, Credentials & Output Folders
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "marketing.db"))
CREDENTIALS_FILE = Path(os.getenv("CREDENTIALS_FILE", BASE_DIR / "credentials.json"))
TOKEN_FILE = Path(os.getenv("TOKEN_FILE", BASE_DIR / "token.json"))
TEMPLATES_DIR = BASE_DIR / "task1_email_automation" / "templates"
GENERATED_FLYERS_DIR = BASE_DIR / "generated_flyers"
DATA_DIR = BASE_DIR / "data"

# Gmail API Configuration (least-privilege scope)
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

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
