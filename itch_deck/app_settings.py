"""Settings page: values, row actions, saves of uninstalled games.
Mixed into App (app.py); split out of app.py on 15 Nov, code unchanged."""
import logging
import shutil
import threading
from pathlib import Path

from . import config, proton
from .input import (A, B, START)
from .library import short_date
from .app_common import _gb

log = logging.getLogger("itch-deck")


class SettingsMixin:
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
        want = self.cfg.get("proton")
        proton_v = (want if want in protons else f"Auto · {protons[0]}") if protons else "Not installed"
        label = "SD card" if config.on_card(root) else "Internal storage"
        self._scan_saves()
        return {
            "install_label": label + (" (missing)" if config.card_missing(root) else ""),
            "install_path": str(root), "free": free, "proton": proton_v,
            "prefix_size": "Checking…", "last_sync": short_date(self.lib.synced_at),
            "update": self.updater.row_value(),
            "pointer": self.cfg.get("pointer_speed", "normal").capitalize(),
        }

    def _save_roots(self):
        roots = {str(config.install_root(self.cfg))}
        roots |= {str(Path(i["dir"]).parent) for i in self.inst.index.values() if i.get("dir")}
        return roots

    def _scan_saves(self):
        """Size of leftover prefixes, in the background (thousands of files per prefix)."""
        self.saves = None
        installed = {Path(i["dir"]).name for i in self.inst.index.values() if i.get("dir")}
        roots = self._save_roots()

        def work():
            dirs = proton.leftover_prefixes(roots, installed)
            self.saves = (dirs, sum(proton.dir_size(d) for d in dirs))
        threading.Thread(target=work, daemon=True).start()

    def _saves_label(self):
        if self.saves is None:
            return "Checking…"
        dirs, size = self.saves
        return f"{len(dirs)} game{'s' * (len(dirs) != 1)} · {_gb(size)}" if dirs else "None"

    def _delete_saves(self):
        dirs = self.saves[0] if self.saves else []
        if not dirs:
            self.say("No saves of uninstalled games to delete.")
            return

        def go():
            def work():
                for d in dirs:
                    log.info("settings: deleting prefix %s", d)
                    shutil.rmtree(d, ignore_errors=True)
                self._scan_saves()
            threading.Thread(target=work, daemon=True).start()
            self.say(f"Deleted the saves of {len(dirs)} uninstalled game{'s' * (len(dirs) != 1)}.")
        self.confirm("Delete saves?", f"Saved games and settings of {len(dirs)} uninstalled "
                     f"game{'s' * (len(dirs) != 1)} are deleted for good. Installed games keep "
                     "theirs.", "Delete", go)

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
            elif label == "Install location":
                opts = config.install_choices()
                cur = str(config.install_root(self.cfg))
                i = next((k for k, (_, p) in enumerate(opts) if str(p) == cur), -1)
                if len(opts) == 1 and i == 0:
                    self.say("No SD card found. Games install to internal storage.")
                else:
                    name, path = opts[(i + 1) % len(opts)]
                    self.cfg["install_root"] = str(path)
                    config.save(self.cfg)
                    self._card_out = config.card_missing(path)
                    sc.v.update(self.settings_values())
                    self.say(f"New games install to {name.lower()}. Installed games stay where they are."
                             if name != "SD card" else "New games install to the SD card. "
                             "Installed games stay where they are.")
            elif label == "Proton version":
                names = config.proton_versions()
                if not names:
                    self.say(proton.NEED_GE, error=True)
                else:
                    opts = [None] + names               # None = Auto (newest)
                    cur = self.cfg.get("proton")
                    i = opts.index(cur) if cur in opts else 0
                    self.cfg["proton"] = opts[(i + 1) % len(opts)]
                    config.save(self.cfg)
                    sc.v.update(self.settings_values())
            elif label == "Saves of uninstalled games":
                self._delete_saves()
            elif label == "Pointer speed":
                order = ("slow", "normal", "fast")
                cur = self.cfg.get("pointer_speed", "normal")
                self.cfg["pointer_speed"] = order[(order.index(cur) + 1) % 3] if cur in order else "normal"
                config.save(self.cfg)
                sc.v["pointer"] = self.cfg["pointer_speed"].capitalize()
            elif label == "Re-import API key":
                self.go_setup("waiting", back=True)
                self.try_import(auto=True)
        elif not isinstance(act, tuple):
            sc.handle(act)
