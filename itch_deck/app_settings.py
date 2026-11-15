"""Settings page: values, row actions, saves of uninstalled games.
Mixed into App (app.py); split out of app.py on 15 Nov, code unchanged."""
import logging
import shutil
import threading
from pathlib import Path

from . import config, pads, proton
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
        proton_v = (want if want in protons else f"Auto · {protons[0]}") if protons else \
            f"Not installed · {pads.name('A')} to download"
        label = "SD card" if config.on_card(root) else "Internal storage"
        self._scan_saves()
        return {
            "install_label": label + (" (missing)" if config.card_missing(root) else ""),
            "install_path": str(root), "free": free, "proton": proton_v,
            "prefix_size": "Checking…", "last_sync": short_date(self.lib.synced_at),
            "itch_user": self.cfg.get("itch_user") or "",
            "update": self.updater.row_value(),
            "pointer": self.cfg.get("pointer_speed", "normal").capitalize(),
            "symbols": self._symbols_label(),
        }

    def _symbols_label(self):
        want = self.cfg.get("button_symbols", "auto")
        if want in pads.KINDS:
            return pads.LABEL[want]
        return f"Auto · {pads.LABEL[self.inp.kind()]}"

    def _disconnect_itch(self):
        self.cfg.pop("api_key", None)
        self.cfg.pop("itch_user", None)
        config.save(self.cfg)
        self.lib.store = None
        log.info("settings: itch disconnected")
        self.go_setup("waiting")
        self.say("Signed out of itch. Sign in again any time.")

    def _get_ge(self):
        """Settings: download GE-Proton now instead of with the first Windows game."""
        job = self.ge_job = {"progress": 0.0, "done": False, "error": None}

        def on_bytes(done, total):
            job["progress"] = done / total if total else 0

        def work():
            try:
                name = proton.fetch_ge(on_bytes=on_bytes)
                job["name"] = name
            except proton.ProtonError as e:
                job["error"] = str(e)
            except Exception:  # noqa: BLE001
                log.exception("ge-proton download failed")
                job["error"] = "Couldn't get GE-Proton. Details are in the log."
            job["done"] = True
        threading.Thread(target=work, daemon=True, name="ge-proton").start()
        self.say("Downloading GE-Proton (about 0.5 GB, one time).")

    def _ge_row(self):
        """Per frame while Settings is open: the Proton row follows a running download."""
        job = getattr(self, "ge_job", None)
        if not job:
            return None
        if not job["done"]:
            return f"Downloading {int(job['progress'] * 100)}%"
        self.ge_job = None
        if job["error"]:
            log.info("ge-proton: %s", job["error"])
            self.say("Couldn't get GE-Proton.", error=True)
        else:
            self.say(f"{job['name']} installed. Windows games are ready to go.")
        return self.settings_values()["proton"]

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
        n = f"{len(dirs)} uninstalled game{'s' * (len(dirs) != 1)}"
        self.confirm("Delete saves?", [f"Saves of {n} are deleted for good.",
                                       "Installed games keep theirs."], "Delete", go)

    def _h_settings(self, act):
        sc = self.scene
        if (act == B and not sc.side) or (act == A and sc.side):
            sc.handle(act)                              # in/out of a category (sidebar)
        elif act in (B, START):
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
                    self.say(f"New games install to {name.lower()}." if name != "SD card"
                             else "New games install to the SD card.")
            elif label == "Proton version":
                names = config.proton_versions()
                job = getattr(self, "ge_job", None)
                if job and not job["done"]:
                    self.say("GE-Proton is already downloading.")
                elif not names:
                    self._get_ge()
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
            elif label == "Button symbols":
                order = pads.CHOICES
                cur = self.cfg.get("button_symbols", "auto")
                self.cfg["button_symbols"] = order[(order.index(cur) + 1) % len(order)] \
                    if cur in order else "auto"
                config.save(self.cfg)
                pads.set_current(self.pad_kind())
                sc.v["symbols"] = self._symbols_label()
            elif label == "Re-import API key":
                self.go_setup("waiting", back=True)
                self.try_import(auto=True)
            elif label == "Disconnect itch":
                self.confirm("Sign out of itch?",
                             ["SCRiTCH forgets the key. Installed games still play.",
                              "To revoke it: itch.io → Settings → API keys."],
                             "Sign out", self._disconnect_itch)
        elif not isinstance(act, tuple):
            sc.handle(act)
