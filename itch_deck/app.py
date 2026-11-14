"""itch-deck: scene switching, key import, library sync. (M2: real library, no installs yet.)"""
import argparse
import logging
import os
import shutil
import sys
import threading
import time

from . import config, net, paths, theme
from .input import (Input, A, B, X, Y, UP, DOWN, LEFT, RIGHT, START, L1, R1,
                    TEXT, BKSP, ENTER, PASTE)
from .library import Library, short_date
from .stores.itch import ItchStore
from .updater import Updater

log = logging.getLogger("itch-deck")
VERSION = "0.2.5"
QUIT_DLG = ("confirm", "Quit itch-deck?", "Downloads in progress pause and resume next time.",
            [("A", "Quit"), ("B", "Cancel")])
LATER = "Installing comes in the next update."


def setup_logging():
    paths.LOGS.mkdir(parents=True, exist_ok=True)
    from logging.handlers import RotatingFileHandler
    h = RotatingFileHandler(paths.LOGS / "app.log", maxBytes=1_000_000, backupCount=3)
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(threadName)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[h, logging.StreamHandler()], force=True)


def _gb(n):
    return f"{n / 1e9:.0f} GB" if n >= 10e9 else f"{n / 1e9:.1f} GB"


class App:
    def __init__(self, windowed=False):
        import pygame
        self.pg = pygame
        self.windowed = windowed
        pygame.init()
        self.inp = Input(pygame)
        self.open_display()
        self.cfg = config.load()
        key = self.cfg.get("api_key")
        self.lib = Library(ItchStore(key) if key else None)
        self.running = True
        self.scene, self.kind = None, None
        self.toast_until = 0
        self.filt, self.lib_focus_id = "all", None
        self.key_result = None          # (status, key, file, user) from the checking thread
        self.pending_key = None         # key waiting for Retry after "offline"
        self.tried_mtime = None
        self.next_poll = 0
        from .ui import widgets
        widgets.LIVE = True                # animate scrolling + spinners (mockups stay still)
        self.updater = Updater(VERSION)
        self.updater.check(quiet=True)     # one GitHub call at launch; Settings shows the result
        self.update_told = False
        if key:
            self.go_library()
            self.lib.queue_covers()
            self.lib.start_sync()
        else:
            self.go_setup("waiting")

    # --- display -------------------------------------------------------
    def open_display(self):
        pg = self.pg
        pg.display.init()
        pg.font.init()
        if self.windowed:
            self.screen = pg.display.set_mode((1280, 800))
        else:
            self.screen = pg.display.set_mode((0, 0), pg.FULLSCREEN)
        pg.display.set_caption("itch-deck")
        pg.mouse.set_visible(False)
        self.t = theme.Theme(pg, self.screen.get_size())
        log.info("display open %s driver=%s", self.screen.get_size(), pg.display.get_driver())

    # --- navigation ----------------------------------------------------
    def say(self, msg, error=False):
        self.scene.toast, self.scene.toast_error = msg, error
        self.toast_until = time.time() + self.t.toast_s

    def _set(self, kind, scene):
        self.kind, self.scene = kind, scene
        self.toast_until = 0

    def go_setup(self, status):
        from .ui.scenes.setup import Setup
        self._set("setup", Setup(self.t, status))
        self.inp.set_text_mode(False)

    def go_library(self):
        from .ui.scenes.library import Library as LibScene
        sc = LibScene(self.t, self.lib.games, filt=self.filt)
        self._set("library", sc)
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

    def go_settings(self):
        from .ui.scenes.settings import Settings
        self.settings_back = self.kind
        self._set("settings", Settings(self.t, self.settings_values(), VERSION,
                                       str(paths.LOGS / "app.log")))

    def _shown(self):
        if self.filt == "installed":
            return [g for g in self.lib.games if g.get("state") == "installed"]
        return self.lib.games

    def settings_values(self):
        root = config.install_root(self.cfg)
        free = "?"
        p = root
        while not p.exists() and p != p.parent:
            p = p.parent
        try:
            free = _gb(shutil.disk_usage(p).free)
        except OSError:
            pass
        protons = config.proton_versions()
        return {
            "install_label": "SD card" if str(root).startswith("/run/media") else "Internal storage",
            "install_path": str(root), "free": free,
            "proton": self.cfg.get("proton") or (protons[0] if protons else "Not found"),
            "prefix_size": "None yet", "last_sync": short_date(self.lib.synced_at),
            "update": self.updater.label(),
        }

    # --- API key -------------------------------------------------------
    def try_import(self, auto=False):
        f = paths.KEY_FILE
        if not f.exists():
            if not auto:
                self.say("No itch_key.txt in Downloads yet.", error=True)
            return
        self.tried_mtime = f.stat().st_mtime
        txt = f.read_text(errors="replace").strip()
        key = txt.split()[0] if txt else ""
        if not key:
            if not auto:
                self.say("itch_key.txt is empty.", error=True)
            return
        self.check_key(key, f)

    def check_key(self, key, file=None):
        self.scene.status, self.scene.typing = "testing", False
        self.inp.set_text_mode(False)

        def work():
            try:
                user = ItchStore(key).check_key()
                self.key_result = ("ok", key, file, user)
            except net.AuthError:
                self.key_result = ("rejected", key, file, None)
            except net.Offline as e:
                log.info("key check offline: %s", e)
                self.key_result = ("offline", key, file, None)
            except Exception:  # noqa: BLE001
                log.exception("key check failed")
                self.key_result = ("offline", key, file, None)
        threading.Thread(target=work, daemon=True, name="keycheck").start()

    def _key_done(self):
        status, key, file, user = self.key_result
        self.key_result = None
        log.info("key check: %s", status)
        if status != "ok":
            self.pending_key = key if status == "offline" else None
            self.scene.status = status
            return
        self.cfg["api_key"] = key
        config.save(self.cfg)
        if file:
            try:
                file.unlink()
            except OSError:
                log.warning("could not delete %s", file)
        self.pending_key = None
        self.lib.store, self.lib.auth_failed = ItchStore(key), False
        self.go_library()
        self.lib.start_sync()
        self.say(f"Connected to itch.io as {user}.")

    # --- per-scene input -----------------------------------------------
    def handle(self, act):
        sc = self.scene
        if sc.overlay and sc.overlay[0] == "confirm":     # only Quit uses it in M2
            if act == A:
                self.running = False
            elif act == B:
                sc.overlay = None
            return
        getattr(self, f"_h_{self.kind}")(act)

    def _h_setup(self, act):
        sc = self.scene
        if sc.status == "testing":
            return
        if sc.typing:
            kind, val = act if isinstance(act, tuple) else (act, None)
            if kind == TEXT:
                sc.typed = (sc.typed + val.strip())[:128]
            elif kind == BKSP:
                sc.typed = sc.typed[:-1]
            elif kind == PASTE:
                sc.typed = (sc.typed + self._clipboard())[:128]
            elif kind in (ENTER, A) and sc.typed:
                self.check_key(sc.typed)
            elif kind == B:
                sc.typing = False
                self.inp.set_text_mode(False)
            return
        if isinstance(act, tuple):
            return
        if act == A:
            label = sc.buttons()[sc.focus]
            if label == "Type key":
                sc.typing, sc.typed = True, ""
                self.inp.set_text_mode(True)
            elif label == "Retry" and self.pending_key:
                self.check_key(self.pending_key, paths.KEY_FILE if paths.KEY_FILE.exists() else None)
            else:
                self.try_import()
        elif act == B:
            sc.overlay = QUIT_DLG
        else:
            sc.handle(act)

    def _clipboard(self):
        try:
            sc = self.pg.scrap
            if not sc.get_init():
                sc.init()
            return (sc.get_text() or "").strip()
        except Exception:  # noqa: BLE001
            return ""

    def _h_library(self, act):
        sc = self.scene
        if act == A and sc.shown:
            self.go_game(sc.shown[sc.focus])
        elif act == B:
            sc.overlay = QUIT_DLG
        elif act == Y:
            if self.lib.start_sync():
                self.say("Refreshing library…")
        elif act == START:
            self.go_settings()
        elif act in (UP, DOWN, LEFT, RIGHT, X) or act in ("L2", "R2"):
            sc.handle(act)
            self.filt = sc.filt
            if sc.shown:
                self.lib_focus_id = sc.shown[sc.focus]["id"]

    def _h_game(self, act):
        sc = self.scene
        if sc.overlay:                    # screenshot viewer
            sc.handle(act)
            return
        if act == B:
            self.go_library()
        elif act in (L1, R1):
            shown = self._shown()
            if sc.g in shown and len(shown) > 1:
                i = (shown.index(sc.g) + (1 if act == R1 else -1)) % len(shown)
                self.go_game(shown[i])
        elif act == START:
            self.go_settings()
        elif act == A and sc.section == "actions":
            acts = sc.actions()
            if acts and acts[sc.focus][2]:
                self.say(LATER)
        elif not isinstance(act, tuple):
            sc.handle(act)

    def _h_settings(self, act):
        sc = self.scene
        if act in (B, START):
            back = getattr(self, "settings_back", "library")
            if back == "game" and self.lib.by_id(self.lib_focus_id):
                self.go_game(self.lib.by_id(self.lib_focus_id))
            else:
                self.go_library()
        elif act == A:
            label = sc.items()[sc.focus][0]
            if label == "Refresh library":
                self.say("Refreshing library…" if self.lib.start_sync() else "Already refreshing…")
            elif label == "Update app":
                u = self.updater
                if u.state == "available":
                    u.download()
                elif u.state == "ready":
                    u.restart(self.pg)
                elif u.state == "source":
                    self.say("Updates only work in the released app.")
                elif not u.busy():
                    u.check()
            elif label == "Re-import API key":
                self.go_setup("waiting")
                self.try_import(auto=True)
            else:
                self.say("Comes in a later update.")
        elif not isinstance(act, tuple):
            sc.handle(act)

    # --- per-frame state -----------------------------------------------
    def _sync_library_scene(self):
        sc = self.scene
        sc.games = self.lib.games
        sc.syncing, sc.sync_page = self.lib.syncing, self.lib.page
        sc.offline_since = self.lib.offline_since if self.lib.games else None
        sc.offline = self.lib.offline and not self.lib.games
        sc.focus = max(0, min(sc.focus, len(sc.shown) - 1))

    def update(self):
        now = time.time()
        if self.toast_until and now > self.toast_until:
            self.scene.toast, self.toast_until = None, 0
        if self.key_result and self.kind == "setup":
            self._key_done()
        if self.lib.auth_failed:
            self.lib.auth_failed = False
            self.go_setup("rejected")
        if self.kind == "setup" and self.scene.status in ("waiting", "rejected") \
                and not self.scene.typing and now > self.next_poll:
            self.next_poll = now + 2
            f = paths.KEY_FILE
            if f.exists() and f.stat().st_mtime != self.tried_mtime:
                self.try_import(auto=True)     # Warpinator drop is picked up by itself
        elif self.kind == "library":
            self._sync_library_scene()
            if self.lib.sync_error and not self.lib.syncing:
                self.say("Couldn't refresh the library. Details are in the log.", error=True)
                self.lib.sync_error = None
            if self.updater.state == "available" and not self.update_told and not self.scene.toast:
                self.update_told = True
                self.say(f"Update v{self.updater.new_version} is ready to download in Settings.")
        elif self.kind == "settings":
            self.scene.v["update"] = self.updater.label()
        elif self.kind == "game":
            self.scene.offline = self.lib.offline
            g = self.lib.by_id(self.scene.g["id"])
            if g is not None and g is not self.scene.g:   # list replaced by a sync
                self.scene.g = g

    def run(self, max_frames=None, script=None):
        clock = self.pg.time.Clock()
        frame = 0
        while self.running:
            for act in self.inp.poll():
                if act == "QUIT_EVENT":
                    self.running = False
                else:
                    self.handle(act)
            if script and frame in script:
                self.handle(script[frame])
            self.update()
            self.scene.draw(self.screen)
            self.pg.display.flip()
            clock.tick(60)
            frame += 1
            if max_frames and frame >= max_frames:
                break
        self.pg.quit()


