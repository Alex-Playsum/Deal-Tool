"""Build marketing email HTML from block list and game pool (inline CSS, table-based, Mailjet-friendly)."""

import html as html_module

# Symbol-only labels for email (no "US" or "($)" - e.g. USD -> "$")
CURRENCY_SYMBOLS_EMAIL = {
    "USD": "$",
    "GBP": "£",
    "EUR": "€",
    "CAD": "$",
    "AUD": "$",
    "NZD": "$",
    "PLN": "zł",
    "BRL": "R$",
    "INR": "₹",
    "IDR": "Rp",
    "CNY": "¥",
}

# Playsum website colors (dark theme)
FONT_FAMILY = "Arial, Helvetica, sans-serif"
WRAPPER_WIDTH = 600
CELL_PADDING = 16
BLOCK_SPACING = 24  # vertical gap between blocks

# Backgrounds: outer email body, inner content strip
BG_DARK = "#1A1B2C"       # outer (email body)
BG_INNER = "#0E131F"     # inner narrower content
BG_CARD = "#2C2D44"      # optional card/section

# Text
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#A0A0A0"
TEXT_MUTED = "#888888"   # strikethrough price

# Accents
ACCENT_GREEN = "#38B278"  # discount badge
LINK_COLOR = "#db00ff"   # links and CTA
BUTTON_BG = "#db00ff"
BUTTON_COLOR = "#ffffff"


def _variant_for_currency(product: dict, currency: str) -> dict | None:
    by_curr = product.get("variants_by_currency") or {}
    return by_curr.get(currency)


def _display_price(product: dict, currency: str, coupon_percent: float) -> str:
    """Discount price in currency, with coupon applied. Returns formatted string or '—'."""
    v = _variant_for_currency(product, currency)
    if not v:
        return "—"
    raw = v.get("discountPrice")
    if raw is None:
        raw = float(v.get("originalPrice", 0))
    else:
        raw = float(raw)
    if coupon_percent and coupon_percent > 0:
        raw = raw * (1 - coupon_percent / 100)
    return f"{raw:.2f}"


def _display_discount_pct(product: dict, coupon_percent: float) -> str:
    """Effective discount % (after coupon if applied). Uses one variant (USD or first)."""
    by_curr = product.get("variants_by_currency") or {}
    v = by_curr.get("USD") or (next(iter(by_curr.values()), None) if by_curr else None)
    if not v:
        return "—"
    orig = float(v.get("originalPrice", 0))
    if orig <= 0:
        return "—"
    base = v.get("discountPrice")
    if base is not None:
        base = float(base)
    else:
        base = orig
    if coupon_percent and coupon_percent > 0:
        base = base * (1 - coupon_percent / 100)
    pct = round((1 - base / orig) * 100)
    return f"{pct}%"


def _original_price(product: dict, currency: str) -> str:
    """Original price in currency for strikethrough display."""
    v = _variant_for_currency(product, currency)
    if not v:
        return ""
    raw = v.get("originalPrice")
    if raw is None:
        return ""
    try:
        return f"{float(raw):.2f}"
    except (TypeError, ValueError):
        return ""


def _currency_symbol(currency: str) -> str:
    """Symbol-only label for email (e.g. USD -> '$')."""
    return CURRENCY_SYMBOLS_EMAIL.get(currency, currency)


