"""SCRiTCH: scene switching, key import, library sync, installs (Linux + Windows via Proton)."""
import argparse
import json
import logging
import os
import shutil
import sys
import threading
import time
import traceback
from pathlib import Path

from . import config, dos_controls, pads, paths, runner, theme, words
from .input import (Input, A, B, X, Y, UP, DOWN, LEFT, RIGHT, START, L1, R1)
from .installer import Installer, slug_of
from .library import Library
from .stores.itch import ItchStore
from .updater import Updater
from .app_common import LATER, QUIT_DLG
from .app_game import GameMixin
from .app_play import PlayMixin
from .app_settings import SettingsMixin
from .app_setup import SetupMixin
from .app_epic import EpicMixin
from .app_gog import GogMixin
from .app_logs import LogsMixin
from .app_dos import DosMixin
from .app_storage import StorageMixin

log = logging.getLogger("scritch")
VERSION = "0.9.30"


class SecretFreeFormatter(logging.Formatter):
    """Every log record (message and traceback) goes through logshare.scrub_secrets: a token or sign-in code in
    a helper's error text (legendary, gogdl) must never be written to app.log. Never raises."""

    def format(self, record):
        text = super().format(record)
        try:
            from .logshare import scrub_secrets
            return scrub_secrets(text)
        except Exception:  # noqa: BLE001 - logging must never fail
            return text


def setup_logging():
    paths.LOGS.mkdir(parents=True, exist_ok=True)
    from logging.handlers import RotatingFileHandler
    h = RotatingFileHandler(paths.LOGS / "app.log", maxBytes=1_000_000, backupCount=3)
    fmt = SecretFreeFormatter("%(asctime)s %(levelname)s %(threadName)s %(message)s")
    h.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logging.basicConfig(level=logging.INFO, handlers=[h, sh], force=True)


