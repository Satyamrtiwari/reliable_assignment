"""Programmatic Pillow promotional flyer renderer with 3 rotatable layouts and exact live prices."""

from datetime import datetime
from pathlib import Path
import textwrap
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageFont

from shared.config import COMPANY_INFO, GENERATED_FLYERS_DIR
from shared.database import (
    count_generated_flyers,
    get_current_week_key,
    log_flyer_generation,
)
from task2_ai_flyer.ai_copywriter import generate_flyer_copy

FLYER_WIDTH = 1080
FLYER_HEIGHT = 1350

LAYOUT_NAMES = ("Card List", "2-Column Grid", "Featured Spotlight")

STYLE_PALETTES: dict[str, dict[str, str]] = {
    "Minimal": {
        "canvas": "#F4F6FB",
        "header_bg": "#1E3A5F",
        "header_accent": "#4361EE",
        "badge_bg": "#E0E7FF",
        "badge_fg": "#1E3A8A",
        "card_bg": "#FFFFFF",
        "card_border": "#DCE4F2",
        "text": "#0F172A",
        "muted": "#475569",
        "price": "#1E3A8A",
        "qty_bg": "#DCFCE7",
        "qty_fg": "#166534",
        "footer_bg": "#0F172A",
        "footer_fg": "#E2E8F0",
    },
    "Bold": {
        "canvas": "#0F172A",
        "header_bg": "#1E1B4B",
        "header_accent": "#F59E0B",
        "badge_bg": "#FEF3C7",
        "badge_fg": "#92400E",
        "card_bg": "#1E293B",
        "card_border": "#334155",
        "text": "#F8FAFC",
        "muted": "#CBD5E1",
        "price": "#FBBF24",
        "qty_bg": "#064E3B",
        "qty_fg": "#6EE7B7",
        "footer_bg": "#020617",
        "footer_fg": "#E2E8F0",
    },
    "Fresh": {
        "canvas": "#F0FDF4",
        "header_bg": "#065F46",
        "header_accent": "#10B981",
        "badge_bg": "#D1FAE5",
        "badge_fg": "#065F46",
        "card_bg": "#FFFFFF",
        "card_border": "#BBF7D0",
        "text": "#064E3B",
        "muted": "#475569",
        "price": "#047857",
        "qty_bg": "#ECFDF5",
        "qty_fg": "#065F46",
        "footer_bg": "#064E3B",
        "footer_fg": "#ECFDF5",
    },
}


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load crisp system TrueType font with safe cross-platform fallbacks."""
    candidates = (
        [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        if bold
        else [
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _format_price(amount: float, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> str:
    """Use Rupee symbol when font supports its glyph, else clean 'Rs.' prefix."""
    try:
        bbox = font.getbbox("₹")
        if bbox and (bbox[2] - bbox[0]) > 0:
            return f"₹{amount:,.2f}"
    except Exception:
        pass
    return f"Rs. {amount:,.2f}"


def _draw_pill(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    font: Any,
    bg_color: str,
    fg_color: str,
    align_right: bool = False,
    pad_x: int = 12,
    height: int = 28,
) -> int:
    """Draw a rounded badge pill and return its width."""
    box = draw.textbbox((0, 0), text, font=font)
    width = (box[2] - box[0]) + (pad_x * 2)
    x1 = (x - width) if align_right else x
    x2 = x if align_right else (x + width)
    draw.rounded_rectangle([x1, y, x2, y + height], radius=height // 2, fill=bg_color)
    draw.text((x1 + pad_x, y + 4), text, font=font, fill=fg_color)
    return width


def resolve_layout(layout: str) -> str:
    """Resolve explicit layout name or auto-rotate cleanly across all 3 layouts."""
    if layout in LAYOUT_NAMES:
        return layout
    existing_count = count_generated_flyers()
    return LAYOUT_NAMES[existing_count % len(LAYOUT_NAMES)]


def _draw_card_list(
    draw: ImageDraw.ImageDraw,
    stock_items: list[dict[str, Any]],
    pal: dict[str, str],
    fonts: dict[str, Any],
) -> int:
    """Render stacked full-width product rows (up to 6 items). Returns bottom Y."""
    visible_items = stock_items[:6]
    card_y = 420
    card_h = 98
    card_gap = 16

    for item in visible_items:
        draw.rounded_rectangle(
            [56, card_y, FLYER_WIDTH - 56, card_y + card_h],
            radius=16,
            fill=pal["card_bg"],
            outline=pal["card_border"],
            width=2,
        )
        name = item["item_name"][:35] + "..." if len(item["item_name"]) > 38 else item["item_name"]
        draw.text((82, card_y + 16), name, font=fonts["item"], fill=pal["text"])
        draw.text(
            (82, card_y + 52),
            f"{item['category']}  •  {item['unit']}",
            font=fonts["meta"],
            fill=pal["muted"],
        )

        price_str = _format_price(float(item["price"]), fonts["price"])
        draw.text((FLYER_WIDTH - 82, card_y + 14), price_str, font=fonts["price"], fill=pal["price"], anchor="ra")
        _draw_pill(
            draw,
            FLYER_WIDTH - 82,
            card_y + 52,
            f"{item['quantity']} in stock",
            fonts["qty"],
            pal["qty_bg"],
            pal["qty_fg"],
            align_right=True,
        )
        card_y += card_h + card_gap

    return card_y


def _draw_two_column_grid(
    draw: ImageDraw.ImageDraw,
    stock_items: list[dict[str, Any]],
    pal: dict[str, str],
    fonts: dict[str, Any],
) -> int:
    """Render 2-column catalog tiles (up to 6 items). Returns bottom Y."""
    visible_items = stock_items[:6]
    margin = 56
    col_gap = 28
    tile_w = (FLYER_WIDTH - (margin * 2) - col_gap) // 2
    tile_h = 204
    row_gap = 20
    start_y = 420

    for idx, item in enumerate(visible_items):
        col = idx % 2
        row = idx // 2
        x1 = margin + col * (tile_w + col_gap)
        y1 = start_y + row * (tile_h + row_gap)
        x2 = x1 + tile_w
        y2 = y1 + tile_h

        draw.rounded_rectangle(
            [x1, y1, x2, y2],
            radius=18,
            fill=pal["card_bg"],
            outline=pal["card_border"],
            width=2,
        )

        _draw_pill(
            draw,
            x1 + 22,
            y1 + 20,
            item["category"].upper()[:18],
            fonts["qty"],
            pal["badge_bg"],
            pal["badge_fg"],
            height=26,
        )

        wrapped_name = textwrap.wrap(item["item_name"], width=25)[:2]
        ny = y1 + 58
        for line in wrapped_name:
            draw.text((x1 + 22, ny), line, font=fonts["grid_item"], fill=pal["text"])
            ny += 28

        draw.text((x1 + 22, y1 + 118), item["unit"][:34], font=fonts["meta"], fill=pal["muted"])

        price_str = _format_price(float(item["price"]), fonts["price"])
        draw.text((x1 + 22, y2 - 48), price_str, font=fonts["price"], fill=pal["price"])
        _draw_pill(
            draw,
            x2 - 22,
            y2 - 44,
            f"{item['quantity']} left",
            fonts["qty"],
            pal["qty_bg"],
            pal["qty_fg"],
            align_right=True,
        )

    rows_used = (len(visible_items) + 1) // 2
    return start_y + rows_used * (tile_h + row_gap)


def _draw_featured_spotlight(
    draw: ImageDraw.ImageDraw,
    stock_items: list[dict[str, Any]],
    pal: dict[str, str],
    fonts: dict[str, Any],
) -> int:
    """Highlight item #1 in a spotlight card + up to 5 compact rows below. Returns bottom Y."""
    hero = stock_items[0]
    hero_y1, hero_y2 = 420, 598
    draw.rounded_rectangle(
        [56, hero_y1, FLYER_WIDTH - 56, hero_y2],
        radius=20,
        fill=pal["card_bg"],
        outline=pal["header_accent"],
        width=3,
    )

    _draw_pill(
        draw,
        84,
        hero_y1 + 22,
        "FEATURED PICK THIS WEEK",
        fonts["qty"],
        pal["badge_bg"],
        pal["badge_fg"],
        height=28,
    )
    hero_name = hero["item_name"][:30] + "..." if len(hero["item_name"]) > 33 else hero["item_name"]
    draw.text((84, hero_y1 + 66), hero_name, font=fonts["hero_item"], fill=pal["text"])
    draw.text(
        (84, hero_y1 + 116),
        f"{hero['category']}  •  {hero['unit']}",
        font=fonts["meta"],
        fill=pal["muted"],
    )

    hero_price = _format_price(float(hero["price"]), fonts["hero_price"])
    draw.text((FLYER_WIDTH - 84, hero_y1 + 48), hero_price, font=fonts["hero_price"], fill=pal["price"], anchor="ra")
    _draw_pill(
        draw,
        FLYER_WIDTH - 84,
        hero_y1 + 114,
        f"{hero['quantity']} in stock",
        fonts["qty"],
        pal["qty_bg"],
        pal["qty_fg"],
        align_right=True,
    )

    # Remaining up to 5 compact rows
    y_pos = hero_y2 + 24
    row_h = 80
    row_gap = 12
    for item in stock_items[1:6]:
        draw.rounded_rectangle(
            [56, y_pos, FLYER_WIDTH - 56, y_pos + row_h],
            radius=14,
            fill=pal["card_bg"],
            outline=pal["card_border"],
            width=2,
        )
        name = item["item_name"][:36] + "..." if len(item["item_name"]) > 39 else item["item_name"]
        draw.text((82, y_pos + 12), name, font=fonts["grid_item"], fill=pal["text"])
        draw.text((82, y_pos + 44), f"{item['category']} • {item['unit']}", font=fonts["meta"], fill=pal["muted"])

        price_str = _format_price(float(item["price"]), fonts["price"])
        draw.text((FLYER_WIDTH - 82, y_pos + 10), price_str, font=fonts["item"], fill=pal["price"], anchor="ra")
        draw.text((FLYER_WIDTH - 82, y_pos + 45), f"{item['quantity']} in stock", font=fonts["qty"], fill=pal["qty_fg"], anchor="ra")
        y_pos += row_h + row_gap

    return y_pos