def _render_pricing_html(
    product: dict,
    currency: str,
    show_price: bool,
    coupon_percent: float,
    show_both: bool = False,
) -> str:
    """Steam-style: green badge (discount % or price, or both), strikethrough original, discounted price. Uses symbol-only (e.g. $ not US ($))."""
    symbol = _currency_symbol(currency)
    discount_pct = _display_discount_pct(product, coupon_percent)
    display_price = _display_price(product, currency, coupon_percent)
    original = _original_price(product, currency)
    if show_both:
        badge_text = discount_pct
    elif show_price:
        badge_text = f"{symbol} {display_price}" if display_price != "—" else "—"
    else:
        badge_text = discount_pct
    parts = []
    if badge_text and badge_text != "—":
        parts.append(
            f'<span style="display:inline-block;background:{ACCENT_GREEN};color:{BUTTON_COLOR};padding:4px 8px;border-radius:4px;font-weight:bold;font-size:14px;">{html_module.escape(badge_text)}</span>'
        )
    if show_both and display_price != "—":
        parts.append(
            f'<span style="color:{TEXT_PRIMARY};font-size:14px;margin-left:6px;">{html_module.escape(symbol + " " + display_price)}</span>'
        )
    if (original and (show_price or show_both) and display_price != "—") or (original and not show_price and not show_both):
        parts.append(
            f'<span style="color:{TEXT_MUTED};text-decoration:line-through;font-size:13px;margin-left:6px;">{html_module.escape(symbol + " " + original)}</span>'
        )
    return " ".join(parts) if parts else html_module.escape(display_price or "—")


def _game_image_url(product: dict, image_source: str, capsule_size: str = "header") -> str | None:
    """Image URL for a game: feed cover or Steam capsule. Fallback to feed if no steam_app_id."""
    if image_source == "steam_capsule":
        app_id = product.get("steam_app_id")
        if app_id is not None:
            from steam_images import get_steam_capsule_url
            return get_steam_capsule_url(app_id, capsule_size)
    return product.get("cover_image") or None


def _block_wrapper_style() -> str:
    return f"max-width:{WRAPPER_WIDTH}px;margin:0 auto;font-family:{FONT_FAMILY};background:{BG_INNER};color:{TEXT_PRIMARY};"

def _block_cell_style(extra: str = "") -> str:
    return f"padding:{CELL_PADDING}px;padding-bottom:{BLOCK_SPACING}px;{extra}"


def _render_header(block: dict) -> str:
    cfg = block.get("config") or {}
    logo_url = (cfg.get("logo_url") or "").strip()
    link = (cfg.get("link") or "").strip()
    title = (cfg.get("title") or "Header").strip()
    view_link = (cfg.get("view_in_browser_url") or "").strip()
    if logo_url:
        img = f'<img src="{html_module.escape(logo_url)}" alt="{html_module.escape(title)}" style="max-width:100%;height:auto;display:block;max-height:40px;" />'
        logo_content = f'<a href="{html_module.escape(link)}" style="color:{TEXT_PRIMARY};text-decoration:none;">{img}</a>' if link else img
    else:
        logo_content = f'<span style="font-size:18px;font-weight:bold;color:{TEXT_PRIMARY};">{html_module.escape(title)}</span>'
    right_content = ""
    if view_link:
        right_content = f'<a href="{html_module.escape(view_link)}" style="color:{LINK_COLOR};text-decoration:none;font-size:12px;">View in browser</a>'
    return f'''
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="{_block_wrapper_style()}">
  <tr><td style="{_block_cell_style()}">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td align="center" style="vertical-align:middle;">{logo_content}</td>
      <td align="right" style="vertical-align:middle;width:1%;white-space:nowrap;">{right_content}</td>
    </tr></table>
  </td></tr>
</table>'''


def _render_title(block: dict) -> str:
    cfg = block.get("config") or {}
    text = (cfg.get("text") or "").strip() or "Title"
    return f'''
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="{_block_wrapper_style()}">
  <tr><td style="{_block_cell_style()}" align="center">
    <span style="font-size:26px;font-weight:bold;color:{TEXT_PRIMARY};">{html_module.escape(text)}</span>
  </td></tr>
</table>'''