class App(SetupMixin, SettingsMixin, GameMixin, PlayMixin, EpicMixin, GogMixin, LogsMixin, DosMixin, StorageMixin):
    def __init__(self, windowed=False, autoplay=None):
        import pygame
        self.pg = pygame
        self.windowed = windowed
        self.autoplay = autoplay        # a game id: started by an "Add to Steam" shortcut (scritch --play ID)
        pygame.display.init()           # not pygame.init(): no audio device (no sound in SCRiTCH)
        pygame.font.init()              # and it starts faster
        pygame.joystick.init()
        self.cfg = config.load()
        self.inp = Input(pygame)
        self.open_display()
        key = self.cfg.get("api_key")
        self.lib = Library(ItchStore(key) if key else None)
        self.lib.on_unhide = self._forget_hidden           # an installed game is not hidden any more
        self.lib.set_hidden(self.cfg.get("hidden"))      # games the player hid from SCRiTCH
        if self.cfg.get("epic"):                   # opt-in: Settings -> Account -> Epic Games
            from .stores.epic import EpicStore
            self.lib.epic = EpicStore()            # cached Epic games show at once
        if self.cfg.get("gog"):                    # opt-in: Settings -> Sources -> GOG
            from .stores.gog import GogStore
            self.lib.gog = GogStore()
        self.inst = Installer(self.lib, lambda: config.install_root(self.cfg), self.cfg)
        self.inst.clean_moves([p for _, p in config.install_choices()])   # a move cut short
        self.lib.set_hidden(self.cfg.get("hidden"))      # again: now the install state is known (hidden + installed = no)
        self._pin_root()
        self.picker = None              # (gid, builds) behind an open Change build picker
        self._progs = []                # program picker rows (relative exe paths)
        self.next_mount_check = 0
        self.on_confirm = None          # what A does on the open confirm dialog (None = Quit)
        self.running = True
        self.scene, self.kind = None, None
        self.fade_from, self.fade_t0, self.fade_dir = None, 0.0, 1   # page slide (_transition)
        self.toast_until = 0
        self.filt, self.lib_focus_id = "all", None
        self.key_result = None          # (status, key, file, user) from the checking thread
        self.pending_key = None         # key waiting for Retry after "offline"
        self.phone = None               # PhoneLink while the Setup page is up (phone login)
        self.phone_text = None          # what the phone sent (set from the server thread)
        self.phone_status = ""          # what the phone page shows while it waits
        self.phone_stop_at = 0
        self.tried_mtime = None
        self.next_poll = 0
        from .ui import widgets
        widgets.LIVE = True                # animate scrolling + spinners (mockups stay still)
        self.updater = Updater(VERSION)
        self.update_told = False
        if not autoplay:                   # a Steam shortcut plays one game and leaves: no update check, art or sync
            self.updater.check(quiet=True)     # one GitHub call at launch; Settings shows the result
            from . import steam_art
            steam_art.apply_in_background()    # SCRiTCH's own Steam tile art, once (v0.9.4)
        if autoplay:
            self.go_library()
        elif key:
            self.go_library()
            self.lib.queue_covers()
            self.lib.start_sync()
            self._start_dos_scan()                 # your own DOS games (the dos folder)
            self.inst.resume()
            if self.lib.epic and self.lib.epic.ready():
                self.lib.start_epic_sync()         # background; failures stay in the log
            if self.lib.gog and self.lib.gog.ready():
                self.lib.start_gog_sync()
        else:
            self.go_setup("waiting")

    def _forget_hidden(self, gid):
        """A hidden game got installed: drop its id from the config ("hidden")."""
        self.cfg["hidden"] = [i for i in (self.cfg.get("hidden") or []) if i != gid]
        config.save(self.cfg)

    # --- display -------------------------------------------------------
    def open_display(self):
        self.fade_from = None
        pg = self.pg
        pg.display.init()
        pg.font.init()
        if self.windowed:
            self.screen = pg.display.set_mode((1280, 800))
        elif (getattr(self, "cfg", None) or {}).get("window") == "fullscreen":
            self.screen = pg.display.set_mode((0, 0), pg.FULLSCREEN)   # old way (mode switch)
        else:
            # A borderless window the size of the screen: gamescope shows it fullscreen without a
            # display mode switch (one of the start-up flickers). "window": "fullscreen" in
            # config.json goes back to the old way.
            sizes = pg.display.get_desktop_sizes()
            self.screen = pg.display.set_mode(sizes[0] if sizes else (0, 0), pg.NOFRAME)
        from .ui import widgets as W
        pg.display.set_caption(W.APP_NAME)
        pg.mouse.set_visible(False)
        self.t = theme.Theme(pg, self.screen.get_size())
        self.screen.blit(W.backdrop(self.t), (0, 0))   # first frame = our background, not black
        pg.display.flip()                               # (a logo splash only flashed: start is too quick)
        log.info("display open %s driver=%s", self.screen.get_size(), pg.display.get_driver())

    # --- navigation ----------------------------------------------------
    def say(self, msg, error=False):
        self.scene.toast, self.scene.toast_error = msg, error
        self.toast_until = time.time() + self.t.toast_s

    def _set(self, kind, scene):
        from .ui import widgets as W
        if self.scene is not None and W.LIVE:
            depth = {"setup": 0, "library": 1, "game": 2, "settings": 3, "epic": 4, "gog": 4, "logs": 4, "storage": 4}
            self.fade_dir = 1 if depth.get(kind, 0) >= depth.get(self.kind, 0) else -1  # in / back
            try:
                self.fade_from, self.fade_t0 = self.screen.copy(), time.monotonic()  # slide + fade
            except Exception:  # noqa: BLE001  - display closed (game running): no fade
                self.fade_from = None
        if kind not in ("setup", "epic", "gog", "logs") and self.phone and not self.phone_stop_at:
            self.phone_stop_at = time.time() + 10  # let the phone read "Connected", then close
        self.kind, self.scene = kind, scene
        self.toast_until = 0

    def go_setup(self, status, back=False):
        from .ui.scenes.setup import Setup
        self._phone_start()
        self._set("setup", Setup(self.t, status, back=back, qr=self.phone and self.phone.qr(),
                                 url=self.phone and self.phone.short_url))
        self.inp.set_text_mode(False)

    def go_library(self):
        from .ui.scenes.library import Library as LibScene
        sc = LibScene(self.t, self.lib.games, filt=self.filt, views=self._views(),
                      stores=self._stores())
        self._set("library", sc)
        self.filt = sc.filt              # the scene fell back to All when its tab is gone (DOS)
        self._sync_library_scene()
        ids = [g["id"] for g in sc.shown]
        if self.lib_focus_id in ids:
            sc.focus = ids.index(self.lib_focus_id)

    def go_game(self, g):
        from .ui.scenes.game import Game
        self.lib_focus_id = g["id"]
        self.lib.ensure_details(g)
        shown = self._shown()
        pos = (shown.index(g) + 1 if g in shown else 1, len(shown))
        self._set("game", Game(self.t, g, pos=pos, offline=self.lib.offline))
        if g.get("state") == "installed" and not self.lib.offline:
            self._check_updates([g["id"]], force=True)      # fresh answer for the page you open

    def _check_updates(self, gids=None, force=False):
        """Newer itch builds of installed games, in the background (Installer.check_updates)."""
        t = getattr(self, "_upd_thread", None)
        if t is not None and t.is_alive():
            return
        self._upd_thread = threading.Thread(target=self.inst.check_updates, args=(gids, force),
                                            daemon=True, name="updates")
        self._upd_thread.start()

    def go_settings(self):
        from .ui.scenes.settings import Settings
        self.settings_back = self.kind
        self._set("settings", Settings(self.t, self.settings_values(), VERSION,
                                       str(paths.LOGS / "app.log")))

    def _stores(self):
        """Connected stores: with two, the library gets a tab per store (All · Installed ·
        itch · Epic · GOG)."""
        return ("itch",) + (("epic",) if self.lib.epic else ()) + (("gog",) if self.lib.gog else ())

    def _views(self):
        """Sort & filter per library tab (cfg "library_views"). Before v0.7.5 there was one
        setting for every tab: it becomes All's, so Installed starts unfiltered."""
        c = self.cfg
        if not isinstance(c.get("library_views"), dict):
            old = {k: c.pop(f"library_{k}") for k in ("sort", "show", "genre", "length")
                   if f"library_{k}" in c}
            c["library_views"] = {"all": old} if old else {}
        from .ui.scenes.library import VIEW
        for v in c["library_views"].values():
            for k, d in VIEW.items():
                v.setdefault(k, d)
        return c["library_views"]

    def _shown(self):
        from .ui.scenes.library import VIEW, visible
        v = self._views().get(self.filt, VIEW)
        return visible(self.lib.games, self.filt, v["sort"], v["show"], v["genre"], v["length"])

    # --- per-scene input -----------------------------------------------
    def handle(self, act):
        sc = self.scene
        if sc.overlay and sc.overlay[0] == "confirm":     # buttons: [action, Cancel]
            if act in (LEFT, RIGHT):
                sc.confirm_focus = 1 - sc.confirm_focus
            elif act == A and sc.confirm_focus == 0:
                fn = self.on_confirm if sc.overlay is not QUIT_DLG else None
                sc.overlay, sc.confirm_focus = None, 0
                if fn:
                    fn()
                else:
                    self.running = False
            elif act in (A, B):                          # A on Cancel, or B
                sc.overlay, sc.confirm_focus = None, 0
            return
        getattr(self, f"_h_{self.kind}")(act)

    def _h_library(self, act):
        sc = self.scene
        if sc.overlay and sc.overlay[0] == "menu":   # X: Sort & filter
            if act in (A, LEFT, RIGHT):
                sc.menu_next(sc.overlay[3][sc.overlay[4]][0], -1 if act == LEFT else 1)
                self.cfg["library_views"] = sc.views      # this tab's Sort & filter
                config.save(self.cfg)
            elif act in (B, X):
                sc.overlay = None
            else:
                sc.handle(act)
            return
        if act == A and sc.shown:
            self.go_game(sc.shown[sc.focus])
        elif act == B and sc.filt != "all":           # other tabs: B goes back to All
            sc.filt, sc.focus, sc._first, sc._sy = "all", 0, 0, None
            self.filt = sc.filt
        elif act == B:
            sc.overlay = QUIT_DLG
        elif act == Y:
            started = self.lib.start_sync()
            self.lib.start_epic_sync()
            self.lib.start_gog_sync()
            self._start_dos_scan()
            if started:
                self.say("Refreshing library…")
        elif act == START:
            self.go_settings()
        elif act in (L1, R1):                     # tabs: All / Installed / Recent
            sc.next_tab(1 if act == R1 else -1)
            self.filt = sc.filt
        elif act in (UP, DOWN, LEFT, RIGHT, X) or act in ("L2", "R2"):
            sc.handle(act)
            self.filt = sc.filt
            if sc.shown:
                self.lib_focus_id = sc.shown[sc.focus]["id"]

    def _transition(self):
        """Page switch: the new page slides in (from the right going deeper, from the left going
        back) on the spring curve while the old frame fades out over it (theme.page_ms)."""
        from .ui import widgets as W
        t = self.t
        k = (time.monotonic() - self.fade_t0) * 1000 / t.page_ms
        if k >= 1:
            self.fade_from = None
            self.scene.draw(self.screen)
            return
        buf = getattr(self, "_page_buf", None)
        if buf is None or buf.get_size() != self.screen.get_size():
            buf = self._page_buf = self.pg.Surface(self.screen.get_size())
        self.scene.draw(buf)
        e = W.spring(k)
        off = int((1 - e) * t.u * t.page_slide_u * self.fade_dir)
        self.screen.blit(W.backdrop(t), (0, 0))
        self.screen.blit(buf, (off, 0))
        self.fade_from.set_alpha(int(255 * max(0.0, 1 - k * 1.6)))   # old page gone by ~60%
        self.screen.blit(self.fade_from, (int(-e * t.u * t.page_slide_u * 0.5 * self.fade_dir), 0))

    # --- per-frame state -----------------------------------------------
    def _sync_library_scene(self):
        sc = self.scene
        sc.games = self.lib.games
        sc.syncing, sc.sync_page = self.lib.syncing, self.lib.page
        sc.offline_since = self.lib.offline_since if self.lib.games else None
        sc.offline = self.lib.offline and not self.lib.games
        sc.activity = self._activity()
        sc.notice = self._update_notice()
        sc.focus = max(0, min(sc.focus, len(sc.shown) - 1))

    def _update_notice(self):
        u = self.updater
        return {"available": f"Update v{u.new_version} available · Settings",
                "downloading": f"Updating · {int(u.frac * 100)}%",
                "ready": f"v{u.new_version} installed · restart in Settings"}.get(u.state)

    def _free_mb(self):
        """Free space where games install, in MB (checked every few seconds, not every frame)."""
        now = time.monotonic()
        if now - getattr(self, "_free_at", -99) > 5:
            self._free_at = now
            try:
                self._free = shutil.disk_usage(config.install_root(self.cfg)).free // 1_000_000
            except OSError:
                self._free = None
        return self._free

    def _activity(self):
        """Footer-left background work (every screen): a running download first, then sync/covers/details."""
        if self.inst.moving:
            g = self.lib.by_id(self.inst.moving)
            if g:
                return f"Moving {int(g.get('progress', 0) * 100)}% · {g['title']}"
        gid = self.inst.current
        g = self.lib.by_id(gid) if gid else None
        if g and g.get("state") == "downloading":
            more = len(self.inst.queue) - 1
            pct = int(g.get('progress', 0) * 100)
            what = {"extract": "Unpacking", "umu": "Getting umu-launcher",
                    "ge": f"Getting GE-Proton {pct}%"}.get(g.get("phase"), f"Downloading {pct}%")
            return f"{what} · {g['title']}" + (f" (+{more})" if more > 0 else "")
        return self.lib.activity()

    def _pin_root(self):
        if not self.cfg.get("install_root") and config.pin_install_root(
                self.cfg, [i["dir"] for i in self.inst.index.values() if i.get("dir")]):
            config.save(self.cfg)
            log.info("install root pinned: %s", self.cfg["install_root"])

    def _check_mounts(self):
        """Installed games whose folder appeared or vanished (SD card) get their state again."""
        self._pin_root()                    # a card inserted later becomes the install location
        root = config.install_root(self.cfg)
        out = config.card_missing(root)
        if out != getattr(self, "_card_out", out):          # card taken out / put back
            log.info("install root %s: %s", root, "card out" if out else "card back")
            self.say("SD card removed." if out else "SD card is back.")
            if not out:                     # clear "SD card missing" install errors
                for g in self.lib.games:
                    if g.get("state") == "failed" and \
                            (g.get("fail_reason") or "").startswith("SD card missing"):
                        self.inst._upd(g["id"], state=None, fail_reason=None)
        self._card_out = out
        for g in self.lib.games:
            info = self.inst.index.get(g["id"])
            if info and g.get("state") in ("installed", "missing") and \
                    (g["state"] == "installed") != Path(info["dir"]).exists():
                log.info("install %s: folder %s", g["id"],
                         "back" if g["state"] == "missing" else "gone")
                self.lib.apply_installs()
                return

    def pad_kind(self):
        """Glyph set to show: Settings → Button symbols, or (Auto) the pad pressed last."""
        want = self.cfg.get("button_symbols", "auto")
        return want if want in pads.KINDS else self.inp.kind()

    def update(self):
        now = time.time()
        pads.set_current(self.pad_kind())
        if self.toast_until and now > self.toast_until:
            self.scene.toast, self.toast_until = None, 0
        if getattr(self, "backup_note", None):            # from the backup thread
            msg, err = self.backup_note
            self.backup_note = None
            self.say(msg, error=err)
        if self.key_result and self.kind == "setup":
            self._key_done()
        self._phone_tick(now)
        self._epic_tick(now)
        self._gog_tick(now)
        self._logs_tick(now)
        self._dos_tick(now)
        self._storage_tick(now)
        if self.lib.auth_failed:
            self.lib.auth_failed = False
            self.go_setup("rejected")
        if self.kind == "setup" and self.scene.status in ("waiting", "rejected") \
                and not self.scene.typing and now > self.next_poll:
            self.next_poll = now + 2
            f = paths.KEY_FILE
            if f.exists() and f.stat().st_mtime != self.tried_mtime:
                self.try_import(auto=True)     # Warpinator drop is picked up by itself
        if self.lib.store and not self.lib.syncing and not self.lib.offline and \
                now > getattr(self, "next_update_check", 0):   # newer builds (6 h per game)
            self.next_update_check = now + 1800
            self._check_updates()
        if now > self.next_mount_check:               # SD card in/out: refresh install states
            self.next_mount_check = now + 2
            self._check_mounts()
        self.scene.activity, self.scene.notice = self._activity(), self._update_notice()
        if self.kind == "library":
            self._sync_library_scene()
            if self.lib.sync_error and not self.lib.syncing:
                words.log_code("L01", f"library refresh: {self.lib.sync_error}")
                self.say(words.with_code("Couldn't refresh the library.", "L01"), error=True)
                self.lib.sync_error = None
        elif self.kind == "settings":
            self.scene.v["update"] = self.updater.row_value()
            self.scene.v["prefix_size"] = self._saves_label()
            self.scene.v["symbols"] = self._symbols_label()
            ge = self._ge_row()
            if ge:
                self.scene.v["proton"] = ge
        elif self.kind == "game":
            sc = self.scene
            sc.offline = self.lib.offline
            sc.card_out = getattr(self, "_card_out", False)
            g = self.lib.by_id(sc.g["id"])
            if g is not None and g is not sc.g:   # list replaced by a sync
                sc.g = g
            g = sc.g
            g["controls_label"] = self.controls_label(g)
            g["controls_value"] = self.controls_value(g)    # the ⚙ menu's Controls row
            g["controls_mode"] = self.controls_of(g)[1]     # what SCRiTCH maps for this game
            pl = self.controls_plan(g)                      # DOS games: the buttons in plain words (game page)
            g["dos_hints"] = pl["hints"] if pl and pl["eff"] != "gamepad" else None
            g["dos_verified"] = pl["verified"] if pl else True
            g["dos_source"] = pl["source_text"] if pl else ""
            g["controls_hint"] = dos_controls.hint_text(pl["hints"], pads.name, 3) if g["dos_hints"] else ""
            sc.free_mb = self._free_mb()
            st = g.get("state")
            sc.phase = g.get("phase") if st == "downloading" else \
                ("queued" if st == "queued" else None)   # waiting shows in the same module
            sc.behind = bool(self.inst.current and self.inst.current != g["id"])
            sc.fail_reason = g.get("fail_reason")
            inst = self.inst.index.get(g["id"])
            sc.install_path = inst["dir"] if inst else None
            n = len(sc.actions())
            sc.focus = max(0, min(sc.focus, n - 1))
            if self.picker and len(self.picker) == 2 and sc.overlay and sc.overlay[0] == "picker":
                if self.picker[0] == g["id"]:
                    self._picker_ready(sc)
            if sc.overlay and sc.overlay[0] == "confirm" and sc.overlay is not QUIT_DLG and (
                    (st not in ("queued", "downloading") and sc.overlay[1].startswith("Cancel"))):
                sc.overlay = None                 # the download finished under the dialog
        self._install_events()

    def _install_events(self):
        """Toasts for installs that finished in the background (and the tile's ✓ pop)."""
        while self.inst.events:
            kind, gid, msg = self.inst.events.pop(0)
            on_page = self.kind == "game" and self.scene.g["id"] == gid
            if kind == "failed" and not on_page:
                self.say(msg, error=True)
            elif kind == "done":
                # always: on the game page too (Omri saw nothing when he waited there), and the
                # tile's ✓ pops the next time the library shows it, even if it never saw it busy
                self.say(msg)
                from .ui import widgets as W
                W.mark_done(gid)
            elif kind == "error":                 # e.g. Change build failed, old build kept
                self.say(msg, error=True)

    def run(self, max_frames=None, script=None):
        clock = self.pg.time.Clock()
        frame = 0
        if self.autoplay:
            self._autoplay()
        while self.running:
            try:                                  # v0.9.28: a failure in one press or frame is logged (with its
                for act in self.inp.poll():       # traceback, in app.log) and the app goes on; it used to die
                    if act == "QUIT_EVENT":       # without a trace
                        self.running = False
                    else:
                        self.handle(act)
                if script and frame in script:
                    self.handle(script[frame])
                self.update()
                if self.fade_from is not None:
                    self._transition()
                else:
                    self.scene.draw(self.screen)
                self._ok_frames = getattr(self, "_ok_frames", 0) + 1
                if self._ok_frames >= 180:                # 3 s of good frames: the trouble is over
                    self._trips, self._seen_errors = 0, {}
            except Exception:  # noqa: BLE001
                self._frame_failed()
            self.pg.display.flip()
            clock.tick(60)
            frame += 1
            if max_frames and frame >= max_frames:
                break
        self.pg.quit()

