"""Disk cache for Steam review data (query_summary per app_id) with TTL."""

import json
import os
from datetime import datetime, timedelta

from config import STEAM_CACHE_PATH, STEAM_CACHE_TTL_HOURS


def _load_all() -> dict:
    """Load full cache from disk. Returns dict app_id_str -> {query_summary, fetched_at}."""
    if not os.path.isfile(STEAM_CACHE_PATH):
        return {}
    try:
        with open(STEAM_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_all(data: dict) -> None:
    """Write full cache to disk."""
    dirpath = os.path.dirname(STEAM_CACHE_PATH)
    if dirpath and not os.path.isdir(dirpath):
        os.makedirs(dirpath, exist_ok=True)
    with open(STEAM_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=0)


def _is_expired(fetched_at: str) -> bool:
    """Return True if fetched_at is older than TTL. Stored times are UTC (naive)."""
    try:
        dt = datetime.fromisoformat(fetched_at.replace("Z", ""))
    except (ValueError, TypeError):
        return True
    now = datetime.utcnow()
    return (now - dt) > timedelta(hours=STEAM_CACHE_TTL_HOURS)


def get(app_id: int | str) -> dict | None:
    """
    Return cached query_summary for app_id, or None if missing/expired.
    """
    data = _load_all()
    key = str(app_id)
    if key not in data:
        return None
    entry = data[key]
    fetched_at = entry.get("fetched_at", "")
    if _is_expired(fetched_at):
        return None
    return entry.get("query_summary")


def set(app_id: int | str, query_summary: dict) -> None:
    """Store query_summary for app_id with current timestamp."""
    data = _load_all()
    data[str(app_id)] = {
        "query_summary": query_summary,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    }
    _save_all(data)


def clear() -> None:
    """Remove all cached entries from disk."""
    if os.path.isfile(STEAM_CACHE_PATH):
        os.remove(STEAM_CACHE_PATH)
