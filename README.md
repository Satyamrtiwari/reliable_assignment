# Reliable Paper Mart – Automated Marketing System

An automated B2B marketing platform built for **Reliable Paper Mart**:
- **Task 1 (`task1_email_automation/`):** Weekly stock availability email automation via Gmail API with Monday–Saturday batch spreading, RFC 8058 + web unsubscribe handling, SQLite send logging, and a Light/Dark Streamlit workspace dashboard.
- **Task 2 (`task2_ai_flyer/`):** *(Next)* AI promotional flyer generation and policy-compliant WhatsApp & Facebook distribution.

---

## Project Structure

```text
reliable_assignment/
├── .streamlit/
│   └── config.toml                 # Light & Dark Streamlit workspace theme config
├── shared/
│   ├── config.py                   # Central settings, Gmail scopes, limits, company info
│   └── database.py                 # SQLite schema, migrations, CSV import, batch & log queries
├── task1_email_automation/
│   ├── email_sender.py             # Gmail API OAuth2 authentication & MIME sending
│   ├── email_template.py           # Jinja2 HTML & plain-text email renderer
│   ├── scheduler.py                # Mon–Sat APScheduler, daily quota batch & test sender
│   ├── unsubscribe_server.py       # FastAPI service (GET/POST /unsubscribe/{token}, /logs)
│   └── templates/
│       └── stock_email.html        # Responsive Light/Dark HTML stock email template
├── task2_ai_flyer/                 # Task 2 modules (to be implemented next)
├── generated_flyers/               # Output directory for generated promotional flyers
├── data/
│   ├── sample_clients.csv          # Sample CSV for bulk client import
│   └── sample_stock.csv            # Sample CSV for bulk stock import
├── tests/
│   └── test_task1.py               # Automated unit tests for Task 1 (12 tests)
├── dashboard.py                    # Streamlit Marketing Workspace UI (Light/Dark)
├── main.py                         # Unified CLI entry point
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variable template
└── .gitignore                      # Excludes credentials.json, token.json, .env, *.db, venv/
```

---

## Task 1 – Key Features & Gmail Policy Compliance

1. **Monday–Saturday Batch Spreading:** Clients are auto-balanced across `assigned_day` (`0=Monday` to `5=Saturday`), keeping daily volume evenly distributed and well under Gmail sending limits (~500/day free Gmail, ~2,000/day Google Workspace).
2. **Quota & Pacing Controls:** Configurable `DAILY_SEND_LIMIT` (default `400`) and `SEND_DELAY_SECONDS` (`2.0s` delay between sends) prevent burst throttling.
3. **Once-Per-Week Deduplication:** Tracks ISO year-week (`YYYY-Www`) in `email_logs` so each active client receives at most one `BATCH` email per week, while `TEST` sends are logged separately without blocking weekly delivery.
4. **Unsubscribe Compliance:** Every email includes a unique token link plus RFC 8058 `List-Unsubscribe` and `List-Unsubscribe-Post` headers. Unsubscribed clients are excluded from both automated batches and manual test sends.
5. **Least-Privilege OAuth2:** Requests only `https://www.googleapis.com/auth/gmail.send` scope (cannot read or delete inbox messages).
6. **Live Inventory Sync:** Stock emails pull directly from `stock_items WHERE in_stock = 1 AND quantity > 0` at send time.

---

## Setup Instructions

### 1. Create Virtual Environment & Install Dependencies
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Gmail API OAuth2 Credentials
1. Open [Google Cloud Console](https://console.cloud.google.com) and create a project.
2. Enable the **Gmail API**.
3. Configure **Google Auth Platform / OAuth Consent Screen** (`External`):
   - Add scope `https://www.googleapis.com/auth/gmail.send`.
   - Add your sender Gmail account under **Test users**.
4. Create an **OAuth Client ID** of type **Desktop app**, download the JSON file, rename it to `credentials.json`, and place it in the project root.
5. *(Optional)* Copy `.env.example` to `.env` to customize limits, schedule time, or company details.

### 3. Initialize Database & Verify OAuth Login
```powershell
python main.py --init-db
python main.py --test-email your_email@gmail.com
```
On the first run, a browser window opens for Gmail OAuth authorization and saves `token.json` locally.

---

## Running Task 1

### Option A: Streamlit Marketing Workspace (UI)
```powershell
streamlit run dashboard.py
```
- **Overview:** KPI cards, Mon–Sat dispatch spread, recent activity, live stock snapshot
- **Customers:** Directory with search/filters, single add, CSV bulk import, and subscription badges
- **Inventory:** Live stock editor (changes immediately reflect in emails)
- **Email campaigns:** Test email sender (blocks unsubscribed addresses), Mon–Sat batch runner (Dry Run / Real), and Light/Dark HTML email preview
- **Activity logs:** Per-recipient send counts and searchable delivery history

### Option B: CLI & Automated Scheduler
- **Start continuous Mon–Sat 09:30 AM scheduler + FastAPI unsubscribe server:**
  ```powershell
  python main.py --serve
  ```
- **Preview or run today's batch manually:**
  ```powershell
  python main.py --send-now --dry-run
  python main.py --send-now
  ```
- **Manage & inspect data:**
  ```powershell
  python main.py --add-client "Client Name" client@example.com
  python main.py --import-clients data/sample_clients.csv
  python main.py --import-stock data/sample_stock.csv
  python main.py --clients
  python main.py --stock
  python main.py --logs
  ```

---

## Running Tests
```powershell
python -m unittest discover -s tests -v
```