def _frame_failed(self):
    """A press or a frame raised: write the traceback to app.log ONCE per distinct error (repeats are only counted,
    one short line every few seconds), tell the player in plain words, and carry on. Five failures in 3 s send the
    player back to the library; a third such trip, or 15 failures in 10 s, or a failing library, stops the app with
    the real error (never a frozen screen)."""
    if getattr(self, "strict", False):            # the selftest and the tests want the real error
        raise
    et, ev, tb = sys.exc_info()
    last = traceback.extract_tb(tb)[-1] if tb else None
    key = (et.__name__ if et else "?", last.filename if last else "", last.lineno if last else 0)
    now = time.time()
    seen = self.__dict__.setdefault("_seen_errors", {})
    rec = seen.get(key)
    if rec is None:
        seen[key] = [0, now]
        log.exception("frame failed (scene %s)", getattr(self, "kind", "?"))
    else:
        rec[0] += 1
        if now - rec[1] >= 5:
            log.error("same error again x%d (%s)", rec[0], key[0])
            rec[0], rec[1] = 0, now
    times = [t for t in getattr(self, "_fail_times", []) if now - t < 10] + [now]
    self._fail_times = times
    self._ok_frames = 0
    if now - getattr(self, "_say_at", 0) >= 5:
        self._say_at = now
        try:
            self.say("Something went wrong.", error=True)
        except Exception:  # noqa: BLE001
            pass
    if len(times) >= 15:
        log.error("too many failures in a row: stopping")
        raise
    if len([t for t in times if now - t < 3]) >= 5:
        self._fail_times = []
        self._trips = getattr(self, "_trips", 0) + 1
        if self._trips >= 3:
            log.error("the screen keeps failing after going back to the library: stopping")
            raise
        try:
            self.go_library()
        except Exception:  # noqa: BLE001
            log.exception("going back to the library failed too")
            raise


