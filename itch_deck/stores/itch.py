"""itch.io API: owned keys (with pagination and the list/object quirk) + games in the user's
collections (free / no-price games never get a download key, so they only show up there)."""
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
    """owned-keys games list platforms in "traits" (["p_linux", ...]); older shapes use booleans."""
    tr = set(g.get("traits") or [])
    p = set()
    for key, name in (("p_linux", "linux"), ("p_windows", "windows"), ("p_osx", "mac"),
                      ("p_android", "android")):
        if g.get(key) or key in tr:
            p.add(name)
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


def _listish(data, field):
    """data[field] as a list (itch sends {} or an object instead of [] in places)."""
    v = data.get(field) if isinstance(data, dict) else None
    if isinstance(v, dict):
        v = list(v.values())
    return [x for x in (v or []) if isinstance(x, dict)]


def parse_collections(data):
    return [c for c in _listish(data, "collections") if "id" in c]


def parse_collection_games(data):
    """/collections/{id}/collection-games -> game dicts ({"game": {...}} rows, or bare games
    from the older /games shape)."""
    rows = _listish(data, "collection_games") or _listish(data, "games")
    return [r["game"] if isinstance(r.get("game"), dict) else r for r in rows
            if isinstance(r.get("game"), dict) or "id" in r]


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


def parse_uploads(data):
    """/games/{id}/uploads -> list of upload dicts (same list/object quirk as owned_keys)."""
    ups = data.get("uploads") if isinstance(data, dict) else None
    if isinstance(ups, dict):
        ups = list(ups.values())
    out = []
    for u in ups or []:
        if not isinstance(u, dict) or "id" not in u:
            continue
        tr = set(u.get("traits") or [])
        out.append({
            "id": u["id"], "filename": u.get("filename") or u.get("display_name") or f"upload-{u['id']}",
            "name": u.get("display_name") or u.get("filename") or "",
            "size": int(u.get("size") or 0), "type": u.get("type") or "default",
            "storage": u.get("storage") or "hosted",
            "demo": bool(u.get("demo")) or "demo" in tr,
            "linux": bool(u.get("p_linux")) or "p_linux" in tr,
            "windows": bool(u.get("p_windows")) or "p_windows" in tr,
            "updated": u.get("updated_at") or u.get("created_at") or "",
        })
    return out


_BAD_ARCH = ("arm", "aarch64", "i386", "i686", "x86_32", "32bit", "32-bit", "linux32")


def pick_build(uploads, platform="linux"):
    """Pitfall #3 rules: skip soundtracks/books/other-OS/external links, prefer full game over
    demo, 64-bit over 32-bit/ARM, then the newest. Returns (best, other candidates)."""
    c = [u for u in uploads if u[platform] and u["type"] == "default" and u["storage"] != "external"]
    if not c:
        return None, []

    def score(u):
        n = u["filename"].lower()
        return (not u["demo"], not any(b in n for b in _BAD_ARCH), u["updated"], u["size"])
    c.sort(key=score, reverse=True)
    return c[0], c[1:]


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
        try:
            self._collections(games, seen)
        except (net.AuthError, net.Offline) as e:          # owned games still count
            log.warning("itch sync: collections skipped (%s)", e)
        except Exception:  # noqa: BLE001
            log.exception("itch sync: collections failed")
        return games

    def _collections(self, games, seen):
        """Free games from the user's collections, added after owned ones (owned wins: it has a
        key). Paid games you don't own are left out, since they can't be downloaded."""
        cols = parse_collections(net.get_json(f"{API}/profile/collections", self.key))
        added = paid = 0
        for c in cols:
            for page in range(1, MAX_PAGES + 1):
                rows = parse_collection_games(net.get_json(
                    f"{API}/collections/{c['id']}/collection-games?page={page}", self.key))
                if not rows:
                    break
                for g in rows:
                    gid = str(g.get("id"))
                    if gid in seen or not g.get("id"):
                        continue
                    if (g.get("min_price") or 0) > 0:
                        paid += 1
                        continue
                    seen.add(gid)
                    games.append(dict(game_from_key({"game": g}), source="collection"))
                    added += 1
        log.info("itch sync: collections %s -> %d free games added, %d paid skipped",
                 [c.get("title") for c in cols], added, paid)

    def list_builds(self, game):
        q = f"?download_key_id={game['download_key_id']}" if game.get("download_key_id") else ""
        ups = parse_uploads(net.get_json(f"{API}/games/{game['id']}/uploads{q}", self.key))
        log.info("uploads %s: %s", game["id"], [(u["id"], u["filename"], u["type"],
                                                "L" if u["linux"] else "", "W" if u["windows"] else "")
                                               for u in ups])
        return ups

    def download_url(self, game, build):
        """itch redirects this to the file on its CDN (same URL butler uses). The key goes in an
        unredirected header so the CDN never sees it."""
        q = f"?download_key_id={game['download_key_id']}" if game.get("download_key_id") else ""
        return f"{API}/uploads/{build['id']}/download{q}"
