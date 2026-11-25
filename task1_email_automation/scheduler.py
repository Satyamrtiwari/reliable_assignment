"""Daily Mon-Sat batch email runner and APScheduler configuration."""

import logging
import time
from datetime import datetime
from typing import Any, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from shared.config import (
    BASE_URL,
    COMPANY_INFO,
    DAILY_SEND_LIMIT,
    DAY_NAMES,
    SCHEDULE_HOUR,
    SCHEDULE_MINUTE,
    SEND_DELAY_SECONDS,
)
from shared.database import (
    count_sent_today,
    get_client_by_email,
    get_clients_due_for_day,
    get_current_week_key,
    get_in_stock_items,
    log_email_attempt,
)
from task1_email_automation.email_sender import get_gmail_service, send_email
from task1_email_automation.email_template import render_stock_email

logger = logging.getLogger(__name__)


def send_test_stock_email(recipient: str) -> dict[str, Any]:
    """Send a single TEST stock email, blocking unsubscribed clients and logging the attempt."""
    recipient_clean = recipient.strip().lower()
    existing = get_client_by_email(recipient_clean)
    if existing and existing["is_unsubscribed"]:
        logger.info("Blocked test send to unsubscribed client %s", recipient_clean)
        return {
            "status": "blocked_unsubscribed",
            "email": recipient_clean,
            "unsubscribed_at": existing.get("unsubscribed_at"),
        }

    stock_items = get_in_stock_items()
    if not stock_items:
        return {"status": "no_stock", "email": recipient_clean}

    week_key = get_current_week_key()
    unsub_token = existing["unsubscribe_token"] if existing else "sample-test-token"
    unsubscribe_url = f"{BASE_URL.rstrip('/')}/unsubscribe/{unsub_token}"
    html_body, text_body = render_stock_email(
        client_name=existing["name"] if existing else "Test Recipient",
        stock_items=stock_items,
        unsubscribe_url=unsubscribe_url,
    )

    try:
        service = get_gmail_service()
        subject = f"[TEST] Weekly Stock Update ({datetime.now().strftime('%d %b %Y')}) - {COMPANY_INFO['name']}"
        msg_id = send_email(
            service=service,
            to_email=recipient_clean,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            unsubscribe_url=unsubscribe_url,
        )
        log_email_attempt(
            client_id=existing["id"] if existing else None,
            client_email=recipient_clean,
            week_key=week_key,
            status="SENT",
            send_type="TEST",
            message_id=msg_id,
        )
        return {"status": "sent", "email": recipient_clean, "message_id": msg_id}
    except Exception as exc:
        log_email_attempt(
            client_id=existing["id"] if existing else None,
            client_email=recipient_clean,
            week_key=week_key,
            status="FAILED",
            send_type="TEST",
            error_message=str(exc),
        )
        return {"status": "failed", "email": recipient_clean, "error": str(exc)}


def run_daily_batch(
    day_override: Optional[int] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Send weekly stock emails to clients assigned to today's Mon-Sat batch."""
    now = datetime.now()
    target_day = now.weekday() if day_override is None else day_override

    if target_day == 6:
        logger.info("Today is Sunday; emails are scheduled Monday-Saturday only.")
        return {"status": "skipped_sunday", "sent": 0, "failed": 0}

    if not 0 <= target_day <= 5:
        raise ValueError("day_override must be between 0 (Monday) and 5 (Saturday)")

    week_key = get_current_week_key(now)
    day_name = DAY_NAMES[target_day]

    stock_items = get_in_stock_items()
    if not stock_items:
        logger.warning("No items in stock; skipping email batch for %s.", day_name)
        return {"status": "no_stock", "sent": 0, "failed": 0}

    sent_today = count_sent_today()
    remaining_quota = max(0, DAILY_SEND_LIMIT - sent_today)
    if remaining_quota == 0:
        logger.warning(
            "Daily limit (%d) reached; halting batch for %s.", DAILY_SEND_LIMIT, day_name
        )
        return {"status": "quota_reached", "sent": 0, "failed": 0}

    due_clients = get_clients_due_for_day(
        day_of_week=target_day, week_key=week_key, limit=remaining_quota
    )
    if not due_clients:
        logger.info("No pending clients due for %s (%s).", day_name, week_key)
        return {"status": "nothing_due", "sent": 0, "failed": 0}

    service = None if dry_run else get_gmail_service()
    subject = f"Weekly Stock Availability Update ({now.strftime('%d %b %Y')}) - {COMPANY_INFO['name']}"

    sent_count = 0
    failed_count = 0

    for idx, client in enumerate(due_clients):
        unsubscribe_url = f"{BASE_URL.rstrip('/')}/unsubscribe/{client['unsubscribe_token']}"
        html_body, text_body = render_stock_email(
            client_name=client["name"],
            stock_items=stock_items,
            unsubscribe_url=unsubscribe_url,
        )

        if dry_run:
            logger.info(
                "[DRY RUN] Would send to %s <%s> (%s)",
                client["name"],
                client["email"],
                day_name,
            )
            sent_count += 1
            continue

        try:
            msg_id = send_email(
                service=service,
                to_email=client["email"],
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                unsubscribe_url=unsubscribe_url,
            )
            log_email_attempt(
                client_id=client["id"],
                client_email=client["email"],
                week_key=week_key,
                status="SENT",
                message_id=msg_id,
            )
            sent_count += 1
            logger.info("Sent to %s (message_id=%s)", client["email"], msg_id)
        except Exception as exc:
            log_email_attempt(
                client_id=client["id"],
                client_email=client["email"],
                week_key=week_key,
                status="FAILED",
                error_message=str(exc),
            )
            failed_count += 1
            logger.error("Failed sending to %s: %s", client["email"], exc)

        # Gentle pacing between sends to stay well within Gmail rate limits
        if idx < len(due_clients) - 1 and SEND_DELAY_SECONDS > 0:
            time.sleep(SEND_DELAY_SECONDS)

    return {
        "status": "completed",
        "day": day_name,
        "week_key": week_key,
        "sent": sent_count,
        "failed": failed_count,
    }


def start_scheduler() -> BackgroundScheduler:
    """Start APScheduler to run the stock email batch Monday-Saturday."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_daily_batch,
        trigger=CronTrigger(day_of_week="mon-sat", hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE),
        id="weekly_stock_email_batch",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started: runs Mon-Sat at %02d:%02d.",
        SCHEDULE_HOUR,
        SCHEDULE_MINUTE,
    )
    return scheduler
