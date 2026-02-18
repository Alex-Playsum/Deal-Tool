"""Get products currently on sale from the index; resolve Steam App ID by name when needed."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import STEAM_WEB_API_KEY
from steam_app_list import get_app_list, resolve_name_to_app_id_cached
from steam_client import fetch_app_reviews, fetch_app_details_full
from steamspy_client import fetch_steamspy_tags


def _is_on_sale(product: dict) -> bool:
    """True if at least one variant has discountPrice or discountPercentage."""
    variants = product.get("variants_by_currency") or {}
    for v in variants.values():
        if v.get("discountPrice") is not None:
            return True
        if (v.get("discountPercentage") or "").strip():
            return True
    return False


def _discount_pct(product: dict) -> int | None:
    """Best discount percentage from any variant, or None."""
    variants = product.get("variants_by_currency") or {}
    best = None
    for v in variants.values():
        pct = (v.get("discountPercentage") or "").strip()
        if pct:
            try:
                n = int(pct)
                if best is None or n > best:
                    best = n
            except ValueError:
                pass
    return best


def _discount_str(product: dict) -> str:
    """Best discount percentage from any variant, or empty."""
    best = _discount_pct(product)
    return f"{best}%" if best is not None else ""


def _sale_end_ms(product: dict) -> int | None:
    """Latest discount end timestamp (Unix ms) from any variant, or None if none."""
    variants = product.get("variants_by_currency") or {}
    latest_ms = None
    for v in variants.values():
        raw = v.get("discountEndDate")
        if raw is None:
            continue
        try:
            ms = int(raw) if isinstance(raw, (int, float)) else int(str(raw).strip())
            if latest_ms is None or ms > latest_ms:
                latest_ms = ms
        except (ValueError, TypeError):
            pass
    return latest_ms


def _sale_end_str(product: dict) -> str:
    """Latest discount end date and time from any variant (Unix ms), in Eastern (ET), 12-hour format; or "—" if none."""
    latest_ms = _sale_end_ms(product)
    if latest_ms is None:
        return "—"
    try:
        dt_utc = datetime.fromtimestamp(latest_ms / 1000.0, tz=timezone.utc)
        dt_eastern = dt_utc.astimezone(ZoneInfo("America/New_York"))
        return dt_eastern.strftime("%Y-%m-%d %I:%M %p ET")
    except (ValueError, OSError):
        return "—"


def _release_date_str(product: dict) -> str:
    """Release date from Steam appdetails, or "—" if not available."""
    return product.get("steam_release_date") or "—"


def get_on_sale_products(index: dict[str, dict], resolve_steam_by_name: bool = True) -> list[dict]:
    """
    Return list of products that are currently on sale (any variant has discount).
    Products are dicts with title, link, platform, variants_by_currency, steam_app_id.
    If resolve_steam_by_name is True and STEAM_WEB_API_KEY is set, products without
    steam_app_id get it resolved via Steam app list name match.
    """
    on_sale = [p for p in index.values() if _is_on_sale(p)]
    if not resolve_steam_by_name or not (STEAM_WEB_API_KEY and STEAM_WEB_API_KEY.strip()):
        return on_sale
    app_list = get_app_list()
    if not app_list:
        return on_sale
    for p in on_sale:
        if p.get("steam_app_id") is not None:
            continue
        title = (p.get("title") or "").strip()
        if not title:
            continue
        app_id = resolve_name_to_app_id_cached(title, app_list)
        if app_id is not None:
            p["steam_app_id"] = app_id
    return on_sale


def enrich_with_steam_reviews(
    products: list[dict],
    progress_callback=None,
) -> list[dict]:
    """
    For each product with steam_app_id, fetch review summary and attach:
    steam_percent_positive, steam_review_desc, steam_total_reviews.
    Products without data get None for those keys. Sorted by percent best first (N/A last).
    progress_callback(current_index, total) called during fetch if provided.
    """
    total = len(products)
    rows = []
    for i, p in enumerate(products):
        if progress_callback:
            progress_callback(i, total)
        row = dict(p)
        app_id = p.get("steam_app_id")
        if app_id is None:
            row["steam_percent_positive"] = None
            row["steam_review_desc"] = None
            row["steam_total_reviews"] = None
            row["steam_release_date"] = None
            row["steam_developer"] = None
            row["steam_publisher"] = None
            row["steam_tags"] = []
            rows.append(row)
            continue
        summary = fetch_app_reviews(app_id, use_cache=True)
        details = fetch_app_details_full(app_id, use_cache=True)
        release_date = details.get("release_date") if details else None
        row["steam_release_date"] = release_date
        row["steam_developer"] = details.get("developer") if details else None
        row["steam_publisher"] = details.get("publisher") if details else None
        row["steam_tags"] = fetch_steamspy_tags(app_id, use_cache=True)
        if not summary:
            row["steam_percent_positive"] = None
            row["steam_review_desc"] = None
            row["steam_total_reviews"] = None
            rows.append(row)
            continue
        total_reviews = summary.get("total_reviews") or 0
        total_positive = summary.get("total_positive") or 0
        if total_reviews > 0:
            row["steam_percent_positive"] = round(100 * total_positive / total_reviews)
        else:
            row["steam_percent_positive"] = None
        row["steam_review_desc"] = (summary.get("review_score_desc") or "").strip() or None
        row["steam_total_reviews"] = total_reviews
        rows.append(row)
    if progress_callback:
        progress_callback(total, total)
    # Sort: best rating first, then by total_reviews desc; N/A at end
    def sort_key(r):
        pct = r.get("steam_percent_positive")
        rev = r.get("steam_total_reviews") or 0
        if pct is None:
            return (-1, 0)
        return (-pct, -rev)
    rows.sort(key=sort_key)
    return rows
