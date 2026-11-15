"""Settings + API key in ~/.config/itch-deck/config.json (chmod 600). The key is never logged."""
import json
import logging
import os
from pathlib import Path

from . import paths

log = logging.getLogger("itch-deck")
DEFAULTS = {"api_key": None, "install_root": None, "proton": None}


def load():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(paths.CONFIG_FILE.read_text()))
    except FileNotFoundError:
        pass
    except Exception as e:  # noqa: BLE001
        log.warning("config unreadable (%s), using defaults", type(e).__name__)
    return cfg


def save(cfg):
    paths.CONFIG.mkdir(parents=True, exist_ok=True)
    tmp = paths.tmp_for(paths.CONFIG_FILE)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(cfg, f, indent=1)
    os.chmod(tmp, 0o600)
    os.replace(tmp, paths.CONFIG_FILE)


def sd_card():
    """First mounted SD card (SteamOS mounts it under /run/media/<user>/<label>)."""
    base = Path("/run/media")
    try:
        for d in sorted(base.glob("*/*")) + sorted(base.glob("*")):
            if d.is_dir() and os.path.ismount(d):
                return d
    except OSError:
        pass
    return None


MEDIA = Path("/run/media")


def on_card(path):
    """True if path lives on removable media (SteamOS mounts the SD card under /run/media)."""
    try:
        Path(path).relative_to(MEDIA)
        return True
    except ValueError:
        return False


def card_missing(path):
    """On removable media whose card isn't mounted. Never mkdir there: /run/media is a tmpfs,
    so files would land in RAM/internal storage instead of on the card."""
    if not on_card(path):
        return False
    p = Path(path)
    for a in [p, *p.parents]:
        if a == MEDIA:
            return True
        try:
            if os.path.ismount(a):
                return False
        except OSError:
            return True
    return True


def drive_name(path):
    return "SD card" if on_card(path) else "internal storage"


def pin_install_root(cfg, installed_dirs=()):
    """Remember the SD card as the install location the first time we see it (or infer it from
    games already installed on a card). Without this, a card that's out made installs quietly go
    to internal storage instead of failing with "SD card missing". True if cfg changed."""
    if cfg.get("install_root"):
        return False
    sd = sd_card()
    root = (sd / "itch") if sd else next((Path(d).parent for d in installed_dirs if on_card(d)), None)
    if root is None:
        return False
    cfg["install_root"] = str(root)
    return True


def install_choices():
    """Install locations Settings can switch between: the SD card (when one is in) and internal."""
    sd = sd_card()
    return ([("SD card", sd / "itch")] if sd else []) + \
        [("Internal storage", paths.HOME / "Games" / "itch")]


def install_root(cfg):
    if cfg.get("install_root"):
        return Path(cfg["install_root"])
    sd = sd_card()
    return (sd / "itch") if sd else (paths.HOME / "Games" / "itch")


def proton_versions():
    """GE-Proton folders, newest first."""
    try:
        found = [d.name for d in paths.STEAM_TOOLS.iterdir() if d.is_dir() and "proton" in d.name.lower()]
    except OSError:
        return []

    def key(n):
        import re
        return [int(x) for x in re.findall(r"\d+", n)] or [0]
    return sorted(found, key=key, reverse=True)
