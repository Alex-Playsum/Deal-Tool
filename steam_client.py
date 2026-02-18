"""Fetch Steam app review summary and appdetails from store.steampowered.com (no API key)."""

import time

import requests

from config import STEAM_APPREVIEWS_URL_TEMPLATE, STEAM_APPDETAILS_URL_TEMPLATE
from steam_cache import get as cache_get, set as cache_set
from steam_appdetails_cache import (
    get as appdetails_cache_get,
    get_developer as appdetails_cache_get_developer,
    get_publisher as appdetails_cache_get_publisher,
    get_screenshots as appdetails_cache_get_screenshots,
    get_short_description as appdetails_cache_get_short_description,
    has_entry as appdetails_cache_has_entry,
    set as appdetails_cache_set,
    set_full as appdetails_cache_set_full,
)
from steam_images import STEAM_CDN_BASE, STEAM_IMAGE_PATHS

# Delay in seconds between requests when fetching many (be respectful to store)
REQUEST_DELAY_SECONDS = 0.4


def fetch_app_reviews(app_id: int | str, use_cache: bool = True) -> dict | None:
    """
    Fetch review query_summary for the given Steam app_id.
    Returns query_summary dict (review_score_desc, total_positive, total_reviews, etc.) or None.
    Uses steam_cache when use_cache is True; adds a short delay after the request.
    """
    app_id = int(app_id)
    if use_cache:
        cached = cache_get(app_id)
        if cached is not None:
            return cached
    url = STEAM_APPREVIEWS_URL_TEMPLATE.format(app_id=app_id)
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success") or "query_summary" not in data:
            return None
        summary = data["query_summary"]
        if use_cache:
            cache_set(app_id, summary)
        time.sleep(REQUEST_DELAY_SECONDS)
        return summary
    except (requests.RequestException, KeyError, TypeError):
        return None


def fetch_app_details(app_id: int | str, use_cache: bool = True) -> str | None:
    """
    Fetch appdetails for the given Steam app_id and return release_date string (e.g. "Aug 21, 2012").
    Returns None if missing, coming_soon, or on error. Uses appdetails cache when use_cache is True.
    """
    app_id = int(app_id)
    if use_cache:
        cached = appdetails_cache_get(app_id)
        if cached is not None:
            return cached
    url = STEAM_APPDETAILS_URL_TEMPLATE.format(app_id=app_id)
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        key = str(app_id)
        if key not in data or not data[key].get("success"):
            appdetails_cache_set(app_id, None)
            time.sleep(REQUEST_DELAY_SECONDS)
            return None
        inner = data[key].get("data") or {}
        release = inner.get("release_date") or {}
        if release.get("coming_soon"):
            date_str = None
        else:
            date_str = (release.get("date") or "").strip() or None
        if use_cache:
            appdetails_cache_set(app_id, date_str)
        time.sleep(REQUEST_DELAY_SECONDS)
        return date_str
    except (requests.RequestException, KeyError, TypeError):
        return None


def _build_capsule_urls(app_id: int) -> dict[str, str]:
    """Build capsule/header CDN URLs for all sizes (same as steam_images)."""
    urls = {}
    for size, path_tpl in STEAM_IMAGE_PATHS.items():
        rel = path_tpl.format(app_id=app_id)
        url = STEAM_CDN_BASE + ("/" + rel if not rel.startswith("/") else rel)
        urls[size] = url
    return urls


def fetch_app_details_full(app_id: int | str, use_cache: bool = True) -> dict | None:
    """
    Fetch appdetails and return { "release_date", "screenshots", "short_description", "developer", "publisher" }.
    Caches result. Uses cache whenever we have a valid entry. Refetches if cache has no developer/publisher (backfill).
    Saves capsule_urls, developer, publisher to cache.
    """
    app_id = int(app_id)
    if use_cache and appdetails_cache_has_entry(app_id):
        cached = {
            "release_date": appdetails_cache_get(app_id),
            "screenshots": appdetails_cache_get_screenshots(app_id, max_count=4),
            "short_description": appdetails_cache_get_short_description(app_id),
            "developer": appdetails_cache_get_developer(app_id),
            "publisher": appdetails_cache_get_publisher(app_id),
        }
        # Backfill: old cache entries lack developer/publisher; refetch to populate
        if cached.get("developer") is not None or cached.get("publisher") is not None:
            return cached
    url = STEAM_APPDETAILS_URL_TEMPLATE.format(app_id=app_id)
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        key = str(app_id)
        if key not in data or not data[key].get("success"):
            time.sleep(REQUEST_DELAY_SECONDS)
            return None
        inner = data[key].get("data") or {}
        release = inner.get("release_date") or {}
        if release.get("coming_soon"):
            date_str = None
        else:
            date_str = (release.get("date") or "").strip() or None
        screenshots_raw = inner.get("screenshots") or []
        screenshots = []
        for s in screenshots_raw[:4]:
            path = (s or {}).get("path_full")
            if path:
                if not path.startswith("http"):
                    path = "https://cdn.cloudflare.steamstatic.com" + (path if path.startswith("/") else "/" + path)
                screenshots.append(path)
        short_desc = (inner.get("short_description") or "").strip() or None
        developers_raw = inner.get("developers") or []
        if isinstance(developers_raw, dict):
            developers_raw = list(developers_raw.values())
        developer = ", ".join(str(x).strip() for x in developers_raw if x and str(x).strip()) or None
        publishers_raw = inner.get("publishers") or []
        if isinstance(publishers_raw, dict):
            publishers_raw = list(publishers_raw.values())
        publisher = ", ".join(str(x).strip() for x in publishers_raw if x and str(x).strip()) or None
        capsule_urls = _build_capsule_urls(app_id)
        appdetails_cache_set_full(
            app_id, date_str, screenshots,
            short_description=short_desc, capsule_urls=capsule_urls,
            developer=developer, publisher=publisher,
        )
        time.sleep(REQUEST_DELAY_SECONDS)
        return {
            "release_date": date_str,
            "screenshots": screenshots,
            "short_description": short_desc,
            "developer": developer,
            "publisher": publisher,
        }
    except (requests.RequestException, KeyError, TypeError):
        return None
