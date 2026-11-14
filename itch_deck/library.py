"""Library: cached game list + background sync, covers and itch-page details.
Threads only touch files and plain dict fields; all pygame drawing stays on the main thread."""
import datetime as dt
import itertools
import json
import logging
import queue
import threading
from pathlib import Path

from . import net, paths
from .stores import itch_page

log = logging.getLogger("itch-deck")
PAGE_MAX_AGE = dt.timedelta(days=7)
MAX_SHOTS = 8
SHOT_W = 1280


def _now():
    return dt.datetime.now().astimezone()


def short_date(iso):
    try:
        d = dt.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return "never"
    today = _now().date()
    if d.date() == today:
        return f"today {d:%H:%M}"
    return f"{d.day} {d:%b}"


def ago(stamp):
    """'2024-03-01 12:00:00' (itch, UTC) -> '3 days ago'. Unknown formats pass through."""
    try:
        d = dt.datetime.fromisoformat(stamp.replace("Z", "")[:19]).replace(tzinfo=dt.timezone.utc)
    except (AttributeError, ValueError):
        return stamp or ""
    s = (_now() - d).total_seconds()
    for unit, n in (("year", 31536000), ("month", 2592000), ("week", 604800), ("day", 86400),
                    ("hour", 3600), ("minute", 60)):
        if s >= n:
            k = int(s // n)
            return f"{k} {unit}{'s' if k > 1 else ''} ago"
    return "just now"


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False))
    tmp.replace(path)


