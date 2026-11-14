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
    tmp = paths.CONFIG_FILE.with_suffix(".tmp")
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
