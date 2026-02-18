"""Fetch SteamSpy appdetails (tags) with disk cache."""

import json
import os
import time
from datetime import datetime, timedelta

import requests

from config import STEAMSPY_APPDETAILS_URL, STEAMSPY_CACHE_PATH, STEAMSPY_CACHE_TTL_HOURS

REQUEST_DELAY_SECONDS = 0.3


def _load_cache() -> dict:
    """Load full cache from disk. Returns dict app_id_str -> {tags: list[str], fetched_at: str}."""
    if not os.path.isfile(STEAMSPY_CACHE_PATH):
        return {}
    try:
        with open(STEAMSPY_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(data: dict) -> None:
    """Write cache to disk."""
    dirpath = os.path.dirname(STEAMSPY_CACHE_PATH)
    if dirpath and not os.path.isdir(dirpath):
        os.makedirs(dirpath, exist_ok=True)
    with open(STEAMSPY_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=0)


def _is_expired(fetched_at: str) -> bool:
    try:
        dt = datetime.fromisoformat(fetched_at.replace("Z", ""))
    except (ValueError, TypeError):
        return True
    return (datetime.utcnow() - dt) > timedelta(hours=STEAMSPY_CACHE_TTL_HOURS)


def fetch_steamspy_tags(app_id: int | str, use_cache: bool = True) -> list[str]:
    """
    Fetch SteamSpy appdetails for the given app_id and return list of tag names (keys of "tags" object).
    Cached to disk. Returns [] on miss or error.
    """
    app_id = int(app_id)
    key = str(app_id)
    if use_cache:
        data = _load_cache()
        if key in data and not _is_expired(data[key].get("fetched_at", "")):
            return list(data[key].get("tags") or [])
    url = STEAMSPY_APPDETAILS_URL.format(app_id=app_id)
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        body = resp.json()
        tags_obj = body.get("tags")
        if isinstance(tags_obj, dict):
            tag_names = [str(k).strip() for k in tags_obj.keys() if k and str(k).strip()]
            if use_cache:
                data = _load_cache()
                data[key] = {"tags": tag_names, "fetched_at": datetime.utcnow().isoformat() + "Z"}
                _save_cache(data)
        else:
            tag_names = []
        time.sleep(REQUEST_DELAY_SECONDS)
        return tag_names
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return []


def clear_steamspy_cache() -> None:
    """Remove SteamSpy cache file from disk."""
    if os.path.isfile(STEAMSPY_CACHE_PATH):
        os.remove(STEAMSPY_CACHE_PATH)