class Library:
    def __init__(self, store=None):
        self.store = store
        self.games, self.synced_at = [], None
        self.syncing = None            # None | "first" | "bg"
        self.page = 0
        self.offline = False
        self.auth_failed = False
        self.sync_error = None
        self._q = queue.PriorityQueue()
        self._seq = itertools.count()
        self._queued = set()
        self._worker = None
        self.load_cache()

    # --- cache ------------------------------------------------------------------
    def load_cache(self):
        try:
            data = json.loads(paths.LIBRARY.read_text())
            self.games = [self._prep(g) for g in data.get("games", [])]
            self.synced_at = data.get("synced_at")
            log.info("cache: %d games, synced %s", len(self.games), self.synced_at)
        except FileNotFoundError:
            pass
        except Exception as e:  # noqa: BLE001
            log.warning("library cache unreadable: %s", e)

    def _prep(self, g):
        g = dict(g)
        g["platforms"] = set(g.get("platforms") or ["other"])
        g.setdefault("size_mb", 0)
        g.setdefault("state", None)
        g.setdefault("screens", 0)
        for f in paths.COVERS.glob(f"{g['id']}.*") if paths.COVERS.exists() else []:
            g["cover_file"] = str(f)
            break
        return g

    def save_cache(self):
        keep = ("id", "title", "author", "cover_url", "url", "short_text", "platforms",
                "download_key_id", "classification")
        games = [{k: (sorted(g[k]) if k == "platforms" else g.get(k)) for k in keep} for g in self.games]
        _write_json(paths.LIBRARY, {"synced_at": self.synced_at, "games": games})

    @property
    def offline_since(self):
        return short_date(self.synced_at) if self.offline else None

    def by_id(self, gid):
        return next((g for g in self.games if g["id"] == gid), None)

    # --- sync -------------------------------------------------------------------
    def start_sync(self):
        if self.syncing or not self.store:
            return False
        self.syncing = "bg" if self.games else "first"
        self.page, self.sync_error = 0, None
        threading.Thread(target=self._sync, daemon=True, name="sync").start()
        return True

    def _sync(self):
        try:
            raw = self.store.sync(on_page=lambda n: setattr(self, "page", n))
            old = {g["id"]: g for g in self.games}
            new = []
            for r in raw:
                g = self._prep(r)
                for k in ("state", "size_mb", "description", "comments", "comment_count",
                          "screens", "shot_files", "details_at"):
                    if k in old.get(g["id"], {}):
                        g[k] = old[g["id"]][k]
                new.append(g)
            new.sort(key=lambda g: g["title"].lower())
            self.games = new
            self.synced_at = _now().isoformat(timespec="seconds")
            self.offline = False
            self.save_cache()
        except net.AuthError as e:
            log.warning("sync: key rejected (%s)", e)
            self.auth_failed = True
        except net.Offline as e:
            log.info("sync: offline (%s)", e)
            self.offline = True
        except Exception as e:  # noqa: BLE001
            log.exception("sync failed")
            self.sync_error = str(e)
        finally:
            self.syncing = None
        if not self.offline and not self.auth_failed:
            self.queue_covers()
            self.queue_prefetch()

    # --- background jobs (covers first, then page details) -----------------------
    def _put(self, prio, kind, gid):
        if (kind, gid) in self._queued:
            return
        self._queued.add((kind, gid))
        self._q.put((prio, next(self._seq), kind, gid))
        if not self._worker or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._work, daemon=True, name="jobs")
            self._worker.start()

    def queue_covers(self):
        for g in self.games:
            if not g.get("cover_file") and g.get("cover_url"):
                self._put(1, "cover", g["id"])

    def queue_prefetch(self):
        for g in self.games:
            if g["platforms"] & {"linux", "windows"} and not self._page_file(g).exists():
                self._put(5, "page", g["id"])

    def _work(self):
        while True:
            try:
                prio, _, kind, gid = self._q.get(timeout=2)
            except queue.Empty:
                return
            self._queued.discard((kind, gid))
            g = self.by_id(gid)
            if not g or (self.offline and prio > 0):
                continue
            try:
                if kind == "cover":
                    self._fetch_cover(g)
                else:
                    self._fetch_page(g)
            except net.Offline as e:
                log.info("%s %s: offline (%s)", kind, gid, e)
            except Exception:  # noqa: BLE001
                log.exception("%s %s failed", kind, gid)

    def _fetch_cover(self, g):
        url = g["cover_url"]
        ext = Path(url.split("?")[0]).suffix.lower() or ".png"
        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            ext = ".png"
        f = paths.COVERS / f"{g['id']}{ext}"
        paths.COVERS.mkdir(parents=True, exist_ok=True)
        f.write_bytes(net.get(url, timeout=20))
        g["cover_file"] = str(f)

    # --- itch page details ------------------------------------------------------
    def _page_file(self, g):
        return paths.PAGES / f"{g['id']}.json"

    def ensure_details(self, g):
        """Called when a game page opens: show cached details now, refresh if old."""
        if not g.get("details_at"):
            self._apply_page(g)
        stale = True
        try:
            stale = _now() - dt.datetime.fromisoformat(g["details_at"]) > PAGE_MAX_AGE
        except (KeyError, TypeError, ValueError):
            pass
        if stale and g.get("url") and not self.offline:
            self._put(0, "page", g["id"])

    def _apply_page(self, g):
        try:
            d = json.loads(self._page_file(g).read_text())
        except (OSError, ValueError):
            return
        g["description"] = d.get("description") or []
        files = [str(p) for p in sorted((paths.SHOTS / g["id"]).glob("*.jpg"),
                                        key=lambda p: int(p.stem))] if d.get("shots") else []
        g["shot_files"], g["screens"] = files, len(files)
        cs = d.get("comments") or []
        for c in cs:
            for x in [c] + c.get("reply_list", []):
                x["when"] = ago(x.get("date", ""))
        g["comments"] = cs or None            # None = section hidden (forum games, parse miss)
        g["comment_count"] = d.get("comment_count", len(cs))
        g["details_at"] = d.get("fetched")

    def _fetch_page(self, g):
        if not g.get("url"):
            return
        html = net.get(g["url"], timeout=25).decode("utf-8", "replace")
        p = itch_page.parse(html)
        if not p["description"]:
            log.warning("page %s: no description found (itch markup changed?)", g["id"])
        if p["saw_comments_markup"] and not p["comments"]:
            log.warning("page %s: comments markup present but none parsed", g["id"])
        n = self._save_shots(g, p["shots"][:MAX_SHOTS])
        _write_json(self._page_file(g), {
            "fetched": _now().isoformat(timespec="seconds"), "description": p["description"],
            "comments": p["comments"], "comment_count": p["comment_count"], "shots": n})
        log.info("page %s: %d paras, %d shots, %d comments", g["id"], len(p["description"]), n,
                 len(p["comments"]))
        g.pop("details_at", None)
        self._apply_page(g)

    def _save_shots(self, g, urls):
        import io
        import pygame as pg
        d = paths.SHOTS / g["id"]
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("*.jpg"):
            old.unlink()
        n = 0
        for u in urls:
            try:
                img = pg.image.load(io.BytesIO(net.get(u, timeout=25)), u.split("?")[0])
                w, h = img.get_size()
                rgb = pg.Surface((w, h), 0, 32)   # palette PNG/GIF -> 32-bit, no display needed
                rgb.blit(img, (0, 0))
                img = rgb
                if w > SHOT_W:
                    img = pg.transform.smoothscale(img, (SHOT_W, int(h * SHOT_W / w)))
                pg.image.save(img, str(d / f"{n}.jpg"))
                n += 1
            except net.Offline:
                raise
            except Exception as e:  # noqa: BLE001
                log.info("screenshot skipped (%s): %s", type(e).__name__, u)
        return n
