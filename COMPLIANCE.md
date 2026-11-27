# Platform Compliance & Policy Architecture

This document explains how **Reliable Paper Mart – Automated Marketing System** stays 100% compliant with **Gmail**, **WhatsApp (Meta)**, and **Facebook (Meta)** official policies so the company's email domain, business phone number, and social accounts are never flagged or banned.

---

## 1. Gmail Sending Compliance (Task 1)

| Risk | How Our System Prevents It |
|---|---|
| Exceeding Gmail daily sending limits (~500/day free Gmail, ~2,000/day Google Workspace) | Clients are auto-balanced across **Monday–Saturday** (`assigned_day` 0–5), capped by `DAILY_SEND_LIMIT` (default `400`), with a `2.0s` delay (`SEND_DELAY_SECONDS`) between sends. |
| Duplicate emails within the same week | Tracks ISO year-week (`YYYY-Www`) in `email_logs`; `get_clients_due_for_day()` skips any client already marked `SENT` (`send_type = 'BATCH'`) for that week. |
| Missing opt-out / spam complaints | Every email includes a unique token unsubscribe link + RFC 8058 `List-Unsubscribe` and `List-Unsubscribe-Post` headers. Unsubscribed clients are excluded from both automated batches and manual test sends. |
| Over-privileged API access | Requests only `https://www.googleapis.com/auth/gmail.send` (cannot read or delete inbox messages). |
| Production deliverability note | For local demos using `localhost` unsubscribe links, emails may land in Spam. In production, send from a Google Workspace domain with SPF/DKIM/DMARC configured and an HTTPS `BASE_URL`. |

---

## 2. Facebook Policy Research & Architecture (Task 2)

### Why Fully Automated Posting to Facebook Groups Is NOT Permitted
- On **January 23, 2024** (Graph API v19.0), Meta announced the deprecation of the **Facebook Groups API**, and on **April 22, 2024**, Meta **permanently removed** the `publish_to_groups` and `groups_access_member_info` permissions across **all** Graph API versions.
- There is **no public Meta API replacement** for publishing automatically into general Facebook Groups (even major schedulers like Buffer and Hootsuite lost group posting).
- Using browser automation (Selenium/Playwright/headless scripts) to simulate human posting in Groups violates Meta's Terms of Service and risks **account locks or permanent bans**.

### Compliant Solution Implemented
1. **Owned Facebook Page Automation (`post_to_facebook_page`):** Uses the official Graph API (`POST https://graph.facebook.com/v21.0/{FB_PAGE_ID}/photos`) with `pages_manage_posts` and `pages_read_engagement` permissions to publish the weekly flyer PNG and caption automatically to Reliable Paper Mart's **Facebook Page**.
2. **Facebook Groups (Human-in-the-Loop Share Pack):** `create_group_share_pack()` prepares the flyer PNG, group-ready caption, and a direct link to the published Page post inside `generated_flyers/share_packs/` (and optionally emails staff via `notify_team_with_share_pack()`), allowing staff to share safely into target Facebook Groups in two clicks with **zero ban risk**.

---

## 3. WhatsApp Policy Research & Architecture (Task 2)

### Why Unofficial Group Automation Is Rejected
- Unofficial libraries (`pywhatkit`, `whatsapp-web.js`, Baileys, or browser automation on WhatsApp Web) violate the **WhatsApp Business Messaging Policy & Terms of Service** and frequently result in **permanent phone number bans**.
- Meta's official **WhatsApp Cloud API Groups** feature has strict constraints: it requires an **Official Business Account (OBA)**, operates on an invite-only model (cannot add users programmatically), caps groups at **8 participants maximum**, and charges per message per member—making it unsuitable for mass customer marketing groups.

### Compliant Solution Implemented
1. **Opted-In 1-to-1 Broadcasts (`send_whatsapp_flyer_broadcast`):** Uses the official **WhatsApp Cloud API** (`POST /{WHATSAPP_PHONE_NUMBER_ID}/media` + `/messages`) to send the flyer image and caption strictly to **opted-in individual contacts** stored in `whatsapp_contacts` (`opted_in = 1`).
2. **WhatsApp Groups (1-Click `wa.me` + Group Share Pack):** Generates an official `https://wa.me/?text=...` click-to-share URL alongside the flyer PNG inside `generated_flyers/share_packs/` so staff can open WhatsApp with the promotional message pre-filled and forward the flyer into customer WhatsApp Groups safely with **zero ban risk**.

---

## 4. Product & Price Accuracy Guarantee

Pure AI image generators (e.g., DALL-E, Midjourney) frequently misspell product names and hallucinate numeric prices. To guarantee 100% accuracy:
- **Groq LLM (`ai_copywriter.py`)** generates only the creative marketing copy (headline, offer badge, subheadline, CTA, and social caption).
- **Pillow (`flyer_generator.py`)** renders the `1080×1350` PNG flyer programmatically using exact item names, units, `₹` prices, and stock quantities queried directly from `marketing.db`.
