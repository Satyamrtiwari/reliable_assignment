"""CLI entry point for Reliable Paper Mart Marketing Automation."""

import argparse
import logging
from datetime import datetime
from pathlib import Path

import uvicorn

from shared.config import BASE_URL, COMPANY_INFO, DAY_NAMES, SERVER_HOST, SERVER_PORT
from shared.database import (
    add_client,
    add_whatsapp_contact,
    get_all_clients,
    get_all_stock_items,
    get_in_stock_items,
    get_recent_flyers,
    get_recent_logs,
    get_summary_stats,
    import_clients_csv,
    import_stock_csv,
    init_db,
    seed_sample_data,
)
from task1_email_automation.scheduler import (
    run_daily_batch,
    send_test_stock_email,
    start_scheduler,
)
from task1_email_automation.unsubscribe_server import app as fastapi_app
from task2_ai_flyer.flyer_generator import generate_flyer_image
from task2_ai_flyer.social_distributor import (
    create_group_share_pack,
    post_to_facebook_page,
    send_whatsapp_flyer_broadcast,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def cmd_init_db() -> None:
    """Initialize SQLite schema and seed sample stock & clients."""
    init_db()
    seeded = seed_sample_data()
    stats = get_summary_stats()
    print(f"Database initialized. Seeded: {seeded}")
    print(f"Summary: {stats}")


def cmd_test_email(recipient: str) -> None:
    """Send a single test stock email (blocked if client has unsubscribed)."""
    init_db()
    seed_sample_data()
    result = send_test_stock_email(recipient)
    if result["status"] == "blocked_unsubscribed":
        print(f"Blocked: {result['email']} has unsubscribed and will not be emailed.")
    elif result["status"] == "no_stock":
        print("Skipped: No items currently in stock.")
    elif result["status"] == "sent":
        print(f"Test email sent successfully to {result['email']}! Gmail Message ID: {result['message_id']}")
    else:
        raise RuntimeError(f"Failed to send test email: {result.get('error')}")


def cmd_clients() -> None:
    """Print all clients, their Mon-Sat day assignment, and subscription status."""
    init_db()
    clients = get_all_clients()
    print(f"\n=== Clients ({len(clients)}) ===")
    for c in clients:
        status = "UNSUBSCRIBED" if c["is_unsubscribed"] else "ACTIVE"
        print(
            f"  #{c['id']} | {DAY_NAMES[c['assigned_day']]:9s} | {status:12s} | "
            f"{c['name']} <{c['email']}>"
        )


def cmd_stock() -> None:
    """Print all stock items and availability."""
    init_db()
    items = get_all_stock_items()
    print(f"\n=== Stock Items ({len(items)}) ===")
    for item in items:
        avail = "IN STOCK" if (item["in_stock"] and item["quantity"] > 0) else "OUT OF STOCK"
        print(
            f"  #{item['id']} | {avail:12s} | INR {item['price']:8.2f} | "
            f"Qty: {item['quantity']:4d} | {item['item_name']} ({item['unit']})"
        )


def cmd_logs() -> None:
    """Display summary stats and recent send logs."""
    init_db()
    stats = get_summary_stats()
    print("\n=== Campaign Summary ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    logs = get_recent_logs(limit=25)
    print("\n=== Recent Email Logs ===")
    if not logs:
        print("  No emails logged yet.")
        return
    for row in logs:
        print(
            f"  [{row['sent_at']}] {row['send_type']:5s} | {row['status']:6s} | {row['week_key']} | "
            f"{row['client_name']} <{row['client_email']}>"
            + (f" | msg_id={row['message_id']}" if row["message_id"] else "")
            + (f" | err={row['error_message']}" if row["error_message"] else "")
        )


def cmd_serve() -> None:
    """Start background Mon-Sat scheduler + FastAPI unsubscribe server."""
    init_db()
    scheduler = start_scheduler()
    try:
        uvicorn.run(fastapi_app, host=SERVER_HOST, port=SERVER_PORT)
    finally:
        scheduler.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reliable Paper Mart - Marketing Automation CLI"
    )
    parser.add_argument("--init-db", action="store_true", help="Initialize DB and seed sample data")
    parser.add_argument("--test-email", metavar="EMAIL", help="Send a single test email")
    parser.add_argument("--send-now", action="store_true", help="Run today's Mon-Sat batch immediately")
    parser.add_argument("--day", type=int, choices=range(6), help="Weekday override (0=Mon .. 5=Sat)")
    parser.add_argument("--dry-run", action="store_true", help="Preview batch without sending emails")
    parser.add_argument("--add-client", nargs=2, metavar=("NAME", "EMAIL"), help="Add a client")
    parser.add_argument("--import-clients", metavar="CSV_PATH", help="Import clients from CSV")
    parser.add_argument("--import-stock", metavar="CSV_PATH", help="Import stock items from CSV")
    parser.add_argument("--clients", action="store_true", help="List all clients and schedules")
    parser.add_argument("--stock", action="store_true", help="List all stock items")
    parser.add_argument("--logs", action="store_true", help="Print campaign summary and email logs")
    parser.add_argument("--serve", action="store_true", help="Run scheduler + FastAPI unsubscribe server")
    parser.add_argument("--generate-flyer", action="store_true", help="Generate weekly AI promotional flyer PNG")
    parser.add_argument("--flyer-style", default="Minimal", choices=["Minimal", "Bold", "Fresh"], help="Flyer color style")
    parser.add_argument(
        "--layout",
        default="Auto-Rotate",
        choices=["Auto-Rotate", "Card List", "2-Column Grid", "Featured Spotlight"],
        help="Flyer layout format",
    )
    parser.add_argument("--theme", default="Weekly paper essentials", help="Campaign theme for AI flyer copy")
    parser.add_argument("--add-wa-contact", nargs=2, metavar=("NAME", "PHONE"), help="Add opted-in WhatsApp contact")
    parser.add_argument("--distribute-flyer", action="store_true", help="Distribute latest/new flyer via FB Page, WA Cloud, & Share Pack")

    args = parser.parse_args()

    if args.init_db:
        cmd_init_db()
    elif args.test_email:
        cmd_test_email(args.test_email)
    elif args.add_client:
        init_db()
        client = add_client(args.add_client[0], args.add_client[1], assigned_day=args.day)
        print(
            f"Added client '{client['name']}' <{client['email']}> "
            f"assigned to {DAY_NAMES[client['assigned_day']]}."
        )
    elif args.import_clients:
        init_db()
        print(f"Imported clients: {import_clients_csv(Path(args.import_clients))}")
    elif args.import_stock:
        init_db()
        print(f"Imported stock: {import_stock_csv(Path(args.import_stock))}")
    elif args.clients:
        cmd_clients()
    elif args.stock:
        cmd_stock()
    elif args.send_now:
        init_db()
        result = run_daily_batch(day_override=args.day, dry_run=args.dry_run)
        print(f"Batch result: {result}")
    elif args.logs:
        cmd_logs()
    elif args.serve:
        cmd_serve()
    elif args.generate_flyer:
        init_db()
        seed_sample_data()
        items = get_in_stock_items()
        flyer = generate_flyer_image(
            stock_items=items,
            style=args.flyer_style,
            layout=args.layout,
            campaign_theme=args.theme,
        )
        print(f"Flyer generated: {flyer['image_path']} (Layout: {flyer['layout']}, AI: {flyer['ai_source']})")
        print(f"Headline: {flyer['headline']}")
        print(f"Caption:\n{flyer['caption']}")
    elif args.add_wa_contact:
        init_db()
        contact = add_whatsapp_contact(args.add_wa_contact[0], args.add_wa_contact[1], opted_in=True)
        print(f"Added opted-in WhatsApp contact: {contact['name']} (+{contact['phone_e164']})")
    elif args.distribute_flyer:
        init_db()
        seed_sample_data()
        recent = get_recent_flyers(limit=1)
        if recent and Path(recent[0]["image_path"]).exists():
            flyer = recent[0]
        else:
            flyer = generate_flyer_image(
                stock_items=get_in_stock_items(),
                style=args.flyer_style,
                layout=args.layout,
                campaign_theme=args.theme,
            )
        fb_res = post_to_facebook_page(
            flyer["image_path"], flyer["caption"], flyer_id=flyer.get("id"), dry_run=args.dry_run
        )
        wa_res = send_whatsapp_flyer_broadcast(
            flyer["image_path"], flyer["caption"], flyer_id=flyer.get("id"), dry_run=args.dry_run
        )
        pack = create_group_share_pack(
            flyer["image_path"],
            flyer["caption"],
            flyer_id=flyer.get("id"),
            fb_post_url=fb_res.get("post_url"),
        )
        print(f"Facebook Page: {fb_res.get('status')} ({fb_res.get('post_url') or fb_res.get('details')})")
        print(f"WhatsApp Cloud: {wa_res.get('status')} (sent={wa_res.get('sent', 0)}, failed={wa_res.get('failed', 0)})")
        print(f"Group Share Pack: {pack['pack_dir']}")
        print(f"WhatsApp Click-to-Share URL: {pack['wa_share_url']}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