def _render_deal_list(
    block: dict,
    games: list[dict],
    options: dict,
) -> str:
    cfg = block.get("config") or {}
    count = min(4, int(cfg.get("games_count") or 4))  # 2x2 grid = max 4
    image_source = (cfg.get("image_source") or "feed").strip() or "feed"
    capsule_size = (cfg.get("capsule_size") or "header").strip() or "header"
    section_title = (cfg.get("section_title") or "").strip()
    currency = options.get("currency") or "USD"
    show_price = options.get("show_price", True)
    show_both = options.get("show_both", False)
    coupon_percent = float(options.get("coupon_percent") or 0)

    products = games[:count]
    if not products:
        return ""

    cell_style = f"width:50%;vertical-align:top;padding:8px;border-bottom:1px solid {BG_CARD};"
    cells = []
    for p in products:
        link = (p.get("link") or "").strip()
        title = (p.get("title") or "").strip() or "Game"
        img_url = _game_image_url(p, image_source, capsule_size) or ""
        pricing_html = _render_pricing_html(p, currency, show_price, coupon_percent, show_both=show_both)
        img_html = ""
        if img_url:
            img_html = f'<a href="{html_module.escape(link)}"><img src="{html_module.escape(img_url)}" alt="{html_module.escape(title)}" style="width:100%;max-width:260px;height:auto;display:block;border:0;" /></a>' if link else f'<img src="{html_module.escape(img_url)}" alt="{html_module.escape(title)}" style="width:100%;max-width:260px;height:auto;display:block;border:0;" />'
        title_html = f'<a href="{html_module.escape(link)}" style="color:{LINK_COLOR};text-decoration:none;font-weight:bold;font-size:14px;">{html_module.escape(title)}</a>' if link else f'<span style="color:{TEXT_PRIMARY};font-weight:bold;font-size:14px;">{html_module.escape(title)}</span>'
        cells.append(
            f'<td style="{cell_style}">'
            f'<div style="margin-bottom:6px;">{img_html}</div>'
            f'<div style="margin-bottom:4px;">{title_html}</div>'
            f'<div>{pricing_html}</div>'
            "</td>"
        )
    # 2x2 grid: pad to 4 cells
    while len(cells) < 4:
        cells.append(f'<td style="{cell_style}"></td>')
    row1 = f"<tr>{cells[0]}{cells[1]}</tr>"
    row2 = f"<tr>{cells[2]}{cells[3]}</tr>"
    title_row = ""
    if section_title:
        title_row = f'<tr><td colspan="2" style="padding-bottom:12px;"><span style="font-size:18px;font-weight:bold;color:{TEXT_PRIMARY};">{html_module.escape(section_title)}</span></td></tr>'
    return f'''
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="{_block_wrapper_style()}">
  <tr><td style="{_block_cell_style()}">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      {title_row}
      {row1}
      {row2}
    </table>
  </td></tr>
</table>'''


def _render_featured(
    block: dict,
    game: dict | None,
    options: dict,
) -> str:
    if not game:
        return ""
    cfg = block.get("config") or {}
    image_source = (cfg.get("image_source") or "feed").strip() or "feed"
    capsule_size = (cfg.get("capsule_size") or "header").strip() or "header"
    description = (cfg.get("description") or "").strip() or (game.get("short_description") or "").strip()
    offer_ends = (cfg.get("offer_ends") or "").strip() or (game.get("sale_end_display") or "").strip()
    currency = options.get("currency") or "USD"
    show_price = options.get("show_price", True)
    show_both = options.get("show_both", False)
    coupon_percent = float(options.get("coupon_percent") or 0)

    link = (game.get("link") or "").strip()
    title = (game.get("title") or "").strip() or "Game"
    img_url = _game_image_url(game, image_source, capsule_size) or ""
    pricing_html = _render_pricing_html(game, currency, show_price, coupon_percent, show_both=show_both)
    img_html = ""
    if img_url:
        img_html = f'<a href="{html_module.escape(link)}"><img src="{html_module.escape(img_url)}" alt="{html_module.escape(title)}" style="width:100%;max-width:100%;height:auto;display:block;border:0;" /></a>' if link else f'<img src="{html_module.escape(img_url)}" alt="{html_module.escape(title)}" style="width:100%;max-width:100%;height:auto;display:block;border:0;" />'
    title_html = f'<a href="{html_module.escape(link)}" style="color:{LINK_COLOR};text-decoration:none;font-size:20px;font-weight:bold;">{html_module.escape(title)}</a>' if link else f'<span style="color:{TEXT_PRIMARY};font-size:20px;font-weight:bold;">{html_module.escape(title)}</span>'
    offer_html = f'<p style="margin:0 0 8px 0;font-size:12px;color:{TEXT_SECONDARY};">{html_module.escape(offer_ends)}</p>' if offer_ends else ""
    desc_html = f'<p style="margin:8px 0 0 0;font-size:14px;line-height:1.5;color:{TEXT_PRIMARY};">{html_module.escape(description)}</p>' if description else ""
    return f'''
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="{_block_wrapper_style()}">
  <tr><td style="{_block_cell_style()}padding-top:0;">
    <div style="margin-bottom:12px;">{img_html}</div>
    <div style="margin-bottom:6px;">{title_html}</div>
    <div style="margin-bottom:6px;">{pricing_html}</div>
    {offer_html}
    {desc_html}
  </td></tr>
</table>'''


