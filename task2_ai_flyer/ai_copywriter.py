"""AI marketing copywriter powered by Groq (with deterministic offline fallback)."""

import json
import logging
from typing import Any, Optional

import requests

from shared.config import COMPANY_INFO, GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def _build_fallback_copy(
    stock_items: list[dict[str, Any]],
    campaign_theme: str,
) -> dict[str, str]:
    """Generate clean deterministic marketing copy when GROQ_API_KEY is unavailable."""
    top_names = [item["item_name"].split("(")[0].strip() for item in stock_items[:3]]
    highlight = ", ".join(top_names) if top_names else "Premium Paper & Packaging"

    price_lines = "\n".join(
        f"• {item['item_name']} — Rs. {item['price']:.2f} ({item['unit']})"
        for item in stock_items[:6]
    )

    caption = (
        f"📄 *{COMPANY_INFO['name']} – Weekly Stock Update!*\n"
        f"Theme: {campaign_theme}\n\n"
        f"Fresh inventory ready for dispatch:\n{price_lines}\n\n"
        f"📞 Order / Bulk Quotes: {COMPANY_INFO['phone']}\n"
        f"📧 {COMPANY_INFO['email']}\n"
        f"#ReliablePaperMart #B2BPaper #PackagingSupplies #OfficePaper"
    )

    return {
        "headline": "Stock Up. Stay Ready.",
        "subheadline": f"Fresh stock ready for dispatch: {highlight}",
        "offer_badge": "IN STOCK • BULK READY",
        "cta_text": "Call or WhatsApp today for same-day dispatch & bulk rates",
        "social_caption": caption,
        "ai_source": "FALLBACK",
    }


def generate_flyer_copy(
    stock_items: list[dict[str, Any]],
    campaign_theme: str = "Weekly paper essentials",
    custom_headline: Optional[str] = None,
) -> dict[str, str]:
    """Generate promotional flyer headline, offer text, and social caption via Groq API.

    Note: Item prices shown on the flyer itself always come directly from SQLite (`stock_items`)
    rather than LLM output, guaranteeing 100% price accuracy.
    """
    fallback = _build_fallback_copy(stock_items, campaign_theme)

    if not GROQ_API_KEY:
        logger.info("GROQ_API_KEY not set; using deterministic marketing copy fallback.")
        if custom_headline and custom_headline.strip():
            fallback["headline"] = custom_headline.strip()
        return fallback

    items_summary = "\n".join(
        f"- {item['item_name']} ({item['category']}, {item['unit']}): Rs. {item['price']:.2f}, Qty {item['quantity']}"
        for item in stock_items[:10]
    )

    system_prompt = (
        "You are a concise B2B marketing copywriter for an Indian paper and packaging wholesaler "
        f"named '{COMPANY_INFO['name']}'. Always output valid JSON only, with no markdown fences."
    )
    user_prompt = (
        f"Campaign theme: {campaign_theme}\n"
        f"Available in-stock items:\n{items_summary}\n\n"
        "Return a JSON object with exactly these 5 string keys:\n"
        '- "headline": short punchy flyer headline (3-6 words, max 38 chars)\n'
        '- "subheadline": crisp value proposition (max 68 chars)\n'
        '- "offer_badge": short uppercase badge (2-4 words, max 22 chars, e.g. "WEEKLY STOCK DEAL")\n'
        '- "cta_text": short call-to-action line (max 65 chars)\n'
        '- "social_caption": engaging WhatsApp & Facebook post caption listing the top items with exact '
        f"Rs. prices from above, plus contact phone {COMPANY_INFO['phone']} and 3-4 relevant hashtags."
    )

    candidate_models = []
    for m in (GROQ_MODEL, "openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"):
        if m and m not in candidate_models:
            candidate_models.append(m)

    for model_id in candidate_models:
        try:
            resp = requests.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_id,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.6,
                    "max_tokens": 1500,
                    "response_format": {"type": "json_object"},
                },
                timeout=20,
            )
            if resp.status_code == 404:
                logger.warning("Groq model '%s' unavailable (404); trying next fallback model.", model_id)
                continue
            if not resp.ok:
                logger.warning("Groq API error for %s (%s): %s", model_id, resp.status_code, resp.text[:300])
                continue
            content = resp.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)

            result = {
                "headline": str(parsed.get("headline") or fallback["headline"]).strip()[:48],
                "subheadline": str(parsed.get("subheadline") or fallback["subheadline"]).strip()[:90],
                "offer_badge": str(parsed.get("offer_badge") or fallback["offer_badge"]).strip().upper()[:26],
                "cta_text": str(parsed.get("cta_text") or fallback["cta_text"]).strip()[:85],
                "social_caption": str(parsed.get("social_caption") or fallback["social_caption"]).strip(),
                "ai_source": f"GROQ ({model_id})",
            }
            if custom_headline and custom_headline.strip():
                result["headline"] = custom_headline.strip()
            return result
        except Exception as exc:
            logger.warning("Groq API call failed for %s (%s); falling back.", model_id, exc)
            break

    if custom_headline and custom_headline.strip():
        fallback["headline"] = custom_headline.strip()
    return fallback
