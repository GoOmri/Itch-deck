"""Library: cached game list + background sync, covers and itch-page details.
Threads only touch files and plain dict fields; all pygame drawing stays on the main thread."""
import datetime as dt
import itertools
import json
import logging
import os
import queue
import threading
import time
from pathlib import Path

from . import config, hltb, net, paths
from .stores import itch_page

log = logging.getLogger("scritch")
PAGE_MAX_AGE = dt.timedelta(days=7)
HLTB_MAX_AGE = dt.timedelta(days=30)   # time to beat (and "not on HLTB") rechecked monthly
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
    tmp = paths.tmp_for(path)    # own name per thread/process: a shared hltb.tmp raced
    tmp.write_text(json.dumps(data, ensure_ascii=False))
    tmp.replace(path)


COVER_MAX = 720          # px, longest side of a saved cover (Epic sends 2560 px art)


def _genre(g, page):
    """Genre from a saved page. Epic pages saved by v0.7.9 kept Steam's first label as is
    ("Indie", "RPG"): cleaned here until the page is fetched again."""
    genre = (page.get("genre") or [""])[0]
    if g.get("store") == "epic" and "steam_genres" not in page:
        from .stores.steam import pick_genre
        genre = pick_genre([genre])
    return genre


def _size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def shrink_cover(f):
    """Save big cover art smaller (in a worker thread), so the library never decodes a 2560 px
    image while scrolling. Returns the file to use (<id>.small.jpg when it was shrunk)."""
    try:
        import pygame as pg
        raw = pg.image.load(str(f))
        w, h = raw.get_size()
        if max(w, h) <= COVER_MAX:
            return f
        img = pg.Surface((w, h), 0, 32)
        img.blit(raw, (0, 0))
        k = COVER_MAX / max(w, h)
        small = pg.transform.smoothscale(img, (max(1, round(w * k)), max(1, round(h * k))))
        out = f.with_name(f"{f.name.split('.')[0]}.small.jpg")
        pg.image.save(small, str(out))
        if out != f:
            f.unlink(missing_ok=True)
        log.info("cover %s: %dx%d -> %dx%d", out.name, w, h, *small.get_size())
        return out
    except Exception as e:  # noqa: BLE001  - keep the original
        log.info("cover %s: not shrunk (%s)", f.name, e)
        return f


