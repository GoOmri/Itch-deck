"""itch-deck: scene switching, key import, library sync, installs (Linux + Windows via Proton)."""
import argparse
import logging
import os
import shutil
import sys
import threading
import time
from pathlib import Path

from . import config, mouse, net, paths, proton, runner, theme
from .input import (Input, A, B, X, Y, UP, DOWN, LEFT, RIGHT, START, L1, R1,
                    TEXT, BKSP, ENTER, PASTE)
from .installer import Installer, slug_of
from .library import Library, short_date
from .stores.itch import ItchStore
from .updater import Updater

log = logging.getLogger("itch-deck")
VERSION = "0.6.1"
QUIT_DLG = ("confirm", "Quit SCRiTCH?", "Downloads in progress pause and resume next time.",
            [("A", "Quit"), ("B", "Cancel")])
LATER = "Comes in a later update."


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
        self.inst = Installer(self.lib, lambda: config.install_root(self.cfg), self.cfg)
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
            self.inst.resume()
        else:
            self.go_setup("waiting")

    # --- display -------------------------------------------------------
    def open_display(self):
        self.fade_from = None
        pg = self.pg
        pg.display.init()
        pg.font.init()
        if self.windowed:
            self.screen = pg.display.set_mode((1280, 800))
        else:
            self.screen = pg.display.set_mode((0, 0), pg.FULLSCREEN)
        from .ui.widgets import APP_NAME
        pg.display.set_caption(APP_NAME)
        pg.mouse.set_visible(False)
        self.t = theme.Theme(pg, self.screen.get_size())
        log.info("display open %s driver=%s", self.screen.get_size(), pg.display.get_driver())

    # --- navigation ----------------------------------------------------
    def say(self, msg, error=False):
        self.scene.toast, self.scene.toast_error = msg, error
        self.toast_until = time.time() + self.t.toast_s

    def _set(self, kind, scene):
        from .ui import widgets as W
        if self.scene is not None and W.LIVE:
            depth = {"setup": 0, "library": 1, "game": 2, "settings": 3}
            self.fade_dir = 1 if depth.get(kind, 0) >= depth.get(self.kind, 0) else -1  # in / back
            try:
                self.fade_from, self.fade_t0 = self.screen.copy(), time.monotonic()  # slide + fade
            except Exception:  # noqa: BLE001  - display closed (game running): no fade
                self.fade_from = None
        self.kind, self.scene = kind, scene
        self.toast_until = 0

    def go_setup(self, status, back=False):
        from .ui.scenes.setup import Setup
        self._set("setup", Setup(self.t, status, back=back))
        self.inp.set_text_mode(False)

    def go_library(self):
        from .ui.scenes.library import Library as LibScene
        sc = LibScene(self.t, self.lib.games, filt=self.filt,
                      sort=self.cfg.get("library_sort", "az"), show=self.cfg.get("library_show", "all"))
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
        from .ui.scenes.library import visible
        return visible(self.lib.games, self.filt, self.cfg.get("library_sort", "az"),
                       self.cfg.get("library_show", "all"))

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
            "update": self.updater.row_value(),
            "pointer": self.cfg.get("pointer_speed", "normal").capitalize(),
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
            if sc.back:                    # came from Settings: the old key still works
                prev = getattr(self, "settings_back", "library")
                self.go_settings()
                self.settings_back = prev  # Settings' own B still returns where it came from
            else:                          # first run / rejected key: nothing to go back to
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
        if sc.overlay and sc.overlay[0] == "menu":   # X: Sort & filter
            if act == A:
                sc.menu_next(sc.overlay[3][sc.overlay[4]][0])
                self.cfg["library_sort"], self.cfg["library_show"] = sc.sort, sc.show
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
            if self.lib.start_sync():
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

    def _h_game(self, act):
        sc = self.scene
        if sc.overlay and sc.overlay[0] == "picker" and act == A:
            self._pick(sc)
            return
        if sc.overlay and sc.overlay[0] == "menu" and act == A:      # ☰ Options
            label = sc.overlay[3][sc.overlay[4]][0]
            sc.overlay = None
            self.game_action(sc.g, label)
            return
        if sc.overlay:                    # screenshot viewer / build picker
            sc.handle(act)
            return
        if act == B:
            self.go_library()
        elif act in (L1, R1):
            shown = self._shown()
            if sc.g in shown and len(shown) > 1:
                i = (shown.index(sc.g) + (1 if act == R1 else -1)) % len(shown)
                self.go_game(shown[i])
        elif act == START:                # ☰ on a game = its Options (Steam Deck); Settings: Library
            sc.open_options()
        elif act == A and sc.section == "actions":
            acts = sc.actions()
            label = acts[min(sc.focus, len(acts) - 1)] if acts else None
            if label and label[0] == "Options":        # the ⚙ button
                sc.open_options()
            elif label and label[2]:
                self.game_action(sc.g, label[0])
        elif not isinstance(act, tuple):
            sc.handle(act)

    # --- install / play ------------------------------------------------
    def confirm(self, title, body, yes, fn):
        self.on_confirm = fn
        self.scene.overlay = ("confirm", title, body, [("A", yes), ("B", "Cancel")])

    def game_action(self, g, label):
        gid = g["id"]
        if label in ("Install", "Retry install"):
            if self.inst.enqueue(g):
                if self.inst.current and self.inst.current != gid:
                    self.say("Queued. It starts after the current download.")
        elif label == "Cancel":
            self.confirm("Cancel the install?", f"{g['title']} stops downloading and the partial "
                         "download is deleted.", "Cancel install", lambda: self.inst.cancel(gid))
        elif label == "Uninstall":
            self.confirm(f"Uninstall {g['title']}?", "The game's files are deleted. You can "
                         "install it again any time.", "Uninstall", lambda: self._uninstall(g))
        elif label == "Play":
            self.play(g)
        elif label == "Change build":
            self.change_build(g)
        elif label.startswith("Controls"):
            self.cycle_controls(g)
        else:
            self.say(LATER)

    # --- Change build (picker) ------------------------------------------
    def change_build(self, g):
        if self.lib.offline or not self.lib.store:
            if len(self.inst.programs(g["id"])) > 1:   # the program list works offline
                self._program_picker(g["id"])
                return
            self.say("Changing the build needs internet.", error=True)
            return
        gid, self.picker = g["id"], None
        self.scene.overlay = ("picker", "Choose a build", "Loading builds…", [], 0)

        def work():
            try:
                builds = self.lib.store.list_builds(g)
            except Exception as e:  # noqa: BLE001
                log.info("change build %s: %s", gid, e)
                builds = None
            self.picker = (gid, builds)
        threading.Thread(target=work, daemon=True, name="builds").start()

    def _picker_ready(self, sc):
        """Fill the open picker once the upload list is in: recommended first, then the rest."""
        from .stores.itch import pick_build
        gid, builds = self.picker
        self.picker = (gid, builds, True, 0)
        if builds is None:
            if len(self.inst.programs(gid)) > 1:
                self._program_picker(gid)
                return
            sc.overlay = None
            self.say("Couldn't load the builds. Try again when you're online.", error=True)
            return
        lin, lin_o = pick_build(builds, "linux")
        win, win_o = pick_build(builds, "windows")
        order = [b for b in [lin] + lin_o + [win] + win_o if b]
        order = [b for i, b in enumerate(order) if b not in order[:i]]
        if not order:
            if len(self.inst.programs(gid)) > 1:
                self._program_picker(gid)
                return
            sc.overlay = None
            self.say("This game has no other Linux or Windows builds.")
            return
        cur = (self.inst.index.get(gid) or {}).get("upload_id")
        items, progs = [], self.inst.programs(gid)
        if len(progs) > 1:                 # first row: which file starts the game
            items.append(("Program to run", Path(progs[0]).name,
                          f"{len(progs)} programs found · A to choose"))
        extra = len(items)
        for b in order:
            kind = "Linux" if b["linux"] else "Windows"
            sub = f"{kind} · {b['size'] // 1_000_000} MB" + (f" · {b['updated'][:10]}" if b["updated"] else "")
            if b["demo"]:
                sub += " · demo"
            val = "Installed" if b["id"] == cur else ("Recommended" if b is order[0] else "")
            items.append((b["filename"], val, sub))
        self.picker = (gid, order, True, extra)
        sub = "A installs it. Saves of Windows builds are kept separately." if cur else \
            "A installs it. Linux builds are recommended when there is one."
        sc.overlay = ("picker", "Choose a build", sub, items, 0)

    def _pick(self, sc):
        if not self.picker or len(self.picker) < 3 or not sc.overlay[3]:
            return
        gid, order, _, extra = self.picker
        i = sc.overlay[4] - extra
        if order == "exe":                 # program picker
            sc.overlay, self.picker = None, None
            if self.inst.set_exe(gid, self._progs[i]):
                self.say(f"{Path(self._progs[i]).name} starts the game from now on.")
            return
        if i < 0:
            self._program_picker(gid)
            return
        b = order[i]
        sc.overlay, self.picker = None, None
        if (self.inst.index.get(gid) or {}).get("upload_id") == b["id"]:
            self.say("That build is already installed.")
            return
        g = self.lib.by_id(gid) or sc.g
        self.inst.enqueue(g, upload_id=b["id"])
        sc.focus = 0
        self.say(f"Installing {b['filename']}…")

    def _program_picker(self, gid):
        """O1 as a program list: every runnable file found in the install, current one tagged."""
        self._progs = self.inst.programs(gid)
        items = [(Path(p).name, "In use" if i == 0 else "", str(Path(p).parent)
                  if str(Path(p).parent) != "." else "Top folder") for i, p in enumerate(self._progs)]
        self.picker = (gid, "exe", True, 0)
        self.scene.overlay = ("picker", "Choose the program", "Pick the file that starts the game. "
                              "Helpers like crash reporters are left out.", items, 0)

    def _uninstall(self, g):
        if not self.inst.uninstall(g["id"]):
            self.say("The SD card is missing, so the game can't be uninstalled now.", error=True)
            return
        self.scene.focus = 0
        self.say(f"{g['title']} was uninstalled.")

    # --- controls (mouse mode) ---------------------------------------------------
    CONTROLS = ("auto", "gamepad", "mouse")

    def controls_of(self, g):
        """(setting, effective): setting auto|gamepad|mouse; auto follows itch's Inputs."""
        setting = (self.cfg.get("controls") or {}).get(g["id"], "auto")
        eff = mouse.auto_mode(g.get("inputs")) if setting == "auto" else setting
        return setting, eff

    def controls_label(self, g):
        setting, eff = self.controls_of(g)
        name = {"gamepad": "Pad", "mouse": "Mouse"}[eff]
        return f"{name} controls" + (" · auto" if setting == "auto" else "")

    def cycle_controls(self, g):
        setting, _ = self.controls_of(g)
        nxt = self.CONTROLS[(self.CONTROLS.index(setting) + 1) % 3]
        ctl = dict(self.cfg.get("controls") or {})
        if nxt == "auto":
            ctl.pop(g["id"], None)
        else:
            ctl[g["id"]] = nxt
        self.cfg["controls"] = ctl
        config.save(self.cfg)
        _, eff = self.controls_of(g)
        log.info("controls %s: %s (%s)", g["id"], nxt, eff)
        self.say({"mouse": "Right stick moves the mouse, R2 clicks while this game runs.",
                  "gamepad": "The game gets the controller as a gamepad."}[eff] +
                 (" (Auto: from the game's itch page)" if nxt == "auto" else ""))

    def play(self, g):
        exe = self.inst.exe_path(g["id"])
        if not exe or not exe.exists():
            self.say("The game's files are missing. Uninstall and install it again.", error=True)
            return
        info = self.inst.index[g["id"]]
        self.lib.mark_played(g)             # Recent tab
        umu = env = hold = None
        sub = None
        if info.get("platform") == "windows":
            umu, pdir = proton.umu_path(), proton.proton_dir(self.cfg)
            if not pdir:
                self.say("GE-Proton isn't installed. Add it with ProtonUp-Qt in Desktop Mode.",
                         error=True)
                return
            if not umu:
                self.say("umu-launcher is missing. Uninstall and install the game again.",
                         error=True)
                return
            prefix = info.get("prefix") or proton.prefix_dir(Path(info["dir"]).parent,
                                                              Path(info["dir"]).name)
            env = proton.env(pdir, prefix)
            if proton.first_run(prefix):
                sub = "Preparing Proton… first run only, about 30 s"
                hold = lambda: proton.first_run(prefix)   # noqa: E731
            log.info("play: %s via %s, prefix %s", g["id"], pdir.name, prefix)
        pg = self.pg
        self.scene.toast, self.toast_until = None, 0
        self._splash(f"Starting {g['title']}…", sub)
        state = {"closed": False}
        mm = None
        if self.controls_of(g)[1] == "mouse":
            mm = mouse.MouseMode(pg, self.inp.pads, self.cfg.get("pointer_speed", "normal"))

        def release():                       # after the overlap: the game has its window up
            if not state["closed"]:
                state["closed"] = True
                pg.display.quit()
                if mm:                       # our window is gone: the mapper owns SDL now
                    mm.start()

        rc, secs = runner.run(exe, slug_of(g), on_started=release, pump=pg.event.pump,
                              size=self.screen.get_size(), umu=umu, extra_env=env, hold=hold)
        if mm:
            mm.stop()
        if state["closed"]:
            self.open_display()
            self._splash("Returning…")
        self.inp.flush()
        self.go_game(self.lib.by_id(g["id"]) or g)
        if mm and mm.error and not runner.crashed(rc, secs):
            self.say(f"Mouse mode isn't available: {mm.error}.", error=True)
        if runner.crashed(rc, secs):
            hint = runner.crash_hint(slug_of(g))
            log.info("play: %s crashed%s", g["id"], f" ({hint})" if hint else "")
            self.say(hint or f"{g['title']} closed right after starting. Details are in its log.",
                     error=True)

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

    def _splash(self, msg, sub=None):
        """One plain frame while the screen changes hands (less of Steam's UI flickers through)."""
        from .ui import widgets as W
        t = self.t
        self.screen.blit(W.backdrop(t), (0, 0))
        W.text(t, self.screen, msg, t.cx, t.h / 2, t.f_h2, anchor="center")
        if sub:
            W.text(t, self.screen, sub, t.cx, t.h / 2 + t.u * 6, t.f_body, color=t.dim,
                   anchor="center")
        self.pg.display.flip()

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
            elif label == "Pointer speed":
                order = ("slow", "normal", "fast")
                cur = self.cfg.get("pointer_speed", "normal")
                self.cfg["pointer_speed"] = order[(order.index(cur) + 1) % 3] if cur in order else "normal"
                config.save(self.cfg)
                sc.v["pointer"] = self.cfg["pointer_speed"].capitalize()
            elif label == "Re-import API key":
                self.go_setup("waiting", back=True)
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
        sc.activity = self._activity()
        sc.notice = self._update_notice()
        sc.focus = max(0, min(sc.focus, len(sc.shown) - 1))

    def _update_notice(self):
        u = self.updater
        return {"available": f"Update v{u.new_version} available · Settings",
                "downloading": f"Updating · {int(u.frac * 100)}%",
                "ready": f"v{u.new_version} installed · restart in Settings"}.get(u.state)

    def _activity(self):
        """Top-bar background work: a running download first, then sync/covers/details."""
        gid = self.inst.current
        g = self.lib.by_id(gid) if gid else None
        if g and g.get("state") == "downloading":
            more = len(self.inst.queue) - 1
            what = {"extract": "Unpacking", "umu": "Getting umu-launcher"}.get(
                g.get("phase"), f"Downloading {int(g.get('progress', 0) * 100)}%")
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
        if now > self.next_mount_check:               # SD card in/out: refresh install states
            self.next_mount_check = now + 2
            self._check_mounts()
        if self.kind == "library":
            self._sync_library_scene()
            if self.lib.sync_error and not self.lib.syncing:
                self.say("Couldn't refresh the library. Details are in the log.", error=True)
                self.lib.sync_error = None
        elif self.kind == "settings":
            self.scene.v["update"] = self.updater.row_value()
        elif self.kind == "game":
            sc = self.scene
            sc.offline = self.lib.offline
            g = self.lib.by_id(sc.g["id"])
            if g is not None and g is not sc.g:   # list replaced by a sync
                sc.g = g
            g = sc.g
            g["controls_label"] = self.controls_label(g)
            st = g.get("state")
            sc.phase = g.get("phase") if st == "downloading" else None
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
        while self.inst.events:
            kind, gid, msg = self.inst.events.pop(0)
            on_page = self.kind == "game" and self.scene.g["id"] == gid
            if kind == "failed" and not on_page:
                self.say(msg, error=True)
            elif kind == "done" and not on_page:
                self.say(msg)
            elif kind == "error":                 # e.g. Change build failed, old build kept
                self.say(msg, error=True)

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
            if self.fade_from is not None:
                self._transition()
            else:
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
    # Settings -> Re-import API key -> B returns to Settings (not a quit dialog)
    app = App(windowed=True)
    app.lib.games = [dict(g) for g in fake.library()]
    app.go_library()
    app.go_settings()
    app.scene.focus = next(i for i, r in enumerate(app.scene.items()) if r[0] == "Re-import API key")
    app.run(max_frames=6, script={1: A, 3: B})
    assert app.kind == "settings" and not app.scene.overlay and app.settings_back == "library", \
        (app.kind, app.scene.overlay)
    # Play: a fake installed game (a tiny script) -> display released, game runs, display back
    app = App(windowed=True)
    app.lib.games = [dict(g) for g in fake.library()]
    g = next(g for g in app.lib.games if g.get("state") == "installed")
    d = paths.HOME / "games" / "fake"
    (d / "files").mkdir(parents=True, exist_ok=True)
    (d / "files" / "run.sh").write_text("#!/bin/sh\necho hello from the game LD=$LD_LIBRARY_PATH\n")
    (d / "files" / "run.sh").chmod(0o755)
    app.inst.index[g["id"]] = {"dir": str(d), "exe": "run.sh"}
    app.go_game(g)
    app.run(max_frames=4, script={1: A})
    out = (paths.LOGS / "games" / f"{slug_of(g)}.log").read_text()
    assert app.kind == "game" and "hello" in out
    assert "_MEI" not in out, "game inherited PyInstaller's LD_LIBRARY_PATH"
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
    p.add_argument("--real", metavar="DATA", help="with --render-mockups: use a copy of the real cache (library.json, covers, pages, shots); SCRITCH_GAME=title picks the game")
    a = p.parse_args(argv)
    setup_logging()
    log.info("start v%s args=%s", VERSION, argv or sys.argv[1:])

    if a.render_mockups:
        from .mockups import render
        files = render(a.render_mockups, VERSION, real=a.real)
        print(f"{len(files)} mockups -> {a.render_mockups}")
        return 0
    if a.selftest:
        selftest(a.screenshot)
        print("selftest ok")
        return 0
    exit_on_signals()
    app = App(windowed=a.windowed)
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
