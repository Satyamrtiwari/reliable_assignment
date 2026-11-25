"""Automated unit tests for Task 1 (DB batching, deduplication, unsubscribe, template, API, quota)."""

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Point DB_PATH to a temporary file before importing project modules
_TMP_DIR = tempfile.TemporaryDirectory()
os.environ["DB_PATH"] = str(Path(_TMP_DIR.name) / "test_marketing.db")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from shared import database  # noqa: E402
from task1_email_automation import scheduler  # noqa: E402
from task1_email_automation.email_template import render_stock_email  # noqa: E402
from task1_email_automation.unsubscribe_server import app  # noqa: E402


class TestTask1System(unittest.TestCase):
    def setUp(self) -> None:
        if database.DB_PATH.exists():
            database.DB_PATH.unlink()
        database.init_db()
        database.seed_sample_data()

    def test_seed_distributes_clients_across_mon_to_sat(self) -> None:
        with database.get_connection() as conn:
            days = [
                r["assigned_day"]
                for r in conn.execute("SELECT assigned_day FROM clients").fetchall()
            ]
        self.assertEqual(sorted(days), [0, 1, 2, 3, 4, 5])

    def test_auto_balance_ignores_unsubscribed_clients(self) -> None:
        with database.get_connection() as conn:
            mon_client = conn.execute(
                "SELECT unsubscribe_token FROM clients WHERE assigned_day = 0"
            ).fetchone()
        database.unsubscribe_by_token(mon_client["unsubscribe_token"])

        new_client = database.add_client("New Mon Client", "newmon@example.com")
        self.assertEqual(new_client["assigned_day"], 0)

    def test_out_of_stock_items_excluded(self) -> None:
        items = database.get_in_stock_items()
        names = [i["item_name"] for i in items]
        self.assertIn("A4 Copier Paper (75 GSM)", names)
        self.assertNotIn("Maplitho Cream Paper (70 GSM)", names)

    def test_unsubscribe_get_and_post_exclude_client(self) -> None:
        c1 = database.add_client("Unsub GET", "unsub.get@example.com", assigned_day=0)
        c2 = database.add_client("Unsub POST", "unsub.post@example.com", assigned_day=0)

        http_client = TestClient(app)

        resp1 = http_client.get(f"/unsubscribe/{c1['unsubscribe_token']}")
        self.assertEqual(resp1.status_code, 200)
        self.assertIn("Unsubscribed Successfully", resp1.text)

        resp2 = http_client.get(f"/unsubscribe/{c1['unsubscribe_token']}")
        self.assertEqual(resp2.status_code, 200)
        self.assertIn("Already Unsubscribed", resp2.text)

        resp_post = http_client.post(f"/unsubscribe/{c2['unsubscribe_token']}")
        self.assertEqual(resp_post.status_code, 200)
        self.assertEqual(resp_post.json()["status"], "unsubscribed")

        due = database.get_clients_due_for_day(0, "2026-W48", limit=100)
        due_emails = [c["email"] for c in due]
        self.assertNotIn("unsub.get@example.com", due_emails)
        self.assertNotIn("unsub.post@example.com", due_emails)

    def test_one_email_per_week_deduplication(self) -> None:
        with patch("task1_email_automation.scheduler.get_gmail_service", return_value=object()), patch(
            "task1_email_automation.scheduler.send_email", return_value="mock-msg-123"
        ) as mock_send:
            res1 = scheduler.run_daily_batch(day_override=0, dry_run=False)
            self.assertEqual(res1["sent"], 1)
            self.assertEqual(mock_send.call_count, 1)

            res2 = scheduler.run_daily_batch(day_override=0, dry_run=False)
            self.assertEqual(res2["status"], "nothing_due")
            self.assertEqual(res2["sent"], 0)
            self.assertEqual(mock_send.call_count, 1)

    def test_test_sends_are_logged_counted_and_do_not_block_batch(self) -> None:
        # Log two TEST emails to Monday's client and one TEST email to an ad-hoc address
        mon_client = database.get_client_by_email("apex.prints.demo@example.com")
        week_key = database.get_current_week_key()
        database.log_email_attempt(mon_client["id"], mon_client["email"], week_key, "SENT", send_type="TEST", message_id="t1")
        database.log_email_attempt(mon_client["id"], mon_client["email"], week_key, "SENT", send_type="TEST", message_id="t2")
        database.log_email_attempt(None, "adhoc@example.com", week_key, "SENT", send_type="TEST", message_id="t3")

        stats = database.get_summary_stats()
        self.assertEqual(stats["emails_sent"], 3)
        self.assertEqual(stats["test_sent"], 3)
        self.assertEqual(stats["batch_sent"], 0)

        counts = {r["client_email"]: r for r in database.get_send_counts_by_recipient()}
        self.assertEqual(counts["apex.prints.demo@example.com"]["total_sent"], 2)
        self.assertEqual(counts["adhoc@example.com"]["total_sent"], 1)

        # Client must STILL receive their weekly BATCH email
        due = database.get_clients_due_for_day(0, week_key, limit=100)
        self.assertIn("apex.prints.demo@example.com", [c["email"] for c in due])

    def test_test_send_blocked_for_unsubscribed_client(self) -> None:
        client = database.add_client("Opted Out", "optedout@example.com", assigned_day=0)
        database.unsubscribe_by_token(client["unsubscribe_token"])
        with patch("task1_email_automation.scheduler.send_email") as mock_send:
            res = scheduler.send_test_stock_email("optedout@example.com")
            self.assertEqual(res["status"], "blocked_unsubscribed")
            mock_send.assert_not_called()

    def test_legacy_db_migration_preserves_rows(self) -> None:
        if database.DB_PATH.exists():
            database.DB_PATH.unlink()
        conn = sqlite3.connect(database.DB_PATH)
        conn.executescript(
            """
            CREATE TABLE clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                assigned_day INTEGER NOT NULL,
                unsubscribe_token TEXT NOT NULL UNIQUE,
                is_unsubscribed INTEGER NOT NULL DEFAULT 0,
                unsubscribed_at TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE email_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                client_email TEXT NOT NULL,
                week_key TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                status TEXT NOT NULL,
                message_id TEXT,
                error_message TEXT
            );
            INSERT INTO clients VALUES (1, 'Legacy Co', 'legacy@example.com', 0, 'tok1', 0, NULL, '2026-11-25 09:00:00');
            INSERT INTO email_logs VALUES (1, 1, 'legacy@example.com', '2026-W48', '2026-11-25 09:05:00', 'SENT', 'm1', NULL);
            """
        )
        conn.commit()
        conn.close()

        database.init_db()
        logs = database.get_recent_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["send_type"], "BATCH")
        self.assertEqual(logs[0]["message_id"], "m1")

    def test_daily_quota_limit_enforced(self) -> None:
        database.add_client("Mon Extra", "mon.extra@example.com", assigned_day=0)
        with patch.object(scheduler, "DAILY_SEND_LIMIT", 1), patch(
            "task1_email_automation.scheduler.get_gmail_service", return_value=object()
        ), patch("task1_email_automation.scheduler.send_email", return_value="mock-msg"):
            res1 = scheduler.run_daily_batch(day_override=0, dry_run=False)
            self.assertEqual(res1["sent"], 1)
            res2 = scheduler.run_daily_batch(day_override=0, dry_run=False)
            self.assertEqual(res2["status"], "quota_reached")

    def test_sunday_skipped(self) -> None:
        res = scheduler.run_daily_batch(day_override=6, dry_run=True)
        self.assertEqual(res["status"], "skipped_sunday")

    def test_render_stock_email_contains_items_and_unsubscribe(self) -> None:
        items = database.get_in_stock_items()
        html_body, text_body = render_stock_email(
            "Apex Print House", items, "http://localhost:8000/unsubscribe/abc"
        )
        self.assertIn("Reliable Paper Mart", html_body)
        self.assertIn("A4 Copier Paper (75 GSM)", html_body)
        self.assertIn("http://localhost:8000/unsubscribe/abc", html_body)
        self.assertIn("http://localhost:8000/unsubscribe/abc", text_body)

    def test_csv_import_clients(self) -> None:
        csv_file = Path(_TMP_DIR.name) / "clients.csv"
        csv_file.write_text(
            "name,email,assigned_day\nCSV Client,csv.client@example.com,3\n",
            encoding="utf-8",
        )
        res = database.import_clients_csv(csv_file)
        self.assertEqual(res, {"added": 1, "skipped": 0})


if __name__ == "__main__":
    unittest.main()
