"""Jinja2 HTML & plain-text email renderer for weekly stock updates."""

from datetime import datetime
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from shared.config import COMPANY_INFO, TEMPLATES_DIR

_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_stock_email(
    client_name: str,
    stock_items: list[dict[str, Any]],
    unsubscribe_url: str,
) -> tuple[str, str]:
    """Render both HTML and plain-text bodies for the weekly stock email."""
    now = datetime.now()
    report_date = now.strftime("%d %b %Y")

    template = _jinja_env.get_template("stock_email.html")
    html_body = template.render(
        company=COMPANY_INFO,
        client_name=client_name,
        stock_items=stock_items,
        report_date=report_date,
        current_year=now.year,
        unsubscribe_url=unsubscribe_url,
    )

    lines = [
        f"{COMPANY_INFO['name']} - Weekly Stock Update ({report_date})",
        "",
        f"Dear {client_name},",
        "",
        "Here are the items currently in stock:",
        "-" * 60,
    ]
    for item in stock_items:
        lines.append(
            f"- {item['item_name']} ({item['category']}) | {item['unit']} | "
            f"INR {item['price']:.2f} | Qty: {item['quantity']}"
        )
    lines.extend(
        [
            "-" * 60,
            "",
            f"Contact us: {COMPANY_INFO['email']} | {COMPANY_INFO['phone']}",
            f"Address: {COMPANY_INFO['address']}",
            "",
            f"To unsubscribe, visit: {unsubscribe_url}",
        ]
    )
    text_body = "\n".join(lines)

    return html_body, text_body