def _render_text(block: dict) -> str:
    cfg = block.get("config") or {}
    content = (cfg.get("content") or "").strip() or ""
    if not content:
        return ""
    return f'''
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="{_block_wrapper_style()}">
  <tr><td style="{_block_cell_style()}line-height:1.5;font-size:14px;color:{TEXT_PRIMARY};">{content}</td></tr>
</table>'''


def _render_picture(block: dict) -> str:
    cfg = block.get("config") or {}
    img_url = (cfg.get("image_url") or "").strip()
    link = (cfg.get("link_url") or "").strip()
    alt = (cfg.get("alt") or "").strip()
    if not img_url:
        return ""
    img = f'<img src="{html_module.escape(img_url)}" alt="{html_module.escape(alt)}" style="max-width:100%;height:auto;display:block;border:0;" />'
    content = f'<a href="{html_module.escape(link)}">{img}</a>' if link else img
    return f'''
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="{_block_wrapper_style()}">
  <tr><td style="{_block_cell_style()}" align="center">{content}</td></tr>
</table>'''


def _render_button(block: dict) -> str:
    cfg = block.get("config") or {}
    text = (cfg.get("text") or "View more").strip()
    url = (cfg.get("url") or "").strip()
    if not url:
        url = "#"
    return f'''
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="{_block_wrapper_style()}">
  <tr><td style="{_block_cell_style()}" align="center"><a href="{html_module.escape(url)}" style="display:inline-block;padding:14px 28px;background:{BUTTON_BG};color:{BUTTON_COLOR};text-decoration:none;font-weight:bold;font-size:14px;border-radius:6px;">{html_module.escape(text)}</a></td></tr>
</table>'''


def _render_game_screenshots(
    block: dict,
    game: dict | None,
    screenshot_urls: list[str],
) -> str:
    """Render 2x2 grid of screenshots; each links to game's Playsum product page."""
    if not game or not screenshot_urls:
        return ""
    link = (game.get("link") or "").strip()
    # Pad to 4 for 2x2
    urls = (screenshot_urls + [""] * 4)[:4]
    cells = []
    for u in urls:
        if u:
            img = f'<img src="{html_module.escape(u)}" alt="" style="width:100%;max-width:280px;height:auto;display:block;border:0;" />'
            cell_content = f'<a href="{html_module.escape(link)}">{img}</a>' if link else img
        else:
            cell_content = ""
        cells.append(f'<td width="50%" style="padding:4px;vertical-align:top;">{cell_content}</td>')
    row1 = f"<tr>{cells[0]}{cells[1]}</tr>"
    row2 = f"<tr>{cells[2]}{cells[3]}</tr>"
    caption = (block.get("config") or {}).get("caption") or ""
    cap_html = f'<tr><td colspan="2" style="padding-bottom:8px;font-size:14px;color:{TEXT_PRIMARY};">{html_module.escape(caption)}</td></tr>' if caption else ""
    return f'''
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="{_block_wrapper_style()}">
  <tr><td style="{_block_cell_style()}">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{cap_html}
      {row1}
      {row2}
    </table>
  </td></tr>
</table>'''