class Library:
    def __init__(self, store=None):
        self.store = store
        self.epic = None               # EpicStore when connected (opt-in, read-only for now)
        self.epic_error, self.epic_syncing = None, False
        self.on_epic_sync = None       # Installer: compare installed Epic builds with Epic's
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
        self.installs, self.live = {}, {}   # set by Installer: install index, in-progress fields
        self.jobs = {"cover": [0, 0], "page": [0, 0], "hltb": [0, 0]}   # [done, total] (top bar)
        self._hltb, self._hltb_client, self._hltb_down = self._load_hltb(), None, False
        self.load_cache()

    # --- cache ------------------------------------------------------------------
    def load_cache(self):
        try:
            data = json.loads(paths.LIBRARY.read_text())
            seen, self.games = set(), []
            for g in data.get("games", []):     # v0.7.6 saved each itch game again per refresh
                if g.get("id") not in seen:
                    seen.add(g.get("id"))
                    self.games.append(self._prep(g))
            self.synced_at = data.get("synced_at")
            log.info("cache: %d games, synced %s", len(self.games), self.synced_at)
        except FileNotFoundError:
            pass
        except Exception as e:  # noqa: BLE001
            log.warning("library cache unreadable: %s", e)

    def mark_played(self, g):
        """Remember when a game was started (Recent tab). Kept in its own small file."""
        import time
        g["played"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        d = self._played()                     # same dict _prep reads: survives a sync
        d[g["id"]] = g["played"]
        try:
            paths.PLAYED.parent.mkdir(parents=True, exist_ok=True)
            paths.PLAYED.write_text(json.dumps(d))
        except (OSError, ValueError) as e:
            log.warning("played.json: %s", e)

    def _played(self):
        if not hasattr(self, "_played_cache"):
            try:
                self._played_cache = json.loads(paths.PLAYED.read_text())
            except (OSError, ValueError):
                self._played_cache = {}
        return self._played_cache

    def _prep(self, g):
        g = dict(g)
        if self._played().get(g["id"]):
            g["played"] = self._played()[g["id"]]
        g["platforms"] = set(g.get("platforms") or ["other"])
        g["store"] = g.get("store") or "itch"    # v0.7.6 cached itch games as store: null
        g.setdefault("size_mb", 0)
        g.setdefault("state", None)
        g.setdefault("screens", 0)
        for f in paths.COVERS.glob(f"{g['id']}.*") if paths.COVERS.exists() else []:
            g["cover_file"] = str(f)
            break
        self._apply_install(g)
        g["ttb"] = self._ttb(g["id"])
        self._page_filters(g)
        return g

    def _page_filters(self, g):
        """Genre + inputs from the saved page, at start and after every sync: the filters need
        them for every game, not just the ones whose page was opened."""
        try:
            d = json.loads(self._page_file(g).read_text())
        except (OSError, ValueError):
            return
        g["genre"] = _genre(g, d)
        g["inputs"] = d.get("inputs") or []

    def _apply_install(self, g):
        inst = self.installs.get(g["id"])
        g["update"] = (inst or {}).get("update")      # newer build on itch (Installer.check_updates)
        if inst and Path(inst["dir"]).exists():
            g["state"], g["size_mb"] = "installed", inst.get("size", 0) // 1_000_000
            g.pop("missing", None)
        elif inst:                     # still installed, but its folder can't be reached
            g["state"] = "missing"
            g["missing"] = "card" if config.card_missing(inst["dir"]) else "files"
        elif g.get("state") in ("installed", "missing"):
            g["state"] = None
        g.update(self.live.get(g["id"], {}))

    def apply_installs(self):
        for g in self.games:
            self._apply_install(g)

    def save_cache(self):
        keep = ("id", "title", "author", "cover_url", "url", "short_text", "platforms",
                "download_key_id", "classification", "source", "store", "app_name", "long_text")
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
                for k in ("size_mb", "description", "comments", "comment_count",
                          "screens", "shot_files", "details_at"):
                    if k in old.get(g["id"], {}):
                        g[k] = old[g["id"]][k]
                self._apply_install(g)          # after the copy: install state wins
                new.append(g)
            new += [g for g in self.games if g.get("store", "itch") != "itch"]   # Epic stays
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
            self.queue_hltb()

    # --- background jobs (covers first, then page details) -----------------------
    def _put(self, prio, kind, gid):
        if (kind, gid) in self._queued:
            return
        self._queued.add((kind, gid))
        self.jobs[kind][1] += 1
        self._q.put((prio, next(self._seq), kind, gid))
        if not self._worker or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._work, daemon=True, name="jobs")
            self._worker.start()

    def queue_covers(self):
        for g in self.games:
            if not g.get("cover_file") and g.get("cover_url"):
                self._put(1, "cover", g["id"])
        big = [g for g in self.games if g.get("cover_file") and _size(g["cover_file"]) > 400_000]
        if big and not getattr(self, "_shrinking", False):       # covers saved before v0.7.8
            self._shrinking = True

            def run():
                for g in big:
                    g["cover_file"] = str(shrink_cover(Path(g["cover_file"])))
                self._shrinking = False
            threading.Thread(target=run, daemon=True, name="shrink").start()

    # --- Epic (read-only, step 1) --------------------------------------------------
    def start_epic_sync(self):
        """Refresh the Epic games in the background (legendary list: a few seconds online)."""
        if not self.epic or self.epic_syncing:
            return False
        self.epic_syncing = True
        threading.Thread(target=self.sync_epic, daemon=True, name="epic").start()
        return True

    def sync_epic(self):
        """Replace the Epic games with Epic's current list. Any failure is logged and keeps the
        Epic games we had (and never touches itch's)."""
        try:
            if not self.epic:
                return False
            raw = self.epic.sync()
        except Exception as e:  # noqa: BLE001  - isolated: never breaks itch
            log.warning("epic sync failed: %s", e)
            self.epic_error = str(e)
            return False
        finally:
            self.epic_syncing = False
        self.epic_error = None
        fresh = [self._prep(g) for g in raw]
        self.games = sorted([g for g in self.games if g.get("store", "itch") != "epic"] + fresh,
                            key=lambda g: g["title"].lower())
        self.save_cache()
        self.queue_covers()
        self.queue_hltb()
        if self.on_epic_sync:
            try:
                self.on_epic_sync()
            except Exception:  # noqa: BLE001
                log.exception("epic update check failed")
        return True

    def drop_epic(self):
        self.epic = None
        self.games = [g for g in self.games if g.get("store", "itch") != "epic"]
        self.save_cache()

    def queue_prefetch(self):
        """Background page fetch: games never fetched, and caches from before Genre /
        Average session were read (so filters fill in without opening every game)."""
        for g in self.games:
            if self._has_details(g) and g["platforms"] & {"linux", "windows"} \
                    and not self._has_page_fields(g):
                self._put(5, "page", g["id"])

    @staticmethod
    def _has_details(g):
        """itch games: their itch page. Epic games: Epic's text + Steam (screenshots, genre)."""
        return bool(g.get("url")) or g.get("store") == "epic"

    def _has_page_fields(self, g):
        try:
            d = json.loads(self._page_file(g).read_text())
        except (OSError, ValueError):
            return False
        if g.get("store") == "epic" and "steam_genres" not in d:   # v0.7.9: first Steam label
            return False                                           # (often "Indie"): refetch once
        return "genre" in d

    def _work(self):
        while True:
            try:
                prio, _, kind, gid = self._q.get(timeout=2)
            except queue.Empty:
                return
            self._queued.discard((kind, gid))
            g = self.by_id(gid)
            if not g or (self.offline and prio > 0):
                self._job_done(kind)
                continue
            if kind == "page":
                g["details_loading"] = True
            try:
                if kind == "cover":
                    self._fetch_cover(g)
                elif kind == "hltb":
                    self._fetch_hltb(g)
                else:
                    self._fetch_page(g)
            except net.Offline as e:
                log.info("%s %s: offline (%s)", kind, gid, e)
                if kind == "hltb":
                    self._hltb_down = True      # HLTB down or changed: skip the rest this run
            except net.NotFound:
                log.info("%s %s: gone on itch.io (404)", kind, gid)
                if kind == "page":
                    _write_json(self._page_file(g), {"fetched": _now().isoformat(timespec="seconds"),
                                                     "missing": True})
                    g.pop("details_at", None)
                    self._apply_page(g)
            except Exception:  # noqa: BLE001
                log.exception("%s %s failed", kind, gid)
            finally:
                g.pop("details_loading", None) if kind == "page" else None
                self._job_done(kind)
            if prio >= 5 and not (kind == "hltb" and self._hltb_down):
                time.sleep(1.5)   # background prefetch: go easy on itch.io

    def _job_done(self, kind):
        j = self.jobs[kind]
        j[0] += 1
        if j[0] >= j[1]:            # batch finished: hide the indicator
            j[0] = j[1] = 0

    def activity(self):
        """Short top-bar text for background work, or None when idle."""
        if self.syncing == "bg":
            return "Refreshing library"
        done, total = self.jobs["cover"]
        if total > 1:
            return f"Covers {done}/{total}"
        done, total = self.jobs["page"]
        if total > 1:
            return f"Game details {done}/{total}"
        return None

    def _fetch_cover(self, g):
        url = g["cover_url"]
        ext = Path(url.split("?")[0]).suffix.lower() or ".png"
        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            ext = ".png"
        f = paths.COVERS / f"{g['id']}{ext}"
        paths.COVERS.mkdir(parents=True, exist_ok=True)
        f.write_bytes(net.get(url, timeout=20))
        g["cover_file"] = str(shrink_cover(f))

    # --- time to beat (HowLongToBeat) ---------------------------------------------
    def _load_hltb(self):
        try:
            return json.loads(paths.HLTB.read_text())
        except (OSError, ValueError):
            return {}

    def _ttb(self, gid):
        """{"main": h, "done": h} for the UI, or None (not looked up yet / not on HLTB)."""
        e = self._hltb.get(gid) or {}
        return {"main": e["main"], "done": e.get("done")} if e.get("main") or e.get("done") else None

    def _hltb_fresh(self, gid):
        try:
            return _now() - dt.datetime.fromisoformat(self._hltb[gid]["at"]) < HLTB_MAX_AGE
        except (KeyError, TypeError, ValueError):
            return False

    def queue_hltb(self):
        """Look up games HLTB hasn't been asked about this month (lowest priority, after pages)."""
        if self._hltb_down:
            return
        for g in self.games:
            if g.get("title") and g["platforms"] & {"linux", "windows"} and not self._hltb_fresh(g["id"]):
                self._put(7, "hltb", g["id"])

    def _fetch_hltb(self, g):
        if self._hltb_down:
            return
        self._hltb_client = self._hltb_client or hltb.Client()
        t = self._hltb_client.lookup(g["title"]) or {}
        self._hltb[g["id"]] = {"at": _now().isoformat(timespec="seconds"), **t}
        _write_json(paths.HLTB, self._hltb)
        g["ttb"] = self._ttb(g["id"])
        log.info("hltb %s: %s", g["id"], hltb.summary(g["ttb"]) or "not found")

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
        if stale and self._has_details(g) and not self.offline:
            self._put(0, "page", g["id"])

    def _apply_page(self, g):
        try:
            d = json.loads(self._page_file(g).read_text())
        except (OSError, ValueError):
            return
        g["page_missing"] = bool(d.get("missing"))
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
        g["inputs"] = d.get("inputs") or []
        g["genre"] = _genre(g, d)
        g["details_from"] = d.get("source") or "itch"
        # pages cached before Genre/Average session were read: stale, so they refetch once
        g["details_at"] = d.get("fetched") if "inputs" in d and "genre" in d else None

    def _fetch_page(self, g):
        if g.get("store") == "epic":
            return self._fetch_epic_page(g)
        if not g.get("url"):
            return
        html = net.get(g["url"], timeout=25).decode("utf-8", "replace")
        p = itch_page.parse(html)
        if not p["description"]:
            log.warning("page %s: no description found (itch markup changed?)", g["id"])
        if p["saw_comments_markup"] and not p["comments"]:
            log.warning("page %s: comments markup present but none parsed", g["id"])
            dbg = paths.LOGS / "pages"            # keep a few samples to fix the parser
            dbg.mkdir(parents=True, exist_ok=True)
            if len(list(dbg.glob("*.html"))) < 5:
                (dbg / f"{g['id']}.html").write_text(html)
        n = self._save_shots(g, p["shots"][:MAX_SHOTS])
        _write_json(self._page_file(g), {
            "fetched": _now().isoformat(timespec="seconds"), "description": p["description"],
            "comments": p["comments"], "comment_count": p["comment_count"], "shots": n,
            "inputs": p["inputs"], "genre": p["genre"]})
        log.info("page %s: %d paras, %d shots, %d comments", g["id"], len(p["description"]), n,
                 len(p["comments"]))
        g.pop("details_at", None)
        self._apply_page(g)

    def _fetch_epic_page(self, g):
        """Epic game page: Epic's own long description; from Steam (same title only) the
        screenshots and genre, and the text when Epic has none. Saved like an itch page."""
        from .stores import steam
        paras = steam.html_paras(g.get("long_text"))
        src, info = ("Epic" if paras else None), None
        try:
            appid = steam.find(g["title"])
            info = steam.details(appid) if appid else None
        except net.Offline:
            raise
        except Exception as e:  # noqa: BLE001  - Steam is a bonus: never fail the page
            log.info("page %s: steam lookup failed: %s", g["id"], e)
        if info and not paras and info["paras"]:
            paras, src = info["paras"], "Steam"
        n = self._save_shots(g, (info or {}).get("shots", [])[:MAX_SHOTS])
        genre = (info or {}).get("genre")
        _write_json(self._page_file(g), {
            "fetched": _now().isoformat(timespec="seconds"), "description": paras,
            "comments": [], "comment_count": 0, "shots": n, "inputs": [],
            "genre": [genre] if genre else [], "steam_genres": (info or {}).get("genres", []),
            "source": src,
            "shots_from": "Steam" if n else None})
        log.info("page %s: epic, text from %s, %d shots, steam %s", g["id"], src,
                 n, "matched" if info else "no match")
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
