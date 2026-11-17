"""Launching a game: hand the screen over, wait, come back.
Mixed into App (app.py); split out of app.py on 15 Nov, code unchanged."""
import logging
import threading
import time
from pathlib import Path

from . import backups, dosbox, mouse, paths, proton, runner, words
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
        dos = None
        if dosbox.is_dosbox_game(info):          # GOG DOS game: native DOSBox Staging (v0.9.7)
            if info.get("setup_steps") and self._gog_needs_setup(info):
                # GOG's setup tool (ISI) writes the game's DOSBox settings files (Heroic runs it
                # for these games too), so it runs BEFORE DOSBox reads them (v0.9.12)
                u, pd = proton.umu_path(), proton.proton_dir(self.cfg)
                if u and pd:
                    pre = info.get("prefix") or proton.prefix_dir(Path(info["dir"]).parent,
                                                                  Path(info["dir"]).name)
                    self._gog_first_run(g, info, u, proton.env(pd, pre))
                else:
                    log.info("play: %s DOS setup skipped (no GE-Proton / umu)", g["id"])
            base = dosbox.native() or self._get_dosbox(g)
            dos = dosbox.launch(info, base) if base else None
            log.info("play: %s dosbox %s", g["id"], "native" if dos else "missing: via Proton")
        elif dosbox.is_own_dos(info):            # your own DOS game: DOSBox Staging (v0.9.19)
            base = dosbox.native() or self._get_dosbox(g)
            if not base:
                self.say("DOSBox isn't available. Check Wi-Fi and try again.", error=True)
                return
            dos = dosbox.launch_own(info, base)
        if info.get("platform") == "windows" and not dos:
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
        if info.get("store") == "gog" and info.get("setup_steps") and not dos and \
                self._gog_needs_setup(info):
            self._gog_first_run(g, info, umu, env)
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
        elif dos:                                 # DOSBox Staging with GOG's settings files
            exe, args, cwd = dos
        elif info.get("store") == "gog":          # from GOG's play task (stores/gog.launch_info)
            args = list(info.get("args") or [])
            cwd = str(Path(info["dir"]) / "files" / info["cwd"]) if info.get("cwd") else None
            if info.get("platform") == "windows":
                from .stores.gog import windows_args
                args = windows_args(args, cwd or exe.parent)
            log.info("play: gog %s -> %s (%d args)", info.get("app_name"), exe, len(args))
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
            log.info("play: %s crashed%s; game log ends:\n    %s", g["id"], f" ({hint})" if hint else "",
                     "\n    ".join(runner.log_tail(slug_of(g))))
            if hint and info.get("store") == "gog" and hint == runner.TRY_OTHER_BUILD:
                hint = ("Try the Windows version in Options." if info.get("platform") == "linux"
                        and "windows" in (g.get("platforms") or ()) else None)  # GOG: no builds list
            if hint:
                self.say(f"{g['title']} couldn't start. {hint}", error=True)
            elif info.get("setup"):              # GOG first-run setup we don't run yet
                words.log_code("P03", f"{g['id']} ({g['title']}) closed after {secs:.0f} s, exit {rc}")
                self.say(words.with_code(f"{g['title']} couldn't start.", "P03"), error=True)
            else:
                words.log_code("P01", f"{g['id']} ({g['title']}) closed after {secs:.0f} s, exit {rc}")
                self.say(words.with_code(f"{g['title']} couldn't start.", "P01"), error=True)

    def _get_dosbox(self, g):
        """First DOS game: install DOSBox Staging (Flathub, once) while a splash says so."""
        res = {}
        log_file = paths.LOGS / "games" / f"{slug_of(g)}-setup.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        th = threading.Thread(target=lambda: res.setdefault("cmd", dosbox.ensure(log_file)),
                              daemon=True, name="dosbox")
        th.start()
        while th.is_alive():
            self.pg.event.pump()
            self._splash("Getting DOSBox…", "One time only, for DOS games")
            th.join(0.25)
        return res.get("cmd")

    def _gog_needs_setup(self, info):
        """Not run yet, or a part was missing last time (v0.9.5 never fetched GOG's setup tool):
        run it (again)."""
        from .stores import gog
        files = Path(info["dir"]) / "files"
        return not info.get("setup_done") or any(gog.required(st) and not gog.step_exe(st, files)
                                                 for st in info["setup_steps"])

    def _gog_first_run(self, g, info, umu, env):
        """GOG Windows game, first Play (v0.9.5): install the parts it needs (Visual C++,
        DirectX…) and run GOG's setup tool, quietly, in its prefix. Once per install (an update
        keeps it done). Failures are logged; the game starts anyway (P03 if it then fails)."""
        from .stores import gog
        slug = slug_of(g)
        log_file = paths.LOGS / "games" / f"{slug}-setup.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        files = Path(info["dir"]) / "files"
        res = {}

        def work():
            try:
                missing = [st["name"] for st in info["setup_steps"]
                           if st["base"] == "redist" and not gog.step_exe(st, files)]
                if missing and self.lib.gog and not self.lib.offline:   # v0.9.5 left ISI out
                    try:
                        self.lib.gog.redist(missing, log_file=log_file)
                    except gog.GogError as e:
                        log.info("play: gog redist %s: %s", missing, e)
                res["failed"] = gog.run_setup(info["setup_steps"], files, umu, env, log_file)
            except Exception as e:  # noqa: BLE001
                log.exception("play: gog first-run setup")
                res["failed"] = [f"error {type(e).__name__}"]
        th = threading.Thread(target=work, daemon=True, name="gog-setup")
        th.start()
        log.info("play: %s first-run setup (%d steps)", g["id"], len(info["setup_steps"]))
        while th.is_alive():                     # keep the screen alive while it works
            self.pg.event.pump()
            self._splash(f"Preparing {g['title']}…", "First run only, can take a few minutes")
            th.join(0.25)
        missing = [st["name"] for st in info["setup_steps"]
                   if gog.required(st) and not gog.step_exe(st, files)]
        info["setup_done"] = not missing         # a part we couldn't get: try again next Play
        if res.get("failed"):
            info["setup"] = True                 # a crash right after -> P03
            log.info("play: %s first-run setup: not done: %s", g["id"], ", ".join(res["failed"]))
        self.inst._save_info(g["id"], info)

    def _backup_after_play(self, g, info, since):
        """Saves backup (16 Nov): automatic after every play, only when the saves changed. In a
        thread (zipping can take a few seconds); the toast comes via self.backup_note."""
        if info.get("store") == "dos":           # the game's saves sit in its own folder
            return

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
