"""Fetch and parse the Playsum product RSS feed."""

import re
import xml.etree.ElementTree as ET

import requests

from config import FEED_URL, FEED_STEAM_APP_ID_TAG


def _local_name(tag: str) -> str:
    """Strip XML namespace from tag name if present."""
    if tag and "}" in tag:
        return tag.split("}", 1)[1]
    return tag or ""


def _text(el) -> str:
    """Get element text, or empty string if None or no text."""
    if el is None:
        return ""
    return (el.text or "").strip()


def _float_or_none(s: str):
    """Parse string to float or None if empty/invalid."""
    if not s or not s.strip():
        return None
    try:
        return float(s.strip())
    except ValueError:
        return None


def fetch_feed(url: str = FEED_URL, timeout: int = 30) -> str:
    """Fetch the RSS feed and return raw XML string."""
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def parse_feed(xml_content: str) -> list[dict]:
    """
    Parse RSS XML and return a list of item dicts.
    Each dict has: title, link, operatingSystems, currency, discountPrice,
    discountPercentage, originalPrice (and optionally other fields).
    """
    root = ET.fromstring(xml_content)
    # Find channel: may be {ns}rss/{ns}channel or rss/channel
    channel = root.find("channel")
    if channel is None:
        for child in root:
            if _local_name(child.tag) == "channel":
                channel = child
                break
    if channel is None:
        return []

    items = []
    for item_el in channel:
        if _local_name(item_el.tag) != "item":
            continue
        # Collect all child elements by local name
        data = {}
        for child in item_el:
            name = _local_name(child.tag)
            text = _text(child)
            data[name] = text

        title = data.get("title", "").strip()
        link = data.get("link", "").strip() or data.get("guid", "").strip()
        if not link and not title:
            continue

        operating_systems = data.get("operatingSystems", "").strip()
        currency = data.get("currency", "").strip().upper() or None
        discount_price = _float_or_none(data.get("discountPrice", ""))
        discount_percentage = data.get("discountPercentage", "").strip()
        original_price = _float_or_none(data.get("originalPrice", ""))
        discount_start = data.get("discountStartDate", "").strip()
        discount_end = data.get("discountEndDate", "").strip()

        if original_price is None:
            continue

        steam_app_id = None
        if FEED_STEAM_APP_ID_TAG and FEED_STEAM_APP_ID_TAG.strip():
            raw_id = data.get(FEED_STEAM_APP_ID_TAG.strip(), "").strip()
            if raw_id:
                try:
                    steam_app_id = int(raw_id)
                except ValueError:
                    pass

        items.append({
            "title": title,
            "link": link,
            "operatingSystems": operating_systems,
            "currency": currency,
            "discountPrice": discount_price,
            "discountPercentage": discount_percentage,
            "discountStartDate": discount_start or None,
            "discountEndDate": discount_end or None,
            "originalPrice": original_price,
            "steam_app_id": steam_app_id,
        })
    return items


def fetch_and_parse(url: str = FEED_URL, timeout: int = 30) -> list[dict]:
    """Fetch the feed and return parsed item list."""
    xml_content = fetch_feed(url=url, timeout=timeout)
    return parse_feed(xml_content)
