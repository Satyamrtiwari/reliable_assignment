"""Policy-compliant social distribution for Task 2 (Facebook Page, WhatsApp Cloud API, & Group Share Packs)."""

import base64
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
import logging
from pathlib import Path
import shutil
from typing import Any, Optional
from urllib.parse import quote

import requests

from shared.config import (
    COMPANY_INFO,
    FB_PAGE_ACCESS_TOKEN,
    FB_PAGE_ID,
    META_GRAPH_API_VERSION,
    SHARE_PACKS_DIR,
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_PHONE_NUMBER_ID,
)
from shared.database import get_whatsapp_contacts, log_social_distribution
from task1_email_automation.email_sender import get_gmail_service

logger = logging.getLogger(__name__)


def _graph_url(path: str) -> str:
    return f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/{path.lstrip('/')}"


def post_to_facebook_page(
    image_path: str | Path,
    caption: str,
    flyer_id: Optional[int] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Publish a promotional flyer image to the configured Facebook Page via official Graph API.

    Note: Meta deprecated and removed the Facebook Groups API (`publish_to_groups`) on
    April 22, 2024 across all Graph API versions. Automated publishing is therefore
    scoped strictly to owned Facebook Pages; Group sharing uses the Group Share Pack.
    """
    img_file = Path(image_path)
    if not img_file.exists():
        raise FileNotFoundError(f"Flyer image not found: {img_file}")

    if dry_run or not FB_PAGE_ID or not FB_PAGE_ACCESS_TOKEN:
        reason = "Dry-run requested" if dry_run else "FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN not configured"
        logged = log_social_distribution(
            flyer_id=flyer_id,
            channel="FACEBOOK_PAGE",
            mode="DRY_RUN",
            status="SIMULATED",
            target=FB_PAGE_ID or "demo_facebook_page",
            details=f"{reason}. Would POST {img_file.name} to /{META_GRAPH_API_VERSION}/<page_id>/photos.",
        )
        return {
            **logged,
            "ok": True,
            "simulated": True,
        }

    url = _graph_url(f"{FB_PAGE_ID}/photos")
    try:
        with open(img_file, "rb") as fp:
            resp = requests.post(
                url,
                data={"caption": caption, "access_token": FB_PAGE_ACCESS_TOKEN},
                files={"source": (img_file.name, fp, "image/png")},
                timeout=30,
            )
        if not resp.ok:
            err_msg = resp.text[:400]
            logged = log_social_distribution(
                flyer_id=flyer_id,
                channel="FACEBOOK_PAGE",
                mode="LIVE",
                status="FAILED",
                target=FB_PAGE_ID,
                details=f"HTTP {resp.status_code}: {err_msg}",
            )
            return {**logged, "ok": False, "error": err_msg}

        payload = resp.json()
        post_id = str(payload.get("post_id") or payload.get("id") or "")
        post_url = f"https://www.facebook.com/{post_id}" if post_id else None
        logged = log_social_distribution(
            flyer_id=flyer_id,
            channel="FACEBOOK_PAGE",
            mode="LIVE",
            status="SUCCESS",
            target=FB_PAGE_ID,
            external_id=post_id,
            post_url=post_url,
            details=f"Published {img_file.name} to Facebook Page.",
        )
        return {**logged, "ok": True, "simulated": False}
    except Exception as exc:
        logged = log_social_distribution(
            flyer_id=flyer_id,
            channel="FACEBOOK_PAGE",
            mode="LIVE",
            status="FAILED",
            target=FB_PAGE_ID,
            details=str(exc),
        )
        return {**logged, "ok": False, "error": str(exc)}


def send_whatsapp_flyer_broadcast(
    image_path: str | Path,
    caption: str,
    flyer_id: Optional[int] = None,
    recipients: Optional[list[dict[str, Any]]] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Send flyer image to opted-in 1-to-1 recipients via official WhatsApp Cloud API.

    Note: Unofficial WhatsApp Web bots violate Meta ToS and risk permanent number bans, and
    the Cloud API Groups feature is restricted to OBA accounts with an 8-person cap.
    Official bulk distribution uses 1-to-1 opted-in Cloud API broadcasts plus click-to-share
    (`wa.me`) for human-assisted group forwarding.
    """
    img_file = Path(image_path)
    if not img_file.exists():
        raise FileNotFoundError(f"Flyer image not found: {img_file}")

    contacts = recipients if recipients is not None else get_whatsapp_contacts(opted_in_only=True)
    if not contacts:
        return {
            "ok": False,
            "status": "NO_RECIPIENTS",
            "sent": 0,
            "failed": 0,
            "results": [],
            "message": "No opted-in WhatsApp contacts found. Add at least one opted-in contact first.",
        }

    if dry_run or not WHATSAPP_PHONE_NUMBER_ID or not WHATSAPP_ACCESS_TOKEN:
        reason = (
            "Dry-run requested"
            if dry_run
            else "WHATSAPP_PHONE_NUMBER_ID / WHATSAPP_ACCESS_TOKEN not configured"
        )
        results = []
        for c in contacts:
            rec = log_social_distribution(
                flyer_id=flyer_id,
                channel="WHATSAPP_CLOUD",
                mode="DRY_RUN",
                status="SIMULATED",
                target=c["phone_e164"],
                details=f"{reason}. Would send {img_file.name} to {c['name']} (+{c['phone_e164']}).",
            )
            results.append(rec)
        return {
            "ok": True,
            "status": "SIMULATED",
            "simulated": True,
            "sent": len(results),
            "failed": 0,
            "results": results,
        }

    headers = {"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"}
    media_url = _graph_url(f"{WHATSAPP_PHONE_NUMBER_ID}/media")

    try:
        with open(img_file, "rb") as fp:
            media_resp = requests.post(
                media_url,
                headers=headers,
                data={"messaging_product": "whatsapp"},
                files={"file": (img_file.name, fp, "image/png")},
                timeout=30,
            )
        if not media_resp.ok:
            err = media_resp.text[:400]
            log_social_distribution(
                flyer_id=flyer_id,
                channel="WHATSAPP_CLOUD",
                mode="LIVE",
                status="FAILED",
                target="media_upload",
                details=f"Media upload failed ({media_resp.status_code}): {err}",
            )
            return {"ok": False, "status": "MEDIA_UPLOAD_FAILED", "sent": 0, "failed": len(contacts), "error": err, "results": []}
        media_id = str(media_resp.json()["id"])
    except Exception as exc:
        log_social_distribution(
            flyer_id=flyer_id,
            channel="WHATSAPP_CLOUD",
            mode="LIVE",
            status="FAILED",
            target="media_upload",
            details=str(exc),
        )
        return {"ok": False, "status": "MEDIA_UPLOAD_FAILED", "sent": 0, "failed": len(contacts), "error": str(exc), "results": []}

    msg_url = _graph_url(f"{WHATSAPP_PHONE_NUMBER_ID}/messages")
    sent = 0
    failed = 0
    results = []
    safe_caption = caption[:1024]

    for c in contacts:
        payload = {
            "messaging_product": "whatsapp",
            "to": c["phone_e164"],
            "type": "image",
            "image": {"id": media_id, "caption": safe_caption},
        }
        try:
            r = requests.post(msg_url, headers=headers, json=payload, timeout=20)
            if r.ok:
                msg_id = str((r.json().get("messages") or [{}])[0].get("id", ""))
                rec = log_social_distribution(
                    flyer_id=flyer_id,
                    channel="WHATSAPP_CLOUD",
                    mode="LIVE",
                    status="SUCCESS",
                    target=c["phone_e164"],
                    external_id=msg_id,
                    details=f"Sent to {c['name']} (+{c['phone_e164']})",
                )
                sent += 1
            else:
                rec = log_social_distribution(
                    flyer_id=flyer_id,
                    channel="WHATSAPP_CLOUD",
                    mode="LIVE",
                    status="FAILED",
                    target=c["phone_e164"],
                    details=f"HTTP {r.status_code}: {r.text[:300]}",
                )
                failed += 1
            results.append(rec)
        except Exception as exc:
            rec = log_social_distribution(
                flyer_id=flyer_id,
                channel="WHATSAPP_CLOUD",
                mode="LIVE",
                status="FAILED",
                target=c["phone_e164"],
                details=str(exc),
            )
            failed += 1
            results.append(rec)

    return {
        "ok": failed == 0 and sent > 0,
        "status": "COMPLETED" if failed == 0 else "PARTIAL_OR_FAILED",
        "simulated": False,
        "sent": sent,
        "failed": failed,
        "media_id": media_id,
        "results": results,
    }


def create_group_share_pack(
    image_path: str | Path,
    caption: str,
    flyer_id: Optional[int] = None,
    fb_post_url: Optional[str] = None,
) -> dict[str, Any]:
    """Generate a compliant Group Share Pack (PNG + captions + 1-click wa.me URL) for manual group sharing."""
    img_file = Path(image_path)
    if not img_file.exists():
        raise FileNotFoundError(f"Flyer image not found: {img_file}")

    pack_dir = SHARE_PACKS_DIR / img_file.stem
    pack_dir.mkdir(parents=True, exist_ok=True)

    copied_img = pack_dir / img_file.name
    if img_file.resolve() != copied_img.resolve():
        shutil.copy2(img_file, copied_img)

    wa_share_url = f"https://wa.me/?text={quote(caption)}"
    fb_group_caption = caption
    if fb_post_url:
        fb_group_caption += f"\n\nOfficial Page Post: {fb_post_url}"

    (pack_dir / "whatsapp_group_caption.txt").write_text(caption, encoding="utf-8")
    (pack_dir / "facebook_group_caption.txt").write_text(fb_group_caption, encoding="utf-8")

    manifest = {
        "company": COMPANY_INFO["name"],
        "flyer_image": str(copied_img),
        "wa_share_url": wa_share_url,
        "fb_page_post_url": fb_post_url,
        "whatsapp_group_caption": caption,
        "facebook_group_caption": fb_group_caption,
    }
    (pack_dir / "share_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    logged = log_social_distribution(
        flyer_id=flyer_id,
        channel="GROUP_SHARE_PACK",
        mode="READY_TO_SHARE",
        status="READY",
        target=str(pack_dir),
        post_url=wa_share_url,
        details="Generated compliant Group Share Pack (PNG + captions + wa.me link).",
    )
    return {**logged, **manifest, "pack_dir": str(pack_dir)}


def notify_team_with_share_pack(
    to_email: str,
    image_path: str | Path,
    caption: str,
    wa_share_url: str,
    fb_post_url: Optional[str] = None,
    flyer_id: Optional[int] = None,
) -> dict[str, Any]:
    """Email the weekly flyer + captions + wa.me link to marketing staff via Task 1 Gmail OAuth."""
    img_file = Path(image_path)
    if not img_file.exists():
        raise FileNotFoundError(f"Flyer image not found: {img_file}")

    msg = MIMEMultipart("mixed")
    msg["To"] = to_email.strip()
    msg["Subject"] = f"Weekly Flyer Ready for Group Sharing - {COMPANY_INFO['name']}"

    fb_line = f"\nFacebook Page Post: {fb_post_url}\n" if fb_post_url else "\n"
    body_text = (
        f"Hi Team,\n\n"
        f"This week's promotional flyer for {COMPANY_INFO['name']} is attached.\n"
        f"To stay 100% compliant with WhatsApp and Facebook Group policies, please share it to your groups:\n\n"
        f"1. Click-to-Share on WhatsApp: {wa_share_url}\n"
        f"{fb_line}"
        f"2. Caption to paste:\n{'-' * 40}\n{caption}\n{'-' * 40}\n"
    )
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    with open(img_file, "rb") as fp:
        att = MIMEImage(fp.read(), name=img_file.name)
        att.add_header("Content-Disposition", "attachment", filename=img_file.name)
        msg.attach(att)

    try:
        service = get_gmail_service()
        raw_bytes = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        res = service.users().messages().send(userId="me", body={"raw": raw_bytes}).execute()
        msg_id = str(res.get("id", ""))
        logged = log_social_distribution(
            flyer_id=flyer_id,
            channel="TEAM_NOTIFY_EMAIL",
            mode="LIVE",
            status="SUCCESS",
            target=to_email.strip(),
            external_id=msg_id,
            details="Sent weekly flyer & Group Share Pack email to staff.",
        )
        return {**logged, "ok": True}
    except Exception as exc:
        logged = log_social_distribution(
            flyer_id=flyer_id,
            channel="TEAM_NOTIFY_EMAIL",
            mode="LIVE",
            status="FAILED",
            target=to_email.strip(),
            details=str(exc),
        )
        return {**logged, "ok": False, "error": str(exc)}
