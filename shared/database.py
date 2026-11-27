"""Shared SQLite database setup, seeding, CSV import, and query helpers."""

from contextlib import contextmanager
import csv
from datetime import datetime
from pathlib import Path
import secrets
import sqlite3
from typing import Any, Iterator, Optional

from shared.config import DB_PATH


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection that commits/rolls back and closes cleanly."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate_email_logs_if_needed(conn: sqlite3.Connection) -> None:
    """Upgrade older email_logs schema (nullable client_id + send_type column) safely."""
    cols = conn.execute("PRAGMA table_info(email_logs)").fetchall()
    if not cols:
        return

    col_names = {c["name"] for c in cols}
    client_id_notnull = any(c["name"] == "client_id" and c["notnull"] == 1 for c in cols)

    if "send_type" in col_names and not client_id_notnull:
        return

    conn.execute("PRAGMA foreign_keys = OFF;")
    conn.executescript(
        """
        ALTER TABLE email_logs RENAME TO email_logs_legacy;

        CREATE TABLE email_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            client_email TEXT NOT NULL,
            week_key TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('SENT', 'FAILED')),
            send_type TEXT NOT NULL DEFAULT 'BATCH' CHECK(send_type IN ('BATCH', 'TEST')),
            message_id TEXT,
            error_message TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
        );

        INSERT INTO email_logs (id, client_id, client_email, week_key, sent_at, status, send_type, message_id, error_message)
        SELECT id, client_id, client_email, week_key, sent_at, status, 'BATCH', message_id, error_message
        FROM email_logs_legacy;

        DROP TABLE email_logs_legacy;
        """
    )
    conn.execute("PRAGMA foreign_keys = ON;")


def init_db() -> None:
    """Create database tables and indexes if they do not exist."""
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                assigned_day INTEGER NOT NULL CHECK(assigned_day BETWEEN 0 AND 5),
                unsubscribe_token TEXT NOT NULL UNIQUE,
                is_unsubscribed INTEGER NOT NULL DEFAULT 0,
                unsubscribed_at TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS stock_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                category TEXT NOT NULL,
                unit TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                in_stock INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS email_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                client_email TEXT NOT NULL,
                week_key TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('SENT', 'FAILED')),
                send_type TEXT NOT NULL DEFAULT 'BATCH' CHECK(send_type IN ('BATCH', 'TEST')),
                message_id TEXT,
                error_message TEXT,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
            );
            """
        )
        _migrate_email_logs_if_needed(conn)
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_clients_day_unsub
                ON clients(assigned_day, is_unsubscribed);

            CREATE INDEX IF NOT EXISTS idx_logs_client_week_status
                ON email_logs(client_id, week_key, status, send_type);

            CREATE INDEX IF NOT EXISTS idx_logs_email
                ON email_logs(client_email);

            CREATE TABLE IF NOT EXISTS flyer_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_key TEXT NOT NULL,
                style TEXT NOT NULL,
                layout TEXT NOT NULL DEFAULT 'Card List',
                campaign_theme TEXT NOT NULL,
                headline TEXT NOT NULL,
                offer_text TEXT NOT NULL,
                caption TEXT NOT NULL,
                image_path TEXT NOT NULL,
                ai_source TEXT NOT NULL,
                item_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS whatsapp_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone_e164 TEXT NOT NULL UNIQUE,
                opted_in INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS social_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flyer_id INTEGER,
                channel TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                target TEXT NOT NULL,
                external_id TEXT,
                post_url TEXT,
                details TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (flyer_id) REFERENCES flyer_logs(id) ON DELETE SET NULL
            );
            """
        )
        flyer_cols = {
            c["name"] for c in conn.execute("PRAGMA table_info(flyer_logs)").fetchall()
        }
        if flyer_cols and "layout" not in flyer_cols:
            conn.execute(
                "ALTER TABLE flyer_logs ADD COLUMN layout TEXT NOT NULL DEFAULT 'Card List'"
            )


