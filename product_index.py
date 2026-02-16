"""Index feed items by product URL and resolve pasted URLs to products."""

import json
import os

from feed_client import parse_feed
from config import STEAM_MAPPING_PATH


def normalize_url(url: str) -> str:
    """Normalize URL for matching: strip whitespace, trailing slash, fragment."""
    if not url or not isinstance(url, str):
        return ""
    u = url.strip()
    if not u:
        return ""
    # Strip fragment
    if "#" in u:
        u = u.split("#", 1)[0]
    # Strip trailing slash
    u = u.rstrip("/")
    return u


def _platform_abbrev(systems: str) -> str:
    """Convert operatingSystems string to 'W, M, L' style."""
    if not systems:
        return ""
    parts = []
    upper = systems.upper()
    if "WINDOWS" in upper:
        parts.append("W")
    if "MAC" in upper:
        parts.append("M")
    if "LINUX" in upper:
        parts.append("L")
    return ", ".join(parts) if parts else ""


def _load_steam_mapping() -> dict[str, int]:
    """Load Steam App ID mapping: normalized product URL -> app_id."""
    if not os.path.isfile(STEAM_MAPPING_PATH):
        return {}
    try:
        with open(STEAM_MAPPING_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    out = {}
    for k, v in data.items():
        if v is None:
            continue
        try:
            app_id = int(v)
        except (TypeError, ValueError):
            continue
        out[normalize_url(str(k))] = app_id
    return out


def build_index(items: list[dict]) -> dict[str, dict]:
    """
    Group feed items by product URL. Each product has one or more variants.
    Returns dict: normalized_product_url -> product record.
    Product record: title, link, platform, variants_by_currency, steam_app_id (if from feed or mapping).
    For each (product, currency) we keep one variant (first seen).
    """
    steam_mapping = _load_steam_mapping()
    index = {}
    for it in items:
        link = it.get("link", "").strip()
        if not link:
            continue
        key = normalize_url(link)
        if not key:
            continue
        title = it.get("title", "").strip()
        platform = _platform_abbrev(it.get("operatingSystems", ""))
        currency = (it.get("currency") or "").strip().upper()
        if not currency:
            continue
        variant = {
            "currency": currency,
            "discountPrice": it.get("discountPrice"),
            "discountPercentage": it.get("discountPercentage"),
            "discountStartDate": it.get("discountStartDate"),
            "discountEndDate": it.get("discountEndDate"),
            "originalPrice": it.get("originalPrice"),
        }
        steam_app_id = it.get("steam_app_id")
        cover_image = it.get("cover_image") or None
        if key not in index:
            index[key] = {
                "title": title,
                "link": link,
                "platform": platform,
                "variants_by_currency": {},
                "steam_app_id": steam_app_id,
                "cover_image": cover_image,
            }
        # One variant per currency (first seen)
        if currency not in index[key]["variants_by_currency"]:
            index[key]["variants_by_currency"][currency] = variant
        if platform and not index[key]["platform"]:
            index[key]["platform"] = platform
        if title and not index[key]["title"]:
            index[key]["title"] = title
        if steam_app_id is not None and index[key]["steam_app_id"] is None:
            index[key]["steam_app_id"] = steam_app_id
        if cover_image and not index[key].get("cover_image"):
            index[key]["cover_image"] = cover_image
    # Apply mapping file (overrides or sets steam_app_id)
    for url_key, app_id in steam_mapping.items():
        if url_key in index:
            index[url_key]["steam_app_id"] = app_id
    return index


def resolve_urls_to_products(
    index: dict[str, dict],
    pasted_urls: list[str],
) -> tuple[list[dict], list[str]]:
    """
    Resolve a list of pasted URLs to product records.
    Returns (list of product dicts in order of first appearance, list of not-found URLs).
    """
    seen_keys = set()
    products = []
    not_found = []
    for raw in pasted_urls:
        key = normalize_url(raw)
        if not key:
            continue
        if key in index:
            if key not in seen_keys:
                seen_keys.add(key)
                products.append(index[key])
        else:
            not_found.append(raw.strip())
    return products, not_found


def items_to_index(items: list[dict]) -> dict[str, dict]:
    """Build product index from parsed feed items."""
    return build_index(items)
