"""Manage games (Settings -> Storage -> Manage games): tick installed games and uninstall them together.
See storagemgr.py. Mixed into App (app.py)."""
import logging
import time

from . import config, storagemgr
from .input import B, X

log = logging.getLogger("scritch")


class StorageMixin:
    def go_storage(self):
        from .ui.scenes.storage import StorageManager
        sort = self.cfg.get("storage_sort", "size")
        if sort not in dict(storagemgr.SORTS):
            sort = "size"
        self._storage_next = time.time() + 2
        self._set("storage", StorageManager(self.t, storagemgr.entries(self.lib.games, self.inst.index),
                                            storagemgr.drives(), sort=sort))

    def _h_storage(self, act):
        sc = self.scene
        if act == B:
            self.go_settings()
        elif act == X:
            if sc.selected:
                ids = sorted(sc.selected)
                n, mb = len(ids), sc.selected_mb()
                self.confirm(f"Uninstall {n} game{'' if n == 1 else 's'}?",
                             [f"Frees about {storagemgr.mb_text(mb)}.", "Windows saves are kept."],
                             "Uninstall", lambda: self._storage_uninstall(ids))
            else:
                self.say("Tick games with A first.")
        else:
            before = sc.sort
            sc.handle(act)
            if sc.sort != before:                                 # remembered for next time
                self.cfg["storage_sort"] = sc.sort
                config.save(self.cfg)

    def _storage_uninstall(self, ids):
        """One after another; the folders are deleted in the background, so this is quick."""
        done = failed = freed = 0
        by_id = {e["id"]: e for e in self.scene.items}
        for gid in ids:
            if self.inst.uninstall(gid):
                done += 1
                freed += (by_id.get(gid) or {}).get("size_mb", 0)
            else:
                failed += 1                                       # e.g. the SD card is out
        log.info("storage: uninstalled %d, failed %d", done, failed)
        sc = self.scene
        sc.selected.clear()
        sc.set_items(storagemgr.entries(self.lib.games, self.inst.index))
        sc.drives = storagemgr.drives()
        if failed:
            self.say("Couldn't uninstall some games. Is the SD card in?", error=True)
        else:
            self.say(f"{done} game{'' if done == 1 else 's'} uninstalled. Freeing {storagemgr.mb_text(freed)}.")

    def _storage_tick(self, now):
        """The free space updates while the folders are being deleted in the background."""
        if self.kind != "storage" or now < getattr(self, "_storage_next", 0):
            return
        self._storage_next = now + 2
        self.scene.drives = storagemgr.drives()
