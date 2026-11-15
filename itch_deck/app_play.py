"""Launching a game: hand the screen over, wait, come back.
Mixed into App (app.py); split out of app.py on 15 Nov, code unchanged."""
import logging
from pathlib import Path

from . import mouse, proton, runner
from .installer import slug_of

log = logging.getLogger("itch-deck")


QUIT_HINT = "To quit a game: hold View + Menu (Create + Options) for 2 seconds"


class PlayMixin:
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
        state = {"closed": False}
        mm = None
        if self.controls_of(g)[1] == "mouse":
            mm = mouse.MouseMode(pg, self.inp.pads, self.cfg.get("pointer_speed", "normal"))
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

        rc, secs = runner.run(exe, slug_of(g), on_started=release, pump=pg.event.pump,
                              size=self.screen.get_size(), umu=umu, extra_env=env, hold=hold)
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
        if combo.fired:                      # closed with the shortcut: not a crash
            self.say(f"{g['title']} closed.")
            return
        if mm and mm.error and not runner.crashed(rc, secs):
            self.say(f"Mouse mode didn't start ({mm.error}). The game ran without it.", error=True)
        if runner.crashed(rc, secs):
            hint = runner.crash_hint(slug_of(g))
            log.info("play: %s crashed%s", g["id"], f" ({hint})" if hint else "")
            self.say(hint or f"{g['title']} closed right after starting. Details are in its log.",
                     error=True)

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
        self.screen.blit(W.backdrop(t), (0, 0))
        W.text(t, self.screen, msg, t.cx, t.h / 2, t.f_h2, anchor="center")
        if sub:
            W.text(t, self.screen, sub, t.cx, t.h / 2 + t.u * 6, t.f_body, color=t.dim,
                   anchor="center")
        self.pg.display.flip()
