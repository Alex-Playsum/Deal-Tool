"""Fetch Steam app review summary and appdetails from store.steampowered.com (no API key)."""

import time

import requests

from config import STEAM_APPREVIEWS_URL_TEMPLATE, STEAM_APPDETAILS_URL_TEMPLATE
from steam_cache import get as cache_get, set as cache_set
from steam_appdetails_cache import get as appdetails_cache_get, set as appdetails_cache_set

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
