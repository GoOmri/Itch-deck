"""Self-update from GitHub Releases. Download next to the binary, swap it in (Linux keeps the
running file open, so renaming is safe), keep itch-deck.old for one rollback, restart via exec."""
import logging
import os
import re
import sys
import threading
from pathlib import Path

from . import net

log = logging.getLogger("itch-deck")
LATEST = "https://api.github.com/repos/GoOmri/Itch-deck/releases/latest"
ASSET = "itch-deck"


def _ver(s):
    return tuple(int(x) for x in re.findall(r"\d+", s or "")[:3]) or (0,)


class Updater:
    """state: idle | checking | latest | available | downloading | ready | error | source"""

    def __init__(self, version):
        self.version = version
        self.exe = Path(sys.executable) if getattr(sys, "frozen", False) else None
        self.state = "idle" if self.exe else "source"
        self.new_version, self.url, self.frac, self.error = None, None, 0.0, None

    def label(self):
        v = self.version
        return {
            "idle": f"v{v} · A to check",
            "checking": f"v{v} · checking…",
            "latest": f"v{v} · up to date",
            "available": f"v{self.new_version} available · A to download",
            "downloading": f"Downloading v{self.new_version} · {int(self.frac * 100)}%",
            "ready": f"v{self.new_version} installed · A to restart",
            "error": f"v{v} · {self.error or 'update failed'} · A to retry",
            "source": f"v{v} · running from source",
        }[self.state]

    def row_value(self):
        """Settings row: (info text, purple button label or None). A presses the button."""
        v, n = self.version, self.new_version
        return {
            "idle": (f"v{v}", "Check"),
            "checking": (f"v{v} · checking…", None),
            "latest": (f"v{v} · up to date", None),
            "available": (f"v{n} available", "Update"),
            "downloading": (f"Downloading v{n} · {int(self.frac * 100)}%", None),
            "ready": (f"v{n} installed", "Restart"),
            "error": (f"v{v} · {self.error or 'update failed'}", "Retry"),
            "source": (f"v{v} · running from source", None),
        }[self.state]

    def busy(self):
        return self.state in ("checking", "downloading")

    def check(self, quiet=False):
        if self.state in ("source", "checking", "downloading", "ready"):
            return
        self.state = "checking"
        threading.Thread(target=self._check, args=(quiet,), daemon=True, name="update").start()

    def _check(self, quiet):
        try:
            rel = net.get_json(LATEST, timeout=15)
            asset = next((a for a in rel.get("assets", []) if a.get("name") == ASSET), None)
            tag = rel.get("tag_name", "")
            if asset and _ver(tag) > _ver(self.version):
                self.new_version, self.url = tag.lstrip("v"), asset["browser_download_url"]
                self.state = "available"
            else:
                self.state = "latest"
            log.info("update check: latest=%s current=%s -> %s", tag, self.version, self.state)
        except Exception as e:  # noqa: BLE001
            log.info("update check failed: %s", e)
            self.state, self.error = ("idle", None) if quiet else ("error", "can't reach GitHub")

    def download(self):
        if self.state != "available":
            return
        self.state, self.frac = "downloading", 0.0
        threading.Thread(target=self._download, daemon=True, name="update").start()

    def _download(self):
        new = self.exe.with_name(self.exe.name + ".new")
        old = self.exe.with_name(self.exe.name + ".old")
        try:
            net.download(self.url, new, progress=lambda f: setattr(self, "frac", f))
            if new.stat().st_size < 5_000_000:
                raise ValueError("download too small")
            os.chmod(new, 0o755)
            if old.exists():
                old.unlink()
            os.replace(self.exe, old)        # running binary stays open under the new name
            os.replace(new, self.exe)
            self.state = "ready"
            log.info("update: v%s installed, previous kept as %s", self.new_version, old.name)
        except Exception as e:  # noqa: BLE001
            log.warning("update download failed: %s", e)
            self.state, self.error = "error", "download failed"
            for p in (new, new.with_name(new.name + ".part")):
                try:
                    p.unlink()
                except OSError:
                    pass

    def restart(self, pg):
        """Replace this process with the new binary (Steam keeps tracking the same PID)."""
        log.info("restarting into v%s", self.new_version)
        pg.quit()
        env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")  # new onefile unpacks fresh
        os.execve(str(self.exe), [str(self.exe), *sys.argv[1:]], env)
