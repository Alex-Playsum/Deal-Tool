"""Disk cache for Steam appdetails (e.g. release_date) per app_id with TTL."""

import json
import os
from datetime import datetime, timedelta

from config import STEAM_APPDETAILS_CACHE_PATH, STEAM_APPDETAILS_CACHE_TTL_HOURS


def _load_all() -> dict:
    """Load full cache from disk. Returns dict app_id_str -> {release_date?, screenshots?, short_description?, fetched_at}."""
    if not os.path.isfile(STEAM_APPDETAILS_CACHE_PATH):
        return {}
    try:
        with open(STEAM_APPDETAILS_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_all(data: dict) -> None:
    """Write full cache to disk."""
    dirpath = os.path.dirname(STEAM_APPDETAILS_CACHE_PATH)
    if dirpath and not os.path.isdir(dirpath):
        os.makedirs(dirpath, exist_ok=True)
    with open(STEAM_APPDETAILS_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=0)


def _is_expired(fetched_at: str) -> bool:
    """Return True if fetched_at is older than TTL."""
    try:
        dt = datetime.fromisoformat(fetched_at.replace("Z", ""))
    except (ValueError, TypeError):
        return True
    now = datetime.utcnow()
    return (now - dt) > timedelta(hours=STEAM_APPDETAILS_CACHE_TTL_HOURS)


def has_entry(app_id: int | str) -> bool:
    """Return True if app_id has a valid (non-expired) cache entry."""
    data = _load_all()
    key = str(app_id)
    if key not in data:
        return False
    return not _is_expired(data[key].get("fetched_at", ""))


def get(app_id: int | str) -> str | None:
    """Return cached release_date string for app_id, or None if missing/expired."""
    data = _load_all()
    key = str(app_id)
    if key not in data:
        return None
    entry = data[key]
    if _is_expired(entry.get("fetched_at", "")):
        return None
    return entry.get("release_date")


def get_screenshots(app_id: int | str, max_count: int = 4) -> list[str]:
    """Return cached screenshot path_full URLs for app_id (up to max_count). Empty if missing/expired."""
    data = _load_all()
    key = str(app_id)
    if key not in data:
        return []
    entry = data[key]
    if _is_expired(entry.get("fetched_at", "")):
        return []
    urls = entry.get("screenshots") or []
    return list(urls)[:max_count]


def get_short_description(app_id: int | str) -> str | None:
    """Return cached short_description for app_id, or None if missing/expired."""
    data = _load_all()
    key = str(app_id)
    if key not in data:
        return None
    entry = data[key]
    if _is_expired(entry.get("fetched_at", "")):
        return None
    return entry.get("short_description")


def get_capsule_url(app_id: int | str, size: str) -> str | None:
    """Return cached capsule/header URL for app_id and size (header, capsule_sm, capsule_md, capsule_616x353), or None if missing/expired."""
    data = _load_all()
    key = str(app_id)
    if key not in data:
        return None
    entry = data[key]
    if _is_expired(entry.get("fetched_at", "")):
        return None
    urls = entry.get("capsule_urls") or {}
    return urls.get(size)


def set(app_id: int | str, release_date: str | None) -> None:
    """Store release_date for app_id with current timestamp (merge; keeps existing screenshots)."""
    data = _load_all()
    key = str(app_id)
    now = datetime.utcnow().isoformat() + "Z"
    if key in data and not _is_expired(data[key].get("fetched_at", "")):
        data[key]["release_date"] = release_date
        data[key]["fetched_at"] = now
    else:
        existing = data.get(key) or {}
        data[key] = {
            "release_date": release_date,
            "screenshots": existing.get("screenshots") or [],
            "short_description": existing.get("short_description"),
            "fetched_at": now,
        }
    _save_all(data)


def set_full(
    app_id: int | str,
    release_date: str | None,
    screenshots: list[str],
    short_description: str | None = None,
    capsule_urls: dict | None = None,
) -> None:
    """Store full appdetails entry: release_date, screenshot path_full URLs, optional short_description, and optional capsule_urls dict (size -> URL)."""
    data = _load_all()
    data[str(app_id)] = {
        "release_date": release_date,
        "screenshots": list(screenshots),
        "short_description": short_description,
        "capsule_urls": dict(capsule_urls) if capsule_urls else {},
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    }
    _save_all(data)


def clear() -> None:
    """Remove cache file from disk."""
    if os.path.isfile(STEAM_APPDETAILS_CACHE_PATH):
        os.remove(STEAM_APPDETAILS_CACHE_PATH)