def selftest(screenshot=None):
    """Headless: walk Setup -> Library (fake games) -> Game -> Settings without network."""
    import tempfile
    from . import fake
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    paths.use_root(tempfile.mkdtemp(prefix="itch-deck-selftest-"))
    app = App(windowed=True)
    assert app.kind == "setup"
    app.run(max_frames=3, script={1: RIGHT})
    app = App(windowed=True)
    app.lib.games = [dict(g) for g in fake.library()]
    app.go_library()
    steps = [RIGHT, DOWN, X, X, A, DOWN, DOWN, UP, UP, R1, L1, A, START, DOWN, B, B, Y, START, B]
    app.run(max_frames=len(steps) * 2 + 2, script={i * 2: s for i, s in enumerate(steps)})
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
    p = argparse.ArgumentParser(prog="itch-deck")
    p.add_argument("--windowed", action="store_true", help="1280x800 window (Desktop Mode)")
    p.add_argument("--selftest", action="store_true", help="headless smoke test")
    p.add_argument("--screenshot", help="with --selftest: save last frame as PNG")
    p.add_argument("--render-mockups", metavar="DIR", help="save every page/state as PNGs to DIR")
    a = p.parse_args(argv)
    setup_logging()
    log.info("start v%s args=%s", VERSION, argv or sys.argv[1:])

    if a.render_mockups:
        from .mockups import render
        files = render(a.render_mockups, VERSION)
        print(f"{len(files)} mockups -> {a.render_mockups}")
        return 0
    if a.selftest:
        selftest(a.screenshot)
        print("selftest ok")
        return 0
    App(windowed=a.windowed).run()
    return 0
