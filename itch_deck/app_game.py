"""Game page: buttons, Change build picker, uninstall, controls (mouse mode).
Mixed into App (app.py); split out of app.py on 15 Nov, code unchanged."""
import logging
import threading
from pathlib import Path

from . import backups, config, mouse, pads, words
from .input import (A, B, START, L1, R1, LEFT, RIGHT)
from .app_common import LATER

log = logging.getLogger("scritch")


class GameMixin:
    CONTROLS = ("auto", "gamepad", "mouse", "keys")

    def _h_game(self, act):
        sc = self.scene
        if sc.overlay and sc.overlay[0] == "picker" and act == A:
            self._pick(sc)
            return
        if sc.overlay and sc.overlay[0] == "menu" and act in (A, LEFT, RIGHT) and \
                sc.overlay[3][sc.overlay[4]][0] == "Controls":           # ◀ ▶ like Sort & filter
            self.cycle_controls(sc.g, -1 if act == LEFT else 1)
            sc.g["controls_value"] = self.controls_value(sc.g)
            sc.open_options(sc.overlay[4])
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
            self.open_options(sc)
        elif act == A and sc.section == "actions":
            acts = sc.actions()
            label = acts[min(sc.focus, len(acts) - 1)] if acts else None
            if label and label[0] == "Options":        # the ⚙ button
                self.open_options(sc)
            elif label and label[2]:
                self.game_action(sc.g, label[0])
        elif not isinstance(act, tuple):
            sc.handle(act)

    def confirm(self, title, body, yes, fn, main=False):
        """main=True: the action doesn't delete or close anything -> purple, not red."""
        self.on_confirm = fn
        self.scene.overlay = ("confirm", title, body, [("A", yes), ("B", "Cancel")]) + \
            (("main",) if main else ())

    def game_action(self, g, label):
        gid = g["id"]
        if label in ("Install", "Retry install"):
            if self.inst.enqueue(g):
                if self.inst.current and self.inst.current != gid:
                    self.say("Queued. It starts after the current download.")
        elif label == "Cancel" and self.inst.moving == gid:
            self.confirm("Cancel the move?", [f"{g['title']} stays where it was."], "Cancel move",
                         lambda: self.inst.cancel_move(gid))
        elif label == "Cancel":
            self.confirm("Cancel the install?", f"{g['title']} stops downloading and the partial "
                         "download is deleted.", "Cancel install", lambda: self.inst.cancel(gid))
        elif label == "Uninstall":
            self.confirm(f"Uninstall {g['title']}?", "The game's files are deleted. You can "
                         "install it again any time.", "Uninstall", lambda: self._uninstall(g))
        elif label == "Remove from library":
            self.confirm(f"Remove {g['title']} from your library?",
                         ["Your game files stay in the folder.", "Copy the folder again to add it back."],
                         "Remove", lambda: self._uninstall(g), main=True)
        elif label == "Program to run":
            self._program_picker(gid)
        elif label == "Play":
            self.play(g)
        elif label == "Update":
            if self.lib.offline or not {"epic": self.lib.epic, "gog": self.lib.gog}.get(
                    g.get("store"), self.lib.store):
                self.say("Updating needs internet.", error=True)
            elif self.inst.update(g) and self.inst.current and self.inst.current != gid:
                self.say("Queued. The update starts after the current download.")
        elif label == "Change build":
            self.change_build(g)
        elif label.startswith("Controls"):
            self.cycle_controls(g)
        elif label == "Saves":
            self.saves_picker(g)
        elif label.startswith("Move to "):
            self._ask_move(g)
        else:
            self.say(LATER)

    def change_build(self, g):
        if g.get("store") == "gog":                    # GOG: Linux or Windows version (v0.9.5)
            return self._gog_versions(g)
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
                          f"{len(progs)} programs found · {pads.name('A')} to choose"))
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
        if order == "saves":               # Saves list: restore one
            z = self._zips[sc.overlay[4]]
            sc.overlay, self.picker = None, None
            self._ask_restore(self.lib.by_id(gid) or sc.g, z)
            return
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
        info = self.inst.index.get(gid) or {}
        if (info.get("platform") if info.get("store") == "gog" else info.get("upload_id")) == b["id"]:
            self.say("That build is already installed.")
            return
        g = self.lib.by_id(gid) or sc.g
        self.inst.enqueue(g, upload_id=b["id"])
        sc.focus = 0
        self.say(f"Installing the {b['filename']} version…" if g.get("store") == "gog"
                 else f"Installing {b['filename']}…")

    def _gog_versions(self, g):
        if self.lib.offline or not self.lib.gog:
            self.say("Changing the version needs internet.", error=True)
            return
        info = self.inst.index.get(g["id"]) or {}
        cur = info.get("platform")
        order = [{"id": p, "filename": name} for p, name in (("linux", "Linux"), ("windows", "Windows"))]
        items = [(b["filename"], "Installed" if b["id"] == cur else
                  ("Recommended" if b["id"] == "linux" and not cur else ""), "") for b in order]
        self.picker = (g["id"], order, True, 0)
        self.scene.overlay = ("picker", "Choose a version",
                              "A installs it. Your saves are kept." if cur else
                              "A installs it.", items, 0)

    def _program_picker(self, gid):
        """O1 as a program list: every runnable file found in the install, current one tagged."""
        self._progs = self.inst.programs(gid)
        items = [(Path(p).name, "In use" if i == 0 else "", str(Path(p).parent)
                  if str(Path(p).parent) != "." else "Top folder") for i, p in enumerate(self._progs)]
        self.picker = (gid, "exe", True, 0)
        self.scene.overlay = ("picker", "Choose the program", "Pick the file that starts the game. "
                              "Helpers like crash reporters are left out.", items, 0)

    def open_options(self, sc):
        """⚙ / ☰: the menu also offers moving the game to the other drive (SD card <-> internal)."""
        t = self.inst.move_target(sc.g["id"], config.install_choices())
        self._move_target = t
        sc.g["move_to"] = (t[0] if t[0] == "SD card" else t[0].lower()) if t else None
        sc.open_options()

    def _ask_move(self, g):
        t = getattr(self, "_move_target", None)
        if not t:
            return
        where = t[0] if t[0] == "SD card" else t[0].lower()
        self.confirm(f"Move {g['title']} to {where}?", ["The game and its saves move together.",
                     "You can play again when it's done."], "Move",
                     lambda: self.inst.move(g["id"], t[1], where), main=True)

    def saves_picker(self, g):
        """⚙ → Saves: the game's backups, newest first; A restores one (after a confirm)."""
        self._zips = backups.listing(g["id"], g["title"])
        if not self._zips:
            self.say("No saves backed up yet. They're saved after you play.")
            return
        items = []
        for i, z in enumerate(self._zips):
            when, tag = backups.label(z)
            items.append((when, tag or ("Latest" if i == 0 else ""),
                          f"{max(1, z.stat().st_size // 1000)} KB"))
        self.picker = (g["id"], "saves", True, 0)
        self.scene.overlay = ("picker", "Saves", "Backed up after each play. A puts one back.",
                              items, 0)

    def _ask_restore(self, g, z):
        when, _ = backups.label(z)
        self.confirm(f"Put back the saves from {when}?", ["Your saves now are backed up first.",
                     "You can go back to them."], "Put back", lambda: self._restore(g, z),
                     main=True)

    def _restore(self, g, z):
        info = dict(self.inst.index.get(g["id"]) or {})

        def work():
            try:
                backups.restore(g["id"], g["title"], info, z)
                self.backup_note = ("Saves put back.", False)
            except Exception as e:  # noqa: BLE001
                log.exception("restore %s failed", g["id"])
                words.log_code("S02", f"{g['id']} ({g['title']}) from {z.name}: {e}")
                self.backup_note = (words.with_code("Couldn't put the saves back.", "S02"), True)
        threading.Thread(target=work, daemon=True, name="restore").start()

    def _uninstall(self, g):
        if not self.inst.uninstall(g["id"]):
            self.say("SD card missing.", error=True)
            return
        self.scene.focus = 0
        self.say(f"{g['title']} was removed." if g.get("store") == "dos"
                 else f"{g['title']} was uninstalled.")

    def controls_of(self, g):
        """(setting, effective): setting auto|gamepad|mouse|keys; auto follows itch's Inputs."""
        setting = (self.cfg.get("controls") or {}).get(g["id"], "auto")
        if setting not in self.CONTROLS:
            setting = "auto"
        eff = mouse.auto_mode(g.get("inputs")) if setting == "auto" else setting
        return setting, eff

    def controls_label(self, g):
        setting, eff = self.controls_of(g)
        name = {"gamepad": "Pad", "mouse": "Mouse", "keys": "Keys"}[eff]
        return f"{name} controls" + (" · auto" if setting == "auto" else "")

    def controls_value(self, g):
        """'Auto · Pad' (what Auto picked for this game), 'Pad', 'Mouse' or 'Keys'."""
        setting, eff = self.controls_of(g)
        name = {"gamepad": "Pad", "mouse": "Mouse", "keys": "Keys"}[eff]
        return f"Auto · {name}" if setting == "auto" else name

    def cycle_controls(self, g, step=1):
        setting, _ = self.controls_of(g)
        nxt = self.CONTROLS[(self.CONTROLS.index(setting) + step) % len(self.CONTROLS)]
        ctl = dict(self.cfg.get("controls") or {})
        if nxt == "auto":
            ctl.pop(g["id"], None)
        else:
            ctl[g["id"]] = nxt
        self.cfg["controls"] = ctl
        config.save(self.cfg)
        _, eff = self.controls_of(g)
        log.info("controls %s: %s (%s)", g["id"], nxt, eff)
        a = pads.name("A")
        if eff in ("mouse", "keys"):       # the row shows the setting; say how the mapping works
            self.say({"mouse": "Mouse: right stick moves, R2 clicks.",
                      "keys": f"Keys: D-pad = arrows, {a} = Space."}[eff])
        else:
            self.scene.toast, self.toast_until = None, 0
