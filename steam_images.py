"""Steam CDN URLs for capsule and header images (for email builder blocks)."""

# Steam CDN base; path_full from appdetails may be relative (e.g. /steam/apps/...)
STEAM_CDN_BASE = "https://cdn.cloudflare.steamstatic.com"

# Known capsule/header sizes (app_id in path)
STEAM_IMAGE_PATHS = {
    "header": "steam/apps/{app_id}/header.jpg",       # 460x215
    "capsule_sm": "steam/apps/{app_id}/capsule_231x87.jpg",
    "capsule_md": "steam/apps/{app_id}/capsule_467x181.jpg",
    "capsule_616x353": "steam/apps/{app_id}/capsule_616x353.jpg",
}


def get_steam_capsule_url(app_id: int | str, size: str = "header") -> str:
    """
    Return Steam CDN URL for the given app_id and image size.
    size: "header" (460x215), "capsule_sm" (231x87), "capsule_md" (467x181), "capsule_616x353" (616x353).
    """
    app_id = int(app_id)
    path = STEAM_IMAGE_PATHS.get(size, STEAM_IMAGE_PATHS["header"])
    rel = path.format(app_id=app_id)
    if rel.startswith("/"):
        return STEAM_CDN_BASE + rel
    return STEAM_CDN_BASE + "/" + rel
