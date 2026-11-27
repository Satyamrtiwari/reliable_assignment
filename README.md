# Reliable Paper Mart – Automated Marketing System

An automated B2B marketing platform built for **Reliable Paper Mart**:
- **Task 1 (`task1_email_automation/`):** Weekly stock availability email automation via Gmail API with Monday–Saturday batch spreading, RFC 8058 + web unsubscribe handling, SQLite send logging, and a Light/Dark Streamlit workspace dashboard.
- **Task 2 (`task2_ai_flyer/`):** AI promotional flyer generation (Groq LLM copy + 1080×1350 Pillow rendering with 3 rotatable layouts) and policy-compliant Facebook & WhatsApp distribution.

See [COMPLIANCE.md](COMPLIANCE.md) for detailed Gmail, WhatsApp, and Facebook policy research and compliance architecture.

---

## Project Structure

```text
reliable_assignment/
├── .streamlit/
│   └── config.toml                 # Light & Dark Streamlit workspace theme config
├── shared/
│   ├── config.py                   # Central settings, Gmail/Groq/Meta env config
│   └── database.py                 # SQLite schema, migrations, CSV import, logs
├── task1_email_automation/
│   ├── email_sender.py             # Gmail API OAuth2 authentication & MIME sending
│   ├── email_template.py           # Jinja2 HTML & plain-text email renderer
│   ├── scheduler.py                # Mon–Sat APScheduler, daily quota batch & test sender
│   ├── unsubscribe_server.py       # FastAPI service (GET/POST /unsubscribe/{token}, /logs)
│   └── templates/
│       └── stock_email.html        # Responsive Light/Dark HTML stock email template
├── task2_ai_flyer/
│   ├── ai_copywriter.py            # Groq API marketing copywriter + deterministic fallback
│   ├── flyer_generator.py          # Pillow 1080x1350 flyer renderer (3 styles x 3 layouts)
│   └── social_distributor.py       # FB Page Graph API, WA Cloud API, & Group Share Packs
├── generated_flyers/               # Output PNG flyers & compliant share_packs/
├── data/
│   ├── sample_clients.csv          # Sample CSV for bulk client import
│   └── sample_stock.csv            # Sample CSV for bulk stock import
├── tests/
│   ├── test_task1.py               # Automated unit tests for Task 1 (12 tests)
│   └── test_task2.py               # Automated unit tests for Task 2 (8 tests)
├── COMPLIANCE.md                   # Platform policy research & compliant design rationale
├── dashboard.py                    # Streamlit Marketing Workspace UI (Light/Dark)
├── main.py                         # Unified CLI entry point
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variable template
└── .gitignore                      # Excludes credentials.json, token.json, .env, *.db, venv/
```

---

## Setup Instructions

### 1. Create Virtual Environment & Install Dependencies
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Gmail API OAuth2 Credentials (Task 1)
1. Open [Google Cloud Console](https://console.cloud.google.com) and create a project.
2. Enable the **Gmail API**.
3. Configure **Google Auth Platform / OAuth Consent Screen** (`External`):
   - Add scope `https://www.googleapis.com/auth/gmail.send`.
   - Add your sender Gmail account under **Test users**.
4. Create an **OAuth Client ID** of type **Desktop app**, download the JSON file, rename it to `credentials.json`, and place it in the project root.

### 3. Configure Environment Variables (Task 2 & Settings)
Copy `.env.example` to `.env` and fill in your keys (leave Meta keys blank to use Dry-Run + Group Share Pack mode):
- `GROQ_API_KEY` — Free API key from [console.groq.com](https://console.groq.com)
- `FB_PAGE_ID` & `FB_PAGE_ACCESS_TOKEN` — From Meta Graph API Explorer (`pages_manage_posts`, `pages_read_engagement`)
- `WHATSAPP_PHONE_NUMBER_ID` & `WHATSAPP_ACCESS_TOKEN` — From Meta WhatsApp Cloud API Setup

### 4. Initialize Database & Verify OAuth Login
```powershell
python main.py --init-db
python main.py --test-email your_email@gmail.com
```
On the first run, a browser window opens for Gmail OAuth authorization and saves `token.json` locally.

---

## Running the System

### Option A: Streamlit Marketing Workspace (UI)
```powershell
streamlit run dashboard.py
```
- **Overview:** KPI cards, Mon–Sat dispatch spread, recent activity, live stock snapshot
- **Customers:** Directory with search/filters, single add, CSV bulk import, and subscription badges
- **Inventory:** Live stock editor (changes immediately reflect in emails and flyers)
- **Email campaigns:** Test email sender (blocks unsubscribed addresses), Mon–Sat batch runner (Dry Run / Real), and Light/Dark HTML email preview
- **AI flyer studio:** Generate `1080×1350` flyers (`Card List`, `2-Column Grid`, `Featured Spotlight`, `Auto-Rotate` across `Minimal`/`Bold`/`Fresh`), download PNGs, publish to Facebook Page, broadcast to opted-in WhatsApp Cloud API contacts, or create a `wa.me` Group Share Pack
- **Activity logs:** Per-recipient email counts, email history, and social distribution audit logs

### Option B: CLI & Automated Scheduler
- **Start continuous Mon–Sat 09:30 AM scheduler + FastAPI unsubscribe server:**
  ```powershell
  python main.py --serve
  ```
- **Task 1 CLI:**
  ```powershell
  python main.py --send-now --dry-run
  python main.py --send-now
  python main.py --add-client "Client Name" client@example.com
  python main.py --clients
  python main.py --stock
  python main.py --logs
  ```
- **Task 2 CLI:**
  ```powershell
  python main.py --generate-flyer --flyer-style Minimal --layout "Auto-Rotate" --theme "Weekly paper essentials"
  python main.py --add-wa-contact "Test Client" 919820000000
  python main.py --distribute-flyer --dry-run
  python main.py --distribute-flyer
  ```

---

## Running Tests
```powershell
python -m unittest discover -s tests -v
```