App._frame_failed = _frame_failed
App.strict = False


def _selftest_epic(app):
    """Settings → Epic Games → Connect: QR page; the phone sends Epic's page -> stand-in legendary
    signs in -> Epic tab fills; then Disconnect. No network: legendary is a tiny script here."""
    from .stores import epic
    b = epic.bin_path()
    b.parent.mkdir(parents=True, exist_ok=True)
    lst = b.parent / "list.json"
    lst.write_text(json.dumps([{"app_name": "Fern", "app_title": "Selftest Epic Game",
                                "asset_infos": {"Windows": {}}, "metadata": {}}]))
    b.write_text("#!/bin/sh\ncase \"$1 $2\" in\n"
                 '"auth --code") mkdir -p "$LEGENDARY_CONFIG_PATH"; '
                 'echo \'{"displayName": "selftest"}\' > "$LEGENDARY_CONFIG_PATH/user.json";;\n'
                 f'"list --json") cat "{lst}";;\n'
                 '"auth --delete") rm -f "$LEGENDARY_CONFIG_PATH/user.json";;\nesac\n')
    b.chmod(0o755)
    app.go_settings()
    labels = [r[0] for r in app.scene.items()]
    app.scene.focus = labels.index("Epic")
    assert app.scene.hints()[0] == ("A", "Sign in")
    app.handle(A)
    assert app.kind == "epic" and app.scene.status in ("phone", "nonet")
    app._epic_got('{"authorizationCode":"' + "c" * 32 + '","sid":null}')
    for _ in range(200):                                 # login + list run in threads
        app.update()
        if app.kind == "library" and not app.lib.epic_syncing and app.lib.by_id("epic-Fern"):
            break
        time.sleep(0.02)
    assert app.kind == "library" and app.scene.filt == "epic", app.kind
    assert app.lib.by_id("epic-Fern") and app.cfg.get("epic"), "Epic games didn't arrive"
    assert app.phone_status.startswith("Connected as selftest")
    app.go_settings()
    app.scene.focus = [r[0] for r in app.scene.items()].index("Epic")
    assert app.scene.hints()[0] == ("A", "Sign out")
    app.handle(A)
    app.handle(A)                                        # confirm
    assert not app.cfg.get("epic") and not app.lib.by_id("epic-Fern") and app.lib.epic is None
    if app.phone:
        app.phone.stop()
        app.phone = None


