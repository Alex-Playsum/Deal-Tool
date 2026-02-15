"""Disk cache for Steam appdetails (e.g. release_date) per app_id with TTL."""

import json
import os
from datetime import datetime, timedelta

from config import STEAM_APPDETAILS_CACHE_PATH, STEAM_APPDETAILS_CACHE_TTL_HOURS


def _load_all() -> dict:
    """Load full cache from disk. Returns dict app_id_str -> {release_date, fetched_at}."""
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


def set(app_id: int | str, release_date: str | None) -> None:
    """Store release_date for app_id with current timestamp."""
    data = _load_all()
    data[str(app_id)] = {
        "release_date": release_date,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    }
    _save_all(data)


def clear() -> None:
    """Remove cache file from disk."""
    if os.path.isfile(STEAM_APPDETAILS_CACHE_PATH):
        os.remove(STEAM_APPDETAILS_CACHE_PATH)