def _render_footer(block: dict) -> str:
    cfg = block.get("config") or {}
    unsubscribe = (cfg.get("unsubscribe_url") or "").strip()
    privacy = (cfg.get("privacy_url") or "").strip()
    terms = (cfg.get("terms_url") or "").strip()
    address = (cfg.get("address") or "").strip()
    lines = []
    if unsubscribe:
        lines.append(f'<a href="{html_module.escape(unsubscribe)}" style="color:{LINK_COLOR};text-decoration:none;">Unsubscribe</a>')
    if privacy:
        lines.append(f'<a href="{html_module.escape(privacy)}" style="color:{LINK_COLOR};text-decoration:none;">Privacy Policy</a>')
    if terms:
        lines.append(f'<a href="{html_module.escape(terms)}" style="color:{LINK_COLOR};text-decoration:none;">Terms</a>')
    if address:
        lines.append(f'<span style="color:{TEXT_SECONDARY};">{html_module.escape(address)}</span>')
    content = " | ".join(lines) if lines else "Footer"
    return f'''
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="{_block_wrapper_style()}">
  <tr><td style="padding-top:24px;padding-bottom:{CELL_PADDING}px;padding-left:{CELL_PADDING}px;padding-right:{CELL_PADDING}px;font-size:11px;color:{TEXT_SECONDARY};" align="center">{content}</td></tr>
</table>'''


def build_email_html(
    blocks: list[dict],
    game_pool: list[dict],
    options: dict,
    get_screenshots: callable = None,
) -> str:
    """
    Build full email HTML from block list and game pool.
    blocks: list of { "type": "header"|"title"|"deal_list"|"featured"|"text"|"picture"|"button"|"game_screenshots"|"footer", "config": {...} }.
    game_pool: list of product dicts (order: featured first, then deal list fill).
    options: { currency, show_price (True=price False=discount%), coupon_percent }.
    get_screenshots: optional callable(app_id) -> list of up to 4 image URLs for game_screenshots block.
    """
    options = options or {}
    get_screenshots = get_screenshots or (lambda app_id: [])
    pool_idx = [0]

    def next_games(n: int) -> list[dict]:
        start = pool_idx[0]
        pool_idx[0] = min(start + n, len(game_pool))
        return game_pool[start:pool_idx[0]]

    def next_game() -> dict | None:
        g = next_games(1)
        return g[0] if g else None

    fragments = []
    for block in blocks:
        btype = (block.get("type") or "").strip().lower()
        if btype == "header":
            fragments.append(_render_header(block))
        elif btype == "title":
            fragments.append(_render_title(block))
        elif btype == "deal_list":
            count = int((block.get("config") or {}).get("games_count") or 4)
            games = next_games(count)
            fragments.append(_render_deal_list(block, games, options))
        elif btype == "featured":
            game = next_game()
            fragments.append(_render_featured(block, game, options))
        elif btype == "text":
            fragments.append(_render_text(block))
        elif btype == "picture":
            fragments.append(_render_picture(block))
        elif btype == "button":
            fragments.append(_render_button(block))
        elif btype == "game_screenshots":
            cfg = block.get("config") or {}
            game = cfg.get("product")
            if game is None and isinstance(cfg.get("game_index"), int):
                gi = cfg["game_index"]
                if 0 <= gi < len(game_pool):
                    game = game_pool[gi]
            if game is None:
                game = next_game()
            if game and game.get("steam_app_id") is not None:
                urls = get_screenshots(game["steam_app_id"])
            else:
                urls = []
            fragments.append(_render_game_screenshots(block, game, urls))
        elif btype == "footer":
            fragments.append(_render_footer(block))

    body = "\n".join(f for f in fragments if f)
    return f'''<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:{BG_DARK};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG_DARK};">
  <tr><td style="padding:20px 10px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:{WRAPPER_WIDTH}px;margin:0 auto;background:{BG_INNER};">
  <tr><td>
{body}
  </td></tr>
</table>
  </td></tr>
</table>
</body>
</html>'''