def _local_now_iso() -> str:
    """Return consistent local timestamp string matching scheduler day/week checks."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_current_week_key(dt: Optional[datetime] = None) -> str:
    """Return ISO year-week identifier (e.g., '2026-W48') to enforce 1 email/client/week."""
    target = dt or datetime.now()
    iso = target.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def get_client_by_email(email: str) -> Optional[dict[str, Any]]:
    """Look up a client by email address (case-insensitive)."""
    normalized = email.strip().lower()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE LOWER(email) = ?", (normalized,)
        ).fetchone()
        return dict(row) if row else None


def add_client(name: str, email: str, assigned_day: Optional[int] = None) -> dict[str, Any]:
    """Insert a new client, auto-balancing across Monday (0) to Saturday (5) active load."""
    normalized_email = email.strip().lower()
    with get_connection() as conn:
        if assigned_day is None:
            counts = {day: 0 for day in range(6)}
            rows = conn.execute(
                """
                SELECT assigned_day, COUNT(*) AS cnt
                FROM clients
                WHERE is_unsubscribed = 0
                GROUP BY assigned_day
                """
            ).fetchall()
            for row in rows:
                counts[row["assigned_day"]] = row["cnt"]
            assigned_day = min(counts, key=counts.get)

        if not 0 <= assigned_day <= 5:
            raise ValueError("assigned_day must be between 0 (Monday) and 5 (Saturday)")

        token = secrets.token_urlsafe(24)
        now = _local_now_iso()
        conn.execute(
            """
            INSERT INTO clients (name, email, assigned_day, unsubscribe_token, is_unsubscribed, created_at)
            VALUES (?, ?, ?, ?, 0, ?)
            """,
            (name.strip(), normalized_email, assigned_day, token, now),
        )
        row = conn.execute(
            "SELECT * FROM clients WHERE email = ?", (normalized_email,)
        ).fetchone()
        return dict(row)


def add_or_update_stock_item(
    item_name: str,
    category: str,
    unit: str,
    price: float,
    quantity: int,
    in_stock: bool = True,
    item_id: Optional[int] = None,
) -> dict[str, Any]:
    """Insert a new stock item or update an existing one by ID."""
    now = _local_now_iso()
    in_stock_int = 1 if (in_stock and quantity > 0) else 0
    with get_connection() as conn:
        if item_id is not None:
            conn.execute(
                """
                UPDATE stock_items
                SET item_name = ?, category = ?, unit = ?, price = ?,
                    quantity = ?, in_stock = ?, updated_at = ?
                WHERE id = ?
                """,
                (item_name.strip(), category.strip(), unit.strip(), float(price), int(quantity), in_stock_int, now, item_id),
            )
            row = conn.execute("SELECT * FROM stock_items WHERE id = ?", (item_id,)).fetchone()
        else:
            cur = conn.execute(
                """
                INSERT INTO stock_items (item_name, category, unit, price, quantity, in_stock, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (item_name.strip(), category.strip(), unit.strip(), float(price), int(quantity), in_stock_int, now),
            )
            row = conn.execute("SELECT * FROM stock_items WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


def import_clients_csv(csv_path: Path) -> dict[str, int]:
    """Import clients from a CSV file (columns: name, email, optional assigned_day)."""
    added = 0
    skipped = 0
    with open(csv_path, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("name") or "").strip()
            email = (row.get("email") or "").strip().lower()
            if not name or not email:
                skipped += 1
                continue
            raw_day = (row.get("assigned_day") or "").strip()
            day = int(raw_day) if raw_day.isdigit() else None
            try:
                add_client(name=name, email=email, assigned_day=day)
                added += 1
            except sqlite3.IntegrityError:
                skipped += 1
    return {"added": added, "skipped": skipped}


def import_stock_csv(csv_path: Path) -> dict[str, int]:
    """Import stock items from a CSV file (item_name, category, unit, price, quantity, in_stock)."""
    added = 0
    skipped = 0
    with open(csv_path, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item_name = (row.get("item_name") or "").strip()
            if not item_name:
                skipped += 1
                continue
            category = (row.get("category") or "General").strip()
            unit = (row.get("unit") or "Unit").strip()
            price = float(row.get("price") or 0)
            quantity = int(row.get("quantity") or 0)
            in_stock = str(row.get("in_stock", "1")).strip().lower() in ("1", "true", "yes")
            add_or_update_stock_item(item_name, category, unit, price, quantity, in_stock=in_stock)
            added += 1
    return {"added": added, "skipped": skipped}


def seed_sample_data() -> dict[str, int]:
    """Seed realistic sample stock items and clients if tables are empty."""
    now = _local_now_iso()
    added_stock = 0
    added_clients = 0

    with get_connection() as conn:
        stock_count = conn.execute("SELECT COUNT(*) FROM stock_items").fetchone()[0]
        if stock_count == 0:
            sample_stock = [
                ("A4 Copier Paper (75 GSM)", "Office Paper", "500 Sheets / Ream", 245.00, 1200, 1),
                ("A4 Copier Paper (80 GSM)", "Office Paper", "500 Sheets / Ream", 275.00, 850, 1),
                ("A3 Printing Paper (80 GSM)", "Office Paper", "500 Sheets / Ream", 540.00, 420, 1),
                ("Virgin Kraft Paper Roll (120 GSM)", "Packaging", "50 Kg Roll", 3150.00, 95, 1),
                ("Duplex Board Grey Back (300 GSM)", "Packaging Board", "100 Sheets / Bundle", 1850.00, 210, 1),
                ("Art Card Glossy (300 GSM)", "Printing Board", "100 Sheets / Packet", 1420.00, 340, 1),
                ("Thermal POS Paper Roll (80mm x 50m)", "Thermal Paper", "Box of 50 Rolls", 1650.00, 160, 1),
                ("3-Ply Corrugated Sheet (48x36 in)", "Corrugated", "25 Sheets / Bundle", 1980.00, 75, 1),
                ("Maplitho Cream Paper (70 GSM)", "Printing Paper", "500 Sheets / Ream", 310.00, 0, 0),
            ]
            conn.executemany(
                """
                INSERT INTO stock_items (item_name, category, unit, price, quantity, in_stock, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [(*item, now) for item in sample_stock],
            )
            added_stock = len(sample_stock)

        client_count = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        if client_count == 0:
            sample_clients = [
                ("Apex Print House", "apex.prints.demo@example.com", 0),
                ("Metro Packaging Co.", "metro.packaging.demo@example.com", 1),
                ("Bright Stationery Mart", "bright.stationery.demo@example.com", 2),
                ("Zenith Offset Printers", "zenith.offset.demo@example.com", 3),
                ("Prime Box & Cartons", "prime.cartons.demo@example.com", 4),
                ("Sunrise Publishers", "sunrise.pub.demo@example.com", 5),
            ]
            for name, email, day in sample_clients:
                conn.execute(
                    """
                    INSERT INTO clients (name, email, assigned_day, unsubscribe_token, is_unsubscribed, created_at)
                    VALUES (?, ?, ?, ?, 0, ?)
                    """,
                    (name, email, day, secrets.token_urlsafe(24), now),
                )
            added_clients = len(sample_clients)

    return {"stock_added": added_stock, "clients_added": added_clients}


def get_all_clients() -> list[dict[str, Any]]:
    """Return all clients ordered by assigned day and ID."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM clients ORDER BY assigned_day ASC, id ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_stock_items() -> list[dict[str, Any]]:
    """Return all stock items (both in-stock and out-of-stock)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM stock_items ORDER BY in_stock DESC, category ASC, item_name ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_in_stock_items() -> list[dict[str, Any]]:
    """Return all currently in-stock items ordered by category and name."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, item_name, category, unit, price, quantity
            FROM stock_items
            WHERE in_stock = 1 AND quantity > 0
            ORDER BY category ASC, item_name ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def count_sent_today(date_str: Optional[str] = None) -> int:
    """Return number of emails (batch + test) successfully sent today."""
    day_prefix = date_str or datetime.now().strftime("%Y-%m-%d")
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM email_logs WHERE status = 'SENT' AND sent_at LIKE ?",
            (f"{day_prefix}%",),
        ).fetchone()
        return int(row["cnt"])


def get_clients_due_for_day(
    day_of_week: int, week_key: str, limit: int
) -> list[dict[str, Any]]:
    """Return subscribed clients assigned to `day_of_week` not yet BATCH-emailed in `week_key`."""
    if limit <= 0:
        return []
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.*
            FROM clients c
            WHERE c.assigned_day = ?
              AND c.is_unsubscribed = 0
              AND NOT EXISTS (
                  SELECT 1 FROM email_logs l
                  WHERE l.client_id = c.id
                    AND l.week_key = ?
                    AND l.status = 'SENT'
                    AND l.send_type = 'BATCH'
              )
            ORDER BY c.id ASC
            LIMIT ?
            """,
            (day_of_week, week_key, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def log_email_attempt(
    client_id: Optional[int],
    client_email: str,
    week_key: str,
    status: str,
    send_type: str = "BATCH",
    message_id: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Record a send attempt (BATCH or TEST, SENT or FAILED) in email_logs."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO email_logs (client_id, client_email, week_key, sent_at, status, send_type, message_id, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                client_id,
                client_email.strip().lower(),
                week_key,
                _local_now_iso(),
                status,
                send_type,
                message_id,
                error_message,
            ),
        )


def unsubscribe_by_token(token: str) -> dict[str, Any]:
    """Mark a client as unsubscribed using their unique token."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, email, is_unsubscribed FROM clients WHERE unsubscribe_token = ?",
            (token,),
        ).fetchone()
        if not row:
            return {"status": "not_found"}

        if row["is_unsubscribed"]:
            return {
                "status": "already_unsubscribed",
                "name": row["name"],
                "email": row["email"],
            }

        conn.execute(
            """
            UPDATE clients
            SET is_unsubscribed = 1, unsubscribed_at = ?
            WHERE id = ?
            """,
            (_local_now_iso(), row["id"]),
        )
        return {
            "status": "unsubscribed",
            "name": row["name"],
            "email": row["email"],
        }


def get_recent_logs(limit: int = 50) -> list[dict[str, Any]]:
    """Fetch recent email send logs joined with client names."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT l.id,
                   COALESCE(c.name, 'Test / Ad-hoc') AS client_name,
                   l.client_email,
                   l.week_key,
                   l.sent_at,
                   l.status,
                   l.send_type,
                   l.message_id,
                   l.error_message
            FROM email_logs l
            LEFT JOIN clients c ON c.id = l.client_id
            ORDER BY l.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_send_counts_by_recipient() -> list[dict[str, Any]]:
    """Aggregate total send counts (total, batch, test, failed) per recipient email."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT LOWER(l.client_email) AS client_email,
                   COALESCE(MAX(c.name), 'Test / Ad-hoc') AS client_name,
                   SUM(CASE WHEN l.status = 'SENT' THEN 1 ELSE 0 END) AS total_sent,
                   SUM(CASE WHEN l.status = 'SENT' AND l.send_type = 'BATCH' THEN 1 ELSE 0 END) AS batch_sent,
                   SUM(CASE WHEN l.status = 'SENT' AND l.send_type = 'TEST' THEN 1 ELSE 0 END) AS test_sent,
                   SUM(CASE WHEN l.status = 'FAILED' THEN 1 ELSE 0 END) AS total_failed,
                   MAX(l.sent_at) AS last_sent_at
            FROM email_logs l
            LEFT JOIN clients c ON c.id = l.client_id
            GROUP BY LOWER(l.client_email)
            ORDER BY total_sent DESC, last_sent_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_summary_stats() -> dict[str, Any]:
    """Return high-level counts for clients, stock, and logs."""
    with get_connection() as conn:
        total_clients = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        active_clients = conn.execute(
            "SELECT COUNT(*) FROM clients WHERE is_unsubscribed = 0"
        ).fetchone()[0]
        unsubscribed = total_clients - active_clients
        in_stock = conn.execute(
            "SELECT COUNT(*) FROM stock_items WHERE in_stock = 1 AND quantity > 0"
        ).fetchone()[0]
        total_sent = conn.execute(
            "SELECT COUNT(*) FROM email_logs WHERE status = 'SENT'"
        ).fetchone()[0]
        batch_sent = conn.execute(
            "SELECT COUNT(*) FROM email_logs WHERE status = 'SENT' AND send_type = 'BATCH'"
        ).fetchone()[0]
        test_sent = conn.execute(
            "SELECT COUNT(*) FROM email_logs WHERE status = 'SENT' AND send_type = 'TEST'"
        ).fetchone()[0]
        total_failed = conn.execute(
            "SELECT COUNT(*) FROM email_logs WHERE status = 'FAILED'"
        ).fetchone()[0]

    return {
        "total_clients": total_clients,
        "active_clients": active_clients,
        "unsubscribed_clients": unsubscribed,
        "in_stock_items": in_stock,
        "emails_sent": total_sent,
        "batch_sent": batch_sent,
        "test_sent": test_sent,
        "emails_failed": total_failed,
    }


def log_flyer_generation(
    week_key: str,
    style: str,
    campaign_theme: str,
    headline: str,
    offer_text: str,
    caption: str,
    image_path: str,
    ai_source: str,
    item_count: int,
    layout: str = "Card List",
) -> dict[str, Any]:
    """Record a generated promotional flyer in flyer_logs."""
    now = _local_now_iso()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO flyer_logs (
                week_key, style, layout, campaign_theme, headline, offer_text,
                caption, image_path, ai_source, item_count, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                week_key,
                style,
                layout,
                campaign_theme,
                headline,
                offer_text,
                caption,
                image_path,
                ai_source,
                item_count,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM flyer_logs WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


def count_generated_flyers() -> int:
    """Return total number of flyers recorded in flyer_logs."""
    with get_connection() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM flyer_logs").fetchone()[0])


def get_recent_flyers(limit: int = 20) -> list[dict[str, Any]]:
    """Return recently generated flyers ordered newest first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM flyer_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def add_whatsapp_contact(name: str, phone: str, opted_in: bool = True) -> dict[str, Any]:
    """Insert or update an opted-in WhatsApp contact (digits only, E.164 without '+')."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 8:
        raise ValueError("Phone number must contain country code and at least 8 digits (e.g., 919820000000).")
    now = _local_now_iso()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO whatsapp_contacts (name, phone_e164, opted_in, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(phone_e164) DO UPDATE SET
                name = excluded.name,
                opted_in = excluded.opted_in
            """,
            (name.strip(), digits, 1 if opted_in else 0, now),
        )
        row = conn.execute(
            "SELECT * FROM whatsapp_contacts WHERE phone_e164 = ?", (digits,)
        ).fetchone()
        return dict(row)


def get_whatsapp_contacts(opted_in_only: bool = False) -> list[dict[str, Any]]:
    """Return WhatsApp contacts ordered newest first."""
    query = "SELECT * FROM whatsapp_contacts"
    if opted_in_only:
        query += " WHERE opted_in = 1"
    query += " ORDER BY id DESC"
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(query).fetchall()]


def set_whatsapp_opt_in(contact_id: int, opted_in: bool) -> None:
    """Update opt-in consent status for a WhatsApp contact."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE whatsapp_contacts SET opted_in = ? WHERE id = ?",
            (1 if opted_in else 0, contact_id),
        )


def log_social_distribution(
    channel: str,
    mode: str,
    status: str,
    target: str,
    flyer_id: Optional[int] = None,
    external_id: Optional[str] = None,
    post_url: Optional[str] = None,
    details: Optional[str] = None,
) -> dict[str, Any]:
    """Record a social distribution event in social_logs."""
    now = _local_now_iso()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO social_logs (
                flyer_id, channel, mode, status, target, external_id, post_url, details, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (flyer_id, channel, mode, status, target, external_id, post_url, details, now),
        )
        row = conn.execute("SELECT * FROM social_logs WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


def get_recent_social_logs(limit: int = 50) -> list[dict[str, Any]]:
    """Return recent social distribution logs ordered newest first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM social_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
