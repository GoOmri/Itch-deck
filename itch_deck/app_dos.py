"""Your own DOS games (Settings -> Storage -> DOS games): the dos folder next to your other games is
scanned at start, on Refresh (Y) and from the "Add DOS games" box. Mixed into App (app.py)."""
import logging
import threading

from . import config

log = logging.getLogger("scritch")


class DosMixin:
    dos_busy = False
    dos_note = None

    def _dos_row(self):
        """Settings row: ("DOS games", "SD card · 3 games", "Folder: scritch/dos")."""
        root = self.inst.dos_root()
        n = sum(1 for i in self.inst.index.values() if i.get("store") == "dos")
        where = "SD card" if config.on_card(root) else "Internal"
        miss = " (missing)" if config.card_missing(root) else ""
        return ("DOS games", f"{where}{miss} \u00b7 {n} game{'' if n == 1 else 's'}",
                f"Folder: {root.parent.name}/dos")

    def _start_dos_scan(self, create=False, tell=False):
        """Scan the dos folder in the background. create: make the folder; tell: say what was found."""
        if self.dos_busy:
            return
        self.dos_busy = True

        def work():
            note = {"n": None, "tell": tell}
            try:
                note["n"] = self.inst.sync_dos(create=create)
            except Exception:  # noqa: BLE001
                log.exception("dos scan failed")
            finally:
                self.dos_busy = False
            self.dos_note = note
        threading.Thread(target=work, daemon=True, name="dos-scan").start()

    def _dos_tick(self, now):
        note, self.dos_note = self.dos_note, None
        if note is None:
            return
        if self.kind == "settings":
            self.scene.v["dos_row"] = self._dos_row()
        if not note["tell"]:
            return
        n = note["n"]
        if n is None:
            self.say("Couldn't read the DOS folder. Is the SD card in?", error=True)
        elif n == 0:
            self.say("No DOS games found. Copy a game folder into the dos folder.")
        else:
            self.say(f"{n} DOS game{'' if n == 1 else 's'} found.")

    def _dos_howto(self):
        """A on Settings -> DOS games."""
        root = self.inst.dos_root()
        drive = "SD card" if config.on_card(root) else "internal storage"
        self.confirm("Add DOS games",
                     [f"Copy game folders or .zip files into {root.parent.name}/dos",
                      f"on your {drive}, then press Refresh."],
                     "Refresh", lambda: self._start_dos_scan(create=True, tell=True), main=True)
