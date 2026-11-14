"""itch.io API: owned keys (with pagination and the list/object quirk)."""
import logging

from .. import net
from .base import Store

log = logging.getLogger("itch-deck")
API = "https://api.itch.io"
MAX_PAGES = 200  # safety stop


def parse_owned_keys(data):
    """owned_keys comes back as a list, or as {} / an object when empty or oddly encoded."""
    ok = data.get("owned_keys") if isinstance(data, dict) else None
    if isinstance(ok, dict):
        ok = list(ok.values())
    return [k for k in (ok or []) if isinstance(k, dict) and isinstance(k.get("game"), dict)]


def platforms_of(g):
    p = set()
    if g.get("p_linux"):
        p.add("linux")
    if g.get("p_windows"):
        p.add("windows")
    if g.get("p_osx"):
        p.add("mac")
    if g.get("p_android"):
        p.add("android")
    if g.get("type") == "html":
        p.add("html")
    cls = g.get("classification") or ""
    if cls == "soundtrack":
        p.add("soundtrack")
    elif cls in ("book", "comic"):
        p.add("book")
    if not p:
        p.add("other")
    return p


def game_from_key(k):
    g = k["game"]
    user = g.get("user") or {}
    return {
        "id": str(g["id"]),
        "title": (g.get("title") or "Untitled").strip(),
        "author": user.get("display_name") or user.get("username") or "",
        "cover_url": g.get("still_cover_url") or g.get("cover_url"),
        "url": g.get("url"),
        "short_text": (g.get("short_text") or "").strip(),
        "platforms": sorted(platforms_of(g)),
        "download_key_id": k.get("id"),
        "classification": g.get("classification"),
    }


class ItchStore(Store):
    name = "itch"

    def __init__(self, key):
        self.key = key

    def check_key(self):
        data = net.get_json(f"{API}/profile", self.key)
        user = data.get("user") or {}
        return user.get("username") or "?"

    def sync(self, on_page=None):
        games, seen = [], set()
        for page in range(1, MAX_PAGES + 1):
            if on_page:
                on_page(page)
            keys = parse_owned_keys(net.get_json(f"{API}/profile/owned-keys?page={page}", self.key))
            if not keys:
                break
            for k in keys:
                g = game_from_key(k)
                if g["id"] not in seen:  # bought twice / bundle + purchase -> one tile
                    seen.add(g["id"])
                    games.append(g)
        log.info("itch sync: %d games over %d page(s)", len(games), page - 1)
        return games
