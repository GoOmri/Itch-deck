"""Manage games (Settings -> Storage -> Manage games, v0.9.24, Omri 17 Nov): the installed games by size, tick several with
the pad and uninstall them in one go to free space on the SD card. Pure data helpers, no pygame.

Own DOS games are left out (Remove from library only forgets them, their files stay, so nothing would be freed).
Uninstalling uses Installer.uninstall, with its safety checks (only folders inside the games folders are deleted).
Windows games keep their saves (the Proton prefix stays, see Settings -> Old save data)."""
import shutil
from pathlib import Path

from . import config, paths

SORTS = (("size", "Size"), ("az", "A-Z"), ("played", "Last played"))


def mb_text(mb):
    """1234 -> '1.2 GB', 500 -> '500 MB'."""
    return f"{mb / 1000:.1f} GB" if mb >= 1000 else f"{int(mb)} MB"


def entries(games, index):
    """The games that can be uninstalled here: installed (not just missing), not your own DOS games.
    [{"id", "title", "size_mb", "drive", "played"}]; size comes from the install record."""
    out = []
    for g in games:
        info = index.get(g["id"])
        if not info or g.get("state") != "installed" or info.get("store") == "dos":
            continue
        mb = g.get("size_mb")
        if not mb:
            mb = int(info.get("size") or 0) // 1_000_000
        out.append({"id": g["id"], "title": g.get("title") or g["id"], "size_mb": int(mb),
                    "drive": "SD card" if config.on_card(info["dir"]) else "Internal",
                    "played": g.get("played") or ""})
    return out


def ordered(items, sort="size"):
    """The list in the chosen order: size (largest first), A-Z, last played (never played last)."""
    if sort == "az":
        return sorted(items, key=lambda e: e["title"].lower())
    if sort == "played":
        return sorted(items, key=lambda e: (not e["played"], _neg(e["played"]), e["title"].lower()))
    return sorted(items, key=lambda e: (-e["size_mb"], e["title"].lower()))


def _neg(text):
    """Sort key that puts the NEWEST timestamp first (timestamps are ISO text)."""
    return tuple(-ord(c) for c in text)


def total_mb(items, ids=None):
    return sum(e["size_mb"] for e in items if ids is None or e["id"] in ids)


def drives():
    """[{"name", "free", "total"}] in bytes: the SD card (when one is in) and internal storage."""
    out = []
    sd = config.sd_card()
    for name, path in (("SD card", sd), ("Internal storage", paths.HOME)):
        if path is None:
            continue
        try:
            u = shutil.disk_usage(Path(path))
            out.append({"name": name, "free": u.free, "total": u.total})
        except OSError:
            pass
    return out
