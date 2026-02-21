"""Fetch and cache Steam app list (GetAppList); resolve product title to Steam app_id by name."""

import json
import os
import re
import time
from datetime import datetime, timedelta

import requests

from config import (
    STEAM_APP_LIST_CACHE_PATH,
    STEAM_APP_LIST_PAGE_SIZE,
    STEAM_APP_LIST_TTL_HOURS,
    STEAM_APP_LIST_URL,
    STEAM_NAME_RESOLUTION_CACHE_PATH,
    STEAM_WEB_API_KEY,
)


def _load_app_list_cache() -> tuple[list[dict], str | None]:
    """Load app list from disk cache. Returns (list of {appid, name}, fetched_at or None)."""
    if not os.path.isfile(STEAM_APP_LIST_CACHE_PATH):
        return [], None
    try:
        with open(STEAM_APP_LIST_CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        apps = data.get("apps", [])
        fetched_at = data.get("fetched_at")
        return apps, fetched_at
    except (json.JSONDecodeError, OSError):
        return [], None


def _save_app_list_cache(apps: list[dict]) -> None:
    """Write app list to disk cache."""
    dirpath = os.path.dirname(STEAM_APP_LIST_CACHE_PATH)
    if dirpath and not os.path.isdir(dirpath):
        os.makedirs(dirpath, exist_ok=True)
    data = {
        "apps": apps,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    }
    with open(STEAM_APP_LIST_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=0)


def _is_cache_expired(fetched_at: str | None) -> bool:
    if not fetched_at:
        return True
    try:
        dt = datetime.fromisoformat(fetched_at.replace("Z", ""))
    except (ValueError, TypeError):
        return True
    return (datetime.utcnow() - dt) > timedelta(hours=STEAM_APP_LIST_TTL_HOURS)


def _parse_app_list_response(body: dict) -> list[dict]:
    """Extract list of {appid, name} from IStoreService/GetAppList response. Handles common shapes."""
    raw = []
    response = body.get("response")
    if isinstance(response, dict):
        raw = response.get("apps", response.get("app_list", []))
    if not raw and isinstance(body.get("applist"), dict):
        raw = body["applist"].get("apps", [])
    if not raw:
        raw = body.get("apps", [])
    result = []
    for a in raw:
        if not isinstance(a, dict):
            continue
        appid = a.get("appid") or a.get("steam_appid")
        if appid is None:
            continue
        name = (a.get("name") or a.get("app_name") or a.get("title") or "").strip()
        result.append({"appid": int(appid), "name": name})
    return result


def get_app_list(force_refresh: bool = False) -> list[dict]:
    """
    Return list of {appid, name} from cache or Steam API (IStoreService/GetAppList).
    Only calls API if STEAM_WEB_API_KEY is set and (cache miss or expired or force_refresh).
    Uses pagination (last_appid, max_results) to fetch the full list.
    """
    apps, fetched_at = _load_app_list_cache()
    if not force_refresh and apps and not _is_cache_expired(fetched_at):
        return apps
    if not STEAM_WEB_API_KEY or not STEAM_WEB_API_KEY.strip():
        return apps  # Return stale cache if any, else []
    key = STEAM_WEB_API_KEY.strip()
    all_apps = []
    last_appid = None
    try:
        while True:
            params = {"key": key, "max_results": STEAM_APP_LIST_PAGE_SIZE}
            if last_appid is not None:
                params["last_appid"] = last_appid
            resp = requests.get(
                STEAM_APP_LIST_URL,
                params=params,
                timeout=120,
            )
            resp.raise_for_status()
            body = resp.json()
            batch = _parse_app_list_response(body)
            if not batch:
                break
            all_apps.extend(batch)
            if len(batch) < STEAM_APP_LIST_PAGE_SIZE:
                break
            last_appid = batch[-1]["appid"]
        if all_apps:
            _save_app_list_cache(all_apps)
            return all_apps
        return apps  # Keep existing cache on empty response
    except (requests.RequestException, json.JSONDecodeError, KeyError, TypeError):
        return apps  # Return existing cache on error


# In-memory cache so we only read/parse the resolution cache once per process.
_memory_resolution: dict[str, int] | None = None


def _load_resolution_cache() -> dict[str, int]:
    """Load name->appid resolution cache from disk (or return in-memory copy). Returns dict normalized_title -> app_id."""
    global _memory_resolution
    if _memory_resolution is not None:
        return _memory_resolution
    if not os.path.isfile(STEAM_NAME_RESOLUTION_CACHE_PATH):
        _memory_resolution = {}
        return _memory_resolution
    try:
        with open(STEAM_NAME_RESOLUTION_CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            _memory_resolution = {}
            return _memory_resolution
        _memory_resolution = {k: int(v) for k, v in data.items() if v is not None and isinstance(v, (int, str)) and str(v).isdigit()}
        return _memory_resolution
    except (json.JSONDecodeError, OSError, ValueError):
        _memory_resolution = {}
        return _memory_resolution


def _save_resolution_cache(cache: dict[str, int]) -> None:
    """Write name->appid resolution cache to disk and update in-memory cache."""
    global _memory_resolution
    dirpath = os.path.dirname(STEAM_NAME_RESOLUTION_CACHE_PATH)
    if dirpath and not os.path.isdir(dirpath):
        os.makedirs(dirpath, exist_ok=True)
    with open(STEAM_NAME_RESOLUTION_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=0)
    _memory_resolution = cache


# Substring matches require the shorter string to be at least this fraction of the longer (by length).
# Avoids false matches like "io" in "evolution" or "access" in "early access".
_RESOLVE_SUBSTRING_MAJORITY = 0.5

# Normalized suffixes (with leading space) for base-game fallback. Strip from end of norm_title
# so e.g. "ARC Raiders - Deluxe Edition" -> "arc raiders" and resolve to base game's app_id.
_EDITION_SUFFIXES = (
    " deluxe edition",
    " standard edition",
    " ultimate edition",
    " enhanced edition",
    " complete edition",
    " gold edition",
    " definitive edition",
    " collector's edition",
    " collectors edition",
)
_MIN_BASE_TITLE_LEN = 2


def _normalize_title(title: str) -> str:
    """Normalize for matching: lowercase, collapse spaces, remove some punctuation."""
    if not title:
        return ""
    s = title.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[-:–—]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def resolve_name_to_app_id(title: str, app_list: list[dict] | None = None) -> int | None:
    """
    Resolve product title to a Steam app_id using the app list.
    Tries exact match (normalized), then case-insensitive, then substring (title in name or name in title,
    with majority length check). If no match, strips edition suffixes (e.g. " - Deluxe Edition") and
    retries so bundles without their own app can use the base game's app_id.
    """
    if not title or not title.strip():
        return None
    if app_list is None:
        app_list = get_app_list()
    if not app_list:
        return None
    norm_title = _normalize_title(title)
    if not norm_title:
        return None
    # Build lookup: normalized name -> list of (appid, original name)
    by_norm: dict[str, list[tuple[int, str]]] = {}
    for a in app_list:
        name = (a.get("name") or "").strip()
        appid = a.get("appid")
        if name and appid is not None:
            n = _normalize_title(name)
            if n not in by_norm:
                by_norm[n] = []
            by_norm[n].append((appid, name))
    # 1) Exact match (normalized)
    if norm_title in by_norm:
        return by_norm[norm_title][0][0]
    # 2) Case-insensitive: norm_title equals some normalized name
    for n, candidates in by_norm.items():
        if n == norm_title:
            return candidates[0][0]
    # 3) Substring: product title contained in Steam name or vice versa, only if majority of titles match
    for n, candidates in by_norm.items():
        if norm_title in n or n in norm_title:
            shorter = min(len(n), len(norm_title))
            longer = max(len(n), len(norm_title))
            if longer > 0 and (shorter / longer) >= _RESOLVE_SUBSTRING_MAJORITY:
                return candidates[0][0]
    # 4) Base-game fallback: strip edition suffixes and try again (for bundles without their own app)
    base_titles = set()
    for suffix in _EDITION_SUFFIXES:
        if norm_title.endswith(suffix):
            base = norm_title[: -len(suffix)].strip()
            if len(base) >= _MIN_BASE_TITLE_LEN:
                base_titles.add(base)
    for base in base_titles:
        if base in by_norm:
            return by_norm[base][0][0]
        for n, candidates in by_norm.items():
            if base in n or n in base:
                shorter = min(len(n), len(base))
                longer = max(len(n), len(base))
                if longer > 0 and (shorter / longer) >= _RESOLVE_SUBSTRING_MAJORITY:
                    return candidates[0][0]
    return None


def resolve_name_to_app_id_cached(title: str, app_list: list[dict] | None = None) -> int | None:
    """
    Resolve product title to Steam app_id using the app list, with disk cache.
    Checks the name-resolution cache first; on miss, calls resolve_name_to_app_id and saves the result.
    """
    norm = _normalize_title(title)
    if not norm:
        return None
    cache = _load_resolution_cache()
    if norm in cache:
        return cache[norm]
    app_id = resolve_name_to_app_id(title, app_list)
    if app_id is not None:
        cache[norm] = app_id
        _save_resolution_cache(cache)
    return app_id


def clear_app_list_cache() -> None:
    """Remove cached app list from disk."""
    if os.path.isfile(STEAM_APP_LIST_CACHE_PATH):
        os.remove(STEAM_APP_LIST_CACHE_PATH)


def clear_name_resolution_cache() -> None:
    """Remove name->appid resolution cache from disk and in-memory cache."""
    global _memory_resolution
    _memory_resolution = None
    if os.path.isfile(STEAM_NAME_RESOLUTION_CACHE_PATH):
        os.remove(STEAM_NAME_RESOLUTION_CACHE_PATH)