def generate_flyer_image(
    stock_items: list[dict[str, Any]],
    style: str = "Minimal",
    layout: str = "Auto-Rotate",
    campaign_theme: str = "Weekly paper essentials",
    custom_headline: Optional[str] = None,
    copy_override: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Create a 1080x1350 promotional flyer PNG from live stock items and log it."""
    if not stock_items:
        raise ValueError("Cannot generate a flyer without at least one in-stock item.")

    chosen_style = style if style in STYLE_PALETTES else "Minimal"
    chosen_layout = resolve_layout(layout)
    pal = STYLE_PALETTES[chosen_style]

    copy = copy_override or generate_flyer_copy(
        stock_items=stock_items,
        campaign_theme=campaign_theme,
        custom_headline=custom_headline,
    )

    GENERATED_FLYERS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    week_key = get_current_week_key(now)
    layout_slug = chosen_layout.lower().replace(" ", "_").replace("-", "")
    filename = f"flyer_{week_key}_{chosen_style.lower()}_{layout_slug}_{now.strftime('%Y%m%d_%H%M%S')}.png"
    out_path = GENERATED_FLYERS_DIR / filename

    img = Image.new("RGB", (FLYER_WIDTH, FLYER_HEIGHT), pal["canvas"])
    draw = ImageDraw.Draw(img)

    fonts = {
        "brand": _load_font(26, bold=True),
        "date": _load_font(20, bold=False),
        "badge": _load_font(20, bold=True),
        "headline": _load_font(54, bold=True),
        "sub": _load_font(24, bold=False),
        "section": _load_font(20, bold=True),
        "item": _load_font(25, bold=True),
        "grid_item": _load_font(22, bold=True),
        "hero_item": _load_font(30, bold=True),
        "hero_price": _load_font(38, bold=True),
        "meta": _load_font(19, bold=False),
        "price": _load_font(28, bold=True),
        "qty": _load_font(18, bold=True),
        "cta": _load_font(22, bold=True),
        "footer": _load_font(19, bold=False),
    }

    # 1. Top Header Block
    draw.rectangle([0, 0, FLYER_WIDTH, 350], fill=pal["header_bg"])
    draw.rectangle([0, 0, FLYER_WIDTH, 12], fill=pal["header_accent"])

    draw.text((56, 42), COMPANY_INFO["name"].upper(), font=fonts["brand"], fill="#FFFFFF")
    draw.text(
        (FLYER_WIDTH - 56, 46),
        f"Week {week_key}  •  {now.strftime('%d %b %Y')}",
        font=fonts["date"],
        fill="#CBD5E1",
        anchor="ra",
    )

    _draw_pill(
        draw,
        56,
        98,
        copy["offer_badge"],
        fonts["badge"],
        pal["badge_bg"],
        pal["badge_fg"],
        pad_x=17,
        height=40,
    )

    headline_lines = textwrap.wrap(copy["headline"], width=26)[:2]
    y_cursor = 158
    for line in headline_lines:
        draw.text((56, y_cursor), line, font=fonts["headline"], fill="#FFFFFF")
        y_cursor += 64

    sub_lines = textwrap.wrap(copy["subheadline"], width=58)[:2]
    sub_y = y_cursor + 10
    for line in sub_lines:
        draw.text((56, sub_y), line, font=fonts["sub"], fill="#E2E8F0")
        sub_y += 32

    # 2. Body Section (dispatched by chosen layout)
    draw.text(
        (56, 378),
        "AVAILABLE STOCK & CURRENT RATES",
        font=fonts["section"],
        fill=pal["muted"],
    )

    if chosen_layout == "2-Column Grid":
        bottom_y = _draw_two_column_grid(draw, stock_items, pal, fonts)
    elif chosen_layout == "Featured Spotlight":
        bottom_y = _draw_featured_spotlight(draw, stock_items, pal, fonts)
    else:
        bottom_y = _draw_card_list(draw, stock_items, pal, fonts)

    remaining_count = max(0, len(stock_items) - 6)
    if remaining_count > 0:
        draw.text(
            (FLYER_WIDTH // 2, bottom_y + 4),
            f"+ {remaining_count} more items in stock — contact us for full wholesale catalog",
            font=fonts["meta"],
            fill=pal["muted"],
            anchor="ma",
        )

    # 3. Bottom CTA & Contact Footer
    footer_y = FLYER_HEIGHT - 165
    draw.rectangle([0, footer_y, FLYER_WIDTH, FLYER_HEIGHT], fill=pal["footer_bg"])
    draw.rectangle([0, footer_y, FLYER_WIDTH, footer_y + 6], fill=pal["header_accent"])

    draw.text(
        (FLYER_WIDTH // 2, footer_y + 26),
        copy["cta_text"],
        font=fonts["cta"],
        fill="#FFFFFF",
        anchor="ma",
    )
    draw.text(
        (FLYER_WIDTH // 2, footer_y + 72),
        f"Phone: {COMPANY_INFO['phone']}   |   Email: {COMPANY_INFO['email']}",
        font=fonts["footer"],
        fill=pal["footer_fg"],
        anchor="ma",
    )
    draw.text(
        (FLYER_WIDTH // 2, footer_y + 106),
        f"{COMPANY_INFO['address']}   •   {COMPANY_INFO['hours']}",
        font=fonts["footer"],
        fill="#94A3B8",
        anchor="ma",
    )

    img.save(out_path, format="PNG")

    logged = log_flyer_generation(
        week_key=week_key,
        style=chosen_style,
        layout=chosen_layout,
        campaign_theme=campaign_theme,
        headline=copy["headline"],
        offer_text=copy["offer_badge"],
        caption=copy["social_caption"],
        image_path=str(out_path),
        ai_source=copy["ai_source"],
        item_count=len(stock_items),
    )

    return {
        **logged,
        "subheadline": copy["subheadline"],
        "cta_text": copy["cta_text"],
    }
