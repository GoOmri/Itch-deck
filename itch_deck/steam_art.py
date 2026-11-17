"""SCRiTCH sets its own Steam art (v0.9.4, Omri 16 Nov: "Ready to share" item pulled forward).

On start (background thread): find SCRiTCH's own non-Steam shortcut in every Steam user's
config/shortcuts.vdf (binary VDF; the entry whose Exe is our launcher), then copy the art that
ships in the release (packaging/steam-art -> bundled as steam-art/) into that user's
config/grid/ as Steam names it:
    <appid>p.png  tile        <appid>.png  wide tile
    <appid>_hero.png          <appid>_logo.png
Rules:
- shortcuts.vdf is only READ (Steam rewrites it while running).
- Never overwrite: a name that exists with any picture extension (the player's own art,
  SteamGridDB's) is skipped.
- Once per shortcut: done ones are remembered in DATA/steam_art.json, so art the player
  removes on purpose doesn't come back.
- The icon isn't read from grid/ by Steam (it's the shortcut's own "icon" key): icon.png is
  copied next to the launcher as scritch-icon.png for the player to pick (README).
Steam may show new grid art only after a restart / going back to Game Mode."""
import json
import logging
import os
import shutil
import struct
import sys
from pathlib import Path

from . import paths

log = logging.getLogger("scritch")

ART = {"tile.png": "{}p", "wide-tile.png": "{}", "hero.png": "{}_hero", "logo.png": "{}_logo"}
PICTURE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")
ICON_NAME = "scritch-icon.png"
OUR_NAMES = ("scritch", "itch-deck")          # launcher file names (old tile: itch-deck)


def art_dir():
    """Where the release keeps the art: bundled steam-art/ (frozen), packaging/ in the source."""
    base = getattr(sys, "_MEIPASS", None)
    if base and (Path(base) / "steam-art").is_dir():
        return Path(base) / "steam-art"
    return Path(__file__).resolve().parents[1] / "packaging" / "steam-art"


def steam_roots(home=None):
    home = Path(home or paths.HOME)
    seen, out = set(), []
    for p in (home / ".local/share/Steam", home / ".steam/steam", home / ".steam/root"):
        try:
            r = p.resolve()
        except OSError:
            continue
        if r.is_dir() and r not in seen:
            seen.add(r)
            out.append(r)
    return out


# --- binary VDF (shortcuts.vdf) -------------------------------------------------
def read_vdf(data):
    """Binary VDF -> nested dicts. Types: 0 map, 1 string, 2 int32, 7 uint64, 8 end."""
    pos = 0

    def cstr():
        nonlocal pos
        end = data.index(b"\x00", pos)
        s = data[pos:end].decode("utf-8", "replace")
        pos = end + 1
        return s

    def node():
        nonlocal pos
        out = {}
        while pos < len(data):
            t = data[pos]
            pos += 1
            if t == 8:
                return out
            key = cstr()
            if t == 0:
                out[key] = node()
            elif t == 1:
                out[key] = cstr()
            elif t == 2:
                out[key] = struct.unpack_from("<i", data, pos)[0]
                pos += 4
            elif t == 7:
                out[key] = struct.unpack_from("<Q", data, pos)[0]
                pos += 8
            else:
                raise ValueError(f"unknown VDF type {t} at {pos - 1}")
        return out
    return node()


def _get(d, key):
    """Steam writes keys in different cases over the years (appid / AppName / Exe / exe)."""
    low = key.lower()
    return next((v for k, v in d.items() if k.lower() == low), None)


def _is_ours(exe, launcher):
    exe = (exe or "").strip().strip('"')
    if not exe:
        return False
    if launcher:
        try:
            return Path(exe).resolve() == Path(launcher).resolve()
        except OSError:
            return False
    return Path(exe).name in OUR_NAMES          # running without a launcher (tests / source)


def find_shortcuts(roots, launcher):
    """[(userdata/<user> dir, unsigned appid)] for every shortcut that starts SCRiTCH."""
    found = []
    for root in roots:
        for user in sorted((root / "userdata").glob("*")):
            f = user / "config" / "shortcuts.vdf"
            if not f.is_file():
                continue
            try:
                tree = read_vdf(f.read_bytes())
            except (OSError, ValueError, IndexError, struct.error) as e:
                log.info("steam art: can't read %s: %s", f, e)
                continue
            for entry in (_get(tree, "shortcuts") or {}).values():
                if isinstance(entry, dict) and _is_ours(_get(entry, "exe"), launcher) \
                        and not str(_get(entry, "LaunchOptions") or "").startswith("--play"):
                    appid = _get(entry, "appid")
                    if isinstance(appid, int) and appid:
                        found.append((user, appid & 0xFFFFFFFF))
    return found


def _exists(grid, stem):
    return any((grid / (stem + ext)).exists() for ext in PICTURE_EXT)


def apply(launcher=None, roots=None, src=None):
    """Copy the art for every SCRiTCH shortcut not done before. Returns names written."""
    src = Path(src or art_dir())
    if not src.is_dir():
        log.info("steam art: no art in this build (%s)", src)
        return []
    done_file = paths.DATA / "steam_art.json"
    try:
        done = json.loads(done_file.read_text())
    except (OSError, ValueError):
        done = []
    written = []
    for user, appid in find_shortcuts(roots if roots is not None else steam_roots(), launcher):
        tag = f"{user.name}/{appid}"
        if tag in done:
            continue
        grid = user / "config" / "grid"
        try:
            grid.mkdir(parents=True, exist_ok=True)
            for name, pattern in ART.items():
                stem = pattern.format(appid)
                if not (src / name).is_file() or _exists(grid, stem):
                    continue
                tmp = grid / (stem + ".png.scritch-tmp")
                shutil.copyfile(src / name, tmp)
                os.replace(tmp, grid / (stem + ".png"))
                written.append(stem + ".png")
        except OSError as e:
            log.info("steam art: can't write to %s: %s", grid, e)
            continue
        done.append(tag)
        log.info("steam art: shortcut %s -> %s", tag, ", ".join(written) or "nothing (art already set)")
    if launcher and (src / "icon.png").is_file():   # for the player to pick in Properties
        icon = Path(launcher).parent / ICON_NAME
        if not icon.exists():
            try:
                shutil.copyfile(src / "icon.png", icon)
            except OSError as e:
                log.info("steam art: icon not copied: %s", e)
    try:
        done_file.parent.mkdir(parents=True, exist_ok=True)
        done_file.write_text(json.dumps(done))
    except OSError:
        pass
    return written


def apply_in_background():
    """Called once at start: never in the way, never fatal. Only in a real build (launcher)."""
    from .updater import launcher_path
    launcher = launcher_path()
    if launcher is None:
        return

    def work():
        try:
            apply(launcher)
        except Exception:  # noqa: BLE001
            log.exception("steam art failed")
    import threading
    threading.Thread(target=work, daemon=True, name="steam-art").start()