def _selftest_gog(app):
    """Settings → GOG → Sign in: QR page; the phone sends GOG's address -> sign-in (GOG's token
    answer stubbed) -> GOG tab fills (GOG's web API stubbed); game page: Install (gogdl stubbed:
    it writes a start.sh) -> Play + ⚙ without Change build -> Uninstall; then Sign out."""
    from .stores import gog
    saved = (gog.GogStore.sync, gog.GogStore._save_user, gog.GogStore._ask, gog.GogStore.info,
             gog.GogStore.install)

    def fake_install(self, app_name, platform, folder, **kw):
        (Path(folder) / "start.sh").write_text("#!/bin/sh\necho gog game\n")
        return gog.launch_info(folder, app_name, platform)
    gog.GogStore.info = lambda self, app_name, platform: {"need": 1000, "build": "B1", "version": "1"}
    gog.GogStore.install = fake_install
    gog.GogStore._ask = lambda self, **kw: {"access_token": "tok", "refresh_token": "r",
                                            "expires_in": 3600, "loginTime": time.time()}
    gog.GogStore.sync = lambda self: [gog.game_from_json(
        {"id": 1207658924, "title": "Selftest GOG Game", "image": "//x/a",
         "worksOn": {"Linux": True}, "category": "Adventure"})] if self.token() else []
    gog.GogStore._save_user = lambda self, tok: gog.user_file().write_text('{"username": "selftest"}')
    try:
        app.go_settings()
        app.scene.focus = [r[0] for r in app.scene.items()].index("GOG")
        assert app.scene.hints()[0] == ("A", "Sign in")
        app.handle(A)
        assert app.kind == "gog" and app.scene.status in ("phone", "nonet")
        app._gog_got("https://embed.gog.com/on_login_success?origin=client&code=" + "Ab_-9" * 20)
        for _ in range(200):                             # login + list run in threads
            app.update()
            if app.kind == "library" and not app.lib.gog_syncing and app.lib.by_id("gog-1207658924"):
                break
            time.sleep(0.02)
        assert app.kind == "library" and app.scene.filt == "gog", app.kind
        assert app.lib.by_id("gog-1207658924") and app.cfg.get("gog"), "GOG games didn't arrive"
        assert app.phone_status.startswith("Connected as selftest")
        assert "gog" in dict(app.scene.tabs())
        g = app.lib.by_id("gog-1207658924")
        app.go_game(g)
        assert [a[0] for a in app.scene.actions()] == ["Install", "Options"]
        app.game_action(g, "Install")
        for _ in range(200):
            app.update()
            if not app.inst.queue and not app.inst.current:
                break
            time.sleep(0.02)
        info = app.inst.index.get(g["id"])
        assert info and info["store"] == "gog" and info["exe"] == "start.sh", g.get("fail_reason")
        app.go_game(app.lib.by_id(g["id"]))
        assert [a[0] for a in app.scene.actions()] == ["Play", "Options"]
        assert app.scene.options() == ["Uninstall", "Controls", "Saves"]
        assert app.inst.uninstall(g["id"]) and g["id"] not in app.inst.index
        app.go_settings()
        app.scene.focus = [r[0] for r in app.scene.items()].index("GOG")
        assert app.scene.hints()[0] == ("A", "Sign out")
        app.handle(A)
        app.handle(A)                                    # confirm
        assert not app.cfg.get("gog") and not app.lib.by_id("gog-1207658924") and app.lib.gog is None
        assert not gog.auth_file().exists()
    finally:
        (gog.GogStore.sync, gog.GogStore._save_user, gog.GogStore._ask, gog.GogStore.info,
         gog.GogStore.install) = saved
    if app.phone:
        app.phone.stop()
        app.phone = None


