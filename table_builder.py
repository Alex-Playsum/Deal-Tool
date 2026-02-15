"""Build Reddit markdown table from product list and selected currencies."""

from config import CURRENCY_LABELS, COUPON_MULTIPLIER


def _base_price(variant: dict) -> float:
    """Price to use for display: discountPrice if present, else originalPrice."""
    base = variant.get("discountPrice")
    if base is not None:
        return float(base)
    return float(variant.get("originalPrice", 0))


def _percent_off_with_code(variant: dict) -> int:
    """Compute % off after 10% coupon: (1 - final/original)*100 rounded."""
    original = float(variant.get("originalPrice", 0))
    if original <= 0:
        return 0
    base = _base_price(variant)
    final = base * COUPON_MULTIPLIER
    return round((1 - final / original) * 100)


def _variant_for_percent(product: dict) -> dict | None:
    """Pick one variant to compute % off (prefer USD, else first)."""
    by_curr = product.get("variants_by_currency") or {}
    if by_curr.get("USD"):
        return by_curr["USD"]
    for v in by_curr.values():
        return v
    return None


def build_reddit_table(
    products: list[dict],
    currencies: list[str],
) -> str:
    """
    Build Reddit markdown table.
    products: list from resolve_urls_to_products (title, link, platform, variants_by_currency).
    currencies: list of currency codes (e.g. ["USD", "EUR", "CAD", "GBP"]).
    """
    if not products:
        return ""

    # Header: Deals | Platform | % Off w/ code | <currency cols> | Types
    header_cells = ["Deals", "Platform", "% Off w/ code"]
    for code in currencies:
        header_cells.append(CURRENCY_LABELS.get(code, code))
    header_cells.append("Types")
    sep = " | "
    header = "| " + sep.join(header_cells) + " |"
    separator = "| " + sep.join(["---"] * len(header_cells)) + " |"
    rows = [header, separator]

    for product in products:
        title = product.get("title", "").strip() or "Unknown"
        link = product.get("link", "").strip()
        platform = product.get("platform", "").strip() or "N/A"
        by_curr = product.get("variants_by_currency") or {}

        # % off: from one variant (USD or first)
        variant_for_pct = _variant_for_percent(product)
        pct_str = "0%"
        if variant_for_pct:
            pct_str = f"{_percent_off_with_code(variant_for_pct)}%"
        else:
            pct_str = "N/A"

        # Reddit link for title
        deal_cell = f"[{title}]({link})" if link else title

        cells = [deal_cell, platform, pct_str]
        for code in currencies:
            v = by_curr.get(code)
            if v is None:
                cells.append("N/A")
            else:
                base = _base_price(v)
                final = round(base * COUPON_MULTIPLIER, 2)
                cells.append(f"{final:.2f}")
        cells.append("Steam")

        # Escape pipe in cell text for Reddit (if title contains |)
        cells_escaped = [str(c).replace("|", "\\|") for c in cells]
        rows.append("| " + sep.join(cells_escaped) + " |")

    return "\n".join(rows)
