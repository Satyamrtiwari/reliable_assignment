"""FastAPI micro-server handling client unsubscribe requests and log inspection."""

from contextlib import asynccontextmanager
import html
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from shared.config import COMPANY_INFO
from shared.database import get_recent_logs, get_summary_stats, init_db, unsubscribe_by_token


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Ensure database schema exists when server starts."""
    init_db()
    yield


app = FastAPI(
    title="Reliable Paper Mart - Unsubscribe & Status Service",
    lifespan=lifespan,
)


@app.get("/")
def health_check() -> dict:
    """Health check and basic campaign stats."""
    return {
        "service": COMPANY_INFO["name"],
        "status": "running",
        "stats": get_summary_stats(),
    }


@app.get("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe_page(token: str) -> HTMLResponse:
    """Handle browser click on the unsubscribe link from an email."""
    result = unsubscribe_by_token(token)
    status = result["status"]

    if status == "not_found":
        return HTMLResponse(
            content=_render_page(
                "Invalid Unsubscribe Link",
                "We could not find a matching subscription for this link.",
                is_error=True,
            ),
            status_code=404,
        )

    safe_email = html.escape(result["email"])
    if status == "already_unsubscribed":
        return HTMLResponse(
            content=_render_page(
                "Already Unsubscribed",
                f"<strong>{safe_email}</strong> is already unsubscribed from {COMPANY_INFO['name']} weekly stock updates.",
            )
        )

    return HTMLResponse(
        content=_render_page(
            "Unsubscribed Successfully",
            f"<strong>{safe_email}</strong> has been removed from {COMPANY_INFO['name']} weekly stock emails. You will not receive future updates.",
        )
    )


@app.post("/unsubscribe/{token}")
def unsubscribe_one_click(token: str) -> JSONResponse:
    """Support RFC 8058 one-click unsubscribe POST requests."""
    result = unsubscribe_by_token(token)
    code = 404 if result["status"] == "not_found" else 200
    return JSONResponse(content=result, status_code=code)


@app.get("/logs")
def view_logs(limit: int = 50) -> dict:
    """Return recent email send logs."""
    return {"logs": get_recent_logs(limit=limit)}


def _render_page(title: str, message: str, is_error: bool = False) -> str:
    accent = "#b91c1c" if is_error else "#15803d"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(title)} - {COMPANY_INFO['name']}</title>
</head>
<body style="font-family: Arial, sans-serif; background:#f4f6f9; padding:40px 16px; margin:0;">
  <div style="max-width:480px; margin:0 auto; background:#fff; padding:28px; border-radius:8px; border:1px solid #e2e8f0;">
    <h2 style="margin:0 0 12px 0; color:{accent};">{html.escape(title)}</h2>
    <p style="margin:0 0 16px 0; color:#334155; line-height:1.5;">{message}</p>
    <hr style="border:none; border-top:1px solid #e2e8f0; margin:16px 0;" />
    <p style="margin:0; font-size:12px; color:#64748b;">
      {COMPANY_INFO['name']} &bull; {COMPANY_INFO['email']} &bull; {COMPANY_INFO['phone']}
    </p>
  </div>
</body>
</html>"""