def selftest(screenshot=None):
    """Headless: walk Setup -> Library (fake games) -> Game -> Settings without network."""
    import tempfile
    from . import fake
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    paths.use_root(tempfile.mkdtemp(prefix="scritch-selftest-"))
    from . import library as library_mod
    library_mod.Library._fetch_dosart = lambda self, g, force=False: None      # never asks GOG in a test
    App.strict = True                                                          # a failing step must fail the test
    app = App(windowed=True)
    assert app.kind == "setup"
    # v0.7 phone login: the phone sends a key -> checked -> library; the page closes soon after
    if app.phone:                                      # needs a network interface
        assert app.scene.qr and app.scene.url
        from .stores import itch as itch_mod
        real_check = itch_mod.ItchStore.check_key
        itch_mod.ItchStore.check_key = lambda self: "selftest-user"
        app.lib.start_sync = lambda *a, **k: None      # the fake key never goes online
        try:
            app._phone_got("Key: AbCdEf0123456789abcdefABCDEF")
            for _ in range(100):
                app.update()
                if app.kind == "library":
                    break
                time.sleep(0.02)
            assert app.kind == "library", app.kind
            assert app.cfg["api_key"] == "AbCdEf0123456789abcdefABCDEF"
            assert "Connected as selftest-user" in app.phone_status
            page = app.phone
            app.phone_stop_at = time.time() - 1
            app.update()
            assert app.phone is None and page.httpd is None, "phone page still open after Setup"
        finally:
            itch_mod.ItchStore.check_key = real_check
            app.cfg.pop("api_key", None)               # later steps start with no key, like
            app.cfg.pop("itch_user", None)             # before (CI has internet: a fake key
            config.save(app.cfg)                       # would be rejected -> back to Setup)
        app = App(windowed=True)
    app.run(max_frames=3, script={1: RIGHT})
    app = App(windowed=True)
    app.lib.games = [dict(g) for g in fake.library()]
    app.go_library()
    steps = [RIGHT, DOWN, X, X, A, DOWN, DOWN, UP, UP, R1, L1, A, START, DOWN, B, B, Y, START, B]
    app.run(max_frames=len(steps) * 2 + 2, script={i * 2: s for i, s in enumerate(steps)})
    # M6 Settings: every row does something; leftover saves found and deleted after Delete
    pre = config.install_root(app.cfg) / "_prefixes" / "old-game"
    pre.mkdir(parents=True, exist_ok=True)
    (pre / "save.dat").write_bytes(b"x" * 2000)
    app.go_settings()
    for _ in range(50):
        if app.saves is not None:
            break
        time.sleep(0.05)
    app.update()
    assert app.scene.v["prefix_size"].startswith("1 game"), app.scene.v["prefix_size"]
    labels = [r[0] for r in app.scene.items()]
    for lab in ("Install location", "Proton version", "Pointer speed"):
        app.scene.focus = labels.index(lab)
        app.handle(A)
        assert app.scene.toast != LATER, lab
    app.scene.focus = labels.index("Send logs")         # v0.9.15: phone page with the cleaned log
    assert app.scene.hints()[0] == ("A", "Open")
    app.handle(A)
    assert app.kind == "logs" and app.scene.status in ("phone", "nonet"), app.kind
    app.handle(B)
    assert app.kind == "settings"
    # Button symbols: Auto -> Steam Deck -> PlayStation -> Xbox -> Auto; glyphs follow
    from . import pads as P
    app.scene.focus = labels.index("Button symbols")
    seen = []
    for _ in range(4):
        app.handle(A)
        app.update()
        seen.append((app.scene.v["symbols"], P.current))
    assert [v for v, _ in seen[:3]] == ["Steam Deck", "PlayStation", "Xbox"], seen
    assert seen[1][1] == "ps" and seen[3][0].startswith("Auto"), seen
    app.scene.focus = labels.index("Saves of uninstalled games")
    assert app.scene.hints()[0] == ("A", "Delete")
    app.handle(A)
    assert app.scene.overlay and app.scene.overlay[0] == "confirm"
    app.handle(A)
    for _ in range(50):
        if not pre.exists():
            break
        time.sleep(0.05)
    assert not pre.exists(), "leftover prefix not deleted"
    # v0.7 Disconnect itch: confirm -> key forgotten -> Setup (with the phone QR if there's a network)
    app.cfg["api_key"], app.cfg["itch_user"] = "k" * 20, "selftest-user"
    app.go_settings()
    labels = [r[0] for r in app.scene.items()]
    app.scene.focus = labels.index("Disconnect itch")
    assert app.scene.hints()[0] == ("A", "Sign out")
    app.handle(A)
    assert app.scene.overlay and app.scene.overlay[0] == "confirm"
    app.handle(A)
    assert app.kind == "setup" and "api_key" not in app.cfg and app.lib.store is None
    app.go_library()
    _selftest_epic(app)
    _selftest_gog(app)
    # Play: a fake installed game (a tiny script) -> display released, game runs, display back
    app = App(windowed=True)
    app.lib.games = [dict(g) for g in fake.library()]
    g = next(g for g in app.lib.games if g.get("state") == "installed")
    d = paths.HOME / "games" / "fake"
    (d / "files").mkdir(parents=True, exist_ok=True)
    save = paths.HOME / ".local/share/selftest-game/save.dat"      # the game saves (Linux)
    (d / "files" / "run.sh").write_text("#!/bin/sh\necho hello from the game LD=$LD_LIBRARY_PATH\n"
                                        f"mkdir -p '{save.parent}' && echo slot1 > '{save}'\n")
    (d / "files" / "run.sh").chmod(0o755)
    app.inst.index[g["id"]] = {"dir": str(d), "exe": "run.sh"}
    app.go_game(g)
    app.run(max_frames=4, script={1: A})
    out = (paths.LOGS / "games" / f"{slug_of(g)}.log").read_text()
    assert app.kind == "game" and "hello" in out
    assert "_MEI" not in out and "/_internal" not in out, "game inherited our bundled libs"
    # Save backups: learned + backed up after play; ⚙ → Saves → confirm puts them back
    def toast_is(msg):
        for _ in range(100):
            app.update()
            if app.scene.toast == msg:
                return True
            time.sleep(0.05)
        return False
    assert toast_is("Saves backed up."), app.scene.toast
    save.write_text("lost\n")
    app.game_action(g, "Saves")
    assert app.scene.overlay and app.scene.overlay[1] == "Saves", app.scene.overlay
    app.handle(A)
    assert app.scene.overlay and app.scene.overlay[0] == "confirm", app.scene.overlay
    app.handle(A)
    assert toast_is("Saves put back.") and save.read_text() == "slot1\n", app.scene.toast
    # ⚙ Controls row (16 Nov): ◀ ▶ change it in place like Sort & filter; Auto shows its pick
    app.go_game(app.lib.by_id(g["id"]) or g)
    app.update()
    app.scene.open_options()
    i = [r[0] for r in app.scene.overlay[3]].index("Controls")
    app.scene.open_options(i)

    def ctl():
        return app.scene.overlay[3][i][1]
    assert ctl().startswith("Auto · "), ctl()
    app.handle(RIGHT)
    assert ctl() == "Pad" and app.cfg["controls"][g["id"]] == "gamepad", ctl()
    app.handle(LEFT)
    app.handle(LEFT)
    assert ctl() == "Keys" and app.scene.overlay[0] == "menu", ctl()
    app.handle(RIGHT)
    assert ctl().startswith("Auto · ") and g["id"] not in app.cfg.get("controls", {}), ctl()
    # Move (16 Nov): ⚙ → Move to internal storage → confirm → copied, switched, old copy gone
    app.scene.overlay = None
    other = paths.HOME / "Internal" / "scritch"
    real_choices = config.install_choices
    config.install_choices = lambda: [("SD card", d.parent), ("Internal storage", other)]
    try:
        app.open_options(app.scene)
        if "More" in [r[0] for r in app.scene.overlay[3]]:           # v0.9.25: a long list tucks Move under More
            app.scene.open_options(more=True)
        labels = [r[0] for r in app.scene.overlay[3]]
        assert "Move to internal storage" in labels, labels
        app.scene.overlay = (*app.scene.overlay[:4], labels.index("Move to internal storage"))
        app.handle(A)
        assert app.scene.overlay and app.scene.overlay[0] == "confirm", app.scene.overlay
        app.handle(A)
        assert toast_is(f"{g['title']} moved to internal storage."), app.scene.toast
        assert app.inst.index[g["id"]]["dir"] == str(other / d.name)
        assert (other / d.name / "files" / "run.sh").exists()
    finally:
        config.install_choices = real_choices
    if screenshot:
        import pygame
        pygame.init()
        app = App(windowed=True)
        app.lib.games = [dict(g) for g in fake.library()]
        app.go_library()
        app.scene.draw(app.screen)
        pygame.image.save(app.screen, screenshot)
        pygame.quit()

