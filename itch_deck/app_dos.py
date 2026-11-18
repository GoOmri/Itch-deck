"""Your own DOS games (Settings -> Storage -> DOS games): the dos folder next to your other games is
scanned at start, on Refresh (Y) and from the "Add DOS games" box. The scan (disk reads, zip unpacking)
runs in a thread; its result is applied here on the main thread (_dos_tick). Mixed into App (app.py)."""
import logging
import threading

from . import config

log = logging.getLogger("scritch")


class DosMixin:
    dos_busy = False
    dos_note = None
    dos_queued = None

    def _dos_row(self):
        """Settings row: ("DOS games", "SD card · 3 games", "Folder: scritch/dos")."""
        root = self.inst.dos_root()
        n = sum(1 for i in list(self.inst.index.values()) if i.get("store") == "dos")
        where = "SD card" if config.on_card(root) else "Internal"
        miss = " (missing)" if config.card_missing(root) else ""
        return ("DOS games", f"{where}{miss} \u00b7 {n} game{'' if n == 1 else 's'}",
                f"Folder: {root.parent.name}/dos")

    def _start_dos_scan(self, create=False, tell=False):
        """Scan the dos folder in the background. create: make the folder; tell: say what was found.
        Asked again while a scan runs (Refresh right after start): it runs once more afterwards."""
        if self.dos_busy:
            q = self.dos_queued or (False, False)
            self.dos_queued = (q[0] or create, q[1] or tell)
            return
        self.dos_busy = True

        def work():
            note = {"result": None, "tell": tell, "failed": False}
            try:
                note["result"] = self.inst.scan_dos(create=create)
            except Exception:  # noqa: BLE001
                log.exception("dos scan failed")
                note["failed"] = True
            self.dos_note = note
        threading.Thread(target=work, daemon=True, name="dos-scan").start()

    def _dos_tick(self, now):
        note, self.dos_note = self.dos_note, None
        if note is None:
            return
        n = None if note["failed"] else self.inst.apply_dos(note["result"])
        self.dos_busy = False
        if self.kind == "settings":
            self.scene.v["dos_row"] = self._dos_row()
        if note["tell"] and n:                   # the Refresh button: ask GOG for art again (once a day at most)
            self.lib.queue_dosart(force=True)
        if note["tell"]:
            if n is None:
                self.say("Couldn't read the DOS folder. Is the SD card in?", error=True)
            elif n == 0:
                self.say("No DOS games found. Copy a game folder into the dos folder.")
            else:
                self.say(f"{n} DOS game{'' if n == 1 else 's'} found.")
        q, self.dos_queued = self.dos_queued, None
        if q:
            self._start_dos_scan(create=q[0], tell=q[1])

    def _dos_howto(self):
        """A on Settings -> DOS games."""
        root = self.inst.dos_root()
        drive = "SD card" if config.on_card(root) else "internal storage"
        self.confirm("Add DOS games",
                     [f"Copy game folders or .zip files into {root.parent.name}/dos",
                      f"on your {drive}, then press Refresh."],
                     "Refresh", lambda: self._start_dos_scan(create=True, tell=True), main=True)
