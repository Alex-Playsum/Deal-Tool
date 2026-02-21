"""Fetch SteamSpy appdetails (tags) with disk cache."""

import json
import os
import re
import time
from datetime import datetime, timedelta

import requests

from config import STEAMSPY_APPDETAILS_URL, STEAMSPY_CACHE_PATH, STEAMSPY_CACHE_TTL_HOURS

REQUEST_DELAY_SECONDS = 0.3

# In-memory cache so we only read/parse the file once per process.
_memory: dict | None = None


def _load_cache() -> dict:
    """Load full cache from disk (or return in-memory copy). Returns dict app_id_str -> {tags, fetched_at}."""
    global _memory
    if _memory is not None:
        return _memory
    if not os.path.isfile(STEAMSPY_CACHE_PATH):
        _memory = {}
        return _memory
    try:
        with open(STEAMSPY_CACHE_PATH, encoding="utf-8") as f:
            _memory = json.load(f)
        return _memory
    except (json.JSONDecodeError, OSError):
        _memory = {}
        return _memory


def _save_cache(data: dict) -> None:
    """Write cache to disk and update in-memory cache."""
    global _memory
    dirpath = os.path.dirname(STEAMSPY_CACHE_PATH)
    if dirpath and not os.path.isdir(dirpath):
        os.makedirs(dirpath, exist_ok=True)
    with open(STEAMSPY_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=0)
    _memory = data


def _is_expired(fetched_at: str) -> bool:
    try:
        dt = datetime.fromisoformat(fetched_at.replace("Z", ""))
    except (ValueError, TypeError):
        return True
    return (datetime.utcnow() - dt) > timedelta(hours=STEAMSPY_CACHE_TTL_HOURS)


def _parse_owners_to_estimate(owners_str: str) -> int | None:
    """Parse SteamSpy owners string like '1,000,000 .. 2,000,000' to midpoint integer, or None."""
    if not owners_str or not isinstance(owners_str, str):
        return None
    s = owners_str.strip()
    if ".." in s:
        parts = s.split("..", 1)
        low = re.sub(r"[^\d]", "", parts[0].strip())
        high = re.sub(r"[^\d]", "", parts[1].strip())
        try:
            lo, hi = int(low or "0"), int(high or "0")
            return (lo + hi) // 2 if (lo or hi) else None
        except ValueError:
            return None
    try:
        return int(re.sub(r"[^\d]", "", s) or "0") or None
    except ValueError:
        return None


def fetch_steamspy_appdetails(app_id: int | str, use_cache: bool = True) -> dict:
    """
    Fetch SteamSpy appdetails for the given app_id.
    Returns dict with keys: tags (list[str]), owners_estimate (int | None), ccu (int | None), fetched_at (str).
    Cached to disk. On error returns {tags: [], owners_estimate: None, ccu: None}.
    """
    app_id = int(app_id)
    key = str(app_id)
    empty = {"tags": [], "owners_estimate": None, "ccu": None, "fetched_at": ""}
    if use_cache:
        data = _load_cache()
        if key in data and not _is_expired(data[key].get("fetched_at", "")):
            cached = data[key]
            if "owners_estimate" in cached and "ccu" in cached:
                return dict(cached)
    url = STEAMSPY_APPDETAILS_URL.format(app_id=app_id)
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        body = resp.json()
        tags_obj = body.get("tags")
        tag_names = [str(k).strip() for k in tags_obj.keys() if k and str(k).strip()] if isinstance(tags_obj, dict) else []
        owners_raw = body.get("owners")
        owners_estimate = _parse_owners_to_estimate(owners_raw) if owners_raw else None
        ccu = body.get("ccu")
        if ccu is not None and not isinstance(ccu, int):
            try:
                ccu = int(ccu)
            except (TypeError, ValueError):
                ccu = None
        fetched_at = datetime.utcnow().isoformat() + "Z"
        result = {"tags": tag_names, "owners_estimate": owners_estimate, "ccu": ccu, "fetched_at": fetched_at}
        if use_cache:
            data = _load_cache()
            data[key] = result
            _save_cache(data)
        time.sleep(REQUEST_DELAY_SECONDS)
        return result
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return empty


def fetch_steamspy_tags(app_id: int | str, use_cache: bool = True) -> list[str]:
    """Return tag names from SteamSpy appdetails (uses fetch_steamspy_appdetails)."""
    return fetch_steamspy_appdetails(app_id, use_cache=use_cache).get("tags") or []


def clear_steamspy_cache() -> None:
    """Remove SteamSpy cache file from disk and in-memory cache."""
    global _memory
    _memory = None
    if os.path.isfile(STEAMSPY_CACHE_PATH):
        os.remove(STEAMSPY_CACHE_PATH)
