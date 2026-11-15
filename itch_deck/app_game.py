"""Game page: buttons, Change build picker, uninstall, controls (mouse mode).
Mixed into App (app.py); split out of app.py on 15 Nov, code unchanged."""
import logging
import threading
from pathlib import Path

from . import config, mouse
from .input import (A, B, START, L1, R1)
from .app_common import LATER

log = logging.getLogger("itch-deck")


class GameMixin:
    CONTROLS = ("auto", "gamepad", "mouse")

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