def main(argv=None):
    p = argparse.ArgumentParser(prog="scritch")
    p.add_argument("--windowed", action="store_true", help="1280x800 window (Desktop Mode)")
    p.add_argument("--play", metavar="GAME_ID", help="play one installed game, then quit (an Add to Steam shortcut)")
    p.add_argument("--selftest", action="store_true", help="headless smoke test")
    p.add_argument("--screenshot", help="with --selftest: save last frame as PNG")
    p.add_argument("--render-mockups", metavar="DIR", help="save every page/state as PNGs to DIR")
    p.add_argument("--real", metavar="DATA", help="with --render-mockups: use a copy of the real cache (library.json, covers, pages, shots); SCRITCH_GAME=title picks the game")
    a = p.parse_args(argv)
    moved = paths.migrate()          # itch-deck -> scritch folders, before any file is opened
    setup_logging()
    log.info("start v%s args=%s", VERSION, argv or sys.argv[1:])
    for line in moved:
        log.info("%s", line)

    if a.render_mockups:
        from .mockups import render
        files = render(a.render_mockups, VERSION, real=a.real)
        print(f"{len(files)} mockups -> {a.render_mockups}")
        return 0
    if a.selftest:
        selftest(a.screenshot)
        print("selftest ok")
        return 0
    other = paths.lock_instance()
    for _ in range(12 if a.play else 0):       # a Steam tile pressed while the old copy is still closing
        if other is None:
            break
        time.sleep(0.5)
        other = paths.lock_instance()
    if other is not None:
        log.warning("another copy is already running (pid %s), quitting", other)
        logging.shutdown()
        return 0
    exit_on_signals()
    sys.excepthook = lambda et, ev, tb: log.error("uncaught error", exc_info=(et, ev, tb))
    threading.excepthook = lambda args: log.error("error in thread %s", getattr(args.thread, "name", "?"),
                                                   exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
    app = App(windowed=a.windowed, autoplay=a.play)
    _APP[0] = app
    app.run()
    log.info("quit")
    logging.shutdown()
    os._exit(0)          # don't wait on background threads (downloads resume next launch)

_APP = [None]

def exit_on_signals():
    """Steam's "Exit game" sends SIGTERM. Handle it ourselves (installed before pygame.init, so
    SDL keeps its hands off): stop a running game, leave the main loop, and hard-exit after 3 s
    if anything stalls."""
    import signal
    os.environ["SDL_NO_SIGNAL_HANDLERS"] = "1"
    # Mouse mode reads the pads while our window is hidden behind a game: SDL would otherwise
    # drop controller input for an unfocused window.
    os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")

    def on_signal(num, _frame):
        log.info("signal %d: quitting", num)
        if _APP[0]:
            _APP[0].running = False
        runner.stop_child()
        t = threading.Timer(3.0, lambda: os._exit(0))
        t.daemon = True
        t.start()
    for name in ("SIGTERM", "SIGHUP", "SIGINT"):
        signal.signal(getattr(signal, name), on_signal)
