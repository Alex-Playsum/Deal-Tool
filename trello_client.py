"""Trello API client for Post Builder: create cards and attach images to the Deal Alerts list."""

import requests

from config import (
    TRELLO_API_KEY,
    TRELLO_BOARD_ID,
    TRELLO_DEAL_ALERTS_LIST_NAME,
    TRELLO_TOKEN,
)

TRELLO_BASE = "https://api.trello.com/1"
SOCIAL_MEDIA_LABEL_NAME = "Social Media"


def _auth_params():
    return {"key": TRELLO_API_KEY, "token": TRELLO_TOKEN}


def _trello_desc_from_post_text(post_text: str) -> str:
    """
    Format post text for Trello description so that # is not interpreted as markdown heading
    and the URL is not unfurled into a preview (wrap in backticks).
    """
    if not (post_text or "").strip():
        return ""
    parts = (post_text or "").strip().split("\n\n")
    out = []
    for i, p in enumerate(parts):
        p = p.strip()
        if not p:
            continue
        if p.startswith("#"):
            out.append("\\" + p)
        elif p.startswith("http://") or p.startswith("https://"):
            out.append("`" + p + "`")
        else:
            out.append(p)
    return "\n\n".join(out)


def get_deal_alerts_list_id() -> str | None:
    """
    Fetch lists for the configured board and return the id of the list named "Deal Alerts".
    Returns None if not configured, board not found, or list name not found.
    """
    if not (TRELLO_API_KEY and TRELLO_TOKEN and TRELLO_BOARD_ID):
        return None
    url = f"{TRELLO_BASE}/boards/{TRELLO_BOARD_ID}/lists"
    try:
        resp = requests.get(url, params=_auth_params(), timeout=15)
        resp.raise_for_status()
        lists = resp.json()
        for lst in lists:
            if (lst.get("name") or "").strip() == TRELLO_DEAL_ALERTS_LIST_NAME:
                return lst.get("id")
        return None
    except (requests.RequestException, KeyError, TypeError):
        return None


def get_social_media_label_id() -> str | None:
    """
    Return the id of the label named 'Social Media' on the configured board.
    If the label does not exist, create it (blue). Returns None if not configured.
    """
    if not (TRELLO_API_KEY and TRELLO_TOKEN and TRELLO_BOARD_ID):
        return None
    url = f"{TRELLO_BASE}/boards/{TRELLO_BOARD_ID}/labels"
    try:
        resp = requests.get(url, params=_auth_params(), timeout=15)
        resp.raise_for_status()
        labels = resp.json()
        for lab in labels:
            if (lab.get("name") or "").strip() == SOCIAL_MEDIA_LABEL_NAME:
                return lab.get("id")
        create_url = f"{TRELLO_BASE}/labels"
        create_resp = requests.post(
            create_url,
            params={**_auth_params(), "name": SOCIAL_MEDIA_LABEL_NAME, "idBoard": TRELLO_BOARD_ID, "color": "blue"},
            timeout=15,
        )
        create_resp.raise_for_status()
        return create_resp.json().get("id")
    except (requests.RequestException, KeyError, TypeError):
        return None


def create_card(id_list: str, name: str, desc: str, id_labels: list[str] | None = None) -> dict | None:
    """Create a card on the given list. Returns the card JSON (with id) or None on failure."""
    if not (TRELLO_API_KEY and TRELLO_TOKEN):
        return None
    url = f"{TRELLO_BASE}/cards"
    params = {**_auth_params(), "idList": id_list, "name": name, "desc": desc}
    if id_labels:
        params["idLabels"] = ",".join(id_labels)
    try:
        resp = requests.post(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, KeyError, TypeError):
        return None


def add_attachment_by_url(card_id: str, image_url: str) -> bool:
    """Add an attachment to a card by URL. Returns True on success."""
    if not (TRELLO_API_KEY and TRELLO_TOKEN) or not (image_url or "").strip():
        return False
    url = f"{TRELLO_BASE}/cards/{card_id}/attachments"
    params = {**_auth_params(), "url": image_url.strip()}
    try:
        resp = requests.post(url, params=params, timeout=15)
        resp.raise_for_status()
        return True
    except requests.RequestException:
        return False


def send_posts_to_trello(posts: list[dict]) -> tuple[int, str | None]:
    """
    For each post dict (title, post_text, header_image_url, link), create a Trello card
    on the Deal Alerts list with name "Deal Alert: {title}", description = post_text,
    and attach the header image by URL.
    Returns (success_count, error_message). error_message is None unless no cards could be created.
    """
    id_list = get_deal_alerts_list_id()
    if not id_list:
        if not (TRELLO_API_KEY and TRELLO_TOKEN and TRELLO_BOARD_ID):
            return 0, "Trello not configured. Add TRELLO_API_KEY, TRELLO_TOKEN, TRELLO_BOARD_ID to config_local.py."
        return 0, f"List '{TRELLO_DEAL_ALERTS_LIST_NAME}' not found on the configured board."
    id_labels = []
    if social_id := get_social_media_label_id():
        id_labels = [social_id]
    success = 0
    last_error = None
    for post in posts:
        title = (post.get("title") or "").strip() or "Untitled"
        name = f"Deal Alert: {title}"
        raw_desc = (post.get("post_text") or "").strip()
        desc = _trello_desc_from_post_text(raw_desc)
        card = create_card(id_list, name, desc, id_labels=id_labels)
        if not card:
            last_error = f"Failed to create card for {title}"
            continue
        success += 1
        image_url = (post.get("header_image_url") or "").strip()
        if image_url:
            add_attachment_by_url(card["id"], image_url)
    if success == 0 and last_error:
        return 0, last_error
    return success, None
