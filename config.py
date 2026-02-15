"""Currency and default configuration for the Reddit table tool."""

import os

# Currency code -> display label for table header
CURRENCY_LABELS = {
    "USD": "US ($)",
    "GBP": "UK (£)",
    "EUR": "EUR (€)",
    "CAD": "CA ($C)",
    "AUD": "AU ($)",
    "NZD": "NZ ($)",
    "PLN": "PL (zł)",
    "BRL": "BR (R$)",
    "INR": "IN (₹)",
    "IDR": "ID (Rp)",
    "CNY": "CN (¥)",
}

# All supported currency codes (order used when no selection is specified)
ALL_CURRENCIES = list(CURRENCY_LABELS.keys())

# Default currencies to show (US, EUR, CA, UK as in screenshot)
DEFAULT_CURRENCIES = ["USD", "EUR", "CAD", "GBP"]

# Feed URL
FEED_URL = "https://api.playsum.live/v1/shop/products/rss"

# Coupon discount (10% off)
COUPON_MULTIPLIER = 0.9

# --- Steam (Deal Finder tab) ---
# Optional Steam Web API key (get free at https://steamcommunity.com/dev/apikey). If empty, name resolution via GetAppList is skipped.
# Load from config_local.py (gitignored) so the key is never committed.
try:
    from config_local import STEAM_WEB_API_KEY
except ImportError:
    STEAM_WEB_API_KEY = ""

# Steam store appreviews (no key required); use {app_id} placeholder
STEAM_APPREVIEWS_URL_TEMPLATE = "https://store.steampowered.com/appreviews/{app_id}?json=1"

# Steam store appdetails (no key required); use {app_id} placeholder (for release_date etc.)
STEAM_APPDETAILS_URL_TEMPLATE = "https://store.steampowered.com/api/appdetails?appids={app_id}&l=english"

# GetAppList (requires key); IStoreService on public API (api.steampowered.com works with community key)
STEAM_APP_LIST_URL = "https://api.steampowered.com/IStoreService/GetAppList/v1/"
STEAM_APP_LIST_PAGE_SIZE = 50000  # max per request

# Cache paths (relative to config file directory)
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
STEAM_CACHE_PATH = os.path.join(_APP_DIR, "cache", "steam_reviews.json")
STEAM_CACHE_TTL_HOURS = 24
STEAM_APP_LIST_CACHE_PATH = os.path.join(_APP_DIR, "cache", "steam_app_list.json")
STEAM_APP_LIST_TTL_HOURS = 48
STEAM_APPDETAILS_CACHE_PATH = os.path.join(_APP_DIR, "cache", "steam_appdetails.json")
STEAM_APPDETAILS_CACHE_TTL_HOURS = 168  # 7 days (release date rarely changes)

# Optional feed element name for Steam App ID (e.g. "steamAppId"). Empty = not used.
FEED_STEAM_APP_ID_TAG = ""

# Optional mapping file: product URL or product UUID -> Steam App ID. Missing file = no mapping.
STEAM_MAPPING_PATH = os.path.join(_APP_DIR, "steam_app_ids.json")

# Steam review score labels -> minimum percent positive (for filter dropdown)
STEAM_LABEL_MIN_PERCENT = {
    "Overwhelmingly Positive": 95,
    "Very Positive": 80,
    "Positive": 70,
    "Mostly Positive": 70,
}
STEAM_LABEL_ORDER = ["Overwhelmingly Positive", "Very Positive", "Positive", "Mostly Positive"]
