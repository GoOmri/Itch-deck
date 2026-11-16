"""Launching a game: hand the screen over, wait, come back.
Mixed into App (app.py); split out of app.py on 15 Nov, code unchanged."""
import logging
import threading
import time
from pathlib import Path

from . import backups, mouse, proton, runner, words
from .installer import slug_of

log = logging.getLogger("scritch")


# To quit a game: hold the pad's View + Menu (DualSense: Create + Options) 2 s (mouse.QuitCombo).
# Drawn with the glyphs of the pad in use (W.glyph_line), so it names the buttons you hold.
QUIT_HINT = ["To quit a game: hold", ("BACK",), "+", ("START",), "for 2 seconds"]


class PlayMixin:
    def play(self, g):
        exe = self.inst.exe_path(g["id"])
        if not exe or not exe.exists():
            self.say("Game files missing. Reinstall to play.", error=True)
            return
        info = self.inst.index[g["id"]]
        self.lib.mark_played(g)             # Recent tab
        umu = env = hold = None
        sub = None
        if info.get("platform") == "windows":
            umu, pdir = proton.umu_path(), proton.proton_dir(self.cfg)
            if not pdir:
                self.say(proton.NEED_GE,
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
        self._splash(f"Starting {g['title']}…", sub or QUIT_HINT)
        args, secret, cwd = (), (), None
        if info.get("store") == "epic":           # legendary says how (and signs the game in)
            from .stores.epic import EpicError
            try:
                lp = self.lib.epic.launch_params(info["app_name"]) if self.lib.epic else None
            except EpicError as e:
                log.info("play: epic launch params: %s", e)
                lp = None
            if not lp:
                self.say(f"{g['title']} couldn't start. Connect Epic again in Settings.", error=True)
                return
            exe = Path(lp["game_directory"]) / lp["game_executable"]
            args = list(lp.get("game_parameters") or []) + list(lp.get("user_parameters") or [])
            secret = list(lp.get("egl_parameters") or [])
            cwd = lp.get("working_directory") or None
            log.info("play: epic %s -> %s (%d args, %d sign-in args)", info["app_name"],
                     exe, len(args), len(secret))
        state = {"closed": False}
        mm = None
        eff = self.controls_of(g)[1]
        if eff in ("mouse", "keys"):           # Keys = keyboard keys + the same mouse
            mm = mouse.MouseMode(pg, self.inp.pads, self.cfg.get("pointer_speed", "normal"),
                                 layout=eff)
        combo = mouse.QuitCombo(pg, self.inp.pads, runner.stop_child)

        def release():                       # the game's window is up: step aside
            if not state["closed"]:
                state["closed"] = True
                state["hidden"] = self._hide_window()
                if not state["hidden"]:
                    pg.display.quit()
                if mm:                       # our window is out of the way: the mapper owns SDL
                    mm.combo = combo         # one pad reader: mouse mode feeds the shortcut
                if not (mm and mm.start()):
                    combo.start()

        t0 = time.time()
        rc, secs = runner.run(exe, slug_of(g), on_started=release, pump=pg.event.pump,
                              size=self.screen.get_size(), umu=umu, extra_env=env, hold=hold,
                              args=args, secret_args=secret, cwd=cwd)
        if mm:
            mm.stop()
        combo.stop()
        if state.get("hidden"):
            self._show_window()              # instant: no display re-init, so no Steam UI gap
            self._splash("Returning…")
        elif state["closed"]:
            self.open_display()
            self._splash("Returning…")
        self.inp.flush()
        self.go_game(self.lib.by_id(g["id"]) or g)
        self._backup_after_play(g, info, t0 - 2)
        if combo.fired:                      # closed with the shortcut: not a crash
            self.say(f"{g['title']} closed.")
            return
        if mm and mm.error and not runner.crashed(rc, secs):
            mode = "Keys" if mm.mapper.layout == "keys" else "Mouse"
            words.log_code("P02", f"{g['id']}: {mode} mode off: {mm.error}")
            self.say(words.with_code(f"{mode} controls didn't start.", "P02"), error=True)
        if runner.crashed(rc, secs):
            hint = runner.crash_hint(slug_of(g))
            log.info("play: %s crashed%s", g["id"], f" ({hint})" if hint else "")
            if hint:
                self.say(f"{g['title']} couldn't start. {hint}", error=True)
            else:
                words.log_code("P01", f"{g['id']} ({g['title']}) closed after {secs:.0f} s, exit {rc}")
                self.say(words.with_code(f"{g['title']} couldn't start.", "P01"), error=True)

    def _backup_after_play(self, g, info, since):
        """Saves backup (16 Nov): automatic after every play, only when the saves changed. In a
        thread (zipping can take a few seconds); the toast comes via self.backup_note."""
        def work():
            try:
                if info.get("platform") != "windows":
                    backups.learn(g["id"], g["title"], since)
                if backups.backup(g["id"], g["title"], info):
                    self.backup_note = ("Saves backed up.", False)
            except Exception as e:  # noqa: BLE001
                log.exception("backup %s failed", g["id"])
                words.log_code("S01", f"{g['id']} ({g['title']}): {e}")
                self.backup_note = (words.with_code("Couldn't back up the saves.", "S01"), True)
        threading.Thread(target=work, daemon=True, name="backup").start()

    def _hide_window(self):
        """Hide our window while a game runs instead of closing the display: showing it again is
        instant, while reopening the display took ~0.9 s under gamescope (Steam's UI showed
        through). config "launch_release": "quit" goes back to closing the display."""
        if self.cfg.get("launch_release") == "quit":
            return False
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")     # pygame-ce: from_display_module is deprecated
                self._win = self.pg.Window.from_display_module()
            self._win.hide()
            log.info("play: window hidden")
            return True
        except Exception as e:  # noqa: BLE001  - old pygame / driver without windows
            log.info("play: can't hide the window (%s), closing the display", e)
            return False

    def _show_window(self):
        self._win.show()
        try:
            self._win.focus()
        except Exception:  # noqa: BLE001
            pass
        self.screen = self.pg.display.get_surface()
        log.info("play: window shown")

    def _splash(self, msg, sub=None):
        """One plain frame while the screen changes hands (less of Steam's UI flickers through)."""
        from .ui import widgets as W
        t = self.t
        W.splash(t, self.screen, msg, sub)
        self.pg.display.flip()
